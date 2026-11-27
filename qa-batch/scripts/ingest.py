#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1 输入归一化：展开清单、判定类型、去重、分配来源编号 S1..Sn。

用法：
    python ingest.py --out out/20261127-sr --topic "SR-MPLS" 笔记.docx 字幕.txt
    python ingest.py --out out/20261127-sr --from-file sources.txt

输入可以是：文件、目录（递归）、网址。以 # 开头的行会被忽略。

产物：<out>/_manifest.json
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA = "qa-batch/manifest/v1"

EXT_KIND = {
    ".pdf": "pdf", ".docx": "docx", ".doc": "doc", ".rtf": "doc",
    ".pptx": "pptx", ".ppt": "ppt",
    ".xlsx": "xlsx", ".xlsm": "xlsx", ".xls": "xls", ".csv": "csv",
    ".txt": "txt", ".text": "txt", ".md": "md", ".markdown": "md",
    ".html": "html", ".htm": "html", ".mhtml": "html",
    ".mp4": "video", ".mkv": "video", ".mov": "video", ".avi": "video",
    ".flv": "video", ".wmv": "video", ".webm": "video", ".ts": "video",
    ".mp3": "audio", ".m4a": "audio", ".wav": "audio", ".aac": "audio",
    ".flac": "audio", ".ogg": "audio", ".amr": "audio",
    ".srt": "subtitle", ".vtt": "subtitle", ".ass": "subtitle", ".ssa": "subtitle",
    ".epub": "epub", ".xmind": "xmind", ".apkg": "apkg", ".json": "json",
}

TRACK_KEYS = {
    "spm_id_from", "vd_source", "from_source", "share_source", "share_medium",
    "share_plat", "share_session_id", "share_tag", "timestamp", "unique_k",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "ref_src",
}

VIDEO_HOSTS = ("bilibili.com", "youtube.com", "youtu.be", "v.qq.com",
               "ixigua.com", "douyin.com", "youku.com", "iqiyi.com")
DOC_HOSTS = ("docs.qq.com", "doc.weixin.qq.com", "feishu.cn", "larksuite.com",
             "notion.site", "notion.so", "yuque.com", "shimo.im",
             "docs.google.com", "confluence")


def is_url(s):
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", s))


def norm_url(u):
    """去掉追踪参数与锚点，host 统一小写。"""
    p = urlsplit(u.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if k.lower() not in TRACK_KEYS]
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path,
                       urlencode(q), ""))


def kind_of_url(u):
    host = (urlsplit(u).netloc or "").lower()
    if any(h in host for h in VIDEO_HOSTS):
        return "video"
    if any(h in host for h in DOC_HOSTS):
        return "onlinedoc"
    return "web"


def sniff_kind(path):
    """先看文件头再信扩展名。"""
    ext = path.suffix.lower()
    kind = EXT_KIND.get(ext, "unknown")
    try:
        with open(path, "rb") as f:
            head = f.read(8)
    except OSError:
        return kind
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        # zip 容器：靠扩展名区分 docx/pptx/xlsx/epub/xmind...
        if kind in ("docx", "pptx", "xlsx", "epub", "xmind", "apkg"):
            return kind
        return "zip"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return {"doc": "doc", "xls": "xls", "ppt": "ppt"}.get(kind, "ole")
    if ext in (".srt", ".vtt", ".ass", ".ssa"):
        return "subtitle"
    return kind


def fingerprint(path, chunk=1 << 20):
    h = hashlib.sha256()
    size = path.stat().st_size
    with open(path, "rb") as f:
        h.update(f.read(chunk))
    return "%s:%d" % (h.hexdigest()[:16], size)


def collect(inputs, from_file):
    items = []
    if from_file:
        fp = Path(from_file)
        if not fp.exists():
            sys.exit("[错误] 清单文件不存在：%s" % from_file)
        for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            items.append(s)
    items.extend(inputs)

    expanded = []
    for s in items:
        if is_url(s):
            expanded.append(s)
        else:
            p = Path(s).expanduser()
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file() and not f.name.startswith("."):
                        expanded.append(str(f))
            elif p.is_file():
                expanded.append(str(p))
            else:
                expanded.append(s)  # 留给后续标 unreachable
    return expanded


def main():
    ap = argparse.ArgumentParser(description="输入归一化：清单展开 / 类型判定 / 去重 / 编号")
    ap.add_argument("inputs", nargs="*", help="文件、目录或网址")
    ap.add_argument("--from-file", help="清单文件，每行一个文件路径或网址")
    ap.add_argument("--out", required=True, help="工作目录，如 out/20261127-sr")
    ap.add_argument("--topic", default="", help="主题名，用于 batch_id 与标题")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    entries = collect(args.inputs, args.from_file)
    if not entries:
        sys.exit("[错误] 没有输入。用法：ingest.py --out DIR 文件或网址...")

    seen = {}
    sources = []
    for raw in entries:
        if is_url(raw):
            key = norm_url(raw)
            kind = kind_of_url(raw)
            fp = None
        else:
            p = Path(raw)
            if not p.exists():
                sources.append({"input": raw, "kind": "unknown", "status": "failed",
                                "reason": "unreachable", "note": "路径不存在"})
                continue
            key = fp = fingerprint(p)
            kind = sniff_kind(p)
        if key in seen:
            sources[seen[key]]["duplicates"].append(raw)
            continue
        seen[key] = len(sources)
        sources.append({"input": raw, "kind": kind, "status": "pending",
                        "reason": "", "note": "", "duplicates": []})

    for i, s in enumerate(sources, 1):
        s["id"] = "S%d" % i
        s.setdefault("duplicates", [])
        s.setdefault("text", "")
        s.setdefault("chars", 0)
        s.setdefault("cards", 0)

    batch = out.name
    manifest = {
        "schema": SCHEMA,
        "batch_id": batch,
        "topic": args.topic,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(sources),
        "sources": sources,
    }
    (out / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("%-4s %-10s %-6s %s" % ("编号", "类型", "状态", "输入"))
    for s in sources:
        print("%-4s %-10s %-6s %s" % (s["id"], s["kind"], s["status"], s["input"][:78]))
    dup = sum(len(s["duplicates"]) for s in sources)
    print("\n合计 %d 个来源" % len(sources) + ("，去重 %d 个" % dup if dup else ""))
    print("清单：%s" % (out / "_manifest.json"))
    print("下一步：python normalize.py --out \"%s\"" % out)


if __name__ == "__main__":
    main()
