# Europaspiel

Lern-App für die Geografie-/GeWi-Arbeit „Europa“: Länder und Hauptstädte, Meere, Gebirge, Flüsse.
Läuft im Browser, ohne Server und ohne Anmeldung. Der Fortschritt wird im `localStorage` gespeichert.

**Spielen:** `Europaspiel.html` (im Hauptordner) im Browser öffnen.

## Aufbau
- `daten/*.json` – alle Lerninhalte (Länder, weitere Länder, Meere, Gebirge, Flüsse). Neue Einträge einfach ergänzen.
  Gebirge und Flüsse haben eine vereinfachte Linie `linie` als `[Längengrad, Breitengrad]`-Punkte.
- `karte/europa.json` – vorberechnete Europakarte (Natural Earth, gemeinfrei, über world-atlas), Lambert-Projektion.
- `src/app.html` – Oberfläche und Spiellogik (reines HTML/CSS/JS).
- `build.js` – baut aus `src/app.html` + JSON die fertige Datei: `node europaspiel/build.js`
- `tools/karte-erzeugen.js` – erzeugt `karte/europa.json` neu.
