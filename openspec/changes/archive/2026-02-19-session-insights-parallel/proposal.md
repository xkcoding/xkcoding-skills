## Why

session-insights 在 20 session + detailed 模式下非常慢（5-10 分钟），因为单个 Agent 串行完成所有会话的语义分析和 Mermaid 图表生成。需要引入并行分批处理和后台执行能力，让重负载场景下的体验可接受。

## What Changes

- SKILL.md 新增**并行执行策略**：当 `session > 10 && depth == detailed` 时，将会话分批（每批 5 个）委派给 Sub-Agent 并行分析，Main Agent 负责合并和生成全局章节
- SKILL.md 新增**后台执行支持**：达到并行阈值时询问用户前台/后台选择；支持 `--background` / `--bg` 参数直接后台执行
- SKILL.md 新增**进度反馈机制**：Sub-Agent 完成时 Main Agent 发送进度消息
- SKILL.md **指令架构重构**：采用业界最佳实践确保 Agent 可靠执行条件分支（见下方说明）

### 指令架构（关键约束）

SKILL.md 是纯 prompt 注入，没有 if/else 解释器。经测试，Agent 会忽略散文式条件分支直接走串行路径。参考 obra/superpowers、baoyu-skills 等成熟 skill 仓库的实践，采用以下架构：

1. **物理文件分离**：并行模式指令抽到 `references/parallel-prompt.md`，串行模式的 Agent 根本看不到并行指令
2. **表格驱动路由**：用 Markdown 表格（而非散文）描述条件 → 动作映射，结构化数据不容易被跳过
3. **`[STOP] BLOCKING` 标记**：在决策点使用视觉权重标记强制 Agent 停下
4. **ASCII 流程图**：在文档开头提供全局流向可视化，Agent 先建立整体认知再执行
5. **DO NOT 负向约束**：在每个互斥路径入口用 "DO NOT" 显式排除错误路径

## Capabilities

### New Capabilities
- `parallel-execution`: 并行分批策略、Sub-Agent 委派指令、结果合并规则、阈值触发条件
- `background-mode`: 后台执行触发、`--background` 参数识别、延迟决策点交互、进度反馈

### Modified Capabilities
<!-- 无现有 spec 需要修改——本次改的是 SKILL.md 的 Agent 指令，不改变已有 spec 定义的外部行为 -->

## Impact

- 修改文件：`session-insights/SKILL.md`（重构为路由表 + 分支文件架构）
- 新增文件：`session-insights/references/parallel-prompt.md`（并行模式的完整指令）
- 不改动：Python 脚本（数据提取层不变）、报告输出格式（最终产物不变）、README
- 用户影响：大任务自动触发并行 + 前台/后台选择，小任务体验不变
