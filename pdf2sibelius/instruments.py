"""
Zuordnung von Instrumenten zu ihrer MusicXML-Transposition.

Hintergrund: Bei transponierenden Instrumenten (z.B. B-Klarinette, Es-Alt-
saxophon, Horn in F) stehen in der gedruckten Partitur die *geschriebenen*
Toene, nicht die klingenden. Audiveris liest genau diese geschriebenen
Toene vom Notenbild ab - das ist korrekt. Es traegt aber kein <transpose>-
Element in die exportierte MusicXML ein, weil es den Instrumentennamen
nicht zuverlaessig erkennt (meist fehlende OCR-Sprachdaten). Ohne dieses
Element weiss Sibelius (und jedes andere Programm) nicht, dass die Stimme
zu einem transponierenden Instrument gehoert, und behandelt die Toene
faelschlich als klingende (Konzert-)Toene.

Dieses Modul traegt nachtraeglich die passenden <transpose>-Elemente und
Instrumentnamen ein, OHNE die bereits erkannten Notenwerte zu veraendern.
Massgeblich ist dabei immer die gedruckte Originalpartitur: man muss dort
nachschauen, welches Instrument zu welcher Notenzeile gehoert
(Instrumentnamen stehen links neben jedem System).

MusicXML-Konvention (siehe MusicXML-Spezifikation, <transpose>):
    klingender Ton = geschriebener Ton + chromatic-Halbtonschritte
Beispiel: B-Trompete -> chromatic = -2 (zwei Halbtoene tiefer als notiert).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Transposition:
    label: str          # Anzeigename fuer die Auswahl in der UI
    abbreviation: str    # kurzer Name fuer part-abbreviation
    chromatic: int        # Halbtonschritte: klingend = geschrieben + chromatic
    diatonic: int          # diatonische Schritte (fuer saubere Notation des Intervalls)


# Gaengige transponierende Blas-/Holzblasinstrumente. chromatic/diatonic
# nach MusicXML-Konvention (klingend = geschrieben + Wert).
TRANSPOSITIONS: dict[str, Transposition] = {
    "concert_pitch": Transposition("In C (nicht transponierend)", "", 0, 0),
    "clarinet_bb": Transposition("Klarinette in B", "Kl.", -2, -1),
    "clarinet_eb": Transposition("Klarinette in Es", "Kl. Es", 3, 2),
    "trumpet_bb": Transposition("Trompete in B", "Trp.", -2, -1),
    "flugelhorn_bb": Transposition("Flügelhorn in B", "Flh.", -2, -1),
    "horn_f": Transposition("Horn in F", "Hr.", -7, -4),
    "alto_sax_eb": Transposition("Altsaxophon in Es", "A-Sax", -9, -5),
    "tenor_sax_bb": Transposition("Tenorsaxophon in B", "T-Sax", -14, -8),
    "baritone_sax_eb": Transposition("Baritonsaxophon in Es", "B-Sax", -21, -12),
    "tenorhorn_bb": Transposition("Tenorhorn in B (Violinschlüssel)", "Thn.", -14, -8),
    "baritone_bb": Transposition("Bariton/Euphonium in B (Violinschlüssel)", "Bar.", -14, -8),
    "piccolo_trumpet_bb": Transposition("Piccolotrompete in B", "Picc.Tp.", -2, -1),
}


@dataclass
class PartAssignment:
    part_index: int          # 1-basiert, Reihenfolge wie in der Partitur / wie von Audiveris exportiert
    instrument_name: str      # anzuzeigender Name, z.B. "1. B-Klarinette"
    transposition_key: str    # Schluessel aus TRANSPOSITIONS


_MUSICXML_NS = ""  # Audiveris-Export nutzt kein Namespace-Prefix


def apply_instrument_assignments(
    xml_path: Path, assignments: list[PartAssignment], out_path: Path | None = None
) -> None:
    """Traegt Instrumentnamen und Transposition in eine score-partwise
    MusicXML-Datei ein und schreibt das Ergebnis nach out_path (Standard:
    xml_path, also in place). Die Notenwerte (<pitch>) werden nicht
    angefasst - nur Metadaten, die Programmen wie Sibelius sagen, wie sie
    die bereits vorhandenen (geschriebenen) Toene zu interpretieren haben.
    """
    doctype = _extract_doctype(xml_path)

    tree = ET.parse(xml_path)
    root = tree.getroot()

    part_list = root.find("part-list")
    if part_list is None:
        raise ValueError("Keine <part-list> in der MusicXML-Datei gefunden.")

    score_parts = part_list.findall("score-part")
    parts = root.findall("part")

    by_index = {a.part_index: a for a in assignments}

    for i, (score_part, part_el) in enumerate(zip(score_parts, parts), start=1):
        assignment = by_index.get(i)
        if assignment is None:
            continue

        _set_part_names(score_part, assignment.instrument_name)
        _set_transpose(part_el, TRANSPOSITIONS[assignment.transposition_key])

    target = out_path or xml_path
    tree.write(target, encoding="UTF-8", xml_declaration=True)
    if doctype:
        _reinsert_doctype(target, doctype)


def _extract_doctype(xml_path: Path) -> str | None:
    """ElementTree kennt keine DOCTYPE-Deklarationen und wuerde sie beim
    Schreiben stillschweigend verwerfen. Wir sichern die Original-Zeile,
    um sie nach dem Schreiben wieder einzufuegen (MusicXML-Leser wie
    Sibelius erwarten sie)."""
    with open(xml_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("<!DOCTYPE"):
                return stripped
            if stripped.startswith("<") and not stripped.startswith("<?xml"):
                break  # erstes echtes Element erreicht, keine DOCTYPE-Zeile vorhanden
    return None


def _reinsert_doctype(xml_path: Path, doctype: str) -> None:
    content = xml_path.read_text(encoding="utf-8")
    first_newline = content.index("\n") + 1
    xml_decl, rest = content[:first_newline], content[first_newline:]
    xml_path.write_text(xml_decl + doctype + "\n" + rest, encoding="utf-8")


def _set_part_names(score_part: ET.Element, instrument_name: str) -> None:
    name_el = score_part.find("part-name")
    if name_el is None:
        name_el = ET.SubElement(score_part, "part-name")
    name_el.text = instrument_name

    abbrev_el = score_part.find("part-abbreviation")
    if abbrev_el is None:
        abbrev_el = ET.SubElement(score_part, "part-abbreviation")
    abbrev_el.text = instrument_name


def _set_transpose(part_el: ET.Element, transposition: Transposition) -> None:
    first_measure = part_el.find("measure")
    if first_measure is None:
        return

    attributes = first_measure.find("attributes")
    if attributes is None:
        attributes = ET.SubElement(first_measure, "attributes")
        first_measure.insert(0, attributes)

    # Vorhandenes <transpose> entfernen, falls Audiveris doch eins gesetzt hat
    old = attributes.find("transpose")
    if old is not None:
        attributes.remove(old)

    if transposition.chromatic == 0 and transposition.diatonic == 0:
        return  # nicht transponierendes Instrument -> kein <transpose> noetig

    transpose_el = ET.Element("transpose")
    diatonic_el = ET.SubElement(transpose_el, "diatonic")
    diatonic_el.text = str(transposition.diatonic)
    chromatic_el = ET.SubElement(transpose_el, "chromatic")
    chromatic_el.text = str(transposition.chromatic)

    # Schema-Reihenfolge innerhalb <attributes>: ... clef*, staff-details*,
    # transpose?, ... Wir fuegen nach dem letzten <clef> ein (oder am Ende,
    # falls kein clef vorhanden ist).
    clefs = attributes.findall("clef")
    if clefs:
        last_clef = clefs[-1]
        idx = list(attributes).index(last_clef)
        attributes.insert(idx + 1, transpose_el)
    else:
        attributes.append(transpose_el)
