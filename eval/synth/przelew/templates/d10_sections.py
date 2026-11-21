"""Numbered sections separated by rules; inline 'Label: value' lines."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from eval.synth.common_przelew import esc, fmt_date, para_styles, pick_font, render_values

NAME = "d10_sections"


def render(case, rng, path):
    font = pick_font(rng)
    st = para_styles(font, 9.5)
    v = render_values(case, rng)
    sec = {
        "zl": ("Dane zleceniodawcy", [f"Nazwa: {esc(case.payer.name)}", f"Adres: {esc(case.payer.address)}",
                                       f"Numer rachunku: {v.z}"]),
        "be": ("Dane beneficjenta", [f"Nazwa: {esc(case.payee.name)}", f"Adres: {esc(case.payee.address)}",
                                      f"Numer rachunku: {v.na}", f"Bank: {esc(case.payee_bank)}"]),
        "pl": ("Szczegóły płatności", [f"Kwota: {v.amount}", f"Data realizacji: {v.date}",
                                        f"Tytuł płatności: {esc(v.title)}"] +
               ([f"Numer referencyjny: {v.ref}"] if v.ref else [])),
    }
    order = rng.choice([["zl", "be", "pl"], ["pl", "zl", "be"], ["be", "zl", "pl"]])
    story = [Paragraph("DYSPOZYCJA PRZELEWU – POTWIERDZENIE", st["h1"]),
             Paragraph(f"{esc(case.bank)}, BIC: {case.bic}", st["n"]),
             Paragraph(f"Data wydruku: {fmt_date(case.gen_date, 'dmy_dash')}", st["s"])]
    for i, k in enumerate(order, 1):
        title, lines = sec[k]
        story += [Spacer(1, 3 * mm), HRFlowable(width="100%", color=colors.darkblue, thickness=1.2),
                  Paragraph(f"{i}. {title}", st["h2"])]
        story += [Paragraph(x, st["n"]) for x in lines]
    story += [Spacer(1, 8 * mm), Paragraph("Dyspozycja została zrealizowana.", st["s"])]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
