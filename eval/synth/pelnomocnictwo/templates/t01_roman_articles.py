"""Roman-numbered articles, accusative 'ustanawia pełnomocnikiem', place/date at the bottom."""
from eval.synth.pelnomocnictwo.lib import esc, id_parts, join_pl, scope_items, title_str, VALIDITY_PL

ID = "dev_t01_roman_articles"
PREFS = {}


def build(c):
    k, r = c.case, c.rng
    s = []
    s.append(c.P(r.choice(["PEŁNOMOCNICTWO", "P E Ł N O M O C N I C T W O", "Pełnomocnictwo procesowe"]), "title"))
    if k.kio_sygn:
        s.append(c.P(f"(dotyczy sprawy {esc(k.kio_sygn)})", "center"))
    s.append(c.P("I. Mocodawca" if len(k.principals) == 1 else "I. Mocodawcy", "h"))
    for i, p in enumerate(k.principals, 1):
        ids = ", ".join(id_parts(c, p, (r.choice(["KRS", "nr KRS", "KRS:"]), r.choice(["NIP", "NIP:"]), "REGON")))
        lead = f"{i}) " if len(k.principals) > 1 else ""
        extra = ""
        if p.typ == "osoba_fizyczna":
            extra = f" – przedsiębiorca {p.owner.form('nom')}, wpisany do CEIDG"
        s.append(c.P(f"{lead}<b>{esc(p.nazwa)}</b>{extra}, z siedzibą: {esc(p.address)}, {ids}."))
    s.append(c.P("II. Ustanowienie pełnomocnika", "h"))
    many = len(k.attorneys) > 1
    names = []
    for a in k.attorneys:
        t = title_str(r, a, "acc")
        n = a.form("acc")
        bits = [f"{t} {n}".strip()]
        if a.pesel:
            bits.append(f"PESEL {a.pesel}")
        if a.bar_no:
            bits.append(f"nr wpisu {a.bar_no}")
        names.append(", ".join(bits))
    verb = "ustanawia" if len(k.principals) == 1 else "ustanawiają"
    s.append(c.P(f"Mocodaw{'ca' if len(k.principals)==1 else 'cy'} {verb} pełnomocnik{'ami' if many else 'iem'}: "
                 + join_pl(names, " oraz ") + "."))
    if many:
        s.append(c.P(r.choice(["Pełnomocnicy działają samodzielnie.", "Każdy z pełnomocników może działać samodzielnie.",
                               "Pełnomocnicy są uprawnieni do działania łącznie lub każdy z osobna."])))
    s.append(c.P("III. Przedmiot", "h"))
    pr = k.procurement
    s.append(c.P(f"Pełnomocnictwo dotyczy postępowania o udzielenie zamówienia publicznego pn. „{esc(pr['tytul'])}”"
                 + (f", nr {esc(pr['numer'])}" if pr.get("numer") else "")
                 + f", prowadzonego przez {esc(pr['zamawiajacy'])}, i obejmuje umocowanie do:"))
    for i, it in enumerate(scope_items(r), 1):
        s.append(c.P(f"{i}. {it};", leftIndent=14))
    s.append(c.P("IV. Postanowienia końcowe", "h"))
    s.append(c.P(r.choice(VALIDITY_PL)))
    s.append(c.sp(14))
    s.append(c.P(f"{k.city}, dnia {c.date()}", "left"))
    s.append(c.sp(10))
    for p in k.principals:
        s.append(c.P(f"Za {esc(p.nazwa)}:" if len(k.principals) > 1 else "Podpis Mocodawcy:", "left"))
        for sg in p.signatories:
            s.append(c.sp(12))
            s.append(c.P(c.sig_line(), "left"))
            s.append(c.P(f"{sg.full}" + (f", {sg.role}" if sg.role else ""), "left"))
    return s
