from http import HTTPStatus
from typing import Any, Iterable, TypeVar

from pydantic import ValidationError
from requests import Response

import requests.exceptions as r_exceptions

from OData1C.connection import Connection, ODataRequest
from OData1C.exceptions import ODataError, ODataResponseError
from OData1C.models import ODataModel
from OData1C.odata.query import Q


class EntityManager:
    """
    A manager for working with a specific entity in 1C OData.

    Key responsibilities:
      - Build relative URLs for the OData entity (e.g., 'zup-demo/odata/standard.odata/Catalog_ФизическиеЛица').
      - Perform CRUD operations (GET, POST, PATCH), handle documents posting/unposting if needed.
      - Validate incoming/outgoing data with a Pydantic model.

    Attributes:
    -----------
    connection : Connection
        An established HTTP connection to the OData service.
    database_name : str
        The name of the 1C database/service root (e.g. 'zup-demo').
    entity_name : str
        The OData entity set name (e.g. 'Catalog_ФизическиеЛица').
    entity_model : ODataModel
        A Pydantic-based model describing fields and validation rules.

    Methods Overview:
    -----------------
    - all() / fetch_all_records(): Retrieve multiple items from the entity set.
    - create(), get(), update(): Perform typical CRUD operations.
    - expand(), filter(), skip(), top(): Build OData query parameters.
    - post_document(), unpost_document(): Additional document-related operations (if needed).
    """

    odata_path = 'odata/standard.odata'
    odata_list_json_key = 'value'

    def __init__(
            self,
            connection: Connection,
            database_name: str,
            entity_name: str,
            entity_model: ODataModel
    ):
        """
        Parameters
        ----------
        connection : Connection
            An instance of Connection with the 1C OData service.
        database_name : str
            The database or service root name (e.g. 'zup-demo').
        entity_name : str
            The OData entity set name (e.g. 'Catalog_ФизическиеЛица').
        entity_model : ODataModel
            A Pydantic model describing the entity fields and validation.
        """
        self.connection = connection
        self.database_name = database_name
        self.entity_name = entity_name
        self.entity_model = entity_model

        self.request: ODataRequest | None = None
        self.response: Response | None = None
        self.validation_errors: list[ValidationError] = []

        # Internal OData query options
        self._expand: Iterable[str] | None = None
        self._filter: Q | None = None
        self._skip: int | None = None
        self._top: int | None = None

    def __str__(self) -> str:
        return f"EntityManager for {self.entity_name}"

    def _check_response(self, ok_status: int) -> None:
        """Raise an ODataResponseError if response status does not match the expected."""
        if self.response.status_code != ok_status:
            raise ODataResponseError(
                self.response.status_code,
                self.response.reason,
                self.response.text
            )

    def _validate_obj(self, obj: dict[str, Any], ignore_invalid: bool) -> ODataModel:
        """
        Validate a single record using the entity_model's model_validate.
        Accumulate validation errors if ignore_invalid=True.
        """
        try:
            return self.entity_model.model_validate(obj)
        except ValidationError as e:
            self.validation_errors.append(e)
            if not ignore_invalid:
                raise e

    def _validate_data(
            self,
            data: list[dict[str, Any]] | dict[str, Any],
            ignore_invalid: bool
    ):
        """
        Validate incoming JSON data (a list or a single record).
        Returns either a list of validated objects or a single validated object.
        """
        self.validation_errors = []
        if isinstance(data, list):
            results = []
            for item in data:
                results.append(self._validate_obj(item, ignore_invalid))
            return results
        return self._validate_obj(data, ignore_invalid)

    def _json(self) -> dict[str, Any]:
        """Return the parsed JSON from the HTTP response."""
        try:
            return self.response.json()
        except r_exceptions.JSONDecodeError as e:
            raise ODataError(e)

    @staticmethod
    def _to_dict(data: Any) -> dict[str, Any]:
        """
        Convert either a Pydantic-based ODataModel or a dict
        into a JSON-serializable dict with correct field aliases.
        """
        if isinstance(data, ODataModel):
            return data.model_dump(by_alias=True)
        return data

    def _build_base_url(self) -> str:
        """
        Build the relative URL that excludes the host/protocol but includes
        database_name, odata_path, and entity_name.

        Example:
            'zup-demo/odata/standard.odata/Catalog_ФизическиеЛица'
        """
        return f"{self.database_name}/{self.odata_path}/{self.entity_name}"

    def get_url(self) -> str:
        """
        Return the full relative URL for this entity set.

        Example:
            'zup-demo/odata/standard.odata/Catalog_ФизическиеЛица'
        """
        return self._build_base_url()

    def get_canonical_url(self, guid: str) -> str:
        """
        Return the canonical URL to fetch/update a specific record by GUID.

        Example:
            'zup-demo/odata/standard.odata/Catalog_ФизическиеЛица(guid'...')
        """
        return f"{self._build_base_url()}(guid'{guid}')"

    def all(self, ignore_invalid: bool = False):
        """
        Fetch all records from the entity set. If ignore_invalid=True,
        skip any objects that fail validation and store errors in self.validation_errors.

        Returns
        -------
        List of validated objects or empty list if none found.
        """
        self.request = ODataRequest(
            method="GET",
            relative_url=self.get_url(),
            query_params=self._prepare_query_params(
                self.qp_select,
                self.qp_expand,
                self.qp_top,
                self.qp_skip,
                self.qp_filter
            )
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)

        try:
            raw_data = self._json()[self.odata_list_json_key]
        except KeyError:
            raise ODataError(
                f"Response JSON has no key '{self.odata_list_json_key}'."
            )
        return self._validate_data(raw_data, ignore_invalid)

    def fetch_all_records(self, ignore_invalid: bool = False):
        """
        An alternative method name that does the same as .all().
        Demonstrates a possible approach for more "business-friendly" naming.
        """
        return self.all(ignore_invalid=ignore_invalid)

    def create(self, data: Any):
        """
        Create a new record in the entity set (HTTP POST).
        """
        self.request = ODataRequest(
            method='POST',
            relative_url=self.get_url(),
            data=self._to_dict(data)
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.CREATED)
        return self._validate_data(self._json(), ignore_invalid=False)

    def get(self, guid: str):
        """
        Fetch a single record by GUID (HTTP GET).
        """
        self.request = ODataRequest(
            method='GET',
            relative_url=self.get_canonical_url(guid),
            query_params=self._prepare_query_params(
                self.qp_select, self.qp_expand
            )
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        return self._validate_data(self._json(), ignore_invalid=False)

    def update(self, guid: str, data: Any):
        """
        Update (PATCH) an existing record identified by GUID.
        """
        self.request = ODataRequest(
            method='PATCH',
            relative_url=self.get_canonical_url(guid),
            data=self._to_dict(data),
            query_params=self._prepare_query_params(
                self.qp_select, self.qp_expand
            )
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        return self._validate_data(self._json(), ignore_invalid=False)

    # If needed, implement post_document / unpost_document similarly.

    @property
    def qp_select(self) -> tuple[str, str | None]:
        """
        Build the $select parameter from the model fields (including nested).
        """
        fields = self.entity_model.model_fields
        nested_models = self.entity_model.nested_models
        aliases = []
        for field_name, info in fields.items():
            alias = info.alias or field_name
            if nested_models and field_name in nested_models:
                # gather subfields
                for nf, ninfo in nested_models[field_name].model_fields.items():
                    nalias = ninfo.alias or nf
                    aliases.append(f"{alias}/{nalias}")
            else:
                aliases.append(alias)

        return ('$select', ", ".join(aliases) if aliases else None)

    @property
    def qp_expand(self) -> tuple[str, str | None]:
        """
        Build the $expand parameter from self._expand fields.
        """
        qp = '$expand'
        if self._expand is None:
            return (qp, None)

        fields = self.entity_model.model_fields
        aliases = []
        for f in self._expand:
            aliases.append(fields[f].alias or f)
        return (qp, ", ".join(aliases))

    def expand(self, *fields: str) -> "EntityManager":
        """
        Set fields that should be expanded in the OData query.
        Example usage: .expand('some_nested') if 'some_nested' is in nested_models
        """
        nested_models = self.entity_model.nested_models or {}
        for f in fields:
            if f not in nested_models:
                raise ValueError(
                    f"Nested model '{f}' not found in {list(nested_models.keys())}."
                )
        self._expand = fields
        return self

    @property
    def qp_filter(self) -> tuple[str, str | None]:
        """
        Build the $filter parameter using self._filter (Q object).
        """
        qp = '$filter'
        if self._filter is None:
            return (qp, None)

        fields = self.entity_model.model_fields
        field_mapping = {f: i.alias or f for f, i in fields.items()}
        return (qp, self._filter.build_expression(field_mapping))

    def filter(self, *args, **kwargs) -> "EntityManager":
        """
        Apply filtering conditions (Django-style lookups or Q objects).
        Example: filter(Q(name='Ivan'), age__gt=30).
        """
        new_q = Q(*args, **kwargs)
        if self._filter:
            self._filter &= new_q
        else:
            self._filter = new_q
        return self

    @property
    def qp_skip(self) -> tuple[str, str | None]:
        """
        Build the $skip parameter if self._skip is set.
        """
        return ('$skip', str(self._skip) if self._skip is not None else None)

    def skip(self, n: int) -> "EntityManager":
        """
        Skip the first n records in the query result.
        """
        self._skip = n
        return self

    @property
    def qp_top(self) -> tuple[str, str | None]:
        """
        Build the $top parameter if self._top is set.
        """
        return ('$top', str(self._top) if self._top is not None else None)

    def top(self, n: int) -> "EntityManager":
        """
        Limit the query result to n records.
        """
        self._top = n
        return self

    @staticmethod
    def _prepare_query_params(*args: tuple[str, str | None]) -> dict[str, str]:
        """
        Combine non-empty query parameters into a dict for ODataRequest.
        """
        qps = {}
        for key, val in args:
            if val is not None:
                qps[key] = val
        return qps
