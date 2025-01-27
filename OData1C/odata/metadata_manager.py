import xml.etree.ElementTree as ET
from http import HTTPStatus
from typing import List, Dict, Tuple

from requests import Response

from OData1C.connection import Connection, ODataRequest
from OData1C.exceptions import ODataResponseError


class MetadataManager:
    """
    High-level class for loading and accessing OData metadata from 1C.

    Provides four main operations (public API):
      1) get_entity_sets() -> List[str]
      2) get_entity_types() -> List[str]
      3) get_properties(entity_type: str) -> List[Dict[str, str]]
      4) reset_metadata() -> None (forces a full reset of metadata)

    Usage:
      - Create an instance with a Connection and database name.
      - Call any of the public methods to retrieve metadata.
      - If needed, call reset_metadata() to force clearing any cached data.
    """

    ODATA_NAMESPACE = "{http://schemas.microsoft.com/ado/2009/11/edm}"
    ODATA_BASE_PATH = "odata/standard.odata"
    METADATA_PATH = "$metadata"

    def __init__(self, connection: Connection, database_name: str) -> None:
        """
        :param connection:     A pre-configured Connection instance with auth/session params.
        :param database_name:  The 1C database name. Used in the final URL:
                               <protocol>://<host>/<database_name>/<ODATA_BASE_PATH>/<METADATA_PATH>
        """
        self._connection = connection
        self._database_name = database_name

        self._is_metadata_loaded = False

        self._entity_sets: List[str] = []
        self._entity_types: List[str] = []
        self._entity_type_properties: Dict[str, List[Dict[str, str]]] = {}

    def get_entity_sets(self) -> List[str]:
        """
        Returns a list of all EntitySet names parsed from the OData metadata.
        """
        self._ensure_metadata_loaded()
        return self._entity_sets

    def get_entity_types(self) -> List[str]:
        """
        Returns a list of all EntityType names parsed from the OData metadata.
        """
        self._ensure_metadata_loaded()
        return self._entity_types

    def get_properties(self, entity_type: str) -> List[Dict[str, str]]:
        """
        Returns a list of properties for the given EntityType name.
        Each property is a dict with keys {"name", "type"}.
        """
        self._ensure_metadata_loaded()
        return self._entity_type_properties.get(entity_type, [])

    def reset_metadata(self) -> None:
        """
        Forces a full reset of the metadata, clearing any cached data.
        """
        self._is_metadata_loaded = False
        self._entity_sets.clear()
        self._entity_types.clear()
        self._entity_type_properties.clear()

    def _ensure_metadata_loaded(self) -> None:
        """
        Lazy-loading mechanism. Checks if metadata is loaded:
        - If not, calls _load_and_parse_metadata to fetch and parse the data.
        """
        if not self._is_metadata_loaded:
            self._load_and_parse_metadata()

    def _load_and_parse_metadata(self) -> None:
        """
        Fetch the raw XML metadata from server and parse it into
        in-memory structures (_entity_sets, _entity_types, _entity_type_properties).
        After parsing, sets the flag `_is_metadata_loaded = True`.
        """
        xml_data = self._fetch_metadata_xml()
        root = ET.fromstring(xml_data)

        entity_sets, entity_types, entity_type_properties = self._parse_metadata_tree(root)
        self._entity_sets = entity_sets
        self._entity_types = entity_types
        self._entity_type_properties = entity_type_properties

        self._is_metadata_loaded = True

    def _build_metadata_url(self) -> str:
        """
        Build the relative URL that excludes the host/protocol but includes
        database_name, odata_base_path, and metadata_path.

        Example:
            "zup-demo/odata/standard.odata/$metadata"

        :return: A relative URL string to be appended to Connection.base_url
        """
        return f"{self._database_name}/{self.ODATA_BASE_PATH}/{self.METADATA_PATH}"

    @staticmethod
    def _check_response(response: Response, expected_status: int) -> None:
        """
        Raises ODataResponseError if response status does not match the expected status.

        :param response:   The Response object to check
        :param expected_status:  The expected HTTP status code (e.g., 200 for OK)
        :raises ODataResponseError: if status_code != expected_status
        """
        if response.status_code != expected_status:
            raise ODataResponseError(
                status_code=response.status_code,
                reason=response.reason,
                details=response.text
            )

    def _fetch_metadata_xml(self) -> str:
        """
        Performs an HTTP GET request to retrieve metadata XML from the OData endpoint,
        using the project-wide standard approach (Connection + ODataRequest).

        :return: The raw XML text from the OData $metadata endpoint
        """
        request = ODataRequest(
            method="GET",
            relative_url=self._build_metadata_url(),
        )
        response = self._connection.send_request(request)
        self._check_response(response, HTTPStatus.OK)
        return response.text

    def _parse_metadata_tree(
            self,
            root: ET.Element
    ) -> Tuple[List[str], List[str], Dict[str, List[Dict[str, str]]]]:
        """
        Parse the XML tree and return the extracted metadata structures:
          - entity_sets: list of EntitySet names
          - entity_types: list of EntityType names
          - entity_type_properties: mapping from EntityType name to a list of property dicts

        :param root: The root Element of the parsed XML document
        :return: (entity_sets, entity_types, entity_type_properties)
        """
        entity_sets = [
            es.get("Name") for es in root.findall(f".//{self.ODATA_NAMESPACE}EntitySet")
            if es.get("Name")
        ]

        entity_types: List[str] = []
        entity_type_properties: Dict[str, List[Dict[str, str]]] = {}

        for et in root.findall(f".//{self.ODATA_NAMESPACE}EntityType"):
            et_name = et.get("Name")
            if not et_name:
                continue

            entity_types.append(et_name)

            props = [
                {
                    "name": prop.get("Name"),
                    "type": prop.get("Type")
                }
                for prop in et.findall(f".//{self.ODATA_NAMESPACE}Property")
                if prop.get("Name") and prop.get("Type")
            ]
            entity_type_properties[et_name] = props

        return entity_sets, entity_types, entity_type_properties
