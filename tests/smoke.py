#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoke.py — 三步能不能跑通。不判好坏，只判有没有断。

    python3 tests/smoke.py

全部用 examples/ 里的编造数据，不碰任何真实记录。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(*args, **kw):
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print(f"[FAIL] {' '.join(args)}\n{(r.stderr or r.stdout)[-800:]}")
        sys.exit(1)
    return r.stdout


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="amber-"))
    events = tmp / "events.jsonl"
    resident = tmp / "resident.md"
    cfg = tmp / "settings.json"

    # 1. 造数据
    corpus = tmp / "corpus.jsonl"
    run("examples/gen-corpus.py", "--n", "300", "--out", str(corpus))
    n_in = sum(1 for _ in corpus.open(encoding="utf-8"))
    assert n_in == 300, f"生成条数不对：{n_in}"

    # 2. 抽取
    run("extract.py", "--source", str(corpus), "--tag", "smoke", "--out", str(events))
    rows = [json.loads(l) for l in events.open(encoding="utf-8") if l.strip()]
    assert len(rows) == 300, f"events 条数不对：{len(rows)}"
    for r in rows[:5]:
        for k in ("dt", "role", "text", "topic", "noise", "wake"):
            assert k in r, f"events 缺字段 {k}"

    # 3. 挑常驻
    cfg.write_text(json.dumps({
        "out": str(events), "resident": str(resident),
        "bump": str(tmp / "bump.json"), "resident_budget": 3000,
        "share_user": 0.55, "share_assistant": 0.25, "tz_offset_hours": 8,
    }, ensure_ascii=False), encoding="utf-8")
    run("pick.py", "--config", str(cfg))
    assert resident.exists(), "常驻没生成"
    body = resident.read_text(encoding="utf-8")
    assert body.startswith("# 常驻"), "常驻标题不对"
    assert len(body) > 200, f"常驻太短：{len(body)}"

    # 4. 检索
    out = run("recall.py", "--config", str(cfg), "膝盖疼怎么办")
    assert "可能相关的原话" in out or out.strip() == "", "检索输出不对"

    print(f"[ok] 三步跑通：300 条 → 常驻 {len(body)} 字")
    print(f"[ok] 临时目录 {tmp}")


if __name__ == "__main__":
    main()
