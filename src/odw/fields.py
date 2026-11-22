"""Generic, YAML-configured field extraction.

A class YAML lists fields by output path (e.g. ``przelew_bankowy.kwota``). Each field has one spec or a list of
specs tried in order until one returns a value. Spec types:

  pattern          regex over the whole text; group 1 (or the whole match) is the value
  labeled          find a label, then the first value of ``value`` kind in the window after it
                   (value: date | amount | token | account | regex)
  text_after_label text that follows a label, across lines, until a stop label
  account          26-digit account by role (sender/receiver) decided by the nearest preceding keyword
  near             first value of a kind after a role keyword, before a competing role (layout-independent)
  first_line, exists, keyword_map, names, llm: see the functions below

New document classes reuse these types through configuration only.
"""

from __future__ import annotations

import re
import datetime as _dt
from typing import Any, Callable

from . import normalize as N
from .config import fold

FLAGS = re.IGNORECASE | re.MULTILINE


def _compile(patterns: list[str] | str, folded: bool = False) -> list[re.Pattern[str]]:
    """`folded`: the pattern with Polish diacritics removed, to be matched against fold(text). fold() is 1:1 per
    character, so match positions on the folded text are valid positions in the original text."""
    if isinstance(patterns, str):
        patterns = [patterns]
    return [re.compile(fold(p) if folded else p, FLAGS) for p in patterns]


def _finder(kind: str, spec: dict[str, Any]) -> Callable[[str], Any]:
    if kind == "date":
        return N.find_date
    if kind == "amount":
        return N.find_amount
    if kind == "account":
        return lambda s: (m := N.ACCOUNT_RE.search(s)) and N.account_value(m)
    if kind == "token":
        tok = re.compile(spec.get("token_pattern", r"[A-Z0-9][A-Z0-9./\-]{3,}"), re.IGNORECASE)
        return lambda s: (m := tok.search(s)) and m.group(0).rstrip(".,;")
    if kind == "company":
        return N.find_company
    if kind == "lawfirm":
        return find_lawfirm
    if kind in N.ID_PATTERNS:
        return lambda s: N.find_id(kind, s)
    if kind == "regex":
        rx = re.compile(spec["value_pattern"], FLAGS)
        # a value that spans a line break is one string in the output: "Kancelaria Radców\nPrawnych" → single spaces
        return lambda s: (m := rx.search(s)) and " ".join((m.group(1) if m.groups() else m.group(0)).split())
    raise ValueError(f"unknown value kind: {kind}")


class Context:
    """Per-document state shared by field specs (e.g. account roles computed once)."""

    def __init__(self, text: str, class_cfg: dict[str, Any], n_items: int = 1):
        self.text = text
        self.cfg = class_cfg
        self.n_items = n_items  # number of items in the enclosing list (for list-relative fields)
        self.label = ""  # the split label that introduced this list item (e.g. "1) Zamawiający – Lider:")
        self.index = 0  # position of this item in the enclosing list
        self._accounts: dict[str, str] | None = None
        self._sections: dict[str, str | None] = {}
        self.values: dict[str, Any] = {}  # fields extracted so far (path → value), for cross-field checks
        self.item_text: str | None = None  # inside a list: the current item's own block (also from document scope)
        self.item: dict[str, Any] | None = None

    def section(self, name: str) -> str | None:
        """Text after the section's start label up to the next section start or end label."""
        if name not in self._sections:
            self._sections[name] = _section_text(self.text, name, self.cfg.get("sections", {}))
        return self._sections[name]

    def sub(self, text: str, n_items: int = 1) -> "Context":
        return Context(text, self.cfg, n_items)

    def accounts(self) -> dict[str, str]:
        if self._accounts is None:
            self._accounts = _assign_accounts(self.text, self.cfg.get("accounts", {}))
        return self._accounts


def _section_text(text: str, name: str, sections: dict[str, Any]) -> str | None:
    """Text after the section's start label up to the next section start or end label.

    `resume_after: [other, …]`: a block of one of those sections inside this one (e.g. party blocks between a short
    "wnoszę odwołanie" and the charges) is cut out instead of ending this section, which resumes after the block.
    """
    spec = sections.get(name)
    if spec is None:
        raise KeyError(f"unknown section: {name}")
    out = _section_pass(text, text, name, sections, False)
    if out is None:  # start label not found: diacritics lost by a font map / OCR ("Zamawiajacy:") → folded retry
        out = _section_pass(text, fold(text), name, sections, True)
    return out


def _section_pass(orig: str, text: str, name: str, sections: dict[str, Any], folded: bool) -> str | None:
    """One pass of _section_text: labels are searched in `text` (possibly folded), pieces are cut from `orig`."""
    spec = sections[name]
    start = None
    for rx in _compile(spec["start"], folded):
        m = rx.search(text)
        if m and (start is None or m.start() < start.start()):
            start = m
    if start is None:
        return None
    resume = set(spec.get("resume_after", []))
    missing = _compile(spec["restart_if_missing"], folded)[0] if "restart_if_missing" in spec else None
    restart_at = _compile(spec["restart_at"], folded)[0] if "restart_at" in spec else None
    pieces, pos, restarted = [], start.end(), False
    for _ in range(8):  # at most a few embedded blocks
        end, owner, owner_match = _next_ender(text, name, sections, pos, folded)
        pieces.append(orig[pos:end])
        if owner in resume and owner_match is not None:
            pos, _, _ = _next_ender(text, owner, sections, owner_match.end(), folded)  # skip the embedded block
        elif (missing and restart_at and not restarted and owner is not None
              and not missing.search(text[start.end():end]) and (m := restart_at.search(text, end))):
            # cut off before any content: resume once at the line of the next content keyword
            restarted, pos = True, text.rfind("\n", 0, m.start()) + 1
        else:
            break
        if pos >= len(text):
            break
    return "\n".join(pieces)


