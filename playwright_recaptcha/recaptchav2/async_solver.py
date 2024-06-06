from __future__ import annotations

import asyncio
import base64
import functools
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from json import JSONDecodeError
from typing import Any, BinaryIO, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import speech_recognition
from playwright.async_api import Locator, Page, Response
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from ..errors import (
    CapSolverError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
)
from .base_solver import BaseSolver
from .recaptcha_box import AsyncRecaptchaBox
from .translations import OBJECT_TRANSLATIONS, ORIGINAL_LANGUAGE_AUDIO


class AsyncAudioFile(speech_recognition.AudioFile):
    """
    A subclass of `speech_recognition.AudioFile` that can be used asynchronously.

    Parameters
    ----------
    file : Union[BinaryIO, str]
        The audio file handle or file path.
    executor : Optional[ThreadPoolExecutor], optional
        The thread pool executor to use, by default None.
    """

    def __init__(
        self,
        file: Union[BinaryIO, str],
        *,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        super().__init__(file)
        self._loop = asyncio.get_event_loop()
        self._executor = executor

    async def __aenter__(self) -> AsyncAudioFile:
        await self._loop.run_in_executor(self._executor, self.__enter__)
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._loop.run_in_executor(self._executor, self.__exit__, *args)


class AsyncSolver(BaseSolver[Page]):
    """
    A class for solving reCAPTCHA v2 asynchronously with Playwright.

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

    async def __aenter__(self) -> AsyncSolver:
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()

    @staticmethod
    async def _get_task_object(recaptcha_box: AsyncRecaptchaBox) -> Optional[str]:
        """
        Get the ID of the object in the reCAPTCHA image challenge task.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
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

        task = await recaptcha_box.bframe_frame.locator("div").all_inner_texts()
        object_ = task[0].split("\n")[1]

        for object_id, translations in object_dict.items():
            if object_ in translations:
                return object_id

        return None

    async def _response_callback(self, response: Response) -> None:
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
            token_match = re.search('"uvresp","(.*?)"', await response.text())

            if token_match is not None:
                self._token = token_match.group(1)

    async def _get_capsolver_response(
        self, recaptcha_box: AsyncRecaptchaBox, image_data: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Get the CapSolver JSON response for an image.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
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
        task_object = await self._get_task_object(recaptcha_box)

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

        response = await self._page.request.post(
            "https://api.capsolver.com/createTask", data=payload
        )

        try:
            response_json = await response.json()
        except JSONDecodeError as err:
            raise CapSolverError from err

        if response_json["errorId"] != 0:
            raise CapSolverError(response_json["errorDescription"])

        return response_json

    async def _solve_tiles(
        self, recaptcha_box: AsyncRecaptchaBox, indexes: List[int]
    ) -> None:
        """
        Solve the tiles in the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
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
            await tile.click()

            if "rc-imageselect-dynamic-selected" not in await tile.get_attribute(
                "class"
            ):
                continue

            changing_tiles[tile] = await tile.locator("img").get_attribute("src")
            await tile.evaluate(style_script)

        start_time = datetime.now()

        while changing_tiles and (datetime.now() - start_time).seconds < 60:
            for tile in changing_tiles.copy():
                image_url = await tile.locator("img").get_attribute("src")

                if changing_tiles[tile] == image_url:
                    continue

                changing_tiles[tile] = image_url
                response = await self._page.request.get(image_url)

                capsolver_response = await self._get_capsolver_response(
                    recaptcha_box, await response.body()
                )

                if (
                    capsolver_response is None
                    or not capsolver_response["solution"]["hasObject"]
                ):
                    changing_tiles.pop(tile)
                    continue

                await tile.click()
                await tile.evaluate(style_script)

    async def _transcribe_audio(
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
        loop = asyncio.get_event_loop()
        response = await self._page.request.get(audio_url)

        wav_audio = BytesIO()
        mp3_audio = BytesIO(await response.body())

        try:
            audio: AudioSegment = await loop.run_in_executor(
                None, AudioSegment.from_mp3, mp3_audio
            )
        except CouldntDecodeError:
            return None

        await loop.run_in_executor(
            None, functools.partial(audio.export, wav_audio, format="wav")
        )

        recognizer = speech_recognition.Recognizer()

        async with AsyncAudioFile(wav_audio) as source:
            audio_data = await loop.run_in_executor(None, recognizer.record, source)

        try:
            return await loop.run_in_executor(
                None,
                functools.partial(
                    recognizer.recognize_google, audio_data, language=language
                ),
            )
        except speech_recognition.UnknownValueError:
            return None

    async def _click_checkbox(self, recaptcha_box: AsyncRecaptchaBox) -> None:
        """
        Click the reCAPTCHA checkbox.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        await recaptcha_box.checkbox.click()

        while recaptcha_box.frames_are_attached() and self._token is None:
            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if await recaptcha_box.any_challenge_is_visible():
                return

            await self._page.wait_for_timeout(250)

    async def _get_audio_url(self, recaptcha_box: AsyncRecaptchaBox) -> str:
        """
        Get the reCAPTCHA audio URL.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
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
            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if await recaptcha_box.audio_challenge_is_visible():
                return await recaptcha_box.audio_download_button.get_attribute("href")

            await self._page.wait_for_timeout(250)

    async def _submit_audio_text(
        self, recaptcha_box: AsyncRecaptchaBox, text: str
    ) -> None:
        """
        Submit the reCAPTCHA audio text.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.
        text : str
            The reCAPTCHA audio text.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        await recaptcha_box.audio_challenge_textbox.fill(text)

        async with self._page.expect_response(
            re.compile("/recaptcha/(api2|enterprise)/userverify")
        ) as response:
            await recaptcha_box.verify_button.click()

        await response.value

        while recaptcha_box.frames_are_attached():
            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if (
                not await recaptcha_box.audio_challenge_is_visible()
                or await recaptcha_box.solve_failure_is_visible()
                or await recaptcha_box.challenge_is_solved()
            ):
                return

            await self._page.wait_for_timeout(250)

    async def _submit_tile_answers(self, recaptcha_box: AsyncRecaptchaBox) -> None:
        """
        Submit the reCAPTCHA image challenge tile answers.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        await recaptcha_box.verify_button.click()

        while recaptcha_box.frames_are_attached():
            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if (
                await recaptcha_box.challenge_is_solved()
                or await recaptcha_box.try_again_is_visible()
            ):
                return

            if (
                await recaptcha_box.check_new_images_is_visible()
                or await recaptcha_box.select_all_matching_is_visible()
            ):
                async with self._page.expect_response(
                    re.compile("/recaptcha/(api2|enterprise)/payload")
                ) as response:
                    await recaptcha_box.new_challenge_button.click()

                await response.value
                return

            await self._page.wait_for_timeout(250)

    async def _solve_image_challenge(self, recaptcha_box: AsyncRecaptchaBox) -> None:
        """
        Solve the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        RecaptchaRateLimitError
            If the reCAPTCHA rate limit has been exceeded.
        """
        while recaptcha_box.frames_are_attached():
            capsolver_response = await self._get_capsolver_response(
                recaptcha_box, await self._payload_response.body()
            )

            if (
                capsolver_response is None
                or not capsolver_response["solution"]["objects"]
            ):
                self._payload_response = None

                async with self._page.expect_response(
                    re.compile("/recaptcha/(api2|enterprise)/reload")
                ) as response:
                    await recaptcha_box.new_challenge_button.click()

                await response.value

                while self._payload_response is None:
                    if await recaptcha_box.rate_limit_is_visible():
                        raise RecaptchaRateLimitError

                    await self._page.wait_for_timeout(250)

                continue

            await self._solve_tiles(
                recaptcha_box, capsolver_response["solution"]["objects"]
            )

            self._payload_response = None
            button = recaptcha_box.skip_button.or_(recaptcha_box.next_button)

            if await button.is_hidden():
                await self._submit_tile_answers(recaptcha_box)
                return

            async with self._page.expect_response(
                re.compile("/recaptcha/(api2|enterprise)/payload")
            ):
                await button.click()

    async def _solve_audio_challenge(self, recaptcha_box: AsyncRecaptchaBox) -> None:
        """
        Solve the reCAPTCHA audio challenge.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
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
            url = await self._get_audio_url(recaptcha_box)
            text = await self._transcribe_audio(url, language=language)

            if text is not None:
                break

            async with self._page.expect_response(
                re.compile("/recaptcha/(api2|enterprise)/reload")
            ) as response:
                await recaptcha_box.new_challenge_button.click()

            await response.value

            while url == await self._get_audio_url(recaptcha_box):
                await self._page.wait_for_timeout(250)

        await self._submit_audio_text(recaptcha_box, text)

    async def recaptcha_is_visible(self) -> bool:
        """
        Check if a reCAPTCHA challenge or unchecked reCAPTCHA box is visible.

        Returns
        -------
        bool
            Whether a reCAPTCHA challenge or unchecked reCAPTCHA box is visible.
        """
        try:
            await AsyncRecaptchaBox.from_frames(self._page.frames)
        except RecaptchaNotFoundError:
            return False

        return True

    async def solve_recaptcha(
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
            retry = AsyncRetrying(
                sleep=self._page.wait_for_timeout,
                stop=stop_after_delay(wait_timeout),
                wait=wait_fixed(0.25),
                retry=retry_if_exception_type(RecaptchaNotFoundError),
                reraise=True,
            )

            recaptcha_box = await retry(
                lambda: AsyncRecaptchaBox.from_frames(self._page.frames)
            )
        else:
            recaptcha_box = await AsyncRecaptchaBox.from_frames(self._page.frames)

        if await recaptcha_box.rate_limit_is_visible():
            raise RecaptchaRateLimitError

        if await recaptcha_box.checkbox.is_visible():
            await self._click_checkbox(recaptcha_box)

            if self._token is not None:
                return self._token

            if (
                recaptcha_box.frames_are_detached()
                or not await recaptcha_box.any_challenge_is_visible()
                or await recaptcha_box.challenge_is_solved()
            ):
                while self._token is None:
                    await self._page.wait_for_timeout(250)

                return self._token

        while not await recaptcha_box.any_challenge_is_visible():
            await self._page.wait_for_timeout(250)

        if image_challenge and await recaptcha_box.image_challenge_button.is_visible():
            await recaptcha_box.image_challenge_button.click()
        elif (
            not image_challenge
            and await recaptcha_box.audio_challenge_button.is_visible()
        ):
            await recaptcha_box.audio_challenge_button.click()

        if image_challenge:
            image = recaptcha_box.image_challenge.locator("img").first
            image_url = await image.get_attribute("src")
            self._payload_response = await self._page.request.get(image_url)

        while attempts > 0:
            self._token = None

            if image_challenge:
                await self._solve_image_challenge(recaptcha_box)
            else:
                await self._solve_audio_challenge(recaptcha_box)

            if (
                recaptcha_box.frames_are_detached()
                or not await recaptcha_box.any_challenge_is_visible()
                or await recaptcha_box.challenge_is_solved()
            ):
                while self._token is None:
                    await self._page.wait_for_timeout(250)

                return self._token

            attempts -= 1

        raise RecaptchaSolveError
