# Tasks

> 顺序即依赖。1–4 不花模型费用；5 在 `/tmp` 一次性仓库 + herdr 里真跑（pi 用本机默认模型，codex 用本机账号）。所有改动在 feature 分支上。

## 0. 前置

- [x] 0.1 从 main 拉 `feat/dispatch-pi` 分支，把本 change 目录作为首个 commit（`docs(openspec): propose dispatch-pi`）；验证：`git branch --show-current` 为 `feat/dispatch-pi`，`openspec validate dispatch-pi --strict` 通过

## 1. 引擎改为执行者无关（spec `dispatch-executors`；codex 行为不变）

- [x] 1.1 在 `dispatch/codex/scripts/lane.py` 引入 `EXECUTORS` 适配表（design D1），把 codex 的 launch 参数、goal / continue / correct / resume 文本、`goal_probe`、`pane_state`、"已下达 goal"的证据、版本命令、verify / 评审出处文案搬进 `codex` 一行，其余代码只经表访问；验证：`python3 -m py_compile` 通过，`grep -n '"codex"\|codex' lane.py` 的命中只在适配表、docstring 与注释里；对同一 lane 构造的 codex `herdr agent start` argv 与改动前逐项相同
- [ ] 1.2 执行者成为 lane 属性（design D2）：`plan` / `create` / `launch` 接受 `--executor codex|pi`，`launch` 写入 bookkeeping；`list` 按 herdr agent 类型 → bookkeeping → `unknown` 推出执行者，`unknown` 的 lane verdict 不进入任何会发送输入的分支；`list --table` 增加执行者列；`plan` 对已有 lane 的 change 返回该 lane 的执行者；验证：临时仓库里 `create` 一条 lane 不启动 agent，`list` 显示 `unknown`；写入 bookkeeping 的 `executor: pi` 后显示 `pi`；删掉该字段、旧格式 bookkeeping 下 herdr 报 codex 的 lane 显示 `codex`
- [ ] 1.3 `record-verify` 的 `executor:` 行与 `publish` 正文出处行取自该 lane 的执行者（design D8）；验证：对 pi lane 生成的 `verify.md` 与评审正文文件 grep 不到 `codex`，含 pi 与 pi-codex-goal 的版本
- [x] 1.4 `doctor.sh` 增加 `--executor codex|pi`（design D7），codex 分支输出与改动前字段一致；pi 分支检测 pi、node ≥ 24、rg、skill 目录内 sandbox-runtime 版本、`pi auth check --no-refresh`（不带 `--credentials`）、Linux 的 bwrap / socat、目标仓库已提交的 `.pi/skills` 或 `.agents/skills` 里的 apply skill；验证：本机 `--executor codex` 的 JSON 与改动前 diff 只多 `executor` 字段；`--executor pi` 在未装 sandbox 依赖时 `required_tools` 里该项 `ok:false`，不报 codex 缺失
- [x] 1.5 新增 `dispatch/sync-engine.sh`：以 `dispatch/codex/scripts/{lane.py,doctor.sh}` 为源复制到 `dispatch/pi/scripts/`，`--check` 比对、不同则非零退出并列出文件；验证：复制后 `--check` 退出 0；改 pi 副本一个字节后 `--check` 退出非 0 并点名 `lane.py`

## 2. pi 适配行（spec `dispatch-executors`、`dispatch-lane-launch`、`dispatch-supervision`）

