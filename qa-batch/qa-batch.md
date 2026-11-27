# qa-batch

把一批学习材料批量整理成**结构固定、去重、原子化**的问答式复习资料。

输入可以是文档、字幕、PDF、课件、表格，输出是一份可以直接交给 [anki-cards](../anki-cards/anki-cards.md) 出牌组的 Markdown。面向学习、面试和考证复习。

---

## 设计思路

它回答的是「**这批材料里有什么值得考**」，不负责生成牌组包。

整条链路拆成五段，每段一个脚本、一个产物、可单独重跑：

```
输入清单 → ① ingest → ② normalize → ③ outline → ④ 写卡 → ⑤ qa_check → ⑥ assemble → 复习资料.md
           归一化      抽取正文      结构切分      （Agent）     质量门禁      合并去重
```

**关键设计**：取、洗、切、检、拼全部由代码完成，只有「读懂内容并写成问答」交给模型。

这样同一批材料重跑，除问答文本外每一步结果都一致——出问题能定位到具体环节，而不是"重新生成一遍看看"。

## 环境要求

| 项 | 要求 |
|---|---|
| Python | 3.8 及以上（实测 3.10） |
| 第三方库 | **无必需依赖**，全部基于标准库 |
| 可选依赖 | `pdfplumber`（处理 PDF）、`openpyxl`（处理 xlsx） |
| 操作系统 | 跨平台 |

`docx` / `pptx` / `epub` 直接读 OOXML 与 zip 容器，**不需要** python-docx、python-pptx、ebooklib。

```bash
# 只有需要处理 PDF 或 Excel 时才装
pip install pdfplumber openpyxl
```

缺库不会崩——对应来源会被标成 `needs_pdf_lib` / `needs_xlsx_lib` 列出来，其余来源照常处理。

## 安装与触发

**作为 Agent Skill 使用**：

```bash
~/.workbuddy/skills/qa-batch/          # 用户级
<项目>/.workbuddy/skills/qa-batch/     # 项目级
```

触发词：`批量问答`、`整理复习资料`、`考点整理`、`生成题库`、`面试复习材料`、`把这批资料变成问答`。

也可以点名：`/qa-batch 把 D:\notes\ 下这批材料整理成复习资料`。

**只用脚本**：直接跑下面五条命令即可，不依赖 Agent。

## 基本使用流程

### 1. 收清单

```bash
python scripts/ingest.py --out out/sr --topic "SR" 材料目录/ 文件A.pdf 文件B.docx
```

支持目录递归、混合文件与网址。清单也可以写成文件（每行一个，`#` 注释）：

```bash
python scripts/ingest.py --out out/sr --topic "SR" --from-file sources.txt
```

产物 `out/sr/_manifest.json`：来源编号 `S1..Sn`、类型、状态。重复文件自动合并，记在 `duplicates`。

### 2. 抽取正文

```bash
python scripts/normalize.py --out out/sr
```

文本写入 `work/text/S*.md`，状态回写 manifest。**这一步是幂等的**——已存在且字数达标的文本直接采信，手工补录的内容不会被覆盖。

正文少于 300 字判 `insufficient`，不进入写卡（可用 `--min-chars` 调）。

### 3. 结构切分

```bash
python scripts/outline.py --out out/sr
```

有标题按标题切；无标题时识别「一、」「第 X 章」「3.2」这类伪标题；再没有就按 1800 字滑窗（`--max-chars` / `--overlap` 可调）。

产物 `work/sections/S1-01.md`，**一节一个文件**，供逐节处理。

### 4. 逐节写卡

没有脚本——这一步由人（或 Agent）读 `work/sections/` 里的每个文件，把内容写成问答，落到 `work/cards/S1.md`。

写卡规范见 `references/card-spec.md`。格式与 `anki-cards` 完全一致：

```markdown
## 概念与背景

### 001
- **正面**：SR 的状态保存在哪里？
- **背面**：**只在头节点**。中间节点只按栈顶 SID 转发，不保存逐隧道状态。
- **标签**：sr::概念
```

### 5. 质量门禁

```bash
python scripts/qa_check.py --out out/sr
```

不通过列错误并退出码 1。检查项：

| 类别 | 检查内容 |
|---|---|
| 结构 | 编号连续无重复、正面/背面/标签齐全、`**` 成对 |
| 标签 | 含 `::` 层级、不含空格、建议全小写 |
| 内容 | 答案 ≤160 字（可调）、空卡黑名单（"是/不是/有多种"）、依赖词（"如上所述""见第 N 张"） |
| 去重 | 跨文件精确重复 + SimHash 近重复 |

另有提醒项：编号未从 1 开始、正面未以问号结尾、单个来源少于 3 张（覆盖偏薄）。

### 6. 拼装与出包

```bash
python scripts/assemble.py --out out/sr --deck "All::1 - Network::1 - SR" \
    --order "概念,原理,对比,建路,业务"
```

`--order` 指定分组顺序，未列出的按出现顺序附在末尾。

**这一步不要省。** 来源编号是按文件名排序分配的，`BGP-LS补充.txt` 会排在 `SR笔记.txt` 前面，不加 `--order` 会把控制面内容顶到第 1 章。

