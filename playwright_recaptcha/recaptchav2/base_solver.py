import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Iterable, Optional, TypeVar, Union

from playwright.async_api import APIResponse as AsyncAPIResponse
from playwright.async_api import Page as AsyncPage
from playwright.async_api import Response as AsyncResponse
from playwright.sync_api import APIResponse as SyncAPIResponse
from playwright.sync_api import Page as SyncPage
from playwright.sync_api import Response as SyncResponse

from .recaptcha_box import RecaptchaBox

PageT = TypeVar("PageT", AsyncPage, SyncPage)
APIResponse = Union[AsyncAPIResponse, SyncAPIResponse]
Response = Union[AsyncResponse, SyncResponse]


class BaseSolver(ABC, Generic[PageT]):
    """
    The base class for reCAPTCHA v2 solvers.

    Parameters
    ----------
    page : PageT
        The Playwright page to solve the reCAPTCHA on.
    attempts : int, optional
        The number of solve attempts, by default 5.
    capsolver_api_key : Optional[str], optional
        The CapSolver API key, by default None.
        If None, the `CAPSOLVER_API_KEY` environment variable will be used.
    """

    def __init__(
        self, page: PageT, *, attempts: int = 5, capsolver_api_key: Optional[str] = None
    ) -> None:
        self._page = page
        self._attempts = attempts
        self._capsolver_api_key = capsolver_api_key or os.getenv("CAPSOLVER_API_KEY")

        self._token: Optional[str] = None
        self._payload_response: Union[APIResponse, Response, None] = None
        self._page.on("response", self._response_callback)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(page={self._page!r}, "
            f"attempts={self._attempts!r}, "
            f"capsolver_api_key={self._capsolver_api_key!r})"
        )

    def close(self) -> None:
        """Remove the response listener."""
        try:
            self._page.remove_listener("response", self._response_callback)
        except KeyError:
            pass

    @staticmethod
    @abstractmethod
    def _get_task_object(recaptcha_box: RecaptchaBox) -> Optional[str]:
        """
        Get the ID of the object in the reCAPTCHA image challenge task.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.

        Returns
        -------
        Optional[str]
            The object ID. Returns None if the task object is not recognized.
        """

    @abstractmethod
    def _response_callback(self, response: Response) -> None:
        """
        The callback for intercepting payload and userverify responses.

        Parameters
        ----------
        response : Response
            The response.
        """

    @abstractmethod
    def _get_capsolver_response(
        self, recaptcha_box: RecaptchaBox, image_data: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Get the CapSolver JSON response for an image.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.
        image_data : bytes
            The image data.

        Returns
        -------
        Optional[Dict[str, Any]]
            The CapSolver JSON response.
            Returns None if the task object is not recognized.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        """

    @abstractmethod
    def _solve_tiles(self, recaptcha_box: RecaptchaBox, indexes: Iterable[int]) -> None:
        """
        Solve the tiles in the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.
        indexes : Iterable[int]
            The indexes of the tiles that contain the task object.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        """

    @abstractmethod
    def _transcribe_audio(self, audio_url: str, *, language: str) -> Optional[str]:
        """
        Transcribe the reCAPTCHA audio challenge.

        Parameters
        ----------
        audio_url : str
            The reCAPTCHA audio URL.
        language : str
            The language of the audio.

        Returns
        -------
        Optional[str]
            The reCAPTCHA audio text.
            Returns None if the audio could not be converted.
        """

    @abstractmethod
    def _click_checkbox(self, recaptcha_box: RecaptchaBox) -> None:
        """
        Click the reCAPTCHA checkbox.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """

    @abstractmethod
    def _get_audio_url(self, recaptcha_box: RecaptchaBox) -> str:
        """
        Get the reCAPTCHA audio URL.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.

        Returns
        -------
        str
            The reCAPTCHA audio URL.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """

    @abstractmethod
    def _submit_audio_text(self, recaptcha_box: RecaptchaBox, text: str) -> None:
        """
        Submit the reCAPTCHA audio text.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.
        text : str
            The reCAPTCHA audio text.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """

    @abstractmethod
    def _submit_tile_answers(self, recaptcha_box: RecaptchaBox) -> None:
        """
        Submit the reCAPTCHA image challenge tile answers.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """

    @abstractmethod
    def _solve_image_challenge(self, recaptcha_box: RecaptchaBox) -> None:
        """
        Solve the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """

    @abstractmethod
    def _solve_audio_challenge(self, recaptcha_box: RecaptchaBox) -> None:
        """
        Solve the reCAPTCHA audio challenge.

        Parameters
        ----------
        recaptcha_box : RecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """

    @abstractmethod
    def recaptcha_is_visible(self) -> bool:
        """
        Check if a reCAPTCHA challenge or unchecked reCAPTCHA box is visible.

        Returns
        -------
        bool
            Whether a reCAPTCHA challenge or unchecked reCAPTCHA box is visible.
        """

    @abstractmethod
    def solve_recaptcha(
        self,
        *,
        attempts: Optional[int] = None,
        wait: bool = False,
        wait_timeout: float = 30,
        image_challenge: bool = False,
    ) -> str:
        """
        Solve the reCAPTCHA and return the `g-recaptcha-response` token.

        Parameters
        ----------
        attempts : Optional[int], optional
            The number of solve attempts, by default 5.
        wait : bool, optional
            Whether to wait for the reCAPTCHA to appear, by default False.
        wait_timeout : float, optional
            The amount of time in seconds to wait for the reCAPTCHA to appear,
            by default 30. Only used if `wait` is True.
        image_challenge : bool, optional
            Whether to solve the image challenge, by default False.

        Returns
        -------
        str
            The `g-recaptcha-response` token.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        RecaptchaNotFoundError
            If the reCAPTCHA was not found.
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        RecaptchaSolveError
            If the reCAPTCHA could not be solved.
        """
