"""Appeal (odwolanie) templates focused on multi-entity parties and party details.

Each template is ``render(case, ctx, path, v)`` where ``v`` is a small dict of variant
switches chosen by the scenario list in generate.py. Cases come from
:func:`make_case`, which reuses the odwolanie sampler (values recombined from train GT)
and then forces the party structure the scenario needs, so the GT stays exact.
"""

from __future__ import annotations

import random

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle

from ..odwolanie import blocks as B
from ..odwolanie import core as C
from ..odwolanie.core import Attorney, Case, Ctx, build_simple, esc

# --------------------------------------------------------------------------- case shaping


def make_case(rng: random.Random, n_zam: int = 1, lead: int | None = None, n_odw: int = 1,
              att: str = "firm", n_att: int = 1, title: str | None = None) -> Case:
    """Sample a case and force its party structure.

    n_zam  - number of contracting authorities; lead = index of the leading one
             (prowadzacy_postepowanie 1, others 0); lead None with n_zam > 1 -> all 0.
    n_odw  - 1 or a consortium of n_odw appellants (GT keeps the leader = odw[0]).
    att    - 'firm' | 'nofirm' (pelnomocnik.nazwa null) | 'none' (no attorney).
    title  - force the first attorney's title key ('rp', 'adw', '').
    """
    case = C.sample_case(rng, {"multi_zam": 0.0, "consortium": 0.0, "data_null": 0.0,
                               "no_attorney": 1.0 if att == "none" else 0.0,
                               "multi_attorney": 1.0 if n_att > 1 else 0.0})
    pl = C.pools()
    P = C.DEFAULT_PROBS
    if n_odw > 1:
        srcs = [s for s in pl.odw if s["nazwa"] != case.odw[0].nazwa]
        case.odw += [C._entity(rng, s, P["krs_null"], P["regon_null"], P["nip_null"])
                     for s in rng.sample(srcs, n_odw - 1)]
        case.odw[0].role = "Lider"
        for e in case.odw[1:]:
            e.role = "Partner"
        case.consortium = True
    taken = {e.nazwa for e in case.odw}
    zsrc = rng.sample([z for z in pl.zam if z["nazwa"] not in taken], n_zam)
    case.zams = [C._entity(rng, s, P["zam_krs_null"], P["zam_regon_null"], P["zam_nip_null"]) for s in zsrc]
    if n_zam > 1:
        for i, z in enumerate(case.zams):
            z.prowadzacy = 1 if i == lead else 0
    if case.attorneys:
        case.attorneys = case.attorneys[:n_att]
        while len(case.attorneys) < n_att:
            other = rng.choice([a for a in pl.att if a["imie_nazwisko"] not in {x.imie_nazwisko for x in case.attorneys}])
            case.attorneys.append(Attorney(other["imie_nazwisko"], rng.choice(["rp", "adw"])))
        if title is not None:
            case.attorneys[0].title_key = title
    if att == "nofirm":
        a0 = case.attorneys[0].imie_nazwisko
        first, last = a0.split()[0], a0.split()[-1]
        tr = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
        case.firm_nazwa = None
        case.firm_mail = f"{first[0].lower()}.{last.lower().translate(tr)}@{rng.choice(['poczta', 'kontakt', 'prawnik'])}.example"
    return case


TITLE_SHORT = {"rp": ["r.pr.", "r. pr.", "radca prawny"], "adw": ["adw.", "adwokat", "mec."], "apl": ["apl. radc."], "": [""]}


def titled(ctx: Ctx, a: Attorney) -> str:
    return f"{ctx.rng.choice(TITLE_SHORT[a.title_key])} {a.imie_nazwisko}".strip()


def ids_inline(ctx: Ctx, e, sep: str = ", ") -> str:
    return sep.join(ctx.id_parts(e))


def firm_line(case: Case, ctx: Ctx) -> str:
    """Firm name immediately followed by its address on the same line (or own address)."""
    if case.firm_nazwa:
        return f"{esc(case.firm_nazwa)}, {esc(case.firm_address)}"
    return f"adres do doręczeń: {esc(case.firm_address)}"


def body(case: Case, ctx: Ctx, s: list, numbering: str = "{i}.") -> None:
    """Common appeal body after the party header."""
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s.append(ctx.P("Zaskarżonym czynnościom i zaniechaniom zarzucam:", "body"))
    s += B.zarzuty_flow(case, ctx, numbering=numbering)
    s += B.requests_flow(case, ctx)
    s += B.justification(case, ctx, n_fill=3)
    s += B.signature(case, ctx)
    s += B.attachments(case, ctx)