def _next_ender(text: str, name: str, sections: dict[str, Any], pos: int, folded: bool = False):
    """(position, owning section, match) of the first label after `pos` that ends section `name`."""
    spec = sections[name]
    enders: list[tuple[re.Pattern[str], str]] = []
    for other, ospec in sections.items():
        if other != name and not ospec.get("isolated"):  # isolated: a fallback section that never ends the others
            enders += [(rx, other) for rx in _compile(ospec["start"], folded)]
    enders += [(rx, "_end") for rx in _compile(sections.get("_end", {}).get("start", []), folded)]
    enders += [(rx, "_end") for rx in _compile(spec.get("end", []), folded)]
    best = (len(text), None, None)
    for rx, owner in enders:
        m = rx.search(text, pos)
        if m and m.start() < best[0]:
            best = (m.start(), owner, m)
    return best


def _assign_accounts(text: str, cfg: dict[str, Any]) -> dict[str, str]:
    sender = _compile(cfg.get("sender_keywords", []))
    receiver = _compile(cfg.get("receiver_keywords", []))
    lookback = int(cfg.get("lookback_chars", 150))
    found: list[tuple[str, str | None]] = []  # (account, role)
    anchors: list[int] = []  # absolute position of the keyword that decided each account's role
    last_kw: list[dict[str, int]] = []  # last position of each role's keyword before each account
    spans: list[tuple[int, int]] = []
    for m in N.ACCOUNT_RE.finditer(text):
        if not m.group("num"):
            continue
        acct = N.digits(m.group("num"))
        if any(a == acct for a, _ in found):
            continue
        base = max(0, m.start() - lookback)
        window = text[base : m.start()]
        best_role, best_pos = None, -1
        per_role: dict[str, int] = {}
        for role, rxs in (("sender", sender), ("receiver", receiver)):
            for rx in rxs:
                for km in rx.finditer(window):
                    per_role[role] = max(per_role.get(role, -1), base + km.start())
                    if km.end() > best_pos:
                        best_role, best_pos = role, km.end()
        found.append((acct, best_role))
        anchors.append(base + best_pos if best_role else -1)
        last_kw.append(per_role)
        spans.append(m.span())
    # Column layout ("Płatnik  Beneficjent" header above "acct1  acct2"): both accounts are decided by the same
    # keyword. Map them by the left-to-right order of the role keywords in that header instead.
    same_line = len(spans) >= 2 and "\n" not in text[spans[0][1] : spans[1][0]]
    if len(found) >= 2 and (same_line or anchors[0] == anchors[1] != -1) and len(last_kw[0]) == 2:
        first_role = min(last_kw[0], key=last_kw[0].get)
        second_role = "receiver" if first_role == "sender" else "sender"
        found[0], found[1] = (found[0][0], first_role), (found[1][0], second_role)
    roles: dict[str, str] = {}
    for acct, role in found:
        if role and role not in roles:
            roles[role] = acct
    accts = [a for a, _ in found]
    # The number as printed: "PL" prefix kept when any occurrence of that number carries it in the document.
    prefixed = {N.digits(m.group("num")) for m in N.ACCOUNT_RE.finditer(text) if m.group("pl") and m.group("num")}

    def printed(r: dict[str, str]) -> dict[str, str]:
        return {role: ("PL" + a if a in prefixed else a) for role, a in r.items()}

    # Domain prior (config): the payee of a KIO fee / stamp duty is a public office. If exactly one of the first
    # two accounts is a configured payee account (always) or, when the role keywords left the roles undecided,
    # has an owner line naming such an office, it is the receiver.
    hints = _compile(cfg.get("receiver_hints", []))
    known = {N.digits(str(k)) for k in cfg.get("known_receivers", [])}
    decided = len(roles) == 2 and roles.get("sender") != roles.get("receiver")
    if len(accts) >= 2 and (hints or known):
        def hinted(i: int) -> bool:
            if accts[i] in known:
                return True
            if decided:  # owner-line hints only break ties; role keywords that already decided both roles win
                return False
            nxt = spans[i + 1][0] if i + 1 < len(spans) else len(text)
            after = "\n".join(text[spans[i][1] : min(nxt, spans[i][1] + 200)].split("\n")[:3])
            return any(h.search(after) for h in hints)

        flags = [hinted(0), hinted(1)]
        if flags[0] != flags[1]:
            r = 0 if flags[0] else 1
            return printed({"receiver": accts[r], "sender": accts[1 - r]})
    # Two accounts but roles missing or clashing (e.g. two-column layout): document order = sender, receiver.
    if len(accts) >= 2 and (len(roles) < 2 or roles.get("sender") == roles.get("receiver")):
        if "sender" in roles and roles["sender"] in accts[:2]:
            roles["receiver"] = next(a for a in accts if a != roles["sender"])
        elif "receiver" in roles and roles["receiver"] in accts[:2]:
            roles["sender"] = next(a for a in accts if a != roles["receiver"])
        else:
            roles = {"sender": accts[0], "receiver": accts[1]}
    return printed(roles)


