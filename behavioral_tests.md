# Testy behawioralne (E2E) — motywacja i koncept

Notatka robocza. Cel: automatyzacja scenariuszy z `test_scenarios.md` i przebiegów
typu "KD → Steam → gra → Home Menu", w duchu Behat/Cucumber/Playwright, ale dla
aplikacji linuksowej działającej jako warstwy Wayland nad innymi aplikacjami.
Scenariusze mogą być zahardkodowane pod konkretną maszynę deweloperską — to
suita uruchamiana lokalnie przed release'em, nie w CI (wymaga sesji Wayland,
GPU, gier).

## Motywacja

Testy jednostkowe pokrywają logikę KD (parsowanie, filtrowanie, budowa komend,
wiring fabryk). Nie pokrywają tego, co psuło się naprawdę:

- stacking warstw KD względem okien **cudzych aplikacji** — splash screen KCD
  i okno RED Launchera (W3) to zwykłe, niefullscreenowe okna, które na chwilę
  wyskakują nad Steamem i znikają, gdy silnik gry przejmie ekran; wymusiły
  zmiany w stackowaniu pod GNOME i KDE (`cede_depth`),
- widoczność elementów KD w praktyce (stacked views: widget "pokazany" nie
  znaczy "bieżący w stosie"),
- cała choreografia: KD uruchamia Steama, Steam grę, Home Menu wraca nad grę.

Sedno: chcemy stwierdzić "X jest teraz widoczny na ekranie" — także dla okien,
których nie kontrolujemy — możliwie **bez patrzenia na piksele**.

## Dlaczego nie gotowe narzędzie

- **Squish** — komercyjny standard dla Qt; introspekcja własnych widgetów, ale
  słaby do interakcji z cudzymi aplikacjami (Steam, gra). Drogi.
- **dogtail / AT-SPI** — introspekcja przez accessibility; działa dla Qt
  (`QT_ACCESSIBILITY=1`), ale gry accessibility nie implementują. Kruche.
- **openQA** — koncepcyjnie najbliższe (testuje całe sesje KDE/GNOME w VM,
  screenshoty + needles), ale ciężka machina, a VM z GPU pod gry to osobny
  problem. Zapożyczamy z niego model "needles", nie samo narzędzie.
- **Playwright/Selenium** — tylko web. Uwaga kalibrująca: `toBeVisible()`
  Playwrighta to "niepusty bounding box i nie display:none" — też nie sprawdza
  przykrycia innym oknem. Poziom pewności "jak w HTML" osiągamy strukturalnie.

Wniosek: cienki własny harness. KD ma dwie cechy, które go upraszczają:
sterowanie w 100% padem (evdev) i istniejące klienty IPC kompozytorów w
`src/infrastructure/`.

## Model warstw: co znaczy "widoczny" bez screenshota

### Warstwa 1 — drzewo Qt (odpowiednik DOM, tylko własne okna)

Problem stacked views rozstrzyga się wewnątrz KD: `QWidget.isVisible()` zwraca
efektywną widoczność (fałsz dla niebieżącej strony stosu), do tego geometria,
`visibleRegion()`, z-order rodzeństwa. Dostęp z zewnątrz procesu:

- **endpoint introspekcyjny KD** (D-Bus/socket za flagą testową): zserializowane
  drzewo z flagami widoczności, "który kafel ma focus", "czy Home Menu jest
  bieżącym widokiem" — odpowiednik `document.querySelector`,
- **GammaRay** (KDAB) — "DevTools dla Qt", do ręcznej diagnozy.

### Warstwa 2 — scena kompozytora (własne i cudze okna)

- **Hyprland**: `hyprctl layers -j` (powierzchnie layer-shell per output i
  warstwa) + `hyprctl clients -j` (okna, fullscreen, workspace). Protokół
  layer-shell gwarantuje: warstwa *overlay* renderuje się nad fullscreenem —
  wnioskowanie "zmapowany na overlay ⇒ nad grą" jest dedukcyjnie pewne.
