// Baut Europaspiel.html: fügt die JSON-Dateien aus daten/ und karte/ in src/app.html ein.
// Aufruf: node europaspiel/build.js
const fs = require('fs'), path = require('path');
const dir = __dirname, j = f => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
const daten = {
  laender: j('daten/laender.json'), weitere: j('daten/weitere-laender.json'),
  meere: j('daten/meere.json'), gebirge: j('daten/gebirge.json'), fluesse: j('daten/fluesse.json'),
  karte: j('karte/europa.json')
};
const json = JSON.stringify(daten).replace(/</g, '\\u003c');
const html = fs.readFileSync(path.join(dir, 'src/app.html'), 'utf8')
  .replace('<!--DATEN-->', `<script type="application/json" id="daten">${json}</script>`);
const voll = '<!doctype html>\n<html lang="de">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + html.replace('</style>', '</style>\n</head>\n<body>') + '\n</body>\n</html>\n';
fs.writeFileSync(path.join(dir, '..', 'Europaspiel.html'), voll);
if (process.argv[2]) fs.writeFileSync(process.argv[2], html); // Variante ohne Rahmen (für Artifact)
console.log('Europaspiel.html geschrieben,', Math.round(html.length / 1024), 'KB');
