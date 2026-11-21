"""Key/value tables for principal(s) and attorney(s); scope as short paragraph; signature grid."""
from eval.synth.pelnomocnictwo.lib import esc, scope_items, title_str
from reportlab.lib.units import mm

ID = "dev_t03_kv_tables"
PREFS = {}


def build(c):
    k, r = c.case, c.rng
    s = [c.P(r.choice(["PEŁNOMOCNICTWO", "PEŁNOMOCNICTWO DO REPREZENTACJI W POSTĘPOWANIU ODWOŁAWCZYM"]), "title")]
    if k.kio_sygn:
        s.append(c.P(f"Sygnatura: {esc(k.kio_sygn)}", "right"))
    s.append(c.P(f"Miejscowość i data: {k.city}, {c.date()}", "left"))
    s.append(c.sp(6))
    for i, p in enumerate(k.principals, 1):
        hdr = "MOCODAWCA" if len(k.principals) == 1 else f"MOCODAWCA {i} (wykonawca wspólnie ubiegający się o zamówienie)"
        s.append(c.P(hdr, "h"))
        rows = [["Nazwa / firma", esc(p.nazwa)], ["Adres siedziby", esc(p.address)]]
        if p.typ == "osoba_fizyczna":
            rows.insert(1, ["Imię i nazwisko przedsiębiorcy", p.owner.full])
            rows.append(["Forma", "osoba fizyczna prowadząca działalność gospodarczą (CEIDG)"])
        if p.krs:
            rows.append(["Numer KRS", p.krs])
        if p.nip:
            rows.append(["NIP", c.nip(p.nip)])
        if p.regon_shown:
            rows.append(["REGON", p.regon])
        rows.append(["Reprezentowany przez", "<br/>".join(f"{sg.full}" + (f" – {sg.role}" if sg.role else "") for sg in p.signatories)])
        s.append(c.table(rows, [55 * mm, 110 * mm], zebra=r.random() < 0.5))
    s.append(c.P("PEŁNOMOCNI" + ("K" if len(k.attorneys) == 1 else "CY"), "h"))
    for a in k.attorneys:
        rows = [["Imię i nazwisko", a.full]]
        if a.title:
            rows.append(["Tytuł zawodowy", title_str(r, a, "nom")])
        if a.bar_no:
            rows.append(["Nr wpisu na listę", a.bar_no])
        if a.pesel:
            rows.append(["PESEL", a.pesel])
        s.append(c.table(rows, [55 * mm, 110 * mm]))
        s.append(c.sp(4))
    s.append(c.P("ZAKRES", "h"))
    s.append(c.P(f"Reprezentowanie Mocodawcy w postępowaniu „{esc(k.procurement['tytul'])}” "
                 f"(zamawiający: {esc(k.procurement['zamawiajacy'])}), w tym do: " + ", ".join(scope_items(r)) + "."))
    s.append(c.sp(18))
    sig = []
    for p in k.principals:
        for sg in p.signatories:
            sig.append([c.P(c.sig_line(), "cell"), c.P(f"{sg.full}<br/>({esc(p.nazwa)})", "small")])
    s.append(c.table([[x[0] for x in sig[i:i+2]] for i in range(0, len(sig), 2)] , grid=False))
    s.append(c.table([[x[1] for x in sig[i:i+2]] for i in range(0, len(sig), 2)] , grid=False))
    return s
