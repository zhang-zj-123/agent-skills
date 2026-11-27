# Agent Skills

一组面向「把材料变成可复习知识」的 Agent Skill，配套可直接调用的命令行脚本。

两个 skill 上下游衔接，也可以各自独立使用：

| Skill | 一句话 | 输入 | 输出 |
|---|---|---|---|
| [anki-cards](./anki-cards/) | 把内容拆成 Anki 问答卡并打包 | 文档 / 字幕 / 笔记 / 网页 | `卡片稿.md` + `.apkg` |
| [qa-batch](./qa-batch/) | 把一批材料整理成问答式复习资料 | 多来源文件 / 链接 / 音视频 | `复习资料_主题.md` |

```
多来源材料 → [qa-batch] → 复习资料_主题.md → [anki-cards] → .apkg → Anki
```

---

## anki-cards

把一份材料变成能长期复习的 Anki 牌组：先出 Markdown 卡片稿人工核对，确认后打包成 `.apkg`。

- 依赖：**仅 genanki**
- 内置 GitHub 风明暗双主题
- 重跑更新原卡，不产生重复
- 详见 [anki-cards/README.md](./anki-cards/README.md)

## qa-batch

把一批材料整理成结构固定、去重、原子化的问答清单。

- 依赖：**无必需第三方库**（PDF 需 pdfplumber，xlsx 需 openpyxl）
- 五段流水线，每段可单独重跑
- 11 条质量门禁，不通过不产出
- 详见 [qa-batch/README.md](./qa-batch/README.md)

---

## 安装

```bash
git clone <this-repo>
```

把需要的 skill 目录放进 Agent 的 skill 路径：

```bash
# 用户级：所有项目可用
~/.workbuddy/skills/
# 项目级
<项目>/.workbuddy/skills/
```

也可以只用脚本，不装 skill：两个项目里的 `scripts/` 都是独立命令行工具。

## 环境

| 项 | 要求 |
|---|---|
| Python | 3.8+ |
| anki-cards | `pip install genanki` |
| qa-batch | 无（PDF：`pdfplumber`，xlsx：`openpyxl`） |
| Anki | 2.1.x+（仅用于导入 apkg） |

## 共同约定

两个项目的卡片格式**字段级一致**，中间无需转换：

```markdown
### 001
- **正面**：问题？
- **背面**：答案，关键词用 **两个星号**。
- **标签**：主题::分组
```

编号必须纯数字且连续，每条字段写在一行内，标签用 `::` 表达层级。

## 环境说明

仓库里的 `SKILL.md` 面向 Agent 描述工作流。其中出现的 Python 解释器路径（如 `C:\Users\...\python.exe`）是作者本机环境，换机器后改成你自己的 `python` 即可，脚本本身不含硬编码路径。

## License

未指定。如需开源发布，请自行添加 LICENSE 文件。
