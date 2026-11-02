# Tasks

> 顺序即依赖。1–3 不花模型费用；4 在 `/tmp` 一次性仓库 + herdr 里真跑（omp 用用户在 omp 里设的默认模型）；5 是文档与注册。所有改动在 feature 分支上，引擎只改 `dispatch/codex/scripts/` 再同步。

## 0. 前置

- [x] 0.1 从 main 拉 `feat/dispatch-omp` 分支，把本 change 目录作为首个 commit（`docs(openspec): propose dispatch-omp`）；验证：`git branch --show-current` 为 `feat/dispatch-omp`，`openspec validate dispatch-omp --strict` 通过

## 1. 引擎：pi 行换成 omp 行（spec `dispatch-executors`；design D1、D2、D4、D5）

- [x] 1.1 沙箱策略相关的函数与常量去掉 `pi_` 前缀（`guard_policy`、`guard_cache_dirs`、`GUARD_DIR`、`PUBLIC_REGISTRIES` 等），删除 `pi_goal_probe`、`pi_layout` / `pi_pane_state` / `pi_input_box`、`pi_startup_problem`、`pi_launch_flags`、`pi_label`、`PI_GOAL_EXTENSION` 与 `EXECUTORS["pi"]`；验证：`grep -n "pi_\|PI_\|\"pi\"" lane.py` 无命中（`openspec` 等无关词除外），`python3 -m py_compile` 通过；`compare` 脚本确认 codex 的启动参数与 prompt 文本仍逐字节不变
- [x] 1.2 `EXECUTORS["omp"]`：`launch_flags(strict, common, policy, goal_text)` 产出 design D2 的参数（含 `--approval-mode yolo`、白名单、`--no-pty --no-lsp`、`-e <GUARD_DIR> --lane-policy`、`--goal`）；新增 `goal_at_launch: True`，`launch` 成功即记 `goal_sent_at` / `goal_mode`，`prompt --goal|--plain` 对这类 lane 拒绝；`launch` 记下 omp 默认模型；`launch_gap: 0`、无 `startup_problem`；验证：对构造的 lane 调 `launch_flags` 得到预期 argv；对 `goal_at_launch` 的 lane 调 `prompt --goal` 返回"已下达"
- [x] 1.3 omp 的 goal 探针（design D4）：解析 `mode_change.data.goal` 与 `goal-completed`，跳过 null goal，连字符规范为下划线；verdict 增加 `goal_dropped`（与 `goal_paused` / `goal_budget_limited` 相同：上报、不恢复，上报后转为 `awaiting_user`）；验证：用 O5 形态构造的 JSONL 样例（只有 active；active→complete 后接 null 的 mode_change；只有 goal-completed；budget-limited；dropped；空文件；缺文件；格式异常行）得到 `active` / `complete` / `complete` / `budget_limited` / `dropped` / `unavailable` / `unavailable` / 不崩
- [x] 1.4 omp 的 `pane_state` / `input_box`（design D5）：先用 O12 已抓到的文本做样例（启动 banner + Working、工作中底栏转圈、空闲 `❯`、带标题的上边框、输入框有字）；`idle` / `done` 都视为不在工作；验证：样例分类为 `working` / `working` / `ready` / `ready` / `typed`，`input_box` 取出所发文字
- [x] 1.5 `record-verify` 的 `executor:` 行写 `omp <版本>` 并另起一行写模型；评审正文出处写 omp；验证：对 omp lane 生成的 `verify.md` 与评审正文里含 omp 版本与模型，除扩展名外不出现 `codex`、`pi`
- [x] 1.6 `doctor.sh`：`--executor pi` 换成 `--executor omp`（design D6），codex 分支输出不变；验证：本机 `--executor codex` 与改动前 diff 为空；`--executor omp` 报出 omp 版本、默认模型及其可用性、herdr omp 集成状态、仓库 skill 是否提交，`--executor pi` 返回用法错误
- [x] 1.7 `dispatch/sync-engine.sh` 目标改为 `dispatch/omp/scripts`，`git mv dispatch/pi dispatch/omp` 后同步引擎；验证：`dispatch/sync-engine.sh --check` 退出 0，`dispatch/pi/` 不存在

## 2. lane-guard（spec `dispatch-executors` 文件工具；design D3）

- [x] 2.1 `read` 的目标是 `协议://` 时只放行 `skill`，`www.` 开头一律 block，其余沿用现有路径规则；拒绝原因说明"只能读本 lane 内的普通路径与 skill"；验证：用模拟扩展接口的确定性测试覆盖 `https://example.com`、`http://x`、`www.example.com`、`ssh://h/p`、`proc://1`、`vault://k`、`mcp://s/t`、`local://x`、`file:///etc/hosts` 均 block，`skill://openspec-apply-change`、`openspec/changes/x/tasks.md` 放行，此前 13 个守卫用例仍全部通过

