from __future__ import annotations

import re
import time
from typing import Any, Optional

from playwright.sync_api import Page, Response

from ..errors import RecaptchaTimeoutError
from .base_solver import BaseSolver


class SyncSolver(BaseSolver[Page]):
    """
    A class for solving reCAPTCHA v3 synchronously with Playwright.

    Parameters
    ----------
    page : Page
        The Playwright page to solve the reCAPTCHA on.
    timeout : float, optional
        The solve timeout in seconds, by default 30.
    """

    def __enter__(self) -> SyncSolver:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _response_callback(self, response: Response) -> None:
        """
        The callback for intercepting reload responses.

        Parameters
        ----------
        response : Response
            The response.
        """
        if re.search("/recaptcha/(api2|enterprise)/reload", response.url) is None:
            return

        token_match = re.search('"rresp","(.*?)"', response.text())

        if token_match is not None:
            self._token = token_match.group(1)

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
        self._token = None
        timeout = timeout or self._timeout
        start_time = time.time()

        while self._token is None:
            if time.time() - start_time >= timeout:
                raise RecaptchaTimeoutError

            self._page.wait_for_timeout(250)

        return self._token
