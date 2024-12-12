from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import Field

from OData1C.models import ODataModel



class ContactInformationModel(ODataModel):
    ref_key: Optional[UUID] = Field(alias="Ref_Key", default=None)
    country: Optional[str] = Field(alias="Страна", default=None)
    city: Optional[str] = Field(alias="Город", default=None)
    street: Optional[str] = Field(alias="Представление", default=None)

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }

class PhysicalPersonModel(ODataModel):
    uid: UUID = Field(alias="Ref_Key")
    code: Optional[str] = Field(alias="Code")
    description: str = Field(alias="Description")
    first_name: Optional[str] = Field(alias="Имя")
    last_name: Optional[str] = Field(alias="Фамилия")
    middle_name: Optional[str] = Field(alias="Отчество")
    birth_date: Optional[datetime] = Field(alias="ДатаРождения")
    gender: Optional[str] = Field(alias="Пол")
    inn: Optional[str] = Field(alias="ИНН")
    snils: Optional[str] = Field(alias="СтраховойНомерПФР")
    contact_information: List[ContactInformationModel] = Field(alias="КонтактнаяИнформация", default=[])

    nested_models = {
        "contact_information": ContactInformationModel
    }

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }
