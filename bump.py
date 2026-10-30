#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bump.py — 记一次「这句话被翻出来用过」。

这是唯一有真标签的信号：被用过的话，比你以为重要的更该留下。
pick.py 读到计数 > 0 的条目，就把它锁进「骨头」块，永不淘汰。

按文本哈希记，不按 seq —— 同一句话在不同书库里可能出现两次。

用法：
    python3 bump.py --text "某句原话"
    python3 bump.py --seq 12345          # 按 events.jsonl 里的 seq 找
    python3 bump.py --show
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "settings.json"))
    ap.add_argument("--text")
    ap.add_argument("--seq")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()

    cfg = {}
    cp = Path(a.config)
    if cp.exists():
        cfg = json.loads(cp.read_text(encoding="utf-8"))
    base = cp.parent if cp.exists() else HERE

    bump_path = Path(cfg.get("bump", "bump.json"))
    if not bump_path.is_absolute():
        bump_path = base / bump_path
    data = load(bump_path)

    if a.show or (not a.text and not a.seq):
        for k, v in sorted(data.items(), key=lambda x: -x[1]):
            print(f"{k}  ×{v}")
        if not data:
            print("还没有引用记录。")
        return

    text = a.text
    if not text and a.seq:
        events = Path(cfg.get("out", "events.jsonl"))
        if not events.is_absolute():
            events = base / events
        for line in events.open(encoding="utf-8"):
            r = json.loads(line)
            if str(r["seq"]) == str(a.seq):
                text = r["text"]
                break
        if not text:
            raise SystemExit(f"events 里没有 seq {a.seq}")

    k = key(text)
    data[k] = data.get(k, 0) + 1
    bump_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"记下：{k} ×{data[k]}")


if __name__ == "__main__":
    main()
