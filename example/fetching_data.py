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
from datetime import datetime
from pprint import pprint

from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from OData1C.connection import Connection
from OData1C.odata.manager import OData
from OData1C.odata.query import Q
from example.models import PhysicalPersonModel



# Load environment variables
load_dotenv()

# OData configuration
HOST = os.getenv('ODATA_HOST')
PROTOCOL = os.getenv('ODATA_PROTOCOL')
USERNAME = os.getenv('ODATA_USERNAME')
PASSWORD = os.getenv('ODATA_PASSWORD')


class PhysicalPersonOData(OData):
    """Class for interacting with OData API for physical persons."""
    database = 'zup-demo'
    entity_model = PhysicalPersonModel
    entity_name = 'Catalog_ФизическиеЛица'


def fetch_filtered_persons(manager):
    """
    Fetch persons filtered by name.

    Args:
        manager (PhysicalPersonOData.manager): OData manager instance.
    """
    persons = manager.filter(first_name='Игорь').all(ignore_invalid=True)
    print("Filtered persons:")
    for i, person in enumerate(persons):
        pprint(f'{i + 1}. {person}')


def fetch_paged_and_filtered_persons(manager):
    """
    Fetch persons with pagination and filtering using Q objects.

    Args:
        manager (PhysicalPersonOData.manager): OData manager instance.
    """
    birth_date_filter = datetime.strptime("1975-01-01", "%Y-%m-%d").isoformat()

    persons = (
        manager
        .filter(Code__lt='0000000020')
        .top(3)
        .all(ignore_invalid=True)
    )
    print("\nPaged and filtered persons:")
    for i, person in enumerate(persons):
        pprint(f'{i + 1}. {person.description}, {person.code}')


def fetch_expanded_persons(manager):
    """
    Fetch persons with expanded contact information.

    Args:
        manager (PhysicalPersonOData.manager): OData manager instance.
    """
    persons = (
        manager
        .expand('contact_information')
        .filter(last_name='Булатов')
        .all(ignore_invalid=True)
    )
    print("\nExpanded persons with contact information:")
    for person in persons:
        print(person, person.contact_information)


def fetch_single_person(manager, guid):
    """
    Fetch a single person by GUID.

    Args:
        manager (PhysicalPersonOData.manager): OData manager instance.
        guid (str): GUID of the person to fetch.
    """

    person = manager.get(guid)
    print("\nSingle person by GUID:")
    print(person)


def debug_manager(manager):
    """
    Print debugging information about the OData manager.

    Args:
        manager (PhysicalPersonOData.manager): OData manager instance.
    """
    print("\nDebug info:")
    print("Request:", manager.request)
    print("Response:", manager.response)
    if manager.response:
        try:
            print("Response JSON:", manager.response.json())
        except Exception as e:
            print("Error decoding JSON:", e)


def main():
    """Main function for interacting with the OData API."""
    with Connection(
            host=HOST,
            protocol=PROTOCOL,
            authentication=HTTPBasicAuth(USERNAME, PASSWORD),
    ) as conn:
        manager = PhysicalPersonOData.manager(conn)

        # Execute various operations
        # Example GUID for fetching a single entity

        # guid_example = 'e09df266-7bf4-11e2-9362-001b11b25590'
        # fetch_single_person(manager, guid_example)
        # fetch_filtered_persons(manager)

        # fetch_paged_and_filtered_persons(manager)
        # fetch_expanded_persons(manager)
        #
        #
        # # Debugging information
        # debug_manager(manager)


if __name__ == "__main__":
    main()
