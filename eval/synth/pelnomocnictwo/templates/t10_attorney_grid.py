"""Prose principal + attorneys in a column table (Lp | Imię i nazwisko | Tytuł | Nr wpisu | PESEL)."""
from eval.synth.pelnomocnictwo.lib import esc, id_parts, scope_items, title_str
from reportlab.lib.units import mm

ID = "dev_t10_attorney_grid"
PREFS = {"n_att": [0.2, 0.55, 0.25], "pesel": 0.4}


def build(c):
    k, r = c.case, c.rng
    s = []
    top = [[c.P(f"{k.city}, {c.date()}", "left"), c.P(f"Sygn. akt: {esc(k.kio_sygn.replace('sygn. akt ', ''))}" if k.kio_sygn else "", "right")]]
    s.append(c.table(top, [85 * mm, 80 * mm], grid=False))
    s.append(c.P("PEŁNOMOCNICTWO", "title"))
    for p in k.principals:
        rep = ", ".join(f"{sg.full}" + (f" ({sg.role})" if sg.role else "") for sg in p.signatories)
        s.append(c.P(f"<b>{esc(p.nazwa)}</b>, {esc(p.address)} (" + ", ".join(id_parts(c, p)) + f"), reprezentowan{'y' if p.typ=='osoba_fizyczna' else 'a'} przez: {rep};"))
    s.append(c.P(("udziela" if len(k.principals) == 1 else "wspólnie udzielają") + " pełnomocnictwa następującym osobom:"))
    rows = [["Lp.", "Imię i nazwisko", "Tytuł zawodowy", "Nr wpisu", "PESEL"]]
    for i, a in enumerate(k.attorneys, 1):
        rows.append([str(i), a.full, title_str(r, a, "nom") or "—", a.bar_no or "—", a.pesel or "—"])
    s.append(c.table(rows, [12 * mm, 50 * mm, 38 * mm, 32 * mm, 33 * mm], header=True))
    s.append(c.sp(6))
    s.append(c.P(f"Pełnomocnictwo obejmuje reprezentację w postępowaniu „{esc(k.procurement['tytul'])}” "
                 + (f"(nr {esc(k.procurement['numer'])}) " if k.procurement.get("numer") else "")
                 + "oraz w szczególności umocowanie do:"))
    for it in scope_items(r):
        s.append(c.P(f"– {it},", leftIndent=12))
    s.append(c.P("Każdy z pełnomocników może działać samodzielnie." if len(k.attorneys) > 1 else ""))
    s.append(c.sp(18))
    sig = [[c.P("<b>Mocodawca</b>", "cell"), c.P("<b>Przyjęcie pełnomocnictwa</b>", "cell")]]
    left = [sg for p in k.principals for sg in p.signatories]
    for i in range(max(len(left), len(k.attorneys))):
        l = c.P(f"<br/><br/>{c.sig_line()}<br/>{left[i].full}", "cell") if i < len(left) else ""
        rr = c.P(f"<br/><br/>{c.sig_line()}<br/>{k.attorneys[i].full}", "cell") if i < len(k.attorneys) else ""
        sig.append([l, rr])
    s.append(c.table(sig, [82 * mm, 82 * mm], grid=False))
    return s
