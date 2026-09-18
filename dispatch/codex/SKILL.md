---
name: codex
description: >-
  Dispatches already-proposed OpenSpec changes to codex — one herdr worktree lane per change, each running the standard OpenSpec apply — then supervises the lanes, independently verifies finished work, pushes the branch and opens a draft review request (GitHub PR via gh, GitLab MR via glab, or an internal forge through whatever MR tool or skill the runtime has). OpenSpec's tasks.md is the only progress record.
  Use when the user asks to dispatch / 派发 / 外包 / hand off an OpenSpec change to codex, wants several changes applied in parallel worktrees, asks how the dispatched lanes are doing, or invokes /dispatch:codex with or without its status / setup sub-commands. Requires Claude Code running inside a herdr pane.
argument-hint: '[<change> …] [--strict] [--ready] [--no-pr] [--no-loop] | status | setup'
metadata:
  author: xkcoding
  version: "0.1.0"
---

# /dispatch:codex

把已经 propose 好的 OpenSpec change 交给 codex 去做：每个 change 一条 lane——一个独立的 git worktree、一个分支、一个 codex——lane 里跑的就是标准的 OpenSpec apply。你是**调度者**：不写一行实现，只负责派发、盯进度、亲手验收、把验证过的分支 push 出去并开评审请求（PR / MR）。

`/opsx:apply` = 我在这里做；`/dispatch:codex` = 派给 codex 做。同一个仓库里每个 change 各选各的。

用用户的语言回复；commit、评审请求用英文。

## 子命令

