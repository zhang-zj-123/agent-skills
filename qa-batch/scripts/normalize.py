#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S3 清洗：把各来源抽成纯文本 <out>/work/text/<SID>.md，并回写 manifest 状态。

设计要点：
  - 幂等：work/text/<SID>.md 已存在就直接采信（人工修正、ASR 转写、手工粘贴都走这条路）
  - 只做确定性抽取，不调用模型
  - 音视频/网页/在线文档不在此处理，标记 needs_transcribe / needs_fetch，由会话侧补齐后重跑本脚本

用法：
    python normalize.py --out out/20261127-sr
    python normalize.py --out out/20261127-sr --min-chars 300
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

MIN_CHARS_DEFAULT = 300
XLSX_MAX_ROWS = 3000


# ---------- 编码 ----------

def read_text_auto(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


# ---------- 各格式抽取 ----------

def from_txt(path):
    text, enc = read_text_auto(path)
    return text


def from_subtitle(path):
    text, _ = read_text_auto(path)
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if s.isdigit():
            continue
        if re.match(r"^\d{1,2}:\d{2}(:\d{2})?[,.]\d{1,3}\s*-->", s):
            continue
        if s.upper().startswith(("WEBVTT", "NOTE")) or re.match(r"^(Dialogue|Format|Style):", s):
            continue
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"\{\\[^}]*\}", "", s)
        if s:
            lines.append(s)
    return "\n".join(lines)


