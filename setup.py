from setuptools import find_packages, setup

setup(
    name="playwright-recaptcha",
    version="0.0.5",
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
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Framework :: AsyncIO",
    ],
)