def odw_simple(case: Case, ctx: Ctx) -> list[str]:
    e = case.odw[0]
    return [f"<b>{esc(e.nazwa)}</b>", esc(e.address)] + ctx.id_parts(e)


def proc_head(case: Case, ctx: Ctx) -> str:
    return "Dotyczy: " + B.proc_sentence(case, ctx)


# --------------------------------------------------------------------------- templates

LEAD_TAGS = ["prowadzący postępowanie", "Lider – prowadzący postępowanie", "pełnomocnik Zamawiających prowadzący postępowanie",
             "Zamawiający prowadzący postępowanie", "lider postępowania"]


def m01_numbered(case, ctx, path, v):
    """'Zamawiający:' followed by a numbered list; lead marked with a dash tag."""
    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.gap(4),
         ctx.P("<br/>".join(B.kio_lines(ctx)), "body", leftIndent=260), ctx.gap(5)]
    s.append(ctx.P("<b>Odwołujący:</b>", "body"))
    s.append(ctx.P("<br/>".join(odw_simple(case, ctx)), "body", leftIndent=16))
    if case.attorneys:
        s.append(ctx.P("reprezentowany przez: " + ", ".join(esc(titled(ctx, a)) for a in case.attorneys), "body", leftIndent=16))
        s.append(ctx.P(firm_line(case, ctx) + f", e-mail: {case.firm_mail}", "body", leftIndent=16))
    s.append(ctx.gap(2))
    s.append(ctx.P("<b>Zamawiający:</b>", "body"))
    tag = ctx.rng.choice(LEAD_TAGS)
    for i, z in enumerate(case.zams, 1):
        mark = f" – {tag}" if z.prowadzacy else ""
        s.append(ctx.P(f"{i}. <b>{esc(z.nazwa)}</b>{mark}<br/>{esc(z.address)}<br/>{ids_inline(ctx, z)}",
                       "body", leftIndent=16))
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    body(case, ctx, s)
    build_simple(path, s, ctx)


def m02_labelled(case, ctx, path, v):
    """'Zamawiający 1' / 'Zamawiający 2' label column; lead named in a separate sentence or inline."""
    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.gap(3), ctx.P("ODWOŁANIE", "title")]
    rows = []
    for i, e in enumerate(case.odw):
        lbl = "Odwołujący" if not case.consortium else ("Odwołujący – Lider" if i == 0 else "Odwołujący – Partner")
        rows.append([f"<b>{lbl}</b>", "<br/>".join([f"<b>{esc(e.nazwa)}</b>", esc(e.address)] + ctx.id_parts(e))])
    lead_inline = v.get("inline", False)
    for i, z in enumerate(case.zams, 1):
        lbl = f"Zamawiający {i}" + (" (lider postępowania)" if (lead_inline and z.prowadzacy) else "")
        rows.append([f"<b>{lbl}</b>", "<br/>".join([f"<b>{esc(z.nazwa)}</b>", esc(z.address)] + ctx.id_parts(z))])
    if case.attorneys:
        rows.append(["<b>Pełnomocnik</b>", "<br/>".join([esc(titled(ctx, a)) for a in case.attorneys]
                                                       + [firm_line(case, ctx), f"e-mail: {case.firm_mail}"])])
    s.append(ctx.table(rows, [38 * mm, 128 * mm], grid=ctx.rng.random() < 0.6))
    lead = next((i for i, z in enumerate(case.zams, 1) if z.prowadzacy), None)
    if lead and not lead_inline:
        s.append(ctx.gap(2))
        s.append(ctx.P(f"Postępowanie prowadzi Zamawiający {lead} jako zamawiający prowadzący postępowanie, "
                       f"działający w imieniu i na rzecz pozostałych Zamawiających na podstawie porozumienia "
                       f"o wspólnym przeprowadzeniu postępowania (art. 38 ust. 1 Pzp).", "just"))
    s.append(ctx.gap(2))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    body(case, ctx, s, numbering="Zarzut {r}")
    build_simple(path, s, ctx, footer="- {p} -")


