"""OmoiOS SDK exceptions."""

from typing import Optional


class OmoiOSError(Exception):
    """Base exception for OmoiOS SDK."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthError(OmoiOSError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class NotFoundError(OmoiOSError):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ValidationError(OmoiOSError):
    """Raised when request validation fails."""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=400)


class ServerError(OmoiOSError):
    """Raised when server returns 5xx error."""

    def __init__(self, message: str = "Server error"):
        super().__init__(message, status_code=500)
