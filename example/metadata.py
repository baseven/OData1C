import os
from pprint import pprint

from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

from OData1C.connection import Connection
from OData1C.odata.metadata_manager import MetadataManager

load_dotenv()

HOST = os.getenv("ODATA_HOST", "localhost")
PROTOCOL = os.getenv("ODATA_PROTOCOL", "http")
USERNAME = os.getenv("ODATA_USERNAME", "Admin")
PASSWORD = os.getenv("ODATA_PASSWORD", "password")
DATABASE_NAME = os.getenv("ODATA_DATABASE", "zup-demo")


def main():
    """
    Demonstrates how to use the MetadataManager class to fetch and inspect
    OData metadata from a 1C server.
    """
    # 1. Create a Connection object to interact with the OData server
    with Connection(
        host=HOST,
        protocol=PROTOCOL,
        authentication=HTTPBasicAuth(USERNAME, PASSWORD)
    ) as conn:
        # 2. Initialize MetadataManager, passing the connection object and database name
        md_manager = MetadataManager(connection=conn, database_name=DATABASE_NAME)

        # 3. Retrieve the list of entity types
        entity_types = md_manager.get_entity_types()
        print("\n=== Entity Types ===")
        pprint(entity_types)

        # 4. Retrieve the list of entity sets (EntitySets)
        entity_sets = md_manager.get_entity_sets()
        print("\n=== Entity Sets ===")
        pprint(entity_sets)

        # 5. Retrieve properties of a specific entity type, if needed
        #    (Replace 'Catalog_ФизическиеЛица' with the actual entity type name in your configuration)
        target_entity = "Catalog_ФизическиеЛица"
        properties = md_manager.get_properties(target_entity)
        print(f"\n=== Properties for '{target_entity}' ===")
        pprint(properties)


if __name__ == "__main__":
    main()
