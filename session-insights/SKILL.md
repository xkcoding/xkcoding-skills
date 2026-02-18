---
name: session-insights
description: Analyze Claude Code sessions for a repo, generate Markdown reports with Mermaid charts showing timelines, tool distribution, collaboration patterns, highlights and pain points.
---

# /session-insights - Claude 会话洞察分析

当用户调用此命令时，按照以下流程执行。脚本负责数据提取，Agent 负责语义分析和报告生成。

## Script Directory

**Important**: All scripts are located in the `scripts/` subdirectory of this skill.

**Agent Execution Instructions**:
1. Determine this SKILL.md file's directory path as `SKILL_DIR`
2. Script path = `${SKILL_DIR}/scripts/<script-name>.py`
3. Replace all `${SKILL_DIR}` in this document with the actual path

**Script Reference**:
| Script | Purpose |
|--------|---------|
| `scripts/session-insights.py` | 从 `~/.claude/projects/` 提取会话 JSONL 数据，输出结构化 JSON |

## Step 0: 交互引导

使用 `AskUserQuestion` 向用户确认选项（一次性问两个问题）：

**问题 1 - 分析范围**（header: "范围"）:
- "最近 5 个会话 (Recommended)" — 快速概览，适合日常回顾
- "最近 10 个会话" — 中等范围，覆盖近期工作
- "最近 20 个会话" — 较完整分析
- "全部会话" — 完整分析，大项目可能较慢

**问题 2 - 分析深度**（header: "深度"）:
- "概览 (summary) (Recommended)" — 统计总览 + 时间线 + 工具分布 + 文件分类。不展开每个会话的详细时序
- "详细 (detailed)" — 以上全部 + 每个会话的详细交互分析（时序图、关键指令精选表）+ 亮点/痛点/跨项目经验

如果用户在调用时已经提供了明确参数（如 `/session-insights --last 5 --depth detailed`），可以跳过引导。

## Step 1: 运行数据提取脚本

脚本位于 `${SKILL_DIR}/scripts/session-insights.py`，输出结构化 JSON。

根据用户选择构造命令：

```bash
# 自动检测项目（用 CWD）
python3 ${SKILL_DIR}/scripts/session-insights.py --last N --depth summary|detailed

# 如果自动检测失败，用项目关键词
python3 ${SKILL_DIR}/scripts/session-insights.py "project-keyword" --last N --depth summary|detailed
```

参数映射：
- "最近 5 个会话" → `--last 5`
- "最近 10 个会话" → `--last 10`
- "最近 20 个会话" → `--last 20`
- "全部会话" → 不加 `--last`

脚本会输出 JSON 到 stdout，包含：
- `totals` — 汇总统计（会话数、消息数、工具调用数、活跃时间等）
- `all_tools` — 工具使用频次排行
- `all_sub_agents` — 子 Agent 类型分布
- `all_files_edited` — 修改的文件列表（含编辑频次）
- `all_files_written` — 创建的文件列表
- `sessions[]` — 每个会话的详细数据：
  - 时间范围、活跃时间/百分比、空闲段
  - 用户输入（已清洗，精选摘要）、Agent 输出摘要
  - 工具使用 top 10、子 Agent 类型、模型分布
  - 修改的文件（含频次）、git commits、使用的 skills

## Step 2: 语义分析（Agent 核心职责）

**这是关键步骤——不要机械输出数据，要用自己的理解来分析和提炼。**

读取 JSON 数据后，Agent 需要：

1. **理解每个会话的主题**：从 `user_inputs` 提炼出这个会话在做什么（而非列出每条消息）
2. **识别开发阶段**：项目经历了哪些阶段（搭建、开发、调试、优化...）
3. **发现协作模式**：用户和 Agent 如何协作，哪些工作流效率高
4. **评估时间效率**：活跃时间 vs 会话时间，是否有可优化空间
5. **总结关键决策**：技术选型、架构变更等重要决策点
6. **提炼亮点 (Highlights)**：做得好的地方——高效的协作模式、精准的任务拆解、一次成功的复杂操作等
7. **识别痛点 (Pain Points)**：做得不好的地方——反复修改、走弯路、效率低的交互模式、理解偏差等
8. **形成可复用经验**：把亮点抽象为 pattern（其他项目可以复用），把痛点转化为具体改进建议

## Step 3: 生成 Markdown 报告

生成一份中文 Markdown 文档。**所有文字都用 Agent 自己的理解来写，不机械复制数据。**

报告结构分为两个层级：

### Summary 模式（概览）

包含章节：一~六

### Detailed 模式

包含章节：一~十一（全部）

---

### 一、项目总览

简短的项目简介（1-2 句，从会话内容推断项目是什么），加上统计表：

| 指标 | 数值 |
|------|------|
| 会话数 | N（有效 M） |
| 时间跨度 | ... |
| 会话总时长 | ... |
| **实际活跃时长** | **...（百分比）** |
| 用户消息总数 | ... |
| 工具调用总次数 | ... |
| 子 Agent 会话数 | ... |
| Git 提交数 | ... |

