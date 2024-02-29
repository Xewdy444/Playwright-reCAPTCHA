from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar, Union

from playwright.async_api import Page as AsyncPage
from playwright.async_api import Response as AsyncResponse
from playwright.sync_api import Page as SyncPage
from playwright.sync_api import Response as SyncResponse

PageT = TypeVar("PageT", AsyncPage, SyncPage)
Response = Union[AsyncResponse, SyncResponse]


class BaseSolver(ABC, Generic[PageT]):
    """
    The base class for reCAPTCHA v3 solvers.

    Parameters
    ----------
    page : PageT
        The Playwright page to solve the reCAPTCHA on.
    timeout : float, optional
        The solve timeout in seconds, by default 30.
    """

    def __init__(self, page: PageT, timeout: float = 30) -> None:
        self._page = page
        self._timeout = timeout

        self._token: Optional[str] = None
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
    def _response_callback(self, response: Response) -> None:
        """
        The callback for intercepting reload responses.

        Parameters
        ----------
        response : Response
            The response.
        """

    @abstractmethod
    def solve_recaptcha(self, timeout: Optional[float] = None) -> str:
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
