from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as file:
    long_description = file.read()

setup(
    name="playwright-recaptcha",
    version="0.1.0",
    author="Xewdy444",
    author_email="xewdy@xewdy.tech",
    description="A library for solving reCAPTCHA v2 and v3 with Playwright",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Xewdy444/Playwright-reCAPTCHA",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "httpx==0.23.3",
        "playwright==1.31.0",
        "pydub==0.25.1",
        "SpeechRecognition==3.9.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Framework :: AsyncIO",
    ],
)
