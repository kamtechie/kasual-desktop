"""Heuristic: does an app look like a game / gaming launcher? Used to pre-select
tiles during onboarding."""

from domain.catalog.app import App

# Matched as substrings of the app's name or command (lowercased).
_LAUNCHER_KEYWORDS = (
    "steam",
    "epic games",
    "gog galaxy",
    "galaxyclient",
    "ea app",
    "ea desktop",
    "origin",
    "battle.net",
    "battlenet",
    "ubisoft",
    "uplay",
    "riot",
    "playnite",
    "itch",
    "amazon games",
    "xbox",
    "rockstar games",
)


def looks_like_game(app: App) -> bool:
    """True if *app* is categorized as a game or resembles a known launcher."""
    if app.is_game:
        return True
    hay = f"{app.name} {app.command}".lower()
    return any(keyword in hay for keyword in _LAUNCHER_KEYWORDS)
