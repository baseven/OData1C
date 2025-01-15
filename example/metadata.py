import os
from pprint import pprint
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

from OData1C.connection import Connection
# Make sure you import the accelerated MetadataManager from wherever you placed it.
from OData1C.odata.metadata import MetadataManager

load_dotenv()

HOST = os.getenv('ODATA_HOST')
PROTOCOL = os.getenv('ODATA_PROTOCOL')
USERNAME = os.getenv('ODATA_USERNAME')
PASSWORD = os.getenv('ODATA_PASSWORD')
DATABASE = os.getenv('ODATA_DATABASE') or "zup-demo"


def main():
    with Connection(
        host=HOST,          # e.g. "1c.dev.evola.ru"
        protocol=PROTOCOL,  # e.g. "https"
        authentication=HTTPBasicAuth(USERNAME, PASSWORD)
    ) as conn:
        # Create an "accelerated" MetadataManager instance
        mdm = MetadataManager(connection=conn, database=DATABASE)

        # 1) Fetch a list of EntityType names
        all_types = mdm.list_entity_types()
        print("\n=== EntityTypes ===")
        pprint(all_types)

        # 2) Fetch a list of EntitySet names
        all_sets = mdm.list_entity_sets()
        print("\n=== EntitySets ===")
        pprint(all_sets)

        # 3) Get the fields (Properties) of a specific EntityType
        fields = mdm.get_properties_for_entity_type("Catalog_ФизическиеЛица")
        print("\nFields for Catalog_ФизическиеЛица:")
        pprint(fields)

        # 4) Force a reload (if you suspect metadata might have changed on the server)
        mdm.reload_metadata()
        # The next calls will then fetch fresh XML and rebuild the structures.

if __name__ == "__main__":
    main()
