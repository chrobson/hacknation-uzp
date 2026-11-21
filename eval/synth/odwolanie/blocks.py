"""Reusable content blocks for appeal templates (body parts, not layouts)."""

from __future__ import annotations

from reportlab.platypus import KeepTogether, ListFlowable, ListItem

from .core import ATTACHMENTS, REQUESTS, Case, Ctx, Entity, esc

KIO_ADDR = [
    ["Prezes Krajowej Izby Odwoławczej", "ul. Postępu 17A", "02-676 Warszawa"],
    ["Krajowa Izba Odwoławcza", "ul. Postępu 17a", "02-676 Warszawa"],
    ["Do Prezesa Krajowej Izby Odwoławczej", "przy Urzędzie Zamówień Publicznych", "ul. Postępu 17A, 02-676 Warszawa"],
    ["KRAJOWA IZBA ODWOŁAWCZA", "Urząd Zamówień Publicznych", "ul. Postępu 17A", "02-676 Warszawa"],
]


def kio_lines(ctx: Ctx) -> list[str]:
    return ctx.rng.choice(KIO_ADDR)


def place_date(case: Case, ctx: Ctx, style: str | None = None, dnia: bool | None = None) -> str:
    if not case.data:
        return ""
    from .core import DATE_STYLES_HEADER, fmt_date

    style = style or ctx.rng.choice(DATE_STYLES_HEADER)
    if dnia is None:
        dnia = ctx.rng.random() < 0.5
    return f"{case.miejscowosc}, {'dnia ' if dnia else ''}{fmt_date(case.data, style)}"


def entity_lines(e: Entity, ctx: Ctx, ids_one_line: bool | None = None, email: bool = True) -> list[str]:
    lines = [f"<b>{esc(e.nazwa)}</b>", esc(e.address)]
    ids = ctx.id_parts(e)
    if ids:
        if ids_one_line is None:
            ids_one_line = ctx.rng.random() < 0.6
        lines += [", ".join(ids)] if ids_one_line else ids
    if email and e.email and ctx.rng.random() < 0.5:
        lines.append(f"e-mail: {e.email}")
    return lines


def attorney_lines(case: Case, ctx: Ctx, lead: str | None = None) -> list[str]:
    if not case.attorneys:
        return []
    lead = lead or ctx.rng.choice(["reprezentowany przez:", "reprezentowana przez:", "pełnomocnik:",
                                   "działający przez pełnomocnika:"])
    out = [f"{lead} {esc(ctx.attorneys_line(case, ctx.rng.choice(['short', 'short', 'long'])))}"]
    addr = f"{esc(case.firm_nazwa)}, {esc(case.firm_address)}"
    out.append(ctx.rng.choice(["adres do korespondencji: ", "adres do doręczeń: ", ""]) + addr)
    out.append(ctx.rng.choice([f"tel. {case.firm_phone}, e-mail: {case.firm_mail}",
                               f"e-mail: {case.firm_mail}", f"{case.firm_mail}"]))
    return out


def odw_block_lines(case: Case, ctx: Ctx) -> list[str]:
    """Appellant(s) as lines, consortium aware (leader first)."""
    if not case.consortium:
        return entity_lines(case.odw[0], ctx)
    out = [ctx.rng.choice(["Wykonawcy wspólnie ubiegający się o udzielenie zamówienia (Konsorcjum):",
                           "Konsorcjum w składzie:", "Wykonawcy wspólnie ubiegający się o zamówienie:"])]
    for i, e in enumerate(case.odw):
        role = "Lider Konsorcjum" if i == 0 else f"Partner Konsorcjum{'' if len(case.odw) == 2 else f' nr {i}'}"
        out.append(f"{i + 1}) {role}:")
        out += entity_lines(e, ctx, email=False)
    return out


def zam_block_lines(case: Case, ctx: Ctx) -> list[str]:
    if len(case.zams) == 1:
        return entity_lines(case.zams[0], ctx)
    out = [ctx.rng.choice(["zamawiający wspólnie przeprowadzający postępowanie (art. 38 Pzp):",
                           "Zamawiający działający wspólnie:"])]
    for i, z in enumerate(case.zams):
        tag = ctx.rng.choice([" – prowadzący postępowanie", " (Lider, prowadzący postępowanie)",
                              " – pełnomocnik zamawiających prowadzący postępowanie"]) if z.prowadzacy else ""
        out.append(f"{i + 1}) Zamawiający{tag}:")
        out += entity_lines(z, ctx)
    return out


