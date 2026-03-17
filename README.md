# Spadajace kulki

Arcade'owa gierka z kamerka: projekt ma teraz dwie wersje:

- pokazowa wersja webowa z wpisywaniem imienia i tabela wynikow,
- starszy prototyp desktopowy w Pythonie z OpenCV i MediaPipe.

## Wymagania

- macOS z kamera
- Python 3.13+
- Node.js 25+

## Wersja pokazowa Web

To jest teraz rekomendowana wersja na dni otwarte.

### Instalacja

```bash
npm install
```

### Uruchomienie

```bash
npm run dev
```

Po uruchomieniu otworz adres podany przez Vite, pozwol przegladarce na dostep do kamery i wpisz imie gracza.

### Co dostajesz

- ekran startowy z polem na imie,
- czytelny, pokazowy UI pod kiosk,
- gre sterowana kamerka bez opuszczania przegladarki,
- lokalna tabele wynikow zapisywana w `localStorage`,
- przycisk do szybkiego restartu kolejnych graczy.

### Build produkcyjny

```bash
npm run build
```

## Wersja Python

To zostalo jako fallback i starszy prototyp.

### Instalacja

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Uruchomienie

```bash
python3 main.py
```

Przy pierwszym uruchomieniu program automatycznie pobierze modele MediaPipe do katalogu `models/`.

Jesli domyslna kamera nie zadziala:

```bash
python3 main.py --camera 1
```

Jesli obraz jest czarny albo macOS wybiera nie ta kamere co trzeba:

```bash
python3 main.py --list-cameras
```

To wypisze kilka indeksow kamer i podpowie, ktore daja sensowny obraz.

Jesli macOS poprosi o dostep do kamery, zezwol Terminalowi albo aplikacji Codex w ustawieniach systemowych.

## Sterowanie

- `R` - restart rundy
- `Q` - wyjscie
- `ESC` - wyjscie

## Jak dziala gra

- Wejdz do kadru i odczekaj chwile, a gra odpali 3-sekundowe odliczanie.
- Runda trwa 60 sekund i ma 3 fazy rosnacej trudnosci.
- Dotykaj obiektow dlonmi albo palcami, buduj combo i poprawiaj rekord.
- Gdy osoba zniknie z kadru na dluzej, gra przejdzie w pauze i wznowi sie po powrocie.
- Po koncu rundy zobaczysz wynik, najlepsze combo i podsumowanie trafionych obiektow specjalnych.

## Typy obiektow

- `normal` - podstawowy punktowany obiekt
- `gold` - daje wiecej punktow
- `slow-mo` - daje punkty i chwilowo spowalnia tempo gry
- `bomb` - odejmuje punkty i resetuje combo

## Rekordy

W wersji webowej wyniki sa zapisywane lokalnie w przegladarce.

W wersji Python statystyki sa zapisywane lokalnie w `data/stats.json`:

- `high_score`
- `best_combo`
- `games_played`
- `last_score`

## Testy

Automatyczne testy logiki gry:

```bash
python3 -m unittest discover -s tests -v
```
