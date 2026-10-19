# Design

## Context

动机见 proposal.md「Why」。这里只记影响做法的现状与实测。

**现状**：`ar.py` 的 `HARNESS_TYPES = ("claude", "codex", "shell")`。第三方模型从两条路进来：`claude` harness 配合 `harness.env`（`resolve_env` 解析 `$VAR`，`unknown_window_warning` 管 200k 窗口），以及 `shell` harness 包一层 `claude -p`，再由 `claude_result()` 解析它的 stdout。四个示例都不用 `harness.env`；`toy` 用 `shell` 跑一个不调模型的脚本。

**实测**（2026-10-19，macOS，glm-5.3，两边都用工具自己的系统配置；在临时仓库里修同一个一行 bug，各跑一次）：

| # | pi 1.3.0 | goose 1.55.0 |
|---|---|---|
| E1 | `pi --mode json --no-session "<p>"` 一轮 19 秒改对，退出 0 | `goose run --output-format json --no-session -t "<p>"` 一轮 66 秒改对，退出 0 |
| E2 | stdout 是 JSONL：`session` → `agent_start` → `turn_*` / `message_*` / `tool_execution_*` → `agent_end` → `agent_settled` | stdout **先是几行 ASCII 横幅**，然后是一个多行 JSON 对象 `{messages, metadata}` |
| E3 | usage 在每条 assistant `message_end.message.usage` 里，**各条分开**：`input / output / cacheRead / cacheWrite / cost.total`；三条消息合计 input 6757、cacheRead 17344、$0.0144 | `metadata` 是累计值：`input_tokens / output_tokens / cache_read_input_tokens / cache_write_input_tokens / cost_usd / status` |
| E4 | 最终文本 = 最后一条 assistant 消息的 text 块 | 最终文本 = `messages` 里最后一条 assistant 的 text 块 |
| E5 | 强制错 key（`--api-key bogus`）：**退出 0**，最后一条 assistant `stopReason: "error"`，`errorMessage: "401: …"`，`content` 为空 | 错 key（`ZHIPU_API_KEY=bogus`）：退出 1，`metadata.status: "error"`，stderr 写明 401 |
| E6 | 没有轮数或费用上限的 flag | `--max-turns 1`：退出 0、`status: "completed"`，最后一句固定话术 "I've reached the maximum number of actions…"；没有费用上限 |
| E7 | 默认把 `~/.pi/agent/skills` 的 28 个 skill（约 23k 字符）写进 system prompt；`--no-skills --no-extensions --no-prompt-templates` 可关 | 默认加载 config 里启用的 extensions（summon 子 agent、extension 管理、tom 等）；`--no-profile --with-builtin developer` 后工具只剩 `edit / load_skill / read_image / shell / tree / write`，同一任务仍改对 |
| E8 | 凭据优先级：`--api-key` > `auth.json` > `models.json` > 环境变量（文档 + 实测：env 里的错 key 被 `auth.json` 盖过，照常成功） | 环境变量 > `config.yaml`（实测 `ZHIPU_API_KEY=bogus` 生效） |
| E9 | 自带模型元数据，glm-5.3 窗口 1M | 内置 `zhipu` provider，glm-5.3 `context_limit` 1000000 |

## Goals / Non-Goals

**Goals:**
- pi / goose 两个 adapter 产出的 checkpoint 字段与 claude / codex 同构（usage 四项、note、cost、turns 能拿就拿）。
- runner 对凭据与端点零感知。
- `known-behaviors.md` 只剩会改变会话做法的条目。

**Non-Goals:**
- 不替用户配置 pi / goose 的模型或 key，doctor 也不检查"配没配好"——没配好时第一轮就会以 error 结束，原因写在 `harness.err` / reason 里。
- 不给 pi 造轮数上限（比如数 `turn_end` 事件后杀进程）。
- 不改报告的结构；只改费用提示文案。

## Decisions

### D1 凭据与端点完全交给工具自己的配置，删掉 `harness.env`

