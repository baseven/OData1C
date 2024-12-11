from datetime import datetime
from http import HTTPStatus
from typing import Any, Callable, Iterable, Type, TypeVar

from pydantic import ValidationError
from requests import Response
import requests.exceptions as r_exceptions

from OData1C.connection import Connection, ODataRequest
from OData1C.exceptions import ODataError, ODataResponseError
from OData1C.models import ODataModel
from OData1C.odata.query import Q

OM = TypeVar("OM", bound=ODataModel)


type_repr = {
    bool: lambda v: str(v).lower(),
    str: lambda v: f"'{v}'",
    datetime: lambda v: "datetime'{}'".format(v.isoformat('T', 'seconds')),
}


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
    entity_model: OM
    entity_name: str

    _err_msg: str = "Required attribute not defined: {}."

    @classmethod
    def manager(cls, connection: Connection) -> 'ODataManager':
        """
        Creates and returns an ODataManager instance for this OData entity.

        Args:
            connection (Connection): The connection used to send HTTP requests.

        Raises:
            AttributeError: If `entity_model` or `entity_name` are not defined.

        Returns:
            ODataManager[OM]: A manager instance for querying and operating on the entity.
        """
        assert hasattr(cls, 'entity_model'), (
            cls._err_msg.format(f'{cls.__name__}.entity_model'))
        assert hasattr(cls, 'entity_name'), (
            cls._err_msg.format(f'{cls.__name__}.entity_name'))
        return ODataManager(odata_class=cls, connection=connection)


