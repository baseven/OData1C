import json
import pytest
from http import HTTPStatus
from pathlib import Path

from OData1C.odata.metadata_manager import MetadataManager
from OData1C.exceptions import ODataResponseError

DATABASE_NAME = "test-db"


def get_test_data_path(filename: str) -> Path:
    """Returns the absolute path to a file inside tests/test_data."""
    return Path(__file__).parent / "test_data" / filename


def read_file(filename: str) -> str:
    """Reads and returns the content of a file from tests/test_data."""
    return get_test_data_path(filename).read_text(encoding="utf-8")


@pytest.fixture
def metadata_content():
    """Fixture providing test metadata XML content from file."""
    return read_file("metadata.xml")


@pytest.fixture
def expected_properties():
    """Fixture providing expected properties mapping from a JSON file."""
    return json.loads(read_file("expected_properties.json"))


@pytest.fixture
def manager(default_connection):
    """
    Creates a fresh MetadataManager instance without patching anything.
    This allows testing initialization and core logic separately.
    """
    return MetadataManager(connection=default_connection, database_name=DATABASE_NAME)


@pytest.fixture
def patched_manager(manager, metadata_content, mocker):
    """
    Uses pytest-mock to patch _fetch_metadata_xml in the MetadataManager instance.
    This ensures real HTTP calls are avoided, and the test metadata is used instead.
    """
    mocker.patch.object(manager, "_fetch_metadata_xml", return_value=metadata_content)
    return manager


def test_metadata_manager_init(manager):
    """
    Ensure the MetadataManager initializes correctly with an empty state.
    """
    assert not manager._is_metadata_loaded
    assert not manager._entity_sets
    assert not manager._entity_types
    assert not manager._entity_type_properties


def test_get_entity_sets(patched_manager):
    """
    Check that get_entity_sets() correctly returns the list of EntitySets from the metadata.xml.
    """
    entity_sets = patched_manager.get_entity_sets()
    expected_sets = [
        "TestEntities", "TestEntities2", "TestEntities3",
        "TestEntity4s", "RecursiveEntities"
    ]
    assert sorted(entity_sets) == sorted(expected_sets)


def test_get_entity_types(patched_manager):
    """
    Check that get_entity_types() correctly returns the list of EntityTypes from the metadata.xml.
    """
    entity_types = patched_manager.get_entity_types()
    expected_types = [
        "TestEntity", "TestEntity2", "TestItem", "TestEntity3",
        "ChildB", "ChildA", "ChildC", "TestEntity4", "RecursiveEntity"
    ]
    assert sorted(entity_types) == sorted(expected_types)


@pytest.mark.parametrize("entity_name", [
    "TestEntity",
    "TestEntity2",
    "TestEntity3",
    "TestEntity4",
    "RecursiveEntity"
])
def test_get_properties(patched_manager, expected_properties, entity_name):
    """
    Ensure get_properties(entity_name) returns the correct properties for each entity.
    This single test covers simple, complex, and recursive entities.
    """
    properties = patched_manager.get_properties(entity_name)
    assert properties == expected_properties[entity_name]


def test_reset_metadata(patched_manager):
    """
    After calling reset_metadata(), the manager should reload metadata on the next request.
    """
    patched_manager.get_entity_sets()
    assert patched_manager._is_metadata_loaded

    patched_manager.reset_metadata()
    assert not patched_manager._is_metadata_loaded
    assert not patched_manager._entity_sets
    assert not patched_manager._entity_types
    assert not patched_manager._entity_type_properties

    patched_manager.get_entity_sets()
    assert patched_manager._is_metadata_loaded


@pytest.mark.parametrize("status_code, reason, text, should_raise", [
    (HTTPStatus.OK, "OK", "All good", False),
    (HTTPStatus.NOT_FOUND, "Not Found", "Error details", True),
    (HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error", "Server broke", True),
])
def test_check_response_error_handling(status_code, reason, text, should_raise):
    """
    Ensure _check_response behaves correctly for different HTTP status codes:
      - 200 => no error,
      - 4xx/5xx => raises ODataResponseError.
    """
    fake_response = type("FakeResponse", (), {
        "status_code": status_code,
        "reason": reason,
        "text": text
    })

    if should_raise:
        with pytest.raises(ODataResponseError) as exc_info:
            MetadataManager._check_response(fake_response(), HTTPStatus.OK)
        assert str(status_code) in str(exc_info.value)
        assert reason in str(exc_info.value)
        assert text in str(exc_info.value)
    else:
        MetadataManager._check_response(fake_response(), HTTPStatus.OK)
