"""Generic, YAML-configured field extraction.

A class YAML lists fields by output path (e.g. ``przelew_bankowy.kwota``). Each field has one spec or a list of
specs tried in order until one returns a value. Spec types:

  pattern          regex over the whole text; group 1 (or the whole match) is the value
  labeled          find a label, then the first value of ``value`` kind in the window after it
                   (value: date | amount | token | account | regex)
  text_after_label text that follows a label, across lines, until a stop label
  account          26-digit account by role (sender/receiver) decided by the nearest preceding keyword

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
    for rx in _compile(spec["labels"]):
        hits.extend(rx.finditer(ctx.text))
    for m in sorted(hits, key=lambda m: m.start()):
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
        for i, line in enumerate(lines[: max_lines + 1]):
            if i > 0 and any(s.match(line) for s in stops):
                break
            if line.strip():
                taken.append(line)
            if "”" in line:  # closing quote ends a quoted title
                break
        value = N.clean_text(" ".join(taken).split("”")[0])
        if value:
            return value
    return None


def _pattern(spec: dict[str, Any], ctx: Context) -> Any:
    for rx in _compile(spec["pattern"]):
        m = rx.search(ctx.text)
        if m:
            if "format" in spec:  # e.g. "{1}/BZP{2}" with regex groups; missing groups become ""
                groups = [m.group(0)] + [g or "" for g in m.groups()]
                value = spec["format"].format(*groups)
                return "".join(value.split()) if spec.get("nospace") else value
            value = m.group(1) if m.groups() else m.group(0)
            return N.digits(value) if spec.get("digits") else N.clean_text(value) if spec.get("clean") else value
    return None


def _account(spec: dict[str, Any], ctx: Context) -> Any:
    return ctx.accounts().get(spec["role"])


def _first_line(spec: dict[str, Any], ctx: Context) -> Any:
    skips = _compile(spec.get("skip", []))
    for line in ctx.text.lstrip(" \t:").split("\n"):
        line = N.clean_text(line)
        if line and not any(rx.search(line) for rx in skips):
            return line
    return None


def _exists(spec: dict[str, Any], ctx: Context) -> Any:
    if spec.get("only_if_multiple") and ctx.n_items < 2:
        return None
    hit = any(rx.search(ctx.text) for rx in _compile(spec["pattern"]))
    return spec.get("true", 1) if hit else spec.get("false", 0)


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


TYPES: dict[str, Callable[[dict[str, Any], Context], Any]] = {
    "labeled": _labeled,
    "text_after_label": _text_after_label,
    "pattern": _pattern,
    "account": _account,
    "first_line": _first_line,
    "exists": _exists,
    "keyword_map": _keyword_map,
}


def extract_field(specs: dict[str, Any] | list[dict[str, Any]], ctx: Context) -> Any:
    for spec in specs if isinstance(specs, list) else [specs]:
        c = ctx
        if "section" in spec:
            text = ctx.section(spec["section"])
            if text is None:
                continue
            c = ctx.sub(text)
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
        return [copy.deepcopy(item_template)]
    chunks = [text]
    if "split" in spec:
        rx = _compile(spec["split"])[0]
        starts = [m for m in rx.finditer(text)]
        if starts:
            chunks = [text[m.end() : (starts[i + 1].start() if i + 1 < len(starts) else len(text))] for i, m in enumerate(starts)]
    chunks = chunks[: int(spec.get("max_items", 50))]
    items = []
    for chunk in chunks:
        item = copy.deepcopy(item_template)
        sub = ctx.sub(chunk, n_items=len(chunks))
        whole = ctx.sub(text, n_items=len(chunks))
        for path, fspecs in spec["fields"].items():
            scoped = fspecs if isinstance(fspecs, list) else [fspecs]
            on_section = any(f.get("scope") == "section" for f in scoped)
            set_path(item, path, extract_field(fspecs, whole if on_section else sub))
        items.append(item)
    return items


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
