# Tasks

> 2026-09-18 重排：第一版按"3 个 skill + `_shared/` + 散文式流程"实现到一半，经用户评审（对照 web-access、baoyu-skills）推翻，改为"一个自包含 skill + 脚本干确定性的活"（design D12–D14）。下面是重排后的任务；已勾选的都在临时仓库里对真实的 herdr / codex / openspec 实测过。

## 1. 骨架与注册

- [x] 1.1 建立 `dispatch/codex/{scripts,references}`；验证：`find dispatch -type d` 只有这三个目录，没有 `_shared/` 或其它 skill 目录
- [x] 1.2 `dispatch/codex/SKILL.md` 的 frontmatter：`name: codex`，第三人称 description（做什么 + 何时用 + 中英触发词，≤ 1024 字符），`argument-hint`，`metadata.version`；验证：`yaml.safe_load` 能解析，description 长度在限内
- [x] 1.3 `.claude-plugin/marketplace.json` 新增插件 `dispatch`（`skills: ["./dispatch/codex"]`），`metadata.version` 提到 0.5.0；验证：`jq -e '.plugins[] | select(.name=="dispatch") | .skills == ["./dispatch/codex"]'` 为 true

## 2. 环境体检脚本（spec `dispatch-preflight`）

- [x] 2.1 `scripts/doctor.sh`：对 openspec / herdr / codex / git / jq / python3 / gh 实际执行 version 命令（不用 `command -v`），再报告登录状态、是否在 herdr pane、是否主 checkout、有无 `openspec/`、codex apply skill 是否已被 git 跟踪，输出 JSON；只用 bash 内建命令；验证：真实环境下 `jq -e '.tools.codex.version and (.env|has("in_herdr_pane"))'` 为 true；`PATH` 只含一个 exit 1 的假 `codex` 时仍输出合法 JSON 且 `codex.ok == false`

## 3. lane 的机械操作 `scripts/lane.py`（spec `dispatch-lane-launch` / `dispatch-supervision` / `dispatch-publish`）

- [x] 3.1 `plan`：准入判定（blocked 说出缺哪个 artifact、all_done、已有 lane、tracked 且有未提交修改 → 拒绝并给原因）、untracked / tracked 分类与 base ref、分支与 agent 名推导（整词截断、非字母开头加前缀、重名加后缀）、发布模式（pr / push-only / local-only + 原因）、缺验证方式的 task；从链接 worktree 发起则拒绝；验证：临时仓库里三种 change 状态 + 已有 lane 的分类全部正确，名字推导的四个用例正确
- [x] 3.2 `create`：fetch → `herdr worktree create` → 守卫（目标必须是刚建好的 worktree 且在预期分支上）→ untracked 的 change 搬入并以路径限定的 commit 成为首个 commit → 核对 base 未动；commit 失败时把 change 搬回主 checkout；验证：base 与 origin/base 的 HEAD 不变、change 只存在于 lane 分支、首个 commit 为 `docs(openspec): propose <c>`、重复 create 被拒、用会失败的 pre-commit hook 触发回滚后 change 回到主 checkout
- [x] 3.3 `launch`：按姿态拼参数（默认 `--approve-for-me`，`--strict` 显式 `--sandbox workspace-write`，两者都带 `--add-dir <主仓库 .git>`，永不 bypass）、由 worktree 反查 workspace 与 pane、读 pane 并判为 ready / dialog / working / exited；验证：真实启动得到 `dialog`（trust）与 `ready`（已受信任）；`pane_state` 对 spike 中捕获的 7 种屏幕文本（升级弹层、trust 弹层、空闲 composer、带 spinner 的 composer、工作中、退回 shell、回答里的编号列表）判别全部正确
- [x] 3.4 `prompt`：发送前确认"恰好一个 agent 的 cwd 是该 lane worktree"、agent 不在 `working`、pane 为 ready；`--goal` / `--plain` 一条 lane 只发一次（簿记记下发出时间，覆盖 herdr 尚未报告 session 的窗口）；`--continue` 记录 nudge；文本经 argv 传递不过 shell；验证：有弹层时拒发、lane 工作中拒发、goal 重发被拒（此项在实测中先失败过一次，修复后通过）、`--continue` 后簿记多一条 nudge 且 lane 完成
- [x] 3.5 `list`：由 `git worktree list` 反查 lane（`change/*` 分支且内含同名 change）、按 cwd 认领 agent、在 lane worktree 内取 n/m、只读探 codex goal 状态、算出 `verdict`；`--table` 每 lane 一行；验证：实测得到 `no_agent` / `working` / `claims_done` / `published` / `lane_pushed_itself`；删除簿记前后 `--table` 输出逐字一致
- [x] 3.6 `record-verify`：stdin JSON → `verify.md`（verified_commit、时间、执行者版本、姿态、逐项检查、偏离）并以路径限定的 commit 提交；任一项非 pass、tasks 未勾完、树不干净则拒绝；幂等；验证：上述情形实测，写入后 `openspec validate --strict` 仍通过
- [x] 3.7 `publish`：要求验证记录仍然有效（HEAD 是紧贴 verified_commit 的 verify.md commit）；越界检测；显式 refspec push、不 force；复用已有 PR；`gh pr create` 全参数显式 + body file，默认 draft；三种降级各带原因；三次失败后交还命令；验证：未验证时拒绝、本地 bare origin 下走 push-only 并打印 `gh pr create` 命令、origin 的 base 分支未动、手工把一条未验证的 lane 分支推上 origin 后被判为 `lane_pushed_itself`。**真实平台上的评审请求创建留到 7.2 / 7.3**
- [x] 3.8 `note`：记下 / 清除"已上报"；验证：escalate 后簿记出现 reason，clear 后消失

