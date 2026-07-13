"""Every wait in the harness, in seconds — the knobs a slower machine turns.

Generous by design: a scenario that fails because Steam was still updating shaders
teaches nothing, and these runs are watched by a human anyway.
"""

HOME_VIEW       = 20.0    # KD's device scan finding the pad, then the Home view
KWIN_WATCHER    = 5.0     # KWin loading the watcher script
TILE_FOCUS      = 3.0     # one pad press moving the focus
STEAM_UI        = 120.0   # Steam starting up, up to its Big Picture page
STEAM_INTRO     = 8.0     # Big Picture's intro animation, which swallows a press
STEAM_PAGE      = 20.0    # a page of Steam's UI animating in, and settling its focus
LAUNCHER        = 180.0   # Steam starting up, then the splash / launcher
GAME_FULLSCREEN = 300.0   # shader compilation lives here
CEDE            = 15.0    # KD getting off the screen
HOME_MENU       = 10.0    # the Home hold opening the menu over the game
EXIT            = 30.0    # a process, or KD, going away on the way out