class ODataManager:
    odata_path = 'odata/standard.odata'
    odata_list_json_key = 'value'

    def __init__(self, odata_class: Type[OData], connection: Connection):
        self.odata_class = odata_class
        self.connection = connection
        self.request: ODataRequest | None = None
        self.response: Response | None = None
        self.validation_errors: list[ValidationError] = []
        self._expand: Iterable[str] | None = None
        self._filter: Q | None = None
        self._skip: int | None = None
        self._top: int | None = None

    def __str__(self):
        return f'{self.odata_class.__name__} manager'

    def _check_response(self, ok_status: int) -> None:
        """Checking response status code."""
        if self.response.status_code != ok_status:
            raise ODataResponseError(self.response.status_code,
                                self.response.reason,
                                self.response.text)

    def _validate(self,
                  data: list[dict[str, Any]] | dict[str, Any],
                  ignore_invalid: bool = False
                  ) -> list[OM] | OM:
        """Validation of response data."""
        self.validation_errors = []
        if isinstance(data, list):
            validated_objs = []
            for obj in data:
                validated_objs.append(self._validate_obj(obj, ignore_invalid))
            return validated_objs
        return self._validate_obj(data, ignore_invalid)

    def _validate_obj(self,
                      obj: dict[str, Any],
                      ignore_invalid: bool) -> OM:
        """Object validation."""
        try:
            return self.odata_class.entity_model.model_validate(obj)
        except ValidationError as e:
            self.validation_errors.append(e)
            if not ignore_invalid:
                raise e

    def _json(self) -> dict[str, Any]:
        """Decodes json response."""
        try:
            data = self.response.json()
        except r_exceptions.JSONDecodeError as e:
            raise ODataError(e)
        return data

    @staticmethod
    def _to_dict(data: OM | dict[str, Any]) -> dict[str, Any]:
        """Converts data to dict."""
        if isinstance(data, ODataModel):
            return data.model_dump(by_alias=True)
        return data

    def get_url(self) -> str:
        """Returns the url of the entity."""
        return (f'{self.odata_class.database}'
                f'/{self.odata_path}'
                f'/{self.odata_class.entity_name}')

    def get_canonical_url(self, guid: str) -> str:
        """Returns the canonical url of the entity."""
        return f"{self.get_url()}(guid'{guid}')"

    def all(self, ignore_invalid: bool = False) -> list[OM]:
        """
        Returns validated instances of the ODataModel class.
        If ignore_invalid = True, invalid objects will be skipped,
        errors will be accumulated in self.validation_errors.
        Otherwise, a pydantic.ValidationError exception will be raised.
        """
        self.request = ODataRequest(
            method='GET',
            relative_url=self.get_url(),
            query_params=self.prepare_query_params(
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
            data: list[dict[str, Any]] = self._json()[self.odata_list_json_key]
        except KeyError:
            raise ODataError(
                f'Response json has no key {self.odata_list_json_key}'
            )
        return self._validate(data, ignore_invalid)

    def create(self, data: OM| dict[str, Any]) -> OM:
        """Creates a new entity."""
        self.request = ODataRequest(method='POST',
                               relative_url=self.get_url(),
                               data=self._to_dict(data))
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.CREATED)
        return self._validate(self._json())

    def get(self, guid: str) -> OM:
        """Get an entity by guid."""
        self.request = ODataRequest(method='GET',
                               relative_url=self.get_canonical_url(guid),
                               query_params=self.prepare_query_params(
                                   self.qp_select, self.qp_expand)
                               )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        return self._validate(self._json())

    def update(self,
               guid: str,
               data: OM | dict[str, Any]) -> OM:
        """Updates (patch) an entity by guid."""
        self.request = ODataRequest(
            method='PATCH',
            relative_url=self.get_canonical_url(guid),
            data=self._to_dict(data),
            query_params=self.prepare_query_params(
                self.qp_select,
                self.qp_expand
            )
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)
        return self._validate(self._json())

    def post_document(self,
                      guid: str,
                      operational_mode: bool = False) -> None:
        """Document posting."""
        self.request = ODataRequest(
            method='POST',
            relative_url=f'{self.get_canonical_url(guid)}/Post',
            query_params={
                'PostingModeOperational':
                    type_repr[bool](
                        operational_mode)
            }
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)

    def unpost_document(self, guid: str) -> None:
        """Cancel posting a document."""
        self.request = ODataRequest(
            method='POST',
            relative_url=f'{self.get_canonical_url(guid)}/Unpost'
        )
        self.response = self.connection.send_request(self.request)
        self._check_response(HTTPStatus.OK)

    """Query parameters."""

    @property
    def qp_select(self) -> tuple[str, str | None]:
        qp = '$select'
        fields = self.odata_class.entity_model.model_fields
        nested_models = self.odata_class.entity_model.nested_models
        aliases = []
        for field, info in fields.items():
            alias = info.alias or field
            if nested_models is not None and field in nested_models:
                for nested_field, nested_info in nested_models[
                    field].model_fields.items():
                    nested_alias = nested_info.alias or nested_field
                    aliases.append(f'{alias}/{nested_alias}')
            else:
                aliases.append(alias)
        return qp, ', '.join(aliases)

    @property
    def qp_expand(self) -> tuple[str, str | None]:
        qp = '$expand'
        if self._expand is None:
            return qp, None
        fields = self.odata_class.entity_model.model_fields
        aliases = []
        for field_name in self._expand:
            aliases.append(fields[field_name].alias or field_name)
        return '$expand', ', '.join(aliases)

    def expand(self, *args: str) -> 'ODataManager':
        nested_models = self.odata_class.entity_model.nested_models
        fields = []
        for field_name in args:
            if field_name not in nested_models:
                raise ValueError(
                    f"Nested model '{field_name}' not found. "
                    f"Use one of {list(nested_models.keys())}"
                )
            fields.append(field_name)
        self._expand = fields
        return self

    @property
    def qp_filter(self) -> tuple[str, str | None]:
        qp = '$filter'
        if self._filter is None:
            return qp, None
        fields = self.odata_class.entity_model.model_fields
        field_mapping = {f: i.alias or f for f, i in fields.items()}
        return qp, self._filter.build_expression(field_mapping)

    def filter(self, *args, **kwargs) -> 'ODataManager':
        """
        Sets filtering conditions.
        Example: filter(Q(a=1, b__gt), c__in=[1, 2])
        :param args: Q objects.
        :param kwargs: Lookups.
        :return: self
        """
        q = Q(*args, **kwargs)
        if self._filter is not None:
            self._filter &= q
        else:
            self._filter = q
        return self

    @property
    def qp_skip(self) -> tuple[str, str | None]:
        return '$skip', self._skip

    def skip(self, n: int) -> 'ODataManager':
        """Skips n number of entities."""
        self._skip = n
        return self

    @property
    def qp_top(self) -> tuple[str, str | None]:
        return '$top', self._top

    def top(self, n: int) -> 'ODataManager':
        """Getting n number of entities."""
        self._top = n
        return self

    @staticmethod
    def prepare_query_params(*args: tuple[str, str]) -> dict[str, Any]:
        qps = {}
        for qp, val in args:
            if val is not None:
                qps[qp] = val
        return qps