def m03_prose_wspolnie(case, ctx, path, v):
    """All authorities in one paragraph ('Zamawiający wspólnie: ...'), optional lead clause."""
    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.gap(3),
         ctx.P(", ".join(B.kio_lines(ctx)), "body"), ctx.gap(3)]
    o = case.odw[0]
    s.append(ctx.P(f"<b>Odwołujący:</b> {esc(o.nazwa)} z siedzibą przy {esc(o.address)}, {ids_inline(ctx, o)}.", "just"))
    if case.attorneys:
        a = case.attorneys[0]
        s.append(ctx.P(f"Pełnomocnik Odwołującego: {esc(titled(ctx, a))}, {firm_line(case, ctx)}, {case.firm_mail}.", "just"))
    parts = [f"{esc(z.nazwa)} z siedzibą: {esc(z.address)}, {ids_inline(ctx, z)}" for z in case.zams]
    txt = "<b>Zamawiający wspólnie:</b> " + "; oraz ".join(parts)
    lead = next((z for z in case.zams if z.prowadzacy), None)
    if lead:
        txt += (f" – w imieniu których postępowanie prowadzi {esc(lead.nazwa)} "
                f"jako {ctx.rng.choice(['lider', 'zamawiający prowadzący postępowanie', 'pełnomocnik zamawiających'])}")
    s.append(ctx.P(txt + ".", "just"))
    s.append(ctx.P("Odwołanie", "title"))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    body(case, ctx, s)
    build_simple(path, s, ctx, footer=None)


def m04_w_imieniu(case, ctx, path, v):
    """'Zamawiający: X, działający w imieniu i na rzecz: 1) Y, 2) Z' - X leads."""
    s = [ctx.table([["", esc(B.place_date(case, ctx))]], [90 * mm, 76 * mm], grid=False), ctx.gap(3),
         ctx.P("<br/>".join(B.kio_lines(ctx)), "bold", leftIndent=250), ctx.gap(4)]
    s.append(ctx.P("<b>Odwołujący:</b>", "body"))
    s.append(ctx.P("<br/>".join(odw_simple(case, ctx)), "body", leftIndent=14))
    if case.attorneys:
        s.append(ctx.P("działający przez pełnomocnika: " + esc(titled(ctx, case.attorneys[0]))
                       + f"<br/>{firm_line(case, ctx)}<br/>e-mail: {case.firm_mail}", "body", leftIndent=14))
    lead, rest = case.zams[0], case.zams[1:]
    s.append(ctx.P("<b>Zamawiający:</b>", "body"))
    s.append(ctx.P(f"<b>{esc(lead.nazwa)}</b>, {esc(lead.address)}, {ids_inline(ctx, lead)},", "body", leftIndent=14))
    s.append(ctx.P(ctx.rng.choice(["prowadzący postępowanie, działający w imieniu i na rzecz:",
                                   "jako zamawiający prowadzący postępowanie, działający w imieniu własnym oraz w imieniu i na rzecz:",
                                   "występujący jako pełnomocnik zamawiających prowadzący postępowanie, działający w imieniu i na rzecz:"]),
                   "body", leftIndent=14))
    for i, z in enumerate(rest, 1):
        s.append(ctx.P(f"{i}) {esc(z.nazwa)}, {esc(z.address)}, {ids_inline(ctx, z)}", "body", leftIndent=28))
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    body(case, ctx, s)
    build_simple(path, s, ctx, footer="Strona {p} z {n}", footer_align="right")


