#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S7 拼装：合并 work/cards/*.md → 一份结构固定的复习资料 md + 质量报告。

特性：
  - 全局重排编号（1..N 连续，满足 anki-cards 的校验）
  - 跨来源去重（问题+答案归一化后相同则只留首条）
  - 按小节标题或标签分组，输出分组张数与可直接复制的出包命令

用法：
    python assemble.py --out out/20261127-sr
    python assemble.py --out out/20261127-sr --group-by tag --deck "All::1 - Network::1 - SR"
"""
import argparse
import json
import re
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

CARD_RE = re.compile(r"^###\s*(\d+)\s*$")
FIELD_RE = r"^- \*\*(?:%s)\*\*\s*[：:]\s*(.*)$"
HEAD_RE = re.compile(r"^##\s+(.+?)\s*$")
PUNCT = re.compile(r"[\s，。、；：？！,.;:?!\"'“”‘’（）()【】\[\]《》<>~`\-—_/\\|]+")


def grab(body, names):
    for n in names:
        m = re.search(FIELD_RE % re.escape(n), body, re.M)
        if m:
            return m.group(1).strip()
    return ""


def norm(s):
    return PUNCT.sub("", re.sub(r"\d+", "#", s or "")).lower()


def parse_with_heading(path):
    """返回 [(heading, card)]，heading 取卡片上方最近的 '## '。"""
    out, heading = [], "未分组"
    cur = None
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        hm = HEAD_RE.match(line)
        if hm and not line.startswith("###"):
            heading = hm.group(1).strip()
            continue
        if CARD_RE.match(line):
            if cur:
                out.append((cur[0], cur[1]))
            cur = [heading, [line]]
            continue
        if cur is not None:
            cur[1].append(line)
    if cur:
        out.append((cur[0], cur[1]))

    cards = []
    for head, lines in out:
        body = "\n".join(lines)
        cards.append((head, {
            "front": grab(body, ["正面", "问题", "Q"]),
            "back": grab(body, ["背面", "答案", "A"]),
            "tag": grab(body, ["标签", "tags", "Tags"]),
            "note": grab(body, ["补充", "备注", "Notes"]),
        }))
    return cards


def main():
    ap = argparse.ArgumentParser(description="合并卡片稿并拼装复习资料")
    ap.add_argument("--out", required=True)
    ap.add_argument("--topic", default="", help="标题，默认取 manifest 的 topic")
    ap.add_argument("--group-by", choices=["section", "tag"], default="section")
    ap.add_argument("--order", default="",
                    help="指定分组顺序，逗号分隔（如 \"概念,原理,对比\"）；未列出的按出现顺序附后")
    ap.add_argument("--deck", default="", help="仅用于打印出包命令")
    ap.add_argument("--filename", default="", help="主文件名，默认 复习资料_<topic>.md")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    mf_path = out / "_manifest.json"
    if not mf_path.exists():
        sys.exit("[错误] 找不到 _manifest.json")
    manifest = json.loads(mf_path.read_text(encoding="utf-8"))
    topic = args.topic or manifest.get("topic") or out.name

    cards_dir = out / "work" / "cards"
    if not cards_dir.exists():
        sys.exit("[错误] 没有 %s，请先写卡片稿" % cards_dir)

    merged, dropped, per_source = [], 0, OrderedDict()
    seen = {}
    for s in manifest["sources"]:
        f = cards_dir / ("%s.md" % s["id"])
        if not f.exists():
            per_source[s["id"]] = (0, s["status"], s.get("reason", "未产出卡片"))
            continue
        rows = parse_with_heading(f)
        kept = 0
        for head, c in rows:
            if not (c["front"] and c["back"] and c["tag"]):
                continue
            key = norm(c["front"]) + "||" + norm(c["back"])
            if key in seen:
                dropped += 1
                continue
            seen[key] = True
            c["head"] = head
            merged.append(c)
            kept += 1
        per_source[s["id"]] = (kept, "ok", "")
        s["cards"] = kept

    if not merged:
        sys.exit("[错误] 没有可用卡片（检查 work/cards/*.md 是否为空）")

    groups = OrderedDict()
    for i, c in enumerate(merged, 1):
        c["no"] = i
        if args.group_by == "tag":
            second = c["tag"].split("::")[-1]
            key = second
        else:
            key = c["head"]
        groups.setdefault(key, []).append(c)

    # 分组顺序：显式 --order 优先，其余按首次出现顺序附后
    if args.order:
        want = [x.strip() for x in args.order.split(",") if x.strip()]
        reordered = OrderedDict()
        for k in want:
            if k in groups:
                reordered[k] = groups[k]
        for k, v in groups.items():
            if k not in reordered:
                reordered[k] = v
        missing = [k for k in want if k not in groups]
        if missing:
            print("[提醒] --order 中这些分组不存在，已忽略：%s" % "、".join(missing))
        groups = reordered

    # 重排后重新分配连续编号，保证页面上编号顺序与阅读顺序一致
    i = 0
    for items in groups.values():
        for c in items:
            i += 1
            c["no"] = i

    lines = ["# %s 复习资料" % topic, ""]
    ok_src = sum(1 for v in per_source.values() if v[0] > 0)
    lines.append("> 来源：%d 个（成功 %d）· 卡片：%d 张 · 生成：%s"
                 % (len(per_source), ok_src, len(merged),
                    datetime.now().strftime("%Y-%m-%d %H:%M")))
    lines.append("> 格式：每条为原子问答，可直接导入 Anki（qa-cards/v1）")
    lines.append("")

    for name, items in groups.items():
        lines.append("## %s（%d 张）" % (name, len(items)))
        lines.append("")
        for c in items:
            lines.append("### %03d" % c["no"])
            lines.append("- **正面**：%s" % c["front"])
            lines.append("- **背面**：%s" % c["back"])
            lines.append("- **标签**：%s" % c["tag"])
            if c["note"]:
                lines.append("- **补充**：%s" % c["note"])
            lines.append("")

    fname = args.filename or ("复习资料_%s.md" % topic)
    main_path = out / fname
    main_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    # 质量报告
    rep = ["# 质量报告 · %s" % topic, "",
           "生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M"),
           "卡片总数：%d（去重丢弃 %d）" % (len(merged), dropped), "",
           "## 来源状态", "", "| 编号 | 类型 | 状态 | 卡数 | 说明 |", "|---|---|---|---|---|"]
    for s in manifest["sources"]:
        n, st, reason = per_source.get(s["id"], (0, s["status"], ""))
        rep.append("| %s | %s | %s | %d | %s |"
                   % (s["id"], s["kind"], st, n, (s.get("reason") or reason or "—")[:40]))
    rep += ["", "## 分组", "", "| 分组 | 张数 |", "|---|---|"]
    for name, items in groups.items():
        rep.append("| %s | %d |" % (name, len(items)))
    rep += ["", "## 处理提示", ""]
    bad = [s for s in manifest["sources"] if s["status"] != "ok"]
    if bad:
        for s in bad:
            rep.append("- **%s**（%s）：%s → %s"
                       % (s["id"], s["kind"], s["status"], s.get("reason") or "无说明"))
    else:
        rep.append("- 全部来源处理成功。")
    (out / "_quality_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

    mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("主文件：%s（%d 张）" % (main_path, len(merged)))
    print("报告：%s" % (out / "_quality_report.md"))
    print("\n分组：")
    for name, items in groups.items():
        print("  %-24s %3d 张  #%03d–%03d"
              % (name[:24], len(items), items[0]["no"], items[-1]["no"]))

    def clean(name):
        return re.sub(r"[:,\"']+", "", name).strip()[:24] or "组"

    spec = ",".join("%d-%d:%s" % (items[0]["no"], items[-1]["no"], clean(name))
                    for name, items in groups.items())
    deck = args.deck or "All::1 - <分类>:1 - %s" % topic

    parts = ['python "C:\\Users\\ZQ\\.workbuddy\\skills\\anki-cards\\scripts\\build_apkg.py"',
             '    --md "%s"' % main_path,
             '    --deck "%s"' % deck,
             '    --lowercase-tags']
    if len(groups) > 1:
        parts.append('    --groups "%s"' % spec)
    print("\n出包命令（需要 genanki 的解释器，整段复制）：")
    for i, p in enumerate(parts):
        print(p + (" \\" if i < len(parts) - 1 else ""))


if __name__ == "__main__":
    main()