## 4. `SKILL.md` 与 references

- [x] 4.1 `SKILL.md`：定位、子命令表、前置检查（只检查不安装）、调度哲学（六条，每条带为什么）、脚本表；验证：顶部是"输入 → 做什么"的表；全文无指向 skill 目录之外的链接、无开发过程编号（`grep -E '\b[DFV][0-9]+\b|〔|design\.md'` 无结果）
- [x] 4.2 `SKILL.md` 的派发、巡检、验收与发布、交还给人四节；验证：`lane.py` 能产出的每一种 verdict 在巡检表里都有一行（脚本核对通过）；全文检索确认没有任何一处指示执行 merge / archive / worktree remove / 分支删除
- [x] 4.3 `SKILL.md` 的技术事实与 References 索引；验证：总长 < 300 行
- [x] 4.4 `references/setup.md`：逐项征得同意的安装表、只引导不代办的事项、版本差异、上手引导（日常流程 / 会话结束后如何恢复 / 怎么退出 / 零安装物声明）；验证：逐条对应 spec `dispatch-preflight` 前四条 Requirement 的每个 Scenario
- [x] 4.5 `references/known-behaviors.md`：每条带发现日期与版本，文末单列"没验证过的说法"；验证：已验证部分每条以 `(日期, 版本)` 开头

## 5. 文档登记

- [x] 5.1 `CLAUDE.md`（新增 skill 一节 + 品味标杆）、`README.md`（Skills 表、前置要求、插件表、仓库结构）、`CHANGELOG.md`（0.5.0）、`.gitignore`（Python 字节码）；验证：三处都出现 `dispatch:codex`，结构描述与实际目录一致
- [x] 5.2 `dispatch/README.md`：定位、与 herdr-dispatch 的区别、安装、前置条件、用法与 flag、姿态（含为什么没有 yolo）、永不做的事、磁盘上留下什么、已知限制、退出方式；验证：README 里每条命令都能在 SKILL.md 或 `lane.py` 的子命令里找到

## 6. 评审请求不绑定 GitHub（design D15）

