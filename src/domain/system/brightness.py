"""Brightness value object — floors at a non-zero minimum, since 0 is a black,
effectively unrecoverable screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol

from domain.system.bounded_value import BoundedValue


@dataclass(frozen=True)
class Brightness(BoundedValue):
    MIN:     ClassVar[int] = 5
    STEP:    ClassVar[int] = 10
    DEFAULT: ClassVar[int] = 70


class BrightnessControl(Protocol):
    """The display-backlight brightness port."""

    def get(self) -> Brightness: ...
    def set(self, brightness: Brightness) -> None: ...

    def is_controllable(self) -> bool:
        """Whether this host has a backlight this adapter can drive — gates the
        Quick-adjust brightness slider so it isn't shown dead."""
        ...
