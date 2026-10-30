#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recall.py — 给一个问题，从 events.jsonl 里捞几条原话。只捞，不改、不评。

为什么要有这一步：常驻集给的是气质和句子，不是事实。
问题里带具体细节（哪天、多少钱、叫什麼名字）时，光靠常驻会编 ——
所以把 1~4 条原文捞出来附在后面。成本几百 token，但决定它是「记得」还是「很像记得」。

用法：
    python3 recall.py "我那块表多少钱"
    python3 recall.py "我那块表多少钱" -k 3 --json
"""
import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CJK = re.compile(r"[\u4e00-\u9fff]")
STOP = set("的了是我你他吗呢吧啊呀嘛哦就都也还很这那个们么什怎样对在有说点会做要能可不没")


def terms(q: str):
    q = re.sub(r"[\s\W_]+", "", q)
    ts = {q[i:i + 2] for i in range(len(q) - 1)} if len(q) > 1 else {q}
    return {t for t in ts if CJK.search(t) and not (set(t) <= STOP)}


class Index:
    def __init__(self, path: Path):
        rows = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
        # 噪声不进索引：系统注入、代码块、太短、链接
        self.rows = [r for r in rows if not r.get("noise")]
        for r in self.rows:      # 兼容早期格式 me/he
            r["role"] = {"me": "user", "he": "assistant"}.get(r["role"], r["role"])
        self.docs = []
        df = Counter()
        for r in self.rows:
            t = terms(r["text"])
            self.docs.append(t)
            df.update(t)
        self.df = df
        self.n = max(1, len(self.rows))

    def search(self, q: str, k: int = 4):
        ts = terms(q)
        if not ts:
            return []
        scored = []
        for r, dt in zip(self.rows, self.docs):
            hit = ts & dt
            if not hit:
                continue
            s = sum(math.log(1 + self.n / self.df[t]) for t in hit)
            s /= max(1, len(dt)) ** 0.5      # 长度归一化，否则长回复通吃
            scored.append((s, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:k]]


def block(hits, cap: int = 80) -> str:
    if not hits:
        return ""
    lines = ["【可能相关的原话】"]
    for r in hits:
        who = "对方" if r["role"] == "user" else "我"
        lines.append(f"- {r['dt'][5:16]} {who}：{r['text'].strip()[:cap]}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--config", default=str(HERE / "settings.json"))
    ap.add_argument("-k", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cfg = {}
    cp = Path(a.config)
    if cp.exists():
        cfg = json.loads(cp.read_text(encoding="utf-8"))
    base = cp.parent if cp.exists() else HERE
    events = Path(cfg.get("out", "events.jsonl"))
    if not events.is_absolute():
        events = base / events
    if not events.exists():
        raise SystemExit(f"找不到 {events}，先跑 extract.py")

    hits = Index(events).search(a.question, a.k)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    else:
        print(block(hits))


if __name__ == "__main__":
    main()