def from_html(path):
    text, _ = read_text_auto(path)
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    import html as _html
    text = _html.unescape(text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def from_docx(path):
    """直接读 OOXML，不依赖 python-docx。"""
    out = []
    with zipfile.ZipFile(path) as z:
        try:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        except KeyError:
            return ""
    # 段落与标题
    for pm in re.finditer(r"(?s)<w:p[ >].*?</w:p>", xml):
        block = pm.group(0)
        style = re.search(r'<w:pStyle[^>]*w:val="([^"]+)"', block)
        texts = re.findall(r"(?s)<w:t[^>]*>(.*?)</w:t>", block)
        line = "".join(texts)
        line = re.sub(r"<[^>]+>", "", line)
        line = (line.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"'))
        if not line.strip():
            out.append("")
            continue
        sname = (style.group(1) if style else "").lower()
        m = re.match(r"heading\s*(\d)", sname)
        if m:
            lvl = min(int(m.group(1)), 6)
            out.append("\n%s %s\n" % ("#" * lvl, line.strip()))
        elif sname in ("title", "subtitle"):
            out.append("\n# %s\n" % line.strip())
        else:
            out.append(line.strip())
    return "\n".join(out)


def from_pptx(path):
    """按页码顺序取每页文本框。"""
    with zipfile.ZipFile(path) as z:
        slides = [n for n in z.namelist()
                  if re.match(r"ppt/slides/slide\d+\.xml$", n)]

        def idx(n):
            return int(re.search(r"slide(\d+)\.xml$", n).group(1))

        out = []
        for n in sorted(slides, key=idx):
            xml = z.read(n).decode("utf-8", errors="replace")
            texts = []
            for pm in re.finditer(r"(?s)<a:p>.*?</a:p>", xml):
                t = "".join(re.findall(r"(?s)<a:t>(.*?)</a:t>", pm.group(0)))
                t = re.sub(r"<[^>]+>", "", t).strip()
                if t:
                    texts.append(t)
            if texts:
                out.append("\n## 第 %d 页\n" % idx(n))
                out.extend(texts)
    return "\n".join(out)


def from_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= XLSX_MAX_ROWS:
                rows.append("…（超过 %d 行已截断）" % XLSX_MAX_ROWS)
                break
            cells = ["" if c is None else str(c).strip() for c in row]
            if not any(cells):
                continue
            rows.append(" | ".join(cells).rstrip(" |"))
        if rows:
            out.append("\n## 工作表：%s\n" % ws.title)
            out.extend(rows)
    wb.close()
    return "\n".join(out)


def from_csv(path):
    text, _ = read_text_auto(path)
    out = []
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if any(cells):
            out.append(" | ".join(cells))
    return "\n".join(out)


def from_pdf(path):
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("needs_pdf_lib")
    out = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            t = page.extract_text() or ""
            if t.strip():
                out.append("\n## 第 %d 页\n" % i)
                out.append(t)
    return "\n".join(out)


def from_epub(path):
    with zipfile.ZipFile(path) as z:
        items = [n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
        out = []
        for n in sorted(items):
            raw = z.read(n).decode("utf-8", errors="replace")
            raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
            raw = re.sub(r"(?i)</(p|div|h[1-6]|li)>", "\n", raw)
            raw = re.sub(r"<[^>]+>", " ", raw)
            import html as _html
            raw = _html.unescape(raw)
            raw = re.sub(r"[ \t]+", " ", raw).strip()
            if raw:
                out.append(raw)
    return "\n\n".join(out)


PARSERS = {
    "txt": from_txt, "md": from_txt, "json": from_txt,
    "subtitle": from_subtitle, "html": from_html,
    "docx": from_docx, "pptx": from_pptx,
    "xlsx": from_xlsx, "csv": from_csv,
    "pdf": from_pdf, "epub": from_epub,
}

# 这些类型脚本不处理，需要会话侧用宿主能力补齐
EXTERNAL = {
    "video": ("needs_transcribe", "视频：需用 AudioTranscribe 转写，写入 work/text/<SID>.md 后重跑"),
    "audio": ("needs_transcribe", "音频：需用 AudioTranscribe 转写，写入 work/text/<SID>.md 后重跑"),
    "web": ("needs_fetch", "网页：需用 WebFetch 抓正文，写入 work/text/<SID>.md 后重跑"),
    "onlinedoc": ("needs_fetch", "在线文档：需用对应 connector 或 WebFetch 取正文"),
    "apkg": ("needs_export", "Anki 牌组：需解包读 notes 表导出为 md"),
    "xmind": ("needs_export", "脑图：需解包读 content.json 导出为 md"),
    "doc": ("needs_convert", "旧版 .doc：请另存为 .docx 后重跑"),
    "xls": ("needs_convert", "旧版 .xls：请另存为 .xlsx 后重跑"),
    "ppt": ("needs_convert", "旧版 .ppt：请另存为 .pptx 后重跑"),
    "ole": ("needs_convert", "旧版 OLE 文档：请另存为新格式后重跑"),
    "zip": ("needs_convert", "压缩容器：请解压后按具体格式重跑"),
    "unknown": ("unsupported", "无法识别格式，请转成 txt/md/pdf 后重跑"),
}


def count_chars(text):
    return len(re.sub(r"\s", "", text or ""))


def main():
    ap = argparse.ArgumentParser(description="抽取纯文本并回写来源状态")
    ap.add_argument("--out", required=True, help="工作目录")
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS_DEFAULT,
                    help="少于该字数判 insufficient（默认 300）")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    mf_path = out / "_manifest.json"
    if not mf_path.exists():
        sys.exit("[错误] 找不到 %s，请先运行 ingest.py" % mf_path)
    manifest = json.loads(mf_path.read_text(encoding="utf-8"))

    textdir = out / "work" / "text"
    textdir.mkdir(parents=True, exist_ok=True)

    for s in manifest["sources"]:
        sid, kind = s["id"], s["kind"]
        dst = textdir / ("%s.md" % sid)
        s["text"] = str(dst.relative_to(out))

        if dst.exists():                       # 幂等：已存在即采信
            n = count_chars(dst.read_text(encoding="utf-8", errors="replace"))
            s["chars"] = n
            s["status"] = "ok" if n >= args.min_chars else "insufficient"
            s["reason"] = "" if n >= args.min_chars else "内容过短（%d 字）" % n
            continue

        if kind in EXTERNAL:
            status, reason = EXTERNAL[kind]
            s["status"], s["reason"] = status, reason
            continue

        parser = PARSERS.get(kind)
        if not parser:
            s["status"], s["reason"] = "unsupported", "无对应解析器：%s" % kind
            continue

        try:
            text = parser(Path(s["input"]))
        except RuntimeError as e:
            if str(e) == "needs_pdf_lib":
                s["status"] = "needs_pdf_lib"
                s["reason"] = "缺 pdfplumber：用 C:\\Python310\\python.exe 运行本脚本"
            else:
                s["status"], s["reason"] = "failed", str(e)
            continue
        except Exception as e:
            s["status"] = "failed"
            s["reason"] = "%s: %s" % (type(e).__name__, str(e)[:120])
            continue

        text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
        n = count_chars(text)
        s["chars"] = n
        if n < args.min_chars:
            s["status"] = "insufficient"
            s["reason"] = "内容过短（%d 字，阈值 %d）" % (n, args.min_chars)
            dst.write_text("# %s\n\n%s\n" % (Path(s["input"]).name, text), encoding="utf-8")
        else:
            s["status"], s["reason"] = "ok", ""
            dst.write_text(text, encoding="utf-8")

    mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("%-4s %-12s %-8s %s" % ("编号", "类型", "状态", "字数/原因"))
    for s in manifest["sources"]:
        extra = str(s["chars"]) if s["status"] in ("ok", "insufficient") else s["reason"]
        print("%-4s %-12s %-8s %s" % (s["id"], s["kind"], s["status"], str(extra)[:70]))

    ok = [s for s in manifest["sources"] if s["status"] == "ok"]
    print("\n可生成卡片的来源：%d / %d" % (len(ok), len(manifest["sources"])))
    need = [s for s in manifest["sources"] if s["status"].startswith("needs_")]
    if need:
        print("需你补齐的：%s" % ", ".join("%s(%s)" % (s["id"], s["status"]) for s in need))
        print("补齐方式：把正文写入 work/text/<SID>.md，再重跑本脚本即可。")
    print("下一步：python outline.py --out \"%s\"" % out)


if __name__ == "__main__":
    main()
