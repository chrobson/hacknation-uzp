"""Board-resolution style ('Uchwała Zarządu ... w sprawie udzielenia pełnomocnictwa'), attorneys in the dative."""
from eval.synth.pelnomocnictwo.lib import esc, id_parts, join_pl, scope_items, title_str

ID = "dev_t12_board_resolution"
PREFS = {"consortium": 0.0, "fizyczna": 0.0}


def build(c):
    k, r = c.case, c.rng
    p = k.principals[0]
    nr = f"{r.randint(1, 60)}/{k.date.year}"
    s = [c.P(f"UCHWAŁA NR {nr}", "title"),
         c.P(f"Zarządu spółki {esc(p.nazwa)} z siedzibą {esc(p.address)}<br/>(" + ", ".join(id_parts(c, p)) + ")", "center"),
         c.P(f"z dnia {c.date()}", "center"),
         c.P("w sprawie udzielenia pełnomocnictwa procesowego", "center", fontName=c.bold), c.sp(10)]
    att = []
    for a in k.attorneys:
        t = title_str(r, a, "dat")
        att.append((f"{t} " if t else "") + a.form("dat") + (f", PESEL {a.pesel}" if a.pesel else ""))
    s.append(c.P("§ 1", "center"))
    s.append(c.P(f"Zarząd Spółki postanawia udzielić {join_pl(att, ' oraz ')} pełnomocnictwa do reprezentowania Spółki "
                 f"w postępowaniu o udzielenie zamówienia publicznego „{esc(k.procurement['tytul'])}”, prowadzonym przez "
                 f"{esc(k.procurement['zamawiajacy'])}" + (f", oraz w sprawie przed KIO o sygn. {esc(k.kio_sygn.replace('sygn. akt ', ''))}" if k.kio_sygn else "") + "."))
    s.append(c.P("§ 2", "center"))
    s.append(c.P("Pełnomocnictwo obejmuje umocowanie do: " + "; ".join(scope_items(r)) + "."))
    s.append(c.P("§ 3", "center"))
    s.append(c.P("Uchwała wchodzi w życie z dniem podjęcia. Niniejsza uchwała stanowi jednocześnie pełnomocnictwo."))
    s.append(c.sp(20))
    s.append(c.P("Podpisy członków Zarządu:", "left"))
    for sg in p.signatories:
        s.append(c.sp(12))
        s.append(c.P(f"{sg.role or 'Członek Zarządu'}: {sg.full}  {c.sig_line()}", "left"))
    return s