## 3. skill 与参考文档

- [x] 3.1 `dispatch/omp/SKILL.md`：由 pi 版改写，入口 `/dispatch:omp`，所有脚本调用带 `--executor omp`；派发流程去掉"逐个错开 / 无模型重启 / 单独下达 goal"，改为"launch 即下达 goal"；姿态句写明沙箱 + 守卫 + 工具白名单，以及 `--approval-mode yolo` 的含义；巡检表加 `goal_dropped`，去掉只属于 pi 的说明；codex 的 SKILL.md 把 pi 换成 omp、版本 0.3.0；验证：`python3 skill-craft/scripts/check.py dispatch/omp` 与 `dispatch/codex` 无 flags，两份 SKILL.md 里 grep 不到 `pi-codex-goal`、`/dispatch:pi`
- [x] 3.2 `dispatch/omp/references/setup.md`：安装 omp（bun）、`omp login` 与选默认模型由用户自己做、`herdr integration install omp` 由用户自己做、征得同意后 `npm ci` 装 lane-guard 依赖、`openspec init --tools oh-my-pi` 并提交；验证：按文档对本机逐项跑 doctor，每个缺失项都对得上文档里的命令
- [x] 3.3 `dispatch/omp/references/known-behaviors.md`：design 的 O1–O12 逐条带日期与版本；lane-guard 的沙箱事实（git 指针、包管理器、禁读、fail closed）从 pi 版移过来并注明当时测于 pi、本次在 omp 上复测的项；未验证项单列；验证：每条已验证事实都有日期与版本

## 4. 真跑验收（`/tmp` 一次性仓库 + herdr）

- [x] 4.1 omp 端到端：一个 2 task 的 change 按 `/dispatch:omp` 的流程走 `plan → create → launch（即下达 goal）→ list`，直到 `claims_done`，再 `record-verify` 与 `publish` 到本地 bare origin；验证：每 task 一个 commit，`list` 显示执行者 `omp`、goal `complete`，`verify.md` 写 omp 版本与模型；`~/.omp/agent` 下的 config 与 `omp plugin list` 前后一致
- [x] 4.2 边界探针（经 omp 的工具调用，以 JSON 事件流与文件系统为准）：worktree 内 commit、bash 写主 checkout、`write` / `edit` 越界、改写 `.git` 指针、`read` 读 `https://example.com` 与 `ssh://` / `proc://` 地址、`read` 读诱饵禁读目录、`npm install`；再在一个声明了 MCP server 的临时 omp 配置下启动，确认模型可用工具仍只有白名单那几个；验证：commit 与 `npm install` 成功，其余全部被拒且无文件变化、无网页内容进入事件流，MCP 工具不出现
- [ ] 4.3 界面与 `--strict`：抓下 omp 退出后、选择框（`--strict` 下越界写触发 lane-guard 询问）两种 pane 原文补进 `pane_state` 样例与 known-behaviors；验证：`list` 对等待询问的 lane 给出 `blocked`，多余回车只会拒绝，退出后的 lane 被识别为 `exited` / `no_agent`
- [ ] 4.4 混跑与 pi 退役：同一临时仓库一条 codex lane、一条 omp lane 跑完，再造一条记录为 `executor: pi` 的 lane；验证：两份引擎的 `list` 输出逐字相同，codex lane 走到 `claims_done`，pi lane 显示 `unknown_executor` 且巡检不向它发送任何输入
- [ ] 4.5 清理：先 `herdr worktree remove --force` 再删临时目录，删对应的 omp session 与本机记录，codex 配置若被写入信任条目则按备份删除；验证：`herdr workspace list` 无实验 workspace，`/tmp` 无实验目录，`~/.codex/config.toml` 与开始前一致

## 5. 注册与文档

- [ ] 5.1 `.claude-plugin/marketplace.json` 的 `dispatch` 插件 `./dispatch/pi` 换成 `./dispatch/omp` 并更新描述；`dispatch/README.md`、仓库 `README.md`、`CLAUDE.md` 把 pi 换成 omp（含依赖、姿态、工具白名单、`--approval-mode yolo` 的含义、pi 已退役）；`CHANGELOG.md` 记 **BREAKING**；`dispatch-executors` 主 spec 的 Purpose 改为 codex 或 omp；验证：`jq . .claude-plugin/marketplace.json` 通过，`grep -rn "dispatch:pi\|dispatch/pi" --include=*.md --include=*.json .` 只剩 CHANGELOG 与 openspec 归档，`openspec validate --all --strict` 通过
