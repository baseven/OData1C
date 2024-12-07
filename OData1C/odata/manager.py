from http import HTTPStatus
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from requests import Response

from OData1C.connection import Connection, ODataRequest
from OData1C.exceptions import ODataError, ODataResponseError
from OData1C.models import ODataModel
from OData1C.odata.query import Q

OM = TypeVar("OM", bound=ODataModel)


class OData:
    """
    Base class for defining an OData entity.

    Subclasses must specify:
    - database (str): The OData service root or database name.
    - entity_model (Type[OM]): A Pydantic model representing the entity schema.
    - entity_name (str): The OData entity set name.

    Once defined, you can create an ODataManager instance via `manager()` to perform
    queries and operations on the entity.
    """

    database: str
    entity_model: Type[OM]
    entity_name: str

    @classmethod
    def manager(cls, connection: Connection) -> "ODataManager[OM]":
        """
        Creates and returns an ODataManager instance for this OData entity.

        Args:
            connection (Connection): The connection used to send HTTP requests.

        Raises:
            AttributeError: If `entity_model` or `entity_name` are not defined.

        Returns:
            ODataManager[OM]: A manager instance for querying and operating on the entity.
        """
        if not hasattr(cls, "entity_model") or not hasattr(cls, "entity_name"):
            raise AttributeError("OData subclass must define 'entity_model' and 'entity_name'.")
        return ODataManager(cls, connection)


class ODataManager(Generic[OM]):
    """
    ODataManager handles querying and retrieving data for a specific OData entity.

    It allows building OData queries by setting filters (`filter()`), expansions (`expand()`),
    and pagination (`top()`, `skip()`), then executing the query with methods like `all()`.
    The manager sends requests, validates responses, and returns typed model instances.
    """

    odata_path = "odata/standard.odata"
    odata_list_json_key = "value"

    def __init__(self, odata_class: Type[OData], connection: Connection):
        """
        Initializes a new ODataManager instance.

        Args:
            odata_class (Type[OData]): The OData subclass defining database, entity_model, and entity_name.
            connection (Connection): The connection used to communicate with the OData service.
        """
        self.odata_class = odata_class
        self.connection = connection
        self.request: Optional[ODataRequest] = None
        self.response: Optional[Response] = None
        self.validation_errors: List[Exception] = []
        self._expand_fields: Optional[List[str]] = None
        self._filter_conditions: Optional[Q] = None
        self._skip: Optional[int] = None
        self._top: Optional[int] = None

    def all(self, ignore_invalid: bool = False) -> List[OM]:
        """
        Executes an OData GET request and returns a list of entity instances.

        This method constructs the OData query based on current filters, expansions, top/skip settings,
        sends the request, checks the response, parses it, and validates the data.

        Args:
            ignore_invalid (bool): If True, invalid items are skipped and stored in `validation_errors`.
                                   If False, the first validation error raises an exception.

        Returns:
            List[OM]: A list of validated model instances corresponding to the OData entities.
        """
        query_params = self._prepare_query_params()
        self.request = ODataRequest(
            method="GET", relative_url=self.get_url(), query_params=query_params
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        data = self._parse_response()
        return self._validate_data(data, ignore_invalid)

    def filter(self, *args: Q, **kwargs: Any) -> "ODataManager[OM]":
        """
        Applies filtering conditions to the OData query.

        You can pass Q objects as positional arguments or key-value pairs
        like `name='Ivanov'` or `age__gt=30`. If a filter already exists,
        the new conditions are combined with the existing ones using logical AND.

        Returns:
            ODataManager[OM]: The manager instance to allow method chaining.
        """
        q_obj = Q(*args, **kwargs)
        if self._filter_conditions:
            self._filter_conditions &= q_obj
        else:
            self._filter_conditions = q_obj
        return self

    def expand(self, *fields: str) -> "ODataManager[OM]":
        """
        Specifies related fields to expand in the OData response.

        For example, `manager.expand('measure_unit', 'nomenclature_type')` will include
        those nested entities in the response, if supported.

        Args:
            *fields (str): Names of fields to expand.

        Returns:
            ODataManager[OM]: The manager instance, allowing method chaining.
        """
        self._expand_fields = list(fields)
        return self

    def top(self, n: int) -> "ODataManager[OM]":
        """
        Limits the number of entities returned by specifying the OData $top option.

        Args:
            n (int): The maximum number of records to return.

        Returns:
            ODataManager[OM]: The manager instance, allowing method chaining.
        """
        self._top = n
        return self

    def skip(self, n: int) -> "ODataManager[OM]":
        """
        Skips a specified number of entities using the OData $skip option.

        Args:
            n (int): The number of records to skip.

        Returns:
            ODataManager[OM]: The manager instance, allowing method chaining.
        """
        self._skip = n
        return self

    def get_url(self) -> str:
        """
        Constructs the base URL for the OData entity set.

        Returns:
            str: The base URL of the OData entity set.
        """
        return f"{self.odata_class.database}/{self.odata_path}/{self.odata_class.entity_name}"

    def _prepare_query_params(self) -> Dict[str, Any]:
        """
        Prepares OData query parameters based on current filters, expansions, top, and skip settings.

        Returns:
            Dict[str, Any]: A dictionary of OData query parameters.
        """
        params = {}
        if self._expand_fields:
            params["$expand"] = ",".join(self._expand_fields)
        if self._filter_conditions:
            params["$filter"] = str(self._filter_conditions)
        if self._top is not None:
            params["$top"] = str(self._top)
        if self._skip is not None:
            params["$skip"] = str(self._skip)
        return params

    def _check_response(self, expected_status: int) -> None:
        """
        Checks if the HTTP response has the expected status code.

        Raises:
            ODataResponseError: If the status code is not as expected.
        """
        if self.response.status_code != expected_status:
            raise ODataResponseError(
                self.response.status_code, self.response.reason, self.response.text
            )

    def _parse_response(self) -> Any:
        """
        Parses the OData response JSON and extracts the entities data.

        Raises:
            ODataError: If the JSON cannot be parsed or the expected key is missing.

        Returns:
            Any: The parsed data, typically a list of entities.
        """
        try:
            return self.response.json()[self.odata_list_json_key]
        except (ValueError, KeyError) as e:
            raise ODataError(f"Error parsing response: {e}") from e

    def _validate_data(self, data: List[Dict[str, Any]], ignore_invalid: bool) -> List[OM]:
        """
        Validates the raw data against the entity model and returns a list of model instances.

        Args:
            data (List[Dict[str, Any]]): The raw entities data from the OData response.
            ignore_invalid (bool): If True, invalid items are skipped and stored in `validation_errors`.
                                   If False, an exception is raised on the first invalid item.

        Returns:
            List[OM]: A list of validated entity instances.
        """
        valid_objects = []
        for item in data:
            try:
                obj = self.odata_class.entity_model.model_validate(item)
                valid_objects.append(obj)
            except Exception as e:
                self.validation_errors.append(e)
                if not ignore_invalid:
                    raise e
        return valid_objects