def _labeled(spec: dict[str, Any], ctx: Context) -> Any:
    find = _finder(spec.get("value", "token"), spec)
    window = int(spec.get("window", 160))
    rejects = _compile(spec.get("reject_before", []))
    back = int(spec.get("reject_before_window", 60))
    # second pass only when the exact labels gave nothing: labels with diacritics folded ("Tytul przelewu")
    for folded in (False, True):
        hay = fold(ctx.text) if folded else ctx.text
        hits = []
        for rank, rx in enumerate(_compile(spec["labels"], folded)):
            hits.extend((rank, m) for m in rx.finditer(hay))
        # default: earliest label in the document; `label_priority`: labels in the YAML order (strongest first)
        order = (lambda h: (h[0], h[1].start())) if spec.get("label_priority") else (lambda h: h[1].start())
        for _, m in sorted(hits, key=order):
            # `reject_before`: the label belongs to a citation ("ustawy z dnia 11 września 2019 r.", "KRS z dnia")
            if rejects and any(r.search(ctx.text[max(0, m.start() - back) : m.start()]) for r in rejects):
                continue
            after = ctx.text[m.end() : m.end() + window].lstrip(" \t:.…")
            value = find(after)
            if value not in (None, "") and _plausible_date(spec, ctx, value):
                return value
    return None


def _plausible_date(spec: dict[str, Any], ctx: Context, value: Any) -> bool:
    """`within_days: [lo, hi]` + `of_field: path`: the date lies lo..hi days BEFORE that field's value (e.g. the
    challenged act 1–25 days before the appeal's own date). Unknown reference date or unparsable value → accepted,
    unless `strict: true` (a whole-document fallback that is only safe inside the window)."""
    if "within_days" not in spec:
        return True
    ref = ctx.values.get(spec.get("of_field", ""))
    try:
        days = (_dt.date.fromisoformat(str(ref)) - _dt.date.fromisoformat(str(value))).days
    except (TypeError, ValueError):
        return not spec.get("strict")
    lo, hi = spec["within_days"]
    return lo <= days <= hi


def _text_after_label(spec: dict[str, Any], ctx: Context) -> Any:
    value = _text_after_label_pass(spec, ctx.text, False)
    # exact labels gave nothing: retry with diacritics folded in labels and stops (value still cut from the original)
    return value if value is not None else _text_after_label_pass(spec, ctx.text, True)


def _text_after_label_pass(spec: dict[str, Any], text: str, folded: bool) -> Any:
    stops = _compile(spec.get("stop_labels", []), folded)
    max_lines = int(spec.get("max_lines", 4))
    f = fold if folded else (lambda s: s)
    for rx in _compile(spec["labels"], folded):
        m = rx.search(f(text))
        if not m:
            continue
        rest = text[m.end() :].lstrip(" \t:")
        lines = rest.split("\n")
        taken: list[str] = []
        inline = spec.get("inline_stops", False)
        for i, line in enumerate(lines[: max_lines + 1]):
            if i > 0 and any(s.match(f(line)) for s in stops):
                break
            if inline:  # a following field glued onto the same line ("… CEN123 zł 17,00 zrealizowano …")
                cut = min((sm.start() for s in stops if (sm := s.search(f(line), 1))), default=None)
                if cut is not None:
                    taken.append(line[:cut])
                    break
            if line.strip():
                taken.append(line)
            if "”" in line:  # closing quote ends a quoted title
                break
        value = N.clean_text(" ".join(taken).split("”")[0])
        if value:
            return value
    return None


# Address / contact fragments that a two-column layout glues into the middle of a name.
_INSERTS = re.compile(
    r"\s*,?\s*(?:ul\.|al\.|pl\.|os\.)\s[^,\n]{1,60}?,\s*\d{2}-\d{3}\s+[A-ZĄĆĘŁŃÓŚŹŻ][\w-]*(?:[ \t]+[A-ZĄĆĘŁŃÓŚŹŻ][\w-]*)?"
    r"|\s*,?\s*(?:e-?mail|tel\.?|fax)\s*:?\s*[\w.+@()-]+(?:\s\d+)*"
)


def _pattern(spec: dict[str, Any], ctx: Context) -> Any:
    rejects = _compile(spec.get("reject", []))
    for rx in _compile(spec["pattern"]):
        m = next((m for m in rx.finditer(ctx.text) if not any(r.search(m.group(1) if m.groups() else m.group(0)) for r in rejects)), None)
        if m:
            if "format" in spec:  # e.g. "{1}/BZP{2}" with regex groups; missing groups become ""
                groups = [m.group(0)] + [g or "" for g in m.groups()]
                for idx, width in (spec.get("pad") or {}).items():  # "00364525" → "364525"; "1234" → "001234"
                    if groups[int(idx)]:
                        groups[int(idx)] = str(int(groups[int(idx)])).zfill(int(width))
                value = spec["format"].format(*groups)
                return "".join(value.split()) if spec.get("nospace") else value
            value = m.group(1) if m.groups() else m.group(0)
            value = N.digits(value) if spec.get("digits") else N.clean_text(value) if spec.get("clean") else value
            if spec.get("strip_inserts") and isinstance(value, str):
                value = N.clean_text(_INSERTS.sub(" ", value))
            if "require" in spec and not any(r.search(value) for r in _compile(spec["require"])):
                continue  # implausible value (e.g. a law-firm field without any law-firm word): try next pattern
            if spec.get("titlecase") or spec.get("nominative"):
                from .names import nominative, titlecase_upper

                value = titlecase_upper(value) if spec.get("titlecase") else value
                value = nominative(value) if spec.get("nominative") else value
            return value
    return None


