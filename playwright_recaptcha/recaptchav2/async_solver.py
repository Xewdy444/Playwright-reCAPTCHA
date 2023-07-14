from __future__ import annotations

import asyncio
import base64
import functools
import io
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from typing import Any, Dict, Iterable, Optional

import pydub
import speech_recognition
from playwright.async_api import Page, Response

from playwright_recaptcha.errors import (
    CapSolverError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
)
from playwright_recaptcha.recaptchav2.recaptcha_box import AsyncRecaptchaBox


class AsyncSolver:
    """
    A class used to solve reCAPTCHA v2 asynchronously.

    Parameters
    ----------
    page : Page
        The playwright page to solve the reCAPTCHA on.
    attempts : int, optional
        The number of solve attempts, by default 3.
    capsolver_api_key : Optional[str], optional
        The CapSolver API key, by default None.
        If None, the CAPSOLVER_API_KEY environment variable will be used.
    """

    def __init__(
        self, page: Page, *, attempts: int = 3, capsolver_api_key: Optional[str] = None
    ) -> None:
        self._page = page
        self._attempts = attempts
        self._capsolver_api_key = capsolver_api_key or os.getenv("CAPSOLVER_API_KEY")

        self._token: Optional[str] = None
        self._payload_response: Optional[Response] = None

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
        Get the reCAPTCHA task object ID.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.

        Returns
        -------
        Optional[str]
            The reCAPTCHA object ID.
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

    async def _get_capsolver_response(
        self, recaptcha_box: AsyncRecaptchaBox, image_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the CapSolver response for the image.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.
        image_url : str
            The tile image URL.

        Returns
        -------
        Optional[Dict[str, Any]]
            The CapSolver response.

        Raises
        ------
        CapSolverError
            If CapSolver returned an error.
        """
        response = await self._page.request.get(image_url)
        image = base64.b64encode(await response.body()).decode("utf-8")
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

    async def _solve_changing_tiles(
        self, recaptcha_box: AsyncRecaptchaBox, indexes: Iterable[int]
    ) -> None:
        """
        Solve the changing tiles.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.
        indexes : Iterable[int]
            The indexes of the tiles that contain the object.

        Raises
        ------
        CapSolverError
            If CapSolver returned an error.
        """
        for index in indexes:
            await recaptcha_box.tile_selector.nth(index).click()
            await self._random_delay(short=True)

        changing_tiles = []

        for tile in await recaptcha_box.tile_selector.all():
            if "rc-imageselect-dynamic-selected" in await tile.get_attribute("class"):
                changing_tiles.append(tile)

        while changing_tiles:
            for tile in changing_tiles:
                while "rc-imageselect-dynamic-selected" in await tile.get_attribute(
                    "class"
                ):
                    await self._page.wait_for_timeout(250)

                capsolver_response = await self._get_capsolver_response(
                    recaptcha_box, await tile.locator("img").get_attribute("src")
                )

                if (
                    capsolver_response is None
                    or not capsolver_response["solution"]["hasObject"]
                ):
                    changing_tiles.remove(tile)
                    continue

                await self._random_delay(short=True)
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
            The reCAPTCHA audio text.
        """
        loop = asyncio.get_event_loop()
        response = await self._page.request.get(audio_url)

        wav_audio = io.BytesIO()
        mp3_audio = io.BytesIO(await response.body())

        with ThreadPoolExecutor() as executor:
            audio = await loop.run_in_executor(
                executor, pydub.AudioSegment.from_mp3, mp3_audio
            )

            await loop.run_in_executor(
                executor, functools.partial(audio.export, wav_audio, format="wav")
            )

            recognizer = speech_recognition.Recognizer()

            with speech_recognition.AudioFile(wav_audio) as source:
                audio_data = await loop.run_in_executor(
                    executor, recognizer.record, source
                )

            try:
                return await loop.run_in_executor(
                    executor, recognizer.recognize_google, audio_data
                )
            except speech_recognition.UnknownValueError:
                return None

    async def _random_delay(self, short: bool = False) -> None:
        """
        Delay the execution for a random amount of time.

        Parameters
        ----------
        short : bool, optional
            Whether to delay for a short amount of time, by default False.
        """
        delay_time = random.randint(200, 450) if short else random.randint(1250, 1500)
        await self._page.wait_for_timeout(delay_time)

    async def _response_listener(self, response: Response) -> None:
        """
        Listen for payload and userverify responses.

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

    async def _click_checkbox(self, recaptcha_box: AsyncRecaptchaBox) -> None:
        """
        Click the reCAPTCHA checkbox.

        Parameters
        ----------
        recaptcha_box : AsyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaSolveError
            If the reCAPTCHA could not be solved.
        """
        await recaptcha_box.checkbox.click(force=True)

        while recaptcha_box.frames_are_attached():
            if await recaptcha_box.is_solved():
                if self.token is None:
                    raise RecaptchaSolveError

                break

            if (
                await recaptcha_box.audio_challenge_is_visible()
                or await recaptcha_box.audio_challenge_button.is_visible()
                and await recaptcha_box.audio_challenge_button.is_enabled()
            ):
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
        if await recaptcha_box.audio_challenge_button.is_visible():
            await recaptcha_box.audio_challenge_button.click(force=True)

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
            await recaptcha_box.audio_challenge_verify_button.click()

        while recaptcha_box.frames_are_attached():
            if await recaptcha_box.rate_limit_is_visible():
                raise RecaptchaRateLimitError

            if (
                await recaptcha_box.new_challenge_button.is_disabled()
                or await recaptcha_box.solve_failure_is_visible()
                or await recaptcha_box.is_solved()
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
            If CapSolver returned an error.
        """
        while recaptcha_box.frames_are_attached():
            while self._payload_response is None:
                await self._page.wait_for_timeout(250)

            await self._random_delay(short=True)

            capsolver_response = await self._get_capsolver_response(
                recaptcha_box, self._payload_response.url
            )

            if (
                capsolver_response is None
                or not capsolver_response["solution"]["objects"]
            ):
                await recaptcha_box.new_challenge_button.click()
                self._payload_response = None
                continue

            await self._solve_changing_tiles(
                recaptcha_box, capsolver_response["solution"]["objects"]
            )

            self._payload_response = None
            await self._random_delay(short=True)

            if await recaptcha_box.next_button.is_visible():
                await recaptcha_box.next_button.click()
                continue

            if await recaptcha_box.skip_button.is_visible():
                await recaptcha_box.skip_button.click()
                return

            await recaptcha_box.verify_button.click()

            while recaptcha_box.frames_are_attached():
                if (
                    await recaptcha_box.try_again_is_visible()
                    or await recaptcha_box.is_solved()
                ):
                    return

                if await recaptcha_box.check_new_images_is_visible():
                    await recaptcha_box.new_challenge_button.click()
                    self._payload_response = None
                    return

                await self._page.wait_for_timeout(250)

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
        await self._random_delay()
        url = await self._get_audio_url(recaptcha_box)
        text = await self._convert_audio_to_text(url)

        if text is None:
            return

        await self._random_delay()
        await self._submit_audio_text(recaptcha_box, text)

    @property
    def token(self) -> Optional[str]:
        """The g-recaptcha-response token."""
        return self._token

    def close(self) -> None:
        """Remove the response listener."""
        try:
            self._page.remove_listener("response", self._response_listener)
        except KeyError:
            pass

    async def solve_recaptcha(
        self, *, attempts: Optional[int] = None, image_challenge: bool = False
    ) -> str:
        """
        Solve the reCAPTCHA and return the g-recaptcha-response token.

        Parameters
        ----------
        attempts : Optional[int], optional
            The number of solve attempts, by default 3.
        image_challenge : bool, optional
            Whether to solve the image challenge, by default False.

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
        CapSolverError
            If CapSolver returned an error.
        """
        if self._capsolver_api_key is None and image_challenge:
            raise CapSolverError(
                "You must provide a CapSolver API key to solve image challenges."
            )

        self._token = None
        self._page.on("response", self._response_listener)

        attempts = attempts or self._attempts
        recaptcha_box = await AsyncRecaptchaBox.from_frames(self._page.frames)

        if (
            await recaptcha_box.checkbox.is_hidden()
            and await recaptcha_box.audio_challenge_button.is_disabled()
        ):
            raise RecaptchaNotFoundError

        if await recaptcha_box.checkbox.is_visible():
            await self._click_checkbox(recaptcha_box)

            if self._token is not None:
                return self._token

        while attempts > 0:
            if image_challenge:
                await self._solve_image_challenge(recaptcha_box)
            else:
                await self._solve_audio_challenge(recaptcha_box)

            if (
                recaptcha_box.frames_are_detached()
                or await recaptcha_box.new_challenge_button.is_disabled()
                or await recaptcha_box.is_solved()
            ):
                if self._token is None:
                    raise RecaptchaSolveError

                return self._token

            if not image_challenge:
                await recaptcha_box.new_challenge_button.click()

            attempts -= 1

        raise RecaptchaSolveError
