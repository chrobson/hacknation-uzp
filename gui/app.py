"""Lokalny interfejs WWW dla Odwołania2JSON.

Każdy przebieg ("run") to osobny katalog w gui/.runs/<id>/ z układem identycznym jak w CLI:
    input/<sprawa>/*.pdf  ->  output/<sprawa>/<nazwa>.json  +  evidence/<sprawa>/<nazwa>.evidence.json
Pipeline uruchamiamy jako podproces (`python main.py --input ... --output ... --evidence ...`), czyli dokładnie
tak, jak robi to start.sh. Dzięki temu GUI nie dubluje logiki ekstrakcji, a limit czasu na dokument (SIGALRM)
działa w głównym wątku procesu potomnego tak samo jak w trybie wsadowym.
"""

from __future__ import annotations

import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

GUI_DIR = Path(__file__).resolve().parent
ROOT = GUI_DIR.parent
STATIC_DIR = GUI_DIR / "static"
RUNS_DIR = Path(os.environ.get("ODW_GUI_RUNS", GUI_DIR / ".runs")).resolve()
PYTHON = os.environ.get("ODW_PYTHON", sys.executable)
KEEP_RUNS = int(os.environ.get("ODW_GUI_KEEP_RUNS", "30"))
MAX_UPLOAD_MB = int(os.environ.get("ODW_GUI_MAX_UPLOAD_MB", "50"))
UPLOAD_CASE = "wgrane"

# Skąd można wybrać gotową sprawę (folder z podfolderami spraw, każdy z plikami PDF).
CASE_SOURCES: dict[str, tuple[str, Path]] = {
    "input": ("input/", ROOT / "input"),
    "train": ("data/train/ (dane treningowe)", ROOT / "data" / "train"),
}

# Klasa wnioskowana z kluczy JSON, gdyby evidence nie powstało (np. awaria przed analizą).
CLASS_BY_TOP_KEY = {"OdwolanieKIO": "odwolanie", "mocodawca": "pelnomocnictwo", "przelew_bankowy": "przelew"}

RUN_ID_RE = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")
_run_slots = threading.BoundedSemaphore(2)

mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/octet-stream", ".bcmap")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("application/octet-stream", ".pfb")

app = FastAPI(title="Odwołania2JSON – podgląd", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------------------------------------------------

def _safe_name(name: str) -> str:
    """Sama nazwa pliku, bez ścieżek i znaków sterujących; zachowuje polskie znaki."""
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name).strip(" .")
    return name or "dokument.pdf"


def _unique(name: str, taken: set[str]) -> str:
    """Unikalna nazwa w obrębie sprawy (po rdzeniu, bo output to <rdzeń>.json)."""
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate, i = name, 2
    while candidate.lower().rsplit(".", 1)[0] in taken:
        candidate = f"{stem}_{i}{suffix}"
        i += 1
    taken.add(candidate.lower().rsplit(".", 1)[0])
    return candidate


def _is_pdf_name(name: str) -> bool:
    return name.lower().endswith(".pdf")


def _new_run(label: str, case: str) -> Path:
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    run = RUNS_DIR / rid
    (run / "input" / case).mkdir(parents=True)
    (run / "meta.json").write_text(
        json.dumps({"id": rid, "label": label, "case": case, "created": time.time(), "status": "pending"},
                   ensure_ascii=False), encoding="utf-8")
    return run


def _run_dir(rid: str) -> Path:
    if not RUN_ID_RE.match(rid):
        raise HTTPException(404, "nieznany przebieg")
    run = RUNS_DIR / rid
    if not (run / "meta.json").is_file():
        raise HTTPException(404, "nieznany przebieg")
    return run


def _read_meta(run: Path) -> dict[str, Any]:
    return json.loads((run / "meta.json").read_text(encoding="utf-8"))


def _write_meta(run: Path, meta: dict[str, Any]) -> None:
    tmp = run / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(run / "meta.json")


