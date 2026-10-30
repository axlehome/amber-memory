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
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CJK = re.compile(r"[\u4e00-\u9fff]")
STOP = set("的了是我你他吗呢吧啊呀嘛哦就都也还很这那个们么什怎样对在有说点会做要能可不没")


def terms(q: str):
    """中英分开切：中文段切二元组，英文词整体收。

    先拼成 `knees疼怎么办` 再切二元组会切出 `s疼` 这种不存在的词，
    纯英文查询则永远 0 命中。所以按语言分段处理。
    """
    out = set()
    for seg in re.findall(r"[\u4e00-\u9fff]+", q):
        if len(seg) > 1:
            for i in range(len(seg) - 1):
                t = seg[i:i + 2]
                if not (set(t) <= STOP):
                    out.add(t)
        else:
            out.add(seg)
    for m in re.finditer(r"[A-Za-z]{2,}", q):
        out.add(m.group(0).lower())
    return out


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
    ap.add_argument("--bump", action="store_true",
                    help="把返回的第一条记一次引用（默认不记：一次记四条等于没区分）")
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

    if a.bump and hits:
        import hashlib
        bp = Path(cfg.get("bump", "bump.json"))
        if not bp.is_absolute():
            bp = base / bp
        data = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {}
        k = hashlib.sha1(hits[0]["text"].encode("utf-8")).hexdigest()[:12]
        data[k] = data.get(k, 0) + 1
        bp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    elif hits:
        print(block(hits))
    else:
        print("没有找到相关的原话。", file=sys.stderr)


if __name__ == "__main__":
    main()