def m05_tables(case, ctx, path, v):
    """Authorities (and consortium members) as tables with a role column."""
    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.P("ODWOŁANIE", "title"),
         ctx.P("do Prezesa Krajowej Izby Odwoławczej", "center"), ctx.gap(4)]
    s.append(ctx.P("I. Odwołujący", "h"))
    if case.consortium:
        order = list(range(len(case.odw)))
        if v.get("leader_last"):
            order = order[1:] + order[:1]
        rows = [["Lp.", "Wykonawca", "Adres", "Identyfikatory", "Rola w konsorcjum"]]
        for n, i in enumerate(order, 1):
            e = case.odw[i]
            rows.append([str(n), esc(e.nazwa), esc(e.address), "<br/>".join(ctx.id_parts(e)),
                         "Lider (pełnomocnik konsorcjum)" if i == 0 else "Członek konsorcjum"])
        s.append(ctx.table(rows, [10 * mm, 45 * mm, 42 * mm, 38 * mm, 31 * mm], header=True))
    else:
        s.append(ctx.P("<br/>".join(odw_simple(case, ctx)), "body"))
    if case.attorneys:
        s.append(ctx.P("Pełnomocnik: " + esc(titled(ctx, case.attorneys[0])) + f", {firm_line(case, ctx)}, "
                       f"e-mail: {case.firm_mail}", "body"))
    s.append(ctx.P("II. Zamawiający", "h"))
    rows = [["Lp.", "Nazwa zamawiającego", "NIP", "REGON", "KRS", "Rola"]]
    for i, z in enumerate(case.zams, 1):
        role = ("Zamawiający prowadzący postępowanie" if z.prowadzacy else "Zamawiający") if len(case.zams) > 1 else "Zamawiający"
        rows.append([str(i), f"{esc(z.nazwa)}<br/>{esc(z.address)}", ctx.nip(z.nip) if z.nip else "—",
                     ctx.regon(z.regon) if z.regon else "—", ctx.krs(z.krs) if z.krs else "—", role])
    s.append(ctx.table(rows, [10 * mm, 58 * mm, 28 * mm, 24 * mm, 24 * mm, 22 * mm], header=True))
    s.append(ctx.P("III. Przedmiot odwołania", "h"))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    body(case, ctx, s, numbering="{a})")
    build_simple(path, s, ctx)


def m06_kv_footer(case, ctx, path, v):
    """Key:value party tables; procurement identifiers only in the page footer."""
    foot = []
    if case.nr:
        foot.append(f"Znak sprawy: {case.nr}")
    if case.bzp:
        foot.append(f"Ogłoszenie BZP: {ctx.bzp(case.bzp)}")
    if case.ted:
        foot.append(f"Dz.Urz. UE: {ctx.ted(case.ted)}")
    foot_txt = "  |  ".join(foot)

    def on_page(c, doc):
        w, _ = doc.pagesize
        c.saveState()
        c.setFont(ctx.font, ctx.size - 2.5)
        c.line(20 * mm, 18 * mm, w - 20 * mm, 18 * mm)
        c.drawString(20 * mm, 14 * mm, foot_txt)
        c.drawRightString(w - 20 * mm, 9 * mm, f"str. {doc.page}")
        c.restoreState()

    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.P("ODWOŁANIE", "title")]

    def kv(title, e):
        rows = [[f"<b>{title}</b>", ""], ["Nazwa:", esc(e.nazwa)], ["Adres:", esc(e.address)]]
        if e.krs:
            rows.append(["KRS:", ctx.krs(e.krs)])
        if e.nip:
            rows.append(["NIP:", ctx.nip(e.nip)])
        if e.regon:
            rows.append(["REGON:", ctx.regon(e.regon)])
        return ctx.table(rows, [32 * mm, 134 * mm], grid=False, shade=colors.HexColor("#f0f0f0"))

    for i, e in enumerate(case.odw):
        s.append(kv("Odwołujący" if not case.consortium else ("Odwołujący (Lider konsorcjum)" if i == 0 else "Członek konsorcjum"), e))
        s.append(ctx.gap(2))
    if case.attorneys:
        a = case.attorneys[0]
        rows = [["<b>Pełnomocnik</b>", ""], ["Imię i nazwisko:", esc(titled(ctx, a))]]
        if case.firm_nazwa:
            rows.append(["Kancelaria:", f"{esc(case.firm_nazwa)}, {esc(case.firm_address)}"])
        else:
            rows.append(["Adres:", esc(case.firm_address)])
        rows.append(["E-mail:", case.firm_mail])
        s.append(ctx.table(rows, [32 * mm, 134 * mm], grid=False, shade=colors.HexColor("#f0f0f0")))
        s.append(ctx.gap(2))
    for i, z in enumerate(case.zams, 1):
        t = "Zamawiający" if len(case.zams) == 1 else f"Zamawiający {i}" + (" (prowadzący postępowanie)" if z.prowadzacy else "")
        s.append(kv(t, z))
        s.append(ctx.gap(2))
    s.append(ctx.P(f"w postępowaniu o udzielenie zamówienia publicznego pn. „{esc(case.tytul)}”, prowadzonym w trybie {case.tryb}.", "just"))
    body(case, ctx, s)
    build_simple(path, s, ctx, footer=None, on_page=on_page, margins=(20, 20, 22, 26))