### 二、开发时间线

两个可视化：

**2.1 会话时间对比表** — 每个会话的主题、时长、活跃时长、活跃率、空闲说明（最大空闲段）

**2.2 Gantt 时间线** — Mermaid `gantt` 图，展示各会话的时间分布和主题：

```
gantt
    title 项目开发时间线（标注活跃时间）
    dateFormat  YYYY-MM-DD HH:mm
    axisFormat  %m-%d %H:%M
    section 会话 1 · 主题
    描述 (活跃 Xmin)   :s1, 起始时间, 持续分钟m
```

**2.3 活跃时间柱状图** — 使用 Mermaid `xychart-beta` 对比每个会话的总时长和活跃时长：

```
xychart-beta
    title "各会话活跃时间占比"
    x-axis ["会话1 主题", "会话2 主题", ...]
    y-axis "时间 (分钟)" 0 --> MAX
    bar [会话总时长...]
    bar [活跃时长...]
```

> 注意：xychart-beta 比普通 bar chart 更直观，优先使用。

### 三、各会话详情

**这是报告的核心章节，在 Summary 模式下只展示简要摘要，在 Detailed 模式下展开完整分析。**

#### Summary 模式下

每个会话用 2-3 行简要描述：主题 + 统计数据 + 关键成果。不展开时序图。

#### Detailed 模式下

对每个会话，展示：

**3.a 主题描述**（1-2 句话概括）

**3.b 核心交互时序图**（Mermaid `sequenceDiagram`）

关键要求：
- **不超过 15 个交互节点/会话**
- 用 `par ... end` 块表示并行操作（如并行开发、并行审查）
- 用 `Note over` 标注阶段分隔（如 Phase 0, Phase 1）
- 用 `loop` 块表示反复迭代的交互（如多轮样式调整）
- 合并连续同类操作为一个有意义的步骤

示例结构：
```
sequenceDiagram
    participant U as 用户
    participant A as Claude Agent
    participant S as 子 Agent

    Note over U,S: Phase 1 — 基建
    U->>A: [用自己的话概括]
    A-->>U: ✅ 结果

    Note over U,S: Phase 2 — 并行开发
    par 并行开发
        U->>S: 功能 A
        U->>S: 功能 B
    end
```

**3.c 统计行**（用户消息数 | 工具调用数 | 子 Agent 数 | Git 提交数）

**3.d 精选用户指令表**（仅 Detailed 模式）

从 user_inputs 中精选 5-10 条最有代表性的指令，展示为表格。选取标准：关键需求、重要 Bug 报告、架构决策、方向转变。**不要列出全部用户输入。**

| # | 用户指令（精简） | Agent 响应 |
|---|-----------------|-----------|
| 1 | "..." | 做了什么 |

**3.e Agent 团队拓扑**（仅当该会话使用了 Agent Team 时展示）

使用 Mermaid `flowchart` + `style` 命令，为每个角色设置**不同颜色**和 **emoji**：

```
flowchart TD
    Lead["🎯 Team Lead<br/>(用户 + Claude)"]
    Designer["🎨 designer<br/>设计规范"]
    Foundation["🏗️ foundation<br/>基建层"]

    Lead -->|"Phase 0"| Designer
    Lead -->|"Phase 1"| Foundation
    Designer -->|"产出物"| Foundation

    style Lead fill:#f0fdfa,stroke:#0d9488,stroke-width:2px
    style Designer fill:#dbeafe,stroke:#3b82f6
    style Foundation fill:#d1fae5,stroke:#10b981
```

