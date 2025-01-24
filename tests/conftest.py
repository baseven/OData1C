import pytest
from requests.auth import AuthBase

from unittest.mock import MagicMock

from OData1C.connection import Connection
@pytest.fixture
def default_auth():
    """
    A fixture that provides a mock authentication object for the Connection.
    """
    return MagicMock(spec=AuthBase)


@pytest.fixture
def default_connection(default_auth):
    """
    A fixture that creates a Connection with default parameters.

    Authentication is mocked using the 'default_auth' fixture.
    """
    return Connection(
        host="test-host",
        protocol="http",
        authentication=default_auth
    )
