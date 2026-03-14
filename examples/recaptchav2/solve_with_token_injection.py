import os

from playwright.sync_api import Page, sync_playwright

from playwright_recaptcha import CapSolverError, recaptchav2


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


def main() -> None:
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

        print(page.text_content("body"))


if __name__ == "__main__":
    main()