def _account(spec: dict[str, Any], ctx: Context) -> Any:
    return ctx.accounts().get(spec["role"])


def _first_line(spec: dict[str, Any], ctx: Context) -> Any:
    """First non-empty line; `cut` patterns trim what a wider layout may append (address, identifiers)."""
    skips = _compile(spec.get("skip", []))
    cuts = _compile(spec.get("cut", []))
    for line in ctx.text.lstrip(" \t:").split("\n"):
        for rx in cuts:
            m = rx.search(line)
            if m and m.start() > 0:
                line = line[: m.start()]
        line = N.clean_text(line)
        if line and not any(rx.search(line) for rx in skips):
            # `reject`: the first real line is not a plausible value (e.g. "1. uwzględnienie odwołania") → null
            return None if any(rx.search(line) for rx in _compile(spec.get("reject", []))) else line
    return None


def _exists(spec: dict[str, Any], ctx: Context) -> Any:
    if spec.get("only_if_multiple") and ctx.n_items < 2:
        return None
    hay = ctx.label if spec.get("in_label") else ctx.text
    pats = spec["pattern"] if isinstance(spec["pattern"], list) else [spec["pattern"]]
    pats = [p.replace("{n}", str(ctx.index + 1)) for p in pats]  # {n}: 1-based number of the current list item
    hit = any(rx.search(hay) for rx in _compile(pats))
    yes, no = spec.get("if_true", spec.get(True, 1)), spec.get("if_false", spec.get(False, 0))
    return yes if hit else no


def _keyword_map(spec: dict[str, Any], ctx: Context) -> Any:
    """Return the key whose pattern matches earliest in the text (optionally after an anchor)."""
    key = _keyword_map_pass(spec, ctx.text, False)
    # nothing matched: retry on text and patterns with diacritics folded
    return key if key is not None else _keyword_map_pass(spec, fold(ctx.text), True)


def _keyword_map_pass(spec: dict[str, Any], text: str, folded: bool) -> Any:
    if "after" in spec:
        m = next((m for rx in _compile(spec["after"], folded) if (m := rx.search(text))), None)
        if m is None:
            return None
        text = text[m.end() : m.end() + int(spec.get("window", 600))]
    if "until" in spec:
        cut = _compile(spec["until"], folded)[0].search(text)
        if cut:
            text = text[: cut.start()]
    best_key, best_pos = None, len(text) + 1
    for key, patterns in spec["map"].items():
        for rx in _compile(patterns, folded):
            m = rx.search(text)
            if m and m.start() < best_pos:
                best_key, best_pos = key, m.start()
    return best_key


NAME = r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?"
_LEGAL_AFTER = re.compile(r"[ \t]*(?:sp\.|spółk|s\.\s?a\.|sp\s*\.?\s*z\s*o)", re.IGNORECASE)
_LEGAL_FORM = re.compile(r"\bS\.\s?A\.|\b[Ss]p\.|\b[Ss]półk", re.IGNORECASE)


def _names(spec: dict[str, Any], ctx: Context) -> Any:
    """All person names in a region → list of items ``{field: name}`` (deduplicated, document order).

    pattern     regex whose group 1 is the name (default: two capitalised words on one line)
    after       optional regex; search only after its first match (e.g. the signature block)
    exclude_from  output path of another field whose names are excluded (e.g. representatives)
    field       output key of the name in each item (default imie_nazwisko)
    company_field  key of the list item's company name, used by assign_to_item (default nazwa)
    stopwords   first/last words that mark a role, not a name (e.g. Prezes, Zarządu)
    not_in      path inside the current list item (e.g. data.nazwa): a name that is part of that company name
                (with a legal form: S.A., sp., spółka) is a company word, not a person ("Tervana Systemy")
    min_word_len  every word of a name at least this long (OCR debris such as "Pawia Il")
    """
    text = ctx.text
    segmented = False
    if "segment_by" in spec and ctx.n_items > 1:  # one segment per list item, e.g. "W imieniu <firma>:" blocks
        parts = re.split(spec["segment_by"], text, flags=FLAGS)
        if len(parts) - 1 >= ctx.n_items:
            text, segmented = parts[ctx.index + 1], True
    if "after" in spec and not segmented:
        m = next((m for rx in _compile(spec["after"]) if (m := rx.search(text))), None)
        if m is None:
            return None
        text = text[m.start() :]
    pats = spec.get("pattern", rf"({NAME}[ \t]+{NAME})")
    rxs = [re.compile(p, re.MULTILINE) for p in (pats if isinstance(pats, list) else [pats])]
    attrs = {k: re.compile(v, FLAGS) for k, v in spec.get("attrs", {}).items()}
    stop = {w.lower() for w in spec.get("stopwords", [])}
    exclude = set(ctx.cfg.get("_excluded_names", {}).get(spec.get("exclude_from", ""), []))
    field = spec.get("field", "imie_nazwisko")
    company = _get_path(ctx.item, spec["not_in"]) if spec.get("not_in") and isinstance(ctx.item, dict) else None
    if not (isinstance(company, str) and _LEGAL_FORM.search(company)):
        company = None
    min_len = int(spec.get("min_word_len", 1))
    items: list[dict[str, Any]] = []
    tails: list[str] = []
    matches = sorted((m for rx in rxs for m in rx.finditer(text)), key=lambda m: m.start())
    from .names import nominative, titlecase_upper

    for m in matches:
        name = " ".join(m.group(1).split())
        if spec.get("titlecase"):
            name = titlecase_upper(name)
        if spec.get("nominative"):
            name = nominative(name)
        words = name.split()
        if any(w.lower() in stop for w in words) or name in exclude or any(i[field] == name for i in items):
            continue
        if any(len(w) < min_len for w in words) or (company and " ".join(m.group(1).split()) in company):
            continue
        if words[-1] in ("Sp", "Spółka", "Spółki") or _LEGAL_AFTER.match(text, m.end()):
            continue  # a company name ("Malik Development Spółka z o.o.", "AG-Complex Sp. z o.o."), not a person
        if "reject_context" in spec:  # e.g. a board member: "Jan Kowalski – Prezes Zarządu" is not a representative
            around = text[max(0, m.start(1) - 40) : m.end(1) + 50]
            if any(r.search(around) for r in _compile(spec["reject_context"])):
                continue
        item: dict[str, Any] = {field: name, **spec.get("extra", {})}
        tail = text[m.end() : m.end() + 60]
        for key, arx in attrs.items():  # e.g. PESEL written right after the name
            am = arx.search(tail)
            if am:
                item[key] = am.group(1)
        items.append(item)
        tails.append(text[m.end() : m.end() + 120])
    if spec.get("assign_to_item") and not segmented and ctx.n_items > 1 and ctx.item_text and items:
        items = _assign_to_item(items, tails, field, ctx, spec.get("company_field", "nazwa")) or items
    return items or None