- **Sway**: `get_tree` ma pole `visible` dla toplevelów, ale layer-shell prawie
  nie jest eksponowany — najpłytsza introspekcja z czwórki.
- **KWin**: API skryptowe (JS przez D-Bus) — `workspace.stackingOrder` z
  geometriami; okluzję liczymy sami (od góry stosu odejmujemy nieprzezroczyste
  prostokąty). Eventy `windowAdded`/`windowRemoved` do watchera.
- **GNOME**: bundlowane rozszerzenie Shella ma dostęp do drzewa aktorów
  Cluttera — to *dosłownie scene graph kompozytora* (`global.get_window_actors()`,
  per aktor: visible, opacity, kolejność malowania). Najgłębsza introspekcja;
  rozszerzenie może wystawić testowy endpoint D-Bus.

### Warstwa 3 — protokół (kompozytor przyznaje, że narysował)

- **wp_presentation (presentation-time)**: klient dostaje per klatka `presented`
  (z timestampem vsynca) albo `discarded`. KD może wiedzieć od kompozytora, że
  klatka np. Home Menu faktycznie trafiła na ekran. Do wpięcia w endpoint
  introspekcyjny.
- Słabsze sygnały: frame callbacki (`wl_surface.frame` — dławione dla
  niewidocznych powierzchni), stan `suspended` w nowszym xdg-shell (tylko
  toplevele, nie layer-shell).

### Warstwa 4 — piksele (ostatnia linia, nie podstawa)

Strukturalnie nie stwierdzimy: (a) że inna powierzchnia *na tej samej warstwie*
nie weszła na wierzch (na Swayu w ogóle, gdzie indziej policzalne), (b) że
piksele wyszły z GPU niesknocone (alpha=0, czarna klatka), (c) **co jest na
klatkach cudzego okna** — treść gry istnieje tylko jako piksele.

Gdy potrzebne: capture z kompozytora (musi obejmować layer-shell!) — `grim` /
`wf-recorder` (wlroots), `spectacle -b -n -o` / D-Bus `org.kde.KWin.ScreenShot2`
(KDE), D-Bus Shella (GNOME); uniwersalnie strumień PipeWire przez portal
ScreenCast. Asercje: template matching OpenCV (`cv2.matchTemplate`, próg
~0.95) na referencyjnych wycinkach trzymanych w repo (model needles z openQA);
dla rzeczy ulotnych (splashe) — nagranie całego scenariusza i analiza klatek po
fakcie ("istnieje klatka, w której needle matchuje"), przy okazji artefakt do
debugowania każdego faila. Opcjonalnie model z wizją (API) do rozmytych asercji.

Przed budową: sanity check na każdym kompozytorze, że capture na pewno łapie
nasze warstwy (KD nad grą + ręczny `grim`/Spectacle).

## Aplikacje cudze (Steam, gry przez Proton/Wine)

Żadnego DOM-u: gra to czarna skrzynka commitująca bufory. Sufit dociekania to
warstwa 2 + stos graficzny. Dostępne sygnały strukturalne:

- **tożsamość i cykl życia okna**: toplevel z `app_id` — gry steamowe mają
  `steam_app_<appid>` (KCD: `steam_app_379430`); tytuł, geometria, fullscreen.
  Eventowo: **wlr-foreign-toplevel-management** (wlroots), sygnały KWin
  scripting (KDE), sygnały Mutter/Clutter w rozszerzeniu (GNOME),
- **dowód renderowania**: MangoHud (już zintegrowany w KD) siedzi w pętli
  renderowania gry i loguje FPS do CSV (`MANGOHUD_LOG`) — asercja "gra renderuje
  >0 FPS od ≥5 s" bez jednego piksela. Dla fullscreenowego ekranu gry to
  wystarcza w zupełności,
- **rurociąg uruchomienia**: drzewo procesów (reaper → proton → wine),
  `~/.steam/registry.vdf` (RunningAppID), logi Steama, `PROTON_LOG=1` — każdy
  etap faila (KD nie odpalił Steama / Steam nie odpalił gry / gra bez okna) ma
  inny strukturalny podpis.

