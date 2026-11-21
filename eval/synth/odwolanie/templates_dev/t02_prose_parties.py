"""No labelled party blocks: parties described in running prose, attorney inflected."""

from .. import blocks as B
from ..core import build_simple, esc


NAME = "dev_t02_prose_parties"
OVERRIDES = {}


def _entity_prose(e, ctx, verb_seat="z siedzibą w"):
    city = e.address.split(" ")[-1]
    bits = [f"{esc(e.nazwa)} {verb_seat} {esc(city)} ({esc(e.address)})"]
    if e.krs:
        bits.append(f"wpisana do rejestru przedsiębiorców Krajowego Rejestru Sądowego pod numerem KRS {ctx.krs(e.krs)}")
    ids = []
    if e.nip:
        ids.append(f"NIP {ctx.nip(e.nip)}")
    if e.regon:
        ids.append(f"REGON {ctx.regon(e.regon)}")
    if ids:
        bits.append("posiadająca " + " oraz ".join(ids))
    return ", ".join(bits)


def render(case, ctx, path):
    s = []
    pd = B.place_date(case, ctx, dnia=True)
    if pd:
        s.append(ctx.P(esc(pd), "right"))
    s.append(ctx.gap(4))
    s.append(ctx.P("<br/>".join(B.kio_lines(ctx)), "body", leftIndent=230))
    s.append(ctx.P("ODWOŁANIE", "title"))
    lead = case.odw[0]
    if case.consortium:
        partners = "; ".join(_entity_prose(e, ctx) for e in case.odw[1:])
        who = (f"Odwołującym są wykonawcy wspólnie ubiegający się o udzielenie zamówienia: lider konsorcjum – "
               f"{_entity_prose(lead, ctx)}, oraz partner – {partners}")
    else:
        who = f"Odwołującym jest {_entity_prose(lead, ctx)}"
    if case.attorneys:
        a0 = case.attorneys[0]
        rest = case.attorneys[1:]
        att = f", reprezentowana przez pełnomocnika – {esc(a0.inflected('acc'))}"
        if rest:
            att += " oraz " + ", ".join(esc(a.inflected("acc")) for a in rest)
        att += (f", z kancelarii działającej pod firmą {esc(case.firm_nazwa)} ({esc(case.firm_address)}), "
                f"adres e-mail do doręczeń: {case.firm_mail}")
        who += att
    s.append(ctx.P(who + ".", "just"))
    if len(case.zams) == 1:
        z = case.zams[0]
        s.append(ctx.P(f"Odwołanie wnoszone jest przeciwko Zamawiającemu, którym jest {_entity_prose(z, ctx)}.", "just"))
    else:
        parts = []
        for z in case.zams:
            tag = " – prowadzący postępowanie w imieniu wszystkich zamawiających" if z.prowadzacy else ""
            parts.append(_entity_prose(z, ctx) + tag)
        s.append(ctx.P("Postępowanie przeprowadzają wspólnie zamawiający: " + "; ".join(parts) + ".", "just"))
    s.append(ctx.P("Odwołanie dotyczy " + B.proc_sentence(case, ctx) + ".", "just"))
    s.append(ctx.P(B.legal_basis(case, ctx), "just"))
    s += B.actions_list(case, ctx)
    s.append(ctx.P("Zamawiającemu zarzucam:", "body"))
    s += B.zarzuty_flow(case, ctx, numbering=ctx.rng.choice(["{i}.", "Zarzut {i}", "{r}."]))
    s += B.requests_flow(case, ctx, title="Wnoszę o:")
    s += B.justification(case, ctx, title="Uzasadnienie", n_fill=5)
    s += B.signature(case, ctx, align=ctx.rng.choice(["right", "left"]))
    s += B.attachments(case, ctx)
    build_simple(path, s, ctx, footer=ctx.rng.choice(["- {p} -", "Strona {p} z {n}"]), margins=(25, 25, 20, 20))