def _assign_to_item(items: list[dict[str, Any]], tails: list[str], field: str, ctx: Context,
                    company_field: str = "nazwa") -> list[dict[str, Any]]:
    """Several principals sign one document: keep the names that belong to the current one — the surname occurs in its
    own block ("Reprezentowany przez …") or the signature is followed by its name in brackets ("(Alfa sp. z o.o.)")."""
    own = ctx.item_text.lower()
    company = _first_str(ctx.item, company_field)
    key = company.lower()[:12] if company else None
    kept = []
    for it, tail in zip(items, tails):
        surname = it[field].split()[-1].lower()
        bracket = re.match(r"[^\n(]{0,40}\n?[^\n(]{0,60}?\(([^)\n]{3,})\)", tail)
        if key and bracket:
            if bracket.group(1).lower().startswith(key[:8]):
                kept.append(it)
            continue  # signature attributed to some company: only that company keeps it
        stem = surname[:-1] if len(surname) > 4 else surname  # tolerate case endings (Kowalski / Kowalskiego)
        if stem in own:
            kept.append(it)
    return kept


def _first_str(item: dict[str, Any] | None, key: str = "nazwa") -> str | None:
    """The item's name: first non-empty `key` (possibly nested, e.g. data.nazwa)."""
    if not isinstance(item, dict):
        return None
    if isinstance(item.get(key), str) and item[key]:
        return item[key]
    for v in item.values():
        if isinstance(v, dict) and (r := _first_str(v, key)):
            return r
    return None


def _llm(spec: dict[str, Any], ctx: Context) -> Any:
    """Last-resort LLM question (only when enabled). The YAML gives the question and a JSON schema."""
    from . import llm

    if not llm.enabled():
        return None
    text = _excerpt(ctx.text, spec["excerpt"]) if "excerpt" in spec else ctx.text
    if "max_chars" in spec:
        text = text[: int(spec["max_chars"])]
    choices = spec.get("choices")  # {"word key": output value}: small models pick word labels far better than numbers
    if choices:
        value = llm.ask(spec["question"], text, {"type": "string", "enum": list(choices)})
        if value is None:
            return None
        value = choices[value]
        # evidence: {value: [patterns]} — reject a label none of whose keywords occurs in the passage (a guess)
        need = (spec.get("evidence") or {}).get(value)
        if need and not any(rx.search(text) for rx in _compile(need)):
            return None
        return value
    value = llm.ask(spec["question"], text, spec.get("schema", {"type": "string"}))
    if value is not None and spec.get("value") == "date":
        value = N.find_date(str(value))
        # the date must be written in the passage (any format), not computed or invented
        if value and spec.get("date_in_text") and value not in {d for d in _all_dates(text)}:
            return None
        # an act precedes the letter: reject the letter's own date and anything later (before_field: path of that date)
        limit = ctx.values.get(spec["before_field"]) if "before_field" in spec else None
        if value and limit and value >= limit:
            return None
    if value is not None and spec.get("verbatim") and _squash(str(value)) not in _squash(text):
        return None  # the model must quote the document, never paraphrase or invent
    return value


def _all_dates(text: str) -> list[str]:
    out, pos = [], 0
    while (m := N.DATE_RE.search(text, pos)):
        d = N.find_date(m.group(0))
        if d:
            out.append(d)
        pos = m.end()
    return out


def _squash(s: str) -> str:
    return " ".join(s.lower().replace("„", '"').replace("”", '"').split())


def _excerpt(text: str, cfg: dict[str, Any]) -> str:
    """The passage the model sees: from the FIRST start pattern (in priority order) that occurs, to the earliest end
    pattern after it; when no start pattern occurs, the head of the document (`fallback_chars`)."""
    for rx in _compile(cfg.get("start", [])):
        m = rx.search(text)
        if m:
            seg = text[m.start():]
            ends = [e.start() for erx in _compile(cfg.get("end", [])) if (e := erx.search(seg, len(m.group(0)) + 1))]
            return seg[: min(ends, default=len(seg))]
    return text[: int(cfg.get("fallback_chars", 2500))]


