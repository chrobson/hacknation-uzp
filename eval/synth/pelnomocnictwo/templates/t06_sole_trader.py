"""Natural person (sole trader) in first person; attorney often with PESEL; 'swoim pełnomocnikiem'."""
from eval.synth.pelnomocnictwo.lib import esc, join_pl, scope_items, title_str, gend

ID = "dev_t06_sole_trader"
PREFS = {"fizyczna": 0.9, "consortium": 0.05, "pesel": 0.5}


def build(c):
    k, r = c.case, c.rng
    s = []
    s.append(c.P(r.choice(["PEŁNOMOCNICTWO SZCZEGÓLNE", "PEŁNOMOCNICTWO", "Pełnomocnictwo"]), "title"))
    paras = []
    for p in k.principals:
        if p.typ == "osoba_fizyczna":
            o = p.owner
            ids = []
            if p.nip:
                ids.append(f"NIP {c.nip(p.nip)}")
            if p.regon_shown:
                ids.append(f"REGON {p.regon}")
            paras.append(f"{o.full}, prowadząc{gend(o, 'y', 'a')} jednoosobową działalność gospodarczą pod firmą "
                         f"<b>{esc(p.nazwa)}</b>, z miejscem wykonywania działalności: {esc(p.address)}, " + ", ".join(ids))
        else:
            ids = [f"KRS {p.krs}"] if p.krs else []
            if p.nip:
                ids.append(f"NIP {c.nip(p.nip)}")
            sg = join_pl([f"{x.full} ({x.role})" if x.role else x.full for x in p.signatories], " i ")
            paras.append(f"<b>{esc(p.nazwa)}</b>, {esc(p.address)}, " + ", ".join(ids) + f", reprezentowana przez: {sg}")
    single_person = len(k.principals) == 1 and k.principals[0].typ == "osoba_fizyczna"
    if single_person:
        o = k.principals[0].owner
        s.append(c.P(f"Ja, niżej podpisan{gend(o, 'y', 'a')} " + paras[0] + ","))
        verb = "ustanawiam swoim" if len(k.attorneys) == 1 else "ustanawiam swoimi"
    else:
        s.append(c.P("Niżej wymienieni:<br/>" + "<br/>".join(f"– {x}" for x in paras)))
        verb = "ustanawiają swoim" if len(k.attorneys) == 1 else "ustanawiają swoimi"
    many = len(k.attorneys) > 1
    atts = []
    for a in k.attorneys:
        t = title_str(r, a, "acc")
        x = f"{t} {a.form('acc')}".strip()
        if a.pesel:
            x += f", legitymując{gend(a, 'ego', 'ą')} się numerem PESEL {a.pesel}"
        if a.bar_no:
            x += f", wpisan{gend(a, 'ego', 'ą')} na listę pod nr {a.bar_no}"
        atts.append(x)
    s.append(c.P(f"{verb} pełnomocnik{'ami' if many else 'iem'} {join_pl(atts, ' oraz ')}, "
                 f"upoważniając {'ich' if many else gend(k.attorneys[0], 'go', 'ją')} do działania w {'moim' if single_person else 'ich'} imieniu w sprawie "
                 f"zamówienia „{esc(k.procurement['tytul'])}” (zamawiający: {esc(k.procurement['zamawiajacy'])}), a w szczególności do:"))
    for it in scope_items(r):
        s.append(c.P(f"• {it}", leftIndent=16))
    if k.kio_sygn:
        s.append(c.P(f"Sprawa przed KIO: {esc(k.kio_sygn)}."))
    s.append(c.sp(16))
    rows = [[f"{k.city}, {c.date()}", ""]]
    names = [sg for p in k.principals for sg in p.signatories]
    for sg in names:
        rows.append(["", c.sig_line()])
        rows.append(["", sg.full])
    s.append(c.table(rows, grid=False, pad=2))
    return s
