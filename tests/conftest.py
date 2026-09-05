import os
import sys
from unittest.mock import MagicMock, patch

# Offscreen backend — works without a display (CI, Xvfb, etc.)
# If the variable is already set (e.g. DISPLAY), don't override it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Mock evdev when unavailable so shared and offscreen tests can still collect.
# The apps' conftest.py files do the same thing.
try:
    import evdev  # noqa: F401
except ImportError:
    sys.modules['evdev'] = MagicMock()

# Add the project root to the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


@pytest.fixture(autouse=True)
def silence_sounds():
    """Mutes sound playback (SoundFeedback) in all tests."""
    with patch("infrastructure.common.audio.feedback.SoundFeedback.play"):
        yield


@pytest.fixture
def mock_gamepad(qapp):
    """
    GamepadWatcher without starting the _loop thread.

    Patches threading.Thread before __init__ calls it,
    so the evdev loop never starts — tests are fully isolated
    from hardware and UInput permissions.
    """
    with patch("infrastructure.linux.input.gamepad_watcher.threading.Thread"):
        from infrastructure.linux.input.gamepad_watcher import GamepadWatcher
        gw = GamepadWatcher()
    return gw
