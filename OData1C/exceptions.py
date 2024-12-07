class ODataError(Exception):
    """Base class for all OData-related errors."""
    pass


class ODataConnectionError(ODataError):
    """
    Raised when there is a connection-related issue with the OData server.
    For example, if the server is unreachable or the request timed out.
    """
    pass


class ODataResponseError(ODataError):
    """
    Raised when the server returns an erroneous HTTP status code or
    the response cannot be processed correctly.
    """

    def __init__(self, status_code: int, reason: str, details: str):
        message = f"Status: {status_code}. Reason: {reason}. Details: {details}"
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.details = details
