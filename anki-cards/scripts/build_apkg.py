#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从卡片 Markdown 生成 Anki .apkg（可选同时导出 .tsv）。

卡片 Markdown 约定格式（每条占一行）：

    ### 01
    - **正面**：问题？
    - **背面**：答案。
    - **标签**：主题::分组
    - **补充**：可选，显示为灰色小字备注

用法：
    python build_apkg.py --md 卡片.md --deck "All::1 - Network::1 - SRv6"
    python build_apkg.py --md 卡片.md --deck "All::1 - Network::1 - SRv6" \
        --groups "1-46:基础,47-96:冲刺" --tsv

依赖：genanki（pip install genanki）
"""
import argparse
import os
import re
import sys
import zlib

try:
    import genanki
except ImportError:
    sys.exit("[错误] 缺少 genanki，请先安装：pip install genanki")

# 固定的模板 ID：所有主题共用同一个「问答卡」模板，避免 Anki 里模板膨胀
MODEL_ID = 1793841699101
MODEL_NAME = "问答卡"

QFTM = '<div class="q">{{Question}}</div>'
AFMT = (
    "{{FrontSide}}\n<hr id=answer>\n"
    '<div class="a">{{Answer}}</div>\n'
    "{{#Notes}}<div class=\"notes\">{{Notes}}</div>{{/Notes}}"
)

CARD_RE = re.compile(r"^###\s*(\d+)\s*$", re.M)
FIELD_RE = r"^- \*\*(?:%s)\*\*\s*[：:]\s*(.*)$"


def grab(body, names):
    for n in names:
        m = re.search(FIELD_RE % re.escape(n), body, re.M)
        if m:
            return m.group(1).strip()
    return ""


def md2html(text):
    """Markdown 行内语法转 HTML。仅处理粗体与行内代码；其余原样保留。"""
    text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return text.replace("\t", " ").replace("\r", "").replace("\n", "<br>")


def parse_cards(md_path):
    text = open(md_path, encoding="utf-8").read()
    parts = CARD_RE.split(text)
    if len(parts) < 3:
        sys.exit("[错误] 未找到卡片。请用 '### 01' 这样的三级标题标记每张卡的起始。")

    cards = []
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1]
        cards.append({
            "n": num,
            "front": grab(body, ["正面", "问题", "Q"]),
            "back": grab(body, ["背面", "答案", "A"]),
            "tag": grab(body, ["标签", "tags", "Tags"]),
            "note": grab(body, ["补充", "备注", "Notes"]),
        })
    return cards


def validate(cards):
    problems = []
    nums = [c["n"] for c in cards]
    if len(set(nums)) != len(nums):
        dup = sorted({n for n in nums if nums.count(n) > 1})
        problems.append("编号重复：%s" % dup)
    expect = list(range(min(nums), max(nums) + 1))
    if sorted(nums) != expect:
        miss = [n for n in expect if n not in nums]
        if miss:
            problems.append("编号不连续，缺：%s" % miss)

    for c in cards:
        if not c["front"]:
            problems.append("第 %02d 张缺正面" % c["n"])
        if not c["back"]:
            problems.append("第 %02d 张缺背面" % c["n"])
        if not c["tag"]:
            problems.append("第 %02d 张缺标签" % c["n"])
        elif "::" not in c["tag"]:
            problems.append("第 %02d 张标签缺少 '::' 层级（如 主题::分组）" % c["n"])
        for key, label in (("front", "正面"), ("back", "背面"), ("note", "补充")):
            if c[key].count("**") % 2:
                problems.append("第 %02d 张%s的 ** 未闭合（粗体标记落单）" % (c["n"], label))
    return problems


def parse_groups(spec):
    """解析 '1-46:基础,47-96:冲刺' -> [(1, 46, '基础'), ...]"""
    out = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        rng, _, name = chunk.partition(":")
        lo, _, hi = rng.partition("-")
        try:
            out.append((int(lo), int(hi), name.strip()))
        except ValueError:
            sys.exit("[错误] 无法解析分组：%r，应为 '起始-结束:名称'" % chunk)
    return out


def stable_id(key):
    return zlib.crc32(key.encode("utf-8")) % (10 ** 9)


def write_tsv(cards, path):
    lines = []
    for c in cards:
        lines.append("\t".join([md2html(c["front"]), md2html(c["back"]), c["tag"]]))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def build_apkg(cards, deck_name, out_path, css, model_name):
    model = genanki.Model(
        MODEL_ID,
        model_name,
        fields=[{"name": "Question"}, {"name": "Answer"}, {"name": "Notes"}],
        templates=[{"name": "Card 1", "qfmt": QFTM, "afmt": AFMT}],
        css=css,
    )
    deck = genanki.Deck(stable_id(deck_name), deck_name)
    for c in cards:
        deck.add_note(genanki.Note(
            model=model,
            fields=[md2html(c["front"]), md2html(c["back"]), md2html(c["note"])],
            tags=[c["tag"]],
            guid=genanki.guid_for("%s|%d" % (deck_name, c["n"])),
        ))
    genanki.Package(deck).write_to_file(out_path)


def main():
    ap = argparse.ArgumentParser(description="卡片 Markdown -> Anki apkg / tsv")
    ap.add_argument("--md", required=True, help="卡片 Markdown 路径")
    ap.add_argument("--deck", required=True, help='牌组全名，如 "All::1 - Network::1 - SRv6"')
    ap.add_argument("--out", default=None, help="输出目录（默认与 md 同目录）")
    ap.add_argument("--name", default=None, help="apkg 文件名前缀（默认取牌组末段）")
    ap.add_argument("--groups", default=None,
                    help='分批，如 "1-46:基础,47-96:冲刺"；不填则整包一个牌组')
    ap.add_argument("--css", default=None, help="自定义 CSS（默认 assets/card.css）")
    ap.add_argument("--model-name", default=MODEL_NAME, help="卡片类型名称")
    ap.add_argument("--lowercase-tags", action="store_true",
                    help="把标签整体转小写（对齐 k8s::core 风格）")
    ap.add_argument("--tsv", action="store_true", help="同时导出 TSV")
    ap.add_argument("--dry-run", action="store_true", help="只校验，不生成文件")
    args = ap.parse_args()

    cards = parse_cards(args.md)
    if args.lowercase_tags:
        for c in cards:
            c["tag"] = c["tag"].lower()

    problems = validate(cards)
    print("解析到 %d 张卡片（编号 %d-%d）" % (len(cards), cards[0]["n"], cards[-1]["n"]))
    if problems:
        print("!! 校验未通过：")
        for p in problems:
            print("   -", p)
        if not args.dry_run:
            sys.exit("已中止生成。修正后重试，或加 --dry-run 只做校验。")
    else:
        print("校验通过：编号连续、字段完整、标签格式正确")

    if args.dry_run:
        return

    outdir = args.out or os.path.dirname(os.path.abspath(args.md))
    os.makedirs(outdir, exist_ok=True)

    here = os.path.dirname(os.path.abspath(__file__))
    css_path = args.css or os.path.join(here, "..", "assets", "card.css")
    css = open(css_path, encoding="utf-8").read()

    # 文件名前缀：取牌组末段的主题名，"All::1 - Network::1 - SRv6" -> "SRv6"
    prefix = args.name
    if not prefix:
        last = args.deck.split("::")[-1]
        prefix = last.split(" - ")[-1].strip() if " - " in last else last.strip()

    groups = parse_groups(args.groups) if args.groups else None
    if not groups:
        path = os.path.join(outdir, "%s.apkg" % prefix)
        build_apkg(cards, args.deck, path, css, args.model_name)
        print("生成 %s | %d 张 | 牌组 %s" % (os.path.basename(path), len(cards), args.deck))
        if args.tsv:
            tsv = os.path.join(outdir, "%s.tsv" % prefix)
            write_tsv(cards, tsv)
            print("生成 %s" % os.path.basename(tsv))
        return

    total = 0
    for idx, (lo, hi, name) in enumerate(groups, 1):
        rows = [c for c in cards if lo <= c["n"] <= hi]
        if not rows:
            print("!! 跳过空分组：%s（%d-%d）" % (name, lo, hi))
            continue
        deck_name = "%s::%d - %s" % (args.deck, idx, name)
        path = os.path.join(outdir, "%s__%d - %s.apkg" % (prefix, idx, name))
        build_apkg(rows, deck_name, path, css, args.model_name)
        print("生成 %s | %d 张 | 牌组 %s" % (os.path.basename(path), len(rows), deck_name))
        if args.tsv:
            tsv = os.path.join(outdir, "%s_%d_%s.tsv" % (prefix, idx, name))
            write_tsv(rows, tsv)
            print("生成 %s" % os.path.basename(tsv))
        total += len(rows)

    covered = {c["n"] for c in cards}
    grouped = set()
    for lo, hi, _ in groups:
        grouped |= {n for n in covered if lo <= n <= hi}
    missed = sorted(covered - grouped)
    if missed:
        print("!! 有 %d 张未落入任何分组：%s" % (len(missed), missed))
    print("合计 %d / %d 张" % (total, len(cards)))


if __name__ == "__main__":
    main()
