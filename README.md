# Agent Skills

一组面向「把材料变成可复习知识」的 Agent Skill，配套可直接调用的命令行脚本。

## 适合谁用

- **备考 / 考证**：手里是一摞 PDF、PPT 课件、教材，需要反复记忆而不是反复翻页。
- **面试冲刺**：想按「大局题 + 细节题」两层过一遍，能口述、能接追问。
- **看视频和长文学习**：内容看完了，但没留下任何可复习的东西。
- **知识整理**：已有笔记、字幕、聊天记录，想沉淀成能抽卡的题库。
- **Agent 用户**：希望把「整理材料 → 出卡片」这条链固定下来，每次不必重新交代一遍。

## 能帮你做什么

| 核心场景 | 你现在的具体问题 | 用哪个 skill |
| --- | --- | --- |
| 一堆材料 → 一份复习资料 | 材料散在 PDF / Word / PPT / 网页 / 视频里，逐份摘录太慢；同一知识点被讲三遍，手工合并不全 | qa-batch |
| 复习资料 → Anki 牌组 | 手工做卡慢、粒度不统一、越做越重复；做完还得一张张导入 | anki-cards |
| 长视频、无字幕素材 | 没有字幕或字幕不准，只能边看边记 | qa-batch + 语音转写 |
| 面试前突击 | 细节记不住，也讲不出「SR 是什么」这类一段话的答案 | anki-cards（问答卡） |
| 复习排期 | 资料做完了却没有节奏，看完就忘 | anki-cards → Anki 间隔重复 |

一句话：**把「看过」变成「记得」**——材料进，能抽的卡出。

> 边界：只整理材料里已有的内容，不替你补材料之外的知识。需要外部补充时，会先说明再补。

## 包含的 skill

两个 skill 上下游衔接，也可以各自独立使用：

| Skill                                    | 一句话               | 输入                | 输出                 |
| ---------------------------------------- | ----------------- | ----------------- | ------------------ |
| [anki-cards](./anki-cards/anki-cards.md) | 把内容拆成 Anki 问答卡并打包 | 文档 / 字幕 / 笔记 / 网页 | `卡片稿.md` + `.apkg` |
| [qa-batch](./qa-batch/qa-batch.md)       | 把一批材料整理成问答式复习资料   | 多来源文件 / 链接 / 音视频  | `复习资料_主题.md`       |

```
多来源材料 → [qa-batch] → 复习资料_主题.md → [anki-cards] → .apkg → Anki
```

## 文档导航

| 文件                         | 内容                                     |
| -------------------------- | -------------------------------------- |
| `about.md`                 | 仓库简介：用途、适用对象、场景、关键词（便于搜索与引用）           |
| `README.md`                | 本文件：仓库总览、下载与安装、共同约定                    |
| `anki-cards/anki-cards.md` | anki-cards 完整说明：环境依赖、卡片格式、命令参数、适用场景与限制 |
| `qa-batch/qa-batch.md`     | qa-batch 完整说明：环境依赖、五段流程、来源支持清单、质量门禁    |
| `anki-cards/SKILL.md`      | anki-cards 的 Agent 工作流定义（给模型读，人可跳过）    |
| `qa-batch/SKILL.md`        | qa-batch 的 Agent 工作流定义（给模型读，人可跳过）      |

---

## anki-cards

把一份材料变成能长期复习的 Anki 牌组：先出 Markdown 卡片稿人工核对，确认后打包成 `.apkg`。

- 依赖：**仅 genanki**
- 内置 GitHub 风明暗双主题
- 重跑更新原卡，不产生重复
- 详见 [anki-cards/anki-cards.md](./anki-cards/anki-cards.md)

## qa-batch

把一批材料整理成结构固定、去重、原子化的问答清单。

- 依赖：**无必需第三方库**（PDF 需 pdfplumber，xlsx 需 openpyxl）
- 五段流水线，每段可单独重跑
- 多道质量门禁（结构 / 标签 / 内容 / 去重），不通过不产出
- 详见 [qa-batch/qa-batch.md](./qa-batch/qa-batch.md)

