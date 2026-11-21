"""Consortium letter in 1st person plural; attorneys in the dative ('udzielamy Panu ...')."""
from eval.synth.pelnomocnictwo.lib import esc, id_parts, join_pl, scope_items, title_str, gend

ID = "dev_t02_consortium_dative"
PREFS = {"consortium": 0.7, "n_att": [0.4, 0.45, 0.15]}


def build(c):
    k, r = c.case, c.rng
    s = []
    s.append(c.P(f"{k.city}, {c.date()}", "right"))
    s.append(c.sp(8))
    s.append(c.P("PEŁNOMOCNICTWO", "title"))
    if len(k.principals) > 1:
        intro = r.choice(["My, niżej podpisani, działając w imieniu wykonawców wspólnie ubiegających się o udzielenie zamówienia:",
                          "Wykonawcy wspólnie ubiegający się o zamówienie (konsorcjum) w składzie:"])
    else:
        intro = "My, niżej podpisani, działając w imieniu:"
    s.append(c.P(intro))
    for i, p in enumerate(k.principals, 1):
        role = ""
        if len(k.principals) > 1:
            role = r.choice(["Lider: ", "Partner: "]) if r.random() < 0.4 else ""
            if role:
                role = "Lider konsorcjum – " if i == 1 else "Członek konsorcjum – "
        ids = "; ".join(id_parts(c, p))
        s.append(c.P(f"{i}. {role}{esc(p.nazwa)}, {esc(p.address)}; {ids}", leftIndent=12))
    people = []
    for a in k.attorneys:
        t = title_str(r, a, "dat")
        nm = f"{a.pan('dat')} {a.form('dat')}"
        if t:
            nm += f", {t}" + (f" (nr wpisu {a.bar_no})" if a.bar_no else "")
        if a.pesel:
            nm += f", PESEL: {a.pesel}"
        people.append(nm)
    s.append(c.P("niniejszym udzielamy " + join_pl(people, " i ") +
                 f" pełnomocnictwa do reprezentowania {'konsorcjum' if len(k.principals) > 1 else 'naszej spółki'} "
                 f"w postępowaniu „{esc(k.procurement['tytul'])}” prowadzonym przez {esc(k.procurement['zamawiajacy'])}, "
                 "w tym w szczególności do: " + "; ".join(scope_items(r)) + "."))
    if k.kio_sygn:
        s.append(c.P(f"Pełnomocnictwo obejmuje w szczególności postępowanie odwoławcze o sygn. {esc(k.kio_sygn)}."))
    s.append(c.sp(16))
    rows = []
    for p in k.principals:
        cell = [c.P(f"<b>{esc(p.nazwa)}</b>", "cell")]
        for sg in p.signatories:
            cell += [c.sp(18), c.P(c.sig_line(), "cell"), c.P(f"{esc(sg.full)}<br/>{esc(sg.role or '')}", "cell")]
        rows.append(cell)
    from reportlab.platypus import Table, TableStyle
    t = Table([rows], hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(t)
    return s
