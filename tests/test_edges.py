#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_edges.py — 边界回归：BOM 输入、纯英文、null 时间、生成器量级。

    python3 tests/test_edges.py

这些是 2026-10-30 那次 Windows 实测里踩出来的坑，用固定断言防回退。
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

if not sys.stdout.isatty():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run(*args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        print(f"[FAIL] {' '.join(args)}\n{(r.stderr or r.stdout)[-1200:]}")
        sys.exit(1)
    return r.stdout


def read_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="amber-edge-"))

    # 1) 输入带 BOM + 纯英文 + null 时间/seq：一行都不能丢，英文不能判噪声
    src = tmp / "in.jsonl"
    src.write_text(
        json.dumps({"role": "user", "text": "This is a fairly long English sentence.",
                    "time": None, "seq": None}, ensure_ascii=False) + "\n" +
        json.dumps({"role": "user", "text": "膝盖有点疼，是不是跑太多了",
                    "time": 1767714631238, "seq": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8-sig")
    out = tmp / "out.jsonl"
    run("extract.py", "--source", str(src), "--tag", "t", "--out", str(out))
    rows = read_jsonl(out)
    assert len(rows) == 2, f"BOM 首行丢了：{len(rows)} 条"
    assert rows[0]["noise"] == "", f"英文被当成噪声：{rows[0]['noise']}"
    assert any(r["text"].startswith("This is") for r in rows), "英文行不见了"

    # 2) 生成器量级：语料不能太短，可召回率不能太低（防「合成语料稀疏」式回退）
    corpus = tmp / "c.jsonl"
    run("examples/gen-corpus.py", "--n", "500", "--out", str(corpus))
    texts = read_jsonl(corpus)
    avg = sum(len(r["text"]) for r in texts) / len(texts)
    assert avg > 20, f"语料太短：平均 {avg:.1f} 字"
    ev = tmp / "e.jsonl"
    run("extract.py", "--source", str(corpus), "--tag", "t", "--out", str(ev))
    rows = read_jsonl(ev)
    ratio = sum(1 for r in rows if r["wake"] > 0) / len(rows)
    assert ratio > 0.08, f"可召回率太低：{ratio:.1%}"

    print(f"[ok] 边界测试通过：平均 {avg:.1f} 字，可召回 {ratio:.1%}")


if __name__ == "__main__":
    main()
