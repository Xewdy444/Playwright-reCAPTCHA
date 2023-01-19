import re
from typing import Iterable

from playwright.sync_api import Frame, Locator

from playwright_recaptcha.errors import RecaptchaNotFoundError


def get_recaptcha_frame(frames: Iterable[Frame]) -> Frame:
    """
    Get the reCAPTCHA frame.

    Parameters
    ----------
    frames : Iterable[Frame]
        The frames to search for the reCAPTCHA frame.

    Returns
    -------
    Frame
        The reCAPTCHA frame.

    Raises
    ------
    RecaptchaNotFoundError
        If the reCAPTCHA frame was not found.
    """
    for frame in frames:
        if re.search("/recaptcha/(api2|enterprise)/bframe", frame.url) is not None:
            return frame

    raise RecaptchaNotFoundError


def get_recaptcha_checkbox(frames: Iterable[Frame]) -> Locator:
    """
    Get the reCAPTCHA checkbox.

    Parameters
    ----------
    frames : Iterable[Frame]
        The frames to search for the reCAPTCHA checkbox.

    Returns
    -------
    Locator
        The reCAPTCHA checkbox.

    Raises
    ------
    RecaptchaNotFoundError
        If the reCAPTCHA checkbox was not found.
    """
    for frame in frames:
        if re.search("/recaptcha/(api2|enterprise)/anchor", frame.url) is not None:
            return frame.get_by_role("checkbox", name="I'm not a robot")

    raise RecaptchaNotFoundError
