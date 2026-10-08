#!/usr/bin/env python3
"""Build this instance's corpus and the public sample. Runs once, from the repository root, when
`ar.py example compress` generates the repository; nothing here is fetched from the network.

The corpus mixes seven kinds of data so that no single trick wins everything:
English prose and Python source come from the local standard library's own docstrings and
source (so the files are real text, not lorem ipsum); the log, the CSV, the Chinese prose and
the repetitive block are generated from a fixed seed; the random bytes are the control that a
"compressor" cannot shrink.
"""

import inspect
import json
import os
import random

CORPUS = os.path.join("autoresearch", "subjects", "codec", "corpus")
SAMPLE = "sample"

ZH_SENTENCES = [
    "清晨的地铁站里，人们握着手机，盯着屏幕上的到站时间。",
    "这座城市的雨总是来得很急，走到街角时鞋已经湿透了。",
    "工程师把咖啡放在键盘旁边，开始读昨天留下的日志。",
    "测试通过并不意味着程序正确，它只说明这些用例还没有发现问题。",
    "老城区的巷子很窄，两辆自行车并排骑过时得侧一下身。",
    "每一次部署之前，团队都会在群里发一句：有人还在改配置吗？",
    "黄昏时分，江边的风把晾在阳台上的衬衫吹得鼓了起来。",
    "数据库迁移脚本跑了四十分钟，所有人都盯着进度条不说话。",
    "小店老板把最后一屉包子端出来，蒸汽在玻璃门上凝成水珠。",
    "我们把接口拆成三层，每一层只回答一个问题。",
    "周末的图书馆比工作日安静得多，翻书的声音都显得很响。",
    "缓存失效的那一刻，流量像退潮后又涌回来的海水。",
    "他在便签上写下三件事，然后把其中两件划掉了。",
    "冬天的早晨，窗户上结着一层薄霜，手指一划就是一道线。",
    "代码审查的目的不是找错，而是让两个人对同一段逻辑有同样的理解。",
    "公交车在红灯前停下，司机顺手把收音机的音量调小了一点。",
    "日志里最有用的往往不是报错那一行，而是它前面的二十行。",
    "菜市场的秤总是比超市的慢半拍，但没有人着急。",
    "新来的同事问为什么这个函数有七个参数，没有人能回答。",
    "傍晚的操场上，几个孩子追着一只不肯落地的风筝。",
    "版本号从零点九跳到一点零的那天，办公室里买了一个蛋糕。",
    "雨停之后，路面上的积水倒映着写字楼的灯光。",
    "监控图上那根突然拔高的线，是凌晨三点的定时任务。",
    "她把钥匙挂在门口的钩子上，这个习惯已经保持了十年。",
    "重构的第一步是写下现在的行为，第二步才是改变它。",
    "山路转过一个弯，云突然散开，远处的村庄露了出来。",
    "回滚只用了两分钟，但找到该回滚的原因花了一个下午。",
    "火车穿过隧道时，车厢里短暂地安静了几秒钟。",
    "配置项的默认值应该是最安全的那个，而不是最方便的那个。",
    "深夜的便利店里，收银员和唯一的顾客聊起了天气。",
]

LEVELS = ["INFO"] * 12 + ["WARN"] * 3 + ["ERROR"] * 1 + ["DEBUG"] * 4
SERVICES = ["api-gateway", "orders", "payments", "inventory", "search", "notifier"]
MESSAGES = [
    "request completed path=/v1/orders/{id} status=200",
    "request completed path=/v1/items/{id} status=200",
    "request completed path=/v1/users/{id}/cart status=200",
    "cache miss key=item:{id}",
    "cache hit key=item:{id}",
    "retrying upstream call attempt={n}",
    "payment authorized order={id} amount={amt}",
    "payment declined order={id} reason=insufficient_funds",
    "stock reserved sku=SKU-{id} qty={n}",
    "search query=\"{q}\" results={n}",
    "notification sent channel=email user={id}",
    "slow query ms={amt} table=orders",
]
QUERIES = ["blue running shoes", "kettle", "usb-c cable 2m", "desk lamp", "rain jacket",
           "coffee grinder", "notebook a5", "wool socks", "phone stand", "garden hose"]
FIRST = ["Wei", "Ana", "Tom", "Yuki", "Omar", "Lena", "Ravi", "Sara", "Ivan", "Mei", "Noah",
         "Zoe", "Kai", "Emma", "Luis", "Nora"]
LAST = ["Chen", "Silva", "Brown", "Tanaka", "Haddad", "Fischer", "Patel", "Novak", "Kim",
        "Rossi", "Nguyen", "Okafor", "Larsen", "Garcia", "Wang", "Dubois"]
CITIES = ["Hangzhou", "Lisbon", "Leeds", "Osaka", "Amman", "Leipzig", "Pune", "Prague", "Busan",
          "Turin", "Hanoi", "Lagos", "Aarhus", "Seville", "Chengdu", "Lyon"]
