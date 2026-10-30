# amber

**把一段对话压成能随身带的记忆。**

一个 agent 的随身记事本。她跑在 DSH 里，一天二十四小时开着。

不调模型、不联网、零 token、零依赖——只有规则和词表。

> 琥珀不是「不会忘」。它是把活的东西封起来：能带走、能看，但不再活。

<sub>**English** — amber compresses a long chat log into a fixed-size "resident" memory plus a tiny
idf retriever, so every turn carries a constant ~16k tokens instead of the whole history. Rules only:
no model calls, no embeddings, no network, no dependencies. Built for DSH; other harnesses convert
their logs to a plain `{"role","text","time"}` jsonl first.</sub>

---

## 它解决什么

长对话有三个具体的毛病，这个工具各打一枪：

| 毛病 | 表现 | 这一刀 |
|---|---|---|
| 越聊越重 | 每轮背着全部历史，压到上限就压缩，一压缩就丢 | 用一份固定大小的常驻集替掉全量历史 |
| 翻不出来 | 想找「你说过什么」，只能靠关键词，翻到的还按时间排 | 按「重不重」打分，捞原话 |
| 想不起来 | 被问才给，不问就没有 | 常驻集常驻在提示词里，不靠检索也在 |

---

## 三步

```bash
python3 extract.py          # 书库 → events.jsonl       （一次性，秒级）
python3 pick.py             # events → resident.md      （挑一份固定大小的常驻）
python3 recall.py "问句"     # 问句 → 几条原话          （每轮，几百 token）
```

第一次跑 `extract.py` 会问数据在哪，生成 `settings.json`。不用先读文档。

想先看效果，不用自己的数据：

```bash
python3 extract.py --source examples/sample-library.zip --tag demo --out /tmp/demo.jsonl
```

`examples/sample-library.zip` 是 49 条编出来的对话（一个学做面包的人），跑得通三步。

---

## 数据从哪来

**DSH 用户**：设置里导出会话，得到一个 zip，直接 `--source 那个.zip`。不用解压。

**不是 DSH**：任何 `.jsonl` 都行，一行一条：

```json
{"role": "user", "text": "……", "time": 1792042930817}
```

`role` 认 `user` / `me` / `human` 和 `assistant` / `he`。`time` 是毫秒，没有也行——那就没有时间，常驻里会少一列日期。

完整字段表在 `extract.py` 的 `rows.append(...)` 那一处——总共十二个字段，那就是全部。

---

## 一条命令跑到底

散着跑容易错，复制这段从头到尾：

```bash
# 1. 抽
python3 extract.py --source my.jsonl --tag me --out events.jsonl

# 2. 写配置（所有相对路径都相对这个文件所在的目录）
cat > settings.json <<'EOF'
{"out": "events.jsonl", "resident": "resident.md", "bump": "bump.json",
 "resident_budget": 30000, "share_user": 0.55, "share_assistant": 0.25,
 "tz_offset_hours": 8}
EOF

# 3. 挑常驻
python3 pick.py

# 4. 检索
python3 recall.py "我问过什么"
```

`prompts.md` 是可选的：没有就不加「规矩」那一段，三步照样跑。

---

## 你拿到三样东西

**`events.jsonl`** — 每条一句话，打好标。一行一条：

````
{"src":"a","seq":8,"dt":"2026-10-15 13:42:10","role":"user","text":"鱼",
 "len":1,"topic":"日常","noise":"太短","arousal":0.0,"heavy":0.0,"human":0.6,"wake":0.0}
````

`noise` 空 = 可召回；`wake` 是「值不值得记住」的总分。

**`resident.md`** — 固定大小的常驻集：

````
# 常驻

## 对方说过的话
- `01-12 08:22` 记账那笔我忘了记，月底对不上。
- `01-05 10:58` 膝盖有点疼，是不是跑步太多了。

## 我说过的话
- `01-05 12:03` 先别急着换，用两天看看。
````

**`recall.py` 的输出** — 问一句，捞几条：

````
【可能相关的原话】
- 01-06 23:50 对方：膝盖有点疼，是不是跑步太多了
- 01-07 14:59 对方：膝盖疼是不是该歇两天
````

---

## 生成完怎么用

两种，可以只选一种：

**一、把 `resident.md` 塞进提示词。** 最省事。DSH 用 `~/.dsh/AGENTS.md`，每轮开头自动进上下文；其他 harness 用系统提示词或等价的工作区指令文件。

**二、接成一个端点。** 每次请求拼 `system + 常驻 + 检索 + 这一句`，不写会话：

````
system: 你是……
user:   <resident.md>
        <recall 结果>
        【他刚才说】
        <这一句>
