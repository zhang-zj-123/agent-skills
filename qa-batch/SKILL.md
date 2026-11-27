---
name: qa-batch
description: 把一批学习材料（网页/视频链接、在线文档、本地视频音频、PDF/Word/TXT/Excel/PPT）批量整理成结构固定的问答式复习资料 md，按重点/考点/易混点分类，可直接交给 anki-cards 出牌组包。当用户提到"批量问答"、"整理复习资料"、"生成考点"、"考点整理"、"做成题库"、"面试复习材料"、"把这批资料变成问答"时使用。
agent_created: true
---

# 批量问答式复习资料生成

把多个来源的材料变成一份**结构固定、去重、原子化**的问答清单。回答的是"材料里有什么值得考"，不负责出卡包（那是 `anki-cards` 的事）。

## 环境

| 用途 | 解释器 |
|---|---|
| 本 skill 全部脚本 | `C:\Python310\python.exe`（有 openpyxl + pdfplumber） |
| 出 apkg（第 7 步） | `C:\Users\ZQ\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（有 genanki） |

两个解释器不要混：托管 venv 没有 pdf/docx 库，Python310 没有 genanki。

## 工作流

### 1. 收清单（只问必要的）

一次问清，最多两个问题：

- 材料在哪：链接、目录、还是具体文件
- 主题名：用于命名 batch 与标题

规模不用问——先跑完抽取，看字数再定分块粒度。**不要一次把整份材料读进上下文**，按第 4 步的章节文件逐节处理。

### 2. 输入归一化

```bash
"C:\Python310\python.exe" scripts/ingest.py --out out/<batch_id> --topic "<主题>" <文件或目录或链接>...
```

批量清单也可以写成文件（每行一个，`#` 注释），用 `--from-file sources.txt`。

产物 `out/<batch_id>/_manifest.json`：来源编号 S1..Sn、类型、状态。重复文件会自动合并（记在 `duplicates`）。

### 3. 抽取正文

```bash
"C:\Python310\python.exe" scripts/normalize.py --out out/<batch_id>
```

脚本能直接处理 txt/md/srt/html/docx/pptx/xlsx/csv/pdf/epub。**处理不了的会标 `needs_*` 并列出来**，按 `references/source-matrix.md` 补齐：

- `needs_transcribe` → 用 `AudioTranscribe` 转写，把文本写进 `work/text/<SID>.md`
- `needs_fetch` → 用 `WebFetch` 抓正文，同样写进 `work/text/<SID>.md`
- `needs_convert` → 让用户另存为新格式

补齐后**重跑同一条命令**即可（幂等，已存在且字数够的文本文件直接采信，不覆盖）。
正文 <300 字的来源判 `insufficient`，不进入写卡。

### 4. 切分

```bash
"C:\Python310\python.exe" scripts/outline.py --out out/<batch_id>
```

有标题按标题切，无标题按 1800 字滑窗 + 200 字重叠。产物 `work/sections/<SID>-<NN>.md`，每节一个文件。

### 5. 逐节写卡

**一节一节读，一节一节写。**读完 `work/sections/S1-01.md` 就写 `work/cards/S1.md` 的对应部分，不要攒到最后。

写之前读 `references/card-spec.md`。硬要求：

```markdown
## 概念与背景

### 001
- **正面**：问题？
- **背面**：答案，关键词用 **两个星号**。
- **标签**：sr::概念
- **补充**：可选
```

- 每文件从 `### 001` 起连续编号（跨来源重复没关系，第 6 步会全局重排）
- **每条内容写在一行内**，换行会被静默丢内容
- 三类都要有：重点 50–60%、考点 20–30%、**易混 ≥10%**
- 标签 `主题::分组`，全小写，不含空格

一个来源的卡写完，就写下一个来源。全部写完进入校验。

### 6. 质量门禁

```bash
"C:\Python310\python.exe" scripts/qa_check.py --out out/<batch_id>
```

不通过会列错误并退出码 1。常见错误与改法：