PRODUCTS = [("kettle", 29.9), ("desk lamp", 42.0), ("notebook a5", 6.5), ("wool socks", 11.0),
            ("phone stand", 15.5), ("usb-c cable 2m", 9.9), ("rain jacket", 79.0),
            ("coffee grinder", 64.0), ("garden hose", 23.0), ("running shoes", 89.0)]


def cut(text, limit):
    """Cut at a line boundary so that the file still reads as text."""
    data = text.encode("utf-8")
    if len(data) <= limit:
        return data
    cutpoint = data.rfind(b"\n", 0, limit)
    return data[:cutpoint + 1] if cutpoint > 0 else data[:limit]


def docstrings(module_names, limit):
    parts, seen = [], set()
    for name in module_names:
        mod = __import__(name)
        for obj in [mod] + [getattr(mod, n, None) for n in sorted(dir(mod))
                            if not n.startswith("_")]:
            doc = inspect.getdoc(obj) if obj is not None else None
            if doc and doc not in seen and len(doc) > 80:
                seen.add(doc)
                parts.append(doc.strip() + "\n")
    return cut("\n".join(parts), limit)


def source(module_name, limit):
    return cut(inspect.getsource(__import__(module_name)), limit)


def events(rng, limit):
    lines, ts = [], 1_760_000_000
    while sum(len(l) for l in lines) < limit:
        ts += rng.randint(1, 9)
        msg = rng.choice(MESSAGES).format(id=rng.randint(1000, 99999), n=rng.randint(1, 60),
                                          amt=round(rng.uniform(5, 400), 2), q=rng.choice(QUERIES))
        rec = {"ts": ts, "level": rng.choice(LEVELS), "service": rng.choice(SERVICES),
               "trace": "%016x" % rng.getrandbits(64), "latency_ms": rng.randint(2, 900),
               "msg": msg}
        lines.append(json.dumps(rec, separators=(",", ":")) + "\n")
    return cut("".join(lines), limit)


def orders(rng, limit):
    lines = ["order_id,date,customer,city,product,qty,unit_price,total\n"]
    n = 10000
    while sum(len(l) for l in lines) < limit:
        n += rng.randint(1, 3)
        product, price = rng.choice(PRODUCTS)
        qty = rng.randint(1, 6)
        lines.append("{},2026-{:02d}-{:02d},{} {},{},{},{},{:.2f},{:.2f}\n".format(
            n, rng.randint(1, 12), rng.randint(1, 28), rng.choice(FIRST), rng.choice(LAST),
            rng.choice(CITIES), product, qty, price, qty * price))
    return cut("".join(lines), limit)


def chinese(rng, limit):
    paragraphs = []
    while sum(len(p.encode("utf-8")) for p in paragraphs) < limit:
        k = rng.randint(4, 7)
        paragraphs.append("".join(rng.sample(ZH_SENTENCES, k)) + "\n\n")
    return cut("".join(paragraphs), limit)


def repeats(rng, limit):
    blocks = []
    while sum(len(b) for b in blocks) < limit:
        i = len(blocks)
        kind = i % 3
        if kind == 0:
            blocks.append("=" * 40 + "\nsection {:03d}\n".format(i) + "-" * 40 + "\n")
        elif kind == 1:
            blocks.append("".join("row {:03d} | {} | {}\n".format(j, "ok" if j % 7 else "retry",
                                                                 "." * (j % 5)) for j in range(12)))
        else:
            blocks.append(("abcabcabd" * 6 + "\n") * 4)
    return cut("".join(blocks), limit)


def noise(rng, limit):
    return bytes(rng.getrandbits(8) for _ in range(limit))


def build(directory, rng, sizes, doc_modules, src_module):
    os.makedirs(directory, exist_ok=True)
    files = {
        "english.txt": docstrings(doc_modules, sizes["text"]),
        "source.py": source(src_module, sizes["text"]),
        "events.jsonl": events(rng, sizes["log"]),
        "orders.csv": orders(rng, sizes["csv"]),
        "zh.txt": chinese(rng, sizes["zh"]),
        "repeats.txt": repeats(rng, sizes["rep"]),
        "noise.bin": noise(rng, sizes["bin"]),
    }
    out = {}
    for name, data in files.items():
        with open(os.path.join(directory, name), "wb") as fh:
            fh.write(data)
        out[name] = len(data)
    return out


corpus = build(CORPUS, random.Random(20261008),
               {"text": 20480, "log": 24576, "csv": 16384, "zh": 8192, "rep": 8192, "bin": 8192},
               ["textwrap", "argparse", "json", "heapq", "bisect", "collections", "itertools",
                "functools", "string", "random", "statistics", "difflib", "fractions",
                "decimal", "logging"], "textwrap")
sample = build(SAMPLE, random.Random(7),
               {"text": 2048, "log": 2048, "csv": 2048, "zh": 1536, "rep": 1024, "bin": 1024},
               ["csv", "shlex", "pprint"], "bisect")
print(json.dumps({"corpus_bytes": sum(corpus.values()), "corpus": corpus,
                  "sample_bytes": sum(sample.values())}))
