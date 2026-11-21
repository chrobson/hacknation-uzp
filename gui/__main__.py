"""Start: python -m gui [--host 127.0.0.1] [--port 8000] [--open]"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gui", description="Odwołania2JSON – lokalny podgląd PDF ↔ JSON")
    ap.add_argument("--host", default="127.0.0.1", help="adres nasłuchu (domyślnie 127.0.0.1; w WSL/Dockerze 0.0.0.0)")
    ap.add_argument("--port", type=int, default=8000, help="port (domyślnie 8000)")
    ap.add_argument("--open", action="store_true", help="otwórz przeglądarkę po starcie")
    ap.add_argument("--reload", action="store_true", help="tryb deweloperski: przeładowanie po zmianie kodu")
    args = ap.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print("Brak zależności GUI. Zainstaluj: pip install -r gui/requirements.txt", file=sys.stderr)
        return 2

    url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}/"
    print(f"Odwołania2JSON GUI: {url}  (Ctrl+C kończy)", flush=True)
    if args.open:
        import threading
        import webbrowser

        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run("gui.app:app", host=args.host, port=args.port, reload=args.reload, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
