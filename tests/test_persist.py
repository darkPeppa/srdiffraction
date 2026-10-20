"""Правила сохранения результатов (--persist)."""
import json

import liga_common.persist as P


def test_persist_rules(tmp_path, monkeypatch):
    res = tmp_path / "results"
    (res / "runs/x/stage2").mkdir(parents=True)
    (res / "runs/x/stage2/stage2.json").write_text("{}")
    (res / "runs/x/stage2/stage2.h5").write_bytes(b"0" * 100)
    (res / "runs/x/ps_t0.bin").write_bytes(b"0" * 100)
    (res / "runs/x/source_table.csv").write_text("a")
    (res / "runs/x/big.csv").write_text("x" * (6 * 1024 * 1024))
    (res / "runs/x/plot.png").write_bytes(b"png")
    monkeypatch.setattr(P, "RESULTS", res)
    monkeypatch.setattr(P, "PERSIST", tmp_path / "results_persist")
    d = P.persist([res], "t", heavy=False, command="test")
    m = json.loads((d / "MANIFEST.json").read_text())
    files = {f["file"] for f in m["files"]}
    assert {"runs/x/stage2/stage2.json", "runs/x/plot.png", "runs/x/big.csv.gz"} <= files
    reasons = {s["file"]: s["reason"] for s in m["skipped"]}
    assert "runs/x/stage2/stage2.h5" in reasons and "runs/x/ps_t0.bin" in reasons
    assert "runs/x/source_table.csv" in reasons
    d2 = P.persist([res], "t", heavy=True)
    files2 = {f["file"] for f in json.loads((d2 / "MANIFEST.json").read_text())["files"]}
    assert "runs/x/stage2/stage2.h5" in files2 and "runs/x/ps_t0.bin" not in files2
    assert d != d2
