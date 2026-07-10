# KD nad pulpitem KDE — likwidacja "obnażenia" Plasmy przy powrocie z aplikacji

Notatka robocza. Zweryfikowano na maszynie z KDE (Plasma 6 / Wayland / KWin 6.5).

## Problem

Po zamknięciu Steama (np. wyjście z Big Picture) pulpit KDE (Plasma) był przez
chwilę widoczny, zanim KD wróci na ekran. Sekwencja przed zmianą:

1. Przy starcie aplikacji KD **unmapował** swoje okno (`hide_view()` →
   `QWidget.hide()`), zostawiając pod aplikacją goły pulpit Plasmy.
2. Powrót wyzwalało dopiero **zakończenie procesu** (blokujące `wait()` w wątku
   → `on_app_finished` → `showFullScreen()`).
3. Steam po zamknięciu okna BPM wygasza podsystemy jeszcze przez 1–5 s zanim
   proces umrze. Okno Steama już nie istnieje, okno KD jeszcze nie — KWin
   pokazuje jedyne co ma: Plasmę. Do tego ~100–300 ms na remap i pierwszą
   klatkę KD.

Dominującą częścią przerwy było okno czasowe "okno Steama zniknęło, ale proces
jeszcze żyje", nie latencja mapowania.

## Rozwiązanie (zaimplementowane)

**Nie unmapować — zostać na TOP, oddać klawiaturę.** KD jest surfacem
wlr-layer-shell na warstwie TOP. Gdy aplikacja przejmuje ekran, zamiast `hide()`:

- `setKeyboardInteractivity(NONE)` — KD zostaje zmapowane na TOP, ale bez
  klawiatury; w trakcie grania klawiatura trafia do gry, nie do KD.
- Powrót: `setKeyboardInteractivity(ON_DEMAND)` — bez remapowania, bez czekania
  na pierwszą klatkę.

KWin stackuje **pełnoekranowe** okna xdg-toplevel **ponad** warstwą layer-shell
TOP — potwierdzone spikem (`tools/spike_topcover.py`). Gdy okno aplikacji
znika (unmap), KWin od razu odsłania **gotowy, narysowany pulpit KD** zamiast
Plasmy. Koszt w trakcie grania ~zero: całkowicie zasłonięty surface nie dostaje
frame callbacków (Qt nic nie renderuje); direct scanout gry nie cierpi.

### Dlaczego nie BOTTOM (pierwotny plan)

Pierwotnie planowano obniżyć warstwę do BOTTOM. Spike
(`tools/spike_layerswitch.py`) potwierdził, że `set_layer` na żywym oknie
działa (LayerShellQt wysyła `zwlr_layer_surface_v1.set_layer` na wire), ale
okazało się, że warstwa BOTTOM w KWin leży **poniżej** normalnych okien
i pulpitu Plasmy — zielony surface na BOTTOM zachowywał się jak tapeta:
okno Konsole i taskbar KDE były nad nim. BOTTOM nie ukrywa KD pod aplikacją —
odsłania KDE ponad KD.

### Pełny ekran vs zwykłe okno

Nie każda aplikacja przykrywa cały ekran:

- **Pełnoekranowa** (Steam BPM, File Browser) — okno pokrywa całe workspace;
  cede (zostań na TOP + `Keyboard.NONE`) wystarcza, gra przykrywa KD.
- **Okienkowa** (Konsole, Brave, Bitwarden) — okno nie pokrywa TOP; KD musi
  zostać naprawdę schowane (`hide()` / `withdraw`), inaczej zasłoni aplikację.

`DeferredHide` rozróżnia te przypadki po właściwościach okna aplikacji:
`fullscreen` (protokół KWin) lub `covers_screen` (geometria >= workspace —
wyłapuje Steam BPM, który nie ustawia `fullscreen` w KWin).

`restore_app` robi to samo synchronicznie przez `_target_is_fullscreen()`,
bo okno przywracanej aplikacji już istnieje na liście okien.

Dodatkowo: trwały skrypt KWin podpięty pod `workspace.windowRemoved` wywołuje
(z debounce 150 ms) odświeżenie listy okien — reakcja na zniknięcie okna
w ~150 ms zamiast pollingu co 3 s. Przyspiesza m.in. `check_active_dyn_gone`
(powrót po zamknięciu okna dynamicznego).

