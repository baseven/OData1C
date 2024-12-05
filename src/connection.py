from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
from urllib.parse import quote, urlencode

from requests import Response, Session, Request
from requests.auth import AuthBase
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from src.exceptions import ODataConnectionError


DEFAULT_CONNECTION_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 120.0

DEFAULT_HEADERS = {
    "Accept": "application/json",
}


@dataclass
class ODataRequest:
    """
    Represents an HTTP request to be sent via the Connection class.

    Attributes:
        method (str): The HTTP method (e.g. 'GET', 'POST', 'PATCH', 'DELETE').
        relative_url (str): The relative URL appended to the base URL of the connection.
        query_params (Optional[Dict[str, Any]]): Additional query parameters for the request.
        data (Optional[Dict[str, Any]]): Data to be sent as JSON in the request body.
    """
    method: str
    relative_url: str
    query_params: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None


class Connection:
    """
    Manages an HTTP connection to a 1C OData server, providing methods
    to send requests and handle sessions.

    This class is designed to be used as a context manager to ensure
    that the underlying HTTP session is properly closed automatically.
    However, it can also be used without a context manager.
    """

    def __init__(
        self,
        host: str,
        protocol: str,
        authentication: AuthBase,
        connection_timeout: Union[int, float] = DEFAULT_CONNECTION_TIMEOUT,
        read_timeout: Union[int, float] = DEFAULT_READ_TIMEOUT
    ) -> None:
        """
        Initializes a new Connection instance.

        Args:
            host (str): The hostname or IP address of the 1C server.
            protocol (str): The protocol to use (e.g. 'http' or 'https').
            authentication (AuthBase): An authentication handler (e.g. HTTPBasicAuth).
            connection_timeout (Union[int, float]): Maximum time in seconds to wait for a connection to the server.
            read_timeout (Union[int, float]): Maximum time in seconds to wait for a response after a connection is established.
            headers (Optional[Dict[str, str]]): Additional HTTP headers to include with every request.
        """
        self.base_url = f"{protocol}://{host}/"
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.auth = authentication
        self.headers = DEFAULT_HEADERS.copy()
        self._session: Optional[Session] = None

    def __enter__(self) -> "Connection":
        self._session = self._create_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session:
            self._session.close()

    def _create_session(self) -> Session:
        """
        Creates and returns a new Session with authentication and predefined headers.
        """
        session = Session()
        session.auth = self.auth
        session.headers.update(self.headers)
        return session

    def get_url(
        self, relative_url: str, query_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Constructs the full URL by combining the base URL with the relative URL and query parameters.

        Args:
            relative_url (str): The relative path to append to the base URL.
            query_params (Optional[Dict[str, Any]]): Additional query parameters.

        Returns:
            str: The fully constructed URL.
        """
        url = f"{self.base_url}{relative_url}"
        if query_params:
            url = f"{url}?{urlencode(query_params, quote_via=quote)}"
        return url

    def send_request(self, request: ODataRequest) -> Response:
        """
        Sends an HTTP request using the current or a new session and returns the response.

        If a session is not available (not used as a context manager), a temporary session
        will be created and closed after the request is complete.

        Args:
            request (ODataRequest): The request object containing method, relative_url, query_params, and data.

        Returns:
            Response: The HTTP response object.

        Raises:
            ODataConnectionError: If a connection or timeout error occurs.
        """
        session = self._session or self._create_session()
        url = self.get_url(request.relative_url, request.query_params)
        raw_request = Request(method=request.method, url=url, json=request.data)
        prepared_request = session.prepare_request(raw_request)

        try:
            response = session.send(
                prepared_request,
                timeout=(self.connection_timeout, self.read_timeout),
            )
            response.raise_for_status()
            return response
        except (RequestsConnectionError, Timeout) as e:
            raise ODataConnectionError(str(e)) from e
        finally:
            if self._session is None:
                session.close()