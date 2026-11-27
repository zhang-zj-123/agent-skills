#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6 质量门禁：校验问答卡稿，不通过则退出码 1（阻止落主文件）。

卡片格式（与 anki-cards 完全一致，脚本可互换）：
    ### 001
    - **正面**：问题？
    - **背面**：答案。
    - **标签**：主题::分组
    - **补充**：可选

用法：
    python qa_check.py --out out/20261127-sr          # 校验 work/cards/*.md
    python qa_check.py --md 卡片.md                    # 校验单文件
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

CARD_RE = re.compile(r"^###\s*(\d+)\s*$", re.M)
FIELD_RE = r"^- \*\*(?:%s)\*\*\s*[：:]\s*(.*)$"

EMPTY_ANSWER = re.compile(
    r"^(是|不是|有|没有|会|不会|多种|重要|不一定|看情况|都对)[。.!！?？]?$")
DEPEND_WORDS = ("如上所述", "如前所述", "同前所述", "见第", "前述",
                "上一张", "同上", "见上文", "见下文", "参见上")
PUNCT = re.compile(r"[\s，。、；：？！,.;:?!\"'“”‘’（）()【】\[\]《》<>~`\-—_/\\|]+")


def grab(body, names):
    for n in names:
        m = re.search(FIELD_RE % re.escape(n), body, re.M)
        if m:
            return m.group(1).strip()
    return ""


