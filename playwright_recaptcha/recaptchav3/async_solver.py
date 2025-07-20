from __future__ import annotations

import re
import time
from typing import Any, Optional

from playwright.async_api import Page, Response, Route

from ..errors import RecaptchaTimeoutError
from .base_solver import BaseSolver


class AsyncSolver(BaseSolver[Page]):
    """
    A class for solving reCAPTCHA v3 asynchronously with Playwright.

    Parameters
    ----------
    page : Page
        The Playwright page to solve the reCAPTCHA on.
    timeout : float, optional
        The solve timeout in seconds, by default 30.
    """

    async def __aenter__(self) -> AsyncSolver:
        if self._block_token_requests and not self._route_callback_added:
            await self.add_token_request_blocker()

        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def _route_callback(self, route: Route) -> None:
        """
        The callback for intercepting requests with the reCAPTCHA token.

        Parameters
        ----------
        route : Route
            The route.
        """
        if self._token is None:
            await route.continue_()
            return

        if (
            self._token in route.request.url
            or (
                route.request.post_data_buffer is not None
                and self._token.encode("utf-8") in route.request.post_data_buffer
            )
            or any(self._token in value for value in route.request.headers.values())
        ):
            await route.abort()
            return

        await route.continue_()

    async def _response_callback(self, response: Response) -> None:
        """
        The callback for intercepting reload responses.

        Parameters
        ----------
        response : Response
            The response.
        """
        if re.search("/recaptcha/(api2|enterprise)/reload", response.url) is None:
            return

        token_match = re.search('"rresp","(.*?)"', await response.text())

        if token_match is not None:
            self._token = token_match.group(1)

    async def close(self) -> None:
        """Remove the interceptors and listeners."""
        super().close()
        await self.remove_token_request_blocker()

    async def add_token_request_blocker(self) -> None:
        """Add the route callback for blocking reCAPTCHA token requests."""
        if self._route_callback_added:
            return

        await self._page.route("**/*", self._route_callback)
        self._route_callback_added = True

    async def remove_token_request_blocker(self) -> None:
        """Remove the route callback for blocking reCAPTCHA token requests."""
        if not self._route_callback_added:
            return

        await self._page.unroute("**/*", self._route_callback)
        self._route_callback_added = False

    async def solve_recaptcha(self, *, timeout: Optional[float] = None) -> str:
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

            await self._page.wait_for_timeout(250)

        return self._token
