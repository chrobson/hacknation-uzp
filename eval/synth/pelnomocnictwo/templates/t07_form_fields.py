"""Form-like layout: numbered fields with labels, checkboxes for principal type."""
from eval.synth.pelnomocnictwo.lib import esc, scope_items, title_str
from reportlab.lib.units import mm

ID = "dev_t07_form_fields"
PREFS = {"fizyczna": 0.25}


def build(c):
    k, r = c.case, c.rng
    s = [c.P("FORMULARZ PEŁNOMOCNICTWA", "title"),
         c.P("(do reprezentacji wykonawcy w postępowaniu odwoławczym przed KIO)", "center"), c.sp(6)]
    if k.kio_sygn:
        s.append(c.P(f"Nr sprawy KIO (jeśli nadano): <b>{esc(k.kio_sygn)}</b>", "left"))
    n = 1
    for p in k.principals:
        prawna = p.typ == "osoba_prawna"
        rows = [[f"{n}. Mocodawca", ""],
                ["Rodzaj", ("[X] osoba prawna / jednostka organizacyjna   [ ] osoba fizyczna" if prawna
                            else "[ ] osoba prawna / jednostka organizacyjna   [X] osoba fizyczna prowadząca działalność")],
                ["Firma (nazwa)", esc(p.nazwa)]]
        if not prawna:
            rows.append(["Imię i nazwisko", p.owner.full])
        rows += [["Adres", esc(p.address)], ["KRS", p.krs or "nie dotyczy"], ["NIP", c.nip(p.nip) if p.nip else "—"],
                 ["Osoby reprezentujące", "; ".join(f"{sg.full}" + (f" ({sg.role})" if sg.role else "") for sg in p.signatories)]]
        t = c.table(rows, [48 * mm, 117 * mm], grid=True)
        s += [t, c.sp(6)]
        n += 1
    for a in k.attorneys:
        rows = [[f"{n}. Pełnomocnik", ""], ["Imię i nazwisko", a.full],
                ["Tytuł zawodowy", title_str(r, a, "nom") or "brak"],
                ["Nr wpisu", a.bar_no or "—"], ["PESEL", a.pesel or "—"]]
        s += [c.table(rows, [48 * mm, 117 * mm]), c.sp(6)]
        n += 1
    s.append(c.P(f"{n}. Zakres umocowania", "h"))
    for it in scope_items(r):
        s.append(c.P(f"[X] {it}", "left", leftIndent=10))
    s.append(c.P(f"{n+1}. Postępowanie: „{esc(k.procurement['tytul'])}”, {esc(k.procurement['zamawiajacy'])}", "h"))
    s.append(c.sp(10))
    s.append(c.P(f"Data: {c.date()}       Miejsce: {k.city}", "left"))
    s.append(c.sp(16))
    for p in k.principals:
        for sg in p.signatories:
            s.append(c.P(f"Podpis: {c.sig_line()}   ({sg.full})", "left"))
            s.append(c.sp(8))
    return s