def parse(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    parts = CARD_RE.split(text)
    cards = []
    if len(parts) < 3:
        return cards
    for i in range(1, len(parts), 2):
        body = parts[i + 1]
        cards.append({
            "n": int(parts[i]),
            "front": grab(body, ["正面", "问题", "Q"]),
            "back": grab(body, ["背面", "答案", "A"]),
            "tag": grab(body, ["标签", "tags", "Tags"]),
            "note": grab(body, ["补充", "备注", "Notes"]),
        })
    return cards


def norm(s):
    return PUNCT.sub("", re.sub(r"\d+", "#", s or "")).lower()


def shingles(s, n=3):
    s = norm(s)
    return [s[i:i + n] for i in range(max(0, len(s) - n + 1))] or [s]


def simhash(s):
    v = [0] * 64
    for sh in shingles(s):
        h = int.from_bytes(hashlib.blake2b(sh.encode("utf-8"), digest_size=8).digest(), "big")
        for b in range(64):
            v[b] += 1 if (h >> b) & 1 else -1
    out = 0
    for b in range(64):
        if v[b] > 0:
            out |= 1 << b
    return out


def hamming(a, b):
    return bin(a ^ b).count("1")


def check_file(path, cards, args, errors, warns):
    nums = [c["n"] for c in cards]
    if not nums:
        errors.append("%s：未解析到卡片（检查 '### 001' 标题）" % path.name)
        return
    if nums[0] != 1:
        warns.append("%s：编号未从 1 开始（当前 %d）" % (path.name, nums[0]))
    if len(set(nums)) != len(nums):
        dup = sorted({n for n in nums if nums.count(n) > 1})
        errors.append("%s：编号重复 %s" % (path.name, dup))
    if sorted(nums) != list(range(min(nums), max(nums) + 1)):
        miss = [n for n in range(min(nums), max(nums) + 1) if n not in nums]
        if miss:
            errors.append("%s：编号不连续，缺 %s" % (path.name, miss))

    for c in cards:
        loc = "%s#%03d" % (path.name, c["n"])
        if not c["front"]:
            errors.append("%s：缺正面" % loc)
        if not c["back"]:
            errors.append("%s：缺背面" % loc)
        if not c["tag"]:
            errors.append("%s：缺标签" % loc)
        for key, label in (("front", "正面"), ("back", "背面"), ("note", "补充")):
            if c[key].count("**") % 2:
                errors.append("%s：%s的 ** 未闭合" % (loc, label))
        if c["tag"] and "::" not in c["tag"]:
            errors.append("%s：标签缺 '::' 层级（主题::分组）" % loc)
        if c["tag"] and re.search(r"\s", c["tag"]):
            errors.append("%s：标签含空格，Anki 会拆成多个标签" % loc)
        if c["tag"] and c["tag"] != c["tag"].lower():
            warns.append("%s：标签含大写（建议全小写）" % loc)
        if EMPTY_ANSWER.match(c["back"] or ""):
            errors.append("%s：空卡（答案过于笼统）" % loc)
        if len(c["back"]) > args.max_answer:
            errors.append("%s：答案 %d 字，超过 %d（需拆分或压缩）"
                          % (loc, len(c["back"]), args.max_answer))
        for w in DEPEND_WORDS:
            if w in c["front"] or w in c["back"]:
                errors.append("%s：含依赖词「%s」，单卡抽出来读不懂" % (loc, w))
        if c["front"] and c["front"][-1] not in "？?。.：:":
            warns.append("%s：正面未以问号结尾" % loc)


def collapse(warns):
    """同类提醒（如'标签含大写'）几十条时压成一行，避免刷屏。"""
    cnt = Counter(w.split("：")[-1] for w in warns)
    seen, out = set(), []
    for w in warns:
        k = w.split("：")[-1]
        if cnt[k] > 3:
            if k in seen:
                continue
            seen.add(k)
            out.append("%s（共 %d 处，未逐条列出）" % (k, cnt[k]))
        else:
            out.append(w)
    return out


def main():
    ap = argparse.ArgumentParser(description="问答卡稿质量门禁")
    ap.add_argument("--out", help="工作目录（校验 work/cards/*.md）")
    ap.add_argument("--md", help="单文件校验")
    ap.add_argument("--max-answer", type=int, default=160, help="答案字数上限（默认 160）")
    ap.add_argument("--min-cards", type=int, default=3, help="每来源最少卡数（默认 3）")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = ap.parse_args()

    files = []
    if args.md:
        files = [Path(args.md)]
    elif args.out:
        cards_dir = Path(args.out).resolve() / "work" / "cards"
        files = sorted(cards_dir.glob("*.md"))
        if not files:
            sys.exit("[错误] %s 下没有 .md 卡片稿" % cards_dir)
    else:
        sys.exit("[错误] 需要 --out 或 --md")

    errors, warns = [], []
    all_cards = []
    per_file = {}
    for f in files:
        cards = parse(f)
        per_file[f.name] = len(cards)
        all_cards.extend([(f.name, c) for c in cards])
        check_file(f, cards, args, errors, warns)
        if len(cards) < args.min_cards:
            warns.append("%s：仅 %d 张，覆盖偏薄" % (f.name, len(cards)))

    # 去重（跨文件）
    exact, near = {}, []
    for fname, c in all_cards:
        k = norm(c["front"]) + "||" + norm(c["back"])
        if k in exact:
            errors.append("重复：%s#%03d 与 %s 内容相同" % (fname, c["n"], exact[k]))
            continue
        exact[k] = "%s#%03d" % (fname, c["n"])
        near.append((fname, c["n"], simhash(c["front"] + c["back"])))
    for i in range(len(near)):
        for j in range(i + 1, len(near)):
            d = hamming(near[i][2], near[j][2])
            if d <= 3 and near[i][0:2] != near[j][0:2]:
                warns.append("近重复：%s#%03d 与 %s#%03d（汉明距离 %d）"
                             % (near[i][0], near[i][1], near[j][0], near[j][1], d))

    tagc = Counter(c["tag"] for _, c in all_cards)
    result = {
        "files": per_file,
        "cards": len(all_cards),
        "errors": errors,
        "warnings": warns,
        "tags": dict(tagc),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("校验 %d 个文件，共 %d 张" % (len(files), len(all_cards)))
        for name, n in per_file.items():
            print("  %-14s %d 张" % (name, n))
        print("标签分布：%s" % "，".join("%s(%d)" % (k, v) for k, v in tagc.most_common()))
        if warns:
            flat = collapse(warns)
            print("\n提醒（%d）：" % len(flat))
            for w in flat[:20]:
                print("  -", w)
            if len(flat) > 20:
                print("  … 另有 %d 条" % (len(flat) - 20))
        if errors:
            print("\n[不通过] 错误（%d）：" % len(errors))
            for e in errors[:30]:
                print("  -", e)
            if len(errors) > 30:
                print("  … 另有 %d 条" % (len(errors) - 30))
            sys.exit(1)
        print("\n通过：字段完整、编号合法、无重复严格命中。")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
