"""
This example demonstrates modifying data using OData:
- Using create(data) to create a new entity. Data can be a dict or a model instance.
- Using update(guid, data) to update an existing entity by GUID.
"""

import os
from datetime import datetime
from uuid import uuid4
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from OData1C.connection import Connection
from OData1C.odata.manager import OData
from example.models import PhysicalPersonModel

load_dotenv()

host = os.getenv('ODATA_HOST')
protocol = os.getenv('ODATA_PROTOCOL')
username = os.getenv('ODATA_USERNAME')
password = os.getenv('ODATA_PASSWORD')

class PhysicalPersonOData(OData):
    database = 'zup-demo'
    entity_model = PhysicalPersonModel
    entity_name = 'Catalog_ФизическиеЛица'


if __name__ == "__main__":
    with Connection(
        host=host,
        protocol=protocol,
        authentication=HTTPBasicAuth(username, password),
    ) as conn:
        manager = PhysicalPersonOData.manager(conn)

        # Пример создания новой сущности
        # data как словарь
        new_person_data = {
            "Description": "Иванов Иван Петрович",
            "Имя": "Иван",
            "Фамилия": "Иванов",
            "Отчество": "Петрович",
            "ДатаРождения": "1985-05-15T00:00:00",
            "Пол": "Мужской"
        }
        created_person = manager.create(new_person_data)
        print("Created person:", created_person)

        # Пример обновления сущности
        # data как экземпляр модели
        # Предположим, что мы хотим обновить ФИО у только что созданной сущности.
        # Нужно GUID созданной сущности, предположим что created_person.uid доступен
        created_person.last_name = "Сидоров"
        updated_person = manager.update(created_person.uid, created_person)
        print("Updated person:", updated_person)