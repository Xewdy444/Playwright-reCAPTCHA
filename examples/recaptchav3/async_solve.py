import asyncio
import re

from playwright.async_api import async_playwright

from playwright_recaptcha import recaptchav3


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://antcpt.com/score_detector/")

        async with recaptchav3.AsyncSolver(page) as solver:
            token = await solver.solve_recaptcha()
            print(token)

        score_pattern = re.compile(r"Your score is: (\d\.\d)")
        score_locator = page.get_by_text(score_pattern)
        print(await score_locator.inner_text())


if __name__ == "__main__":
    asyncio.run(main())
