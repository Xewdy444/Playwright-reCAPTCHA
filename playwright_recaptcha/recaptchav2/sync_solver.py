from __future__ import annotations

import base64
import os
import random
import re
from io import BytesIO
from json import JSONDecodeError
from typing import Any, Dict, Iterable, List, Optional, Union

import speech_recognition
from playwright.sync_api import APIResponse, Locator, Page, Response
from pydub import AudioSegment
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

from ..errors import (
    CapSolverError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
)
from .recaptcha_box import SyncRecaptchaBox


class SyncSolver:
    """
    A class for solving reCAPTCHA v2 synchronously with Playwright.

    Parameters
    ----------
    page : Page
        The Playwright page to solve the reCAPTCHA on.
    attempts : int, optional
        The number of solve attempts, by default 5.
    capsolver_api_key : Optional[str], optional
        The CapSolver API key, by default None.
        If None, the `CAPSOLVER_API_KEY` environment variable will be used.
    """

    def __init__(
        self, page: Page, *, attempts: int = 5, capsolver_api_key: Optional[str] = None
    ) -> None:
        self._page = page
        self._attempts = attempts
        self._capsolver_api_key = capsolver_api_key or os.getenv("CAPSOLVER_API_KEY")

        self._token: Optional[str] = None
        self._payload_response: Union[APIResponse, Response, None] = None
        self._page.on("response", self._response_callback)

    def __repr__(self) -> str:
        return (
            f"SyncSolver(page={self._page!r}, "
            f"attempts={self._attempts!r}, "
            f"capsolver_api_key={self._capsolver_api_key!r})"
        )

    def __enter__(self) -> SyncSolver:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @staticmethod
    def _get_task_object(recaptcha_box: SyncRecaptchaBox) -> Optional[str]:
        """
        Get the ID of the object in the reCAPTCHA image challenge task.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.

        Returns
        -------
        Optional[str]
            The object ID. Returns None if the task object is not recognized.
        """
        object_dict = {
            "taxis": "/m/0pg52",
            "bus": "/m/01bjv",
            "school bus": "/m/02yvhj",
            "motorcycles": "/m/04_sv",
            "tractors": "/m/013xlm",
            "chimneys": "/m/01jk_4",
            "crosswalks": "/m/014xcs",
            "traffic lights": "/m/015qff",
            "bicycles": "/m/0199g",
            "parking meters": "/m/015qbp",
            "cars": "/m/0k4j",
            "bridges": "/m/015kr",
            "boats": "/m/019jd",
            "palm trees": "/m/0cdl1",
            "mountains or hills": "/m/09d_r",
            "fire hydrant": "/m/01pns0",
            "stairs": "/m/01lynh",
        }

        task = recaptcha_box.bframe_frame.locator("div").all_inner_texts()

        for object_name, object_id in object_dict.items():
            if object_name in task[0]:
                return object_id

        return None

    def _response_callback(self, response: Response) -> None:
        """
        The callback for intercepting payload and userverify responses.

        Parameters
        ----------
        response : Response
            The response.
        """
        if (
            re.search("/recaptcha/(api2|enterprise)/payload", response.url) is not None
            and self._payload_response is None
        ):
            self._payload_response = response
        elif (
            re.search("/recaptcha/(api2|enterprise)/userverify", response.url)
            is not None
        ):
            token_match = re.search('"uvresp","(.*?)"', response.text())

            if token_match is not None:
                self._token = token_match.group(1)

    def _random_delay(self, short: bool = True) -> None:
        """
        Delay the browser for a random amount of time.

        Parameters
        ----------
        short : bool, optional
            Whether to delay for a short amount of time, by default True.
        """
        delay_time = random.randint(150, 350) if short else random.randint(1250, 1500)
        self._page.wait_for_timeout(delay_time)

    def _get_capsolver_response(
        self, recaptcha_box: SyncRecaptchaBox, image_data: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Get the CapSolver JSON response for an image.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.
        image_data : bytes
            The image data.

        Returns
        -------
        Optional[Dict[str, Any]]
            The CapSolver JSON response.
            Returns None if the task object is not recognized.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        """
        image = base64.b64encode(image_data).decode("utf-8")
        task_object = self._get_task_object(recaptcha_box)

        if task_object is None:
            return None

        payload = {
            "clientKey": self._capsolver_api_key,
            "task": {
                "type": "ReCaptchaV2Classification",
                "image": image,
                "question": task_object,
            },
        }

        response = self._page.request.post(
            "https://api.capsolver.com/createTask", data=payload
        )

        try:
            response_json = response.json()
        except JSONDecodeError as err:
            raise CapSolverError from err

        if response_json["errorId"] != 0:
            raise CapSolverError(response_json["errorDescription"])

        return response_json

    def _solve_tiles(
        self, recaptcha_box: SyncRecaptchaBox, indexes: Iterable[int]
    ) -> None:
        """
        Solve the tiles in the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.
        indexes : Iterable[int]
            The indexes of the tiles that contain the task object.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        """
        changing_tiles: List[Locator] = []

        for index in indexes:
            tile = recaptcha_box.tile_selector.nth(index)
            tile.click()

            if "rc-imageselect-dynamic-selected" in tile.get_attribute("class"):
                changing_tiles.append(tile)

            self._random_delay()

        while changing_tiles:
            for tile in changing_tiles.copy():
                if "rc-imageselect-dynamic-selected" in tile.get_attribute("class"):
                    continue

                image_url = tile.locator("img").get_attribute("src")
                response = self._page.request.get(image_url)

                capsolver_response = self._get_capsolver_response(
                    recaptcha_box, response.body()
                )

                if (
                    capsolver_response is None
                    or not capsolver_response["solution"]["hasObject"]
                ):
                    changing_tiles.remove(tile)
                else:
                    tile.click()

    def _convert_audio_to_text(self, audio_url: str) -> Optional[str]:
        """
        Convert the reCAPTCHA audio to text.

        Parameters
        ----------
        audio_url : str
            The reCAPTCHA audio URL.

        Returns
        -------
        Optional[str]
            The reCAPTCHA audio text. Returns None if the audio could not be converted.
        """
        response = self._page.request.get(audio_url)

        wav_audio = BytesIO()
        mp3_audio = BytesIO(response.body())
        audio: AudioSegment = AudioSegment.from_mp3(mp3_audio)
        audio.export(wav_audio, format="wav")

        recognizer = speech_recognition.Recognizer()

        with speech_recognition.AudioFile(wav_audio) as source:
            audio_data = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio_data)
        except speech_recognition.UnknownValueError:
            return None

    def _click_checkbox(self, recaptcha_box: SyncRecaptchaBox) -> None:
        """
        Click the reCAPTCHA checkbox.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        recaptcha_box.checkbox.click(force=True)

        while recaptcha_box.frames_are_attached() and self._token is None:
            if recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if recaptcha_box.challenge_is_visible():
                return

            self._page.wait_for_timeout(250)

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
        while True:
            if recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if recaptcha_box.audio_challenge_is_visible():
                return recaptcha_box.audio_download_button.get_attribute("href")

            self._page.wait_for_timeout(250)

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

        with self._page.expect_response(
            re.compile("/recaptcha/(api2|enterprise)/userverify")
        ):
            recaptcha_box.verify_button.click()

        while recaptcha_box.frames_are_attached():
            if recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if (
                not recaptcha_box.challenge_is_visible()
                or recaptcha_box.solve_failure_is_visible()
                or recaptcha_box.challenge_is_solved()
            ):
                return

            self._page.wait_for_timeout(250)

    def _submit_tile_answers(self, recaptcha_box: SyncRecaptchaBox) -> None:
        """
        Submit the reCAPTCHA image challenge tile answers.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        recaptcha_box.verify_button.click()

        while recaptcha_box.frames_are_attached():
            if recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if (
                recaptcha_box.challenge_is_solved()
                or recaptcha_box.try_again_is_visible()
            ):
                return

            if (
                recaptcha_box.check_new_images_is_visible()
                or recaptcha_box.select_all_matching_is_visible()
            ):
                with self._page.expect_response(
                    re.compile("/recaptcha/(api2|enterprise)/payload")
                ):
                    recaptcha_box.new_challenge_button.click()

                return

            self._page.wait_for_timeout(250)

    def _solve_image_challenge(self, recaptcha_box: SyncRecaptchaBox) -> None:
        """
        Solve the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        while recaptcha_box.frames_are_attached():
            self._random_delay()

            capsolver_response = self._get_capsolver_response(
                recaptcha_box, self._payload_response.body()
            )

            if (
                capsolver_response is None
                or not capsolver_response["solution"]["objects"]
            ):
                self._payload_response = None

                with self._page.expect_response(
                    re.compile("/recaptcha/(api2|enterprise)/payload")
                ):
                    recaptcha_box.new_challenge_button.click()

                continue

            self._solve_tiles(recaptcha_box, capsolver_response["solution"]["objects"])
            self._random_delay()

            self._payload_response = None
            button = recaptcha_box.skip_button.or_(recaptcha_box.next_button)

            if button.is_visible():
                with self._page.expect_response(
                    re.compile("/recaptcha/(api2|enterprise)/payload")
                ):
                    recaptcha_box.new_challenge_button.click()

                continue

            self._submit_tile_answers(recaptcha_box)
            return

    def _solve_audio_challenge(self, recaptcha_box: SyncRecaptchaBox) -> None:
        """
        Solve the reCAPTCHA audio challenge.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        self._random_delay(short=False)

        while True:
            url = self._get_audio_url(recaptcha_box)
            text = self._convert_audio_to_text(url)

            if text is not None:
                break

            with self._page.expect_response(
                re.compile("/recaptcha/(api2|enterprise)/payload")
            ):
                recaptcha_box.new_challenge_button.click()

        self._submit_audio_text(recaptcha_box, text)

    def close(self) -> None:
        """Remove the response listener."""
        try:
            self._page.remove_listener("response", self._response_callback)
        except KeyError:
            pass

    def recaptcha_is_visible(self) -> bool:
        """
        Check if a reCAPTCHA challenge or unchecked reCAPTCHA box is visible.

        Returns
        -------
        bool
            Whether a reCAPTCHA challenge or unchecked reCAPTCHA box is visible.
        """
        try:
            SyncRecaptchaBox.from_frames(self._page.frames)
        except RecaptchaNotFoundError:
            return False

        return True

    def solve_recaptcha(
        self,
        *,
        attempts: Optional[int] = None,
        wait: bool = False,
        wait_timeout: float = 30,
        image_challenge: bool = False,
    ) -> str:
        """
        Solve the reCAPTCHA and return the `g-recaptcha-response` token.

        Parameters
        ----------
        attempts : Optional[int], optional
            The number of solve attempts, by default 5.
        wait : bool, optional
            Whether to wait for the reCAPTCHA to appear, by default False.
        wait_timeout : float, optional
            The amount of time in seconds to wait for the reCAPTCHA to appear,
            by default 30. Only used if `wait` is True.
        image_challenge : bool, optional
            Whether to solve the image challenge, by default False.

        Returns
        -------
        str
            The `g-recaptcha-response` token.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        RecaptchaNotFoundError
            If the reCAPTCHA was not found.
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        RecaptchaSolveError
            If the reCAPTCHA could not be solved.
        """
        if image_challenge and self._capsolver_api_key is None:
            raise CapSolverError(
                "You must provide a CapSolver API key to solve image challenges."
            )

        self._token = None
        attempts = attempts or self._attempts

        if wait:
            retry = Retrying(
                sleep=self._page.wait_for_timeout,
                stop=stop_after_delay(wait_timeout),
                wait=wait_fixed(0.25),
                retry=retry_if_exception_type(RecaptchaNotFoundError),
                reraise=True,
            )

            recaptcha_box = retry(
                lambda: SyncRecaptchaBox.from_frames(self._page.frames)
            )
        else:
            recaptcha_box = SyncRecaptchaBox.from_frames(self._page.frames)

        if recaptcha_box.checkbox.is_visible():
            self._click_checkbox(recaptcha_box)

            if self._token is not None:
                return self._token
        elif recaptcha_box.rate_limit_is_visible():
            raise RecaptchaRateLimitError

        if image_challenge and recaptcha_box.image_challenge_button.is_visible():
            recaptcha_box.image_challenge_button.click(force=True)

        if not image_challenge and recaptcha_box.audio_challenge_button.is_visible():
            recaptcha_box.audio_challenge_button.click(force=True)

        if image_challenge and self._payload_response is None:
            image = recaptcha_box.image_challenge.locator("img").first
            image_url = image.get_attribute("src")
            self._payload_response = self._page.request.get(image_url)

        while attempts > 0:
            self._token = None

            if image_challenge:
                self._solve_image_challenge(recaptcha_box)
            else:
                self._solve_audio_challenge(recaptcha_box)

            if (
                recaptcha_box.frames_are_detached()
                or not recaptcha_box.challenge_is_visible()
                or recaptcha_box.challenge_is_solved()
            ):
                while self._token is None:
                    self._page.wait_for_timeout(250)

                return self._token

            if not image_challenge:
                recaptcha_box.new_challenge_button.click()

            attempts -= 1

        raise RecaptchaSolveError
