# KD nad pulpitem KDE — likwidacja "obnażenia" Plasmy przy powrocie ze Steama

Notatka robocza do weryfikacji na maszynie z KDE (Plasma 6 / Wayland).

## Problem

Po zamknięciu Steama (np. wyjście z Big Picture) pulpit KDE (Plasma) jest przez
chwilę widoczny, zanim KD wróci na ekran. Sekwencja przed zmianą:

1. Przy starcie aplikacji KD **unmapował** swoje okno (`hide_view()` →
   `QWidget.hide()`), zostawiając pod aplikacją goły pulpit Plasmy.
2. Powrót wyzwalało dopiero **zakończenie procesu** (blokujące `wait()` w wątku
   → `on_app_finished` → `showFullScreen()`).
3. Steam po zamknięciu okna BPM wygasza podsystemy jeszcze przez 1–5 s zanim
   proces umrze. Okno Steama już nie istnieje, okno KD jeszcze nie — KWin
   pokazuje jedyne co ma: Plasmę. Do tego ~100–300 ms na remap i pierwszą
   klatkę KD.

Dominującą częścią przerwy jest okno czasowe "okno Steama zniknęło, ale proces
jeszcze żyje", nie latencja mapowania.

## Rozwiązanie (zaimplementowane)

**Nie unmapować — obniżyć warstwę.** KD jest surfacem wlr-layer-shell (warstwa
TOP). Gdy aplikacja przejmuje ekran, zamiast `hide()`:

- `setLayer(BOTTOM)` + `setKeyboardInteractivity(NONE)` — KD zostaje zmapowane
  i narysowane, ale pod normalnymi/fullscreenowymi oknami; klawiatura nie może
  do niego trafić w trakcie grania.
- Powrót: `setLayer(TOP)` + `ON_DEMAND` — bez remapowania i bez czekania na
  pierwszą klatkę.

Gdy okno Steama znika, KWin od razu odsłania **gotowy, narysowany pulpit KD**
zamiast Plasmy. Koszt w trakcie grania ~zero: całkowicie zasłonięty surface nie
dostaje frame callbacków (Qt nic nie renderuje); direct scanout gry nie cierpi
(liczy się najwyższy pełnoekranowy surface).

Dodatkowo: trwały skrypt KWin podpięty pod `workspace.windowRemoved` wywołuje
(z debounce) odświeżenie listy okien — reakcja na zniknięcie okna w ~150 ms
zamiast pollingu co 3 s. Przyspiesza m.in. `check_active_dyn_gone` (powrót po
zamknięciu okna dynamicznego).

### Zmienione pliki

- `src/infrastructure/kde/qt/ui/layer_shell.py` — helpery `set_layer()` /
  `set_keyboard()` (zmiana właściwości na zmapowanym oknie).
- `src/infrastructure/kde/qt/desktop/surface.py` — `LayerShellSurface`:
  `drop_below()` (BOTTOM zamiast hide), logiczna widoczność `_in_front`
  (`is_visible()` = "KD jest na wierzchu", nie "widget zmapowany").
- `src/infrastructure/common/qt/desktop/surface.py` — port `DesktopSurface`
  zyskał `drop_below()`; `PlainSurface` robi fallback do `hide()`.
- `src/infrastructure/windows/qt/desktop_surface.py` — `drop_below()` →
  `hide()` (zachowanie Windows bez zmian).
- `src/infrastructure/common/qt/desktop/desktop.py` — `hide_view()` →
  `surface.drop_below()`; nowy `withdraw_view()` → `surface.hide()` (prawdziwe
  schowanie do traya); `show_fullscreen()` tłumi hover kafelków (powrót bez
  remapu nie wywoła już `showEvent`).
- `src/domain/shell/desktop_view.py` — port: nowa metoda `withdraw_view()`.
- `src/domain/shell/desktop.py` — `pause()` używa `withdraw_view()` (pauza do
  traya nadal naprawdę chowa okno — obniżone KD zasłaniałoby pulpit Plasmy,
  którego użytkownik wtedy właśnie potrzebuje).
- `src/infrastructure/kde/wm/window_manager.py` — trwały skrypt zdarzeń
  (`workspace.windowRemoved` → D-Bus → debounce 150 ms → `refresh_now()`).

## Do zweryfikowania na maszynie z KDE

1. **`setLayer` na żywo**: czy LayerShellQt propaguje zmianę warstwy na już
   zmapowanym oknie (KWin wspiera `zwlr_layer_surface_v1.set_layer` od v2;
   LayerShellQt powinien wysyłać żądanie po `layerChanged`). Po `set_layer`
   wywołujemy `widget.update()`, żeby wymusić commit — sprawdzić, czy to
   wystarcza. Szybki test: rozszerzyć `tools/spike_layershell.py` o timer
   przełączający TOP↔BOTTOM co 2 s nad otwartym oknem innej aplikacji.
