"""Consortium blocks 'Lider' / 'Partner' with headings; attorneys as a bullet list, often without titles."""
from eval.synth.pelnomocnictwo.lib import esc, id_parts, scope_items, title_str

ID = "dev_t08_leader_partner"
PREFS = {"consortium": 0.9, "no_title": 0.5, "n_att": [0.3, 0.5, 0.2]}


def build(c):
    k, r = c.case, c.rng
    s = []
    if k.kio_sygn:
        c.header = [(k.kio_sygn.upper(), "right")]
    s.append(c.P("PEŁNOMOCNICTWO", "title"))
    s.append(c.P(f"sporządzone w miejscowości {k.city} w dniu {c.date()}", "center"))
    s.append(c.hr())
    labels = ["LIDER KONSORCJUM", "PARTNER KONSORCJUM", "PARTNER KONSORCJUM 2"] if len(k.principals) > 1 else ["WYKONAWCA"]
    for lab, p in zip(labels, k.principals):
        s.append(c.P(lab, "h"))
        s.append(c.P(f"{esc(p.nazwa)}<br/>{esc(p.address)}<br/>" + "<br/>".join(id_parts(c, p, ("KRS:", "NIP:", "REGON:"))), "left"))
        s.append(c.P("w imieniu którego działa: " + ", ".join(f"{sg.full}" + (f" – {sg.role}" if sg.role else "") for sg in p.signatories), "left"))
    s.append(c.hr())
    s.append(c.P(("Wykonawcy wspólnie" if len(k.principals) > 1 else "Wykonawca") + " ustanawia" + ("ją" if len(k.principals) > 1 else "") +
                 " pełnomocnikiem/pełnomocnikami:"))
    for a in k.attorneys:
        t = title_str(r, a, "abbr")
        line = f"• {a.full}" + (f" – {t}" if t else "")
        if a.pesel:
            line += f", PESEL {a.pesel}"
        s.append(c.P(line, "left", leftIndent=14))
    s.append(c.P(f"do reprezentowania wykonawców w postępowaniu „{esc(k.procurement['tytul'])}” prowadzonym przez "
                 f"{esc(k.procurement['zamawiajacy'])}, w szczególności do: " + "; ".join(scope_items(r)) + "."))
    s.append(c.sp(20))
    for lab, p in zip(labels, k.principals):
        s.append(c.P(f"<b>Za {lab.lower()}:</b>", "left"))
        for sg in p.signatories:
            s.append(c.sp(14))
            s.append(c.P(f"{c.sig_line()}<br/>{sg.full}", "left"))
    return s
