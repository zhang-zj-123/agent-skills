# 来源与格式矩阵

## 一、脚本自己能处理的（`normalize.py` 直接抽）

| 格式 | 判定 | 抽取方式 | 注意 |
|---|---|---|---|
| `.txt` `.md` `.json` | 扩展名 | 编码自动探测 utf-8 / gb18030 / big5 | 乱码会自动回退 |
| `.srt` `.vtt` `.ass` | 扩展名 | 去序号与时间轴，保留台词 | **比 ASR 转写准，优先用字幕** |
| `.html` `.htm` `.mhtml` | 扩展名 | 去 script/style，标签转换行 | 正文占比低时会误收导航 |
| `.docx` | ZIP + `word/document.xml` | 读段落，识别 Heading 样式转 `#` | 不需要 python-docx |
| `.pptx` | ZIP + `ppt/slides/*.xml` | 按页码取文本框，每页一个 `##` | 图表里的数字取不到 |
| `.xlsx` `.xlsm` | openpyxl | 每个 sheet 一段，行转 `a \| b \| c` | 超过 3000 行截断 |
| `.csv` | 标准库 | 同上 | 编码自动探测 |
| `.pdf` | `%PDF` 文件头 | pdfplumber 逐页取文本 | **需用 `C:\Python310\python.exe` 跑** |
| `.epub` | ZIP | 按章节 XHTML 取文本 | — |

## 二、要靠宿主能力补齐的（脚本标 `needs_*`）

跑完 `normalize.py` 会列出这些来源，补齐方式统一是：**把正文写进 `work/text/<SID>.md`，再重跑 `normalize.py`**（幂等，不会覆盖已修正的内容）。

| 状态 | 类型 | 补齐方式 |
|---|---|---|
| `needs_transcribe` | mp4 / mkv / mov / mp3 / m4a | 用 `AudioTranscribe` 转写 → 写入文本文件 |
| `needs_fetch` | 网页 / 在线文档链接 | 用 `WebFetch` 抓正文；在线文档走对应 connector |
| `needs_convert` | `.doc` `.xls` `.ppt` | 用 Office/WPS 另存为新格式再重跑 |
| `needs_pdf_lib` | PDF 但缺 pdfplumber | 换 `C:\Python310\python.exe` 执行 |
| `needs_ocr` | 扫描件 PDF（每页 <20 字） | OCR 后写入文本文件 |
| `needs_export` | `.apkg` / `.xmind` | 解包导成 md 后重跑 |
| `unsupported` | 图片 / 未知容器 | 转成 txt 或 pdf |

## 三、异常判定与处置

| 场景 | 判定信号 | 动作 | 报告里的状态 |
|---|---|---|---|
| 路径不存在 | `Path.exists()` 为假 | 跳过，不中断整批 | `failed / unreachable` |
| 网址 403/401/付费墙 | HTTP 状态码 | 不重试 | `needs_fetch`（附原因） |
| 需登录/验证码 | 正文含登录字样 | 提示手动导出 PDF | `needs_auth` |
| JS 渲染空白 | 正文 <300 字但 HTML 很大 | 抓 meta 兜底，仍空则跳过 | `needs_browser` |
| 404 / 已删除 | 状态码 4xx | 跳过 | `unreachable` |
| 扫描件 PDF | 每页文本 <20 字 | 不做 OCR，标出来 | `insufficient` |
| 加密文档 | 解析抛 `encrypted` | 跳过 | `encrypted` |
| 编码乱码 | UTF-8 解码失败 | 回退 GB18030 → Big5 | 自动处理，不报错 |
| 内容过短 | 去空白后 <300 字 | 不进入写卡阶段 | `insufficient` |
| 多来源同文 | 文件指纹相同 | 只留首个，其余记进 `duplicates` | 自动去重 |
| 文件过大 | >200MB 或 >300 页 | 截断处理 | `truncated` |
| 旧版 Office | OLE 文件头 `\xd0\xcf\x11\xe0` | 要求另存 | `needs_convert` |

## 四、建议但尚未实现的来源

按价值排序，前三个值得优先补：

1. **已有 `.apkg` 牌组** — 解 zip 读 `notes` 表，做增量：只补旧牌组里没有的知识点（需 `zstandard`，托管 venv 已装）
2. **`.xmind` 脑图** — 解 zip 读 `content.json`，层级关系直接变问答
3. **Excel 题库** — 表头含"题目/答案/解析"时直接映射为卡，**不经模型，零幻觉**
4. 播客 RSS、教材截图 OCR、网页合集（RSS/sitemap/书签导出）、代码仓库 README、腾讯文档/飞书/Notion、聊天记录导出、arXiv 论文、m3u8 公开课