def _near(spec: dict[str, Any], ctx: Context) -> Any:
    """Layout-independent: the first value of a kind found after a role keyword, before any competing role keyword.

    anchors  role keywords (e.g. 'Zamawiając\\w*', 'Instytucja\\s+zamawiająca')
    value    date | amount | account | token | regex | company | nip | krs | regon | pesel | email
    stop     keywords of other roles; the search window ends at the first one (e.g. 'Odwołując\\w*')
    window   max characters after the anchor (default 400)
    """
    find = _finder(spec.get("value", "token"), spec)
    window = int(spec.get("window", 400))
    stops = _compile(spec.get("stop", []))
    hits = sorted((m for rx in _compile(spec["anchors"]) for m in rx.finditer(ctx.text)), key=lambda m: m.start())
    before = int(spec.get("before", 0))  # also look this many characters before the anchor (nearest value wins)
    # the backward scan ends at its own stops (default: `stop`), e.g. a blank line closing the other party's block
    back_stops = _compile(spec["before_stop"]) if "before_stop" in spec else stops
    for m in hits:
        if before:
            prev = ctx.text[max(0, m.start() - before) : m.start()]
            cut = max((sm.end() for rx in back_stops for sm in rx.finditer(prev)), default=0)
            if spec.get("value") == "company":  # a name starts a line of the block: earliest such match
                starts = [cut] + [cut + k + 1 for k, ch in enumerate(prev[cut:]) if ch == "\n"]
                for j in starts:
                    value = find(prev[j:])
                    if value not in (None, "") and prev[j:].lstrip()[:3] == value[:3]:
                        return value
            else:  # identifiers: the value nearest to the anchor (token boundaries backwards, first hit wins)
                for i in range(len(prev) - 1, cut - 1, -1):
                    if i > cut and not (prev[i - 1].isspace() or prev[i - 1] in ",;:(") or prev[i].isspace():
                        continue
                    value = find(prev[i:])
                    if value not in (None, ""):
                        return value
        end = m.end() + window
        while end < len(ctx.text) and not ctx.text[end].isspace():  # never cut a token at the window edge
            end += 1
        seg = ctx.text[m.end() : end]
        cut = min((sm.start() for rx in stops if (sm := rx.search(seg))), default=len(seg))
        value = find(seg[:cut])
        if value not in (None, ""):
            return value
    return None


# ---- law firm of a representative (Odwołujący's pełnomocnik) -------------------------------------------------------
_UP = "A-ZĄĆĘŁŃÓŚŹŻ"
_LF_MARKER = re.compile(r"Kancelari|Adwokac|\bRadc|Prawn[aiy]\b|Prawnicz|Legal|\bLaw\b|Partners|Wspólni|Partnerzy"
                        r"|Spółka\s+Partnersk|\bsp\.\s?p\.|Attorney|\bLex\b", re.IGNORECASE)
# labels that introduce the firm name itself: the next text is the firm even without a law-firm word
_LF_INTRO = re.compile(r"^(?:.*\b(?:z\s+(?-i:kancelari\w*(?:\s+prawn\w*)?)|z\s+(?=(?-i:Kancelari))|pod\s+firmą)|(?:Law\s+firm\s*/\s*)?Kancelaria\s*:|"
                       r"Nazwa\s+kancelarii\s*:?)\s*", re.IGNORECASE)
_LF_ADDR_LABEL = re.compile(r"^(?:adres\w*\s+(?:do|dla)\s+(?:korespondencji|doręczeń)|Law\s+firm\s*/\s*Kancelaria"
                            r"(?=\s+Kancelari))\s*[:–-]?\s*", re.IGNORECASE)
_LF_PERSON = re.compile(r"^.*?\b(?:adw\.|(?-i:adwokat\w*|radc\w*\s+prawn\w*)|r\.\s*pr\.|mec\.|apl\.\s*\w+\.?)\s+"
                        rf"(?-i:[{_UP}]\w+(?:\s+[{_UP}][\w-]+)?)(?:\s*[,;–—-]\s*|\s+|$)", re.IGNORECASE)
_LF_NOT = re.compile(r"^(?:ul\.|al\.|pl\.|os\.|tel|fax|e-?mail|adres|NIP|KRS|REGON|www\.|\d|\(|"
                     r"Zamawiaj|Odwołuj|Dotyczy|ODWOŁANIE|Imię|Przedstawiciel|Pełnomocni|reprezent|Za\s+Odwołuj|"
                     r"W\s+imieniu|Dane|Nr\b|Numer)", re.IGNORECASE)
_LF_END = re.compile(r"(?:\bsp\.\s?[kjp]\.|\bs\.\s?c\.|\bS\.A\.|sp\.\s*z\s*o\.\s*o\.|odpowiedzialnością|Spółka\s+Partnerska"
                     r"|Spółka\s+Akcyjna|Partnerzy|Wspólnicy\s+sp\.\s?\w\.)\s*$", re.IGNORECASE)
_LF_CUT = re.compile(r"\s*;|\s*[,;]?\s*(?:\b(?:ul\.|al\.|pl\.|os\.)(?:\s|$)|\d{2}\s?-\s?\d{3}\b|\(|\||\btel\.|\be-?mail\b"
                     r"|\bOddział\b|[\w.+-]+@)|\s*,\s*(?=[^,]*\d)", re.IGNORECASE)
