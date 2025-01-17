import xml.etree.ElementTree as ET
from typing import List, Dict, Optional

from requests import Request
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from OData1C.connection import Connection
from OData1C.exceptions import ODataConnectionError


class MetadataManager:
    """
    A class for working with $metadata in 1C OData (using caching + "acceleration"):
    - On the first load, it fetches and parses the XML, storing data about:
      (1) EntitySets: a list of available sets
      (2) EntityTypes: a dict containing each EntityType's fields (Properties)
    - Subsequent calls retrieve data from in-memory structures instead of re-parsing XML every time.
    """

    NAMESPACE = "{http://schemas.microsoft.com/ado/2009/11/edm}"
    ODATA_PATH = "odata/standard.odata"

    def __init__(self, connection: Connection, database: str) -> None:
        """
        :param connection: A pre-configured Connection instance.
        :param database: The database name, e.g. "zup-demo",
                         resulting in a URL pattern like:
                         https://<host>/<database>/odata/standard.odata/$metadata
        """
        self.connection = connection
        self.database = database

        # Cached root of the metadata XML (for debugging or advanced usage)
        self._cached_metadata_root: Optional[ET.Element] = None

        # "Accelerated" structures:
        # - A list of entity set names (e.g. ["Catalog_ФизическиеЛица", "Document_ЗаявкаНаПодборПерсонала", ...])
        self._entity_sets_list: Optional[List[str]] = None

        # - A dict mapping EntityType name -> list of properties
        #   Example: {"Catalog_ФизическиеЛица": [{"name": "Ref_Key", "type": "Edm.Guid"}, ...], ...}
        self._entity_types_dict: Optional[Dict[str, List[Dict[str, str]]]] = None

    def _ensure_metadata_loaded(self) -> None:
        """
        Ensures that metadata has been fetched and parsed.
        If not loaded, triggers a fetch from the OData endpoint.
        """
        if self._cached_metadata_root is not None:
            return  # Already loaded

        raw_xml = self._fetch_metadata()
        root = ET.fromstring(raw_xml)
        self._cached_metadata_root = root

        # Build our accelerated structures right away
        self._parse_and_store(root)

    def _fetch_metadata(self) -> str:
        """
        Performs a GET request to .../$metadata and returns the raw XML response as a string.
        """
        url = f"{self.connection.base_url}{self.database}/{self.ODATA_PATH}/$metadata"
        session = self.connection._session or self.connection._create_session()

        raw_request = Request(
            method='GET',
            url=url,
            headers={"Accept": "application/xml"}
        )
        prepared_request = session.prepare_request(raw_request)

        try:
            response = session.send(
                prepared_request,
                timeout=(self.connection.connection_timeout, self.connection.read_timeout)
            )
            response.raise_for_status()
            return response.text
        except (RequestsConnectionError, Timeout) as e:
            raise ODataConnectionError(f"Error while fetching metadata: {e}") from e
        finally:
            if self.connection._session is None:
                session.close()

    def _parse_and_store(self, root: ET.Element) -> None:
        """
        Parses the XML tree once and populates:
          - self._entity_sets_list
          - self._entity_types_dict
        """
        entity_sets: List[str] = []
        entity_types_dict: Dict[str, List[Dict[str, str]]] = {}

        # Collect entity sets
        for es in root.findall(f".//{self.NAMESPACE}EntitySet"):
            es_name = es.get("Name")
            if es_name:
                entity_sets.append(es_name)

        # Collect entity types and their properties
        for et in root.findall(f".//{self.NAMESPACE}EntityType"):
            et_name = et.get("Name")
            if not et_name:
                continue

            props: List[Dict[str, str]] = []
            for prop in et.findall(f".//{self.NAMESPACE}Property"):
                p_name = prop.get("Name")
                p_type = prop.get("Type")
                props.append({"name": p_name, "type": p_type})

            entity_types_dict[et_name] = props

        self._entity_sets_list = entity_sets
        self._entity_types_dict = entity_types_dict

    def reload_metadata(self) -> None:
        """
        Forces a reload of the metadata (and re-parsing).
        """
        self._cached_metadata_root = None
        self._entity_sets_list = None
        self._entity_types_dict = None
        self._ensure_metadata_loaded()

    def list_entity_types(self) -> List[str]:
        """
        Returns a list of all EntityType names (keys in _entity_types_dict).
        """
        self._ensure_metadata_loaded()
        return list(self._entity_types_dict.keys())

    def list_entity_sets(self) -> List[str]:
        """
        Returns a list of EntitySet names collected from the metadata.
        """
        self._ensure_metadata_loaded()
        return self._entity_sets_list or []

    def get_properties_for_entity_type(self, entity_type_name: str) -> List[Dict[str, str]]:
        """
        Returns the pre-built list of properties for a given EntityType name.
        Example return format: [{"name": "Ref_Key", "type": "Edm.Guid"}, ...]
        """
        self._ensure_metadata_loaded()
        if not self._entity_types_dict:
            return []
        return self._entity_types_dict.get(entity_type_name, [])