def _prune_runs() -> None:
    runs = sorted((p for p in RUNS_DIR.iterdir() if p.is_dir() and RUN_ID_RE.match(p.name)), reverse=True)
    for old in runs[KEEP_RUNS:]:
        shutil.rmtree(old, ignore_errors=True)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _leaves(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, obj


CLASS_ORDER = {"odwolanie": 0, "pelnomocnictwo": 1, "przelew": 2}


def _summarize(run: Path, case: str) -> list[dict[str, Any]]:
    """Podsumowanie dokumentów: najpierw rozpoznane (odwołanie, pełnomocnictwo, przelew, inne), na końcu {}."""
    docs = []
    for pdf in sorted((run / "input" / case).glob("*"), key=lambda p: p.name.lower()):
        if not pdf.is_file() or not _is_pdf_name(pdf.name):
            continue
        out = run / "output" / case / (pdf.stem + ".json")
        ev_path = run / "evidence" / case / (pdf.stem + ".evidence.json")
        data = _load_json(out)
        ev = _load_json(ev_path) or {}
        fields = ev.get("fields") or {}
        cls = ev.get("class") if ev else None
        if cls is None and isinstance(data, dict) and data:
            cls = next((CLASS_BY_TOP_KEY[k] for k in data if k in CLASS_BY_TOP_KEY), "nieznana")
        leaves = list(_leaves(data)) if isinstance(data, dict) else []
        filled = [p for p, v in leaves if v is not None]
        docs.append({
            "name": pdf.name,
            "stem": pdf.stem,
            "class": cls,
            "has_output": data is not None,
            "empty": data == {},
            "pages": ev.get("pages"),
            "stats": {
                "total": len(leaves),
                "filled": len(filled),
                "located": sum(1 for p in filled if (fields.get(p) or {}).get("boxes")),
                "derived": sum(1 for p in filled if (fields.get(p) or {}).get("source") == "derived"),
            },
        })
    docs.sort(key=lambda d: (d["class"] is None, CLASS_ORDER.get(d["class"] or "", 9), d["name"].lower()))
    return docs


def _execute(run: Path) -> dict[str, Any]:
    """Uruchamia pipeline CLI na katalogu przebiegu i zapisuje podsumowanie w meta.json."""
    meta = _read_meta(run)
    case = meta["case"]
    n = sum(1 for p in (run / "input" / case).iterdir() if _is_pdf_name(p.name))
    cmd = [PYTHON, str(ROOT / "main.py"), "--input", str(run / "input"), "--output", str(run / "output"),
           "--evidence", str(run / "evidence")]
    started = time.time()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    with _run_slots:
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=60 + 45 * max(n, 1), env=env)
            rc, log = proc.returncode, (proc.stdout + proc.stderr)
        except subprocess.TimeoutExpired as e:
            rc, log = -1, f"przekroczono limit czasu ({e.timeout:.0f} s)"
        except OSError as e:
            rc, log = -1, f"nie udało się uruchomić pipeline'u: {e}"
    meta.update({
        "status": "ok" if rc == 0 else "error",
        "returncode": rc,
        "duration": round(time.time() - started, 2),
        "log": log[-8000:],
        "docs": _summarize(run, case),
    })
    _write_meta(run, meta)
    return meta


def _doc(run: Path, idx: int) -> tuple[dict[str, Any], dict[str, Any]]:
    meta = _read_meta(run)
    docs = meta.get("docs") or []
    if not 0 <= idx < len(docs):
        raise HTTPException(404, "nie ma takiego dokumentu")
    return meta, docs[idx]


# ---------------------------------------------------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "root": str(ROOT), "python": PYTHON}


@app.get("/api/cases")
def cases() -> dict[str, Any]:
    sources = []
    for sid, (label, base) in CASE_SOURCES.items():
        if not base.is_dir():
            continue
        items = []
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            n = sum(1 for f in d.iterdir() if f.is_file() and _is_pdf_name(f.name))
            if n:
                items.append({"name": d.name, "pdfs": n})
        loose = sum(1 for f in base.iterdir() if f.is_file() and _is_pdf_name(f.name))
        if loose:
            items.insert(0, {"name": ".", "pdfs": loose, "label": "(pliki bezpośrednio w folderze)"})
        if items:
            sources.append({"id": sid, "label": label, "cases": items})
    return {"sources": sources}


class CaseRequest(BaseModel):
    source: str
    case: str


@app.post("/api/run/case")
def run_case(req: CaseRequest) -> dict[str, Any]:
    if req.source not in CASE_SOURCES:
        raise HTTPException(400, "nieznane źródło")
    base = CASE_SOURCES[req.source][1].resolve()
    src = (base / req.case).resolve()
    if src != base and base not in src.parents or not src.is_dir():
        raise HTTPException(404, "nie ma takiej sprawy")
    pdfs = sorted(f for f in src.iterdir() if f.is_file() and _is_pdf_name(f.name))
    if not pdfs:
        raise HTTPException(400, "sprawa nie zawiera plików PDF")
    case = _safe_name(src.name) if req.case != "." else UPLOAD_CASE
    run = _new_run(f"{CASE_SOURCES[req.source][0].split(' ')[0]}{'' if req.case == '.' else req.case}", case)
    taken: set[str] = set()
    for f in pdfs:
        shutil.copy2(f, run / "input" / case / _unique(_safe_name(f.name), taken))
    _prune_runs()
    return _execute(run)


