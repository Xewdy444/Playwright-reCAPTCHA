from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from functools import wraps
from typing import Awaitable, Callable, Iterable, List, Tuple, Union

from playwright.async_api import Frame as AsyncFrame
from playwright.async_api import Locator as AsyncLocator
from playwright.sync_api import Frame as SyncFrame
from playwright.sync_api import Locator as SyncLocator

from playwright_recaptcha.errors import RecaptchaNotFoundError, RecaptchaSolveError
from playwright_recaptcha.recaptchav2.locales import SIGNATURES

Locator = Union[AsyncLocator, SyncLocator]
Frame = Union[AsyncFrame, SyncFrame]


class RecaptchaBox(ABC):
    """
    The base class for reCAPTCHA v2 boxes.

    Attributes
    ----------
    anchor_frame : Frame
        The reCAPTCHA anchor frame.
    bframe_frame : Frame
        The reCAPTCHA bframe frame.
    checkbox : Locator
        The reCAPTCHA checkbox locator.
    audio_challenge_button : Locator
        The reCAPTCHA audio challenge button locator.
    new_challenge_button : Locator
        The reCAPTCHA new challenge button locator.
    audio_download_button : Locator
        The reCAPTCHA audio download button locator.
    audio_challenge_textbox : Locator
        The reCAPTCHA audio challenge textbox locator.
    audio_challenge_verify_button : Locator
        The reCAPTCHA audio challenge verify button locator.

    Methods
    -------
    from_frames(frames: Iterable[Frame]) -> Union[AsyncRecaptchaBox, SyncRecaptchaBox]
        Create a reCAPTCHA box using a list of frames.
    frames_are_attached() -> bool
        Check if the reCAPTCHA frames are attached.
    rate_limit_is_visible() -> bool
        Check if the reCAPTCHA rate limit message is visible.
    solve_failure_is_visible() -> bool
        Check if the reCAPTCHA solve failure message is visible.
    audio_challenge_is_visible() -> bool
        Check if the reCAPTCHA audio challenge is visible.
    is_solved() -> bool
        Check if the reCAPTCHA challenge is solved.

    Raises
    ------
    RecaptchaNotFoundError
        If the reCAPTCHA was not found.
    RecaptchaSolveError
        If no unchecked reCAPTCHA boxes were found.
    """

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
        anchor_frames = list(
            filter(
                lambda frame: re.search(
                    "/recaptcha/(api2|enterprise)/anchor", frame.url
                )
                is not None,
                frames,
            )
        )

        bframe_frames = list(
            filter(
                lambda frame: re.search(
                    "/recaptcha/(api2|enterprise)/bframe", frame.url
                )
                is not None,
                frames,
            )
        )

        frame_pairs = []

        for anchor_frame in anchor_frames:
            frame_id = anchor_frame.name[2:]

            for bframe_frame in bframe_frames:
                if frame_id in bframe_frame.name:
                    frame_pairs.append((anchor_frame, bframe_frame))

        if not frame_pairs:
            raise RecaptchaNotFoundError

        return frame_pairs

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
        Check if the reCAPTCHA frames are attached before running the decorated function,
        otherwise return False.

        Parameters
        ----------
        func : Union[
            Callable[[AsyncRecaptchaBox], Awaitable[bool]], Callable[[SyncRecaptchaBox], bool]
        ]
            The function to decorate.

        Returns
        -------
        Union[
            Callable[[AsyncRecaptchaBox], Awaitable[bool]], Callable[[SyncRecaptchaBox], bool]
        ]
            The decorated function.
        """

        @wraps(func)
        def sync_wrapper(self: SyncRecaptchaBox) -> bool:
            if self.frames_are_detached():
                return False

            return func(self)

        @wraps(func)
        async def async_wrapper(self: AsyncRecaptchaBox) -> bool:
            if self.frames_are_detached():
                return False

            return await func(self)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper

        return sync_wrapper

    @property
    def checkbox(self) -> Locator:
        """The reCAPTCHA checkbox locator."""
        return self.anchor_frame.get_by_role("checkbox", name=SIGNATURES['im_not_a_robot'])

    @property
    def audio_challenge_button(self) -> Locator:
        """The reCAPTCHA audio challenge button locator."""
        return self.bframe_frame.get_by_role("button", name=SIGNATURES['get_an_audio_challenge'])

    @property
    def new_challenge_button(self) -> Locator:
        """The reCAPTCHA new challenge button locator."""
        return self.bframe_frame.get_by_role("button", name=SIGNATURES['get_a_new_challenge'])

    @property
    def audio_download_button(self) -> Locator:
        """The reCAPTCHA audio download button locator."""
        return self.bframe_frame.get_by_role(
            "link", name=SIGNATURES['download_audio_as_mp3']
        )

    @property
    def audio_challenge_textbox(self) -> Locator:
        """The reCAPTCHA audio challenge textbox locator."""
        return self.bframe_frame.get_by_role("textbox", name=SIGNATURES['enter_what_you_hear'])

    @property
    def audio_challenge_verify_button(self) -> Locator:
        """The reCAPTCHA audio challenge verify button locator."""
        return self.bframe_frame.get_by_role("button", name=SIGNATURES['verify'])

    def frames_are_attached(self) -> bool:
        """
        Check if the reCAPTCHA frames are attached.

        Returns
        -------
        bool
            True if the reCAPTCHA frames are attached, False otherwise.
        """
        return (
            not self.anchor_frame.is_detached() and not self.bframe_frame.is_detached()
        )

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
            If the reCAPTCHA frames were not found.
        RecaptchaSolveError
            If no unchecked reCAPTCHA boxes were found.
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
    def is_solved(self) -> bool:
        """
        Check if the reCAPTCHA challenge is solved.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge is solved, False otherwise.
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

    Attributes
    ----------
    anchor_frame : Frame
        The reCAPTCHA anchor frame.
    bframe_frame : Frame
        The reCAPTCHA bframe frame.
    checkbox : Locator
        The reCAPTCHA checkbox locator.
    audio_challenge_button : Locator
        The reCAPTCHA audio challenge button locator.
    new_challenge_button : Locator
        The reCAPTCHA new challenge button locator.
    audio_download_button : Locator
        The reCAPTCHA audio download button locator.
    audio_challenge_textbox : Locator
        The reCAPTCHA audio challenge textbox locator.
    audio_challenge_verify_button : Locator
        The reCAPTCHA audio challenge verify button locator.

    Methods
    -------
    from_frames(frames: Iterable[SyncFrame]) -> SyncRecaptchaBox
        Create a reCAPTCHA box using a list of frames.
    frames_are_attached() -> bool
        Check if the reCAPTCHA frames are attached.
    rate_limit_is_visible() -> bool
        Check if the reCAPTCHA rate limit message is visible.
    solve_failure_is_visible() -> bool
        Check if the reCAPTCHA solve failure message is visible.
    audio_challenge_is_visible() -> bool
        Check if the reCAPTCHA audio challenge is visible.
    is_solved() -> bool
        Check if the reCAPTCHA challenge is solved.

    Raises
    ------
    RecaptchaNotFoundError
        If the reCAPTCHA was not found.
    RecaptchaSolveError
        If no unchecked reCAPTCHA boxes were found.
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
            If the reCAPTCHA frames were not found.
        RecaptchaSolveError
            If no unchecked reCAPTCHA boxes were found.
        """
        frame_pairs = cls._get_recaptcha_frame_pairs(frames)

        for anchor_frame, bframe_frame in frame_pairs:
            checkbox = anchor_frame.get_by_role("checkbox", name=SIGNATURES['im_not_a_robot'])

            if (
                bframe_frame.get_by_role(
                    "button", name=SIGNATURES['get_an_audio_challenge']
                ).is_visible()
                or checkbox.is_visible()
                and not checkbox.is_checked()
            ):
                return cls(anchor_frame, bframe_frame)

        raise RecaptchaSolveError("No unchecked reCAPTCHA boxes were found.")

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
        return self.bframe_frame.get_by_text(SIGNATURES['try_again_later']).is_visible()

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
            SIGNATURES['multiple_correct_solutions_required']
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
        return self.bframe_frame.get_by_text(SIGNATURES['press_play_to_listen']).is_visible()

    @RecaptchaBox._check_if_attached
    def is_solved(self) -> bool:
        """
        Check if the reCAPTCHA challenge is solved.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge is solved, False otherwise.
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

    Attributes
    ----------
    anchor_frame : Frame
        The reCAPTCHA anchor frame.
    bframe_frame : Frame
        The reCAPTCHA bframe frame.
    checkbox : Locator
        The reCAPTCHA checkbox locator.
    audio_challenge_button : Locator
        The reCAPTCHA audio challenge button locator.
    new_challenge_button : Locator
        The reCAPTCHA new challenge button locator.
    audio_download_button : Locator
        The reCAPTCHA audio download button locator.
    audio_challenge_textbox : Locator
        The reCAPTCHA audio challenge textbox locator.
    audio_challenge_verify_button : Locator
        The reCAPTCHA audio challenge verify button locator.

    Methods
    -------
    from_frames(frames: Iterable[AsyncFrame]) -> AsyncRecaptchaBox
        Create a reCAPTCHA box using a list of frames.
    frames_are_attached() -> bool
        Check if the reCAPTCHA frames are attached.
    rate_limit_is_visible() -> bool
        Check if the reCAPTCHA rate limit message is visible.
    solve_failure_is_visible() -> bool
        Check if the reCAPTCHA solve failure message is visible.
    audio_challenge_is_visible() -> bool
        Check if the reCAPTCHA audio challenge is visible.
    is_solved() -> bool
        Check if the reCAPTCHA challenge is solved.

    Raises
    ------
    RecaptchaNotFoundError
        If the reCAPTCHA was not found.
    RecaptchaSolveError
        If no unchecked reCAPTCHA boxes were found.
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
            If the reCAPTCHA frames were not found.
        RecaptchaSolveError
            If no unchecked reCAPTCHA boxes were found.
        """
        frame_pairs = cls._get_recaptcha_frame_pairs(frames)

        for anchor_frame, bframe_frame in frame_pairs:
            checkbox = anchor_frame.get_by_role("checkbox", name=SIGNATURES['im_not_a_robot'])

            if (
                await bframe_frame.get_by_role(
                    "button", name=SIGNATURES['get_an_audio_challenge']
                ).is_visible()
                or await checkbox.is_visible()
                and not await checkbox.is_checked()
            ):
                return cls(anchor_frame, bframe_frame)

        raise RecaptchaSolveError("No unchecked reCAPTCHA boxes were found.")

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
        return await self.bframe_frame.get_by_text(SIGNATURES['try_again_later']).is_visible()

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
            SIGNATURES['multiple_correct_solutions_required']
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
        return await self.bframe_frame.get_by_text(SIGNATURES['press_play_to_listen']).is_visible()

    @RecaptchaBox._check_if_attached
    async def is_solved(self) -> bool:
        """
        Check if the reCAPTCHA challenge is solved.

        Returns
        -------
        bool
            True if the reCAPTCHA challenge is solved, False otherwise.
        """
        return await self.checkbox.is_visible() and await self.checkbox.is_checked()
