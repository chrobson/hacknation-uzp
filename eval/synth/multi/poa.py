"""Power-of-attorney (pelnomocnictwo) templates focused on several principals and signatories.

Each template is ``build(ctx, v)`` returning a platypus story; ``ctx`` is the
pelnomocnictwo :class:`lib.Ctx` (its case is the ground truth). Cases come from
:func:`make_case`, which reuses the pelnomocnictwo sampler and forces the structure.
"""

from __future__ import annotations

import random

from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle

from ..pelnomocnictwo import lib as L
from ..pelnomocnictwo.lib import att_name, esc, id_parts, join_pl, scope_items, title_str


def make_case(rng: random.Random, n_principals: int = 2, n_sig: tuple[int, ...] = (2, 1), n_att: int = 1,
              fizyczna: tuple[bool, ...] = (), pesel: float = 0.4) -> L.Case:
    w = [0.0, 0.0, 0.0]
    w[n_att - 1] = 1.0
    case = L.sample_case(rng, {"consortium": 1.0 if n_principals > 1 else 0.0, "fizyczna": 0.0,
                               "n_att": w, "pesel": pesel, "hide_krs": 0.0, "hide_nip": 0.0})
    pools = L.load_pools()
    used = {a.full for a in case.attorneys}
    princ = []
    for i in range(n_principals):
        if i < len(fizyczna) and fizyczna[i]:
            p = L._principal_fizyczna(rng, pools)
        else:
            p = case.principals[i] if i < len(case.principals) and case.principals[i].typ == "osoba_prawna" \
                else L._principal_prawna(rng, pools, 0.0)
            want = n_sig[i] if i < len(n_sig) else 1
            sigs = p.signatories[:want]
            while len(sigs) < want:
                s = L.make_person(rng)
                if s.full in used or s.full in {x.full for x in sigs}:
                    continue
                s.role = rng.choice(L.SIGN_ROLES)
                sigs.append(s)
            p.signatories = sigs
        used |= {s.full for s in p.signatories}
        princ.append(p)
    if len({p.nazwa for p in princ}) < len(princ):
        return make_case(rng, n_principals, n_sig, n_att, fizyczna, pesel)
    case.principals = princ
    case.consortium = n_principals > 1
    return case


def _who(p: L.Principal, ctx: L.Ctx) -> str:
    ids = ", ".join(id_parts(ctx, p))
    if p.typ == "osoba_fizyczna":
        return (f"{esc(p.owner.full)}, prowadzący(a) działalność gospodarczą pod firmą {esc(p.nazwa)}, "
                f"{esc(p.address)}, {ids}")
    return f"{esc(p.nazwa)} z siedzibą: {esc(p.address)}, {ids}"


def _att_dat(ctx: L.Ctx, a: L.Person) -> str:
    t = title_str(ctx.rng, a, "dat")
    s = f"{t + ' ' if t else ''}{a.form('dat')}"
    if a.pesel:
        s += f", PESEL {a.pesel}"
    return s


def _att_acc(ctx: L.Ctx, a: L.Person) -> str:
    t = ctx.rng.choice(["mec.", title_str(ctx.rng, a, "acc")]) if a.title else ""
    s = f"{t + ' ' if t else ''}{a.form('acc')}"
    if a.pesel:
        s += f" (PESEL: {a.pesel})"
    return s


def _proc(ctx: L.Ctx) -> str:
    k = ctx.case
    return f"postępowaniu o udzielenie zamówienia publicznego pn. „{esc(k.procurement['tytul'])}”, prowadzonym przez {esc(k.procurement['zamawiajacy'])}"


def _sig_cells(ctx: L.Ctx, p: L.Principal) -> list:
    cell = [ctx.P(f"<b>Za {esc(p.nazwa)}:</b>", "cell")]
    for sg in p.signatories:
        cell += [ctx.sp(16), ctx.P(ctx.sig_line(), "cell"), ctx.P(f"{esc(sg.full)}" + (f" – {esc(sg.role)}" if sg.role else ""), "cell")]
    return cell


