"""
Kernlogik der PDF-zu-Sibelius-Umwandlung.

Ablauf:
1. PDF-Seiten als Vorschaubilder rendern (fuer die Seitenauswahl im Browser).
2. Audiveris im Batch-Modus auf den ausgewaehlten Seiten laufen lassen
   (Notenerkennung / OMR) und nach MusicXML exportieren.
3. Bekannten Audiveris-Exportfehler korrigieren: Die Datei deklariert die
   ungueltige Versionsnummer "4.0.3" statt der gueltigen MusicXML-Version
   "4.0". Manche Programme (u.a. Sibelius) erkennen "4.0.3" nicht und
   fallen auf einen alten/eingeschraenkten Import-Modus zurueck.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


class PipelineError(RuntimeError):
    """Fehler in einem Schritt der Umwandlung, mit Nutzer-lesbarer Meldung."""


# ---------------------------------------------------------------------------
# Audiveris finden
# ---------------------------------------------------------------------------

_CANDIDATE_PATHS = [
    "/opt/audiveris/bin/Audiveris",  # Linux .deb Installer
    "/usr/local/bin/Audiveris",
    "/Applications/Audiveris.app/Contents/MacOS/Audiveris",  # macOS
    r"C:\Program Files\Audiveris\Audiveris.exe",  # Windows
]


def find_audiveris() -> str:
    """Liefert den Pfad zur Audiveris-Programmdatei oder wirft PipelineError."""
    env_path = os.environ.get("AUDIVERIS_BIN")
    if env_path and Path(env_path).exists():
        return env_path

    which = shutil.which("Audiveris") or shutil.which("audiveris")
    if which:
        return which

    for candidate in _CANDIDATE_PATHS:
        if Path(candidate).exists():
            return candidate

    raise PipelineError(
        "Audiveris wurde nicht gefunden. Bitte installieren (siehe README.md) "
        "oder den Pfad zur ausfuehrbaren Datei in der Umgebungsvariable "
        "AUDIVERIS_BIN angeben."
    )


# ---------------------------------------------------------------------------
# Seiten-Vorschau
# ---------------------------------------------------------------------------

@dataclass
class PagePreview:
    number: int  # 1-basiert, wie in Audiveris' -sheets Option
    image_path: Path


def render_page_previews(pdf_path: Path, out_dir: Path, dpi: int = 90) -> list[PagePreview]:
    """Rendert jede PDF-Seite als PNG, damit der Nutzer Nicht-Noten-Seiten
    (Titelblatt, Impressum, ...) abwaehlen kann."""
    import pymupdf as fitz

    out_dir.mkdir(parents=True, exist_ok=True)
    previews = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            img_path = out_dir / f"page-{i:03d}.png"
            pix.save(img_path)
            previews.append(PagePreview(number=i, image_path=img_path))
    finally:
        doc.close()
    return previews


# ---------------------------------------------------------------------------
# Audiveris-Lauf
# ---------------------------------------------------------------------------

@dataclass
class TranscriptionResult:
    mxl_path: Path
    log_path: Path
    warnings: list[str] = field(default_factory=list)


def _sheets_arg(pages: list[int]) -> str:
    """Formt eine Liste von Seitenzahlen in Audiveris' Range-Syntax,
    z.B. [2,3,4,7] -> '2-4 7'."""
    pages = sorted(set(pages))
    ranges = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
            continue
        ranges.append((start, prev))
        start = prev = p
    ranges.append((start, prev))
    return " ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in ranges)


def run_audiveris(
    pdf_path: Path,
    included_pages: list[int],
    work_dir: Path,
    log_callback=None,
) -> TranscriptionResult:
    """Fuehrt Audiveris im Batch-Modus aus und exportiert MusicXML.

    log_callback(line: str) wird pro Log-Zeile aufgerufen (fuer Live-Fortschritt).
    """
    if not included_pages:
        raise PipelineError("Keine Seiten zur Verarbeitung ausgewaehlt.")

    audiveris_bin = find_audiveris()
    output_dir = work_dir / "audiveris_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        audiveris_bin,
        "-batch",
        "-sheets",
        *_sheets_arg(included_pages).split(" "),
        "-transcribe",
        "-export",
        "-output",
        str(output_dir),
        str(pdf_path),
    ]

    log_path = work_dir / "audiveris.log"
    with open(log_path, "w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            if log_callback:
                log_callback(line.rstrip("\n"))
        returncode = process.wait()

    mxl_candidates = list(output_dir.glob("*.mxl"))
    if returncode != 0 or not mxl_candidates:
        tail = _tail(log_path, 40)
        raise PipelineError(
            "Audiveris konnte die Partitur nicht transkribieren "
            f"(Exit-Code {returncode}). Ende des Logs:\n{tail}"
        )

    warnings = _collect_warnings(log_path)
    return TranscriptionResult(mxl_path=mxl_candidates[0], log_path=log_path, warnings=warnings)


def _tail(path: Path, n: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


def _collect_warnings(log_path: Path) -> list[str]:
    interesting = []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if "flagged as invalid" in line or "No target duration" in line:
            interesting.append(line.strip())
    return interesting


# ---------------------------------------------------------------------------
# MusicXML-Versionsfix (fuer Sibelius-Kompatibilitaet)
# ---------------------------------------------------------------------------

_BAD_VERSION_RE = re.compile(r"MusicXML 4\.0\.3")
_BAD_ATTR_RE = re.compile(r'(<score-partwise\s+version=")4\.0\.3(")')


def fix_musicxml_version(mxl_path: Path, fixed_path: Path) -> bool:
    """Korrigiert die von Audiveris faelschlich vergebene MusicXML-Version
    "4.0.3" (kein gueltiger Standardwert) zu "4.0". Gibt zurueck, ob eine
    Korrektur noetig war."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(mxl_path) as zf:
            zf.extractall(tmp_dir)

        xml_candidates = list(tmp_dir.glob("*.xml")) + list(tmp_dir.glob("**/score.xml"))
        xml_candidates = [p for p in xml_candidates if "META-INF" not in str(p)]
        if not xml_candidates:
            raise PipelineError("Keine score.xml im MusicXML-Container gefunden.")
        xml_path = xml_candidates[0]

        content = xml_path.read_text(encoding="utf-8")
        patched = _BAD_VERSION_RE.sub("MusicXML 4.0", content)
        patched = _BAD_ATTR_RE.sub(r"\g<1>4.0\g<2>", patched)
        changed = patched != content
        xml_path.write_text(patched, encoding="utf-8")

        fixed_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(fixed_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
            for file in tmp_dir.rglob("*"):
                if file.is_file():
                    zf_out.write(file, file.relative_to(tmp_dir))

    return changed


# ---------------------------------------------------------------------------
# Gesamtpipeline
# ---------------------------------------------------------------------------

def convert(
    pdf_path: Path,
    included_pages: list[int],
    work_dir: Path,
    log_callback=None,
) -> tuple[Path, list[str]]:
    """Fuehrt die komplette Umwandlung durch und liefert
    (Pfad zur finalen .mxl-Datei, Liste von Warnungen)."""
    result = run_audiveris(pdf_path, included_pages, work_dir, log_callback)
    final_path = work_dir / "ergebnis.mxl"
    version_fixed = fix_musicxml_version(result.mxl_path, final_path)
    if log_callback:
        if version_fixed:
            log_callback("MusicXML-Versionsstring korrigiert (4.0.3 -> 4.0) fuer Sibelius-Kompatibilitaet.")
        log_callback("Fertig.")
    return final_path, result.warnings
