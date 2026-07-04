"""The BTN_MODE recall policy: how the guide button summons the Kasual menu.

Under HOLD_1S a press shorter than HOLD_SECONDS is not a recall but a "short
press", forwarded to the foreground app so e.g. Steam still sees its guide button;
``release()`` reports whether that forward is due. When Kasual is in control,
recall is always immediate regardless of the app's policy.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from domain.input.vocabulary import Trigger

HOLD_SECONDS = 1.0


class RecallTrigger:
    def __init__(
        self,
        on_recall: Callable[[], None],
        *,
        hold_seconds: float = HOLD_SECONDS,
        timer_factory: Callable[[float, Callable[[], None]], object] = threading.Timer,
    ) -> None:
        self._on_recall     = on_recall
        self._hold_seconds  = hold_seconds
        self._timer_factory = timer_factory
        self._timer         = None
        self._recalled      = False

    def press(self, *, kasual_active: bool, trigger: str) -> None:
        """BTN_MODE went down. Recall now (CLICK / Kasual active) or arm the hold."""
        self._recalled = False
        if kasual_active or trigger == Trigger.CLICK:
            self._fire_recall()
        else:
            self._timer = self._timer_factory(self._hold_seconds, self._fire_recall)
            self._timer.start()

    def release(self, *, suppressed: bool) -> bool:
        """BTN_MODE went up. Cancel any pending hold; report if a short-press
        forward to the foreground app is due (the press did not recall and our
        UI is not in control)."""
        self._disarm()
        return not self._recalled and not suppressed

    def cancel(self) -> None:
        """Abandon any in-flight press (e.g. on gamepad refresh/disconnect)."""
        self._disarm()
        self._recalled = False

    def _disarm(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _fire_recall(self) -> None:
        self._recalled = True
        self._on_recall()
