import os

import pytest
from playwright.sync_api import Page, sync_playwright

from playwright_recaptcha import (
    CapSolverError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


def get_recaptcha_token(
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
    create_task_response = page.request.post(
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

    task_json = create_task_response.json()

    if task_json["errorId"] != 0:
        raise CapSolverError(task_json["errorDescription"])

    while True:
        task_result = page.request.post(
            "https://api.capsolver.com/getTaskResult",
            data={"clientKey": api_key, "taskId": task_json["taskId"]},
        )

        task_result_json = task_result.json()

        if task_result_json["errorId"] != 0:
            raise CapSolverError(task_result_json["errorDescription"])

        if task_result_json["status"] == "ready":
            break

        page.wait_for_timeout(1000)

    return task_result_json["solution"]["gRecaptchaResponse"]


@pytest.mark.xfail(raises=RecaptchaRateLimitError)
def test_solver_with_normal_recaptcha() -> None:
    """Test the solver with a normal reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True)


@pytest.mark.xfail(raises=(RecaptchaNotFoundError, RecaptchaRateLimitError))
def test_solver_with_hidden_recaptcha() -> None:
    """Test the solver with a hidden reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        page.goto("https://www.google.com/recaptcha/api2/demo?invisible=true")
        page.get_by_role("button").click()

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True)


@pytest.mark.xfail(raises=RecaptchaRateLimitError)
def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(slow_mo=1000)
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True)


@pytest.mark.xfail(raises=CapSolverError)
def test_solver_with_image_challenge() -> None:
    """Test the solver with an image challenge."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True, image_challenge=True)


def test_recaptcha_not_found_error() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/")

        with pytest.raises(RecaptchaNotFoundError), recaptchav2.SyncSolver(
            page
        ) as solver:
            solver.solve_recaptcha()


def test_token_injection() -> None:
    """Test the token injection with a reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        token = get_recaptcha_token(
            page,
            os.getenv("CAPSOLVER_API_KEY"),
            "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-",
            "https://www.google.com/recaptcha/api2/demo",
        )

        with recaptchav2.SyncSolver(page) as solver:
            solver.inject_token(token, wait=True)

        with page.expect_navigation():
            page.get_by_role("button", name="Submit").click()

        assert page.text_content("body") == "Verification Success... Hooray!"
