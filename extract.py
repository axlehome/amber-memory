#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract.py — 把聊天记录抽成 events.jsonl。

进：DSH 导出的书库 zip（内含 session.v4.jsonl），或任何一个 jsonl
出：events.jsonl，一行一条，字段固定（见 README）

不改原文、不删原文、不联网、不调模型。

用法：
    python3 extract.py                      # 读 settings.json；没有就进入引导
    python3 extract.py --source a.zip --tag a --source b.zip --tag b
    python3 extract.py --config my.json
"""
import argparse
import json
import re
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "libs"))
import emotion  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")

# 话题：默认一组通用类别，可在 settings.json 的 topic_rules 里覆盖
DEFAULT_TOPICS = [
    ("技术", r"代码|函数|报错|日志|端口|进程|部署|接口|脚本|编译|配置|git|api|bug|版本"),
    ("项目", r"计划|方案|项目|需求|进度|任务|步骤|验收|预算|时间表|里程碑"),
    ("情感", r"难过|开心|害怕|怕|难受|喜欢|想念|孤独|陪|舍不得|心疼"),
]

# 话题先验：情感 > 日常 > 项目 > 技术
# 技术话里常常出现「丢了」「最后」，不加先验会混进重话
DEFAULT_PRIOR = {"情感": 1.3, "日常": 1.0, "项目": 0.9, "技术": 0.5}

# 谁说的：对方的亲身感受是经历，我的共情句是回应。两者同分就错了
DEFAULT_ROLE_W = {"user": 1.0, "assistant": 0.55}

# 冷静的重话：没表情、没感叹号，但说的是不能丢的事
# 这是一份通用默认值，语言习惯不同就在 settings.json 的 heavy_words 里换掉
HEAVY = ["忘了", "记不住", "丢了", "回不来", "再也", "最后", "永远",
         "再见", "消失", "没了", "记得", "留下", "带走", "舍不得", "还在"]

TECH_CTX = re.compile(
    r"代码|函数|窗口|报错|日志|端口|进程|插件|服务端|session|配置文件|"
    r"部署|接口|token|截图|截图|终端|命令|脚本|文件")


# ---------------------------------------------------------------- settings

def load_settings(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return {}


def ask(question: str) -> str:
    try:
        return input(question).strip()
    except EOFError:
        return ""


def guide() -> dict:
    """第一次跑：问两个问题，生成 settings.json。"""
    print("没有找到 settings.json。\n")
    print("你的数据是哪种？")
    print("  1) DSH 导出的书库 zip")
    print("  2) 已有的 events.jsonl / 聊天记录 jsonl")
    choice = ask("\n输入 1 或 2：")

    if choice not in ("1", "2"):
        print("\n没有选择。用法：\n"
              "  python3 extract.py --source 路径.zip --tag 名字\n"
              "字段说明见 README。")
        sys.exit(2)

    sources = []
    while True:
        p = ask("路径：" if not sources else "还有吗？（回车结束）路径：")
        if not p:
            break
        p = str(Path(p).expanduser())
        tag = ask(f"给它起个短名（回车用文件名）：") or Path(p).stem
        sources.append({"path": p, "tag": tag})

    if not sources:
        print("没有路径，退出。")
        sys.exit(2)

    settings = {
        "sources": sources,
        "out": "events.jsonl",
        "tz_offset_hours": 8,
        "topic_rules": [[n, p] for n, p in DEFAULT_TOPICS],
        "topic_prior": DEFAULT_PRIOR,
    }
    dst = HERE / "settings.json"
    dst.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {dst}")
    return settings


# ---------------------------------------------------------------- 读取

def iter_records(path: Path, tag: str, tz):
    """从 zip 或 jsonl 里逐条吐出 (seq, ts, role, text)。"""
    def parse(line: str, n: int):
        line = line.strip()
        if not line:
            return None
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            return None

        t = e.get("type")
        data = e.get("data") or {}
        if t == "user/message":
            role, msg = "user", data
        elif t == "assistant/message":
            role, msg = "assistant", data.get("message") or {}
        elif "text" in e and "role" in e:
            # 已经是简单格式：
            # {"role": "user"|"assistant", "text": "...", "time": 毫秒}
            role = "user" if e["role"] in ("user", "me", "human") else "assistant"
            return (e.get("seq", n), e.get("time", 0), role, str(e["text"]))
        else:
            return None

        parts = [b.get("text", "") for b in (msg.get("content") or [])
                 if b.get("type") == "text"]
        text = "\n".join(p for p in parts if p).strip()
        if not text:
            return None
        return (e.get("seq", n), e.get("time", 0), role, text)

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            name = "session.v4.jsonl"
            if name not in z.namelist():
                cands = [n for n in z.namelist() if n.endswith(".jsonl")]
                if not cands:
                    print(f"[skip] {path} 里没有 jsonl", file=sys.stderr)
                    return
                name = cands[0]
            with z.open(name) as f:
                for i, line in enumerate(f):
                    r = parse(line.decode("utf-8", "replace"), i)
                    if r:
                        yield (tag,) + r
    else:
        with path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                r = parse(line, i)
                if r:
                    yield (tag,) + r


# ---------------------------------------------------------------- 打标

SYS_INJECT = ("This is an automatically generated", "Current runtime context",
              "# 你醒来会读到这一页", "<system-reminder")


def noise_reason(text: str) -> str:
    t = text.lstrip()
    # 这些不是人说的话：harness 注入的提醒、压缩摘要、工作区说明
    if "<system-reminder" in text or t.startswith(SYS_INJECT):
        return "系统注入"
    bare = re.sub(r"[\s\W_]", "", text)
    if not bare:
        return "纯符号"
    if not CJK.search(text) and not re.search(r"[a-zA-Z]{3,}", text):
        return "无字"
    if len(CJK.findall(text)) < 4:
        return "太短"
    if text.count("```") >= 2 or text.count("`") >= 6:
        return "代码块"
    if re.search(r"https?://\S+", text):
        return "链接"
    return ""


def heavy_score(text: str, words=None) -> float:
    hits = sum(1 for w in (words or HEAVY) if w in text)
    if not hits:
        return 0.0
    if TECH_CTX.search(text):
        hits = max(1, hits // 3)
    if re.search(r"[😂🤪😅🙈]", text):
        hits *= 0.4
    s = min(1.0, 0.3 * hits)
    if re.search(r"我|你", text):
        s = min(1.0, s + 0.2)
    if len(CJK.findall(text)) <= 80:
        s = min(1.0, s + 0.1)
    return round(s, 3)


def human_score(text: str) -> float:
    s = 0.0
    if re.search(r"我|你|咱", text):
        s += 0.4
    if not re.search(r"^[-*#\d]|\n[-*#\d]", text):
        s += 0.2
    if not re.search(r"[A-Za-z_]{4,}\(|\.js|\.py|src/|http", text):
        s += 0.2
    if len(CJK.findall(text)) <= 120:
        s += 0.2
    if text.count("「") >= 2:      # 引用别人的话，不是自己说的
        s *= 0.6
    return round(min(1.0, s), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "settings.json"))
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    cfg_path = Path(a.config).expanduser()
    cfg = load_settings(cfg_path)
    # 所有相对路径都相对 settings.json 所在目录，跟 pick/recall 保持一致
    cfg_base = cfg_path.resolve().parent if cfg_path.exists() else HERE

    if a.source:
        tags = (a.tag + [Path(x).stem for x in a.source])[:len(a.source)]
        sources = [{"path": p, "tag": t} for p, t in zip(a.source, tags)]
    elif cfg.get("sources"):
        sources = cfg["sources"]
    else:
        cfg = guide()
        sources = cfg["sources"]

    tz = timezone(timedelta(hours=cfg.get("tz_offset_hours", 8)))
    topics = [(n, r) for n, r in cfg.get("topic_rules", DEFAULT_TOPICS)]
    prior = cfg.get("topic_prior", DEFAULT_PRIOR)
    heavy_words = cfg.get("heavy_words", HEAVY)
    role_w = cfg.get("role_weight", DEFAULT_ROLE_W)

    def topic_of(text: str) -> str:
        for name, pat in topics:
            if re.search(pat, text, re.I):
                return name
        return "日常"

    rows, by_src = [], {}
    for s in sources:
        p = Path(s["path"]).expanduser()
        if not p.is_absolute():
            p = cfg_base / p
        if not p.exists():
            print(f"[skip] {p} 不存在", file=sys.stderr)
            continue
        n = 0
        for tag, seq, ts, role, text in iter_records(p, s["tag"], tz):
            noise = noise_reason(text)
            hv, hu = heavy_score(text, heavy_words), human_score(text)
            aw = round(emotion.arousal(text), 3)
            topic = topic_of(text)
            wake = 0.0 if noise or hu < 0.7 else round(
                (0.6 * aw + 0.4 * hv) * prior.get(topic, 0.6)
                * role_w.get(role, 1.0), 3)
            rows.append({
                "src": tag, "seq": seq, "time": ts,
                "dt": datetime.fromtimestamp(ts / 1000, tz).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
                "role": role, "text": text, "len": len(text),
                "topic": topic, "noise": noise,
                "arousal": aw, "heavy": hv, "human": hu, "wake": wake,
            })
            n += 1
        by_src[s["tag"]] = n

    rows.sort(key=lambda r: (r["time"], r["src"], r["seq"]))
    out = Path(a.out or cfg.get("out", "events.jsonl"))
    if not out.is_absolute():
        out = cfg_base / out
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    meta = {
        "count": len(rows), "by_src": by_src,
        "by_role": {"user": sum(1 for r in rows if r["role"] == "user"),
                    "assistant": sum(1 for r in rows if r["role"] == "assistant")},
        "first": rows[0]["dt"] if rows else None,
        "last": rows[-1]["dt"] if rows else None,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
