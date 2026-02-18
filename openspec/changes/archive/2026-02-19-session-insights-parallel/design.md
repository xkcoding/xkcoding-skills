## Context

session-insights SKILL.md 当前是线性执行：脚本提取 → Agent 逐个分析 → 串行生成报告。20 session detailed 模式需要 5-10 分钟，瓶颈在 Agent 的语义分析和 Mermaid 图表生成（Step 2+3），不在数据提取（Step 1，秒级）。

SKILL.md 是纯 Agent 指令，改动不涉及代码，只需要在指令中加入并行委派和后台执行的策略描述。Agent 已有 Task 工具（支持 `run_in_background`）和 AskUserQuestion 工具。

## Goals / Non-Goals

**Goals:**
- detailed 模式 10+ session 时通过 Sub-Agent 并行分批，第三章（最重的部分）提速 3-4 倍
- 支持后台执行，用户可以继续其他工作
- 保持小任务（summary 模式、≤10 session）的体验不变
- 最终报告产物格式不变

**Non-Goals:**
- 不修改 Python 脚本
- 不改变报告的章节结构或内容质量
- 不做 summary 模式的并行优化（已够快）
- 不实现断点续传（中断后重跑即可）

## Decisions

### D1: 章节分类 — 可并行 vs 必须串行

**分析**：报告 11 章节中，哪些可以独立并行？

| 类型 | 章节 | 原因 |
|------|------|------|
| 可并行 | 三、各会话详情 | 每个 session 独立分析，互不依赖 |
| 串行-数据聚合 | 四、工具分布 / 五、Agent / 六、文件 | 纯数据汇总，Main Agent 快速生成 |
| 串行-全局视角 | 一、总览 / 二、时间线 | 需要所有 session 数据 |
| 串行-跨会话 | 七~十一 | 需要看完所有会话分析才能对比提炼 |

**决策**：只并行**第三章（各会话详情）**，这是 detailed 模式中占 70%+ 工作量的部分。其余章节由 Main Agent 串行生成。

### D2: 批次大小 5 session/batch

**选择**：每个 Sub-Agent 处理 5 个 session。

**理由**：
- 5 个 session 的 detailed 分析（时序图 + 指令表 + 拓扑图）是一个 Sub-Agent 单次合理的工作量
- 20 session → 4 个并行 Sub-Agent，并行度足够
- 更小的批次（如 2-3 个）启动开销占比过高

### D3: 延迟决策点 — 脚本跑完后再问前台/后台

**选择**：在 Step 1（脚本执行）完成后、Step 2（语义分析）开始前插入决策点。

**备选方案**：
- A) Step 0 就问 — 用户还不知道实际数据量，选择不够 informed
- B) Step 1 后问 — 用户看到 "检测到 20 个会话" 后做选择 ✓
- C) 不问，自动决策 — 用户可能想看实时进度

**触发条件**：`session_count > 10 && depth == detailed` 时弹出选择。其他情况默认前台，不打扰。

### D4: `--background` / `--bg` 跳过询问

**选择**：用户在调用时带 `--background` 或 `--bg` 参数，直接后台执行，不弹出 AskUserQuestion。

**理由**：用户已经知道任务重，不需要再确认。与 `--last N --depth detailed` 参数风格保持一致。

### D5: 后台执行用 Task(run_in_background: true) 包裹

**选择**：后台模式下，Main Agent 用 Task 工具启动一个 `run_in_background: true` 的 sub-agent，该 sub-agent 内部再执行并行分析。

**理由**：Task 的 `run_in_background` 是 Claude Code 唯一的后台执行机制。Main Agent 立即返回提示信息，用户可继续工作。

### D6: Sub-Agent 输入输出协议

**选择**：Main Agent 将 JSON 数据中对应批次的 sessions 子数组 + 报告格式要求作为 prompt 传给 Sub-Agent，Sub-Agent 返回该批次的 Markdown 片段。

**数据流**：
```
Main Agent → Sub-Agent prompt:
  - sessions[0:5] 的 JSON 数据
  - 第三章的格式要求（从 SKILL.md 中提取）
  - "返回 Markdown 片段，不要包含章节标题"

Sub-Agent → 返回:
  - 各 session 的详情 Markdown（主题、时序图、统计、指令表、拓扑图）
```

Main Agent 收到所有片段后按 session 时间顺序拼装。

### D7: 指令架构 — 物理分离并行/串行分支

