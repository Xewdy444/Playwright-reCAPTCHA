from __future__ import annotations

import io
import random
import re
from typing import Any, Optional

import httpx
import pydub
import speech_recognition
from playwright.sync_api import Page, Response

from playwright_recaptcha.errors import (
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
)
from playwright_recaptcha.recaptchav2.recaptcha_box import SyncRecaptchaBox


class SyncSolver:
    """
    A class used to solve reCAPTCHA v2 synchronously.

    Parameters
    ----------
    page : Page
        The playwright page to solve the reCAPTCHA on.
    attempts : int, optional
        The number of solve attempts, by default 3.

    Attributes
    ----------
    token : Optional[str]
        The g-recaptcha-response token.

    Methods
    -------
    close() -> None
        Remove the userverify response listener.
    solve_recaptcha(attempts: Optional[int] = None) -> str
        Solve the reCAPTCHA and return the g-recaptcha-response token.

    Raises
    ------
    RecaptchaNotFoundError
        If the reCAPTCHA was not found.
    RecaptchaRateLimitError
        If the reCAPTCHA rate limit has been exceeded.
    RecaptchaSolveError
        If the reCAPTCHA could not be solved.
    """

    def __init__(self, page: Page, attempts: int = 3) -> None:
        self._page = page
        self._attempts = attempts
        self.token: Optional[str] = None

    def __repr__(self) -> str:
        return f"SyncSolver(page={self._page!r}, attempts={self._attempts!r})"

    def __enter__(self) -> SyncSolver:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @staticmethod
    def _convert_audio_to_text(audio_url: str) -> Optional[str]:
        """
        Convert the reCAPTCHA audio to text.

        Parameters
        ----------
        audio_url : str
            The reCAPTCHA audio URL.

        Returns
        -------
        Optional[str]
            The reCAPTCHA audio text.
        """
        response = httpx.get(audio_url)

        wav_audio = io.BytesIO()
        mp3_audio = io.BytesIO(response.content)
        audio = pydub.AudioSegment.from_mp3(mp3_audio)
        audio.export(wav_audio, format="wav")

        recognizer = speech_recognition.Recognizer()

        with speech_recognition.AudioFile(wav_audio) as source:
            audio_data = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio_data)
        except speech_recognition.UnknownValueError:
            return None

    def _random_delay(self) -> None:
        """Delay the execution for a random amount of time between 1 and 4 seconds."""
        self._page.wait_for_timeout(random.randint(1000, 4000))

    def _extract_token(self, response: Response) -> None:
        """
        Extract the g-recaptcha-response token from the userverify response.

        Parameters
        ----------
        response : Response
            The response to extract the g-recaptcha-response token from.
        """
        if re.search("/recaptcha/(api2|enterprise)/userverify", response.url) is None:
            return

        token_match = re.search('"uvresp","(.*?)"', response.text())

        if token_match is not None:
            self.token = token_match.group(1)

    def _get_audio_url(self, recaptcha_box: SyncRecaptchaBox) -> str:
        """
        Get the reCAPTCHA audio URL.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.

        Returns
        -------
        str
            The reCAPTCHA audio URL.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        if recaptcha_box.audio_challenge_button.is_visible():
            recaptcha_box.audio_challenge_button.click(force=True)

        while True:
            if recaptcha_box.audio_challenge_is_visible():
                break

            if recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            self._page.wait_for_timeout(100)

        return recaptcha_box.audio_download_button.get_attribute("href")

    def _submit_audio_text(self, recaptcha_box: SyncRecaptchaBox, text: str) -> None:
        """
        Submit the reCAPTCHA audio text.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.
        text : str
            The reCAPTCHA audio text.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        recaptcha_box.audio_challenge_textbox.fill(text)
        recaptcha_box.audio_challenge_verify_button.click()

        while recaptcha_box.frames_are_attached():
            if (
                recaptcha_box.checkbox.is_checked()
                or recaptcha_box.solve_failure_is_visible()
            ):
                break

            if recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            self._page.wait_for_timeout(100)

    def close(self) -> None:
        """Remove the userverify response listener."""
        try:
            self._page.remove_listener("response", self._extract_token)
        except KeyError:
            pass

    def solve_recaptcha(self, attempts: Optional[int] = None) -> str:
        """
        Solve the reCAPTCHA and return the g-recaptcha-response token.

        Parameters
        ----------
        attempts : Optional[int], optional
            The number of solve attempts, by default 3.

        Returns
        -------
        str
            The g-recaptcha-response token.

        Raises
        ------
        RecaptchaNotFoundError
            If the reCAPTCHA was not found.
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        RecaptchaSolveError
            If the reCAPTCHA could not be solved.
        """
        self.token = None
        self._page.on("response", self._extract_token)

        attempts = attempts or self._attempts
        recaptcha_box = SyncRecaptchaBox.from_frames(self._page.frames)

        if recaptcha_box.checkbox.is_hidden():
            raise RecaptchaNotFoundError

        recaptcha_box.checkbox.click(force=True)

        while True:
            if (
                recaptcha_box.audio_challenge_is_visible()
                or recaptcha_box.audio_challenge_button.is_visible()
                and recaptcha_box.audio_challenge_button.is_enabled()
            ):
                break

            if (
                not recaptcha_box.frames_are_attached()
                or recaptcha_box.checkbox.is_checked()
            ):
                if self.token is None:
                    raise RecaptchaSolveError

                return self.token

            self._page.wait_for_timeout(100)

        while attempts > 0:
            self._random_delay()
            url = self._get_audio_url(recaptcha_box)
            text = self._convert_audio_to_text(url)

            if text is None:
                recaptcha_box.new_challenge_button.click()
                attempts -= 1
                continue

            self._random_delay()
            self._submit_audio_text(recaptcha_box, text)

            if (
                not recaptcha_box.frames_are_attached()
                or recaptcha_box.checkbox.is_checked()
            ):
                if self.token is None:
                    raise RecaptchaSolveError

                return self.token

            recaptcha_box.new_challenge_button.click()
            attempts -= 1

        raise RecaptchaSolveError