def m07_consortium_prose(case, ctx, path, v):
    """Consortium appellant in prose; attorney named in inflected forms (GT nominative)."""
    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.gap(3),
         ctx.P("<br/>".join(B.kio_lines(ctx)), "body", leftIndent=250), ctx.gap(4),
         ctx.P("ODWOŁANIE WYKONAWCÓW WSPÓLNIE UBIEGAJĄCYCH SIĘ O UDZIELENIE ZAMÓWIENIA", "title")]
    members = []
    for i, e in enumerate(case.odw):
        role = "Lidera Konsorcjum" if i == 0 else "Partnera Konsorcjum"
        members.append(f"{esc(e.nazwa)} z siedzibą przy {esc(e.address)} ({ids_inline(ctx, e)}) – w charakterze {role}")
    a = case.attorneys[0] if case.attorneys else None
    txt = ("<b>Odwołujący</b> – wykonawcy wspólnie ubiegający się o udzielenie zamówienia: " + "; ".join(members))
    if a:
        firm = (f" z {esc(case.firm_nazwa)}, {esc(case.firm_address)}" if case.firm_nazwa
                else f", prowadzącego indywidualną praktykę, adres: {esc(case.firm_address)}")
        txt += (f", reprezentowani przez pełnomocnika – {esc(a.inflected('acc'))}{firm}, e-mail: {case.firm_mail}")
    s.append(ctx.P(txt + ".", "just"))
    z = case.zams[0]
    s.append(ctx.P(f"<b>Zamawiający</b>: {esc(z.nazwa)}, {esc(z.address)}, {ids_inline(ctx, z)}.", "just"))
    s.append(ctx.P(proc_head(case, ctx) + ".", "just"))
    if a:
        s.append(ctx.P(f"Umocowanie {esc(a.inflected('gen'))} wynika z pełnomocnictwa udzielonego przez {'obu' if len(case.odw) == 2 else 'wszystkich'} członków "
                       f"konsorcjum, które załączam do niniejszego odwołania.", "just"))
    body(case, ctx, s)
    build_simple(path, s, ctx)


def m08_leader_second(case, ctx, path, v):
    """Consortium listed partner first, leader second (explicitly labelled); several attorneys."""
    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.gap(3),
         ctx.P("<br/>".join(B.kio_lines(ctx)), "bold", leftIndent=250), ctx.gap(4)]
    s.append(ctx.P("<b>Odwołujący – Konsorcjum w składzie:</b>", "body"))
    order = case.odw[1:] + case.odw[:1]
    for n, e in enumerate(order, 1):
        role = "Lider Konsorcjum (pełnomocnik)" if e is case.odw[0] else "Partner Konsorcjum"
        s.append(ctx.P(f"{n}) {role}: <b>{esc(e.nazwa)}</b>, {esc(e.address)}, {ids_inline(ctx, e, '; ')}", "body", leftIndent=14))
    if case.attorneys:
        names = [esc(titled(ctx, a)) for a in case.attorneys]
        s.append(ctx.P("Pełnomocnicy Odwołującego: " + ", ".join(names), "body", leftIndent=14))
        s.append(ctx.P(firm_line(case, ctx) + f", tel. {case.firm_phone}, e-mail: {case.firm_mail}", "body", leftIndent=14))
    s.append(ctx.gap(2))
    s.append(ctx.P("<b>Zamawiający:</b>", "body"))
    for i, z in enumerate(case.zams, 1):
        pre = f"{i}) " if len(case.zams) > 1 else ""
        mark = " (prowadzący postępowanie)" if z.prowadzacy else ""
        s.append(ctx.P(f"{pre}<b>{esc(z.nazwa)}</b>{mark}, {esc(z.address)}, {ids_inline(ctx, z, '; ')}", "body", leftIndent=14))
    s.append(ctx.P("Odwołanie", "title"))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    body(case, ctx, s, numbering="{r}.")
    build_simple(path, s, ctx, footer="{p}/{n}", footer_align="right")


