[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![PyPI](https://img.shields.io/pypi/v/playwright-recaptcha.svg)](https://pypi.org/project/playwright-recaptcha/)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/Xewdy444/Playwright-reCAPTCHA/blob/main/LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# Playwright-reCAPTCHA
A Python libary for solving reCAPTCHA v2 and v3 with Playwright.

## Solving reCAPTCHA v2
reCAPTCHA v2 is solved by transcribing the audio challenge using the Google speech recognition API and entering the text as the response.

## Solving reCAPTCHA v3
reCAPTCHA v3 is solved by waiting for the reload POST request (https://www.google.com/recaptcha/api2/reload or https://www.google.com/recaptcha/enterprise/reload) and parsing the token from the response.

---

All of the solvers return the g-recaptcha-response token required for the form submission.

It's important to note that reCAPTCHA v3 uses a token-based scoring system, where each user's token is automatically assigned a score based on their interactions with the website. This score is used to determine the likelihood of the user being a human or a bot. The token is then passed to the website's server, and it's up to the website owner to decide what action to take based on the score.

# Installation
```
pip install playwright-recaptcha
```

This library requires ffmpeg to be installed on your system in order to convert the audio challenge from reCAPTCHA v2 into text.

|   OS    |                                          Install                                           |
| :-----: | :----------------------------------------------------------------------------------------: |
| Debian  |                                sudo apt-get install ffmpeg                                 |
|  MacOS  |                                    brew install ffmpeg                                     |
| Windows | Download and install the latest static build from [here](https://ffmpeg.org/download.html) |

> **Note**
> Make sure to have ffmpeg and ffprobe in your system's PATH so that the library can find them.

# Examples

## reCAPTCHA v2

### Synchronous
```py
from playwright.sync_api import sync_playwright
from playwright_recaptcha import recaptchav2

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.google.com/recaptcha/api2/demo")

    with recaptchav2.SyncSolver(page) as solver:
        token = solver.solve_recaptcha()
        print(token)
```

### Asynchronous
```py
import asyncio
from playwright.async_api import async_playwright
from playwright_recaptcha import recaptchav2

async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        async with recaptchav2.AsyncSolver(page) as solver:
            token = await solver.solve_recaptcha()
            print(token)

asyncio.run(main())
```

## reCAPTCHA v3

### Synchronous
```py
from playwright.sync_api import sync_playwright
from playwright_recaptcha import recaptchav3

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("https://antcpt.com/score_detector/")

    with recaptchav3.SyncSolver(page) as solver:
        token = solver.solve_recaptcha()
        print(token)
```

### Asynchronous
```py
import asyncio
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

asyncio.run(main())
```

# Exceptions
|        Exception        |                                                                     Description                                                                     |
| :---------------------: | :-------------------------------------------------------------------------------------------------------------------------------------------------: |
|     RecaptchaError      |                           The base class for reCAPTCHA exceptions, used as a catch-all for any reCAPTCHA-related errors.                            |
|  RecaptchaVersionError  |     An exception raised when the reCAPTCHA v3 solver is used for reCAPTCHA v2. To solve this issue, simply use the reCAPTCHA v2 solver instead.     |
| RecaptchaNotFoundError  |                                       An exception raised when the reCAPTCHA v2 was not found on the website.                                       |
| RecaptchaRateLimitError | An exception raised when the reCAPTCHA rate limit has been reached. This can happen if the library is being used to solve reCAPTCHA v2 too quickly. |
|   RecaptchaSolveError   |           An exception raised when the reCAPTCHA v2 could not be solved via speech-to-text conversion in the specified amount of retries.           |
|  RecaptchaTimeoutError  |                             An exception raised when the reCAPTCHA v3 could not be solved within the specified timeout.                             |

# Disclaimer
This library is intended for use in automated testing and development environments only and should not be used for any illegal or malicious purposes. Any use of this library for activities that violate the terms of service of any website or service is strictly prohibited. The contributors of this library will not be held liable for any damages or legal issues that may arise from the use of this library. By using this library, you agree to these terms and take full responsibility for your actions.
