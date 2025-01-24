import pytest
from unittest.mock import MagicMock
from requests import Response
from requests.auth import AuthBase
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from OData1C.connection import Connection, ODataRequest
from OData1C.exceptions import ODataConnectionError


BASE_URL = "http://test-host"
RELATIVE_URL = "Catalog_Номенклатура"
QUERY_PARAMS = {"code": "123", "foo": "bar"}
EXPECTED_QUERY_PARAMS = ["code=123", "foo=bar"]


@pytest.fixture
def mocked_session(mocker):
    """
    Fixture that patches the 'Session' class used in the Connection module, returning a mock object.

    Note:
    - The path for patching ('session_path') depends on how and where the 'Session' class is imported
      in the target module. Here, the path is dynamically constructed based on the 'Connection' class's
      module (`Connection.__module__`) to ensure accuracy, even if the project structure changes.

    - If 'Session' is imported directly in the module, such as:
          from requests import Session
      Then you should patch it as '<module_path>.Session' (e.g., 'OData1C.connection.Session').

    - If 'Session' is used via the `requests` namespace, such as:
          import requests
          requests.Session()
      Then you should patch it as 'requests.Session'.

    - The 'headers' attribute in 'Session' is dynamically created in its constructor (e.g.,
      self.headers = CaseInsensitiveDict()) and may not be present in the class definition.
      To avoid AttributeError when using autospec=True, the 'headers' attribute is explicitly
      added to the mocked instance.
    """
    session_path = f"{Connection.__module__}.Session"
    mock_session_class = mocker.patch(session_path, autospec=True)
    mock_session_instance = mock_session_class.return_value
    mock_session_instance.headers = {}
    return mock_session_instance


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


@pytest.mark.parametrize(
    "relative_url, query_params, expected_url, expected_query_params",
    [
        # Test without query params
        (RELATIVE_URL, None, f"{BASE_URL}/{RELATIVE_URL}", None),

        # Test with query params
        (RELATIVE_URL, QUERY_PARAMS, f"{BASE_URL}/{RELATIVE_URL}", EXPECTED_QUERY_PARAMS),

        # Test empty relative URL
        ("", None, f"{BASE_URL}/", None),

        # Test empty query params
        (RELATIVE_URL, {}, f"{BASE_URL}/{RELATIVE_URL}", None),
    ]
)
def test_get_url(default_connection, relative_url, query_params, expected_url, expected_query_params):
    """
    Test that get_url constructs the URL correctly for different scenarios.
    """
    url = default_connection.get_url(relative_url, query_params)
    # Check base URL
    assert url.startswith(expected_url), f"Expected URL to start with {expected_url}, but got {url}"
    # Check query params if provided
    if expected_query_params:
        for param in expected_query_params:
            assert param in url, f"Expected query parameter '{param}' not found in {url}"


def test_session_lifecycle(mocked_session, default_connection):
    """
    Verify that Connection as a context manager:
    - Creates a session on enter.
    - Closes the session on exit.
    """
    # Ensure no session exists initially
    initial_session = default_connection._session
    assert initial_session is None, "Expected no session before context manager"

    # Test session creation within the context manager
    with default_connection as conn_in_context:
        active_session = conn_in_context._session
        assert active_session is not None, "Expected a session to be created within the context manager"

    # Ensure the session was closed after exiting the context manager
    mocked_session.close.assert_called_once()


@pytest.mark.parametrize("status_code, ok", [
    (200, True),
    (404, False),
])
def test_send_request_2xx_and_4xx_returns_response(mocked_session, default_connection, status_code, ok):
    """
    Verify that Connection.send_request:
    - Returns the raw Response object.
    - Handles both 2xx (successful) and 4xx (client error) HTTP statuses without raising exceptions.
    """
    mock_response = MagicMock(spec=Response, status_code=status_code, ok=ok)
    mocked_session.send.return_value = mock_response

    request = ODataRequest(method="GET", relative_url="Catalog_Номенклатура")
    response = default_connection.send_request(request)

    mocked_session.send.assert_called_once()

    assert response is mock_response, "Expected the mock response object to be returned"
    assert response.status_code == status_code, f"Expected status code {status_code}, but got {response.status_code}"


@pytest.mark.parametrize("side_effect, msg", [
    (RequestsConnectionError("Network fail"), "Network fail"),
    (Timeout("Timed out"), "Timed out"),
])
def test_send_request_network_errors(mocked_session, default_connection, side_effect, msg):
    """
    Test that Connection.send_request raises ODataConnectionError
    when a network error or timeout occurs.
    """
    mocked_session.send.side_effect = side_effect
    req = ODataRequest("GET", "Catalog_Номенклатура")
    with pytest.raises(ODataConnectionError) as exc:
        default_connection.send_request(req)
    assert msg in str(exc.value)
    mocked_session.send.assert_called_once()
