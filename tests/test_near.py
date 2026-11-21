"""Layout-independent extraction: values found near role keywords, whatever the layout."""

from odw.fields import Context, extract_field, extract_list

CFG = {"sections": {"zam": {"start": r"^\s*Zamawiając\w*\s*:"}}}
ROLES_ZAM = [r"Zamawiając\w*", r"Instytucj\w*\s+zamawiając\w*"]
ROLES_ODW = [r"Odwołując\w*", r"Wykonawc\w*\s+wnosząc\w*\s+odwołanie"]

TABLE = """| Instytucja zamawiająca | Gmina Rudnik Wielki, NIP 999 026 42 87, REGON 999242211 |
| Wykonawca wnoszący odwołanie | Alfa Budownictwo sp. z o.o., KRS 0000123456, NIP PL1234567890 |"""
INLINE = "Odwołujący: Alfa Budownictwo sp. z o.o. (KRS 0000123456, NIP 1234567890), reprezentowany przez adw. Jan Nowak. " \
         "Zamawiający: Gmina Rudnik Wielki (NIP 9990264287)."


def near(value, anchors, stop):
    return {"type": "near", "value": value, "anchors": anchors, "stop": stop}


def test_table_layout():
    ctx = Context(TABLE, CFG)
    assert extract_field(near("company", ROLES_ZAM, ROLES_ODW), ctx) == "Gmina Rudnik Wielki"
    assert extract_field(near("nip", ROLES_ZAM, ROLES_ODW), ctx) == "9990264287"
    assert extract_field(near("company", ROLES_ODW, ROLES_ZAM), ctx) == "Alfa Budownictwo sp. z o.o."
    assert extract_field(near("nip", ROLES_ODW, ROLES_ZAM), ctx) == "1234567890"
    assert extract_field(near("krs", ROLES_ZAM, ROLES_ODW), ctx) is None  # the authority has no KRS; do not borrow


def test_inline_layout_stops_at_competing_role():
    ctx = Context(INLINE, CFG)
    assert extract_field(near("nip", ROLES_ODW, ROLES_ZAM), ctx) == "1234567890"
    assert extract_field(near("nip", ROLES_ZAM, ROLES_ODW), ctx) == "9990264287"


def test_list_without_section_uses_only_layout_independent_specs():
    spec = {"section": "zam", "fields": {
        "nazwa": [{"type": "first_line"}, {**near("company", ROLES_ZAM, ROLES_ODW), "if_no_section": True}],
        "nip": [{**near("nip", ROLES_ZAM, ROLES_ODW), "if_no_section": True}],
    }}
    items = extract_list(spec, Context(TABLE, CFG), {"nazwa": None, "nip": None})
    assert items == [{"nazwa": "Gmina Rudnik Wielki", "nip": "9990264287"}]
