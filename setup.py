from setuptools import find_packages, setup

from playwright_recaptcha import __version__

setup(
    name="playwright-recaptcha",
    version=__version__,
    author="Xewdy444",
    author_email="xewdy@xewdy.tech",
    description="A libary for solving reCAPTCHA v2 and v3 with Playwright",
    license="MIT",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Xewdy444/Playwright-reCAPTCHA",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "httpx==0.23.3",
        "playwright==1.30.0",
        "pydub==0.25.1",
        "SpeechRecognition==3.9.0",
    ],
)
