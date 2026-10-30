#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一份同量级的合成对话，用来在 README 里公开复现数字。

不是真实记录，一个字都不是——主题全是做饭、养花、修车这类家常事。
固定随机种子，谁跑都得到同一份。

用法：
    python3 gen-corpus.py              # 生成 corpus.jsonl（默认 5000 条）
    python3 gen-corpus.py --n 2000
"""
import argparse
import json
import random
import time

SEED = 20261030

# 八个主题，各一组「他说的」和「我说的」句子骨架
TOPICS = {
    "做饭": [
        "今天试了个{t}，火大了{s}",
        "你说{t}要焖多久",
        "{t}第一次做，{s}但还行",
        "冰箱里剩的半颗{t}还能怎么吃",
        "我把{t}的方子改了，少放糖",
        "{t}糊锅了，{s}",
        "这个{t}比我上次做的强",
    ],
    "养花": [
        "窗台那盆{t}叶子发黄了",
        "浇水的间隔是不是长了，{t}看着{s}",
        "{t}开花了，可惜只开一朵",
        "换盆之后{t}缓了两周才缓过来",
        "这盆{t}放阳台还是放屋里",
        "{t}又长虫了，{s}",
        "剪枝的时候把{t}剪秃了",
    ],
    "修车": [
        "电动车{t}有异响",
        "去修车铺问了一下，{t}要{s}",
        "自己换了{t}，比店里便宜一半",
        "{t}拧不动，得多使点劲",
        "雨天之后{t}就有点涩",
        "这车骑了三年，{t}该换了",
        "轮胎{ta}扎了个钉子",
    ],
    "记账": [
        "这个月{t}花了{s}",
        "记了半年的账，发现{t}是最大头",
        "{t}那笔我忘了记，月底对不上",
        "把{t}的开销单独列了一栏",
        "预算又超了，还是{t}",
        "这周{t}控制得还行",
        "算了下{t}一年下来是{s}",
    ],
    "跑步": [
        "今天跑了{t}公里，{s}",
        "膝盖有点疼，是不是{t}太多了",
        "早上跑完{t}，一整天都清醒",
        "换了双鞋，跑{t}轻松不少",
        "配速掉到{t}了",
        "下雨没跑，在家做了{s}",
        "这周累计{t}，比上周多",
    ],
    "学英语": [
        "今天背了{t}个单词，{s}",
        "听力还是跟不上，{t}太快",
        "把{t}那集又听了一遍",
        "语法书看到{t}章了",
        "口语练了{t}分钟，{s}",
        "这个词{t}到底怎么用",
        "每天固定{t}，坚持了{s}",
    ],
    "旅行": [
        "订了去{t}的票，{s}",
        "那个{t}的民宿看着不错",
        "{t}那边现在什么天气",
        "行程排太满了，{t}一天跑三个地方",
        "回来算了一下，{t}这趟花了{s}",
        "下次去{t}想多待两天",
        "{t}的照片整理出来了",
    ],
    "工作": [
        "今天开会又拖到{t}点",
        "那个{t}的方案被打回来了",
        "手上三件事叠一起，{s}",
        "{t}这块不归我管，但还是得跟",
        "月底{t}要交，{s}",
        "把{t}的流程简化了一半",
        "同事{t}那套做法其实更省事",
    ],
}

FILL = ["有点咸", "还行", "不怎么样", "挺顺的", "翻车了", "出乎意料", "勉强能看",
        "味道不错", "精神多了", "有点累", "没跑完", "挺值", "贵了", "便宜",
        "三十分钟", "一个小时", "两天", "半个月", "八十块", "两百多", "一千二",
        "五公里", "三公里", "十公里", "二十个", "五十个", "半小时", "四十分钟"]

NUM = ["3", "5", "8", "12", "20", "30", "45", "60", "90", "120", "180", "200"]

# 我的回应骨架
REPLY = [
    "那就先按这个来，不行再调",
    "这个我记一下，下次你问我能翻出来",
    "嗯，{t}那事你上周也提过一次",
    "先别急着换，用两天看看",
    "你说的这个数我存着，回头对一下",
    "行，那你先弄，弄完跟我说",
    "这个得看情况，别一次全上",
    "有点意思，{t}这条路之前没想到",
    "上次那笔也是这么记的，对得上",
    "差不多够了，别再加",
]

NOISE = [
    "```\n$ ls\n```",
    "https://example.com/a/b/c",
    "??",
    "。",
    "",
    "1",
]

TOPIC_NAMES = list(TOPICS.keys())


def fill(s: str, t: str) -> str:
    return (s.replace("{t}", t).replace("{ta}", t)
             .replace("{s}", random.choice(FILL))
             .replace("{t}", random.choice(NUM)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--out", default="corpus.jsonl")
    a = ap.parse_args()

    random.seed(SEED)
    t0 = int(time.mktime(time.strptime("2026-01-05 09:00:00", "%Y-%m-%d %H:%M:%S"))) * 1000
    now = t0
    n = 0
    with open(a.out, "w", encoding="utf-8") as f:
        while n < a.n:
            topic = random.choice(TOPIC_NAMES)
            tmpl = random.choice(TOPICS[topic])
            # 模板里的 {t} 是主题词，用主题名本身
            text = tmpl.replace("{t}", topic).replace("{ta}", topic)
            text = text.replace("{s}", random.choice(FILL)).replace("{t}", random.choice(NUM))
            text = text.replace("{s}", random.choice(FILL))

            role = "user" if random.random() < 0.47 else "assistant"
            if role == "assistant":
                r = random.choice(REPLY).replace("{t}", topic)
                text = f"{r}" if random.random() < 0.75 else f"{r}。{random.choice(FILL)}"

            # 一成多是噪音：短句、空行、代码块、链接
            if random.random() < 0.12:
                text = random.choice(NOISE)
                if not text.strip():
                    continue

            # 七成追加一两次，把平均长度拉到跟真实记录接近
            if random.random() < 0.75:
                extra = random.choice([
                    "其实上次也遇到过，只是没当回事",
                    "我想了两天，还是觉得先别动",
                    "这事儿要是有个准话，我就不折腾了",
                    "你给我个方向，我自己往下走",
                    "说出来才发现，比闷着强",
                    "记下来吧，免得下次又忘",
                ])
                text = text + "。" + extra
                if random.random() < 0.45:
                    text = text + "。" + random.choice([
                        "反正也不急这一天", "等手上这摊收了我再弄",
                        "你要是有空，帮我看看这一步对不对",
                        "今天先记在这儿", "越拖越不想动",
                    ])

            now += random.randint(30_000, 900_000)
            rec = {"role": role, "text": text, "time": now}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"[ok] 写了 {n} 条到 {a.out}")


if __name__ == "__main__":
    main()
