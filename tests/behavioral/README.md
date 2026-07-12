# Testy behawioralne — PoC (KDE Plasma 6)

Koncept i motywacja: [`behavioral_tests.md`](../../behavioral_tests.md) w korzeniu repo.
Pliki celowo nie nazywają się `test_*.py` — pytest ich nie zbiera; to suita
uruchamiana ręcznie na żywej sesji, nie w CI.

## Moduły

- `kwin_watcher.py` — eventowy watcher toplevelów: wstrzykuje skrypt do KWin
  (mechanika jak w `src/infrastructure/kde/wm/window_manager.py`), każdy event
  (`added`/`removed`/`fullscreen`/`minimized`/`stacking`) niesie pełny snapshot
  `workspace.stackingOrder`. `wait_for()` konsumuje eventy sekwencyjnie, więc
  łańcuch waitów aseruje *kolejność* zdarzeń.
- `virtual_pad.py` — wirtualny pad (evdev `UInput`, kształt Xbox 360): przechodzi
  `GamepadWatcher._is_gamepad` i jest grabowany przez KD jak fizyczny.
- `scenario_kcd.py` — scenariusz PoC: uruchomienie KCD przez Steama, splash,
  fullscreen gry, proces, cede-depth, Home Menu nad grą.

## Uruchomienie (na maszynie z KDE Plasma 6 / Wayland)

1. Odłącz fizyczne pady (KD grabuje pierwsze pasujące urządzenie).
2. Uprawnienia do `/dev/uinput` (jak dla KD; grupa `input` / reguła udev).
3. Uruchom KD (`./kasual.sh`) — może już działać; jego pętla skanowania
   podłapie wirtualny pad, gdy tylko powstanie.
4. `python3 tests/behavioral/scenario_kcd.py`
   (inna gra: `STEAM_APPID=292030 python3 ...` — RED Launcher / W3).

Wynik: kroki `PASS/FAIL/WARN/SKIP` na stdout, pełny log eventów w
`tests/behavioral/artifacts/kcd-<data>.json`.

## Co PoC ma zweryfikować (poza samym scenariuszem)

- Czy powierzchnie layer-shell KD (`resourceClass=kasual-desktop`) w ogóle
  występują w `workspace.stackingOrder` — od tego zależą asercje stackingu
  (krok raportuje WARN i asercje przechodzą w SKIP, jeśli nie).
- Kierunek `stackingOrder` (samokalibracja po oknie desktopu w `top_down()`);
  do skontrolowania w JSON-ie z artifacts.
- Czy `fullScreen`/`fullscreen`/`coversScreen` poprawnie łapie fullscreen gry.
- Czy KD grabuje wirtualny pad — w logu KD: `Grabbed: behavioral-test-pad`.

Diagnostyka błędów skryptu KWin: `journalctl --user -t kwin_wayland -f`.

## Następne kroki (po weryfikacji PoC)

warstwa pytest-bdd (Gherkin), endpoint introspekcyjny KD, MangoHud FPS,
pozostałe kompozytory, opcjonalny capture ekranu — patrz plan w
`behavioral_tests.md`.
