import unittest

from playwright.async_api import async_playwright

from playwright_recaptcha import (
    RecaptchaTimeoutError,
    RecaptchaVersionError,
    recaptchav3,
)


class TestRecaptchaSolver(unittest.IsolatedAsyncioTestCase):
    async def test_solver(self) -> None:
        async with async_playwright() as playwright:
            for playwright_browser in (
                playwright.chromium,
                playwright.firefox,
                playwright.webkit,
            ):
                browser = await playwright_browser.launch()
                page = await browser.new_page()
                await page.goto("https://antcpt.com/score_detector/")

                async with recaptchav3.AsyncSolver(page) as solver:
                    token = await solver.solve_recaptcha()
                    self.assertIsNotNone(token)

    async def test_solver_with_slow_browser(self) -> None:
        async with async_playwright() as playwright:
            for playwright_browser in (
                playwright.chromium,
                playwright.firefox,
                playwright.webkit,
            ):
                browser = await playwright_browser.launch(slow_mo=1000)
                page = await browser.new_page()
                await page.goto("https://antcpt.com/score_detector/")

                async with recaptchav3.AsyncSolver(page) as solver:
                    token = await solver.solve_recaptcha()
                    self.assertIsNotNone(token)

    async def test_recaptcha_not_found(self) -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto("https://www.google.com/")

            with self.assertRaises(RecaptchaTimeoutError):
                async with recaptchav3.AsyncSolver(page, timeout=10) as solver:
                    await solver.solve_recaptcha()

    async def test_recaptcha_version_error(self) -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto("https://cobra.ehr.com/ESS/Home/Login.aspx")

            with self.assertRaises(RecaptchaVersionError):
                async with recaptchav3.AsyncSolver(page) as solver:
                    await solver.solve_recaptcha()


if __name__ == "__main__":
    unittest.main()