产物：

| 文件 | 内容 |
|---|---|
| `复习资料_<主题>.md` | 主交付物，全局重排编号、跨来源去重、按章节分组 |
| `_quality_report.md` | 来源状态、分组张数、失败原因 |
| 终端输出 | 现成的 `build_apkg.py` 命令，整段复制即可出包 |

出包时先判断要不要分包：**分组超过 5 组就别加 `--groups`**，出一个整包。十几组会生成十几个 apkg，导入后复习调度全打散。

## 支持的来源

| 格式 | 支持情况 | 说明 |
|---|---|---|
| `.txt` `.md` `.json` | ✅ 内置 | 直接读 |
| `.srt` `.vtt` `.ass` `.ssa` | ✅ 内置 | 字幕，自动去时间轴 |
| `.html` `.htm` | ✅ 内置 | 去标签取正文 |
| `.docx` | ✅ 内置 | 读 OOXML，无需 python-docx |
| `.pptx` | ✅ 内置 | 逐页取文本框 |
| `.xlsx` | ⚠️ 需 openpyxl | 逐行转文本，适合题库 |
| `.csv` | ✅ 内置 | 直接读 |
| `.pdf` | ⚠️ 需 pdfplumber | 扫描件（纯图片）抽不出字，需先 OCR |
| `.epub` | ✅ 内置 | 按章节取 XHTML |
| 网页链接 | 🔶 需补齐 | 标 `needs_fetch`，用 WebFetch 抓正文写入 `work/text/<SID>.md` 后重跑 |
| 视频 / 音频 | 🔶 需补齐 | 标 `needs_transcribe`，用语音转写后写入 `work/text/<SID>.md` 后重跑 |
| 在线文档 | 🔶 需补齐 | 标 `needs_fetch`，用对应连接器导出 |
| `.doc` `.xls` `.ppt` | 🔶 需转存 | 老格式不解析，另存为新格式后重跑 |
| `.apkg` `.xmind` | 🔶 需导出 | 标 `needs_export`，先解包导出为 md |

**边界说清楚**：脚本不联网、不调模型。网页和音视频由 Agent 侧的抓取/转写能力补齐，补齐后重跑同一条 `normalize` 即可（幂等）。

## 输出结构

```
out/sr/
├── _manifest.json              # 来源清单与状态
├── _quality_report.md          # 质量报告
├── 复习资料_SR.md              # 主交付物
├── work/
│   ├── text/S1.md              # 抽出的正文（可手工覆盖）
│   ├── sections/S1-01.md       # 切好的章节
│   └── cards/S1.md             # 写好的卡
```

所有中间产物都保留，方便定位「哪一步出了问题」——是没抓到正文，还是切分切坏了，还是写卡漏了。

## 适用场景

- 把课程讲义、教材章节、字幕批量转成考点清单
- 考前把一堆散资料压成一份可背的问答
- 面试前整理某个技术栈的概念、对比、易混点
- 已有题库（Excel/CSV）转成 Anki 牌组

## 不适用场景

- **只给一两个小文件** —— 直接用 `anki-cards` 更快，五段流水线是给批量材料准备的
- **材料本身是零散问号句**（如笔记里写"存在方向性？"）—— 机器只会照抄，不会替你补答案
- **需要外部知识补充** —— 它只整理材料里有的内容，不引入材料外的知识（如选型建议、架构设计、面试扩展题）
- **扫描版 PDF、图片型课件** —— 抽不出文字，需先 OCR

## 已知问题

1. **滑窗重叠**：无标题长文按 1800 字切块时有 200 字重叠，相邻节会重复读同一段。写卡时需人工去重，`qa_check` 只能拦字面相同的重复。
2. **切分粒度偏粗**：1500 字一块里可能混着 5–6 个主题，写卡时还要自己再切一次。改 `--max-chars` 可调小，但太小会切断上下文。
3. **跨段归纳是短板**：擅长「把一句话变成一张卡」，不擅长「把三处话合成一个结论」。实测 SR 笔记，74 个人工卡里机器覆盖 66%，漏掉的主要是跨段归纳和藏在对比句里的核心机制。

## 目录结构

```
qa-batch/
├── SKILL.md                    # Agent 使用说明（工作流、格式契约、常见坑）
├── README.md
├── references/
│   ├── card-spec.md            # 写卡规范：三类占比、原子化判据、五条禁令
│   └── source-matrix.md        # 格式能力表、补齐方式、异常判定
└── scripts/
    ├── ingest.py               # 清单归一化 / 类型判定 / 去重 / 编号
    ├── normalize.py            # 正文抽取（幂等）
    ├── outline.py              # 标题或滑窗切分
    ├── qa_check.py             # 质量门禁
    └── assemble.py             # 合并 / 去重 / 重排 / 出包命令
```

## 与 anki-cards 的关系

两个项目是上下游：

```
多来源材料 → [qa-batch] → 复习资料_主题.md → [anki-cards] → .apkg
```

卡片格式字段级一致（正面 / 背面 / 标签 / 补充），中间不需要任何转换脚本。