E8 说明两个工具的凭据优先级方向相反：pi 的 `auth.json` 会静默盖过 runner 注入的环境变量，goose 则相反。runner 想可靠地控制凭据，就得为每个工具写一套注入逻辑（pi 必须走 `--api-key`），而这件事用户在工具里配一次就够了。`harness.env` 唯一的用途是给 `claude` 接端点，这条路已经关了。

备选：保留 `harness.env` 当通用环境透传。没有剩余用例，留着就是一个能被拿去重新接端点的口子。

`harness_env()` 继续去掉父会话的 `CLAUDECODE` / `CLAUDE_CODE_SSE_PORT` / `CLAUDE_CODE_ENTRYPOINT`，只是不再合并 extra。

### D2 `claude` 拒绝 `ANTHROPIC_BASE_URL`，在 preflight 与 doctor 两处

去掉 `harness.env` 后，`claude` 子进程仍继承 runner 的环境，用户在 shell 里 export 的端点变量会原样生效。runner 在 preflight 发现 `claude` subject 且环境里有 `ANTHROPIC_BASE_URL` 时直接拒绝，doctor 记为 problem。只看这一个变量：它是把 Claude Code 指向非 Anthropic 端点的必要条件；`ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_MODEL` 单独存在不改变去向。

备选：判断 URL 的域名是否属于 Anthropic。会把企业代理、网关一类合法用法误判成允许或拒绝，规则也要跟着域名变；一刀切更好解释。

### D3 两个 adapter 的命令

```
pi    --mode json --no-session --no-skills --no-extensions --no-prompt-templates
      [--model <harness.model>] <prompt>
goose run --output-format json --no-session --no-profile --with-builtin developer
      [--model <harness.model>] [--max-turns <max_turns>] -t <prompt>
```

- 隔离（E7）：每轮只看 prompt 与仓库，和"harness 无状态"一致，也避免用户全局装的 skill 或子 agent 改变一轮的行为、让轮与轮不可比。pi 保留 `AGENTS.md` / `CLAUDE.md` 的读取（不加 `--no-context-files`），与 claude harness 读取仓库 `CLAUDE.md` 的行为一致。
- prompt 走 argv，与 claude / codex 一致；`ar.py` 的日志已把它显示成 `<prompt>`。
- stdin 给 `/dev/null`（`spawn` 现有行为），避免任一工具在无 TTY 时等输入。
- pi 不传 `--provider`：`--model` 接受 `provider/id`，用户想换 provider 写进 `harness.model` 即可。

### D4 解析与成败判定

- pi：逐行解析 JSONL；对 role 为 assistant 的 `message_end` 累加 `input / output / cacheRead / cacheWrite` 与 `cost.total`，`turns` = assistant 消息数，`session_id` 取 `session` 事件的 `id`；最后一条 assistant 消息 `stopReason == "error"` → failure `harness_error:<errorMessage 前 200 字>`（E5，与退出码无关）；没有任何 assistant 消息且退出 0 → `harness_output_not_json`，与 claude 一致。
- goose：从 stdout 第一个以 `{` 开头的行起整体 `json.loads`（E2）；`metadata.status == "error"` 或退出码非 0 → failure；`max_turns` 截断（E6）不判 failure，也不设 `cut_off`：goose 没有给出可靠信号，匹配那句固定话术太脆，这一轮照常打分即可。
- 只给 runner 用的事实（E2–E7）写在这两个函数的 docstring 里，带日期与版本，不进 `known-behaviors.md`。

### D5 不支持的上限在启动前拒绝

pi 设了 `max_turns` / `max_budget_usd`，或 goose 设了 `max_budget_usd`，在 `resolve_harness` 阶段就拒绝，因为不拒绝等于用户以为有上限、实际没有。只拒绝 `research.json`（research 级默认或 subject 级覆盖）里**显式写出的非 null 值**：`resolve_harness` 现有的 `max_turns` 默认值 40 只给 `claude` 与 `goose`，pi 的默认是 null。`init --harness pi` 生成的模板把 `max_turns` 写成 null。

### D6 `shell` 只取 stdout 尾巴

删掉 `run_harness` 里 `shell` 走 `claude_result()` 的分支；`claude_result()` 只服务 `claude`，可以简化掉 stream-json 的处理，但它对单行 JSON 的读法不变。`_doc_type` / `_doc_command` 改写成"不调模型的脚本或自定义执行器"。