| 输入 | 做什么 |
|---|---|
| `<change> [<change> …]` | 派发这些 change → [派发](#派发) |
| 不带 change 名 | 列出可派发的 change 让用户选，然后派发 |
| `status` | 对所有 lane 巡检一次 → [巡检](#巡检) |
| `setup` | 环境检测、征得同意后协助安装、上手引导 → 读 `references/setup.md` |

派发可带：`--strict`（越出沙箱的操作等用户批准，见下）、`--ready`（评审请求直接开成 ready，默认 draft）、`--no-pr`（只 push，不开评审请求）、`--no-loop`（不武装定时巡检）。

用户要求"绕过审批 / 沙箱 / yolo"：说明这里不提供——默认姿态已经不需要人盯着批准，同时保留沙箱。

## 前置检查

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/doctor.sh"
```

只读，输出一份 JSON。它对每个工具**实际执行** version 命令——`PATH` 上存在但跑不起来的 shim 也算缺失。

- `required_tools` 里有 `ok: false`、不在 herdr pane 里、不在 git 主 checkout、仓库没有 `openspec/`、没有**已提交**的 `.agents/skills/openspec-apply-change/`、codex 未登录 → 停下，说清缺什么，请用户运行 `/dispatch:codex setup`。**派发和巡检路径上不安装、不登录、不初始化任何东西。**
- `gh` / `glab` 缺失或未登录不算停：它们只管"开评审请求"，push 不需要它们。具体会怎样由 `plan` 返回的 `review` 决定，在确认页里提前说明。
- 工具版本与 `verified_against` 不同：报告一行，继续。

## 调度哲学

**进度只有一份真相，在 OpenSpec 里。** 计划是 change 的 artifact，进度是 lane 里那份 `tasks.md`，完成声明是 `state: all_done`。不另建任何进度文件。每次巡检都从 git、herdr、openspec 现查，不依赖对话记忆，也不依赖上一个会话——所以读进度永远在 lane 的 worktree 里读，主 checkout 里的同名 change 可能是一份永远不会被勾选的旧副本。

**声明不是结论。** lane 说做完了、goal 状态是 `complete`、屏幕上写着 "Goal achieved"、herdr 报 `done`——都只是"该去验收了"的信号。验收由你在 lane 的 worktree 里亲手重跑。同理，一次调用没有正常返回，不代表 lane 没收到：被中断的 prompt 多半已经送达，先看 lane 实际怎样了再决定下一步。

**先看再动。** 往 lane 发任何东西之前先看它的 pane。有选择列表停在那里时什么都不发——此时提交的文字会按下它高亮的默认项，而 codex 升级弹层的默认项是"立即升级"。弹层永远选那个"对用户机器无改动、不写入任何偏好"的选项；会写入设置的（比如目录 trust）先问用户；认不出来的弹层，把原文交给用户。

**只碰自己的，只做可逆的。** 只操纵工作目录就是某条 lane worktree 的那个 agent；永不 `focus`（会抢用户的焦点），永不 `herdr server stop`。永不 commit 或 push base 分支；永不 force-push；永不 merge、archive、删 worktree、删分支——这些命令最后打印给用户，由人来跑。

**codex 的自动审查不替你守流程。** 它拦的是破坏性操作和数据外泄，对"lane push 自己的 feature 分支"是放行的。所以"lane 不 push"靠两件事：goal 里写明了，以及发布前检查 origin 上是不是已经有了这条分支。

**拿不准就交给人。** lane 在提问、在等审批、goal 被人暂停、同一个 worktree 里有两个 agent——把原话报给用户，不要替他回答。

## 脚本

机械、易错的操作都在 `lane.py` 里，不要手工重做它们（手工搬目录、拼 refspec、转义 `$openspec-…` 都出过事）。每个子命令打印**一个** JSON；`"ok": false` 时 `error` 写着它为什么拒绝——拒绝是信息，不是要绕过的障碍。

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" <子命令> …
```

| 子命令 | 作用 |
|---|---|
| `plan [<change> …] [--no-pr]` | 只读。哪些 change 可派发、不可派发的原因、推导出的分支 / worktree / agent 名、base、发布能做到哪一步 |
| `create <change>` | 建 worktree 与 `change/<change>` 分支；change 还没提交时，把它搬进 worktree 成为该分支的首个 commit。base 分支不会被动 |
| `launch <change> [--strict]` | 在 lane 的 pane 里启动 codex；返回 `state`：`ready` / `dialog` / `exited` / `unknown`，附 `pane_tail` |
| `prompt <change> --goal \| --plain \| --continue \| --resume \| --correct "<text>"` | 发一条 prompt。发之前自动确认身份、确认 lane 空闲、确认没有弹层；goal 只会发出一次 |
| `list [--table]` | 所有 lane 的总览与 `verdict`。`--table` 每条 lane 一行，给人看 |
| `record-verify <change>` | 从 stdin 的 JSON 写 `verify.md` 并提交到 lane 分支 |
| `publish <change> --title "<t>" [--body-file F] [--ready] [--no-pr] [--via gh\|glab\|handoff] [--ack-remote]` | 检查越界 push → 显式 refspec push → 能自己开评审请求就开（或复用已有的），否则交出 `handoff` |
| `forge [--set gh\|glab\|handoff\|none [--tool NAME]] [--forget]` | 这个远端的 host 用什么开评审请求；选择按 host 记住 |
| `note <change> escalate "<reason>" \| clear \| review-url <url>` | 记下 / 清除"已上报给用户"；记下别的工具开出来的评审请求地址 |

## 评审请求工具

push 是纯 git，任何托管都一样；**只有"开评审请求"取决于代码放在哪**。不要假设是 GitHub。`plan` 返回的 `review.mode` 说明这个仓库会怎么走：

| `review.mode` | 含义 | 发布时 |
|---|---|---|
| `review` | host 是 GitHub → `gh`，或 GitLab → `glab`，且该 CLI 已登录 | `publish` 自己开（全参数显式，不会卡在交互提问上） |
| `handoff` | 用户为这个 host 指定了运行时里的某个工具或 skill（记在 `review.tool`） | `publish` 只 push，并返回 `handoff`：`remote_url` / `source_branch` / `target_branch` / `title` / `body_file` / `draft`。用那个工具开——是 skill 就用 `Skill` 调用它，把这几样交给它；拿到地址后 `note <change> review-url <url>` |
| `undecided` | 认不出的 host，也没有记住过选择 | 在派发的确认页里**一并问用户一次**：`gh` / `glab` / 运行时里现有的某个 MR 工具或 skill（看看可用的 skill 列表里有没有对得上这个 host 的）/ 不开。然后 `forge --set …` 记住，同一个 host 以后不再问 |
| `push-only` / `local-only` | 做不到，`reason` 里写着为什么 | 如实告诉用户，不硬开 |

评审请求的正文永远先落成文件（`handoff.body_file`），再交给任何工具——换工具不用重写，也留了一份记录。具体的 `gh` / `glab` / 某个 skill 只是例子；运行时里有别的等价工具，按同样的规则用。

## 派发

1. **计划。** `plan <change…>`。不可派发的 change 把 `reason` 原样告诉用户，其余照常继续；`tasks_without_verification` 非空时提醒用户：这些 task 没写怎么验证，验收时只能靠读 diff。
2. **确认一次。** 展示每个 change 的分支、worktree、剩余 task 数、change 目录状态（`untracked` → 会成为 lane 分支的首个 commit；`tracked` → 从当前 HEAD 拉分支），再加三句话：
   - 姿态——默认：`codex 自动审查 + 沙箱：越出沙箱的操作由 codex 的审查模型自动判定，不会停下来等你`；`--strict`：`沙箱 + 按需审批：越界操作停下来等你批准，我只转达、不代答，lane 会因此停顿`。
   - 做完之后——按 `plan` 返回的 `review` 如实说：我亲手重跑验收、写 `verify.md`、push，然后对 `<pr_base>` 开 draft 评审请求（写明用什么开：`gh` / `glab` / `review.tool`）；`push-only` / `local-only` 连同 `reason` 一起说明；`undecided` 就在这里把[评审请求工具](#评审请求工具)那个问题一并问掉。不承诺做不到的事。
   - 永远不会发生的事：不动 `<pr_base>`；不 merge、不 archive、不删 worktree。
   lane 超过 4 条时提醒：所有 lane 共用一个 codex 账号，限流是共享的。用 `AskUserQuestion` 问一次：`按此派发` / `改用 --strict` / `取消`。**得到回答之前不创建任何东西。**
3. **逐个 `create`。** 一条失败就记下原因，继续下一条——一条 lane 失败不中止整次派发，也不要去删它已经建好的东西。记下每次返回的 `new_workspaces`：同一仓库第一次派发时 herdr 会多开一个对应主仓库本身的 workspace，它不属于任何 lane，报告里告诉用户可以自行关闭。
4. **逐个 `launch`，全部启动完再下达 goal。** 按 `state` 处理：
   - `ready` → 下一步。
   - `dialog` → 读 `pane_tail`，按「先看再动」处理，然后重新看 pane，直到出现 composer。已知的两个：升级提示 → `herdr agent send-keys <agent_name> 2`（Skip；不选"立即升级"，也不选会写入偏好的"跳过到下个版本"）；目录 trust → 先问用户（接受会把主仓库根写进用户的 codex 配置，对该仓库今后所有 worktree 生效），同意则 `send-keys <agent_name> enter`。
   - `exited` → codex 启动后就退出了，不是"慢"。`pane_tail` 里有真正的报错；把它记为这条 lane 的失败原因，不要原样重试。
5. **逐个 `prompt <change> --goal`。** goal 文本由脚本持有（含 lane 的全部边界）。codex 拒绝 `/goal` 时改用 `--plain`，并告诉用户这条 lane 每个 turn 结束都会停、要靠巡检续跑。
6. **收尾。** 立刻巡检一次；除非 `--no-loop`，用 `Skill` 调用 `loop`，参数 `5m /dispatch:codex status`，告诉用户怎么停。最后报告：每条 lane 的分支 / worktree / 姿态 / 启动结果，多出来的 workspace，版本差异，以及"会话结束后 lane 会继续跑，回来执行 `/dispatch:codex status` 即恢复监督"。

## 巡检

`list`（给用户看用 `--table`），然后按每条 lane 的 `verdict` 处理。无变化的 lane 不要去读 pane——巡检会跑很多次，省着用上下文。

| verdict | 做什么 |
|---|---|
| `working` | 不打扰 |
| `claims_done` | [验收与发布](#验收与发布) |
| `verified_unpublished` | 直接 `publish`（上次发布没成） |
| `published` | 只报告 |
| `idle_unfinished` | 先读 pane。lane 在提问或报告阻塞 → 把原话交给用户并 `note … escalate`，不续跑。只是停了 → `prompt --continue`。`nudges_without_progress` ≥ 2 → 不再续跑，上报 |
| `blocked` | 读 pane，把请求原文交给用户。**不代答审批。** 启动期那类弹层按「先看再动」处理 |
| `goal_usage_limited` | 账号限流。`prompt --resume`，每次巡检最多一次；下次巡检再看 |
| `goal_paused` / `goal_blocked` / `goal_budget_limited` | 上报，不恢复：暂停多半是用户自己按的；`blocked` 是 codex 连续多个 turn 确认过的阻塞 |
| `lane_pushed_itself` | lane 越界了。上报；用户明确接受之后才 `publish --ack-remote` |
| `no_agent` | 刚 `create` 完还没启动 → `launch`。否则 codex 已退出 → 上报，由用户决定重新派发还是进 worktree 原地 `/opsx:apply` |
| `ambiguous_agent` | 同一个 worktree 里不止一个 agent。不碰，上报 |
| `awaiting_user` | 已上报过，一行带过；用户答复后 `note … clear` |
| `herdr_unreachable` | herdr 连不上（多半是当前会话不在 herdr pane 里）。进度照常报告，但不操纵任何 lane；请用户回到 herdr pane 里再执行 |

`all_settled` 为 true 时停掉定时巡检，说明每条 lane 在等什么。当前会话没有武装定时、又还有未了结的 lane 时，重新武装。

## 验收与发布

在 lane 的 worktree 里（不是主 checkout）：

1. 逐个 task 重跑它自己写明的验证方式；没写的，读 `git diff <base>..HEAD` 对照 spec 判断，并在 evidence 里写明"无机械检查，依据 diff 判断"。
2. `openspec validate <change> --strict`。
3. 看一眼 commit：是否每个 task 一个、有没有夹带无关改动。粒度粗只记一笔，不要求 lane 改写历史。
4. 任何一项不过 → `prompt <change> --correct "<哪条检查、输出是什么>"`，lane 保持打开，什么都不 push。
5. 全过 → 把结果喂给 `record-verify`：

```bash
echo '{"tasks":[{"id":"1.1","check":"<命令或判断依据>","result":"pass","evidence":"<输出摘要>"}],"deviations":["<lane 在 commit 信息里记的偏离；没有就留空数组>"]}' \
  | python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" record-verify <change>
```

6. `publish <change> --title "<type>(<scope>): <summary>"`。标题用 Conventional Commits，不放 lane 名或分支名。想给 reviewer 一段比 `verify.md` 更好读的摘要，就写进文件用 `--body-file` 传入；其中必须说明代码由 codex 编写、在什么姿态下运行。返回里带 `handoff` 的，按[评审请求工具](#评审请求工具)用对应的工具开，再 `note <change> review-url <url>`。
7. push 被拒（non-fast-forward）→ 停下上报，**不 force**。

返工不需要新机制：reviewer 要改什么，就往 lane 的 `tasks.md` 里加 task 或取消勾选——下次巡检它自然变回 `idle_unfinished`，做完后重新验收，同一个评审请求收到新 commit。

## 交还给人

全部 lane 了结后，打印（**不执行**）后续命令，按这个顺序——git 拒绝删除仍被 worktree 检出的分支，所以清理在前：

```bash
herdr worktree remove --workspace <ws>      # 会杀掉其中的 codex，并丢弃该 checkout 里未提交的改动
gh pr merge <number> --squash --delete-branch   # GitLab: glab mr merge <iid>；其它平台：在它的页面上合并
/opsx:archive <change>                      # 时点随项目惯例；OpenSpec 官方推荐在合并之后
```

用户让你 archive：不做，指给他项目自己的 `/opsx:archive`。

## 技术事实

下面是 2026-09 在 herdr 0.9.0、codex 0.154–0.155、openspec 1.13.1 上实测到的。当作提示而不是保证：行为不符时以眼前的 pane 为准，并更新 `references/known-behaviors.md`。

- herdr 的 `agent_status` 不可靠：同一时刻三条都已完成的 lane 分别读出 `done`、`idle`、`working`。它只是辅助信号。
- codex 工作期间 composer 依然可见；"有 composer"不等于"空闲"。
- herdr 要到 lane 的首个 turn 结束后才报告 session id；在那之前 goal 状态查不到。
- 链接 worktree 的 git 元数据在主仓库的 `.git/` 里，所以 lane 必须被授予对它的写权限才能 commit——授权范围是整个 `.git`，缩不到子目录。
- 未受信任的目录下 codex 默认只读沙箱，此时额外的可写目录会被拒绝并让 codex **启动即退出**；herdr 一侧只看得到 `timeout`。
- 目录 trust 记在主仓库根上：仓库已受信任时，新 worktree 不再弹。
- 多条 lane 同时向同一个 `.git` 提交是安全的（实测 3 条并行、9 个交错的 commit、零锁冲突），不需要额外的锁协议。
- `herdr worktree remove` 之后，lane 的分支和 commit 仍在主仓库里。

## References 索引

| 文件 | 何时加载 |
|---|---|
| `references/setup.md` | 用户执行 `setup`，或前置检查没过、需要告诉用户怎么补 |
| `references/known-behaviors.md` | 遇到与「技术事实」不符的行为、认不出的弹层或报错、或想确认某个 herdr / codex 行为是否验证过 |