Sterowanie Steamem padem (nawigacja po Big Picture) to najkruchszy krok —
zależy od stanu biblioteki. Podstawowy scenariusz odpala grę przez
`steam steam://rungameid/<appid>`; wariant "padem przez BPM" jako osobny,
opcjonalny scenariusz.

## Case: splash KCD / RED Launcher — właściwa asercja

Splash to krótkotrwały, niefullscreenowy toplevel: mapuje się nad Steamem, żyje
chwilę, znika, ekran przejmuje fullscreen gry. Dwie pułapki:

1. "Toplevel splasha się zmapował" to **za słaba asercja** — będzie prawdą
   nawet, gdy bug wróci i KD go przykryje. Właściwa: *"splash zmapowany ORAZ w
   porządku kompozycji nie ma nad nim powierzchni KD"* (czyli `cede_depth`
   zadziałał). Strukturalnie sprawdzalne: GNOME (kolejność aktorów), KDE
   (`stackingOrder`), Hyprland (`layers` + `clients`); Sway — tylko piksele
   albo krok pominięty.
2. Okno żyje krótko ⇒ watcher musi być **eventowy (subskrypcja sygnałów), nie
   pollingowy** — polling co sekundę może splash przegapić. To przesądza
   architekturę.

## Architektura harnessu

- **Driver wejścia**: wirtualny gamepad przez `evdev.UInput` — KD widzi go jak
  prawdziwy pad. Zero współrzędnych ekranu; precyzyjna kontrola czasu wciśnięcia
  (test progu przytrzymania Home >1 s i kontrprzykład 0,5 s).
- **Watcher okien/warstw**: eventowy, per kompozytor, za wspólnym interfejsem
  (analogicznie do adapterów w `src/infrastructure/`). API w stylu
  `windows.wait_for(app_id=..., fullscreen=True, timeout=40)`,
  `windows.assert_above(splash, kd_surfaces)`.
- **Introspekcja KD**: endpoint D-Bus/socket za flagą testową (drzewo widoków,
  focus, widoczność) + presentation feedback.
- **Screen** (opcjonalny): nagrywanie scenariusza + needle matching; artefakt
  przy failu.
- **Warstwa scenariuszy**: `pytest-bdd` (integruje się z istniejącym pytest,
  te same fixtures) — scenariusze z `test_scenarios.md` przepisują się ~1:1
  na Gherkin.

### Przykładowy scenariusz (kroki w trzech smakach)

```gherkin
Scenariusz: uruchomienie KCD przez Steama i powrót Home Menu
  Zakładając widoczny pulpit KD                          # introspekcja KD
  Gdy wciskam A na kaflu Steam                           # uinput
  Wtedy okno Steama przechodzi w fullscreen w ciągu 30 s # watcher
  Oraz proces Steam istnieje                             # proc
  Gdy uruchamiam grę steam://rungameid/379430            # shell
  Wtedy pojawia się niefullscreenowy toplevel steam_app_379430  # watcher
  Oraz nad splashem nie ma powierzchni KD                # watcher (stacking)
  Wtedy toplevel steam_app_379430 przechodzi w fullscreen w ciągu 60 s
  Oraz gra renderuje >0 FPS przez 5 s                    # MangoHud
  Gdy przytrzymuję Home przez 1,2 s                      # uinput
  Wtedy Home Menu jest widoczne nad grą                  # introspekcja + stacking
```

## Plan PoC

1. Eventowy watcher toplevelów dla jednego kompozytora (KDE albo GNOME — tam
   były bugi i tam introspekcja stackingu jest pełna).
2. Wirtualny pad (`evdev.UInput`) + smoke test: start KD, nawigacja po kaflach.
3. Scenariusz KCD jak wyżej, z asercją względnego porządku splash/KD.
4. Dopiero po weryfikacji: warstwa pytest-bdd, endpoint introspekcyjny KD,
   pozostałe kompozytory, opcjonalny Screen.
