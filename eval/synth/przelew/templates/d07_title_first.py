"""Reordered sections: title as headline, amount and date next, accounts at the bottom."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from eval.synth.common_przelew import esc, fmt_date, para_styles, pick_font, render_values

NAME = "d07_title_first"


def render(case, rng, path):
    font = pick_font(rng, allow_mono=False)
    st = para_styles(font, 10)
    v = render_values(case, rng)
    story = [Paragraph(esc(case.bank).upper(), st["s"]),
             Paragraph(rng.choice(["Tytuł operacji", "Opis płatności", "Tytułem"]), st["s"]),
             Paragraph(esc(v.title), st["h2"]),
             HRFlowable(width="100%", color=colors.grey), Spacer(1, 3 * mm),
             Paragraph(f"<font size=18><b>{v.amount}</b></font>", st["n"]), Spacer(1, 4 * mm),
             Paragraph(f"zrealizowano {v.date}", st["n"])]
    if v.ref:
        story.append(Paragraph(f"numer transakcji {v.ref}", st["n"]))
    story += [Spacer(1, 30 * mm), HRFlowable(width="100%", color=colors.grey),
              Paragraph(f"Rachunek obciążony: {v.z} ({esc(case.payer.name)})", st["s"]),
              Paragraph(f"Rachunek uznany: {v.na} ({esc(case.payee.name)}, {esc(case.payee_bank)})", st["s"]),
              Paragraph(f"Wydruk: {fmt_date(case.gen_date, 'iso_time', rng)}", st["s"])]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=30 * mm, rightMargin=30 * mm).build(story)
