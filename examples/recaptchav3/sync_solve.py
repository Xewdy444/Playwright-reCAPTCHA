import re

from playwright.sync_api import sync_playwright

from playwright_recaptcha import recaptchav3


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto("https://antcpt.com/score_detector/")

        with recaptchav3.SyncSolver(page) as solver:
            token = solver.solve_recaptcha()
            print(token)

        score_pattern = re.compile(r"Your score is: (\d\.\d)")
        score_locator = page.get_by_text(score_pattern)
        print(score_locator.inner_text())


if __name__ == "__main__":
    main()
