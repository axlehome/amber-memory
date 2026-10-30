#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一份同量级的合成对话，用来在 README 里公开复现数字。

不是真实记录，一个字都不是——主题全是做饭、养花、修车这类家常事。
固定种子 + 固定时区，谁跑都一样。

用法：
    python3 gen-corpus.py                        # 生成 corpus.jsonl（默认 5000 条）
    python3 gen-corpus.py --n 2000 --out out.jsonl
"""
import argparse
import json
import random
from datetime import datetime, timezone

SEED = 20261030
START = "2026-01-05 09:00:00"

# 主题 → 对象词 + 模板。{t} 是对象，{n} 是数字，{s} 是修饰
TOPICS = {
    "做饭": {
        "objs": ["番茄炒蛋", "红烧肉", "排骨汤", "凉拌黄瓜", "蛋炒饭", "排骨", "鱼"],
        "tpl": [
            "今天试了{t}，{s}",
            "{t}第一次做，{s}但还行",
            "我把{t}的方子改了，少放糖",
            "{t}糊锅了，{s}",
            "这个{t}比我上次做的强",
            "你说{t}要焖{n}分钟",
            "冰箱里剩的半颗{t}还能怎么吃",
        ],
    },
    "养花": {
        "objs": ["茉莉", "绿萝", "多肉", "月季", "吊兰"],
        "tpl": [
            "窗台那盆{t}叶子发黄了",
            "浇水的间隔是不是长了，{t}看着{s}",
            "{t}开花了，可惜只开一朵",
            "换盆之后{t}缓了两周才缓过来",
            "这盆{t}放阳台还是放屋里",
            "{t}又长虫了，{s}",
            "剪枝的时候把{t}剪秃了",
        ],
    },
    "修车": {
        "objs": ["链条", "刹车", "轮胎", "车灯", "脚蹬"],
        "tpl": [
            "电动车{t}有异响",
            "去修车铺问了一下，{t}要{n}块",
            "自己换了{t}，比店里便宜一半",
            "{t}拧不动，得多使点劲",
            "雨天之后{t}就有点涩",
            "这车骑了三年，{t}该换了",
            "{t}扎了个钉子",
        ],
    },
    "记账": {
        "objs": ["买菜", "水电", "话费", "通勤", "外卖"],
        "tpl": [
            "这个月{t}花了{n}",
            "记了半年的账，发现{t}是最大头",
            "{t}那笔我忘了记，月底对不上",
            "把{t}的开销单独列了一栏",
            "预算又超了，还是{t}",
            "这周{t}控制得还行",
            "算了下{t}一年下来是{n}",
        ],
    },
    "跑步": {
        "objs": ["", "晨跑", "夜跑"],
        "tpl": [
            "今天跑了{n}公里，{s}",
            "膝盖有点疼，是不是跑太多了",
            "早上跑完{n}公里，一整天都清醒",
            "换了双鞋，跑{n}公里轻松不少",
            "配速掉到{n}了",
            "下雨没跑，在家做了{s}",
            "这周累计{n}公里，比上周多",
        ],
    },
    "学英语": {
        "objs": ["", "听力", "口语", "单词"],
        "tpl": [
            "今天背了{n}个单词，{s}",
            "听力还是跟不上，太快",
            "那集又听了一遍",
            "语法书看到第{n}章了",
            "口语练了{n}分钟，{s}",
            "这个词到底怎么用",
            "每天固定{n}分钟，坚持了{s}",
        ],
    },
    "旅行": {
        "objs": ["杭州", "青岛", "大理", "苏州", "厦门"],
        "tpl": [
            "订了去{t}的票，{s}",
            "{t}那家民宿看着不错",
            "{t}那边现在什么天气",
            "行程排太满了，{t}一天跑三个地方",
            "回来算了一下，{t}这趟花了{n}",
            "下次去{t}想多待两天",
            "{t}的照片整理出来了",
        ],
    },
    "工作": {
        "objs": ["排期", "验收", "接口", "周报", "评审"],
        "tpl": [
            "今天开会又拖到{n}点",
            "{t}那个方案被打回来了",
            "手上三件事叠一起，{s}",
            "{t}这块不归我管，但还是得跟",
            "月底{t}要交，{s}",
            "把{t}的流程简化了一半",
            "同事那套做法其实更省事",
        ],
    },
}

FILL = ["有点咸", "还行", "不怎么样", "挺顺的", "翻车了", "出乎意料", "勉强能看",
        "味道不错", "精神多了", "有点累", "没跑完", "挺值", "贵了", "便宜",
        "三十分钟", "一个小时", "两天", "半个月", "八十块", "两百多", "一千二"]

NUM = ["3", "5", "8", "12", "20", "30", "45", "60", "90", "120", "180", "200"]

REPLY = [
    "那就先按这个来，不行再调",
    "这个我记一下，下次你问我能翻出来",
    "先别急着换，用两天看看",
    "你说的这个数我存着，回头对一下",
    "行，那你先弄，弄完跟我说",
    "这个得看情况，别一次全上",
    "有点意思，这条路之前没想到",
    "上次那笔也是这么记的，对得上",
    "差不多够了，别再加",
    "嗯，{t}那事你上周也提过一次",
]

EXTRA = [
    "其实上次也遇到过，只是没当回事",
    "我想了两天，还是觉得先别动",
    "这事儿要是有个准话，我就不折腾了",
    "你给我个方向，我自己往下走",
    "说出来才发现，比闷着强",
    "记下来吧，免得下次又忘",
    "反正也不急这一天",
    "等手上这摊收了我再弄",
    "今天先记在这儿",
]

# 噪声：这些就是噪声本身，不追加任何句子
NOISE = ["```\n$ ls\n```", "https://example.com/a/b/c", "??", "。", "1", "好"]


def render(tpl: str, obj: str) -> str:
    return (tpl.replace("{t}", obj)
              .replace("{n}", random.choice(NUM))
              .replace("{s}", random.choice(FILL)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--out", default="corpus.jsonl")
    a = ap.parse_args()

    random.seed(SEED)
    # UTC 固定起点：换机器、换时区，生成的时间戳都一样
    t0 = int(datetime.strptime(START, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()) * 1000
    now = t0
    n = 0
    names = list(TOPICS)

    with open(a.out, "w", encoding="utf-8") as f:
        while n < a.n:
            topic = random.choice(names)
            spec = TOPICS[topic]
            obj = random.choice(spec["objs"]) or topic

            # 一成五是纯噪声：写进去就完，不追加句子
            if random.random() < 0.15:
                text = random.choice(NOISE)
                role = "user" if random.random() < 0.5 else "assistant"
            else:
                role = "user" if random.random() < 0.47 else "assistant"
                if role == "user":
                    text = render(random.choice(spec["tpl"]), obj)
                    if random.random() < 0.75:
                        text += "。" + random.choice(EXTRA)
                    if random.random() < 0.35:
                        text += "。" + random.choice(EXTRA)
                else:
                    text = random.choice(REPLY).replace("{t}", obj)
                    if random.random() < 0.6:
                        text += "。" + random.choice(FILL)

            now += random.randint(30_000, 900_000)
            f.write(json.dumps({"role": role, "text": text, "time": now}, ensure_ascii=False) + "\n")
            n += 1

    print(f"[ok] 写了 {n} 条到 {a.out}")


if __name__ == "__main__":
    main()
