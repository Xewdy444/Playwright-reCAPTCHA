import re
from typing import Iterable, Union

from playwright.async_api import Frame as AsyncFrame
from playwright.async_api import Locator as AsyncLocator
from playwright.sync_api import Frame as SyncFrame
from playwright.sync_api import Locator as SyncLocator

from playwright_recaptcha.errors import RecaptchaNotFoundError


def get_recaptcha_frame(
    frames: Iterable[Union[AsyncFrame, SyncFrame]]
) -> Union[AsyncFrame, SyncFrame]:
    """
    Find the reCAPTCHA frame in the provided list of frames.

    Parameters
    ----------
    frames : Iterable[Union[AsyncFrame, SyncFrame]]
        A list of frames to search for the reCAPTCHA frame.

    Returns
    -------
    Union[AsyncFrame, SyncFrame]
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


def get_recaptcha_checkbox(
    frames: Iterable[Union[AsyncFrame, SyncFrame]]
) -> Union[AsyncLocator, SyncLocator]:
    """
    Find the reCAPTCHA checkbox in the provided list of frames.

    Parameters
    ----------
    frames : Iterable[Union[AsyncFrame, SyncFrame]]
        A list of frames to search for the reCAPTCHA checkbox.

    Returns
    -------
    Union[AsyncLocator, SyncLocator]
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