# a lower-case line still continues the name when the name broke inside the legal form ("Spółka z\nograniczoną …")
_LF_CONT_LOWER = re.compile(r"^(?:ograniczon\w*|odpowiedzialno\w*|o\.\s?o\.|i\s|spółka\b|sp\.)", re.IGNORECASE)
_LF_GEN = [(r"\bKancelarii\b", "Kancelaria"), (r"\bPrawnej\b", "Prawna"), (r"\bAdwokackiej\b", "Adwokacka"),
           (r"\bRadcowskiej\b", "Radcowska"), (r"\bPrawniczej\b", "Prawnicza")]


def _lf_clean(v: str) -> str:
    m = _LF_CUT.search(v)
    v = v[: m.start()] if m and m.start() > 0 else v
    v = " ".join(v.split()).strip(" ,;:–—-")
    v = re.sub(r"^(Kancelari\w*)\s+(?=Kancelari)", "", v)  # table label + value: "Kancelaria Kancelaria X"
    if v.startswith("Kancelarii"):
        for a, b in _LF_GEN:
            v = re.sub(a, b, v)
    return v


def find_lawfirm(seg: str) -> str | None:
    """The representative's law firm in the text after a representation anchor ("reprezentowany przez", "Pełnomocnik",
    "adres do doręczeń"): a firm-shaped line with a law-firm word, or the text right after "z Kancelarii"/"Kancelaria:";
    a wrapped name is joined with its continuation line, the address that follows is cut off."""
    lines = seg.split("\n")[:8]
    for i, raw in enumerate(lines):
        line = raw.strip(" \t:–—-,;")
        if not line:
            continue
        intro = False
        m = _LF_ADDR_LABEL.match(line)
        if m:
            line = line[m.end():]
        m = _LF_INTRO.match(line)
        if m and (m.end() < len(line) or i + 1 < len(lines)):
            intro, line = True, line[m.end():].strip(" :–—-,")
            if not line:  # "z kancelarii prawnej" at the end of the line: the firm is the next line
                j = next((k for k in range(i + 1, len(lines)) if lines[k].strip()), None)
                if j is None:
                    return None
                i, line = j, lines[j].strip(" \t:–—-,;")
        person = False
        pm = _LF_PERSON.match(line)
        if pm:
            person, line = True, line[pm.end():].strip()
            if not line:
                continue
        k = re.search(rf"(?-i:(?:(?!Pełnomocni|Odwołuj|Adres|Law\b|Firm|Nazwa|Kancelaria\s+Kancelari)[{_UP}][\w&.-]*[ \t]+){{0,3}}?Kancelari)", line)
        if k and not intro:
            line = line[k.start():]
        if not line or not re.match(rf"(?-i:[{_UP}0-9])", line) or _LF_NOT.match(line):
            if _LF_NOT.match(line or "") and re.match(r"(?:Zamawiaj|Dotyczy|ODWOŁANIE)", line or "", re.IGNORECASE):
                return None
            continue
        if not (intro or person or _LF_MARKER.search(line)):
            continue
        cand, joined = line, 0
        while (not _LF_CUT.search(cand) and not _LF_END.search(cand) and joined < 2 and i + 1 < len(lines)):
            nxt = lines[i + 1].strip(" \t,;")
            if (not nxt or _LF_NOT.match(nxt) or ":" in nxt
                    or not (re.match(rf"(?-i:[{_UP}])", nxt) or _LF_CONT_LOWER.match(nxt) or re.search(r"\b(?:z|i|w|oraz|&)$", cand))
                    or (_LF_MARKER.search(cand) and re.fullmatch(rf"(?-i:[{_UP}]\w+[ \t]+[{_UP}][\w-]+)", nxt))):
                break
            cand, i, joined = cand + " " + nxt, i + 1, joined + 1
        if not (intro or _LF_MARKER.search(cand)):
            continue
        value = _lf_clean(cand)
        if len(value) >= 6 and not re.fullmatch(rf"(?-i:[{_UP}]\w+[ \t]+[{_UP}][\w-]+)", value):
            return value
    return None


