"""Base resource class for OmoiOS API resources."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omoios.client import AsyncOmoiOSClient


class BaseResource:
    """Base class for all API resources.

    Provides a reference to the parent client for making HTTP requests.
    """

    def __init__(self, client: "AsyncOmoiOSClient") -> None:
        """Initialize the resource with a client reference.

        Args:
            client: The async OmoiOS client instance
        """
        self._client = client
