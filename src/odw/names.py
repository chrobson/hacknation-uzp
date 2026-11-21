"""Polish person names: declined forms → nominative (GT stores names in the nominative).

Conservative by design: a name already in the nominative must come back unchanged. A form is converted only
when it carries an unambiguous case ending (-owi, -skiego, -skiej, -ę, -ą, ...) or, for the ambiguous male
genitive/accusative "-a", only when the first name is a known male name ("Grzegorza Furmana" → "Grzegorz
Furman", while "Aleksandra Marciniak" stays a woman's name).
"""

from __future__ import annotations

import os
import re
from functools import cache

MALE = set("""Adam Adrian Aleksander Andrzej Antoni Arkadiusz Artur Bartłomiej Bartosz Bogdan Bogusław Cezary Czesław
Damian Daniel Dariusz Dawid Dominik Edward Emil Eryk Filip Franciszek Grzegorz Henryk Hubert Igor Ignacy Ireneusz
Jacek Jakub Jan Janusz Jarosław Jerzy Józef Julian Kacper Kamil Karol Kazimierz Konrad Krystian Krzysztof Leszek
Lech Łukasz Maciej Maksymilian Marcin Marek Marian Mariusz Mateusz Michał Mieczysław Mikołaj Mirosław Norbert Oskar
Patryk Paweł Piotr Przemysław Radosław Rafał Robert Roman Ryszard Sebastian Szymon Sławomir Stanisław Stefan
Tadeusz Tomasz Waldemar Wiesław Witold Władysław Wojciech Zbigniew Zdzisław Zenon Zygmunt Kajetan Bronisław""".split())
# genitive/accusative stems that are not simply nominative + "a"
MALE_GEN_IRREGULAR = {"Pawła": "Paweł", "Marka": "Marek", "Leszka": "Leszek", "Jacka": "Jacek", "Aleksandra": "Aleksander",
                      "Jerzego": "Jerzy", "Cezarego": "Cezary", "Ignacego": "Ignacy", "Antoniego": "Antoni",
                      "Bartłomieja": "Bartłomiej", "Macieja": "Maciej", "Wojciecha": "Wojciech", "Andrzeja": "Andrzej",
                      "Mikołaja": "Mikołaj", "Kacpra": "Kacper"}
MALE_DAT_IRREGULAR = {"Pawłowi": "Paweł", "Markowi": "Marek", "Leszkowi": "Leszek", "Jackowi": "Jacek",
                      "Aleksandrowi": "Aleksander", "Jerzemu": "Jerzy", "Cezaremu": "Cezary", "Ignacemu": "Ignacy",
                      "Antoniemu": "Antoni", "Kacprowi": "Kacper"}
HONORIFIC = re.compile(r"^(?:Pan(?:a|u|em)?|Pani(?:ą)?|Panią)\s+", re.IGNORECASE)

_ADJ = [("ckiego", "cki"), ("skiego", "ski"), ("dzkiego", "dzki"), ("ckiemu", "cki"), ("skiemu", "ski"),
        ("dzkiemu", "dzki"), ("ckim", "cki"), ("skim", "ski"), ("iego", "i"), ("iemu", "i"), ("ego", "y"), ("emu", "y")]
_ADJ_F = [("ckiej", "cka"), ("skiej", "ska"), ("dzkiej", "dzka"), ("cką", "cka"), ("ską", "ska"), ("dzką", "dzka"),
          ("owej", "owa"), ("ową", "owa")]


def _female_first(token: str) -> str:
    for suf, rep in (("ę", "a"), ("ą", "a"), ("cie", "ta"), ("ce", "ka"), ("dze", "ga"), ("rze", "ra"), ("nie", "na"),
                     ("cji", "cja"), ("lii", "lia"), ("rii", "ria"), ("ii", "ia"), ("ie", "a"), ("y", "a"), ("i", "a")):
        if token.endswith(suf) and len(token) > len(suf) + 1:
            return token[: -len(suf)] + rep
    return token


def _male_surname(token: str) -> str:
    for suf, rep in _ADJ:
        if token.endswith(suf) and len(token) > len(suf) + 1:
            return token[: -len(suf)] + rep
    for suf in ("owi", "em", "a", "u"):
        if token.endswith(suf) and len(token) > len(suf) + 2:
            return token[: -len(suf)]
    return token


def nominative(name: str) -> str:
    """Nominative of a person name: the SGJP dictionary (Morfeusz2) when installed, else the rules below."""
    rule = _rule_nominative(name)
    try:
        return _dict_nominative(name, rule) or rule
    except Exception:  # a dictionary problem must never break extraction
        return rule


@cache
def _morfeusz():
    """Morfeusz2 analyser (optional dependency; ODW_MORFEUSZ=0 disables it). None when unavailable."""
    if os.environ.get("ODW_MORFEUSZ", "1") == "0":
        return None
    try:
        import morfeusz2

        return morfeusz2.Morfeusz(generate=False)
    except Exception:
        return None


