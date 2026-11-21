"""Generate the example PDF for the extra class (dev only):

    uv run --with reportlab python examples/klasy/make_fixture.py [--font /path/DejaVuSans.ttf]
"""

import argparse
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

TEXT = """Sygn. akt: KIO 1234/26
Warszawa, dnia 12 października 2026 r.
Adresat:
Belmoria Rozwiązania S.A.
ul. Zaczarowana 78, 90-803 Łódź
WEZWANIE
Krajowa Izba Odwoławcza, działając na podstawie art. 519 ust. 1 ustawy Prawo zamówień publicznych,
wzywa Odwołującego do uzupełnienia następujących braków formalnych odwołania:
brak dowodu uiszczenia brakującej części wpisu w kwocie 5 000,00 zł oraz brak odpisu pełnomocnictwa.
Braki należy uzupełnić w terminie 3 dni od dnia doręczenia wezwania.
Pouczenie: nieuzupełnienie braków w terminie skutkuje zwróceniem odwołania.
Przewodniczący: Jan Kowalski"""

DEFAULT_FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/DejaVuSans.ttf"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default=next((f for f in DEFAULT_FONTS if Path(f).exists()), None))
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "przyklady" / "sprawa1" / "pismo_kio.pdf")
    args = ap.parse_args()
    if not args.font:
        raise SystemExit("need a TTF font with Polish glyphs: --font /path/to/DejaVuSans.ttf")
    pdfmetrics.registerFont(TTFont("Body", args.font))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(args.out), pagesize=A4)
    c.setFont("Body", 10)
    y = A4[1] - 60
    for line in TEXT.splitlines():
        c.drawString(50, y, line)
        y -= 16
    c.save()
    print(args.out)


if __name__ == "__main__":
    main()
