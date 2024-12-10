"""
This example demonstrates fetching data from OData:
- Using filter() to apply conditions (Django-style lookups, Q objects).
- Using expand() to retrieve related nested entities.
- Using top() and skip() for pagination.
- Using get() to fetch a single entity by GUID.
- Using all(ignore_invalid=True) to skip invalid entities.
- Inspecting manager.request and manager.response for debugging.
"""

import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from OData1C.connection import Connection
from OData1C.odata.manager import OData
from example.models import PhysicalPersonModel

from OData1C.odata.query import Q

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

        # Пример фильтрации по имени
        persons = (
            manager
            .filter(Description='Булатов Игорь Виленович')
            .all(ignore_invalid=True)
        )
        print("Filtered persons:")
        for p in persons:
            print(p)

        # Пример с использованием Q-объектов и пагинации
        persons_paged = (
            manager
            .filter(Q(description__gt='A'))  # пример фильтра с Q, просто условие
            .top(5)
            .skip(2)
            .all(ignore_invalid=True)
        )
        print("\nPaged and filtered persons:")
        for p in persons_paged:
            print(p)

        # Пример использования expand (предполагая, что contact_information может быть расширяемым полем)
        # В данном случае expand не всегда нужно, зависит от API, пример для наглядности
        persons_expanded = (
            manager
            .expand('contact_information')
            .filter(last_name='Булатов')
            .all(ignore_invalid=True)
        )
        print("\nExpanded persons with contact information:")
        for p in persons_expanded:
            print(p, p.contact_information)

        # Получение одного объекта по GUID
        guid_example = 'e09df266-7bf4-11e2-9362-001b11b25590'  # пример GUID
        single_person = manager.get(guid_example)
        print("\nSingle person by GUID:")
        print(single_person)

        # Отладка: просмотр request и response
        print("\nDebug info:")
        print("Request:", manager.request)
        print("Response:", manager.response)
        if manager.response:
            print("Response JSON:", manager.response.json())