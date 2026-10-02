from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar, Union

from playwright.async_api import Page as AsyncPage
from playwright.async_api import Response as AsyncResponse
from playwright.async_api import Route as AsyncRoute
from playwright.sync_api import Page as SyncPage
from playwright.sync_api import Response as SyncResponse
from playwright.sync_api import Route as SyncRoute

PageT = TypeVar("PageT", AsyncPage, SyncPage)
Response = Union[AsyncResponse, SyncResponse]
Route = Union[AsyncRoute, SyncRoute]


class BaseSolver(ABC, Generic[PageT]):
    """
    The base class for reCAPTCHA v3 solvers.

    Parameters
    ----------
    page : PageT
        The Playwright page to solve the reCAPTCHA on.
    timeout : float, optional
        The solve timeout in seconds, by default 30.
    block_token_requests : bool, optional
        Whether to block requests containing the reCAPTCHA token, by default False.
    """

    def __init__(
        self, page: PageT, *, timeout: float = 30, block_token_requests: bool = False
    ) -> None:
        self._page = page
        self._timeout = timeout
        self._block_token_requests = block_token_requests

        self._token: Optional[str] = None
        self._route_callback_added = False
        self._page.on("response", self._response_callback)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(page={self._page!r}, "
            f"timeout={self._timeout!r})"
        )

    def close(self) -> None:
        """Remove the reload response listener."""
        try:
            self._page.remove_listener("response", self._response_callback)
        except KeyError:
            pass

    @abstractmethod
    def _route_callback(self, route: Route) -> None:
        """
        The callback for intercepting requests with the reCAPTCHA token.

        Parameters
        ----------
        route : Route
            The route.
        """

    @abstractmethod
    def _response_callback(self, response: Response) -> None:
        """
        The callback for intercepting reload responses.

        Parameters
        ----------
        response : Response
            The response.
        """

    @abstractmethod
    def add_token_request_blocker(self) -> None:
        """Add the route callback for blocking reCAPTCHA token requests."""

    @abstractmethod
    def remove_token_request_blocker(self) -> None:
        """Remove the route callback for blocking reCAPTCHA token requests."""

    @abstractmethod
    def solve_recaptcha(self, *, timeout: Optional[float] = None) -> str:
        """
        Wait for the reCAPTCHA to be solved and return the `g-recaptcha-response` token.

        Parameters
        ----------
        timeout : Optional[float], optional
            The solve timeout in seconds, by default 30.

        Returns
        -------
        str
            The `g-recaptcha-response` token.

        Raises
        ------
        RecaptchaTimeoutError
            If the solve timeout has been exceeded.
        """