def m09_two_columns(case, ctx, path, v):
    """Two-column party header: appellant left, authorities right ('Zamawiający nr 1' ...)."""
    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.gap(3)]
    left = [ctx.P("<b>ODWOŁUJĄCY</b>", "body")]
    for i, e in enumerate(case.odw):
        if case.consortium:
            left.append(ctx.P("<i>Lider:</i>" if i == 0 else "<i>Partner:</i>", "small"))
        left.append(ctx.P("<br/>".join([f"<b>{esc(e.nazwa)}</b>", esc(e.address)] + ctx.id_parts(e)), "small"))
    if case.attorneys:
        left.append(ctx.P("<b>Pełnomocnik:</b><br/>" + esc(titled(ctx, case.attorneys[0])) + "<br/>"
                          + firm_line(case, ctx) + f"<br/>{case.firm_mail}", "small"))
    right = [ctx.P("<b>ZAMAWIAJĄCY</b>", "body")]
    for i, z in enumerate(case.zams, 1):
        lab = f"Zamawiający nr {i}" + (" – prowadzący postępowanie" if z.prowadzacy else "") if len(case.zams) > 1 else ""
        if lab:
            right.append(ctx.P(f"<i>{lab}:</i>", "small"))
        right.append(ctx.P("<br/>".join([f"<b>{esc(z.nazwa)}</b>", esc(z.address)] + ctx.id_parts(z)), "small"))
    t = Table([[left, right]], colWidths=[83 * mm, 83 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEAFTER", (0, 0), (0, 0), 0.5, colors.grey)]))
    s.append(t)
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    body(case, ctx, s)
    build_simple(path, s, ctx, footer="Strona {p}")


def m10_firm_letterhead(case, ctx, path, v):
    """Law-firm letterhead (name and address on one line); appellant represented in prose."""
    a = case.attorneys[0]
    head = (f"{case.firm_nazwa}, {case.firm_address}" if case.firm_nazwa
            else f"{titled(ctx, a)}, {case.firm_address}")

    def on_page(c, doc):
        w, h = doc.pagesize
        c.saveState()
        c.setFont(ctx.bold, ctx.size - 0.5)
        c.drawCentredString(w / 2, h - 12 * mm, head)
        c.setFont(ctx.font, ctx.size - 1.5)
        c.drawCentredString(w / 2, h - 16.5 * mm, f"tel. {case.firm_phone} · e-mail: {case.firm_mail}")
        c.line(20 * mm, h - 19 * mm, w - 20 * mm, h - 19 * mm)
        c.restoreState()

    s = [ctx.P(esc(B.place_date(case, ctx)), "right"), ctx.gap(3),
         ctx.P("<br/>".join(B.kio_lines(ctx)), "body", leftIndent=250), ctx.gap(4)]
    o = case.odw[0]
    s.append(ctx.P(f"<b>Odwołujący:</b> {esc(o.nazwa)}, {esc(o.address)}, {ids_inline(ctx, o)}", "body"))
    if len(case.zams) == 1:
        z = case.zams[0]
        s.append(ctx.P(f"<b>Zamawiający:</b> {esc(z.nazwa)}, {esc(z.address)}, {ids_inline(ctx, z)}", "body"))
    else:
        s.append(ctx.P("<b>Zamawiający (wspólnie):</b>", "body"))
        for z in case.zams:
            mark = " – pełnomocnik zamawiających prowadzący postępowanie" if z.prowadzacy else ""
            s.append(ctx.P(f"• {esc(z.nazwa)}{mark}, {esc(z.address)}, {ids_inline(ctx, z)}", "body", leftIndent=12))
    s.append(ctx.P("ODWOŁANIE", "title"))
    s.append(ctx.P(proc_head(case, ctx), "just"))
    s.append(ctx.P(f"Odwołujący, reprezentowany przez {esc(a.inflected('acc'))} (pełnomocnictwo z dnia "
                   f"{ctx.d(case.extra_dates[1])} w załączeniu), wnosi niniejsze odwołanie.", "just"))
    body(case, ctx, s)
    build_simple(path, s, ctx, footer=None, on_page=on_page, margins=(22, 20, 26, 20))


TEMPLATES = {
    "m01_numbered": m01_numbered,
    "m02_labelled": m02_labelled,
    "m03_prose_wspolnie": m03_prose_wspolnie,
    "m04_w_imieniu": m04_w_imieniu,
    "m05_tables": m05_tables,
    "m06_kv_footer": m06_kv_footer,
    "m07_consortium_prose": m07_consortium_prose,
    "m08_leader_second": m08_leader_second,
    "m09_two_columns": m09_two_columns,
    "m10_firm_letterhead": m10_firm_letterhead,
}
