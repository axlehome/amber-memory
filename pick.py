#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pick.py — 从 events.jsonl 挑一份常驻集（固定大小的随身记忆）。

进：events.jsonl（extract.py 产出）+ prompts.md（你的规矩，可选）
出：resident.md

三条原则：
  1. 锁定块不动 —— 被引用过的话（bump.json）永远不淘汰
  2. 只从可换块挤 —— 预算满了，挤掉 wake 最低的
  3. 不自动重跑 —— 跑一次是重挑，旧的好东西会被挤掉；更新请看 README

用法：
    python3 pick.py
    python3 pick.py --budget 30000 --out resident.md
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


ROLE_MAP = {"me": "user", "he": "assistant"}     # 兼容早期格式


def load_rows(path: Path):
    rows = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
    for r in rows:
        r["role"] = ROLE_MAP.get(r["role"], r["role"])
    return rows


def dedupe(items):
    seen, out = set(), []
    for r in items:
        k = re.sub(r"\s+", "", r["text"])[:40]
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def one_line(text: str, cap: int = 140) -> str:
    t = re.sub(r"\s*\n+\s*", " / ", text.strip())
    return t if len(t) <= cap else t[:cap] + "…"


BAD = re.compile(r"\[(Intro|Verse|Chorus|Pre-Chorus|Bridge|Outro)|Piano playing|"
                 r"Soft sigh|Vocal\]")


def usable(r):
    t = r["text"]
    return not (BAD.search(t) or "```" in t or "http" in t)


def take(items, budget, locked_keys):
    """先放锁定的，再按 wake 填，填不下就跳过。"""
    alive = [r for r in items if usable(r)]
    locked = [r for r in alive if r["text"] in locked_keys]
    rest = sorted([r for r in alive if r["text"] not in locked_keys],
                  key=lambda r: -r["wake"])
    out, n = [], 0
    for r in locked + rest:
        line = f"- `{r['dt'][5:16]}` {one_line(r['text'])}"
        if n + len(line) > budget:
            continue
        out.append(line)
        n += len(line)
    return out, n, len(locked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "settings.json"))
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    cfg_path = Path(a.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig")) if cfg_path.exists() else {}
    base = cfg_path.parent if cfg_path.exists() else HERE

    events = Path(cfg.get("out", "events.jsonl"))
    if not events.is_absolute():
        events = base / events
    if not events.exists():
        raise SystemExit(f"找不到 {events}，先跑 extract.py")

    rows = load_rows(events)

    # 骨头：被引用过的话
    bump_path = Path(cfg.get("bump", "bump.json"))
    if not bump_path.is_absolute():
        bump_path = base / bump_path
    locked = set()
    if bump_path.exists():
        b = json.loads(bump_path.read_text(encoding="utf-8"))
        locked = {r["text"] for r in rows
                  if hashlib.sha1(r["text"].encode("utf-8")).hexdigest()[:12] in b}

    budget = a.budget or cfg.get("resident_budget", 30000)
    his_share = cfg.get("share_user", 0.55)
    my_share = cfg.get("share_assistant", 0.25)

    users = dedupe([r for r in rows if r["role"] == "user" and r["wake"] > 0])
    asst = dedupe([r for r in rows if r["role"] == "assistant" and r["wake"] > 0])

    u_lines, u_n, u_lock = take(users, int(budget * his_share), locked)
    a_lines, a_n, a_lock = take(asst, int(budget * my_share), locked)

    head = ""
    prompts = Path(cfg.get("prompts", "prompts.md"))
    if not prompts.is_absolute():
        prompts = base / prompts
    if prompts.exists():
        head = prompts.read_text(encoding="utf-8").strip() + "\n\n"

    doc = (head + "# 常驻\n\n## 对方说过的话\n" + "\n".join(u_lines) +
           "\n\n## 我说过的话\n" + "\n".join(a_lines) + "\n")

    out = Path(a.out or cfg.get("resident", "resident.md"))
    # 统一 LF：Windows 上 write_text 默认把 \n 写成 \r\n，文件字符数会和打印的对不上
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(doc)

    print(f"字数 {len(doc)} / 预算 {budget}")
    print(f"对方 {len(u_lines)} 条 / {u_n} 字（锁定 {u_lock}）")
    print(f"我 {len(a_lines)} 条 / {a_n} 字（锁定 {a_lock}）")
    print(f"估算 token ≈ {int(len(doc) * 0.65)}")


if __name__ == "__main__":
    main()