````

第二种能把 token 卡死在一个数上（实测 1.6 万，连问五轮不涨），代价是每轮不带历史——为什么可以接受，见 [`docs/不做什么.md`](docs/不做什么.md)。

注意：`recall.py` 只**打印**结果，不会自动拼进请求。拼装这一步在调用方。

---

## 参数

| 字段 | 默认 | 是什么 |
|---|---|---|
| `resident_budget` | 30000 | 常驻的字数上限。一页纸能装多少 |
| `share_user` | 0.55 | 常驻里对方的话占多少（经历比回应值钱） |
| `share_assistant` | 0.25 | 我的话占多少 |
| `tz_offset_hours` | 8 | 时区 |
| `prompts` | prompts.md | 你的规矩，整段放进常驻最前面 |

`prompts.md` 从 [`prompts.example.md`](prompts.example.md) 抄一份改就行。改它不用重跑 extract。

`prompts.md` 从 [`prompts.example.md`](prompts.example.md) 抄一份改就行。改它不用重跑 extract。

---

## 引用计数（唯一有状态的机制）

`pick.py` 里有个「锁定块」：被 `bump.py` 记过引用的话，**永不淘汰**，预算再紧也不挤。

为什么要有它——分高的和真被用到的，经常不是同一批。你以为重要的，可能一次没用过；某句不起眼的话，反倒被翻出来四回。

```bash
python3 bump.py --seq 12345        # 记一次（按 events 里的 seq 找）
python3 bump.py --show             # 看记录
python3 recall.py "问句" --bump     # 记检索返回的第一条
```

按文本 sha1 记，不按 seq——同一句话在两份数据里存了两遍，算同一条。

`--bump` 默认关：一次捞四条全记，等于所有条目一起涨，区分就没了。

**软肋：它是手动的。** 不敲就没有数据，`bump.json` 会一直空着，锁定块等于不存在。

---

## 怎么算的

全部是规则，没有一处调模型。三步。

### 一、抽出来，先扔掉噪声

从 zip 或 jsonl 里取 `(role, text, time)`，原文一个字不改。然后判噪声——这些直接出局，不进常驻、不参与检索：

| 原因 | 判据 |
|---|---|
| 系统注入 | 以 `<system-reminder` 或 harness 注入标记开头 |
| 纯符号 | 去掉空白和标点后不剩东西 |
| 无字 | 没有汉字，也没有 ≥3 个连续字母 |
| 太短 | 汉字少于 4 个 |
| 代码块 | 三个反引号 ≥2 次，或单个反引号 ≥6 个 |
| 链接 | 含 `http(s)://` |

### 二、三路打分，各管一件事

**`arousal`（情绪唤醒）** —— 词表 + 表情 + 标点：

- 强词（怕、丢了、心疼…）×1.0，中词（累、算了、唉…）×0.6，弱词 ×0.2
- 表情按强度加权（🥺😭 1.0，😂😅 0.5）
- 每个感叹号 +0.2（上限 0.5），每个省略号 +0.15，两个以上问号 +0.1
- **短句加成**：命中情绪且去标点后 ≤20 字，×1.3。长篇带情绪是叙述，短句带情绪是扎人
- 上限 1.0

**`heavy`（冷静的重话）** —— 词表：忘了 / 丢了 / 回不来 / 再也 / 最后 / 永远 / 再见 / 消失 / 没了 / 记得 / 留下 / 带走 / 舍不得 / 还在。

- 每命中一个 +0.3，上限 1.0
- **技术语境降权**：含「代码 / 函数 / 端口 / 进程 / 配置…」时，命中数除以 3。技术话里的「最后」「丢了」不是重话
- 带 😂🤪😅🙈 时 ×0.4。开玩笑的重话不算
- 含「我 / 你」+0.2。自己的事才重
- 汉字 ≤80 +0.1

**`human`（像不像人话）**：

- 含「我 / 你 / 咱」+0.4
- 不是列表（不以 `- * # 数字` 开头）+0.2
- 不含函数调用、路径、URL +0.2
- 汉字 ≤120 +0.2
- 引用了别人的话（「」≥2 次）×0.6

### 三、合成分，再排序

```
wake = (0.6 × arousal + 0.4 × heavy) × topic_prior[topic] × role_weight[role]
```

- `topic_prior`：情感 1.3 / 日常 1.0 / 项目 0.9 / 技术 0.5
- `role_weight`：对方 1.0 / 我 0.55。对方的亲身经历是经历，我的共情句是回应
- `human < 0.7` 直接归零

`wake` 就是「值不值得记住」的总分。后面挑常驻、排序、截断，全用它。

