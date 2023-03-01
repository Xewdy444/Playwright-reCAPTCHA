from playwright.sync_api import sync_playwright

from playwright_recaptcha import recaptchav2


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        page.goto(
            "https://www.google.com/recaptcha/api2/demo", wait_until="networkidle"
        )

        with recaptchav2.SyncSolver(page) as solver:
            token = solver.solve_recaptcha()
            print(token)


if __name__ == "__main__":
    main()
