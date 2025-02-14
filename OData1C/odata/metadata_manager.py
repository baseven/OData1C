import xml.etree.ElementTree as ET
from http import HTTPStatus
from typing import List, Dict, Tuple, Optional, Set, Any

from requests import Response

from OData1C.connection import Connection, ODataRequest
from OData1C.exceptions import ODataResponseError

MAX_RECURSION_DEPTH = 5


class MetadataManager:
    """
    High-level class for loading and accessing OData metadata from 1C.
    Provides the following public API methods:
      1) get_entity_sets() -> List[str]
      2) get_entity_types() -> List[str]
      3) get_properties(entity_type: str) -> List[Dict[str, Any]]
      4) reset_metadata() -> None
    """

    ODATA_NAMESPACE = "{http://schemas.microsoft.com/ado/2009/11/edm}"
    ODATA_BASE_PATH = "odata/standard.odata"
    METADATA_PATH = "$metadata"

    def __init__(self, connection: Connection, database_name: str) -> None:
        """
        :param connection: A pre-configured Connection instance with auth/session parameters.
        :param database_name: The 1C database name used to build the metadata URL.
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

    def get_properties(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Returns a list of properties for the given EntityType name.
        Each property is a dictionary with keys such as "name" and "type".
        If a property is a Collection (a reference to another entity type),
        its properties will be recursively expanded.
        """
        self._ensure_metadata_loaded()
        return self._expand_properties(entity_type)

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
        Lazy-loading mechanism: loads metadata if it has not been loaded yet.
        """
        if not self._is_metadata_loaded:
            self._load_and_parse_metadata()

    # TODO: Implement JSON parsing if the 1C OData endpoint provides JSON-based metadata.
    def _load_and_parse_metadata(self) -> None:
        """
        Fetches and parses the raw XML metadata from the server,
        initializing internal data structures.
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
        Builds the relative URL for fetching metadata.
        Example: "database_name/odata/standard.odata/$metadata"
        """
        return f"{self._database_name}/{self.ODATA_BASE_PATH}/{self.METADATA_PATH}"

    @staticmethod
    def _check_response(response: Response, expected_status: int) -> None:
        """
        Raises an error if the response status code is not as expected.
        """
        if response.status_code != expected_status:
            raise ODataResponseError(
                status_code=response.status_code,
                reason=response.reason,
                details=response.text
            )

    def _fetch_metadata_xml(self) -> str:
        """
        Retrieves the metadata XML from the OData endpoint.
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
        Parses the XML tree and returns:
          - A list of EntitySet names.
          - A list of EntityType names.
          - A mapping of EntityType names to their property dictionaries.
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

    def _expand_properties(
            self,
            entity_type: str,
            depth: int = 0,
            visited: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recursively expands properties of the given EntityType, including nested collections.

        :param entity_type: The name of the EntityType to expand.
        :param depth: Current recursion depth.
        :param visited: Set of already visited entity types to prevent circular references.
        :return: A list of property dictionaries, with nested collections expanded.
        """
        if visited is None:
            visited = set()

        if entity_type in visited or depth > MAX_RECURSION_DEPTH:
            return []

        visited.add(entity_type)

        properties = self._entity_type_properties.get(entity_type, [])
        expanded_properties = []

        for prop in properties:
            expanded_properties.append(prop)

            related_type = self._get_related_type(prop.get("type", ""))
            if related_type and related_type in self._entity_type_properties:
                expanded_properties.append({
                    "name": f"{prop['name']} (expanded)",
                    "type": "Collection",
                    "depth": depth + 1,
                    "properties": self._expand_properties(related_type, depth + 1, visited)
                })

        return expanded_properties

    def _get_related_type(self, type_str: str) -> Optional[str]:
        """
        Extracts and returns the name of the related entity from a collection type string.
        Example:
            "Collection(namespace.Entity_RowType)" -> "Entity"
        """
        if type_str.startswith("Collection(") and type_str.endswith(")"):
            content = type_str[len("Collection("):-1]
            related = content.split('.')[-1]
            return related.replace("_RowType", "")
        return None