### Zmienione pliki

- `src/infrastructure/kde/qt/ui/layer_shell.py` — helper `set_keyboard()`
  (zmiana `KeyboardInteractivity` na zmapowanym oknie). `set_layer()` usunięty
  (nie używany po odrzuceniu BOTTOM).
- `src/infrastructure/kde/qt/desktop/surface.py` — `LayerShellSurface`:
  `drop_below()` (zostań na TOP + `Keyboard.NONE`), logiczna widoczność
  `_in_front` (`is_visible()` = "KD ma klawiaturę", nie "widget zmapowany").
- `src/infrastructure/common/qt/desktop/surface.py` — port `DesktopSurface`
  zyskał `drop_below()`; `PlainSurface` robi fallback do `hide()`.
- `src/infrastructure/windows/qt/desktop_surface.py` — `drop_below()` →
  `hide()` (zachowanie Windows bez zmian).
- `src/infrastructure/common/qt/desktop/desktop.py` — `hide_view()` →
  `surface.drop_below()` (cede); nowy `withdraw_view()` → `surface.hide()`
  (prawdziwe schowanie do traya / oddanie ekranu okienkowej aplikacji);
  `show_fullscreen()` tłumi hover kafelków (powrót bez remapu nie wywoła
  `showEvent`).
- `src/domain/shell/desktop_view.py` — port: nowa metoda `withdraw_view()`.
- `src/domain/shell/desktop.py` — `pause()` używa `withdraw_view()` (pauza do
  traya nadal naprawdę chowa okno).
- `src/domain/lifecycle/app_lifecycle.py` — `restore_app()` rozróżnia cede
  vs withdraw przez `_target_is_fullscreen()`; `DeferredHide` rozbrojony
  przy restore (okno już istnieje).
- `src/infrastructure/kde/qt/desktop/deferred_hide.py` — przyjmuje `on_cede`
  i `on_hide`; wybiera na podstawie `fullscreen || covers_screen` okna.
- `src/infrastructure/kde/qt/desktop/app_windows.py` — `app_window_fullscreen()`
  (fullscreen lub covers_screen).
- `src/domain/catalog/window.py` — pola `fullscreen`, `covers_screen`.
- `src/infrastructure/kde/wm/window_manager.py` — skrypt KWin pobiera
  `fullscreen` i `coversScreen` (geometria >= `virtualScreenSize`); trwały
  skrypt zdarzeń (`windowRemoved` → D-Bus → debounce 150 ms → `refresh_now()`).
- `tools/spike_layerswitch.py`, `tools/spike_topcover.py` — spiki
  weryfikujące warstwy na żywym KWin.

## Odrzucone warianty

- **BOTTOM layer** — KWin stackuje BOTTOM pod NormalLayer; pulpit Plasmy,
  panele i okna przebijają ponad surfacem na BOTTOM.
- **Plan B (hide + natychmiastowy re-show)** — niepotrzebny; cede na TOP działa.
- **Kurtyna (osobny surface na BOTTOM)** — niepotrzebny.

## Deferred show (zaimplementowane)

Dla aplikacji okienkowych (withdraw), powrót KD wyzwala **zniknięcie ostatniego
okna aplikacji**, nie exit procesu. `DeferredShow` (lustro `DeferredHide`)
obserwuje listę okien i po `_CONFIRM_MS` = 500 ms ciszy woła
`AppLifecycle.on_app_windows_gone()` → `reactivate_desktop()` → TOP +
`ON_DEMAND` + input. Wraz ze skryptem `windowRemoved` (reakcja ~150 ms) KD
wraca w ~650 ms zamiast po 1–5 s.

Dla aplikacji pełnoekranowych (cede) `DeferredShow` jest uzbrojone dla
spójności, ale zniknięcie okna odsłania KD natychmiast bez jego pomocy.

Potwierdzenie 500 ms chroni przed grą, która odtwarza okno w locie (zmiana
trybu wideo): unmap→map w tym oknie czasowym nie liczy się jako zniknięcie.

### Zmienione pliki (deferred show)

