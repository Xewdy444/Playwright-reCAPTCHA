import unittest

from playwright.sync_api import sync_playwright

from playwright_recaptcha import (
    RecaptchaTimeoutError,
    RecaptchaVersionError,
    recaptchav3,
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
                page.goto("https://antcpt.com/score_detector/")

                with recaptchav3.SyncSolver(page) as solver:
                    token = solver.solve_recaptcha()
                    self.assertIsNotNone(token)

    def test_solver_with_slow_browser(self) -> None:
        with sync_playwright() as playwright:
            for playwright_browser in (
                playwright.chromium,
                playwright.firefox,
                playwright.webkit,
            ):
                browser = playwright_browser.launch(slow_mo=1000)
                page = browser.new_page()
                page.goto("https://antcpt.com/score_detector/")

                with recaptchav3.SyncSolver(page) as solver:
                    token = solver.solve_recaptcha()
                    self.assertIsNotNone(token)

    def test_recaptcha_not_found(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto("https://www.google.com/")

            with self.assertRaises(RecaptchaTimeoutError), recaptchav3.SyncSolver(
                page, timeout=10
            ) as solver:
                solver.solve_recaptcha()

    def test_recaptcha_version_error(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto("https://cobra.ehr.com/ESS/Home/Login.aspx")

            with self.assertRaises(RecaptchaVersionError), recaptchav3.SyncSolver(
                page
            ) as solver:
                solver.solve_recaptcha()


if __name__ == "__main__":
    unittest.main()
