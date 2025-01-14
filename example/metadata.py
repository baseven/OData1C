"""
Пример использования MetadataManager, который принимает Connection и database,
а путь 'odata/standard.odata' захардкожен внутри класса.
"""

import os
from pprint import pprint
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

from OData1C.connection import Connection
from OData1C.odata.metadata import MetadataManager

load_dotenv()

# Допустим, в .env у нас:
#   ODATA_HOST=1c.dev.evola.ru
#   ODATA_PROTOCOL=https
#   ODATA_USERNAME=...
#   ODATA_PASSWORD=...
HOST = os.getenv('ODATA_HOST')
PROTOCOL = os.getenv('ODATA_PROTOCOL')
USERNAME = os.getenv('ODATA_USERNAME')
PASSWORD = os.getenv('ODATA_PASSWORD')

# Также можно .env хранить:
#   ODATA_DATABASE=zup-demo
# Если нет, просто хардкодим здесь
DATABASE = os.getenv('ODATA_DATABASE') or "zup-demo"


def main():
    with Connection(
        host=HOST,          # "1c.dev.evola.ru"
        protocol=PROTOCOL,  # "https"
        authentication=HTTPBasicAuth(USERNAME, PASSWORD)
    ) as conn:
        # Создаём MetadataManager, передав только database
        mdm = MetadataManager(connection=conn, database=DATABASE)

        # 1) Получаем список EntityType
        entity_types = mdm.list_entity_types()
        print("\n=== EntityTypes ===")
        pprint(entity_types)

        # 2) Получаем список EntitySet
        entity_sets = mdm.list_entity_sets()
        print("\n=== EntitySets ===")
        pprint(entity_sets)


if __name__ == "__main__":
    main()
