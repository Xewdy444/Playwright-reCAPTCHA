[![Python](https://img.shields.io/pypi/pyversions/playwright-recaptcha.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/playwright-recaptcha.svg)](https://pypi.org/project/playwright-recaptcha/)
[![Downloads](https://img.shields.io/pypi/dm/playwright-recaptcha.svg)](https://pypi.org/project/playwright-recaptcha/)
[![License](https://img.shields.io/badge/license-MIT-red)](https://github.com/Xewdy444/Playwright-reCAPTCHA/blob/main/LICENSE)

---

<div align="center">
  <a href="https://www.capsolver.com/">
    <img src="https://cdn.discordapp.com/attachments/1105172394655625306/1105180101802471575/20221207-160749.gif"/>
  </a>
  <br> At the lowest price on the market, you may receive a variety of solutions, including reCAPTCHA v2, reCAPTCHA v3, hCaptcha, hCaptcha Click, FunCaptcha, picture-to-text, AWS Amazon CAPTCHA, and more. With this service, 0.1s is the slowest speed ever measured.
</div>

---

# Playwright-reCAPTCHA
A Python library for solving reCAPTCHA v2 and v3 with Playwright.

## Solving reCAPTCHA v2
reCAPTCHA v2 is solved by using the following methods:

- Solving the audio challenge by transcribing the audio using the Google speech recognition API and entering the text as the response.
- Solving the image challenge using the CapSolver API for image classification.

## Solving reCAPTCHA v3
The solving of reCAPTCHA v3 is done by the browser itself, so this library simply waits for the browser to make a POST request to https://www.google.com/recaptcha/api2/reload or https://www.google.com/recaptcha/enterprise/reload and parses the response to get the `g-recaptcha-response` token.

---

All solvers return the `g-recaptcha-response` token, which is required for form submissions. If you are unsure about the version of reCAPTCHA being used, you can check out [this blog post](https://www.capsolver.com/blog/reCAPTCHA/identify-what-recaptcha-version-is-being-used) for more information.

## Installation
    pip install playwright-recaptcha

This library requires FFmpeg to be installed on your system in order to convert the audio challenge from reCAPTCHA v2 into text.

|   OS    |        Command         |
| :-----: | :--------------------: |
| Debian  | apt-get install ffmpeg |
|  MacOS  |  brew install ffmpeg   |
| Windows | winget install ffmpeg  |

You can also download the latest static build from [here](https://ffmpeg.org/download.html).

> **Note**
> Make sure to have the ffmpeg and ffprobe binaries in your system's PATH so that the SpeechRecognition library can find them.

## reCAPTCHA v2 Example
For more reCAPTCHA v2 examples, see the [examples folder](https://github.com/Xewdy444/Playwright-reCAPTCHA/tree/main/examples/recaptchav2).

```python
from playwright.sync_api import sync_playwright
from playwright_recaptcha import recaptchav2

with sync_playwright() as playwright:
    browser = playwright.firefox.launch()
    page = browser.new_page()
    page.goto("https://www.google.com/recaptcha/api2/demo")

    with recaptchav2.SyncSolver(page) as solver:
        token = solver.solve_recaptcha(wait=True)
        print(token)
```

If you would like to solve the image challenge, you can set the `CAPSOLVER_API_KEY` environment variable to your CapSolver API key. You can also pass the API key as an argument to `recaptchav2.SyncSolver()` with `capsolver_api_key="your_api_key"`. Then, set `image_challenge=True` in `solver.solve_recaptcha()`.

```python
with recaptchav2.SyncSolver(page, capsolver_api_key="your_api_key") as solver:
    token = solver.solve_recaptcha(wait=True, image_challenge=True)
    print(token)
```

## reCAPTCHA v3 Example
For more reCAPTCHA v3 examples, see the [examples folder](https://github.com/Xewdy444/Playwright-reCAPTCHA/tree/main/examples/recaptchav3).

```python
from playwright.sync_api import sync_playwright
from playwright_recaptcha import recaptchav3

with sync_playwright() as playwright:
    browser = playwright.firefox.launch()
    page = browser.new_page()

    with recaptchav3.SyncSolver(page) as solver:
        page.goto("https://antcpt.com/score_detector/")
        token = solver.solve_recaptcha()
        print(token)
```

It is best to initialize the solver before navigating to the page with the reCAPTCHA v3 challenge. This is because the solver adds a listener for the POST request to https://www.google.com/recaptcha/api2/reload or https://www.google.com/recaptcha/enterprise/reload and if the request is made before the listener is added, the `g-recaptcha-response` token will not be captured.


## Disclaimer
This library is intended for use in automated testing and development environments only and should not be used for any illegal or malicious purposes. Any use of this library for activities that violate the terms of service of any website or service is strictly prohibited. The contributors of this library will not be held liable for any damages or legal issues that may arise from the use of this library. By using this library, you agree to these terms and take full responsibility for your actions.