@app.post("/api/run/upload")
async def run_upload(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    accepted, skipped = [], []
    run: Path | None = None
    taken: set[str] = set()
    for up in files:
        name = _safe_name(up.filename or "dokument.pdf")
        content = await up.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
        if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
            skipped.append(f"{name}: plik większy niż {MAX_UPLOAD_MB} MB")
            continue
        if not _is_pdf_name(name):
            if content[:1024].lstrip().startswith(b"%PDF") or b"%PDF" in content[:1024]:
                name += ".pdf"
            else:
                skipped.append(f"{name}: to nie jest plik PDF")
                continue
        if run is None:
            run = _new_run("wgrane pliki", UPLOAD_CASE)
        name = _unique(name, taken)
        (run / "input" / UPLOAD_CASE / name).write_bytes(content)
        accepted.append(name)
    if run is None:
        raise HTTPException(400, "brak plików PDF do przetworzenia" + (": " + "; ".join(skipped) if skipped else ""))
    meta = _read_meta(run)
    meta["label"] = (accepted[0] if len(accepted) == 1 else f"{accepted[0]} +{len(accepted) - 1}")[:120]
    _write_meta(run, meta)
    _prune_runs()
    meta = await _in_thread(_execute, run)
    if skipped:
        meta["skipped"] = skipped
        _write_meta(run, meta)
    return meta


async def _in_thread(fn, *args):
    import anyio.to_thread

    return await anyio.to_thread.run_sync(fn, *args)


@app.get("/api/runs")
def runs() -> list[dict[str, Any]]:
    if not RUNS_DIR.is_dir():
        return []
    out = []
    for p in sorted((p for p in RUNS_DIR.iterdir() if RUN_ID_RE.match(p.name)), reverse=True):
        meta = _load_json(p / "meta.json")
        if meta and meta.get("status") in ("ok", "error"):
            out.append({k: meta.get(k) for k in ("id", "label", "created", "status")} | {"docs": len(meta.get("docs") or [])})
    return out


@app.get("/api/runs/{rid}")
def run_meta(rid: str) -> dict[str, Any]:
    return _read_meta(_run_dir(rid))


@app.get("/api/runs/{rid}/docs/{idx}/pdf")
def doc_pdf(rid: str, idx: int) -> FileResponse:
    run = _run_dir(rid)
    meta, doc = _doc(run, idx)
    return FileResponse(run / "input" / meta["case"] / doc["name"], media_type="application/pdf")


@app.get("/api/runs/{rid}/docs/{idx}/json")
def doc_json(rid: str, idx: int, download: bool = False) -> Response:
    run = _run_dir(rid)
    meta, doc = _doc(run, idx)
    path = run / "output" / meta["case"] / (doc["stem"] + ".json")
    if not path.is_file():
        raise HTTPException(404, "brak wyniku JSON dla tego dokumentu")
    if download:
        return FileResponse(path, media_type="application/json", filename=doc["stem"] + ".json")
    return Response(path.read_bytes(), media_type="application/json")


@app.get("/api/runs/{rid}/docs/{idx}/evidence")
def doc_evidence(rid: str, idx: int) -> JSONResponse:
    run = _run_dir(rid)
    meta, doc = _doc(run, idx)
    ev = _load_json(run / "evidence" / meta["case"] / (doc["stem"] + ".evidence.json"))
    return JSONResponse(ev or {"fields": {}, "class": doc.get("class"), "page_sizes": []})


@app.get("/api/runs/{rid}/case_report")
def case_report(rid: str) -> JSONResponse:
    """Kontrola formalna sprawy (config/case_rules.yaml), zapisana przez pipeline obok evidence."""
    run = _run_dir(rid)
    meta = _read_meta(run)
    return JSONResponse(_load_json(run / "evidence" / meta["case"] / "_sprawa.report.json") or {"rules": []})


@app.get("/api/runs/{rid}/zip")
def run_zip(rid: str) -> Response:
    run = _run_dir(rid)
    meta = _read_meta(run)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted((run / "output").rglob("*.json")):
            zf.write(f, f.relative_to(run / "output").as_posix())
    name = f"odwolania2json-{meta['case']}.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{_quote(name)}"})


def _quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s)