**问题**：首次实现将并行和串行指令放在同一个 SKILL.md 中，用散文条件分支路由。测试发现 Agent 直接忽略条件判断走了串行路径。

**根因**：SKILL.md 是纯 prompt 注入，LLM 看到全部文本后倾向走最简单/最线性的路径。散文式 if/else 对 LLM 只是"建议"不是"指令"。

**选择**：采用业界验证有效的 pattern 组合：

| Pattern | 来源 | 作用 |
|---------|------|------|
| 并行指令抽到独立文件 `references/parallel-prompt.md` | obra/superpowers | Agent 串行时看不到并行指令，消除路径干扰 |
| Step 1 末尾用表格路由 | baoyu-skills, zachwills | 结构化条件映射，比散文更难跳过 |
| `[STOP] BLOCKING` 标记 | baoyu-slide-deck | 视觉权重强制 Agent 停下做判断 |
| ASCII 流程图 | baoyu-skills | Agent 先建立全局流向认知 |
| `DO NOT` 负向约束 | obra/superpowers | 在互斥路径入口显式排除错误路径 |

**备选方案**：
- A) 纯散文条件 — 已测试失败
- B) 所有场景都走并行（忽略阈值） — 小任务浪费开销
- C) MCP server 强制状态机 — 过于重量级，不值得

### D8: 主文件结构 — 路由 + 执行分离

**选择**：SKILL.md 只做路由（Step 0 → Step 1 → 路由表 → 指向对应执行路径），具体执行指令按模式分离：
- 串行模式：继续在 SKILL.md 的 Step 2/3/4 中执行（已有内容不动）
- 并行模式：Agent 读取 `references/parallel-prompt.md` 获取完整的并行执行指令

**理由**：串行路径是原有行为、文本量适中，留在主文件即可。并行路径是新增的大段指令，放入独立文件可以避免主文件膨胀，也实现了物理隔离。

### D9: 修改 Python 脚本（推翻原「不修改脚本」约束）

**背景**：原 Non-Goals 声明「不修改 Python 脚本」。经过 v1-v4 四次纯 prompt 层面的迭代全部失败，证明仅靠 SKILL.md 指令无法阻止 Agent 读取大量 JSON 数据。

**根因**：SKILL.md 是 prompt 注入，Agent 读取后以"最小阻力路径"执行。当脚本输出大量 JSON 到 stdout 时，Agent 自然会读取全部内容（多轮 Read/处理操作），导致后续路由指令（Step 2 AskUserQuestion）被推出注意力窗口。

**已验证失败的方案**（全部是纯 prompt 层面）：
- v1: 散文条件分支 → Agent 直接忽略
- v2: 表格路由 + [STOP] BLOCKING + 文件分离 → Agent 忽略子章节标记
- v3: 独立 Step 2 + 强制 AskUserQuestion → Agent 读完数据后跳过 Step 2
- v4: 重定向到文件 + 仅提取 count + DO NOT 约束 → Agent 不执行重定向指令

**决策**：添加 `--output-file` 参数到 Python 脚本。指定后，完整 JSON 保存到文件，stdout 只输出摘要（session_count、depth 等 6 个字段）。这在数据层面而非指令层面强制分离，Agent 无论如何执行脚本都只能看到摘要。

**理由**：脚本的控制力 > prompt 的控制力。脚本是代码，行为确定性 100%；prompt 是建议，Agent 遵循率不可靠。最小修改（添加一个参数 + 10 行代码），向后兼容（不带 `--output-file` 时行为不变）。

## Risks / Trade-offs

- **[Sub-Agent 质量一致性]** 不同 Sub-Agent 的分析风格可能不一致 → prompt 中包含明确的格式模板和示例，减少偏差
- **[Context 压力]** 每个 Sub-Agent 收到 5 session 的 JSON + 格式指令，可能较长 → 只传必要数据（user_inputs、top_tools、时间信息），不传完整 agent_summaries
- **[后台任务失败]** Sub-Agent 可能失败或超时 → Main Agent 在合并阶段检测缺失批次，对缺失的 session 生成简化摘要作为 fallback
- **[并行开销]** 4 个 Sub-Agent 的启动开销约 10-15 秒 → 只在 10+ session detailed 时触发，小任务不受影响
- **[Agent 忽略条件分支]** LLM 倾向走线性路径，跳过散文条件判断 → D7 采用物理文件分离 + 表格路由 + BLOCKING 标记组合解决（已测试验证散文方案失败）