def _person_email(spec: dict[str, Any], ctx: Context) -> Any:
    """E-mail whose local part carries the surname of an already extracted person (`person`: item field path),
    e.g. 'Angelika Pikoń' → a.pikon@…; among several such addresses the first one in the text."""
    item = ctx.item or {}
    name = _get_path(item, spec["person"]) if item else ctx.values.get(spec["person"])
    if not isinstance(name, str) or len(name.split()) < 2:
        return None
    surname = fold(name.split()[-1].split("-")[0]).lower()
    if len(surname) < 3:
        return None
    for m in re.finditer(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", ctx.text):
        local = fold(m.group(0).split("@")[0]).lower()
        if surname in local or surname[:-1] in local and len(surname) > 5:
            return m.group(0).rstrip(".")
    return None


TYPES: dict[str, Callable[[dict[str, Any], Context], Any]] = {
    "labeled": _labeled,
    "text_after_label": _text_after_label,
    "pattern": _pattern,
    "account": _account,
    "first_line": _first_line,
    "exists": _exists,
    "keyword_map": _keyword_map,
    "names": _names,
    "llm": _llm,
    "near": _near,
    "person_email": _person_email,
}


def extract_field(specs: dict[str, Any] | list[dict[str, Any]], ctx: Context,
                  scopes: dict[str, Context] | None = None) -> Any:
    spec_list = specs if isinstance(specs, list) else [specs]
    # a spec without its own `scope` inherits the scope of the field's first spec
    field_scope = spec_list[0].get("scope") if spec_list else None
    for spec in spec_list:
        if spec.get("only_if_single") and ctx.n_items > 1:
            continue  # document-wide fallbacks would give every list item the same value
        c = (scopes or {}).get(spec.get("scope", field_scope), ctx)
        ctx_for_sections = c
        if "unless_section" in spec and ctx_for_sections.section(spec["unless_section"]) is not None:
            continue  # fallback used only when the document has no such section
        if spec.get("section"):  # `section: null` overrides an inherited section (whole document)
            text = ctx_for_sections.section(spec["section"])
            if text is None:
                continue
            c = ctx_for_sections.sub(text)
            c.values = ctx_for_sections.values  # cross-field checks (e.g. `within_days`) still see earlier fields
            c.index, c.n_items, c.label = ctx_for_sections.index, ctx_for_sections.n_items, ctx_for_sections.label
        value = TYPES[spec["type"]](spec, c)
        if value not in (None, ""):
            if spec.get("cast") == "int":
                value = int(value)
            return value
    return None


def extract_list(spec: dict[str, Any], ctx: Context, item_template: dict[str, Any]) -> list[dict[str, Any]]:
    """A list of items (e.g. parties): take a section, optionally split it into items, extract item fields."""
    import copy

    text = ctx.section(spec["section"]) if "section" in spec else ctx.text
    if text is None:
        # No section found (unknown layout): only layout-independent specs marked `if_no_section` may run,
        # on the whole document, producing a single item.
        item = copy.deepcopy(item_template)
        doc = ctx.sub(ctx.text)
        doc.item = item  # later fields may read earlier ones (e.g. the representative's e-mail by surname)
        for path, fspecs in spec["fields"].items():
            usable = [f for f in (fspecs if isinstance(fspecs, list) else [fspecs]) if f.get("if_no_section")]
            if usable:
                value = extract_field(usable, doc)
                if value is not None:
                    set_path(item, path, value)
        _imply(item, spec)
        return [item]
    chunks, labels = [text], [""]
    # `split_if`: split into items only when the section shows an explicit multi-party signal (e.g. a consortium)
    may_split = "split_if" not in spec or any(r.search(text) for r in _compile(spec["split_if"]))
    if "split" in spec and may_split:
        rx = _compile(spec["split"])[0]
        starts = [m for m in rx.finditer(text)]
        if starts:
            chunks = [text[m.end() : (starts[i + 1].start() if i + 1 < len(starts) else len(text))] for i, m in enumerate(starts)]
            labels = [m.group(0) for m in starts]
            head = text[: starts[0].start()]
            if spec.get("keep_head") and len(re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]", head)) >= 12:
                chunks.insert(0, head)  # "A …; oraz B …" or "A (lead) … na rzecz: 1) B": text before the first marker is an item
                labels.insert(0, "")
    if "prefer" in spec and len(chunks) > 1:
        # e.g. consortium → only the leader: move the first item whose label or text matches `prefer` to the front
        prefs = _compile(spec["prefer"])
        pick = next((i for i, (c, l) in enumerate(zip(chunks, labels)) if any(r.search(l + "\n" + c) for r in prefs)), 0)
        chunks.insert(0, chunks.pop(pick))
        labels.insert(0, labels.pop(pick))
    chunks = chunks[: int(spec.get("max_items", 50))]
    labels = labels[: len(chunks)]
    items = []
    for index, (chunk, label) in enumerate(zip(chunks, labels)):
        item = copy.deepcopy(item_template)
        sub = ctx.sub(chunk, n_items=len(chunks))
        sub.label = label
        whole = ctx.sub(text, n_items=len(chunks))
        doc = ctx.sub(ctx.text, n_items=len(chunks))
        for c in (sub, whole, doc):
            c.index = index
            c.item_text, c.item = chunk, item  # the item's own block and its (partly filled) values
        scopes = {"section": whole, "document": doc}
        for path, fspecs in spec["fields"].items():
            value = extract_field(fspecs, sub, scopes)  # each spec may pick its own scope (item/section/document)
            if value is not None or not isinstance(_get_path(item, path), list):
                set_path(item, path, value)
        _imply(item, spec)
        items.append(item)
    return items


def _imply(item: dict[str, Any], spec: dict[str, Any]) -> None:
    """`imply: [{if_any: [path, …], set: {path: value}}]` — consistency inside one list item: when any of the
    `if_any` fields was extracted, the `set` fields take the given values (e.g. a named representative ⇒ flag 1)."""
    for rule in spec.get("imply", []):
        if any(_get_path(item, p) not in (None, "", []) for p in rule["if_any"]):
            for path, value in rule["set"].items():
                set_path(item, path, value)


def _get_path(obj: Any, path: str) -> Any:
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        obj = obj[int(part[1:-1])] if part.startswith("[") else obj.get(part) if isinstance(obj, dict) else None
    return obj


def set_path(obj: Any, path: str, value: Any) -> None:
    """Set ``a.b[0].c`` inside nested dicts/lists (lists must already exist in the template)."""
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for part in parts[:-1]:
        obj = obj[int(part[1:-1])] if part.startswith("[") else obj[part]
    last = parts[-1]
    if last.startswith("["):
        obj[int(last[1:-1])] = value
    else:
        obj[last] = value
