"""Deterministic generator for the asset library and the query splits.

Assets are UI assets (icons, illustrations, components, photos) with a fixed set of
attributes. A query names an asset the way a person would - in English or Chinese, with
synonyms, hex colours, size words, typos - and may add a preference that only matters once
several assets fit. Everything is drawn from a seed, so the public split and the held-out split
come from the same distribution but share no query.
"""

import json
import random

SUBJECTS = {
    "search": (["search", "magnifier", "find", "lookup", "magnifying glass"], ["搜索", "放大镜", "查找"]),
    "cart": (["cart", "shopping cart", "basket", "shopping basket"], ["购物车", "购物篮"]),
    "user": (["user", "profile", "avatar", "account", "person"], ["用户", "头像", "账户", "个人中心"]),
    "home": (["home", "house", "homepage", "main page"], ["首页", "主页", "房子"]),
    "settings": (["settings", "gear", "cog", "preferences", "options"], ["设置", "齿轮", "偏好设置"]),
    "back": (["back arrow", "left arrow", "chevron left", "go back", "previous"], ["返回", "左箭头", "后退"]),
    "bell": (["bell", "notification", "alert", "reminder"], ["铃铛", "通知", "提醒"]),
    "trash": (["trash", "delete", "bin", "garbage", "remove"], ["垃圾桶", "删除", "移除"]),
    "heart": (["heart", "like", "favorite", "favourite", "love"], ["爱心", "喜欢", "收藏", "点赞"]),
    "star": (["star", "rating", "rate", "starred"], ["星星", "评分", "星级"]),
    "calendar": (["calendar", "date", "schedule", "agenda"], ["日历", "日期", "日程"]),
    "camera": (["camera", "photo capture", "snapshot", "take picture"], ["相机", "拍照", "摄像头"]),
    "lock": (["lock", "padlock", "secure", "password", "security"], ["锁", "密码", "安全"]),
    "mail": (["mail", "email", "envelope", "inbox", "letter"], ["邮件", "信封", "邮箱"]),
    "download": (["download", "save to device", "get file", "pull down"], ["下载", "保存到本地"]),
    "upload": (["upload", "import", "send file", "attach"], ["上传", "导入", "附件"]),
    "play": (["play", "start playback", "media play", "resume"], ["播放", "开始播放"]),
    "pause": (["pause", "hold", "suspend"], ["暂停"]),
    "edit": (["edit", "pencil", "modify", "compose", "write"], ["编辑", "铅笔", "修改", "撰写"]),
    "share": (["share", "send to", "forward", "share link"], ["分享", "转发"]),
    "filter": (["filter", "funnel", "refine", "narrow down"], ["筛选", "漏斗", "过滤"]),
    "clock": (["clock", "time", "history", "recent"], ["时钟", "时间", "历史记录", "最近"]),
    "map": (["map", "location", "pin", "place", "gps"], ["地图", "定位", "位置", "地点"]),
    "wifi": (["wifi", "wireless", "signal", "network"], ["无线", "信号", "网络"]),
}
STYLES = {
    "line": (["line", "outline", "outlined", "linear", "stroke"], ["线性", "线框", "描边"]),
    "filled": (["filled", "solid", "glyph", "fill"], ["面性", "实心", "填充"]),
    "duotone": (["duotone", "two-tone", "two tone"], ["双色"]),
    "3d": (["3d", "three-d", "isometric"], ["立体", "3D"]),
    "flat": (["flat", "flat style"], ["扁平"]),
}
COLORS = {
    "red": (["red", "crimson", "#ff0000", "#e53935"], ["红色", "红"]),
    "blue": (["blue", "navy", "#1e88e5", "#0000ff"], ["蓝色", "蓝"]),
    "green": (["green", "emerald", "#43a047"], ["绿色", "绿"]),
    "gray": (["gray", "grey", "#9e9e9e", "neutral"], ["灰色", "灰"]),
    "black": (["black", "#000000", "dark"], ["黑色", "黑"]),
    "white": (["white", "#ffffff", "light"], ["白色", "白"]),
    "yellow": (["yellow", "amber", "#fdd835"], ["黄色", "黄"]),
    "purple": (["purple", "violet", "#8e24aa"], ["紫色", "紫"]),
    "orange": (["orange", "#fb8c00", "tangerine"], ["橙色", "橘色"]),
}
SIZES = {
    16: (["16", "16px", "16x16", "small", "sm"], ["16 像素", "小号"]),
    24: (["24", "24px", "24x24", "medium", "md", "regular"], ["24 像素", "中号", "常规"]),
    32: (["32", "32px", "32x32", "large", "lg"], ["32 像素", "大号"]),
    48: (["48", "48px", "48x48", "xl", "extra large"], ["48 像素", "特大"]),
    64: (["64", "64px", "64x64", "xxl", "huge"], ["64 像素", "超大"]),
}
PLATFORMS = {
    "ios": (["ios", "iphone", "apple"], ["苹果", "iOS 端"]),
    "android": (["android", "material"], ["安卓", "安卓端"]),
    "web": (["web", "website", "browser", "desktop"], ["网页", "桌面端"]),
    "all": (["cross-platform", "universal", "any platform"], ["全平台", "通用"]),
}
KINDS = {
    "icon": (["icon", "ico"], ["图标"]),
    "illustration": (["illustration", "illo", "drawing"], ["插画", "插图"]),
    "component": (["component", "widget", "ui block"], ["组件", "控件"]),
    "photo": (["photo", "image", "picture"], ["照片", "图片"]),
}
FORMATS = ["svg", "png", "lottie"]
PREFS = {
    "latest": (["latest", "newest", "most recent version"], ["最新", "最新版"]),
    "popular": (["most popular", "most used", "most downloaded", "widely used"], ["最多人用", "最常用", "下载最多"]),
    "svg": (["svg", "vector"], ["矢量", "svg 格式"]),
    "png": (["png", "bitmap", "raster"], ["png 格式", "位图"]),
    "lottie": (["lottie", "animated", "animation"], ["动效", "动画"]),
}
FILLERS = (["I need", "looking for", "find me", "give me a", "show me"], ["我要一个", "找一下", "请给我", "需要"])
ATTRS = ("style", "color", "size", "platform", "kind")
TABLES = {"style": STYLES, "color": COLORS, "size": SIZES, "platform": PLATFORMS, "kind": KINDS}


