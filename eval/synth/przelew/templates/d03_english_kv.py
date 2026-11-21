"""English-labelled payment confirmation, label/value rows without grid."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from eval.synth.common_przelew import (FOOTERS_EN, esc, fmt_date, para_styles, pick_font,
                                       render_values)

NAME = "d03_english_kv"


def render(case, rng, path):
    font = pick_font(rng)
    st = para_styles(font, 9.5)
    v = render_values(case, rng, english=True,
                      acct_styles=["pl", "pl_spaced", "pl_space_after", "plain"])
    lab = rng.choice([
        dict(t="PAYMENT CONFIRMATION", pay="Ordering party", za="Debit account", ben="Beneficiary",
             na="Beneficiary account (IBAN)", am="Amount", dt="Value date", ti="Payment details",
             ref="Transaction ID"),
        dict(t="Outgoing transfer – confirmation", pay="Sender", za="From account", ben="Recipient",
             na="To account", am="Transfer amount", dt="Execution date", ti="Reference / title",
             ref="Bank reference"),
    ])
    rows = [[lab["pay"], Paragraph(f"{esc(case.payer.name)}<br/>{esc(case.payer.address)}", st["n"])],
            [lab["za"], v.z],
            [lab["ben"], Paragraph(f"{esc(case.payee.name)}<br/>{esc(case.payee.address)}", st["n"])],
            [lab["na"], v.na],
            ["Beneficiary bank", case.payee_bank],
            [lab["am"], Paragraph(f"<b>{v.amount}</b>", st["n"])],
            [lab["dt"], v.date],
            [lab["ti"], Paragraph(esc(v.title), st["n"])]]
    if v.ref:
        rows.append([lab["ref"], v.ref])
    rows += [["Status", rng.choice(["Completed", "Executed", "Booked"])], ["Fee", "0.00 PLN"]]
    t = Table(rows, colWidths=[50 * mm, 120 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (0, -1), font[1], 9),
                           ("FONT", (1, 0), (1, -1), font[0], 9.5),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    story = [Paragraph(esc(case.bank) + f" · SWIFT/BIC {case.bic}", st["s"]),
             Paragraph(lab["t"], st["h1"]),
             Paragraph(f"Printed on {fmt_date(case.gen_date, 'en_long')}", st["s"]),
             HRFlowable(width="100%", thickness=1, color=colors.black), Spacer(1, 4 * mm), t,
             Spacer(1, 8 * mm), Paragraph(rng.choice(FOOTERS_EN), st["s"])]
    SimpleDocTemplate(str(path), pagesize=rng.choice([A4, LETTER]), topMargin=18 * mm).build(story)
