"""Polish person names: declined forms → nominative (GT stores names in the nominative).

Conservative by design: a name already in the nominative must come back unchanged. A form is converted only
when it carries an unambiguous case ending (-owi, -skiego, -skiej, -ę, -ą, ...) or, for the ambiguous male
genitive/accusative "-a", only when the first name is a known male name ("Grzegorza Furmana" → "Grzegorz
Furman", while "Aleksandra Marciniak" stays a woman's name).
"""

from __future__ import annotations

import re

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
                     ("lii", "lia"), ("rii", "ria"), ("ii", "ia"), ("ie", "a"), ("y", "a"), ("i", "a")):
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
    name = HONORIFIC.sub("", " ".join(name.split()))
    parts = name.split()
    if len(parts) < 2:
        return name
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
    if first.endswith(("ę", "ą")) or fem_last:
        new_rest = [t[: -len(fem_last[0])] + fem_last[1] if fem_last and t == last else t for t in rest]
        new_rest = [t[:-1] + "a" if t.endswith(("ę", "ą")) and len(t) > 3 else t for t in new_rest]
        return " ".join([_female_first(first)] + new_rest)
    return name


def titlecase_upper(name: str) -> str:
    """'Halina ZIELIŃSKA' → 'Halina Zielińska' (keeps hyphenated parts)."""
    return " ".join("-".join(p.capitalize() for p in t.split("-")) if t.isupper() and len(t) > 1 else t for t in name.split())
