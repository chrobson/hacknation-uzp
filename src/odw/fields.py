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
from typing import Any, Callable

from . import normalize as N

FLAGS = re.IGNORECASE | re.MULTILINE


def _compile(patterns: list[str] | str) -> list[re.Pattern[str]]:
    if isinstance(patterns, str):
        patterns = [patterns]
    return [re.compile(p, FLAGS) for p in patterns]


def _finder(kind: str, spec: dict[str, Any]) -> Callable[[str], Any]:
    if kind == "date":
        return N.find_date
    if kind == "amount":
        return N.find_amount
    if kind == "account":
        return lambda s: (m := N.ACCOUNT_RE.search(s)) and N.digits(m.group(1))
    if kind == "token":
        tok = re.compile(spec.get("token_pattern", r"[A-Z0-9][A-Z0-9./\-]{3,}"), re.IGNORECASE)
        return lambda s: (m := tok.search(s)) and m.group(0).rstrip(".,;")
    if kind == "company":
        return N.find_company
    if kind in N.ID_PATTERNS:
        return lambda s: N.find_id(kind, s)
    if kind == "regex":
        rx = re.compile(spec["value_pattern"], FLAGS)
        return lambda s: (m := rx.search(s)) and (m.group(1) if m.groups() else m.group(0))
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
    spec = sections.get(name)
    if spec is None:
        raise KeyError(f"unknown section: {name}")
    start = None
    for rx in _compile(spec["start"]):
        m = rx.search(text)
        if m and (start is None or m.start() < start.start()):
            start = m
    if start is None:
        return None
    enders: list[re.Pattern[str]] = []
    for other, ospec in sections.items():
        if other != name:
            enders += _compile(ospec["start"])
    enders += _compile(sections.get("_end", {}).get("start", []))
    enders += _compile(spec.get("end", []))
    end = len(text)
    for rx in enders:
        m = rx.search(text, start.end())
        if m and m.start() < end:
            end = m.start()
    return text[start.end() : end]


def _assign_accounts(text: str, cfg: dict[str, Any]) -> dict[str, str]:
    sender = _compile(cfg.get("sender_keywords", []))
    receiver = _compile(cfg.get("receiver_keywords", []))
    lookback = int(cfg.get("lookback_chars", 150))
    found: list[tuple[str, str | None]] = []  # (account, role)
    anchors: list[int] = []  # absolute position of the keyword that decided each account's role
    last_kw: list[dict[str, int]] = []  # last position of each role's keyword before each account
    spans: list[tuple[int, int]] = []
    for m in N.ACCOUNT_RE.finditer(text):
        acct = N.digits(m.group(1))
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
    # Two accounts but roles missing or clashing (e.g. two-column layout): document order = sender, receiver.
    if len(accts) >= 2 and (len(roles) < 2 or roles.get("sender") == roles.get("receiver")):
        if "sender" in roles and roles["sender"] in accts[:2]:
            roles["receiver"] = next(a for a in accts if a != roles["sender"])
        elif "receiver" in roles and roles["receiver"] in accts[:2]:
            roles["sender"] = next(a for a in accts if a != roles["receiver"])
        else:
            roles = {"sender": accts[0], "receiver": accts[1]}
    return roles


def _labeled(spec: dict[str, Any], ctx: Context) -> Any:
    find = _finder(spec.get("value", "token"), spec)
    window = int(spec.get("window", 160))
    hits = []
    for rank, rx in enumerate(_compile(spec["labels"])):
        hits.extend((rank, m) for m in rx.finditer(ctx.text))
    # default: earliest label in the document; `label_priority`: labels in the YAML order (strongest first)
    order = (lambda h: (h[0], h[1].start())) if spec.get("label_priority") else (lambda h: h[1].start())
    for _, m in sorted(hits, key=order):
        after = ctx.text[m.end() : m.end() + window].lstrip(" \t:.…")
        value = find(after)
        if value not in (None, ""):
            return value
    return None


def _text_after_label(spec: dict[str, Any], ctx: Context) -> Any:
    stops = _compile(spec.get("stop_labels", []))
    max_lines = int(spec.get("max_lines", 4))
    for rx in _compile(spec["labels"]):
        m = rx.search(ctx.text)
        if not m:
            continue
        rest = ctx.text[m.end() :].lstrip(" \t:")
        lines = rest.split("\n")
        taken: list[str] = []
        inline = spec.get("inline_stops", False)
        for i, line in enumerate(lines[: max_lines + 1]):
            if i > 0 and any(s.match(line) for s in stops):
                break
            if inline:  # a following field glued onto the same line ("… CEN123 zł 17,00 zrealizowano …")
                cut = min((sm.start() for s in stops if (sm := s.search(line, 1))), default=None)
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
    r"\s*,?\s*(?:ul\.|al\.|pl\.|os\.)\s[^,\n]{1,60}?,\s*\d{2}-\d{3}\s+[A-ZŁŚŻŹĆŃÓ][\w-]*(?:[ \t]+[A-ZŁŚŻŹĆŃÓ][\w-]*)?"
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
    text = ctx.text
    if "after" in spec:
        m = next((m for rx in _compile(spec["after"]) if (m := rx.search(text))), None)
        if m is None:
            return None
        text = text[m.end() : m.end() + int(spec.get("window", 600))]
    if "until" in spec:
        cut = re.search(spec["until"], text, FLAGS)
        if cut:
            text = text[: cut.start()]
    best_key, best_pos = None, len(text) + 1
    for key, patterns in spec["map"].items():
        for rx in _compile(patterns):
            m = rx.search(text)
            if m and m.start() < best_pos:
                best_key, best_pos = key, m.start()
    return best_key


NAME = r"[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?"


def _names(spec: dict[str, Any], ctx: Context) -> Any:
    """All person names in a region → list of items ``{field: name}`` (deduplicated, document order).

    pattern     regex whose group 1 is the name (default: two capitalised words on one line)
    after       optional regex; search only after its first match (e.g. the signature block)
    exclude_from  output path of another field whose names are excluded (e.g. representatives)
    stopwords   first/last words that mark a role, not a name (e.g. Prezes, Zarządu)
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
    items: list[dict[str, Any]] = []
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
    return items or None


def _llm(spec: dict[str, Any], ctx: Context) -> Any:
    """Last-resort LLM question (only when enabled). The YAML gives the question and a JSON schema."""
    from . import llm

    if not llm.enabled():
        return None
    value = llm.ask(spec["question"], ctx.text, spec.get("schema", {"type": "string"}))
    if value is not None and spec.get("value") == "date":
        value = N.find_date(str(value))
    return value


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
        if "section" in spec:
            text = ctx_for_sections.section(spec["section"])
            if text is None:
                continue
            c = ctx_for_sections.sub(text)
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
        for path, fspecs in spec["fields"].items():
            usable = [f for f in (fspecs if isinstance(fspecs, list) else [fspecs]) if f.get("if_no_section")]
            if usable:
                value = extract_field(usable, doc)
                if value is not None:
                    set_path(item, path, value)
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
        scopes = {"section": whole, "document": doc}
        for path, fspecs in spec["fields"].items():
            value = extract_field(fspecs, sub, scopes)  # each spec may pick its own scope (item/section/document)
            if value is not None or not isinstance(_get_path(item, path), list):
                set_path(item, path, value)
        items.append(item)
    return items


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
