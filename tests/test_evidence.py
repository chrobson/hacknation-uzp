"""Evidence: every quoted value gets page + snippet + boxes; evidence never lands in output/."""

import json
import shutil
from pathlib import Path

from odw.__main__ import main

CASE = Path(__file__).resolve().parents[1] / "data" / "train" / "przyklad_50"


def test_evidence_written_outside_output(tmp_path):
    inp = tmp_path / "in" / "c1"
    inp.mkdir(parents=True)
    for pdf in CASE.glob("*.pdf"):
        shutil.copy(pdf, inp)
    out, ev = tmp_path / "out", tmp_path / "ev"
    assert main(["--input", str(tmp_path / "in"), "--output", str(out), "--evidence", str(ev)]) == 0
    assert sorted(p.name for p in (out / "c1").iterdir()) == ["odwolanie.json", "pelnomocnictwo.json", "potwierdzenie_przelewu.json"]
    e = json.loads((ev / "c1" / "odwolanie.evidence.json").read_text(encoding="utf-8"))
    nip = e["fields"]["Odwolujacy[0].nip"]
    assert nip["value"] == "9990838738" and nip["page"] == 1 and "9990838738" in nip["snippet"]
    assert nip["boxes"] and all(b["x1"] > b["x0"] and b["bottom"] > b["top"] for b in nip["boxes"])
    assert e["fields"]["ZamowieniePubliczne.numer_ted"]["boxes"]
    assert e["fields"]["OdwolanieKIO.czynnosc_opis"]["source"] == "derived"


def test_refuses_evidence_inside_output(tmp_path):
    (tmp_path / "in").mkdir()
    out = tmp_path / "out"
    assert main(["--input", str(tmp_path / "in"), "--output", str(out), "--evidence", str(out / "ev")]) == 2
