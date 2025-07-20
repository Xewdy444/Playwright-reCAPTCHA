import httpx
from playwright.sync_api import sync_playwright

from playwright_recaptcha import recaptchav3


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        with recaptchav3.SyncSolver(page, block_token_requests=True) as solver:
            page.goto("https://antcpt.com/score_detector/")
            token = solver.solve_recaptcha()

        with httpx.Client() as client:
            response = client.post(
                "https://antcpt.com/score_detector/verify.php",
                json={"g-recaptcha-response": token},
            )

            print(response.json())


if __name__ == "__main__":
    main()
