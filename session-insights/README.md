# session-insights

分析 Claude Code 会话数据，生成带 Mermaid 图表的 Markdown 洞察报告。

## 功能

- 自动提取 `~/.claude/projects/` 中的 JSONL 会话数据
- 基于 CWD 自动识别当前项目，也支持关键词搜索
- 计算活跃时间 vs 空闲时间，识别效率瓶颈
- 生成 Mermaid 图表：Gantt 时间线、xychart 柱状图、pie 工具分布、sequence 交互时序、flowchart Agent 拓扑
- 四种分析模式：概览、逐个详细、并行详细、后台详细
- 并行模式使用 `claude -p` 实现 OS 级真并行，20+ 会话也能在合理时间内完成
- 输出带时间戳的独立报告，保留历史快照

## 前置要求

- Python 3（标准库，无外部依赖）
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI 已安装（并行模式需要 `claude -p` 命令）

## 安装

### 方式一：Plugin Marketplace（推荐）

在 Claude Code 中运行：

```bash
/plugin marketplace add xkcoding/xkcoding-skills
```

然后安装插件：

```bash
/plugin install productivity-skills@xkcoding-skills
```

也可以直接告诉 Claude Code：

> 请帮我安装 github.com/xkcoding/xkcoding-skills 中的 Skills

### 方式二：手动安装（全局）

```bash
git clone https://github.com/xkcoding/xkcoding-skills.git ~/xkcoding-skills

mkdir -p ~/.claude/skills
cp -r ~/xkcoding-skills/session-insights ~/.claude/skills/session-insights
```

### 方式三：手动安装（项目级）

```bash
cd /path/to/your-project

mkdir -p .claude/skills
cp -r /path/to/xkcoding-skills/session-insights .claude/skills/session-insights
```

### 方式四：符号链接（适合本仓库开发者）

```bash
ln -s /path/to/xkcoding-skills/session-insights ~/.claude/skills/session-insights
```

### 更新

通过 Marketplace 安装的用户：

1. 在 Claude Code 中运行 `/plugin`
2. 切换到 **Marketplaces** 标签
3. 选择 **xkcoding-skills** → **Update marketplace**

手动安装的用户重新 `git pull && cp -r` 即可。

### 验证

启动新的 Claude Code 会话，输入 `/` 后查看自动补全列表中是否出现 `session-insights`。

## 使用

```bash
# 交互模式（推荐）—— 会引导你选择分析范围和模式
/session-insights

# 直接指定参数
/session-insights --last 5 --depth detailed

# 后台执行
/session-insights --last 20 --depth detailed --background
```

### 分析模式

交互引导会让你选择：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| 概览报告 | 统计总览 + 时间线 + 工具分布 + 文件分类 | 快速回顾 |
| 逐个详细分析 | 串行处理每个会话，完整时序图 + 指令表 | 会话数 <= 10 |
| 并行详细分析 | 分批并行处理（`claude -p` 真并行） | 会话数 10+，可看实时进度 |
| 后台详细分析 | 后台运行，你可以继续其他工作 | 大量会话，不想等待 |

## 输出

报告写入当前项目的 `./docs/` 目录：

```
./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md
```

### 报告结构

| 章节 | 概览 | 详细 |
|------|------|------|
| 一、项目总览 | ✓ | ✓ |
| 二、开发时间线 | ✓ | ✓ |
| 三、各会话详情 | 简要摘要 | 完整时序图 + 指令表 |
| 四、工具使用分布 | ✓ | ✓ |
| 五、子 Agent 委派分析 | ✓ | ✓ |
| 六、文件变更全景 | ✓ | ✓ |
| 七、用户交互模式 | - | ✓ |
| 八、关键决策记录 | - | ✓ |
| 九、亮点 | - | ✓ |
| 十、痛点与改进 | - | ✓ |
| 十一、跨项目经验 | - | ✓ |

## 目录结构

```
session-insights/
├── README.md                        <- 你在这里
├── SKILL.md                         <- Agent 指令入口
├── references/
│   └── parallel-prompt.md           <- 并行模式执行指令
└── scripts/
    ├── session-insights.py          <- 数据提取脚本
    └── session-insights-analyze.py  <- 并行分析编排脚本（claude -p + ThreadPoolExecutor）
```
