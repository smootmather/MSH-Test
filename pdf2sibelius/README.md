# PDF &rarr; Sibelius

Lokale Web-App, die eine PDF-Partitur per Noten-Erkennung (OMR) in eine
MusicXML-Datei (`.mxl`) umwandelt, die sich direkt in Sibelius importieren
lässt (*Datei &rarr; Öffnen*).

Die eigentliche Erkennung übernimmt [Audiveris](https://github.com/Audiveris/audiveris)
(Open Source). Diese App ist eine komfortable Oberfläche darum herum und
behebt zusätzlich einen bekannten Audiveris-Exportfehler: Die exportierte
Datei deklariert die ungültige MusicXML-Version `4.0.3` statt `4.0`, was in
Sibelius zur Meldung "alte Version des MusicXML-Formats" führen kann. Die
App korrigiert das automatisch.

## Voraussetzungen

1. **Java** (mind. Java 17, empfohlen 21+) – meist schon vorhanden. Prüfen mit:
   ```
   java -version
   ```
2. **Audiveris** (Version 5.5 oder neuer, empfohlen 5.11+) – Installer für
   Windows (`.msi`), macOS (`.dmg`) oder Linux (`.deb`) von der
   [Releases-Seite](https://github.com/Audiveris/audiveris/releases)
   herunterladen und installieren.
   - Linux: `sudo apt install ./Audiveris-<version>-ubuntuXX.XX-x86_64.deb`
     installiert nach `/opt/audiveris/` (wird automatisch gefunden).
   - Windows/macOS: Standard-Installationspfad wird automatisch erkannt.
     Falls nicht gefunden, den Pfad zur ausführbaren Datei in der
     Umgebungsvariable `AUDIVERIS_BIN` setzen.
3. **Python 3.10+**

## Installation

```bash
cd pdf2sibelius
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Starten

```bash
python app.py
```

Dann im Browser öffnen: <http://127.0.0.1:5000>

## Ablauf

1. PDF hochladen.
2. Die App zeigt jede Seite als Vorschaubild. Seiten ohne Notenlinien
   (Titelblatt, Impressum, Inhaltsverzeichnis) abwählen – eine einzige
   solche Seite lässt sonst die komplette Erkennung fehlschlagen.
   (Seite 1 ist standardmäßig vorab abgewählt, da meist ein Titelblatt.)
3. "Umwandlung starten" klicken und den Fortschritt im Log verfolgen
   (bei größeren Partituren mehrere Minuten).
4. Ergebnis herunterladen und in Sibelius öffnen.

## Grenzen der Noten-Erkennung (OMR)

Automatische Noten-Erkennung ist nie fehlerfrei – das gilt für jede
OMR-Software, nicht nur für dieses Tool. Nach dem Import in Sibelius bitte
insbesondere prüfen:

- **Rhythmische Details wie Triolen** werden nicht immer erkannt,
  besonders in dicht gesetzten Partituren mit vielen Stimmen gleichzeitig.
- **Instrumentennamen** werden oft nicht übernommen, wenn Audiveris keine
  passenden OCR-Sprachdaten geladen hat (Stimmen heißen dann generisch
  "Voice 1", "Voice 2", ...). Reihenfolge entspricht der Reihenfolge im PDF.
- Allgemein: Töne, Bindebögen, Dynamik-Zeichen und Taktarten gegen das
  Original gegenprüfen, vor allem bei dicht gedruckten Passagen.

Die App zeigt nach der Umwandlung eine Warnliste mit Stellen an, die
Audiveris selbst als unsicher markiert hat (z.B. Takte mit unklarer
Taktart) – das ist ein guter erster Anhaltspunkt, wo man in Sibelius genauer
hinschauen sollte.

## Projektstruktur

```
pdf2sibelius/
├── app.py          Flask-Webserver (Routen, Job-Verwaltung)
├── pipeline.py      Kernlogik: Audiveris aufrufen, MusicXML-Fix, PDF-Vorschau
├── templates/
│   └── index.html   Oberfläche (Upload, Seitenauswahl, Fortschritt)
├── static/
│   ├── style.css
│   └── script.js
└── requirements.txt
```

## Fehlerbehebung

- **"Audiveris wurde nicht gefunden"**: Audiveris installieren (siehe oben)
  oder `AUDIVERIS_BIN` auf die ausführbare Datei setzen.
- **Umwandlung schlägt fehl / bricht komplett ab**: Meist eine Seite ohne
  Notenlinien wurde nicht abgewählt. Log-Ausgabe prüfen (dort steht z.B.
  `flagged as invalid` für die betroffene Seite).
- Diese App läuft nur lokal auf dem eigenen Rechner (kein öffentlicher
  Server) – die hochgeladene PDF verlässt den eigenen Rechner nicht.