| 错误 | 改法 |
|---|---|
| 答案超过 160 字 | 拆成两张，或压成 ①②③ |
| 编号不连续 | 补号或删号，别留空 |
| 重复 | 删掉后出现的同义卡 |
| 含依赖词 | 把"如上所述"换成自足的表述 |
| 空卡（"是/不是/有多种"） | 补具体内容，或直接删 |

默认只报前 30 条错误，改完重跑。

### 7. 拼装与出包

```bash
"C:\Python310\python.exe" scripts/assemble.py --out out/<batch_id> --deck "All::1 - <分类>:1 - <主题>" \
    --order "概念,原理,对比,建路,业务"
```

`--order` 指定分组顺序，逗号分隔，未列出的按出现顺序附在末尾。**这一步不要省**：来源编号是按文件名排序分配的（`BGP-LS补充.txt` 会排在 `SR笔记.txt` 前面），不加 `--order` 会把 BGP-LS 这类控制面内容顶到第 1 章。

产物：

- `复习资料_<主题>.md` — 主交付物，全局重排编号，跨来源去重
- `_quality_report.md` — 来源状态、分组张数、失败原因
- 终端会打印现成的 `build_apkg.py` 命令（含 `--groups`），整段复制即可

出包时**先判断要不要分包**：分组超过 5 组就别加 `--groups`，出一个整包。12 组会生成 12 个 apkg，导入后复习调度全打散，不如单包。只有"基础/冲刺"这种 2–3 段的大切分才值得分包。

需要出卡包时，用托管 venv 跑那条命令即可。

### 8. 交付

先给 md 让用户看内容，**不要直接出 apkg**。说明：

- 总张数与分组分布（表格）
- 哪些来源失败/内容不足，原因是什么
- 哪几张可能不准（ASR 转写、扫图、公式多的材料）
- 是否要压缩张数或补某一类

用户确认后再出包。

## 卡片格式契约

本 skill 的产物与 `anki-cards` 的 `build_apkg.py` **字段级一致**（正面/背面/标签/补充），不转换格式直接能用。两条硬约束来自那个脚本：

1. 卡号必须是**纯数字**（`^###\s*(\d+)\s*$`），不能写成 `### S1-01`
2. 编号必须**从最小值到最大值连续**，不能有空洞 —— `assemble.py` 会全局重排保证这点

## 常见坑

1. **一次读全文**：100 页 PDF 直接塞进来，后半段质量断崖。按 `work/sections/` 逐节处理。
2. **忘了重跑 normalize**：手工补齐 `work/text/<SID>.md` 后不重跑，manifest 里状态还是 `needs_fetch`，`outline.py` 会跳过该来源。
3. **标签带空格**：`sr::概念 重点` 会被 Anki 拆成两个标签，层级就丢了。多标签用两个 `::` 层级，不要空格。
4. **答案里换行**：解析器每字段只取一行，换行后面的内容直接消失。用 ①②③ 连接。
5. **改了 deck 名**：已导入 Anki 的卡会变成新卡，因为 guid = 牌组名 + 卡号。定好名字再出包。
6. **`.doc`/`.xls`/`.ppt` 老格式**：脚本不解析，要求另存。别硬试。
7. **PDF 用错解释器**：托管 venv 没 pdfplumber，会报 `needs_pdf_lib`，换 `C:\Python310\python.exe`。
8. **滑窗重叠区被写两遍**：无标题长文的相邻块有 200 字重叠，同一知识点会出现两次。写卡前先看上一节末尾，重叠部分只写一次；`qa_check` 只能拦字面相同的重复，换个说法就漏。
9. **漏掉"藏在对比句里"的核心机制**：例如"中间节点没有网络的状态"出现在 SR-TE 与 RSVP 的对比句中，容易只写成对比卡，漏掉"SR 状态只在头节点"这张独立概念卡。读完一节回头问一遍：这里有没有一句是**别处的前提**？有就单独拆一张。


## 参考

- `references/card-spec.md` — 写卡规范：三类占比、原子化判据、五条禁令、自检清单
- `references/source-matrix.md` — 格式能力表、补齐方式、异常判定与处置
