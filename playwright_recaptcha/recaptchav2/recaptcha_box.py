from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from functools import wraps
from typing import Awaitable, Callable, Iterable, List, Tuple, Union, overload

from playwright.async_api import Frame as AsyncFrame
from playwright.async_api import Locator as AsyncLocator
from playwright.sync_api import Frame as SyncFrame
from playwright.sync_api import Locator as SyncLocator

from ..errors import RecaptchaNotFoundError

Locator = Union[AsyncLocator, SyncLocator]
Frame = Union[AsyncFrame, SyncFrame]


class RecaptchaBox(ABC):
    """The base class for reCAPTCHA v2 boxes."""

    @staticmethod
    def _get_recaptcha_frame_pairs(
        frames: Iterable[Frame],
    ) -> List[Tuple[Frame, Frame]]:
        """
        Get the reCAPTCHA anchor and bframe frame pairs.

        Parameters
        ----------
        frames : Iterable[Frame]
            A list of frames to search for the reCAPTCHA anchor and bframe frames.

        Returns
        -------
        List[Tuple[Frame, Frame]]
            A list of reCAPTCHA anchor and bframe frame pairs.

        Raises
        ------
        RecaptchaNotFoundError
            If no reCAPTCHA anchor and bframe frame pairs were found.
        """
        anchor_frames = [
            frame
            for frame in frames
            if re.search("/recaptcha/(api2|enterprise)/anchor", frame.url) is not None
        ]

        bframe_frames = [
            frame
            for frame in frames
            if re.search("/recaptcha/(api2|enterprise)/bframe", frame.url) is not None
        ]

        frame_pairs = []

        for anchor_frame in anchor_frames:
            frame_id = anchor_frame.name[2:]

            for bframe_frame in bframe_frames:
                if frame_id in bframe_frame.name:
                    frame_pairs.append((anchor_frame, bframe_frame))

        if not frame_pairs:
            raise RecaptchaNotFoundError

        return frame_pairs

    @overload
    @staticmethod
    def _check_if_attached(
        func: Callable[[AsyncRecaptchaBox], Awaitable[bool]]
    ) -> Callable[[AsyncRecaptchaBox], Awaitable[bool]]:
        ...

    @overload
    @staticmethod
    def _check_if_attached(
        func: Callable[[SyncRecaptchaBox], bool]
    ) -> Callable[[SyncRecaptchaBox], bool]:
        ...

    @staticmethod
    def _check_if_attached(
        func: Union[
            Callable[[AsyncRecaptchaBox], Awaitable[bool]],
            Callable[[SyncRecaptchaBox], bool],
        ]
    ) -> Union[
        Callable[[AsyncRecaptchaBox], Awaitable[bool]],
        Callable[[SyncRecaptchaBox], bool],
    ]:
        """
        Check if the reCAPTCHA frames are attached
        before running the decorated function, otherwise return False.

        Parameters
        ----------
        func : Union[
            Callable[[AsyncRecaptchaBox], Awaitable[bool]],
            Callable[[SyncRecaptchaBox], bool],
        ]
            The function to decorate.

        Returns
        -------
        Union[
            Callable[[AsyncRecaptchaBox], Awaitable[bool]],
            Callable[[SyncRecaptchaBox], bool],
        ]
            The decorated function.
        """

        @wraps(func)
        def sync_wrapper(recaptcha_box: SyncRecaptchaBox) -> bool:
            if recaptcha_box.frames_are_detached():
                return False

            return func(recaptcha_box)

        @wraps(func)
        async def async_wrapper(recaptcha_box: AsyncRecaptchaBox) -> bool:
            if recaptcha_box.frames_are_detached():
                return False

            return await func(recaptcha_box)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper

        return sync_wrapper

    @property
    def checkbox(self) -> Locator:
        """The reCAPTCHA checkbox locator."""
        return self.anchor_frame.get_by_role("checkbox", name="I'm not a robot")

    @property
    def audio_challenge_button(self) -> Locator:
        """The reCAPTCHA audio challenge button locator."""
        return self.bframe_frame.get_by_role("button", name="Get an audio challenge")

    @property
    def image_challenge_button(self) -> Locator:
        """The reCAPTCHA image challenge button locator."""
        return self.bframe_frame.get_by_role("button", name="Get a visual challenge")

    @property
    def new_challenge_button(self) -> Locator:
        """The reCAPTCHA new challenge button locator."""
        return self.bframe_frame.get_by_role("button", name="Get a new challenge")

    @property
    def audio_download_button(self) -> Locator:
        """The reCAPTCHA audio download button locator."""
        return self.bframe_frame.get_by_role(
            "link", name="Alternatively, download audio as MP3"
        )

    @property
    def audio_challenge_textbox(self) -> Locator:
        """The reCAPTCHA audio challenge textbox locator."""
        return self.bframe_frame.get_by_role("textbox", name="Enter what you hear")

    @property
    def skip_button(self) -> Locator:
        """The reCAPTCHA skip button locator."""
        return self.bframe_frame.get_by_role("button", name="Skip")

    @property
    def next_button(self) -> Locator:
        """The reCAPTCHA next button locator."""
        return self.bframe_frame.get_by_role("button", name="Next")

    @property
    def verify_button(self) -> Locator:
        """The reCAPTCHA verify button locator."""
        return self.bframe_frame.get_by_role("button", name="Verify")

    @property
    def tile_selector(self) -> Locator:
        """The reCAPTCHA tile selector locator."""
        return self.bframe_frame.locator(".rc-imageselect-tile")

    @property
    def image_challenge(self) -> Locator:
        """The reCAPTCHA image challenge locator."""
        return self.bframe_frame.locator(".rc-imageselect-challenge")

    def frames_are_attached(self) -> bool:
        """
        Check if all of the reCAPTCHA frames are attached.

        Returns
        -------
        bool
            True if all of the reCAPTCHA frames are attached, False otherwise.
        """
        return not self.frames_are_detached()

    def frames_are_detached(self) -> bool:
        """
        Check if any of the reCAPTCHA frames are detached.

        Returns
        -------
        bool
            True if any of the reCAPTCHA frames are detached, False otherwise.
        """
        return self.anchor_frame.is_detached() or self.bframe_frame.is_detached()

    @property
    @abstractmethod
    def anchor_frame(self) -> Frame:
        """The reCAPTCHA anchor frame."""

    @property
    @abstractmethod
    def bframe_frame(self) -> Frame:
        """The reCAPTCHA bframe frame."""

    @classmethod
    @abstractmethod
    def from_frames(
        cls,
        frames: Iterable[Frame],
    ) -> Union[AsyncRecaptchaBox, SyncRecaptchaBox]:
        """
        Create a reCAPTCHA box using a list of frames.

        Parameters
        ----------
        frames : Iterable[Frame]
            A list of frames to search for the reCAPTCHA frames.

        Returns
        -------
        Union[AsyncRecaptchaBox, SyncRecaptchaBox]
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaNotFoundError
            If the reCAPTCHA frames were not found
            or if no unchecked reCAPTCHA boxes were found.
        """

    @abstractmethod
    def rate_limit_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA rate limit message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA rate limit message is visible, False otherwise.
        """

    @abstractmethod
    def solve_failure_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA solve failure message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA solve failure message is visible, False otherwise.
        """

    @abstractmethod
    def audio_challenge_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA audio challenge is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA audio challenge is visible, False otherwise.
        """

    @abstractmethod
    def try_again_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA try again message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA try again message is visible, False otherwise.
        """

    @abstractmethod
    def check_new_images_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA check new images message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA check new images message is visible, False otherwise.
        """

    @abstractmethod
    def select_all_matching_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA select all matching images message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA select all matching images message is visible,
            False otherwise.
        """

    @abstractmethod
    def challenge_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA challenge is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge is visible, False otherwise.
        """

    @abstractmethod
    def challenge_is_solved(self) -> bool:
        """
        Check if the reCAPTCHA challenge has been solved.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge has been solved, False otherwise.
        """


class SyncRecaptchaBox(RecaptchaBox):
    """
    The synchronous class for reCAPTCHA v2 boxes.

    Parameters
    ----------
    anchor_frame : SyncFrame
        The reCAPTCHA anchor frame.
    bframe_frame : SyncFrame
        The reCAPTCHA bframe frame.
    """

    def __init__(self, anchor_frame: SyncFrame, bframe_frame: SyncFrame) -> None:
        self._anchor_frame = anchor_frame
        self._bframe_frame = bframe_frame

    def __repr__(self) -> str:
        return f"SyncRecaptchaBox(anchor_frame={self._anchor_frame!r}, bframe_frame={self._bframe_frame!r})"

    @classmethod
    def from_frames(cls, frames: Iterable[SyncFrame]) -> SyncRecaptchaBox:
        """
        Create a reCAPTCHA box using a list of frames.

        Parameters
        ----------
        frames : Iterable[SyncFrame]
            A list of frames to search for the reCAPTCHA frames.

        Returns
        -------
        SyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaNotFoundError
            If the reCAPTCHA frames were not found
            or if no unchecked reCAPTCHA boxes were found.
        """
        frame_pairs = cls._get_recaptcha_frame_pairs(frames)

        for anchor_frame, bframe_frame in frame_pairs:
            recaptcha_box = cls(anchor_frame, bframe_frame)

            if (
                recaptcha_box.checkbox.is_visible()
                and not recaptcha_box.checkbox.is_checked()
                or recaptcha_box.audio_challenge_button.is_visible()
                or recaptcha_box.image_challenge_button.is_visible()
            ):
                return recaptcha_box

        raise RecaptchaNotFoundError("No unchecked reCAPTCHA boxes were found.")

    @property
    def anchor_frame(self) -> SyncFrame:
        """The reCAPTCHA anchor frame."""
        return self._anchor_frame

    @property
    def bframe_frame(self) -> SyncFrame:
        """The reCAPTCHA bframe frame."""
        return self._bframe_frame

    @RecaptchaBox._check_if_attached
    def rate_limit_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA rate limit message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA rate limit message is visible, False otherwise.
        """
        return self.bframe_frame.get_by_text("Try again later").is_visible()

    @RecaptchaBox._check_if_attached
    def solve_failure_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA solve failure message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA solve failure message is visible, False otherwise.
        """
        return self.bframe_frame.get_by_text(
            "Multiple correct solutions required - please solve more."
        ).is_visible()

    @RecaptchaBox._check_if_attached
    def audio_challenge_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA audio challenge is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA audio challenge is visible, False otherwise.
        """
        return self.bframe_frame.get_by_text("Press PLAY to listen").is_visible()

    @RecaptchaBox._check_if_attached
    def try_again_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA try again message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA try again message is visible, False otherwise.
        """
        return self.bframe_frame.get_by_text(
            re.compile("Please try again")
        ).is_visible()

    @RecaptchaBox._check_if_attached
    def check_new_images_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA check new images message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA check new images message is visible, False otherwise.
        """
        return self.bframe_frame.get_by_text(
            re.compile("Please also check the new images")
        ).is_visible()

    @RecaptchaBox._check_if_attached
    def select_all_matching_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA select all matching images message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA select all matching images message is visible,
            False otherwise.
        """
        return self.bframe_frame.get_by_text(
            re.compile("Please select all matching images")
        ).is_visible()

    @RecaptchaBox._check_if_attached
    def challenge_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA challenge is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge is visible, False otherwise.
        """
        button = self.skip_button.or_(self.next_button).or_(self.verify_button)
        return button.is_enabled()

    @RecaptchaBox._check_if_attached
    def challenge_is_solved(self) -> bool:
        """
        Check if the reCAPTCHA challenge has been solved.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge has been solved, False otherwise.
        """
        return self.checkbox.is_visible() and self.checkbox.is_checked()