def p01_columns(ctx, v):
    """Principals side by side (Lider | Partner) in a table; signatures per principal."""
    k, r = ctx.case, ctx.rng
    s = [ctx.P(f"{k.city}, dnia {ctx.date()}", "right"), ctx.sp(8), ctx.P("PEŁNOMOCNICTWO", "title")]
    hdr, rows = [], {"Nazwa": [], "Siedziba": [], "KRS": [], "NIP": []}
    for i, p in enumerate(k.principals):
        hdr.append(f"<b>{'Mocodawca 1 – Lider' if i == 0 else f'Mocodawca {i + 1} – Partner'}</b>")
        rows["Nazwa"].append(esc(p.nazwa))
        rows["Siedziba"].append(esc(p.address))
        rows["KRS"].append(p.krs or "nie dotyczy")
        rows["NIP"].append(ctx.nip(p.nip) if p.nip else "—")
    data = [[""] + hdr] + [[k_] + vals for k_, vals in rows.items()]
    w = 140 / len(k.principals)
    s.append(ctx.table(data, [26 * mm] + [w * mm] * len(k.principals), header=True))
    s.append(ctx.sp(8))
    atts = [_att_dat(ctx, a) for a in k.attorneys]
    s.append(ctx.P("Wymienieni wyżej wykonawcy, wspólnie ubiegający się o udzielenie zamówienia, udzielają "
                   + join_pl(atts) + f" pełnomocnictwa do reprezentowania ich w {_proc(ctx)}, w szczególności do: "
                   + "; ".join(scope_items(r)) + "."))
    if k.kio_sygn:
        s.append(ctx.P(f"Pełnomocnictwo dotyczy także sprawy o sygn. akt {esc(k.kio_sygn)}."))
    s.append(ctx.P(r.choice(L.VALIDITY_PL)))
    s.append(ctx.sp(14))
    t = Table([[_sig_cells(ctx, p) for p in k.principals]], hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(t)
    return s


def p02_prose_inflected(ctx, v):
    """One paragraph per principal, signatories inflected after 'reprezentowana przez'."""
    k, r = ctx.case, ctx.rng
    s = [ctx.P(f"{k.city}, {ctx.date()}", "right"), ctx.sp(6), ctx.P("PEŁNOMOCNICTWO", "title")]
    parts = []
    for i, p in enumerate(k.principals):
        if p.typ == "osoba_fizyczna":
            parts.append(_who(p, ctx))
            continue
        sigs = [f"{sg.pan('acc')} {sg.form('acc')}" + (f" – {esc(sg.role)}" if sg.role else "") for sg in p.signatories]
        parts.append(f"{_who(p, ctx)}, reprezentowana przez {join_pl(sigs, ' oraz ')}")
    lead = "<b>" + r.choice(["Mocodawcy:", "My, niżej podpisani:", "Wykonawcy wspólnie ubiegający się o udzielenie zamówienia:"]) + "</b>"
    s.append(ctx.P(lead))
    for i, ptxt in enumerate(parts, 1):
        s.append(ctx.P(f"{i}) {ptxt}" + (";" if i < len(parts) else ","), leftIndent=12))
    many = len(k.attorneys) > 1
    s.append(ctx.P(f"zwani dalej łącznie „Mocodawcami”, niniejszym ustanawiają {'pełnomocnikami' if many else 'pełnomocnikiem'} "
                   + join_pl([_att_acc(ctx, a) for a in k.attorneys], " i ")
                   + f" i upoważniają {'ich' if many else 'go'} do działania w {_proc(ctx)}, w tym do: "
                   + "; ".join(scope_items(r)) + "."))
    s.append(ctx.P(r.choice(L.VALIDITY_PL)))
    s.append(ctx.sp(12))
    for p in k.principals:
        for sg in p.signatories:
            s.append(ctx.P(f"{ctx.sig_line()}<br/>{esc(sg.full)}, {esc(sg.role or 'właściciel')} – {esc(p.nazwa)}", "left"))
            s.append(ctx.sp(8))
    return s


def p03_footer_ids(ctx, v):
    """Company letterhead; the principal's KRS/NIP only in the page footer; many signatories."""
    k, r = ctx.case, ctx.rng
    p = k.principals[0]
    ctx.header = [(p.nazwa, "left"), (p.address, "left")]
    ctx.footer = [(" | ".join(id_parts(ctx, p, regon=True)), "center"), ("strona {page}", "right")]
    s = [ctx.P(f"{k.city}, dnia {ctx.date()}", "right"), ctx.sp(10), ctx.P("Pełnomocnictwo", "title")]
    sigs = [f"{sg.full} ({sg.role})" if sg.role else sg.full for sg in p.signatories]
    s.append(ctx.P(f"Działając w imieniu Spółki pod firmą <b>{esc(p.nazwa)}</b> (dalej: „Mocodawca”), my, niżej podpisani: "
                   + esc(join_pl(sigs)) + ", uprawnieni do łącznej reprezentacji Mocodawcy, udzielamy pełnomocnictwa:"))
    for i, a in enumerate(k.attorneys, 1):
        line = f"{i}. {att_name(r, a)}"
        if a.bar_no:
            line += f", nr wpisu {a.bar_no}"
        if a.pesel:
            line += f", PESEL: {a.pesel}"
        s.append(ctx.P(line, leftIndent=14))
    s.append(ctx.P(f"do {r.choice(['samodzielnego', 'łącznego lub samodzielnego'])} reprezentowania Mocodawcy w {_proc(ctx)}, a w szczególności do: "
                   + "; ".join(scope_items(r)) + "."))
    s.append(ctx.sp(14))
    cells = []
    for sg in p.signatories:
        cells.append([ctx.P(ctx.sig_line(), "cell"), ctx.P(esc(sg.full), "cell"), ctx.P(esc(sg.role or ""), "cell")])
    t = Table([cells], hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(t)
    return s


def p04_kv_forms(ctx, v):
    """'Mocodawca 1' / 'Mocodawca 2' key:value tables and an attorney table."""
    k, r = ctx.case, ctx.rng
    s = [ctx.P("PEŁNOMOCNICTWO", "title"), ctx.P(f"Miejscowość i data: {k.city}, {ctx.date()}", "left"), ctx.sp(6)]
    for i, p in enumerate(k.principals, 1):
        rows = [[f"<b>Mocodawca {i}</b>" if len(k.principals) > 1 else "<b>Mocodawca</b>", ""],
                ["Firma / nazwa:", esc(p.nazwa)], ["Adres:", esc(p.address)]]
        if p.typ == "osoba_fizyczna":
            rows.append(["Imię i nazwisko przedsiębiorcy:", esc(p.owner.full)])
        if p.krs:
            rows.append(["Nr KRS:", p.krs])
        if p.nip:
            rows.append(["NIP:", ctx.nip(p.nip)])
        rows.append(["Reprezentowany przez:", "<br/>".join(f"{esc(sg.full)}" + (f", {esc(sg.role)}" if sg.role else "") for sg in p.signatories)])
        s.append(ctx.table(rows, [48 * mm, 118 * mm]))
        s.append(ctx.sp(6))
    rows = [["Lp.", "Pełnomocnik", "Tytuł zawodowy", "PESEL"]]
    for i, a in enumerate(k.attorneys, 1):
        rows.append([str(i), esc(a.full), title_str(r, a, "nom") or "—", a.pesel or "—"])
    s.append(ctx.P("<b>Pełnomocnicy:</b>", "left"))
    s.append(ctx.table(rows, [12 * mm, 62 * mm, 50 * mm, 42 * mm], header=True))
    s.append(ctx.sp(6))
    s.append(ctx.P(f"Zakres umocowania: reprezentowanie {'Mocodawców' if len(k.principals) > 1 else 'Mocodawcy'} w {_proc(ctx)}, "
                   "w tym " + "; ".join(scope_items(r)) + "."))
    s.append(ctx.sp(14))
    for p in k.principals:
        s.append(ctx.P(f"Podpisy w imieniu: {esc(p.nazwa)}", "left"))
        for sg in p.signatories:
            s.append(ctx.P(f"{ctx.sig_line()} ({esc(sg.full)})", "left"))
        s.append(ctx.sp(8))
    return s


def p05_joint_letter(ctx, v):
    """Joint POA where the leader's signatories also sign for the partner by name, attorneys in dative."""
    k, r = ctx.case, ctx.rng
    s = [ctx.P(f"{k.city}, {ctx.date()}", "right"), ctx.sp(6),
         ctx.P("PEŁNOMOCNICTWO ŁĄCZNE", "title"),
         ctx.P("udzielone przez wykonawców wspólnie ubiegających się o udzielenie zamówienia", "center"), ctx.sp(6)]
    for i, p in enumerate(k.principals):
        tag = "Lider Konsorcjum" if i == 0 else "Członek Konsorcjum"
        s.append(ctx.P(f"<b>{tag}:</b> {_who(p, ctx)}"))
    s.append(ctx.P("udzielają " + join_pl([_att_dat(ctx, a) for a in k.attorneys]) +
                   f" pełnomocnictwa do reprezentowania konsorcjum w {_proc(ctx)}"
                   + (f" oraz w postępowaniu odwoławczym sygn. {esc(k.kio_sygn)}" if k.kio_sygn else "")
                   + ", w szczególności do: " + "; ".join(scope_items(r)) + "."))
    s.append(ctx.P(r.choice(L.VALIDITY_PL)))
    s.append(ctx.sp(12))
    for p in k.principals:
        for sg in p.signatories:
            s.append(ctx.P(f"{ctx.sig_line()}", "left"))
            s.append(ctx.P(f"{esc(sg.full)}" + (f", {esc(sg.role)}" if sg.role else "") + f" (za: {esc(p.nazwa)})", "small"))
            s.append(ctx.sp(6))
    return s


TEMPLATES = {
    "p01_columns": p01_columns,
    "p02_prose_inflected": p02_prose_inflected,
    "p03_footer_ids": p03_footer_ids,
    "p04_kv_forms": p04_kv_forms,
    "p05_joint_letter": p05_joint_letter,
}