- `src/domain/lifecycle/launch_show.py` — nowy port `LaunchShow`.
- `src/infrastructure/kde/qt/desktop/deferred_show.py` — maszyna stanu.
- `src/infrastructure/kde/qt/desktop/app_windows.py` — `has_mapped_window()`,
  wyciągnięte z `DeferredHide._app_window_present` (używane przez obie strony).
- `src/domain/lifecycle/app_lifecycle.py` — `arm()` przy launch i restore,
  `cancel()` przy `reactivate_desktop` / `on_app_finished`; nowe
  `on_app_windows_gone()` (respektuje pauzę).
- `src/infrastructure/common/qt/desktop/desktop_builder.py` — fabryka +
  `_NoDeferredShow` dla platform bez adaptera.

### Ryzyko rezydualne

Jeśli aplikacja zostanie bez okien na dłużej niż 500 ms, ale nie umiera, KD
wjedzie na wierzch. Po fałszywym podniesieniu watcher jest już rozbrojony —
ponowne pojawienie się okna nie zepchnie KD z powrotem. Dla aplikacji
pełnoekranowych (cede) ryzyko jest czysto teoretyczne — okno gry przykrywa
TOP, więc fałszywe podniesienie jest niewidoczne.

Nieuzbrojone przypadki: gdy okno aplikacji nigdy się nie zmapuje, `DeferredHide`
chowa KD po 5 s guardem, a `DeferredShow` nie ma czego pilnować (`_seen_window`
zostaje `False`) — zachowanie jak przed zmianą.

## Przenośność na Hyprland / Sway / GNOME (vs branch `kde_independence`)

Branch `kde_independence` przenosi `LayerShellSurface` + bridge `layer_shell.py`
do `infrastructure/linux/wayland/` i współdzieli je między KWin, Sway i
Hyprlandem (wszystkie mówią zwlr-layer-shell); GNOME dostaje osobny
`GnomeSurface` oparty o rozszerzenie "Kasual Helper" (Mutter nie ma layer-shell).

**Hyprland / Sway — cede działa bez dodatkowej implementacji.** Zmiana żyje
w całości w `LayerShellSurface` i używa standardowego `set_keyboard_interactivity`
(protokół >= v2). Pełnoekranowe okna w wlroots kompozytorach również stackowane
są ponad layer-shell TOP (zwlr-layer-shell spec: "surfaces are rendered above
... always below regular windows" dla TOP) — zachowanie analogiczne do KWin.
`covers_screen` wymaga jednak adaptera, który pobiera geometrię okien (KWin robi
to przez skrypt `virtualScreenSize`; Sway/Hyprland mają IPC do geometrii). Bez
tego fallback to `hide()` — aplikacje nie-ustawiające `fullscreen` w protokole
(jak Steam BPM) wracają do zachowania z mignięciem.

**GNOME — zaimplementowane (cede w rozszerzeniu).**

Mutter nie ma layer-shell. Zmierzone zachowanie stackingu (przez `Debug`
rozszerzenia): okno pełnoekranowe siedzi w warstwie NORMAL (2), a `make_above`
wypycha okno (nawet pełnoekranowe) do warstwy TOP (4). KD jest pokazywane przez
`showFullScreen()`, więc gdyby przy cede zostało `make_above`, wylądowałoby
w warstwie 4 — **nad** grą (warstwa 2) i by ją zasłoniło (dokładnie ten błąd:
KD bez chrome nad Steamem).

Niezmiennik cede (`GnomeSurface.drop_below` → `CedeOverlay` → `_ceded`) w
`_sync()`: **KD nad zwykłymi oknami, pod każdym oknem pełnoekranowym**. Zdejmuje
z okien KD flagę above (`unmake_above` → spadają do warstwy 2), podnosi KD nad
zwykłe okna, a potem podnosi **wszystkie** nie-nasze okna pełnoekranowe z powrotem
nad KD, w kolejności stosu (gra zostaje nad launcherem). Do tego
`_setRestackGuard(false)` i `_setUnredirectSuppressed(false)` (najwyższa apka
dostaje direct scanout). Gdy znika ostatnie okno pełnoekranowe, nic nie jest
podnoszone nad KD → KD staje się najwyżej → Mutter od razu je odsłania, bez
remapu i bez pollingu. Powrót przez `deferred_show` → `ShowOverlay` zeruje `_ceded`
i przypina KD z powrotem (przez `make_above`).

Podnoszenie robi `raiseWindow()` (`raise_and_make_recent()`) — czysta operacja
stackingu z wnętrza Shella, nie podlega ochronie przed kradzieżą fokusu (inaczej
niż klienckie `activate()`). `notify::fullscreen` na każdym oknie wyzwala `_sync`,
żeby gra wchodząca w fullscreen po splashu launchera trafiła nad KD.

Iteracje, które doprowadziły do reguły „zbiór okien fullscreen" (zmierzone przez
`Debug`): (1) `make_above` na KD → warstwa 4 nad grą → KD zasłaniało Steama;
(2) podnoszenie okna z fokusem per-sync → po zamknięciu gry fokus szedł na
terminal i to on lądował nad KD (sekunda pulpitu, bo dopiero `deferred_show`
przypinał KD); (3) zapamiętane pojedyncze okno → przy Steam+gra `_sync` podnosił
Steama nad KCD (waiting screen zamiast gry). Reguła „pod wszystkimi fullscreen"
obsługuje wszystkie trzy: powrót (brak fullscreen → KD na wierzchu), Steam sam
(Steam nad KD) i Steam+gra (gra nad Steamem nad KD).

