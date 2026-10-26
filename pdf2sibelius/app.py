"""
PDF -> Sibelius (MusicXML) - lokale Web-Oberflaeche.

Start:
    python app.py
Dann im Browser: http://127.0.0.1:5000

Siehe README.md fuer Voraussetzungen (Java + Audiveris).
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
)

import instruments
import pipeline

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

# job_id -> {status, log: [str], pages: [PagePreview], error, download_ready, warnings}
JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/upload")
def upload():
    file = request.files.get("pdf")
    if not file or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Bitte eine PDF-Datei auswaehlen."}), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = _job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = job_dir / "input.pdf"
    file.save(pdf_path)

    try:
        previews = pipeline.render_page_previews(pdf_path, job_dir / "previews")
    except Exception as exc:  # noqa: BLE001 - dem Nutzer die genaue Ursache zeigen
        return jsonify({"error": f"PDF konnte nicht gelesen werden: {exc}"}), 400

    with _LOCK:
        JOBS[job_id] = {
            "status": "awaiting_pages",
            "log": [],
            "warnings": [],
            "error": None,
            "download_ready": False,
            "num_pages": len(previews),
        }

    return jsonify(
        {
            "job_id": job_id,
            "pages": [
                {"number": p.number, "thumb_url": f"/thumb/{job_id}/{p.image_path.name}"}
                for p in previews
            ],
        }
    )


@app.get("/thumb/<job_id>/<filename>")
def thumb(job_id: str, filename: str):
    return send_from_directory(_job_dir(job_id) / "previews", filename)


@app.post("/convert/<job_id>")
def convert(job_id: str):
    job_dir = _job_dir(job_id)
    pdf_path = job_dir / "input.pdf"
    if job_id not in JOBS or not pdf_path.exists():
        return jsonify({"error": "Unbekannter Auftrag. Bitte PDF erneut hochladen."}), 404

    data = request.get_json(force=True)
    included_pages = sorted({int(p) for p in data.get("pages", [])})
    if not included_pages:
        return jsonify({"error": "Bitte mindestens eine Seite auswaehlen."}), 400

    with _LOCK:
        JOBS[job_id].update(status="running", log=[], error=None, download_ready=False)

    def log_callback(line: str) -> None:
        with _LOCK:
            JOBS[job_id]["log"].append(line)
            # Log nicht unbegrenzt wachsen lassen
            if len(JOBS[job_id]["log"]) > 2000:
                JOBS[job_id]["log"] = JOBS[job_id]["log"][-2000:]

    def worker() -> None:
        try:
            final_path, warnings = pipeline.convert(
                pdf_path, included_pages, job_dir, log_callback=log_callback
            )
            parts = pipeline.list_parts(final_path)
            with _LOCK:
                JOBS[job_id].update(
                    status="awaiting_instruments",
                    intermediate_path=str(final_path),
                    result_path=str(final_path),
                    download_ready=True,
                    warnings=warnings,
                    parts=[{"index": p.index, "current_name": p.current_name} for p in parts],
                )
        except pipeline.PipelineError as exc:
            with _LOCK:
                JOBS[job_id].update(status="error", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            with _LOCK:
                JOBS[job_id].update(status="error", error=f"Unerwarteter Fehler: {exc}")

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "running"})


@app.get("/status/<job_id>")
def status(job_id: str):
    with _LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Unbekannter Auftrag."}), 404
        return jsonify(
            {
                "status": job["status"],
                "log_tail": job["log"][-60:],
                "error": job.get("error"),
                "download_ready": job.get("download_ready", False),
                "warnings": job.get("warnings", []),
                "parts": job.get("parts", []),
            }
        )


@app.get("/instrument-options")
def instrument_options():
    return jsonify(
        [
            {"key": key, "label": t.label}
            for key, t in instruments.TRANSPOSITIONS.items()
        ]
    )


@app.post("/assign/<job_id>")
def assign(job_id: str):
    with _LOCK:
        job = JOBS.get(job_id)
    if not job or not job.get("intermediate_path"):
        return jsonify({"error": "Kein Zwischenergebnis fuer diesen Auftrag vorhanden."}), 404

    data = request.get_json(force=True)
    raw_assignments = data.get("assignments", [])

    assignments = []
    for a in raw_assignments:
        key = a.get("transposition_key", "concert_pitch")
        if key not in instruments.TRANSPOSITIONS:
            return jsonify({"error": f"Unbekannte Instrument-Transposition: {key}"}), 400
        name = (a.get("name") or "").strip()
        if not name:
            continue
        assignments.append(
            instruments.PartAssignment(
                part_index=int(a["index"]), instrument_name=name, transposition_key=key
            )
        )

    job_dir = _job_dir(job_id)
    final_path = job_dir / "ergebnis_final.mxl"
    try:
        pipeline.apply_instrument_assignments(
            Path(job["intermediate_path"]), assignments, final_path
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Instrumentenzuweisung fehlgeschlagen: {exc}"}), 500

    with _LOCK:
        JOBS[job_id].update(status="done", result_path=str(final_path), download_ready=True)

    return jsonify({"status": "done"})


@app.get("/download/<job_id>")
def download(job_id: str):
    with _LOCK:
        job = JOBS.get(job_id)
    if not job or not job.get("download_ready"):
        return jsonify({"error": "Ergebnis noch nicht bereit."}), 404
    return send_file(job["result_path"], as_attachment=True, download_name="partitur.mxl")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
