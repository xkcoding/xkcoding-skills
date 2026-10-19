# Tasks

> 顺序即依赖。1 不花 LLM 费用；2 的单测用伪造的 stdout，不调模型；3 用本机 pi / goose 的系统配置（glm-5.3）真跑；4–5 是文档。所有改动在 `feat/autoresearch` 分支上。

## 0. 前置

- [x] 0.1 归档 `autoresearch-mvp`（`openspec archive autoresearch-mvp`），让 `autoresearch-harness` / `autoresearch-skill` 进入 `openspec/specs/`；验证：`openspec validate autoresearch-pi-goose-harness --strict` 通过

## 1. 删掉第三方端点与 `harness.env`（spec `autoresearch-harness` REMOVED / Claude Code adapter / Shell adapter）

- [x] 1.1 删 `harness.env`：`KNOWN_KEYS` 去掉 `env`，删除 `resolve_env` 及其在 `resolve_harness` / `preflight` / `cmd_doctor` / `unknown_window_warning` 的调用，`harness_env()` 只去掉父会话变量、不再合并 extra，`harness.meta.json` 去掉 `env_extra`；未知键拒绝 `env` 时附迁移提示（改 `type` 为 `pi` / `goose`、在工具里配 key）；验证：带 `"env": {}` 的 `research.json` 跑 `doctor` 得到含迁移提示的拒绝，四个示例 `example <name>` 后 `doctor` 均 `ok: true`
- [x] 1.2 删除 `MODEL_ALIASES`、`unknown_window_warning` 及 doctor 里的窗口告警；验证：`grep -n "unknown_window\|MODEL_ALIASES\|CLAUDE_CODE_MAX_CONTEXT" autoresearch/scripts/ar.py` 无结果
- [x] 1.3 `claude` subject 遇到环境里的 `ANTHROPIC_BASE_URL`：`preflight` 拒绝（指向 `pi` / `goose`），`doctor` 记 problem；验证：`ANTHROPIC_BASE_URL=x python3 ar.py run main --rounds 0` 在 kata 示例里拒绝且不产生 checkpoint，`doctor` 的 `problems` 含该变量名；unset 后 `run --rounds 0` 记下基线
- [x] 1.4 `shell` 不再走 `claude_result()`：`run_harness` 里 shell 只取 stdout 尾巴，`claude_result()` 去掉为 shell 写的 stream-json 说明（单行 JSON 与 result 行的读法对 claude 保留）；`_doc_type` / `_doc_command` 改为"不调模型的脚本或自定义执行器"；验证：`example toy` 跑 3 轮 outcome 与改动前一致；一个打印 Claude Code result 行的 shell 命令跑一轮，checkpoint 的 usage 全 null、note 是 stdout 尾巴

## 2. pi / goose adapter（spec `autoresearch-harness` Pi adapter / Goose adapter）

