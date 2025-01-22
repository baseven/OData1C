import pytest
from unittest.mock import MagicMock
from requests import Response
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from OData1C.connection import Connection, ODataRequest
from OData1C.exceptions import ODataConnectionError


@pytest.fixture
def mocked_session(mocker):
    """
    A fixture that patches 'OData1C.connection.Session', returning a mock object.
    Also sets up headers = {} to avoid autospec issues.
    Returns the mock instance (Session) that the code under test will use.
    """
    mock_session_class = mocker.patch("OData1C.connection.Session", autospec=True)
    mock_session_instance = mock_session_class.return_value

    # Ensure we have .headers = {}
    mock_session_instance.headers = {}
    return mock_session_instance


@pytest.fixture
def default_connection():
    """
    A fixture that creates a Connection with defaults.
    Authentication is just a MagicMock for now.
    """
    return Connection(
        host="test-host",
        protocol="http",
        authentication=MagicMock()
    )


def test_get_url_no_params():
    """
    Test that get_url constructs the URL correctly without query params.
    """
    conn = Connection(
        host="test-host",
        protocol="http",
        authentication=MagicMock()
    )
    url = conn.get_url("Catalog_Номенклатура")
    assert url == "http://test-host/Catalog_Номенклатура"


def test_get_url_with_params():
    """
    Test that get_url constructs the URL correctly with query params.
    """
    conn = Connection(
        host="test-host",
        protocol="http",
        authentication=MagicMock()
    )
    url = conn.get_url("Catalog_Номенклатура", {"code": "123", "foo": "bar"})
    assert url.startswith("http://test-host/Catalog_Номенклатура?")
    assert "code=123" in url
    assert "foo=bar" in url


def test_session_lifecycle(mocked_session, default_connection):
    """
    Check that using Connection as a context manager
    creates the session on enter and closes on exit.
    """
    # At the start, no session
    assert default_connection._session is None

    # Entering context should create a session
    with default_connection as conn_in_context:
        assert conn_in_context._session is not None

    # after exiting, session should be closed
    # => check that 'close()' was called once
    mocked_session.close.assert_called_once()


@pytest.mark.parametrize("status_code, ok", [
    (200, True),
    (404, False),
])
def test_send_request_2xx_and_4xx_returns_response(mocked_session, default_connection, status_code, ok):
    """
    Verifies that Connection.send_request returns the raw Response object
    (and does not raise exceptions) for both 2xx (200) and 4xx (404) HTTP statuses.

    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = status_code
    mock_response.ok = ok

    mocked_session.send.return_value = mock_response

    request = ODataRequest(method="GET", relative_url="Catalog_Номенклатура")
    response = default_connection.send_request(request)

    mocked_session.send.assert_called_once()

    assert response is mock_response, "Expected the same mock response object to be returned"
    assert response.status_code == status_code, (
        f"Expected status_code {status_code}, got {response.status_code}"
    )


@pytest.mark.parametrize("side_effect, msg", [
    (RequestsConnectionError("Network fail"), "Network fail"),
    (Timeout("Timed out"), "Timed out"),
])
def test_send_request_network_errors(mocked_session, default_connection, side_effect, msg):
    """
    If a network error or a timeout occurs,
    we expect ODataConnectionError to be raised.
    """
    mocked_session.send.side_effect = side_effect

    req = ODataRequest("GET", "Catalog_Номенклатура")
    with pytest.raises(ODataConnectionError) as exc:
        default_connection.send_request(req)
    assert msg in str(exc.value)
    mocked_session.send.assert_called_once()
