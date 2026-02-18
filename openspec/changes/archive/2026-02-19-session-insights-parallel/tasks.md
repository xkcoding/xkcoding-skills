## 1. 并行执行策略（v1 — 散文条件，已完成但测试失败）

- [x] 1.1 在 SKILL.md 的 Step 1 和 Step 2 之间新增「执行策略判断」段落：检测 session_count > 10 && depth == detailed 时进入并行模式，否则走原有串行流程
- [x] 1.2 新增「并行模式 — Step 2P: 分批委派」段落：描述将 sessions 按每 5 个分批、用 Task 工具并行启动 Sub-Agent 的指令，包含 Sub-Agent 的 prompt 模板（输入数据 + 格式要求 + 返回规则）
- [x] 1.3 新增「并行模式 — 执行顺序」段落：描述 Main Agent 在等待 Sub-Agent 期间先生成四/五/六章（数据聚合），收集结果后拼装三章，最后生成一/二/七~十一章（全局视角）
- [x] 1.4 新增「并行模式 — 结果合并与 Fallback」段落：描述按时间顺序合并 Sub-Agent 返回的 Markdown 片段，以及 Sub-Agent 失败时的简化摘要 fallback 策略

## 2. 后台执行支持（v1 — 已完成但测试失败）

- [x] 2.1 在 SKILL.md Step 0 交互引导段落中追加 `--background` / `--bg` 参数识别说明：当用户指定该参数时跳过交互引导中的前台/后台选择
- [x] 2.2 新增「延迟决策点」段落（位于 Step 1 之后）：当并行阈值触发且无 `--background` 参数时，用 AskUserQuestion 展示 session 数量和预估时间，让用户选择前台/后台
- [x] 2.3 新增「后台执行」段落：描述选择后台时用 Task(run_in_background: true) 包裹 Step 2~4 的全部工作，Main Agent 立即返回提示信息和预期输出路径

## 3. 进度反馈（v1 — 已完成但测试失败）

- [x] 3.1 在并行模式前台执行的指令中增加进度报告：每个 Sub-Agent 批次完成时输出 "✓ 批次 N/M 完成（会话 X-Y）"，全部完成后输出 "✓ 所有批次分析完成，正在生成全局章节..."

## 4. 指令架构重构（v2 — 基于最佳实践）

- [x] 4.1 在 SKILL.md 开头（Step 0 之前）添加 ASCII 流程图，展示完整执行流向（串行 vs 并行分支）
- [x] 4.2 将 SKILL.md 中并行相关段落（执行策略判断、延迟决策点、后台执行、Step 2P、执行顺序、结果合并）全部移到 `references/parallel-prompt.md`
- [x] 4.3 将 SKILL.md Step 1 末尾的散文条件改为表格驱动路由 + `[STOP] BLOCKING` 标记：条件满足时指示 Agent 读取 `references/parallel-prompt.md` 执行
- [x] 4.4 在 SKILL.md Step 2 头部添加 `DO NOT` 负向约束：并行条件满足时禁止执行此步骤
- [x] 4.5 清理 SKILL.md 中 v1 残留的并行指令文本，确保主文件只做路由不含并行执行细节

## 5. Step 2 独立路由 Step（v3 — 强制 AskUserQuestion）

- [x] 5.1 将路由判断升级为 `## Step 2: 执行模式选择`，强制使用 AskUserQuestion（无条件工具调用）
- [x] 5.2 原 Step 2/3/4 重新编号为 Step 3/4/5
- [x] 5.3 Step 3 头部添加 DO NOT gate（并行模式跳过）
- [x] 5.4 Step 2 中实现 response mapping：用户选择 → Read parallel-prompt.md 或 → 继续 Step 3
- [x] 5.5 parallel-prompt.md 中的 Step 引用更新为 Step 4（报告格式）和 Step 5（输出）
- [x] 5.6 更新 ASCII 流程图反映新的 Step 编号和分支结构

## 6. 注意力衰减修复（v4 — 数据读取延迟）

- [x] 6.1 重构 Step 1：脚本输出重定向到临时文件 `/tmp/session-insights-raw.json`，仅提取 session_count 和 depth，禁止在此步骤读取完整 JSON
- [x] 6.2 更新 Step 3：添加「首先读取临时 JSON 文件」指令和 JSON 结构说明
- [x] 6.3 更新 parallel-prompt.md：添加「读取数据」步骤，在分批和后台执行前读取临时文件
- [x] 6.4 更新 ASCII 流程图：反映新的数据流（脚本→文件→仅提取 count→路由→读取数据）

## 7. 脚本层面强制分离（v5 — 修改脚本输出）

- [x] 7.1 修改 session-insights.py：添加 `--output-file` 参数，指定后 full JSON 保存到文件、stdout 只输出 summary
- [x] 7.2 简化 SKILL.md Step 1：移除重定向和手动 count 提取，改为运行脚本时带 `--output-file`，从摘要输出读取 session_count
- [x] 7.3 更新 design.md：添加 D9 说明为何修改脚本（原「不修改 Python 脚本」约束被 4 次实践推翻）

## 8. 双重保险（v5b — 脚本强制 + 流程前置路由）

- [x] 8.1 修改 session-insights.py：移除 else 分支，脚本**始终**保存 JSON 到文件 + stdout 只输出摘要（即使不带 --output-file）
- [x] 8.2 SKILL.md Step 0：将执行方式（串行/前台并行/后台）合并为第 3 个问题，在脚本运行前就确定路由
- [x] 8.3 SKILL.md Step 2：简化为纯分流（根据 Step 0 选择），移除所有 session_count 条件判断和 AskUserQuestion
- [x] 8.4 更新 ASCII 流程图：反映新的三问式 Step 0 和无条件分流 Step 2

## 9. 两问合一（v5c — 深度与执行方式合并）

- [x] 9.1 Step 0 问题 2 改为「分析模式」：4 个选项（概览 / 详细串行 / 详细前台并行 / 详细后台），每个选项直接映射执行路径
- [x] 9.2 Step 2 更新为按问题 2 的选项名称直接分流
- [x] 9.3 Step 1 更新 --depth 参数映射：概览→summary，详细*→detailed
- [x] 9.4 更新 ASCII 流程图

## 10. 脚本层真并行（v6 — claude -p + ThreadPoolExecutor）

- [x] 10.1 新建 `scripts/session-insights-analyze.py`：分批 + `claude -p` OS 级并行 + 拼装第三章
- [x] 10.2 SKILL.md Step 2「并行详细分析」路径改为运行 `session-insights-analyze.py`，Agent 只等结果
- [x] 10.3 SKILL.md 脚本引用表添加 `session-insights-analyze.py`
- [x] 10.4 更新 ASCII 流程图反映新的脚本并行架构