- [ ] 2.1 pi 的 launch（design D3）：参数 `-e <skill>/scripts/lane-guard -e npm:pi-codex-goal@0.6.1 --approve --no-mcp --tui-mode regular --lane-policy <file>`；`launch` 先生成策略文件到 `~/.claude/dispatch/<repo-id>/<change>-policy.json`（allowWrite = worktree + git common dir，denyWrite = 其下 `hooks` / `config`，denyRead = `~/.ssh` / `~/.aws` / `~/.gnupg`，allowedDomains = 公共源 + `npm config get registry` / `pip config get global.index-url` 的 host，posture）；验证：临时仓库里对一条 lane 运行 `launch --executor pi`，策略文件内容与上述一致且路径已做 realpath，pane 底栏出现 lane-guard 的就绪提示
- [ ] 2.2 pi 的 `goal_probe`（design D5）：从 herdr 报的 session 路径倒序取最后一条 `customType == "pi-codex-goal"` 且带 `status` 的记录，连字符规范为下划线；文件不存在或无记录时返回 `unavailable`；验证：用实测形态构造的 JSONL 样例（只有 `usage/active`；末条 `set/complete`；含 `budget-limited`；空文件）分别得到 `active` / `complete` / `budget_limited` / `unavailable`
- [ ] 2.3 pi 的 `pane_state`（design D6、P7）：`Working` 分隔行 → `working`；`To resume this session` 或无 pi 底栏的 shell → `exited`；空输入框 + 底栏 → `ready`；其余 → `unknown`；changelog 与 Update Available 横幅不影响判断；验证：用实测抓到的四段 pane 文本（启动就绪含 changelog、工作中、goal 完成空闲、退出后）做样例，分类结果正确
- [ ] 2.4 pi 的"已下达 goal"证据与提交确认（design D5、D6）：pi 不以 session 存在为证据；`launch` 后等到 `ready` 才允许 `prompt`；`prompt` 后约 15 秒内未进入 `working` 且输入框仍是所发文字 → `send-keys enter` 一次，仍不动则 `ok:false` 附 pane 尾部；`done` 与 `idle` 都视为不在工作；验证：临时仓库里对刚启动的 pi lane 立即 `prompt --goal`，lane 进入工作且 session 里只有一条 goal `set` 记录；对已下达 goal 的 lane 再发 `--goal` 被拒
- [ ] 2.5 pi 的启动间隔与锁冲突重试（design D9）：适配表加 `launch_gap`（pi 4 秒、codex 0），`launch` 遇到 `exited` 且 pane 尾部是配置锁冲突时等 `launch_gap` 重启一次并在结果里带 `retried`，其它退出不重试；`SKILL.md` 的派发步骤写明 pi lane 逐个 launch、goal 之间同样间隔；验证：用 5.5 抓到的锁冲突 pane 文本与一段普通启动报错做样例，前者判为可重试、后者不重试

## 3. lane-guard 扩展（spec `dispatch-executors` 沙箱 / 文件工具 / MCP / 不改用户配置）

- [ ] 3.1 `dispatch/pi/scripts/lane-guard/package.json` 钉死 `@anthropic-ai/sandbox-runtime@0.0.26`、`pi.extensions` 指向 `index.ts`；`index.ts` 注册 `--lane-policy`，只从该文件读策略，替换 `bash` 并接管 `user_bash`，策略缺失 / 解析失败 / 初始化失败时 bash 一律返回错误（fail closed）；验证：`PI_OFFLINE=1 pi --no-extensions -e <dir> --help` 退出 0 且帮助里有 `--lane-policy`；`npm install` 后 `node_modules/` 不进 git（`git status` 干净）
- [ ] 3.2 同一扩展里的 `tool_call` 守卫：`write` / `edit` 目标先 realpath 最近的已存在祖先再比对，可写根与 `denyWrite` 与沙箱同源；默认姿态 `block` 带原因，`posture: strict` 时用 `ctx.ui.confirm` 询问；验证：在 5.2 的真跑里一并验收（本任务完成标志为代码与 3.1 的加载检查通过）

## 4. skill、文档与注册