def library(rng, per_subject=(18, 30)):
    """Every subject gets a spread of variants; one in ten repeats another's attributes with a
    different version and download count, which is what makes a preference matter."""
    assets = []
    for subject in SUBJECTS:
        variants = []
        for _ in range(rng.randint(*per_subject)):
            if variants and rng.random() < 0.10:
                base = dict(rng.choice(variants))
            else:
                base = {"style": rng.choice(list(STYLES)), "color": rng.choice(list(COLORS)),
                        "size": rng.choice(list(SIZES)), "platform": rng.choice(list(PLATFORMS)),
                        "kind": rng.choice(list(KINDS)), "format": rng.choice(FORMATS)}
            variants.append(base)
        for v in variants:
            v = dict(v)
            v["subject"] = subject
            v["version"] = rng.randint(1, 5)
            v["downloads"] = rng.randint(0, 20000)
            assets.append(v)
    rng.shuffle(assets)
    out = []
    for i, a in enumerate(assets):
        a["id"] = "a{:04d}".format(i + 1)
        a["name"] = "{}-{}-{}".format(a["subject"], a["style"], a["size"])
        tags = [a["subject"], a["style"], a["color"], a["kind"], a["platform"], a["format"],
                str(a["size"])]
        if rng.random() < 0.3:
            tags.append(rng.choice(SUBJECTS[a["subject"]][0][1:]))
        if rng.random() < 0.3:
            tags.append(rng.choice(SUBJECTS[a["subject"]][1]))
        a["tags"] = tags
        if rng.random() < 0.6:
            a["desc"] = "A {} {} {} in {}, {}px, for {}.".format(
                a["style"], a["subject"], a["kind"], a["color"], a["size"], a["platform"])
        else:
            a["desc"] = "{}{}{}{}，{} 像素，{}。".format(
                COLORS[a["color"]][1][0], STYLES[a["style"]][1][0], SUBJECTS[a["subject"]][1][0],
                KINDS[a["kind"]][1][0], a["size"], PLATFORMS[a["platform"]][1][0])
        out.append({k: a[k] for k in ("id", "name", "kind", "subject", "style", "color", "size",
                                       "platform", "format", "version", "downloads", "tags",
                                       "desc")})
    return out


