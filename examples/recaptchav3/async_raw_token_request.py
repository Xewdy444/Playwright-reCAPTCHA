import asyncio

import httpx
from playwright.async_api import async_playwright

from playwright_recaptcha import recaptchav3


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()

        async with recaptchav3.AsyncSolver(page, block_token_requests=True) as solver:
            await page.goto("https://antcpt.com/score_detector/")
            token = await solver.solve_recaptcha()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://antcpt.com/score_detector/verify.php",
                json={"g-recaptcha-response": token},
            )

            print(response.json())


if __name__ == "__main__":
    asyncio.run(main())