- [ ] 4.1 新建 `dispatch/pi/SKILL.md`：结构对齐 `dispatch/codex/SKILL.md`，入口 `/dispatch:pi`，所有脚本调用带 `--executor pi`，姿态句、启动期处理、goal 下达、技术事实按 pi 写，写明 `status` 覆盖全部 lane；codex 的 SKILL.md 补"巡检覆盖两种执行者、执行者列"；验证：`python3 skill-craft/scripts/check.py dispatch/pi` 与 `dispatch/codex` 无 error
- [ ] 4.2 `dispatch/pi/references/setup.md`：安装 pi、Node ≥ 24、ripgrep、Linux 的 bwrap / socat，征得同意后在 skill 目录 `npm install`，pi 登录由用户自己做，`openspec init --tools pi` 并提交；验证：按文档在本机逐项执行 `/dispatch:pi setup` 的检测，每个缺失项都给出文档里的那条命令
- [ ] 4.3 `dispatch/pi/references/known-behaviors.md`：design 的 P1–P15 逐条带日期与版本；未验证项单列（`paused` / `blocked` / `waiting` / `budget_limited` 的真实出现、`--strict` 确认框样子、`--offline` 行为、长任务 compaction）；验证：每条已验证事实都有日期与版本号
- [ ] 4.4 `.claude-plugin/marketplace.json` 的 `dispatch` 插件 `skills` 加 `./dispatch/pi` 并更新描述；`dispatch/README.md`（执行者两种、前置条件按执行者、pi 姿态、`sync-engine.sh`）；仓库 `CLAUDE.md` 增加 `dispatch:pi` 一节与"改引擎后跑 `sync-engine.sh`"的开发规范；`CHANGELOG.md`；`dispatch/codex` 版本 0.2.0、`dispatch/pi` 0.1.0；验证：`jq . .claude-plugin/marketplace.json` 解析通过，`dispatch/sync-engine.sh --check` 退出 0

## 5. 真跑验收（`/tmp` 一次性仓库 + herdr）

- [ ] 5.1 pi 端到端：一个 2 task 的 change 按 `/dispatch:pi` 的流程走 `plan → create → launch → prompt --goal → list`，直到 `claims_done`，再 `record-verify` 与 `publish --no-pr`；验证：每 task 一个 commit，`list` 显示执行者 `pi`、goal `complete`，`verify.md` 的 executor 行为 pi，用户的 `~/.pi/agent/settings.json` 与 `trust.json` 前后一致
- [ ] 5.2 pi lane 的边界探针：在 lane 里让 pi 依次做 worktree 内 commit、bash 写主 checkout、bash 写 `.git/hooks`、`write` 写主 checkout、`edit` 改 `.git/config`、经 `/tmp` 别名写 worktree、curl 未放行域名、npm 源可达；再把策略文件改坏重启 lane 让 pi 跑任意 bash；验证：commit / 别名写入 / npm 源成功，其余全部被拒且无文件变化，改坏策略后 bash 被拒并给出原因
- [ ] 5.3 `--strict` 的 pi lane：诱发一次越界 `write`，抓取确认框的 pane 文本，据此补 `pane_state` 的 `dialog` 规则并写进 known-behaviors；验证：补规则后 `list` 对该 lane 给出 `blocked`，lane 在人工拒绝后继续工作
- [ ] 5.4 混跑：同一临时仓库一条 codex lane、一条 pi lane 同时跑完；验证：分别从 `dispatch/codex/scripts/lane.py` 与 `dispatch/pi/scripts/lane.py` 执行 `list`，两份输出逐字相同；codex lane 的 verdict 序列与改动前一致（goal 走到 `complete`、`claims_done`）
- [ ] 5.5 配置锁冲突：在一个临时的 `PI_CODING_AGENT_DIR`（空的 `auth.json`，不复制任何凭据）里预先占住 `auth.json.lock`，启动 pi 抓下退出时的 pane 原文，写进 known-behaviors 并据此定下 2.5 的匹配规则；再在真实配置下一次派发 4 条 pi lane；验证：锁被占时 pi 退出且原文含锁相关报错；4 条 lane 全部到 `ready`、各自完成 goal，`list` 中无 `no_agent`
- [ ] 5.6 清理：先 `herdr worktree remove --force`（或关闭 workspace）再删临时目录，删对应的 pi session；验证：`herdr workspace list` 无实验 workspace，`/tmp` 无实验目录