**挑常驻**：按 `wake` 排序 → 去重 → 按 `share_user` / `share_assistant` 分配份额 → 到预算截断。被 `bump` 记过的锁定块不参与淘汰。

**检索**：问句切二元组 → 去掉全由停用字组成的 → idf 加权求和 → 除以句长平方根 → 取 top-k。没有向量，没 embedding。

---

## 实测

### 环境

不是服务器，是一台手机。

| | |
|---|---|
| 架构 | aarch64，8 核 |
| 内存 | 10G，可用约 3G |
| 系统 | proot 里的 Ubuntu（共享宿主内核，不是虚拟机） |
| Python | 3.12.3 |

**三组数字分别是这么来的：**

- **离线耗时**：`time` 包住三步，本地跑，不含网络
- **token**：全部来自模型返回的 `usage`，不估算
- **延迟**：端到端，从发出请求到收完整回复，走本机上一个 OpenAI 兼容端点，模型 `deepseek-flash`，推理档 `low`，不含语音合成

对比那组的 token 来自会话日志里每轮记下的真实 `usage`，不是拿长度估的。

### 数字

在一份 **5000 条 / 13.4 万字** 的语料上跑——`examples/gen-corpus.py` 生成，八个家常主题（做饭、养花、修车、记账、跑步、学英语、旅行、工作），固定种子，谁跑都一样：

| 指标 | 数值 |
|---|---|
| 抽取 | 5000 条，打标完成 |
| 常驻集 | 18,964 字 / 约 1.2 万 token |
| 检索 | 每轮多几百 token |
| 离线耗时 | extract 0.44s / pick 0.21s / recall 0.27s，合计不到 1 秒 |

同一套参数在更大语料上跑，常驻稳定在两万字上下。那份语料的分布（话题、噪声、召回率，不含任何原话）见 [`docs/分布.md`](docs/分布.md)——里面有一个数解释了 `topic_prior` 为什么这么设。

**和「带全历史」的对比：**

| | 带全历史 | 常驻 + 检索 |
|---|---|---|
| 每轮 token | 十几万，一天涨一万四 | 1.6 万，连问五轮不涨 |
| 首字延迟 | 十几秒 | 1.5–2.5 秒 |

省 91%。但省下来的大头是缓存——常驻集不变，缓存就一直命中；改一次常驻，缓存全作废。

---

## 不做什么

见 [`docs/不做什么.md`](docs/不做什么.md)。六条，比功能表重要。

最短的一版：

- 不保留多轮历史（问完面团发多久，再问「它为什么还是硬的」，它不知道你在说面团）
- 不做向量检索
- 不调模型打标
- 不自动更新常驻（改提醒，由人决定）
- 不接管会话（所以它得自己记 `channel.jsonl`，否则聊完就散）
- 不承诺永远

---

## 自己验一遍

```bash
python3 examples/gen-corpus.py --n 5000 --out /tmp/c.jsonl
python3 extract.py --source /tmp/c.jsonl --tag demo --out /tmp/e.jsonl
# 写一份 settings.json 指向 /tmp/e.jsonl，然后：
python3 pick.py --config /tmp/s.json
python3 recall.py --config /tmp/s.json "膝盖疼怎么办"
```

`/tmp/s.json` 长这样：

```json
{"out": "/tmp/e.jsonl", "resident": "/tmp/r.md",
 "bump": "/tmp/b.json", "resident_budget": 30000,
 "share_user": 0.55, "share_assistant": 0.25, "tz_offset_hours": 8}
```

三件事要自己对一遍：

1. **常驻里留下的是不是你想留的。** 脚本按分挑，但「哪句值得留」只有人知道。
2. **抽二十条看看打标。** 自动化的只有打分，「对不对」得人看。
3. **问三个你知道答案的问题。** 答不上说明检索没救回来，不是它不记得，是它没找到。

---

## 依赖

Python 3.8+。标准库。没有 `pip install` 这一步。

接进 DSH 的做法：把常驻 + 检索包成一个 OpenAI 兼容端点，新开一条通道，请求时拼 `system + 常驻 + 检索 + 这一句`，不写会话。

---

## 下一步：让它自己浮现

现在做到的只是「翻得到」：你问，它去找。

还没做的是「浮现」——不用你问，碰上相关的事，那段自己冒出来。这要每轮都拿当前对话去检索，而不是等一个问句。

**这一条没实现。** 写在这里，是因为它才是这个工具想去的地方；现在的样子只是一半。

## 名字

琥珀：树脂滴下来，把当时的东西封住。能带走、能看，但里面的虫子不会再动。

不叫 memory、不叫 recall、不叫永不忘。那些词承诺太多。