Wykrywanie fullscreen: rozszerzenie zwracało `is_fullscreen()` w `ListWindows`
od początku, ale adapter to gubił — teraz `GnomeWindowManager` parsuje
`fullscreen` (i `desktop_file`), więc `DeferredHide` poprawnie wybiera cede
dla apki pełnoekranowej, a `hide()` (realny unmap) dla okienkowej.

*Ograniczenie:* reguła bazuje na `is_fullscreen()`. Gra w trybie borderless
(pełny rozmiar wyjścia bez stanu fullscreen) nie zostanie podniesiona nad KD.
Steam BPM i KCD w trybie fullscreen działają; `covers_screen` bez fullscreen
jest otwarty (tak jak na KDE).

*Atrybucja okno → aplikacja:* okno XWayland zgłasza X11 WM_CLASS (np.
`Bitwarden`), nie flatpakowe app-id kafelka (`com.bitwarden.desktop`). KWin
dokłada `desktopFile`; GNOME nie miał odpowiednika, więc okno lądowało jako
"zewnętrzne" (osobny kafel dynamiczny, kafel Apps "not running", `DeferredHide`
bez dopasowania). Rozszerzenie raportuje teraz app-id przez
`Shell.WindowTracker.get_window_app(w).get_id()` (dla flatpaka rozwiązywane po
sandboxed-app-id, więc niezależne od WM_CLASS), adapter mapuje je na
`desktop_file`. Parytet z KWin.

*Forwarder / single-instance (np. flatpak):* proces uruchamiający kończy się,
gdy tylko przekaże żądanie, a prawdziwe okno żyje pod innym PID-em. `on_app_finished`
sprawdza więc `_still_windowed(app_id)`: jeśli aplikacja wciąż ma okno, nie
wracamy na KD — powrót zostawiamy `DeferredShow` (window-gone). Bez tego KD
"odbijało" nad świeżo pokazanym oknem (Bitwarden). Fix jest w domenie, wspólny
dla wszystkich kompozytorów.

**Szybki refresh po `windowRemoved` jest KWin-only** (skrypty KWin przez
D-Bus). Odpowiedniki wymagają osobnych adapterów: Sway — IPC `subscribe` na
zdarzenia okien, Hyprland — socket2 (`closewindow`), GNOME — sygnał z
rozszerzenia. Na branchu adaptery wlroots pollują co 3 s, więc bez tego
powrót po zamknięciu okna dynamicznego reaguje tam wolniej niż na KDE.

`DeferredShow` działa wszędzie, gdzie `WindowManager` publikuje listę okien,
ale na pollingu 3 s KD wróci nawet ~3,5 s po zniknięciu okna. Sam komponent
nie zależy od KWin — tylko `has_mapped_window()` sięga po `expand_pid_tree`
z adaptera KWin i przy przenosinach trafia do `linux/`.