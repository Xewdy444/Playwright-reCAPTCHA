from __future__ import annotations

import re
import time
from typing import Any, Optional

from playwright.async_api import Page, Response

from ..errors import RecaptchaTimeoutError


class AsyncSolver:
    """
    A class used to solve reCAPTCHA v3 asynchronously.

    Parameters
    ----------
    page : Page
        The Playwright page to solve the reCAPTCHA on.
    timeout : int, optional
        The solve timeout in seconds, by default 30.
    """

    def __init__(self, page: Page, timeout: int = 30) -> None:
        self._page = page
        self._timeout = timeout

        self._token: Optional[str] = None
        self._page.on("response", self._extract_token)

    def __repr__(self) -> str:
        return f"AsyncSolver(page={self._page!r}, timeout={self._timeout!r})"

    async def __aenter__(self) -> AsyncSolver:
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.close()

    async def _extract_token(self, response: Response) -> None:
        """
        Extract the `g-recaptcha-response` token from the reload response.

        Parameters
        ----------
        response : Response
            The response to extract the `g-recaptcha-response` token from.
        """
        if re.search("/recaptcha/(api2|enterprise)/reload", response.url) is None:
            return

        token_match = re.search('"rresp","(.*?)"', await response.text())

        if token_match is not None:
            self._token = token_match.group(1)

    def close(self) -> None:
        """Remove the reload response listener."""
        try:
            self._page.remove_listener("response", self._extract_token)
        except KeyError:
            pass

    async def solve_recaptcha(self, timeout: Optional[int] = None) -> str:
        """
        Wait for the reCAPTCHA to be solved and return the `g-recaptcha-response` token.

        Parameters
        ----------
        timeout : Optional[int], optional
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
        self._token = None
        timeout = timeout or self._timeout
        start_time = time.time()

        while self._token is None:
            if time.time() - start_time >= timeout:
                raise RecaptchaTimeoutError

            await self._page.wait_for_timeout(250)

        return self._token
