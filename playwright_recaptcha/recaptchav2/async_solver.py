from __future__ import annotations

import asyncio
import base64
import functools
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from json import JSONDecodeError
from typing import Any, BinaryIO, Dict, Iterable, Optional, Union

import speech_recognition
from playwright.async_api import APIResponse, Page, Response
from pydub import AudioSegment
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
from .recaptcha_box import AsyncRecaptchaBox


class AsyncAudioFile(speech_recognition.AudioFile):
    """
    A subclass of `speech_recognition.AudioFile` that can be used asynchronously.

    Parameters
    ----------
    file : BinaryIO
        The audio file.
    executor : Optional[ThreadPoolExecutor], optional
        The thread pool executor to use, by default None.
    """

    def __init__(
        self, file: BinaryIO, *, executor: Optional[ThreadPoolExecutor] = None
    ) -> None:
        super().__init__(file)
        self._executor = executor

    async def __aenter__(self) -> AsyncAudioFile:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, super().__enter__)
        return self

    async def __aexit__(self, *args: Any) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, super().__exit__, *args)


class AsyncSolver:
    """
    A class used to solve reCAPTCHA v2 asynchronously.

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
            f"AsyncSolver(page={self._page!r}, "
            f"attempts={self._attempts!r}, "
            f"capsolver_api_key={self._capsolver_api_key!r})"
        )

    async def __aenter__(self) -> AsyncSolver:
        return self

    async def __aexit__(self, *args: Any) -> None:
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

        task = await recaptcha_box.bframe_frame.locator("div").all_inner_texts()

        for object_name, object_id in object_dict.items():
            if object_name in task[0]:
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

    async def _random_delay(self, short: bool = True) -> None:
        """
        Delay the browser for a random amount of time.

        Parameters
        ----------
        short : bool, optional
            Whether to delay for a short amount of time, by default True.
        """
        delay_time = random.randint(150, 350) if short else random.randint(1250, 1500)
        await self._page.wait_for_timeout(delay_time)

    async def _wait_for_value(self, attribute: str) -> None:
        """
        Wait for an attribute to have a value.

        Parameters
        ----------
        attribute : str
            The attribute.
        """
        while getattr(self, attribute) is None:
            await self._page.wait_for_timeout(250)

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
        self, recaptcha_box: AsyncRecaptchaBox, indexes: Iterable[int]
    ) -> None:
        """
        Solve the tiles in the reCAPTCHA image challenge.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.
        indexes : Iterable[int]
            The indexes of the tiles that contain the task object.

        Raises
        ------
        CapSolverError
            If the CapSolver API returned an error.
        """
        changing_tiles = []

        for index in indexes:
            tile = recaptcha_box.tile_selector.nth(index)
            await tile.click()

            if "rc-imageselect-dynamic-selected" in await tile.get_attribute("class"):
                changing_tiles.append(tile)

            await self._random_delay()

        while changing_tiles:
            for tile in changing_tiles.copy():
                if "rc-imageselect-dynamic-selected" in await tile.get_attribute(
                    "class"
                ):
                    continue

                image_url = await tile.locator("img").get_attribute("src")
                response = await self._page.request.get(image_url)

                capsolver_response = await self._get_capsolver_response(
                    recaptcha_box, await response.body()
                )

                if (
                    capsolver_response is None
                    or not capsolver_response["solution"]["hasObject"]
                ):
                    changing_tiles.remove(tile)
                else:
                    await tile.click()

    async def _convert_audio_to_text(self, audio_url: str) -> Optional[str]:
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
        loop = asyncio.get_event_loop()
        response = await self._page.request.get(audio_url)

        wav_audio = BytesIO()
        mp3_audio = BytesIO(await response.body())

        with ThreadPoolExecutor() as executor:
            audio = await loop.run_in_executor(
                executor, AudioSegment.from_mp3, mp3_audio
            )

            await loop.run_in_executor(
                executor, functools.partial(audio.export, wav_audio, format="wav")
            )

            recognizer = speech_recognition.Recognizer()

            async with AsyncAudioFile(wav_audio, executor=executor) as source:
                audio_data = await loop.run_in_executor(
                    executor, recognizer.record, source
                )

            try:
                return await loop.run_in_executor(
                    executor, recognizer.recognize_google, audio_data
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
        RecaptchaSolveError
            If the reCAPTCHA could not be solved.
        """
        await recaptcha_box.checkbox.click(force=True)

        while recaptcha_box.frames_are_attached():
            if await recaptcha_box.challenge_is_solved():
                if self._token is None:
                    raise RecaptchaSolveError

                break

            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if await recaptcha_box.challenge_is_visible():
                break

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
                break

            await self._page.wait_for_timeout(250)

        return await recaptcha_box.audio_download_button.get_attribute("href")

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
        ):
            await recaptcha_box.verify_button.click()

        while recaptcha_box.frames_are_attached():
            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if (
                not await recaptcha_box.challenge_is_visible()
                or await recaptcha_box.solve_failure_is_visible()
                or await recaptcha_box.challenge_is_solved()
            ):
                break

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
            await self._wait_for_value("_payload_response")
            await self._random_delay()

            capsolver_response = await self._get_capsolver_response(
                recaptcha_box, await self._payload_response.body()
            )

            if (
                capsolver_response is None
                or not capsolver_response["solution"]["objects"]
            ):
                self._payload_response = None
                await recaptcha_box.new_challenge_button.click()
                continue

            await self._solve_tiles(
                recaptcha_box, capsolver_response["solution"]["objects"]
            )

            await self._random_delay()

            self._payload_response = None
            button = recaptcha_box.skip_button.or_(recaptcha_box.next_button)

            if await button.is_visible():
                await button.click()
                continue

            async with self._page.expect_response(
                re.compile("/recaptcha/(api2|enterprise)/(payload|userverify)")
            ):
                await recaptcha_box.verify_button.click()

                if (
                    await recaptcha_box.check_new_images_is_visible()
                    or await recaptcha_box.select_all_matching_is_visible()
                ):
                    await recaptcha_box.new_challenge_button.click()
                else:
                    await self._wait_for_value("_token")

            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            return

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
        await self._random_delay(short=False)

        while True:
            url = await self._get_audio_url(recaptcha_box)
            text = await self._convert_audio_to_text(url)

            if text is not None:
                break

            async with self._page.expect_response(
                re.compile("/recaptcha/(api2|enterprise)/payload")
            ):
                await recaptcha_box.new_challenge_button.click()

        await self._submit_audio_text(recaptcha_box, text)

    async def _get_recaptcha_box(self) -> AsyncRecaptchaBox:
        """
        Get the reCAPTCHA box.

        Returns
        -------
        AsyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaNotFoundError
            If the reCAPTCHA was not found.
        """
        recaptcha_box = await AsyncRecaptchaBox.from_frames(self._page.frames)

        if (
            await recaptcha_box.checkbox.is_hidden()
            and await recaptcha_box.audio_challenge_button.is_disabled()
        ):
            raise RecaptchaNotFoundError

        return recaptcha_box

    def close(self) -> None:
        """Remove the response listener."""
        try:
            self._page.remove_listener("response", self._response_callback)
        except KeyError:
            pass

    async def recaptcha_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA is visible.

        Returns
        -------
        bool
            Whether the reCAPTCHA is visible.
        """
        try:
            await self._get_recaptcha_box()
        except RecaptchaNotFoundError:
            return False

        return True

    async def solve_recaptcha(
        self,
        *,
        attempts: Optional[int] = None,
        wait: bool = False,
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
            RecaptchaNotFoundError will be raised if the reCAPTCHA has not appeared
            after 30 seconds.
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
        if self._capsolver_api_key is None and image_challenge:
            raise CapSolverError(
                "You must provide a CapSolver API key to solve image challenges."
            )

        self._token = None
        attempts = attempts or self._attempts

        if wait:
            retry = AsyncRetrying(
                sleep=self._page.wait_for_timeout,
                stop=stop_after_delay(30),
                wait=wait_fixed(0.25),
                retry=retry_if_exception_type(RecaptchaNotFoundError),
                reraise=True,
            )

            recaptcha_box = await retry(self._get_recaptcha_box)
        else:
            recaptcha_box = await self._get_recaptcha_box()

        if await recaptcha_box.checkbox.is_visible():
            await self._click_checkbox(recaptcha_box)

            if self._token is not None:
                return self._token
        elif await recaptcha_box.rate_limit_is_visible():
            raise RecaptchaRateLimitError

        if image_challenge and await recaptcha_box.image_challenge_button.is_visible():
            await recaptcha_box.image_challenge_button.click(force=True)

        if (
            not image_challenge
            and await recaptcha_box.audio_challenge_button.is_visible()
        ):
            await recaptcha_box.audio_challenge_button.click(force=True)

        if image_challenge and self._payload_response is None:
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
                or not await recaptcha_box.challenge_is_visible()
                or await recaptcha_box.challenge_is_solved()
            ):
                if self._token is None:
                    raise RecaptchaSolveError

                return self._token

            if not image_challenge:
                await recaptcha_box.new_challenge_button.click()

            attempts -= 1

        raise RecaptchaSolveError
