from typing import ClassVar, Dict, Optional, Type

from pydantic import BaseModel


class ODataModel(BaseModel):
    """
    Base model for data serialization, deserialization, and validation.

    The `nested_models` class variable is used to optimize queries involving nested entities.
    It should be a dictionary where keys are the names of fields representing nested entities,
    and values are the corresponding `ODataModel` subclasses for those nested entities.

    If `nested_models` is set to `None`, all fields of nested entities will be requested
    and included in the query results, regardless of their presence in the nested model.
    """

    nested_models: ClassVar[Optional[Dict[str, Type["ODataModel"]]]] = None