def _readings(token: str) -> list[tuple[str, set[str], set[str], set[str]]]:
    """(lemma, cases, genders, qualifiers) of singular proper-noun readings of a token."""
    out = []
    for _, _, (_form, lemma, tag, quals, _q2) in _morfeusz().analyse(token):
        parts = tag.split(":")
        if parts[0] not in ("subst", "depr") or len(parts) < 4 or "sg" not in parts[1].split("."):
            continue
        lemma = lemma.split(":")[0]
        if lemma[:1].isupper():
            out.append((lemma, set(parts[2].split(".")), set(parts[3].split(".")), set(quals)))
    return out


def _dict_nominative(name: str, rule: str) -> str | None:
    """Pick the case and gender of the first name (a dictionary first name) under which most surname tokens agree,
    then replace every token by its lemma; tokens unknown to the dictionary keep the rules' form."""
    if _morfeusz() is None:
        return None
    parts = HONORIFIC.sub("", " ".join(name.split())).split()
    if not 2 <= len(parts) <= 4:
        return None
    firsts = [r for r in _readings(parts[0]) if "imię" in r[3]]
    if not firsts:
        return None
    rest = [[(t, _readings(t)) for t in p.split("-")] for p in parts[1:]]
    best = None
    for lemma, cases, genders, _ in firsts:
        for case in cases:
            for gender in genders & {"m1", "f"}:
                hits, out_rest = 0, []
                for sub in rest:
                    outs = []
                    for tok, readings in sub:
                        ok = [r for r in readings if case in r[1] and gender in r[2]]
                        ok.sort(key=lambda r: ("nazwisko" not in r[3], r[0] != tok, "imię" in r[3]))
                        hits += bool(ok)
                        outs.append(ok[0][0] if ok else None)
                    out_rest.append(outs)
                key = (hits, case == "nom", lemma == parts[0], lemma == rule.split()[0],
                       gender == "f" if parts[0].endswith("a") else gender == "m1")
                if best is None or key > best[0]:
                    best = (key, lemma, case, out_rest)
    if best is None or (best[0][0] == 0 and best[2] != "nom"):
        return None
    _, lemma, _, out_rest = best
    rule_parts = rule.split()
    res = [lemma]
    for i, (sub, outs) in enumerate(zip(rest, out_rest)):
        fallback = rule_parts[i + 1].split("-") if len(rule_parts) == len(parts) else [t for t, _ in sub]
        res.append("-".join(o or (fallback[j] if j < len(fallback) else sub[j][0]) for j, o in enumerate(outs)))
    return " ".join(res)


def _rule_nominative(name: str) -> str:
    original = " ".join(name.split())
    name = HONORIFIC.sub("", original)
    parts = name.split()
    if len(parts) < 2:
        return original  # "Panu Tomaszowi": not a full name; keep the honorific so stopword filters can reject it
    first, rest = parts[0], parts[1:]
    last = rest[-1]

    # male dative: Ryszardowi Cieślakowi, Aleksandrowi Jastrzębskiemu
    if first in MALE_DAT_IRREGULAR or (first.endswith("owi") and first[:-3] in MALE):
        return " ".join([MALE_DAT_IRREGULAR.get(first, first[:-3])] + [_male_surname(t) for t in rest])
    # male genitive/accusative: Grzegorza Furmana, Pawła Kowalskiego (first name must be a known male name)
    male_gen = MALE_GEN_IRREGULAR.get(first) or (first[:-1] if first.endswith("a") and first[:-1] in MALE else None)
    if male_gen and first == "Aleksandra" and not (last.endswith(("ego", "a")) and not last.endswith(("ska", "cka", "dzka", "owa"))):
        male_gen = None  # "Aleksandra Marciniak": a woman's name in the nominative
    if male_gen:
        return " ".join([male_gen] + [_male_surname(t) for t in rest])
    # female forms with an unambiguous ending on either token: Patrycję Malinowską, Annie Kowalskiej, Anny Nowak
    fem_last = next(((suf, rep) for suf, rep in _ADJ_F if last.endswith(suf)), None)
    # female dative/locative first names: Edycie, Annie, Marcie, Oldze, Agnieszce, Patrycji, Marii
    fem_dat = first.endswith(("cie", "ce", "dze", "rze", "nie", "cji", "rii", "lii")) and len(first) > 4
    if first.endswith(("ę", "ą")) or fem_last or fem_dat:
        new_rest = [t[: -len(fem_last[0])] + fem_last[1] if fem_last and t == last else t for t in rest]
        new_rest = [t[:-1] + "a" if t.endswith(("ę", "ą")) and len(t) > 3 else t for t in new_rest]
        return " ".join([_female_first(first)] + new_rest)
    return name


def titlecase_upper(name: str) -> str:
    """'Halina ZIELIŃSKA' → 'Halina Zielińska' (keeps hyphenated parts)."""
    return " ".join("-".join(p.capitalize() for p in t.split("-")) if t.isupper() and len(t) > 1 else t for t in name.split())