- [x] 2.1 `HARNESS_TYPES` 加 `pi` / `goose`；`resolve_harness`：`max_turns` 的默认 40 只给 `claude` / `goose`，pi 显式设 `max_turns` 或 `max_budget_usd`、goose 显式设 `max_budget_usd` 时拒绝并点名该键；`preflight` 与 doctor 的"CLI 在不在 PATH"检查覆盖四种模型 harness；验证：四种组合各写一个最小 `research.json`，`doctor` 的拒绝信息点名正确的键，pi 不写 `max_turns` 时不拒绝
- [x] 2.2 pi 命令拼装与 `pi_events()` 解析（design D3 / D4）：累加 assistant `message_end` 的 usage 与 cost，`turns` = assistant 消息数，`session_id` 取 `session.id`，最后一条 `stopReason: error` → failure 带 `errorMessage`；docstring 写明 E2–E5、E7 及验证版本 pi 1.3.0；验证：用 design 实测里那三种 stdout 形态（正常三条消息、退出 0 的 401、空输出）构造的样例跑解析函数，得到预期的 usage / failure
- [x] 2.3 goose 命令拼装与 `goose_output()` 解析：从第一个以 `{` 开头的行起解析，usage / cost 取 `metadata`，`status: error` 或非 0 退出 → failure，`--max-turns` 透传、截断不判 failure；docstring 写明 E2–E6 及验证版本 goose 1.55.0；验证：带横幅的正常输出、`status: error` + 退出 1、`--max-turns 1` 截断三种样例解析结果符合 spec
- [x] 2.4 `init --harness` 接受 `pi` / `goose`，pi 模板 `max_turns: null`；`_doc_type`、`_doc_max_turns`、`_doc_max_budget_usd` 写清各 harness 支持哪些上限，新增 `_doc_model`，写明 codex / pi / goose 不填即用工具自己配置的默认模型；doctor 的 `tools` 增加 `pi` / `goose`（执行 `--version`）；验证：空仓库 `init --harness pi` 后 `doctor` `ok: true`，`tools.pi.version` 为 `1.3.0`、`tools.goose.version` 含 `1.55.0`
- [x] 2.5 报告费用提示文案改为"harness 按自己价格表的估算，不是账单"；验证：`report` 生成的 HTML 里 grep 不到"Anthropic 价格"

## 3. 真跑验收

- [x] 3.1 `example kata` 两个 subject 改成 `"type": "pi"`（不配 `model`，用 pi 的系统默认 glm-5.3），`cases` 跑 2 轮、`impl` 跑 1 轮；验证：checkpoint 的 `harness.type` 为 `pi`、usage 四项与 cost 非 null、note 为最后一条 assistant 文本，`serve` 的报告能显示这几轮
- [x] 3.2 同样用 `"type": "goose"`，`max_turns: 40`，`cases` 跑 2 轮；验证同 3.1，另把 goose 的 config 临时换一个错 key 的 provider 跑 1 轮（或 `ZHIPU_API_KEY=bogus`），该轮 outcome 为 `error`、reason 含 401、工作树被还原
- [x] 3.3 pi 失败路径：`pi` 的 subject 跑一轮时让模型调用失败（`harness.model` 写一个该 provider 不存在的模型名，或临时 `--api-key` 不可行时改 `auth.json` 的副本），该轮 outcome 为 `error` 而不是按退出码 0 走 gate/score；验证：checkpoint 的 reason 含 pi 的 `errorMessage`

## 4. known-behaviors 与 SKILL.md（design D7）

- [x] 4.1 按 D7 的表改 `references/known-behaviors.md`：删第三方端点整节与过程数据，保留的条目各压成一行并保留日期与版本，新增 pi / goose 一节（配置入口、各自支持的上限、费用是估算）；验证：文件里 grep 不到 `GLM`、`ANTHROPIC_BASE_URL`、`stream-json`、`thinking_tokens`，每条都带 `(日期, 版本)`
- [x] 4.2 改 `SKILL.md`：子命令表 `--harness claude|codex|pi|goose|shell`、doctor 一行去掉 `harness.env`、init 第 6 步改成"模型与凭据在各工具里配"、技术事实删第三方端点条并在代价条加 pi / goose，References 索引里 known-behaviors 的加载时机去掉"第三方端点"；验证：`python3 skill-craft/scripts/check.py autoresearch` 无新增问题，`grep -n "harness.env\|GLM" autoresearch/SKILL.md` 无结果
- [x] 4.3 改仓库 `CLAUDE.md` 的 autoresearch 一节：harness 列表加 `pi` / `goose`，known-behaviors 描述去掉 GLM；验证：`grep -n "GLM" CLAUDE.md` 无结果

## 5. 收尾

- [x] 5.1 全量回归：四个示例各 `example` 一次后 `doctor` `ok: true`，toy 跑 5 轮 outcome 序列与改动前一致，`python3.9 -c "import ast; ast.parse(open('autoresearch/scripts/ar.py').read())"` 通过；验证：命令输出贴进本 change 的提交说明
