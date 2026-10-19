# Proposal

## Why

autoresearch 目前用 Claude Code 接第三方模型（`claude` harness + `harness.env` 里的 `ANTHROPIC_BASE_URL` 指向 GLM 等兼容端点），这种用法会被 Claude Code 判定为在蒸馏模型，不能再支持。第三方模型需要换一条不经过 Claude Code 的路：pi 与 goose 都是能无人值守跑一轮的 coding agent CLI，原生支持 GLM，2026-10-19 在本机实跑通过。

顺带把 `known-behaviors.md` 里只服务于 runner 解析、或只是过程数据的条目清出去：会话用不上的事实不该占 skill 的上下文。

## What Changes

- 新增 `pi` harness：`pi --mode json --no-session`，关闭全局 skill / extension / prompt template 的加载，模型与凭据用 pi 自己的配置（`~/.pi/agent/`）。
- 新增 `goose` harness：`goose run --output-format json --no-session --no-profile --with-builtin developer`，模型与凭据用 goose 自己的配置（`~/.config/goose/config.yaml`）。
- **BREAKING** 删除 `harness.env`：runner 不再管凭据与端点，每个工具用自己的系统配置。旧定义里的 `harness.env` 会被未知键检查拒绝，提示去配工具自己的 config。
- **BREAKING** `claude` harness 只接 Anthropic：runner 自身环境里有 `ANTHROPIC_BASE_URL` 时，`claude` subject 拒绝启动并指向 `pi` / `goose`。删除端点模型的窗口告警（`unknown_window_warning`）。
- `shell` harness 保留，定位收窄为不调模型的脚本（`examples/toy`）与自定义执行器；不再把 stdout 当 Claude Code 的 JSON 解析。
- `init --harness` 与 `doctor` 认识 `pi` / `goose`：doctor 执行它们的版本命令，只报告不安装、不登录。
- 清理 `references/known-behaviors.md`：删除"第三方 Anthropic 兼容端点"整节；只给 runner 用的解析事实挪进 `ar.py` 对应 adapter 的注释；过程数据（单轮耗时、费用曲线、事件流体积）删除；只保留会改变会话做法的条目。SKILL.md「技术事实」同步收敛。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `autoresearch-harness`：新增 pi / goose adapter；删除环境透传要求；`claude` adapter 拒绝第三方端点；`shell` adapter 不再解析 Claude Code JSON。
- `autoresearch-skill`：`doctor` 检测 pi / goose、去掉端点窗口告警；`init --harness` 接受 `pi` / `goose`。

注：这两个 capability 由 `autoresearch-mvp` 引入，该 change 已完成但未归档，`openspec/specs/` 下还没有它们。归档顺序必须是先 `autoresearch-mvp`，再本 change。

## Impact

- 代码：`autoresearch/scripts/ar.py`（`HARNESS_TYPES`、`resolve_harness`、`run_harness`、新增两个事件解析函数、删除 `resolve_env` / `unknown_window_warning` / `MODEL_ALIASES`、doctor、init 模板的 `_doc_*`）。
- 文档：`autoresearch/SKILL.md`、`autoresearch/references/known-behaviors.md`、仓库 `CLAUDE.md` 里 autoresearch 一节的 harness 列表。
- 示例：四个示例都不用 `harness.env`，不受影响；`toy` 继续用 `shell`。
- 依赖：运行时多两个可选 CLI（pi ≥ 1.3.0，npm `@earendil-works/pi-coding-agent`；goose ≥ 1.55.0，Homebrew `block-goose-cli`），各自需事先配好模型与凭据。
- 已有研究：用 `harness.env` 接 GLM 的 `research.json` 需改为 `"type": "pi"` 或 `"goose"` 并删掉 `env`。
