from __future__ import annotations

import base64
import re
from datetime import datetime
from io import BytesIO
from json import JSONDecodeError
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import speech_recognition
from playwright.sync_api import Locator, Page, Response
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

from ..errors import (
    CapSolverError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
)
from .base_solver import BaseSolver
from .recaptcha_box import SyncRecaptchaBox
from .translations import OBJECT_TRANSLATIONS, ORIGINAL_LANGUAGE_AUDIO


class SyncSolver(BaseSolver[Page]):
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
            "/m/0pg52": OBJECT_TRANSLATIONS["taxis"],
            "/m/01bjv": OBJECT_TRANSLATIONS["bus"],
            "/m/04_sv": OBJECT_TRANSLATIONS["motorcycles"],
            "/m/013xlm": OBJECT_TRANSLATIONS["tractors"],
            "/m/01jk_4": OBJECT_TRANSLATIONS["chimneys"],
            "/m/014xcs": OBJECT_TRANSLATIONS["crosswalks"],
            "/m/015qff": OBJECT_TRANSLATIONS["traffic_lights"],
            "/m/0199g": OBJECT_TRANSLATIONS["bicycles"],
            "/m/015qbp": OBJECT_TRANSLATIONS["parking_meters"],
            "/m/0k4j": OBJECT_TRANSLATIONS["cars"],
            "/m/015kr": OBJECT_TRANSLATIONS["bridges"],
            "/m/019jd": OBJECT_TRANSLATIONS["boats"],
            "/m/0cdl1": OBJECT_TRANSLATIONS["palm_trees"],
            "/m/09d_r": OBJECT_TRANSLATIONS["mountains_or_hills"],
            "/m/01pns0": OBJECT_TRANSLATIONS["fire_hydrant"],
            "/m/01lynh": OBJECT_TRANSLATIONS["stairs"],
        }

        task = recaptcha_box.bframe_frame.locator("div").all_inner_texts()
        object_ = task[0].split("\n")[1]

        for object_id, translations in object_dict.items():
            if object_ in translations:
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

    def _solve_tiles(self, recaptcha_box: SyncRecaptchaBox, indexes: List[int]) -> None:
        """
        Solve the tiles in the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : SyncRecaptchaBox
            The reCAPTCHA box.
        indexes : List[int]
            The indexes of the tiles that contain the task object.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        """
        changing_tiles: Dict[Locator, str] = {}
        indexes = indexes.copy()

        style_script = """
        (element) => {
            element.style = "";
            element.className = "rc-imageselect-tile";
        }
        """

        for index in indexes:
            tile = recaptcha_box.tile_selector.nth(index)
            tile.click()

            if "rc-imageselect-dynamic-selected" not in tile.get_attribute("class"):
                continue

            changing_tiles[tile] = tile.locator("img").get_attribute("src")
            tile.evaluate(style_script)

        start_time = datetime.now()

        while changing_tiles and (datetime.now() - start_time).seconds < 60:
            for tile in changing_tiles.copy():
                image_url = tile.locator("img").get_attribute("src")

                if changing_tiles[tile] == image_url:
                    continue

                changing_tiles[tile] = image_url
                response = self._page.request.get(image_url)

                capsolver_response = self._get_capsolver_response(
                    recaptcha_box, response.body()
                )

                if (
                    capsolver_response is None
                    or not capsolver_response["solution"]["hasObject"]
                ):
                    changing_tiles.pop(tile)
                    continue

                tile.click()
                tile.evaluate(style_script)

    def _transcribe_audio(
        self, audio_url: str, *, language: str = "en-US"
    ) -> Optional[str]:
        """
        Transcribe the reCAPTCHA audio challenge.

        Parameters
        ----------
        audio_url : str
            The reCAPTCHA audio URL.
        language : str, optional
            The language of the audio, by default en-US.

        Returns
        -------
        Optional[str]
            The reCAPTCHA audio text.
            Returns None if the audio could not be converted.
        """
        response = self._page.request.get(audio_url)

        wav_audio = BytesIO()
        mp3_audio = BytesIO(response.body())

        try:
            audio: AudioSegment = AudioSegment.from_mp3(mp3_audio)
        except CouldntDecodeError:
            return None

        audio.export(wav_audio, format="wav")
        recognizer = speech_recognition.Recognizer()

        with speech_recognition.AudioFile(wav_audio) as source:
            audio_data = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio_data, language=language)
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
        recaptcha_box.checkbox.click()

        while recaptcha_box.frames_are_attached() and self._token is None:
            if recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if recaptcha_box.any_challenge_is_visible():
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
                not recaptcha_box.audio_challenge_is_visible()
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
            capsolver_response = self._get_capsolver_response(
                recaptcha_box, self._payload_response.body()
            )

            if (
                capsolver_response is None
                or not capsolver_response["solution"]["objects"]
            ):
                self._payload_response = None

                with self._page.expect_response(
                    re.compile("/recaptcha/(api2|enterprise)/reload")
                ):
                    recaptcha_box.new_challenge_button.click()

                while self._payload_response is None:
                    if recaptcha_box.rate_limit_is_visible():
                        raise RecaptchaRateLimitError

                    self._page.wait_for_timeout(250)

                continue

            self._solve_tiles(recaptcha_box, capsolver_response["solution"]["objects"])
            self._payload_response = None

            button = recaptcha_box.skip_button.or_(recaptcha_box.next_button)

            if button.is_hidden():
                self._submit_tile_answers(recaptcha_box)
                return

            with self._page.expect_response(
                re.compile("/recaptcha/(api2|enterprise)/payload")
            ):
                button.click()

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
        parsed_url = urlparse(recaptcha_box.anchor_frame.url)
        query_params = parse_qs(parsed_url.query)
        language = query_params["hl"][0]

        if language not in ORIGINAL_LANGUAGE_AUDIO:
            language = "en-US"

        while True:
            url = self._get_audio_url(recaptcha_box)
            text = self._transcribe_audio(url, language=language)

            if text is not None:
                break

            with self._page.expect_response(
                re.compile("/recaptcha/(api2|enterprise)/reload")
            ):
                recaptcha_box.new_challenge_button.click()

            while url == self._get_audio_url(recaptcha_box):
                self._page.wait_for_timeout(250)

        self._submit_audio_text(recaptcha_box, text)

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

        if recaptcha_box.rate_limit_is_visible():
            raise RecaptchaRateLimitError

        if recaptcha_box.checkbox.is_visible():
            self._click_checkbox(recaptcha_box)

            if self._token is not None:
                return self._token

            if (
                recaptcha_box.frames_are_detached()
                or not recaptcha_box.any_challenge_is_visible()
                or recaptcha_box.challenge_is_solved()
            ):
                while self._token is None:
                    self._page.wait_for_timeout(250)

                return self._token

        while not recaptcha_box.any_challenge_is_visible():
            self._page.wait_for_timeout(250)

        if image_challenge and recaptcha_box.image_challenge_button.is_visible():
            recaptcha_box.image_challenge_button.click()
        elif not image_challenge and recaptcha_box.audio_challenge_button.is_visible():
            recaptcha_box.audio_challenge_button.click()

        if image_challenge:
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
                or not recaptcha_box.any_challenge_is_visible()
                or recaptcha_box.challenge_is_solved()
            ):
                while self._token is None:
                    self._page.wait_for_timeout(250)

                return self._token

            attempts -= 1

        raise RecaptchaSolveError