2. **Scenariusz Steam**: uruchomić Steam z kafelka → wyjść z BPM → w momencie
   zniknięcia okna Steama powinno być widać KD (tapeta + kafelki), nie Plasmę.
   Przez 1–5 s (do śmierci procesu) KD może być jeszcze nieinteraktywne — to
   oczekiwane.
3. **Panele Plasmy**: warstwa BOTTOM leży pod dokami — jeśli w sesji są panele,
   mogą być widoczne nad KD do czasu podniesienia na TOP. Ocenić, czy to
   przeszkadza.
4. **Pauza (odłączenie pada / tray)**: KD ma naprawdę zniknąć — pulpit Plasmy
   ma być normalnie dostępny.
5. **Klawiatura w trakcie grania**: wpisywanie tekstu w grze nie może trafiać
   do KD (obniżone KD ma `Keyboard.NONE`).
6. **X11/offscreen**: bez layer-shell `drop_below()` degraduje do `hide()` —
   zachowanie jak przed zmianą.

### Plan B (gdyby `set_layer` na żywo nie działał)

- hide + natychmiastowy re-show z warstwą ustawioną przed mapowaniem, albo
- osobny, stale zmapowany surface "kurtyna" na warstwie BOTTOM (czarny lub z
  tapetą KD), a główne okno KD chowane jak dotąd.

## Pomysł na później: deferred show (nieimplementowane)

Symetrycznie do `DeferredHide`: gdy okna pilnowanej aplikacji znikną z listy,
a proces wciąż żyje, po krótkim potwierdzeniu (2 puste odświeżenia ~500 ms)
podnieść KD na TOP i odzyskać input — zamiast czekać na exit procesu.

Ryzyko: gra odtwarzająca okno w locie (zmiana rozdzielczości/trybu) wywoła
fałszywy powrót KD nad działającą grę. Po wdrożeniu warstwy BOTTOM problem
wizualny już nie istnieje, więc zysk (input + przykrycie paneli 1–5 s
wcześniej) może nie być wart tego ryzyka. Jeśli wracać do tematu — tylko jako
opt-in per aplikacja (np. klucz `X-Kasual-ShowOnWindowsGone` dla kafelka
Steama, który okien w locie nie odtwarza).

## Przenośność na Hyprland / Sway / GNOME (vs branch `kde_independence`)

Branch przenosi `LayerShellSurface` + bridge `layer_shell.py` do
`infrastructure/linux/wayland/` i współdzieli je między KWin, Sway i Hyprlandem
(wszystkie mówią zwlr-layer-shell); GNOME dostaje osobny `GnomeSurface` oparty
o rozszerzenie "Kasual Helper" (Mutter nie ma layer-shell).

**Hyprland / Sway — działa bez dodatkowej implementacji.** Zmiana żyje w całości
w `LayerShellSurface` i używa standardowego żądania `zwlr_layer_surface_v1
.set_layer` (protokół ≥ v2; Sway i Hyprland wspierają). LayerShellQt mówi
czystym protokołem, więc działa też poza KDE (branch już instaluje tę bibliotekę
dla tych kompozytorów). Do weryfikacji na urządzeniu tak samo jak na KWin
(punkt 1 wyżej). Uwaga porządkowa: merge z masterem będzie konfliktował przez
przeniesienie plików — zmiany z `infrastructure/kde/qt/desktop/surface.py` i
`infrastructure/kde/qt/ui/layer_shell.py` trzeba przenieść 1:1 do
`infrastructure/linux/wayland/{surface,layer_shell}.py`.

**GNOME — potrzebna dodatkowa implementacja.**

1. *Minimum (bez tego merge się wysypie w runtime):* `GnomeSurface` musi dostać
   `drop_below()` — port `DesktopSurface` jest strukturalny (Protocol), więc
   domyślne ciało z portu nie jest dziedziczone; bez metody `hide_view()` rzuci
   `AttributeError`. Fallback `drop_below() → hide()` przywraca stare
   zachowanie (mignięcie pulpitu GNOME zostaje).
2. *Pełny efekt:* odpowiednik obniżenia warstwy trzeba dodać w rozszerzeniu
   Kasual Helper — zamiast unmapować okno: zwolnić pin i zepchnąć okno na dół
   stosu Muttera (okno zostaje zmapowane pod grą), a przy powrocie z powrotem
   je przypiąć. Bonus: pozostawienie okna zmapowanym omija wyścig
   frame-callbacków Muttera, który branch obchodzi przez `DeferredUnmap`.

**Szybki refresh po `windowRemoved` jest KWin-only** (skrypty KWin przez
D-Bus). Odpowiedniki wymagają osobnych adapterów: Sway — IPC `subscribe` na
zdarzenia okien, Hyprland — socket2 (`closewindow`), GNOME — sygnał z
rozszerzenia. Na branchu adaptery wlroots pollują co 3 s, więc bez tego powrót
po zamknięciu okna dynamicznego reaguje tam wolniej niż na KDE.