- [x] 6.1 `lane.py`：从 `origin` 解析 host（ssh / https / 带端口 / 带凭证 / 本地路径），`github.com` → `gh`、host 含 `gitlab` → `glab`、其它 → 未定；`review_route` 给出 `review` / `handoff` / `undecided` / `push-only` / `local-only` 及原因；验证：7 种 URL 形态的 host 与猜测全部正确；在本仓库（GitHub）上只读探测得到 `review` + `gh` + 正确的 `owner/repo`
- [x] 6.2 `lane.py forge [--set gh|glab|handoff|none [--tool NAME]] [--forget]`：选择按 host 存入 `~/.claude/dispatch/forges.json`；`handoff` 必须带 `--tool`；验证：设置后 `plan` 的 `review` 变为 `handoff` 且 `remembered: true`，`--forget` 后回到 `undecided`，缺 `--tool` 被拒
- [x] 6.3 `publish` 拆成"push"与"开评审请求"：push 永远执行；`review` 模式下由脚本用 `gh` 或 `glab` 全参数显式地开（或复用已有的）；其余模式交出 `handoff`（remote_url / source_branch / target_branch / title / body_file / draft / tool）；正文先落成文件；`--via` 可单次覆盖；验证：handoff 模式下分支已推、base 未动、返回的交接包字段齐全且正文文件含来源说明；`glab` 未登录时降级为 push-only 并给出原因
- [x] 6.4 `note <change> review-url <url>` 与 `list` 的 REVIEW 列（gh / glab 查到的，或手工记回的）；验证：记回地址后 `list --table` 显示该 lane 为 `published` 且 REVIEW 列非空；非 URL 被拒
- [x] 6.5 `doctor.sh` 把 `glab` 列为可选工具；`SKILL.md` 新增「评审请求工具」一节并去掉正文里对 `gh` / PR 的绑定；`references/setup.md`、`references/known-behaviors.md`（`glab` 标明仅核对过 `--help`）、`dispatch/README.md`、`CLAUDE.md`、`CHANGELOG.md` 同步；spec `dispatch-publish` / `dispatch-preflight` 改为与平台无关的表述；验证：`SKILL.md` 仍 < 300 行、无指向目录外的链接；`openspec validate --strict` 通过

## 7. 端到端试运行（MVP 验收）

- [ ] 7.1 让插件在一个 Claude Code 会话里生效（`/plugin` 更新 marketplace 或 `claude --plugin-dir`），准备一个已 `openspec init --tools claude,codex`、`.agents/skills/` 已提交、带远端的试验仓库（GitHub / GitLab / 内部平台均可，首选你日常用的那个），propose 两个互不相干的小 change（各 2–3 个 task，每个 task 自带可机械执行的验证）；验证：`/dispatch:codex setup` 体检全绿，`lane.py plan` 对两个 change 均为 `eligible: true` 且 `review.mode` 为 `review` 或 `handoff`
- [ ] 7.2 在 herdr pane 内执行 `/dispatch:codex <change-a> <change-b>`，走完确认 → 两条 lane 并行 → 定时巡检 → 独立验收 → `verify.md` → push → draft 评审请求；验证：两个 draft 评审请求已打开，各自分支上有 propose commit、逐 task commit 与 `verify.md`；base 分支 HEAD 自始至终未变；主 checkout `git status` 干净
- [ ] 7.3 补测未覆盖的行为，结论回填 `references/known-behaviors.md`：`--strict` 下出现审批请求时的上报；往已发布 lane 的 `tasks.md` 加 task 后的返工路径（同一 PR 收到新 commit）；结束会话后在新会话用 `/dispatch:codex status` 恢复监督；一个耗时明显更长的 change 下 lane 的停顿 / 限流 / context 表现；自动审查拒绝一个请求时的表现；在一个 GitLab 仓库上走 `glab` 路径、在一个内部平台仓库上走 handoff 路径（由运行时里的 MR skill 开出评审请求并记回地址）；验证：「没验证过的说法」里这几项要么挪进已验证并标日期版本，要么写明为什么仍未能验证
- [ ] 7.4 验证退出成本：试验仓库里除 `change/*` 分支与 PR 外没有本插件留下的任何文件（`git ls-files` 无 dispatch 相关路径、`openspec/config.yaml` 未被改动）；取一条未完成的 lane，进入其 worktree 直接 `/opsx:apply` 能接着做；验证：两点均成立，并与 `dispatch/README.md`「退出方式」一致