### D7 `known-behaviors.md` 的筛法

尺子：**这条会不会改变会话的做法**（建议用户、设计 subject、读进度、人工介入）。只服务 runner 的事实进对应代码的注释；过程数据（某次跑了多少秒、多少钱、事件流多大）删除；仍有用的结论压成一行，保留日期与版本。

| 现有条目 | 处理 |
|---|---|
| claude `--help` 不列全部 flag；`-p` JSON 字段；`CLAUDECODE` 去除；上限触发退出 1 | 删（`run_harness` 注释里已有） |
| `--max-budget-usd` 是首个 API 调用后才判定、实际可远超上限 | 留一行（会话要据此告诉用户预算不是硬上限） |
| stream-json 包装、prompt 缓存跨进程命中率 | 删 |
| codex 事件流字段、`--add-dir`、kata 跑数据、stdin 提示 | 删（字段进 `codex_events` 注释，已有） |
| codex 的模型来自它自己的 config、`harness.model` 为 null | 并入新的一行"模型与凭据都用工具自己的配置" |
| 循环不能在 codex 沙箱里启动 | 留（会话不能从 codex 里起循环） |
| 第三方 Anthropic 兼容端点整节 | 删 |
| git revert 拒绝空 commit | 删 |
| `kill -9` 遗弃 harness 进程组 | 留（停循环的方式） |
| 未 add 的新文件也算本轮改动 → 仓库要有 `.gitignore` | 留，与"agent 不留临时文件"合并 |
| 平凡轮次代价、opus / sonnet 代价差 | 压成一行"代价量级"，留在 SKILL.md 技术事实，KB 删 |
| 一轮进行中手改打分器会被当越界 crash，可从 patch 恢复 | 留（人工介入） |
| 可枚举合成任务一两轮打满；公开 / 隐藏差距看过拟合 | 留（设计打分器），压成一行 |
| compress 31 轮曲线 | 删 |
| 未验证：MiniMax、`CLAUDE_CODE_MAX_OUTPUT_TOKENS` | 删 |
| 未验证：长时间限流、其它 `is_error` 子类型 | 留限流；子类型删（runner 已记原文） |
| 新增：pi / goose | 一节两三行：模型与凭据先在工具里配好（pi `/login`、`goose configure`）；pi 没有轮数与费用上限、只能靠 `timeout_sec`；goose 有轮数上限、没有费用上限；两者的费用都是客户端按价格表的估算 |

SKILL.md「技术事实」删掉第三方端点那条，代价那条保留并加上 pi / goose 的一句；`init` 一节与子命令表里的 `harness.env` 说法改成"模型与凭据在各工具里配"；`--harness` 的可选值加上 `pi|goose`。报告里费用的提示文案从"Claude Code 按 Anthropic 价格的估算"改为"harness 自己按价格表的估算，不是账单"。

## Risks / Trade-offs

- [pi / goose 的输出格式随版本变] → 解析函数只依赖 E2–E5 里的少数字段，找不到时 usage 留 null、不判失败；成败只看 E5 的两个信号。docstring 标明验证版本。
- [pi 没有轮数上限，一轮可能拖很久] → `timeout_sec` 杀整个进程组（现有机制）；init 的说明里写明 pi 只能靠它。
- [goose 截断后照常打分，看不出这一轮被截断] → 接受；note 里那句固定话术本身就进了账本和报告，人能看到。
- [用户在 shell 里 export 了 `ANTHROPIC_BASE_URL` 却只想用订阅] → 拒绝信息写明变量名，unset 即可；这是有意为之的硬拒绝。
- [删 `harness.env` 打断已有研究] → 未知键拒绝时附迁移提示（改 `type`、在工具里配 key）。本机只有本人在用。

## Migration Plan

1. 先归档 `autoresearch-mvp`（本 change 的 delta 修改它引入的 capability），再实现本 change。
2. 已有 `research.json`：删 `harness.env`；原来用 GLM 的改为 `"type": "pi"` 或 `"goose"`，并在工具里配好模型与 key。
3. 回滚：整个 change 在 `feat/autoresearch` 分支上，按 commit revert。
