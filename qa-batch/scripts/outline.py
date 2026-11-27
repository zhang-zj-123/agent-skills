#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4 结构切分：把 work/text/<SID>.md 按标题切成小节，供模型逐节写卡。

产物：
  work/sections/<SID>-<NN>.md   每节一个文件（模型逐个读，避免一次塞全文）
  work/outline.json             章节树：标题、字数、文件

用法：python outline.py --out out/20261127-sr [--max-chars 1800] [--overlap 200]
"""
import argparse
import json
import re
import sys
from pathlib import Path

HEAD_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# 中文文档常见的"伪标题"：一、xxx / 第 3 章 xxx / 3.2 xxx
PSEUDO_RES = (
    re.compile(r"^([一二三四五六七八九十]+)、\s*(\S.{0,38})$"),
    re.compile(r"^(第[一二三四五六七八九十百]+[章节讲部篇])\s*(.{0,38})$"),
    re.compile(r"^(\d+(?:\.\d+){1,3})\s+(\S.{0,38})$"),
)


def pseudo_marks(lines):
    marks = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or len(s) > 44 or s.endswith(("。", "，", "；", "：", "！", "？")):
            continue
        for r in PSEUDO_RES:
            if r.match(s):
                marks.append((i, 2, s))
                break
    return marks


def split_by_heading(text):
    """按标题切。返回 [(level, title, body)]，标题后到下一个同级或更高级标题之间的内容归本节。"""
    lines = text.splitlines()
    marks = [(i, len(m.group(1)), m.group(2))
             for i, line in enumerate(lines) for m in [HEAD_RE.match(line)] if m]
    if len(marks) < 3:
        marks = pseudo_marks(lines)
    if len(marks) < 3:
        return None, []

    # 取出现次数最多的层级作为分节主层级（通常是 H2）
    from collections import Counter
    lvl = Counter(m[1] for m in marks).most_common(1)[0][0]

    out = []
    for idx, (ln, level, title) in enumerate(marks):
        if level != lvl:
            continue
        end = len(lines)
        for ln2, level2, _ in marks:
            if ln2 > ln and level2 <= level:
                end = ln2
                break
        body = "\n".join(lines[ln + 1:end]).strip()
        out.append((level, title, body))
    return lvl, out


def chunk_text(text, max_chars, overlap):
    """无标题时按段落滑窗切块，尽量在空行处断；超长段落硬切。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    # 单个段落本身超过上限 -> 先硬切成上限大小的片段
    flat = []
    for p in paras:
        if len(p) <= max_chars:
            flat.append(p)
        else:
            for i in range(0, len(p), max_chars):
                flat.append(p[i:i + max_chars])
    paras = flat
    if not paras:
        return []
    chunks, buf, size = [], [], 0
    for p in paras:
        if size + len(p) > max_chars and buf:
            chunks.append("\n\n".join(buf))
            tail = []
            if overlap > 0:
                acc = 0
                for q in reversed(buf):
                    if acc + len(q) > overlap:
                        break
                    tail.insert(0, q)
                    acc += len(q)
                buf, size = tail, acc
            else:
                buf, size = [], 0
        buf.append(p)
        size += len(p)
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


def main():
    ap = argparse.ArgumentParser(description="按标题切分，输出逐节文件")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-chars", type=int, default=1800)
    ap.add_argument("--overlap", type=int, default=200)
    args = ap.parse_args()

    out = Path(args.out).resolve()
    mf_path = out / "_manifest.json"
    if not mf_path.exists():
        sys.exit("[错误] 找不到 _manifest.json，请先运行 ingest.py / normalize.py")
    manifest = json.loads(mf_path.read_text(encoding="utf-8"))

    secdir = out / "work" / "sections"
    secdir.mkdir(parents=True, exist_ok=True)
    for old in secdir.glob("*.md"):
        old.unlink()

    outline = {}
    total = 0
    for s in manifest["sources"]:
        if s["status"] != "ok":
            continue
        src = out / s.get("text", "")
        if not src.exists():
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        lvl, secs = split_by_heading(text)

        if not secs:
            chunks = chunk_text(text, args.max_chars, args.overlap)
            secs = [(0, "分块 %d" % (i + 1), c) for i, c in enumerate(chunks)]
            mode = "chunk"
        else:
            mode = "heading"

        entries = []
        for i, (level, title, body) in enumerate(secs, 1):
            if not body.strip():
                continue
            fn = secdir / ("%s-%02d.md" % (s["id"], len(entries) + 1))
            head = "> 来源 %s｜章节「%s」｜约 %d 字\n\n" % (
                s["id"], title.strip("# ").strip(), len(re.sub(r"\s", "", body)))
            fn.write_text(head + body + "\n", encoding="utf-8")
            entries.append({"idx": len(entries) + 1, "title": title.strip("# ").strip(),
                            "chars": len(re.sub(r"\s", "", body)),
                            "file": str(fn.relative_to(out))})
        outline[s["id"]] = {"mode": mode, "sections": entries,
                            "total_chars": sum(e["chars"] for e in entries)}
        total += len(entries)

    (out / "work" / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")

    for sid, v in outline.items():
        print("%s | %s | %d 节 | %d 字" % (sid, v["mode"], len(v["sections"]), v["total_chars"]))
        for e in v["sections"]:
            print("   %02d %-38s %5d 字  %s" % (e["idx"], e["title"][:38], e["chars"], e["file"]))
    print("\n共 %d 节，已写入 %s" % (total, secdir))
    print("下一步：逐节读 work/sections/*.md 写卡，输出到 work/cards/<SID>.md")


if __name__ == "__main__":
    main()