> 关键：必须用 `style` 给节点上色，否则所有节点灰白一片，无法区分角色。推荐配色：
> - Lead: teal (#f0fdfa/#0d9488)
> - Designer: blue (#dbeafe/#3b82f6)
> - Foundation/Builder: green (#d1fae5/#10b981)
> - Feature team: purple (#ede9fe/#8b5cf6), orange (#ffedd5/#f97316)
> - Reviewer: amber (#fef3c7/#f59e0b)

### 四、工具使用分布

**4.1 Pie 图** — Top 10 工具调用比例：

```
pie title 工具调用分布（Top 10，共 N 次）
    "Edit (编辑文件)" : 372
    "Bash (命令执行)" : 363
```

**4.2 工具使用模式表** — 按类别分组（代码编辑、命令执行、代码阅读、任务管理、浏览器测试、诊断），每个工具列出次数和用途。

### 五、子 Agent 委派分析

使用 Mermaid `flowchart` + `subgraph` 分组展示：
- Agent Team 成员（按团队分 subgraph）
- Ad-hoc 子 Agent（Explore、frontend-architect 等）
- 每个节点标注调用次数和 emoji

```
flowchart TD
    Main["Claude Main Agent<br/>N 次工具调用"]

    subgraph "Agent Team: xxx (会话 N)"
        T1["designer ×2<br/>🎨 设计规范"]
        T2["foundation ×2<br/>🏗️ 基建"]
    end

    subgraph "Ad-hoc 子 Agent"
        E["Explore ×9<br/>🔍 代码探索"]
    end

    Main --> T1 & T2
    Main --> E

    style Main fill:#f0fdfa,stroke:#0d9488,stroke-width:2px
```

### 六、文件变更全景

**6.1 新建文件分类表** — 按类别分组（组件、Store、工具、样式、规格、资源等）

**6.2 高频编辑文件 Top 10** — 使用脚本提供的 `edit_count` 字段排序，说明每个文件频繁编辑的原因

| 文件 | 编辑次数 | 说明 |
|------|---------|------|

---

**以下章节仅 Detailed 模式**

### 七、用户交互模式总结

**7.1 用户消息类型分布** — Mermaid `pie` 图，Agent 自行从用户消息中分类（功能需求、Bug 报告、UI 调整、工作流指令、探讨/决策等）

**7.2 典型交互模式** — 归纳 3-5 个高频交互模式（如：探索→讨论→实现、截图驱动反馈、渐进式优化等）

**7.3 工作流/技能使用统计** — 如果项目使用了 skills（OpenSpec、sc:git 等），列出调用次数和用途表

### 八、关键决策记录

用表格记录项目中的重要技术决策：

| 决策 | 背景 | 结果 |
|------|------|------|
| 技术栈选择 | 用户要求... | 选定 ... |

选取标准：技术选型、架构变更、方案转变、策略调整。通常 5-8 条。

### 九、亮点 (Highlights)

提炼 3-5 个做得好的地方，形成可复用的 pattern。**每个亮点必须包含三部分**：

> **亮点 N：标题**
>
> 具体描述 — 发生了什么，为什么做得好（2-3 句）
>
> **数据支撑**: 从哪些指标看出来的（效率、一次成功率、活跃率等）
>
> **可复用 Pattern**: 抽象为其他项目也能用的 1 句话经验

分析维度（按优先级）：
1. 高效协作模式（如：精准的一句话指令、好的任务拆分习惯、Agent Team 并行）
2. 工具使用效率（如：善用子 Agent 并行、批量操作代替逐个操作）
3. 架构/技术决策（如：正确的库选型、合理的抽象层次）
4. 流程创新（如：Spec 驱动开发、Reviewer 独立验收）

### 十、痛点与改进 (Pain Points & Improvements)

识别 3-5 个做得不好或可以优化的地方。**每个痛点必须包含三部分**：

> **痛点 N：标题**
>
> 具体描述 — 发生了什么，表现是什么（2-3 句）
>
> **影响**: 浪费了多少时间/轮次/精力（量化）
>
> **改进**: 具体、可操作的改进建议（1-2 条）

分析维度（按优先级）：
1. 返工/走弯路（同一功能反复修改、方向错误后回退）
2. 集成问题（静态审查通过但运行时失败）
3. 沟通成本（理解偏差、需要多轮澄清、指令模糊）
4. 效率瓶颈（活跃率低、上下文溢出、长时间空闲段）

### 十一、跨项目经验总结

面向未来项目的可复用洞察，三个维度各 2-3 条：

1. **最佳实践**: 值得在所有项目中推广的做法
2. **避坑指南**: 其他项目应该注意避免的问题
3. **工作流优化建议**: 对 Claude Code 使用方式的改进建议

---

## Step 4: 输出

将生成的 Markdown 写入 `./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md`。

其中 `{YYYYMMDD-HHmmss}` 为报告生成时的时间戳（如 `20260218-153042`），确保每次生成都是独立快照，不覆盖历史。

告知用户文件已生成的路径。

## 注意事项

### 内容质量
- **语义理解优先**：不要机械复制粘贴消息内容，用自己的理解来总结和提炼
- **合并连续操作**：连续的工具调用应合并为一个有意义的步骤描述
- **突出关键决策**：重点展示技术选型、架构变更、问题解决等转折点
- **不要 dump 用户输入**：永远不要以 `<details>` 折叠块形式列出完整用户输入列表。只提供精选摘要表

### Mermaid 图表
- **序列图控制节点数**：每个会话不超过 15 个交互节点
- **使用 par 块**：并行操作必须用 `par ... end` 包裹
- **flowchart 必须上色**：Agent Team 拓扑必须用 `style` 为每个节点设置不同 fill/stroke 颜色
- **使用 xychart-beta**：活跃时间对比优先使用 xychart-beta（双柱状图），不要用普通 bar
- **subgraph 分组**：子 Agent 分析用 subgraph 按团队分组

### 安全与格式
- **不要暴露敏感信息**：如果 session 中有 API key、密码等，不要写入报告
- **输出语言**：全部中文
- **章节编号**：使用中文数字（一、二、三...）
- **脚本失败兜底**：如果脚本执行失败，Agent 应该直接用 Glob + Read 工具读取 JSONL 文件，手动提取数据