def proc_sentence(case: Case, ctx: Ctx) -> str:
    parts = [f"postępowania o udzielenie zamówienia publicznego prowadzonego w trybie {case.tryb} pn. "
             f"„{esc(case.tytul)}”"]
    labels = {
        "nr": ctx.rng.choice(["nr referencyjny: ", "znak sprawy: ", "numer postępowania: ", "nr sprawy "]),
        "bzp": ctx.rng.choice(["ogłoszenie w BZP nr ", "ogłoszenie o zamówieniu nr ",
                               "ogłoszenie opublikowane w Biuletynie Zamówień Publicznych pod nr "]),
        "ted": ctx.rng.choice(["ogłoszenie w Dz. Urz. UE nr ", "numer ogłoszenia TED: ", "TED: "]),
    }
    for k, v in ctx.proc_parts(case):
        parts.append(labels[k] + esc(v))
    return ", ".join(parts)


def zarzuty_flow(case: Case, ctx: Ctx, numbering: str = "Zarzut nr {i}", heading_style: str = "body") -> list:
    out = []
    for i, z in enumerate(case.zarzuty, 1):
        lbl = numbering.format(i=i, r=["I", "II", "III", "IV", "V"][i - 1], a="abcde"[i - 1])
        out.append(ctx.P(f"<b>{lbl}</b> – {ctx.zarzut(z, 'head')};", heading_style))
    return out


def actions_list(case: Case, ctx: Ctx) -> list:
    items = [ListItem(ctx.P(ctx.zarzut(z, "action") + ";", "just"), leftIndent=14) for z in case.zarzuty]
    return [ListFlowable(items, bulletType="1", bulletFormat="%s)", bulletFontName=ctx.font,
                         bulletFontSize=ctx.size, leftIndent=14)]


def requests_flow(case: Case, ctx: Ctx, title: str = "W związku z powyższym wnoszę o:") -> list:
    reqs = ctx.rng.sample(REQUESTS, ctx.rng.randint(3, len(REQUESTS)))
    out = [ctx.P(title, "bold")]
    out += [ctx.P(f"{i}. {r};") for i, r in enumerate(reqs, 1)]
    return out


def justification(case: Case, ctx: Ctx, title: str = "UZASADNIENIE", n_fill: int = 4) -> list:
    out = [ctx.P(title, "h", alignment=1)]
    out.append(ctx.P(ctx.zarzut(case.first, "fact") + " " + ctx.filler(1)[0], "just"))
    for z in case.zarzuty[1:]:
        out.append(ctx.P(ctx.zarzut(z, "fact"), "just"))
    d = case.extra_dates[0]
    out.append(ctx.P(f"Odwołujący pismem z dnia {ctx.d(d)} zwracał się do Zamawiającego o wyjaśnienia, "
                     f"jednak nie uzyskał odpowiedzi. " + " ".join(ctx.filler(2)), "just"))
    for f in ctx.filler(n_fill):
        out.append(ctx.P(f, "just"))
    return out


def signature(case: Case, ctx: Ctx, align: str = "right") -> list:
    st = "right" if align == "right" else "body"
    if case.attorneys:
        names = [a.with_title("short") for a in case.attorneys[: ctx.rng.choice([1, len(case.attorneys)])]]
        lines = ["..............................", "<br/>".join(esc(n) for n in names),
                 ctx.rng.choice(["pełnomocnik Odwołującego", "(podpisano kwalifikowanym podpisem elektronicznym)", ""])]
    else:
        lines = ["..............................", esc(case.signer), f"{case.signer_role}",
                 "(kwalifikowany podpis elektroniczny)"]
    return [ctx.gap(6), KeepTogether([ctx.P(l, st) for l in lines if l])]


def attachments(case: Case, ctx: Ctx, title: str = "Załączniki:") -> list:
    items = ctx.rng.sample(ATTACHMENTS[:5], ctx.rng.randint(2, 5))
    if case.consortium:
        items.append("umowa konsorcjum")
    return [ctx.gap(3), ctx.P(title, "bold")] + [ctx.P(f"{i}. {esc(x)}", "small") for i, x in enumerate(items, 1)]


def legal_basis(case: Case, ctx: Ctx) -> str:
    who = esc(case.odw[0].nazwa) if not case.consortium else "wykonawców wspólnie ubiegających się o udzielenie zamówienia"
    return (f"Działając w imieniu {who} (dalej: „Odwołujący”)"
            + (", na podstawie załączonego pełnomocnictwa" if case.attorneys else "")
            + ", na podstawie art. 505 ust. 1 i art. 513 pkt 1 i 2 ustawy z dnia 11 września 2019 r. – "
              "Prawo zamówień publicznych (t.j. Dz. U. z 2024 r. poz. 1320 ze zm., dalej: „Pzp”) wnoszę "
              "odwołanie wobec niezgodnych z przepisami ustawy czynności i zaniechań Zamawiającego, polegających na:")
