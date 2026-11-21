"""Short single-paragraph authorisation; UPPERCASE surnames; signatories inflected after 'przez'."""
from eval.synth.pelnomocnictwo.lib import esc, join_pl, title_str

ID = "dev_t09_short_upper"
PREFS = {"consortium": 0.15, "fizyczna": 0.1}


def build(c):
    k, r = c.case, c.rng
    up = r.random() < 0.75
    s = [c.P(f"{k.city}, {c.date()}", "right"), c.sp(20),
         c.P(r.choice(["PEŁNOMOCNICTWO", "UPOWAŻNIENIE – PEŁNOMOCNICTWO PROCESOWE"]), "title"), c.sp(6)]
    parts = []
    for p in k.principals:
        ids = []
        if p.krs:
            ids.append(f"wpisana do rejestru przedsiębiorców KRS pod nr {p.krs}")
        if p.nip:
            ids.append(f"NIP {c.nip(p.nip)}")
        if p.typ == "osoba_fizyczna":
            parts.append(f"{p.owner.form('nom', upper_last=up)} prowadząc{'a' if p.owner.female else 'y'} działalność pod firmą "
                         f"{esc(p.nazwa)}" + (f", NIP {c.nip(p.nip)}" if p.nip else ""))
        else:
            sg = join_pl([f"{x.role} – {x.form('acc', upper_last=up)}" if x.role else x.form('acc', upper_last=up) for x in p.signatories], " oraz ")
            parts.append(f"{esc(p.nazwa)} z siedzibą {esc(p.address)}, " + ", ".join(ids) + f", reprezentowana przez {sg}")
    atts = []
    for a in k.attorneys:
        t = title_str(r, a, "acc")
        atts.append((f"{t} " if t else "") + a.form("acc", upper_last=up) + (f" (PESEL: {a.pesel})" if a.pesel else ""))
    verb = "udziela" if len(k.principals) == 1 else "udzielają"
    s.append(c.P(join_pl(parts, " oraz ") + f" {verb} niniejszym pełnomocnictwa procesowego, ustanawiając pełnomocnik"
                 + ("ami " if len(atts) > 1 else "iem ") + join_pl(atts, " i ") +
                 f", do reprezentowania przed Krajową Izbą Odwoławczą w sprawie dotyczącej zamówienia „{esc(k.procurement['tytul'])}”"
                 + (f" (sygn. {esc(k.kio_sygn.replace('sygn. akt ', ''))})" if k.kio_sygn else "") + ", ze wszystkimi uprawnieniami wynikającymi z przepisów prawa."))
    s.append(c.sp(30))
    for p in k.principals:
        for sg in p.signatories:
            s.append(c.P(f"{c.sig_line()}<br/>{sg.form('nom', upper_last=up)}", "right"))
            s.append(c.sp(10))
    return s
