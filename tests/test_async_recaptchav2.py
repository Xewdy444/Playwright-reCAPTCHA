import os

import pytest
from playwright.async_api import Page, async_playwright

from playwright_recaptcha import (
    CapSolverError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


async def get_recaptcha_token(
    page: Page, api_key: str, site_key: str, website_url: str
) -> str:
    """
    Get the reCAPTCHA token using the CapSolver API.

    Parameters
    ----------
    page : Page
        The Playwright page.
    api_key : str
        The CapSolver API key.
    site_key : str
        The reCAPTCHA site key.
    website_url : str
        The URL of the website where the reCAPTCHA is located.

    Returns
    -------
    str
        The reCAPTCHA token.

    Raises
    -------
    CapSolverError
        If there is an error creating the task or getting the result.
    """
    create_task_response = await page.request.post(
        "https://api.capsolver.com/createTask",
        data={
            "clientKey": api_key,
            "task": {
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": website_url,
                "websiteKey": site_key,
            },
        },
    )

    task_json = await create_task_response.json()

    if task_json["errorId"] != 0:
        raise CapSolverError(task_json["errorDescription"])

    while True:
        task_result = await page.request.post(
            "https://api.capsolver.com/getTaskResult",
            data={"clientKey": api_key, "taskId": task_json["taskId"]},
        )

        task_result_json = await task_result.json()

        if task_result_json["errorId"] != 0:
            raise CapSolverError(task_result_json["errorDescription"])

        if task_result_json["status"] == "ready":
            break

        await page.wait_for_timeout(1000)

    return task_result_json["solution"]["gRecaptchaResponse"]


@pytest.mark.asyncio
@pytest.mark.xfail(raises=RecaptchaRateLimitError)
async def test_solver_with_normal_recaptcha() -> None:
    """Test the solver with a normal reCAPTCHA."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        async with recaptchav2.AsyncSolver(page) as solver:
            await solver.solve_recaptcha(wait=True)


@pytest.mark.asyncio
@pytest.mark.xfail(raises=(RecaptchaNotFoundError, RecaptchaRateLimitError))
async def test_solver_with_hidden_recaptcha() -> None:
    """Test the solver with a hidden reCAPTCHA."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()

        await page.goto("https://www.google.com/recaptcha/api2/demo?invisible=true")
        await page.get_by_role("button").click()

        async with recaptchav2.AsyncSolver(page) as solver:
            await solver.solve_recaptcha(wait=True)


@pytest.mark.asyncio
@pytest.mark.xfail(raises=RecaptchaRateLimitError)
async def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(slow_mo=1000)
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        async with recaptchav2.AsyncSolver(page) as solver:
            await solver.solve_recaptcha(wait=True)


@pytest.mark.asyncio
@pytest.mark.xfail(raises=CapSolverError)
async def test_solver_with_image_challenge() -> None:
    """Test the solver with an image challenge."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        async with recaptchav2.AsyncSolver(page) as solver:
            await solver.solve_recaptcha(wait=True, image_challenge=True)


@pytest.mark.asyncio
async def test_recaptcha_not_found_error() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/")

        with pytest.raises(RecaptchaNotFoundError):
            async with recaptchav2.AsyncSolver(page) as solver:
                await solver.solve_recaptcha()


@pytest.mark.asyncio
async def test_token_injection() -> None:
    """Test the token injection with a reCAPTCHA."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        token = await get_recaptcha_token(
            page,
            os.getenv("CAPSOLVER_API_KEY"),
            "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-",
            "https://www.google.com/recaptcha/api2/demo",
        )

        async with recaptchav2.AsyncSolver(page) as solver:
            await solver.inject_token(token, wait=True)

        async with page.expect_navigation():
            await page.get_by_role("button", name="Submit").click()

        assert await page.text_content("body") == "Verification Success... Hooray!"
