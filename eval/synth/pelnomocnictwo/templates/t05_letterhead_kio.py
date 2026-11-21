"""Company letterhead drawn in the page header, KIO signature line, 'upoważniam' + accusative."""
from eval.synth.pelnomocnictwo.lib import esc, join_pl, scope_items, title_str, gend

ID = "dev_t05_letterhead_kio"
PREFS = {"consortium": 0.1, "kio": 0.8}


def build(c):
    k, r = c.case, c.rng
    p0 = k.principals[0]
    head = [p0.nazwa, p0.address]
    ids = []
    if p0.nip:
        ids.append(f"NIP: {c.nip(p0.nip)}")
    if p0.krs:
        ids.append(f"KRS: {p0.krs}")
    if ids:
        head.append(" | ".join(ids))
    al = r.choice(["left", "center"])
    c.header = [(h, al) for h in head]
    c.margins = (22, 20, 38, 22)
    c.footer = [(r.choice(["Strona {page}", "str. {page}", ""]), "right")]
    s = []
    s.append(c.P(f"{k.city}, {c.date()}", "right"))
    if k.kio_sygn:
        s.append(c.P(f"<b>Sygn. akt:</b> {esc(k.kio_sygn.replace('sygn. akt ', ''))}", "left"))
    s.append(c.P("Krajowa Izba Odwoławcza<br/>ul. Postępu 17a<br/>02-676 Warszawa", "left", leftIndent=250))
    s.append(c.sp(10))
    s.append(c.P("PEŁNOMOCNICTWO PROCESOWE", "title"))
    sigs = k.principals[0].signatories
    sg_txt = join_pl([f"{sg.form('nom')} – {sg.role}" if sg.role else sg.form('nom') for sg in sigs], " oraz ")
    if len(k.principals) == 1:
        if p0.typ == "osoba_fizyczna":
            who = f"Ja, {p0.owner.full}, prowadząc{gend(p0.owner, 'y', 'a')} działalność gospodarczą pod firmą {esc(p0.nazwa)}"
            verb = "upoważniam"
        else:
            who = f"Działając w imieniu {esc(p0.nazwa)} (dalej: Spółka), jako {sg_txt}"
            verb = "upoważniam" if len(sigs) == 1 else "upoważniamy"
    else:
        others = "; ".join(f"{esc(p.nazwa)}, {esc(p.address)}" + (f", NIP {c.nip(p.nip)}" if p.nip else "") + (f", KRS {p.krs}" if p.krs else "") for p in k.principals[1:])
        who = (f"Działając w imieniu wykonawców wspólnie ubiegających się o zamówienie: {esc(p0.nazwa)} oraz {others}, "
               f"my, niżej podpisani")
        verb = "upoważniamy"
    atts = []
    for a in k.attorneys:
        t = title_str(r, a, "acc")
        x = f"{a.pan('acc')} {a.form('acc')}" if r.random() < 0.5 else a.form("acc")
        if t:
            x = f"{t} {x}" if r.random() < 0.5 else f"{x}, {t}"
        if a.pesel:
            x += f" (PESEL {a.pesel})"
        atts.append(x)
    target = f"w sprawie odwołania o sygn. {esc(k.kio_sygn)}" if k.kio_sygn else "w postępowaniu odwoławczym"
    s.append(c.P(f"{who}, niniejszym {verb} {join_pl(atts, ' oraz ')} do reprezentowania przed Krajową Izbą Odwoławczą {target}, "
                 f"dotyczącego postępowania „{esc(k.procurement['tytul'])}”, prowadzonego przez {esc(k.procurement['zamawiajacy'])}."))
    s.append(c.P("Pełnomocnictwo obejmuje umocowanie do: " + "; ".join(scope_items(r)) + "."))
    s.append(c.sp(24))
    for p in k.principals:
        if len(k.principals) > 1:  # consortium: say which company each signer acts for
            s.append(c.P(f"za {esc(p.nazwa)}:", "right"))
        for sg in p.signatories:
            s.append(c.P(c.sig_line(), "right"))
            s.append(c.P(f"({sg.full})", "right"))
            s.append(c.sp(8))
    return s
