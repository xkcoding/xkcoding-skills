# Proposal

## Why

Auto Research / Loop Engineering 的承诺是"给 agent 一个长期目标，让它无人值守地多轮迭代"。Karpathy 的 autoresearch 把循环写在 `program.md` 里让 agent 自驱，只适合单文件、单指标、不需要停的场景：状态在对话上下文里、预算和停止条件靠模型自觉、打分器无法保护。Koala 俱乐部 2026-09-29 的视频（nano-grafana：自动移植 Grafana 渲染器）展示了一套在真实工程里跑通的极简框架——research ⊃ subject ⊃ round，git 当实验日志，账本放在仓库外，keep / discard / crash 三种结局，打分器带版本，harness 无状态、每轮一次调用——两个 subject 分别无人值守跑了 21 轮和 8 轮，报告里每轮的耗时、token、自述、缺口清单都可追溯。

本机没有任何可复用的实现。用户的第一个真实目标是优化 base-skills 里的 DRR skill（知识召回率、召准率、GT 资产选用率），但那个打分器是项目特有的；循环基建本身应当通用，先做基建，再接 DRR。

## What Changes

- 新增插件 `autoresearch`，含一个自包含的 skill `autoresearch`（带子命令）：`/autoresearch init | run | status | report | doctor`。
- 循环由脚本 `scripts/ar.py`（纯 Python 标准库，兼容 3.9）作为**外部进程**驱动，不依赖 Claude Code 会话：每轮组装 prompt → 拉起 harness → 边界检查 → gate → score → commit → keep / discard / crash → 写账本 → 判断停止。skill 只负责引导人写研究定义、启动循环、读报告。
- 目标仓库内新增定义目录 `autoresearch/`（`research.json` + `subjects/<name>/{program.md, score, gate}`），仓库旁新增账本目录 `<research>.ar/`（checkpoint 记录、每轮产物、报告）。仓库本身只多出 research 分支上的 commit。
- Research 是一等概念：一个 research 下挂多个 subject，subject 之间可声明依赖，一次只跑一个 subject，一份报告覆盖全部 subject。
- 打分器契约：任意可执行文件，输出 `{score, version, details, remaining[]}`；版本由打分器自报，只在同版本内比较；`remaining` 是喂给下一轮的缺口清单，也是 harness 无状态的依据。gate 与 score 分离，gate 失败即 crash、不打分。
- harness adapter 三种：`claude`（`claude -p`，第一版用 Claude Code 订阅登录）、`codex`（`codex exec`）、`shell`（任意命令，用于自测与自定义）。第三方模型（GLM、MiniMax 等 Anthropic 兼容端点）通过 harness 的 env 透传接入，列为后续任务。
- 静态报告生成器：从账本生成单文件 HTML，字段与视频报告对齐（状态、分数与版本、commit、各阶段耗时、token 四项、agent 自述、指标面板、缺口清单、按打分器版本分色带的曲线）。
- 自带一个两 subject 的示例研究（`examples/kata`，用例生成 → 实现，仿视频的 case-gen → render），用于验证机制和演示。
- 不改动本仓库现有 skill，不改 OpenSpec 配置。

## Capabilities

### New Capabilities

- `autoresearch-layout`：research / subject 的定义文件、`.ar` 账本目录、checkpoint 记录、打分器与 gate 的输入输出契约。
- `autoresearch-round-loop`：一轮的阶段顺序、三种结局与 git append-only 日志、基线、打分器版本、编辑边界、停止条件、中断与续跑。
- `autoresearch-harness`：harness adapter 的统一接口、三种实现、超时与用量采集、嵌套会话隔离、第三方端点接入。
- `autoresearch-report`：从账本生成的静态报告。
- `autoresearch-skill`：skill 子命令、`init` 脚手架、`doctor` 体检、人工介入（改打分器、改 program）的流程。

### Modified Capabilities

（无。`openspec/specs/` 目前为空。）

## Impact

- **新增目录**：`autoresearch/`（`SKILL.md` + `scripts/ar.py` + `references/` + `examples/kata/`）。
- **修改文件**：`.claude-plugin/marketplace.json`（注册插件 `autoresearch`）、`CLAUDE.md`、`README.md`、`CHANGELOG.md`。
- **运行时依赖**（用户机器）：python3 ≥ 3.9、git ≥ 2.23（`git worktree` / `revert`）、`claude` 或 `codex` CLI 之一。
- **对目标仓库的影响**：多一个 `autoresearch/` 定义目录（建议提交）、一条 `research/<name>` 分支及其上的 commit；仓库旁多一个 `<research>.ar/` 目录（不入库）。退出 = 删分支、删两个目录。
- **外部耦合**：`claude -p` 的 JSON 输出字段、`codex exec` 的 JSONL 事件、第三方端点的 env 约定都会随版本漂移；design 里的每条结论须标注验证所用版本。