def choose(matches, pref):
    """The selection rule: a format preference filters; latest = highest version; popular and
    the default = most downloads; ties break on the lower id. Returns (asset, effective pref)."""
    pool = list(matches)
    if pref in FORMATS:
        pool = [m for m in pool if m["format"] == pref] or pool
        if pool is matches or len(pool) == len(matches):
            pref = pref if any(m["format"] == pref for m in matches) else None
    if pref == "latest":
        top = max(m["version"] for m in pool)
        pool = [m for m in pool if m["version"] == top]
    pool.sort(key=lambda m: (-m["downloads"], m["id"]))
    return pool[0], pref


def typo(rng, word):
    if len(word) < 5 or not word.isalpha():
        return word
    i = rng.randint(1, len(word) - 3)
    if rng.random() < 0.5:
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    return word[:i] + word[i + 1:]


def phrase(rng, table, key, lang):
    en, zh = table[key]
    if lang == "zh" or (lang == "mix" and rng.random() < 0.5):
        return rng.choice(zh)
    word = rng.choice(en)
    return typo(rng, word) if rng.random() < 0.12 else word


def queries(rng, assets, n, prefix):
    by_subject = {}
    for a in assets:
        by_subject.setdefault(a["subject"], []).append(a)
    out = []
    for i in range(n):
        seed = rng.choice(assets)
        mentioned = rng.sample(ATTRS, rng.randint(1, 3))
        while True:
            matches = [a for a in by_subject[seed["subject"]]
                       if all(a[k] == seed[k] for k in mentioned)]
            if len(matches) <= 20 or len(mentioned) == len(ATTRS):
                break
            mentioned.append(next(k for k in ATTRS if k not in mentioned))
        pref = rng.choice(list(PREFS)) if rng.random() < 0.35 else None
        gt, pref = choose(matches, pref)
        lang = rng.choices(["en", "zh", "mix"], [55, 35, 10])[0]
        parts = [phrase(rng, SUBJECTS, seed["subject"], lang)]
        for k in mentioned:
            parts.append(phrase(rng, TABLES[k], seed[k], lang))
        if pref:
            parts.append(phrase(rng, PREFS, pref, lang))
        rng.shuffle(parts)
        if lang == "zh":
            text = ("的".join(parts[:-1]) + parts[-1]) if len(parts) > 1 and rng.random() < 0.4 \
                else "".join(parts)
        else:
            text = " ".join(parts)
        if rng.random() < 0.3:
            filler = rng.choice(FILLERS[1] if lang == "zh" else FILLERS[0])
            text = filler + text if lang == "zh" else filler + " " + text
        out.append({"id": "{}{:04d}".format(prefix, i + 1), "query": text, "gt": gt["id"],
                    "relevant": sorted(a["id"] for a in by_subject[seed["subject"]])})
    return out


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def generate(library_seed, train_seed, heldout_seed, n_train, n_heldout):
    assets = library(random.Random(library_seed))
    train = queries(random.Random(train_seed), assets, n_train, "q")
    heldout = queries(random.Random(heldout_seed), assets, n_heldout, "h")
    return assets, train, heldout
