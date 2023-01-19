from __future__ import annotations

import re
import time
from typing import Any, Optional

from playwright.sync_api import Page, Response

from playwright_recaptcha.errors import RecaptchaTimeoutError, RecaptchaVersionError


class SyncSolver:
    """
    A class used to solve reCAPTCHA v3 synchronously.

    Parameters
    ----------
    page : Page
        The playwright page to solve the reCAPTCHA on.
    timeout : int, optional
        The timeout in seconds, by default 30.

    Attributes
    ----------
    token : Optional[str]
        The reCAPTCHA token.

    Methods
    -------
    close() -> None
        Remove the reload response listener.
    solve_recaptcha(timeout: Optional[int] = None) -> str
        Solve the reCAPTCHA and return the token.

    Raises
    ------
    RecaptchaTimeoutError
        If the timeout is reached.
    RecaptchaVersionError
        If the reCAPTCHA is not version 3.
    """

    def __init__(self, page: Page, timeout: int = 30) -> None:
        self._page = page
        self._timeout = timeout
        self.token = None

    def __repr__(self) -> str:
        return f"SyncSolver(page={self._page!r}, timeout={self._timeout!r})"

    def __enter__(self) -> SyncSolver:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _extract_token(self, response: Response) -> None:
        """
        Extract the reCAPTCHA token from the userverify response.

        Parameters
        ----------
        response : Response
            The response to extract the token from.
        """
        if re.search("/recaptcha/(api2|enterprise)/reload", response.url) is None:
            return

        token_match = re.search(r'"rresp","(.*?)"', response.text())

        if token_match is not None:
            self.token = token_match.group(1)

    def close(self) -> None:
        """Remove the reload response listener."""
        try:
            self._page.remove_listener("response", self._extract_token)
        except KeyError:
            pass

    def solve_recaptcha(self, timeout: Optional[int] = None) -> str:
        """
        Solve the reCAPTCHA and return the token.

        Parameters
        ----------
        timeout : Optional[int], optional
            The timeout in seconds, by default None.

        Returns
        -------
        str
            The reCAPTCHA token.

        Raises
        ------
        RecaptchaTimeoutError
            If the timeout is reached.
        RecaptchaVersionError
            If the reCAPTCHA is not version 3.
        """
        self._page.on("response", self._extract_token)
        start_time = time.time()
        timeout = timeout or self._timeout

        while self.token is None:
            if time.time() - start_time >= timeout:
                raise RecaptchaTimeoutError

            self._page.wait_for_timeout(100)

        if len(self.token) > 600:
            raise RecaptchaVersionError

        return self.token
