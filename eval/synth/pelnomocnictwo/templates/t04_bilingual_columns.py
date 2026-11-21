"""Bilingual PL | EN side-by-side columns (table)."""
from eval.synth.pelnomocnictwo.lib import esc, id_parts, scope_items, SCOPE_EN, SIGN_ROLES_EN, title_str
from reportlab.lib.units import mm

ID = "dev_t04_bilingual_columns"
PREFS = {"fizyczna": 0.05}


def build(c):
    k, r = c.case, c.rng
    s = [c.P("PEŁNOMOCNICTWO / POWER OF ATTORNEY", "title")]
    if k.kio_sygn:
        s.append(c.P(f"Ref.: {esc(k.kio_sygn)}", "right"))
    rows = []
    plp = []
    enp = []
    for p in k.principals:
        plp.append(f"<b>{esc(p.nazwa)}</b>, {esc(p.address)}, " + ", ".join(id_parts(c, p)))
        enp.append(f"<b>{esc(p.nazwa)}</b>, {esc(p.address)}, " + ", ".join(
            id_parts(c, p, ("National Court Register No.", "Tax ID", "Statistical No."))))
    rows.append([("Mocodawca:" if len(plp) == 1 else "Mocodawcy (konsorcjum):") + "<br/>" + "<br/>".join(plp),
                 ("Principal:" if len(enp) == 1 else "Principals (consortium):") + "<br/>" + "<br/>".join(enp)])
    multi = len(k.principals) > 1

    def _who(p):  # consortium: name the company each representative acts for
        return f"{esc(p.nazwa)} – " if multi else ""
    sigs_pl = "; ".join(_who(p) + ", ".join(f"{sg.full} ({sg.role or 'osoba uprawniona'})" for sg in p.signatories) for p in k.principals) if multi else \
        "; ".join(f"{sg.full} ({sg.role or 'osoba uprawniona'})" for p in k.principals for sg in p.signatories)
    sigs_en = "; ".join(_who(p) + ", ".join(f"{sg.full} ({SIGN_ROLES_EN.get(sg.role, 'authorised person')})" for sg in p.signatories) for p in k.principals) if multi else \
        "; ".join(f"{sg.full} ({SIGN_ROLES_EN.get(sg.role, 'authorised person')})" for p in k.principals for sg in p.signatories)
    rows.append([f"reprezentowany przez: {sigs_pl}", f"represented by: {sigs_en}"])
    att_pl = "<br/>".join(f"– {title_str(r, a, 'nom')} {a.full}".replace("–  ", "– ") + (f", PESEL {a.pesel}" if a.pesel else "") for a in k.attorneys)
    att_en = "<br/>".join(f"– {a.full}" + (f" ({r.choice(['attorney-at-law', 'legal counsel'])})" if a.title else "") + (f", PESEL {a.pesel}" if a.pesel else "") for a in k.attorneys)
    rows.append([f"niniejszym udziela pełnomocnictwa:<br/>{att_pl}", f"hereby grants a power of attorney to:<br/>{att_en}"])
    sc_pl = scope_items(r)
    sc_en = r.sample(SCOPE_EN, len(SCOPE_EN) - 1)
    rows.append([f"do reprezentowania w postępowaniu „{esc(k.procurement['tytul'])}”, w tym do: " + "; ".join(sc_pl) + ".",
                 "to represent the Principal in the public procurement procedure referred to opposite, including to: " + "; ".join(sc_en) + "."])
    rows.append([f"{k.city}, {c.date()}", f"{k.city}, {c.date()}"])
    s.append(c.table(rows, [82 * mm, 82 * mm], grid=r.random() < 0.6))
    s.append(c.sp(20))
    for p in k.principals:
        for sg in p.signatories:
            s.append(c.P(c.sig_line(), "left"))
            s.append(c.P(f"{sg.full} – {sg.role or ''} / {SIGN_ROLES_EN.get(sg.role, '')}" + (f" ({esc(p.nazwa)})" if multi else ""), "small"))
            s.append(c.sp(10))
    return s
