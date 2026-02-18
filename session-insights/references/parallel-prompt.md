# 并行模式执行指令

> 本文件在 session_count > 10 且 depth == detailed 时由 Main Agent 读取。
> 包含分批委派、执行顺序、结果合并的完整指令。
> 报告的章节格式仍以 SKILL.md 中 Step 4 的定义为准。

---

## 0. 读取数据

使用 Read 工具读取 Step 1 保存的 JSON 数据文件 `/tmp/session-insights-raw.json`，获取完整数据。提取 `sessions` 数组用于后续分批，提取 `totals`、`all_tools`、`all_sub_agents`、`all_files_edited`、`all_files_written` 用于数据聚合章节。

---

## 前台并行模式

### 1. 分批策略

将 sessions 按每 **5 个**一批分组：
- 20 个 session → 4 批（5, 5, 5, 5）
- 13 个 session → 3 批（5, 5, 3）
- 11 个 session → 3 批（5, 5, 1）

### 2. 启动 Sub-Agent（并行委派）

> **⚠️ 关键：必须在一条 response 中同时包含所有批次的 Task 工具调用。**
> 不要等一个 Task 完成后再启动下一个——那是串行，不是并行。
> 正确做法：一次性生成 N 个 Task 工具调用，让它们同时运行。

每个 Sub-Agent 使用以下 prompt 模板：

~~~
Task(
  subagent_type: "general-purpose",
  description: "分析会话批次 {batch_index}/{total_batches}",
  prompt: """
  你是 session-insights 的会话分析 Sub-Agent。请分析以下 {batch_size} 个会话数据，
  为每个会话生成详细分析的 Markdown 片段。

  ## 输入数据

  {当前批次的 sessions JSON 子数组，只包含该批次的 session 数据}

  ## 输出格式

  对每个会话生成以下结构（不要包含「三、各会话详情」章节标题）：

  ### 会话 N：{日期} {主题概括}

  **核心交互时序图**

  （Mermaid sequenceDiagram，不超过 15 个节点，用 par/loop/Note over 语法）

  **统计**：用户消息 X | 工具调用 Y | 子 Agent Z | Git 提交 W

  **精选用户指令**

  | # | 用户指令（精简） | Agent 响应 |
  |---|-----------------|-----------|
  （精选 5-10 条最有代表性的指令）

  **Agent 团队拓扑**（仅当该会话使用了 Agent Team 时展示，Mermaid flowchart + style 上色）

  ## 规则
  - 用自己的理解来分析，不机械复制数据
  - 时序图合并连续同类操作，控制在 15 节点以内
  - flowchart 必须用 style 为每个节点设置不同颜色
  - 按会话时间顺序排列
  - 返回纯 Markdown 片段，不要额外解释文字
  """
)
~~~

### 3. 执行顺序

1. **启动 Sub-Agent**：在单条消息中发出所有批次的 Task 调用（并行分析第三章各会话详情）
2. **同时生成数据聚合章节**：在 Sub-Agent 工作期间，Main Agent 利用 JSON 数据直接生成：
   - 四、工具使用分布
   - 五、子 Agent 委派分析
   - 六、文件变更全景
3. **收集 Sub-Agent 结果**：等待所有批次返回，按会话时间顺序拼装第三章
4. **生成全局视角章节**：需要所有会话分析结果才能写的章节：
   - 一、项目总览
   - 二、开发时间线
   - 七~十一（仅 detailed 模式）
5. **最终拼装**：按章节编号（一~十一）顺序拼装完整报告，然后执行 SKILL.md 中的 Step 5（输出文件）

> 这个执行顺序让 Main Agent 在等待 Sub-Agent 时不闲着，同时确保需要跨会话视角的章节在所有数据就绪后才生成。

### 4. 进度报告

每个 Sub-Agent 批次完成时，输出进度消息：

```
✓ 批次 {N}/{M} 完成（会话 {start}-{end}）
```

全部批次完成后输出：

```
✓ 所有批次分析完成，正在生成全局章节...
```

### 5. 结果合并

收集所有 Sub-Agent 返回的 Markdown 片段后：

1. 按会话时间（session 的 `start_time`）升序排列
2. 在最前面添加章节标题 `## 三、各会话详情`
3. 依次拼接所有片段

### 6. Fallback 策略

如果某个 Sub-Agent **失败**（返回空内容、错误信息、或超时无响应）：

1. Main Agent 自行为该批次的 session 生成**简化摘要**（每个 session 2-3 行：主题 + 统计数据 + 关键成果，不生成时序图和指令表）
2. 在该批次的简化摘要前添加提示：`> ⚠️ 以下会话因分析超时，仅展示简要摘要`
3. 继续拼装报告，不中断整体流程

---

## 后台模式

当用户选择后台执行（或指定了 `--background` / `--bg`）时：

使用 **Task 工具** 启动一个 `run_in_background: true` 的 sub-agent，将分析和报告生成的全部工作委托给它：

~~~
Task(
  subagent_type: "general-purpose",
  run_in_background: true,
  description: "session-insights 后台分析",
  prompt: """
  你是 session-insights 分析 Agent。以下是提取好的 JSON 数据：
  {完整 JSON 数据}

  请按照以下指令完成分析和报告生成：
  1. 将 sessions 按每 5 个分批，用 Task 工具并行启动 Sub-Agent 分析第三章
  2. 同时生成第四/五/六章（数据聚合）
  3. 收集 Sub-Agent 结果，拼装第三章
  4. 生成第一/二/七~十一章（全局视角）
  5. 按章节顺序拼装完整报告
  6. 写入 ./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md

  {将上方「前台并行模式」的分批指令 + SKILL.md 中 Step 4 的报告格式 + Step 5 的输出指令嵌入此处}
  """
)
~~~

Main Agent 立即向用户返回：

- 「已在后台启动分析任务，预计需要 {estimated_time} 分钟」
- 「报告将写入：`./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md`」
- 「你可以继续其他工作，稍后查看任务输出」

然后 Main Agent 的工作结束，后续由后台 sub-agent 完成。