class AsyncRecaptchaBox(RecaptchaBox):
    """
    The asynchronous class for reCAPTCHA v2 boxes.

    Parameters
    ----------
    anchor_frame : AsyncFrame
        The reCAPTCHA anchor frame.
    bframe_frame : AsyncFrame
        The reCAPTCHA bframe frame.
    """

    def __init__(self, anchor_frame: AsyncFrame, bframe_frame: AsyncFrame) -> None:
        self._anchor_frame = anchor_frame
        self._bframe_frame = bframe_frame

    def __repr__(self) -> str:
        return f"AsyncRecaptchaBox(anchor_frame={self._anchor_frame!r}, bframe_frame={self._bframe_frame!r})"

    @classmethod
    async def from_frames(cls, frames: Iterable[AsyncFrame]) -> AsyncRecaptchaBox:
        """
        Create a reCAPTCHA box using a list of frames.

        Parameters
        ----------
        frames : Iterable[AsyncFrame]
            A list of frames to search for the reCAPTCHA frames.

        Returns
        -------
        AsyncRecaptchaBox
            The reCAPTCHA box.

        Raises
        ------
        RecaptchaNotFoundError
            If the reCAPTCHA frames were not found
            or if no unchecked reCAPTCHA boxes were found.
        """
        frame_pairs = cls._get_recaptcha_frame_pairs(frames)

        for anchor_frame, bframe_frame in frame_pairs:
            recaptcha_box = cls(anchor_frame, bframe_frame)

            if (
                await recaptcha_box.checkbox.is_visible()
                and not await recaptcha_box.checkbox.is_checked()
                or await recaptcha_box.audio_challenge_button.is_visible()
                or await recaptcha_box.image_challenge_button.is_visible()
            ):
                return recaptcha_box

        raise RecaptchaNotFoundError("No unchecked reCAPTCHA boxes were found.")

    @property
    def anchor_frame(self) -> AsyncFrame:
        """The reCAPTCHA anchor frame."""
        return self._anchor_frame

    @property
    def bframe_frame(self) -> AsyncFrame:
        """The reCAPTCHA bframe frame."""
        return self._bframe_frame

    @RecaptchaBox._check_if_attached
    async def rate_limit_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA rate limit message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA rate limit message is visible, False otherwise.
        """
        return await self.bframe_frame.get_by_text("Try again later").is_visible()

    @RecaptchaBox._check_if_attached
    async def solve_failure_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA solve failure message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA solve failure message is visible, False otherwise.
        """
        return await self.bframe_frame.get_by_text(
            "Multiple correct solutions required - please solve more."
        ).is_visible()

    @RecaptchaBox._check_if_attached
    async def audio_challenge_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA audio challenge is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA audio challenge is visible, False otherwise.
        """
        return await self.bframe_frame.get_by_text("Press PLAY to listen").is_visible()

    @RecaptchaBox._check_if_attached
    async def try_again_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA try again message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA try again message is visible, False otherwise.
        """
        return await self.bframe_frame.get_by_text(
            re.compile("Please try again")
        ).is_visible()

    @RecaptchaBox._check_if_attached
    async def check_new_images_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA check new images message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA check new images message is visible, False otherwise.
        """
        return await self.bframe_frame.get_by_text(
            re.compile("Please also check the new images")
        ).is_visible()

    @RecaptchaBox._check_if_attached
    async def select_all_matching_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA select all matching images message is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA select all matching images message is visible,
            False otherwise.
        """
        return await self.bframe_frame.get_by_text(
            re.compile("Please select all matching images")
        ).is_visible()

    @RecaptchaBox._check_if_attached
    async def challenge_is_visible(self) -> bool:
        """
        Check if the reCAPTCHA challenge is visible.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge is visible, False otherwise.
        """
        button = self.skip_button.or_(self.next_button).or_(self.verify_button)
        return await button.is_enabled()

    @RecaptchaBox._check_if_attached
    async def challenge_is_solved(self) -> bool:
        """
        Check if the reCAPTCHA challenge has been solved.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge has been solved, False otherwise.
        """
        return await self.checkbox.is_visible() and await self.checkbox.is_checked()
