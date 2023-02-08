import asyncio

from playwright.async_api import async_playwright

from playwright_recaptcha import recaptchav2


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        async with recaptchav2.AsyncSolver(page) as solver:
            token = await solver.solve_recaptcha()
            print(token)


if __name__ == "__main__":
    asyncio.run(main())
