# Testy behawioralne — PoC (KDE Plasma 6)

Koncept i motywacja: [`behavioral_tests.md`](../../behavioral_tests.md) w korzeniu repo.
Pliki celowo nie nazywają się `test_*.py` — pytest ich nie zbiera; to suita
uruchamiana ręcznie na żywej sesji, nie w CI.

## Moduły

- `kwin_watcher.py` — eventowy watcher toplevelów: wstrzykuje skrypt do KWin
  (mechanika jak w `src/infrastructure/kde/wm/window_manager.py`), każdy event
  (`added`/`removed`/`fullscreen`/`minimized`/`stacking`/`activated`) niesie pełny
  snapshot `workspace.stackingOrder`. `wait_for()` konsumuje eventy sekwencyjnie,
  więc łańcuch waitów aseruje *kolejność* zdarzeń.
- `kd_client.py` — klient testowego API KD (D-Bus, `KD_TEST_API=1`): stan powłoki
  (kafle, focus, powierzchnie).
- `navigation.py` — nawigacja padem po kaflach, z odczytem focusu po każdym kroku.
- `virtual_pad.py` — wirtualny pad (evdev `UInput`, kształt Xbox 360): przechodzi
  `GamepadWatcher._is_gamepad` i jest grabowany przez KD jak fizyczny.
- `scenario_kcd.py` — scenariusz PoC: **KD** uruchamia grę (pad → kafel → A),
  splash, fullscreen gry, cede-depth, Home Menu nad grą.

## Dlaczego KD musi wystawiać własny stan

Powierzchnie layer-shell (pulpit KD, HomeHeader, hint bar) **nie występują w
`workspace.stackingOrder`** — KWin przez API skryptowe pokazuje wyłącznie
toplevele. Stackingu KD nie da się więc stwierdzić od strony kompozytora; mówi o
nim samo KD (`ShellIntrospectionService`), a protokół layer-shell domyka wniosek:
menu Home jest powierzchnią warstwy `overlay` (zmapowane ⇒ nad każdym oknem, także
grą), a pulpit „sunk" siedzi na `bottom` (⇒ pod oknami aplikacji, także splashem).

Scenariusz musi też odpalać grę **przez KD**, nie przez `steam://rungameid/…`:
cała choreografia chowania (DeferredHide, CedeDepth) uzbraja się wyłącznie w
`AppLifecycle.on_tile_activated` — launch z boku zostawia HomeHeader i hint bar
nad Steamem.

## Uruchomienie (na maszynie z KDE Plasma 6 / Wayland)

1. Odłącz fizyczne pady (KD grabuje pierwsze pasujące urządzenie).
2. Uprawnienia do `/dev/uinput` (jak dla KD; grupa `input` / reguła udev).
3. Zatrzymaj działające KD — wirtualny pad musi istnieć, zanim KD wystartuje.
4. `python3 tests/behavioral/scenario_kcd.py` — skrypt tworzy pad i czeka, aż KD
   pojawi się na szynie.
5. W drugim terminalu: `KD_TEST_API=1 ./kasual.sh`

Kafel i appid są zahardkodowane pod bibliotekę tej maszyny (`TILE_ID`, `APPID` na
górze scenariusza) — suita jest lokalna, nie CI-owa. Kafel wskazuje się przez `id`
(stem `.desktop`) albo wyświetlaną nazwę; przy złym — błąd wypisuje listę
dostępnych.

Wynik: kroki `PASS/FAIL/WARN` na stdout, pełny log eventów w
`tests/behavioral/artifacts/kcd-<data>.json`. Na wyjściu (także po failu)
scenariusz zamyka grę i Steama — **bez asercji**: „ładne" kończenie aplikacji to
osobny scenariusz, nie doczepka do tego.

## Pułapki (wszystkie kosztowały debugowanie)

- Slot D-Bus **nie może** nazywać się `event` — nadpisuje `QObject.event()`, przez
  które QtDBus dostarcza wywołania; komunikat dociera i jest po cichu gubiony.
- `QCoreApplication(sys.argv)` bez przypisania jest zbierany przez GC: nazwa usługi
  zostaje na szynie, ścieżka obiektu znika, watcher nie dostaje nic.
- KWin 6.5 nie ma `workspace.stackingOrderChanged` (jest per-okno). Błąd JS zabija
  cały skrypt po cichu — jedyny ślad: `journalctl --user -b | grep kwin_scripting`.
- `loadScript` zwraca `-1` jako **poprawną** odpowiedź, gdy skrypt o tej nazwie
  wisi po wywalonym runie: `qdbus6 org.kde.KWin /Scripting
  org.kde.kwin.Scripting.unloadScript behavioral_watcher`.

## Następne kroki

warstwa pytest-bdd (Gherkin), MangoHud FPS jako dowód renderowania, pozostałe
kompozytory, opcjonalny capture ekranu — patrz plan w `behavioral_tests.md`.
