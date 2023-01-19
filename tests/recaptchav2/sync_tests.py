import unittest

from playwright.sync_api import sync_playwright

from playwright_recaptcha import (
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


class TestRecaptchaSolver(unittest.TestCase):
    def test_solver(self) -> None:
        with sync_playwright() as playwright:
            for playwright_browser in (
                playwright.chromium,
                playwright.firefox,
                playwright.webkit,
            ):
                browser = playwright_browser.launch()
                page = browser.new_page()
                page.goto("https://www.google.com/recaptcha/api2")

                with recaptchav2.SyncSolver(page) as solver:
                    try:
                        token = solver.solve_recaptcha()
                        self.assertIsNotNone(token)
                    except RecaptchaRateLimitError:
                        pass

    def test_solver_with_slow_browser(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(slow_mo=1000)
            page = browser.new_page()
            page.goto("https://www.google.com/recaptcha/api2")

            with recaptchav2.SyncSolver(page) as solver:
                try:
                    token = solver.solve_recaptcha()
                    self.assertIsNotNone(token)
                except RecaptchaRateLimitError:
                    pass

    def test_recaptcha_not_found(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto("https://www.google.com/")

            with self.assertRaises(RecaptchaNotFoundError), recaptchav2.SyncSolver(
                page
            ) as solver:
                solver.solve_recaptcha()


if __name__ == "__main__":
    unittest.main()