---

## 下载地址

| 工具            | 用途               | 地址                                                 |
| ------------- | ---------------- | -------------------------------------------------- |
| **WorkBuddy** | 运行本仓库的 skill     | <https://www.workbuddy.cn/>（首页「立即下载」）              |
| WorkBuddy 文档  | 上手与功能说明          | <https://www.workbuddy.cn/docs/workbuddy/Overview> |
| **Anki**      | 导入并复习 `.apkg` 牌组 | <https://apps.ankiweb.net/>                        |

> **WorkBuddy 推荐码：`ixu9ww36f9tv2p`**
>
> 邀请链接：<https://www.workbuddy.cn/events/invite?inviteCode=ixu9ww36f9tv2p>
>
> 通过链接或填写推荐码注册，新用户可获得额外额度，也支持本仓库持续更新。

## 安装

### 方式一：通过 WorkBuddy 安装（推荐）

1. 安装并打开 [WorkBuddy](https://www.workbuddy.cn/)。
2. 把仓库地址发给它，说一句：

   > 把 <https://github.com/zhang-zj-123/agent-skills> 里的 anki-cards 和 qa-batch 安装到我的技能目录

3. WorkBuddy 会把两个目录写入技能路径，**新开一个会话**后生效（技能索引在会话启动时建立）。
4. 直接说触发词即可调用：`做成 anki卡片`、`批量问答`、`整理复习资料`。

### 方式二：从网页下载

1. 打开仓库：<https://github.com/zhang-zj-123/agent-skills>
2. 点右上角 **Code → Download ZIP**。
3. 解压后，把需要的目录整个复制到技能路径：

   | 系统            | 技能路径                                |
   | ------------- | ----------------------------------- |
   | Windows       | `C:\Users\<用户名>\.workbuddy\skills\` |
   | macOS / Linux | `~/.workbuddy/skills/`              |

4. `SKILL.md` 必须位于目录第一层，结构如下：

```
~/.workbuddy/skills/
├── anki-cards/
│   ├── SKILL.md
│   └── scripts/
└── qa-batch/
    ├── SKILL.md
    └── scripts/
```

5. 新开会话，说触发词即可。只想要其中一个 skill 时，只复制对应目录。

技能分两级：用户级 `~/.workbuddy/skills/`（所有项目可用）、项目级 `<项目>/.workbuddy/skills/`（仅该项目）。

### 方式三：只用脚本

不装 skill 也能用，两个项目里的 `scripts/` 都是独立命令行工具，`--help` 查看参数：

```bash
python anki-cards/scripts/build_apkg.py --help
python qa-batch/scripts/ingest.py --help
```

## 环境

| 项                                 | 要求                                  |
| --------------------------------- | ----------------------------------- |
| Python                            | 3.8+                                |
| anki-cards                        | `pip install genanki`               |
| qa-batch                          | 无（PDF：`pdfplumber`，xlsx：`openpyxl`） |
| [Anki](https://apps.ankiweb.net/) | 2.1.x+（仅用于导入 apkg）                  |

## 共同约定

两个项目的卡片格式**字段级一致**，中间无需转换：

```markdown
### 001
- **正面**：问题？
- **背面**：答案，关键词用 **两个星号**。
- **标签**：主题::分组
```

编号必须纯数字且连续，每条字段写在一行内，标签用 `::` 表达层级。

## 关于 SKILL.md 中的路径

仓库里的 `SKILL.md` 面向 Agent 描述工作流。其中出现的 Python 解释器路径（如 `C:\Users\...\python.exe`）是作者本机环境，换机器后改成你自己的 `python` 即可，脚本本身不含硬编码路径。

## 联系

- 邮箱（QQ）：<2548218881@qq.com>
- 仓库：<https://github.com/zhang-zj-123/agent-skills>
- 问题与建议：欢迎提 Issue

## License

未指定。如需开源发布，请自行添加 LICENSE 文件。
