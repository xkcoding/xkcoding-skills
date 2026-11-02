---
name: omp
description: >-
  Dispatches already-proposed OpenSpec changes to omp (oh-my-pi) — one herdr worktree lane per change, each running the standard OpenSpec apply under an OS sandbox, a write/read guard and a tool allowlist, with whatever model omp is configured for — then supervises the lanes, independently verifies finished work, pushes the branch and opens a draft review request (GitHub PR via gh, GitLab MR via glab, or an internal forge through whatever MR tool or skill the runtime has). OpenSpec's tasks.md is the only progress record.
  Use when the user asks to dispatch / 派发 / 外包 / hand off an OpenSpec change to omp or oh-my-pi, wants a change applied by a third-party model (GLM, DeepSeek, Qwen…) in an isolated worktree, asks how the dispatched lanes are doing, or invokes /dispatch:omp with or without its status / setup sub-commands. Requires Claude Code running inside a herdr pane.
argument-hint: '[<change> …] [--strict] [--ready] [--no-pr] [--no-loop] | status | setup'
metadata:
  author: xkcoding
  version: "0.1.0"
---

# /dispatch:omp

把已经 propose 好的 OpenSpec change 交给 omp（oh-my-pi）去做：每个 change 一条 lane——一个独立的 git worktree、一个分支、一个 omp——lane 里跑的就是标准的 OpenSpec apply。你是**调度者**：不写一行实现，只负责派发、盯进度、亲手验收、把验证过的分支 push 出去并开评审请求（PR / MR）。

`/opsx:apply` = 我在这里做；`/dispatch:codex` = 派给 codex；`/dispatch:omp` = 派给 omp。同一个仓库里每个 change 各选各的；任一入口的 `status` 都管仓库里**全部** lane，并按每条 lane 自己的执行者判断。

omp 用的模型与凭据是 omp 自己配置的（`~/.omp/agent/`，默认模型是用户在 omp 里设的那个），这里不传、不改、不读凭据。

用用户的语言回复；commit、评审请求用英文。

## 子命令

| 输入 | 做什么 |
|---|---|
| `<change> [<change> …]` | 派发这些 change → [派发](#派发) |
| 不带 change 名 | 列出可派发的 change 让用户选，然后派发 |
| `status` | 对所有 lane 巡检一次 → [巡检](#巡检) |
| `setup` | 环境检测、征得同意后协助安装、上手引导 → 读 `references/setup.md` |

派发可带：`--strict`（越出 lane 的文件写入弹给人批准，见下）、`--ready`（评审请求直接开成 ready，默认 draft）、`--no-pr`（只 push，不开评审请求）、`--no-loop`（不武装定时巡检）。

用户要求"绕过沙箱 / 关掉守卫 / 放开工具"：说明这里不提供——默认姿态已经不需要人盯着，同时保留沙箱、守卫与工具白名单。

## 前置检查

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/doctor.sh" --executor omp
```

只读，输出一份 JSON。它对每个工具**实际执行** version 命令——`PATH` 上存在但跑不起来的 shim 也算缺失。

- `required_tools` 里有 `ok: false`（含 `sandbox_runtime`：skill 目录里的沙箱依赖没装）、`logins.omp_model` 为空或 `logins.omp_model_ready` 为 false、`env.herdr_omp_integration` 为 false、不在 herdr pane 里、不在 git 主 checkout、仓库没有 `openspec/`、`repo.omp_apply_skill_tracked` 为 false（`.omp/skills/`、`.agents/skills/`、`.claude/skills/` 下都没有**已提交**的 `openspec-apply-change`）→ 停下，说清缺什么，请用户运行 `/dispatch:omp setup`。**派发和巡检路径上不安装、不登录、不初始化任何东西。**
- `env.sandbox_platform` 不是 macOS 或 Linux → 停下：这里没有 OS 沙箱，不派发。
- `gh` / `glab` 缺失或未登录不算停：它们只管"开评审请求"，push 不需要它们。具体会怎样由 `plan` 返回的 `review` 决定，在确认页里提前说明。
- 工具版本与 `verified_against` 不同：报告一行，继续。

## 调度哲学

**进度只有一份真相，在 OpenSpec 里。** 计划是 change 的 artifact，进度是 lane 里那份 `tasks.md`，完成声明是 `state: all_done`。不另建任何进度文件。每次巡检都从 git、herdr、openspec 现查，不依赖对话记忆，也不依赖上一个会话——所以读进度永远在 lane 的 worktree 里读，主 checkout 里的同名 change 可能是一份永远不会被勾选的旧副本。

**声明不是结论。** lane 说做完了、goal 是 `complete`、herdr 报 `idle`——都只是"该去验收了"的信号。验收由你在 lane 的 worktree 里亲手重跑。同理，一次调用没有正常返回，不代表 lane 没收到：被中断的 prompt 多半已经送达，先看 lane 实际怎样了再决定下一步。

**先看再动。** 往 lane 发任何东西之前先看它的 pane。有选择列表停在那里时什么都不发——提交的文字或回车会按下高亮项。lane-guard 的越界询问默认高亮的是 `Deny`，但那依然是人的决定，不是你的：只转达，不按键。认不出来的弹层，把原文交给用户。

**只碰自己的，只做可逆的。** 只操纵工作目录就是某条 lane worktree 的那个 agent；永不 `focus`（会抢用户的焦点），永不 `herdr server stop`。永不 commit 或 push base 分支；永不 force-push；永不 merge、archive、删 worktree、删分支——这些命令最后打印给用户，由人来跑。

**边界靠机制，不靠模型自觉。** omp 自身没有 OS 沙箱。lane 的边界由三样东西给出：
- **OS 沙箱**（随 skill 发布的 lane-guard 扩展）：shell 命令里可写的只有 lane worktree、主仓库 `.git` 里 commit 要写的部分（objects、refs、reflog、LFS 对象）和这条 lane 自己的管理目录、各包管理器的缓存和 lane 自己的临时目录；凡是告诉 git 仓库与配置在哪的文件（`.git` 指针、`commondir`、`gitdir`、`config`、`config.worktree`、hooks、其他 worktree 的管理文件）都写不了；读不到 SSH / 云 / GnuPG / docker / kube / netrc / gh / glab / codex / omp 的凭据；网络只放行公共包源与用户为 npm / pip / Go / Maven / Cargo 配置的源；沙箱起不来时 shell 一律拒绝，不会裸跑。
- **守卫**：`write` / `edit` 越界即被拦并把原因交给模型——一次改多个文件、移动或改名时逐个检查，路径里的软链（包括指向还不存在的文件的）都先解析；`read` 读不到上面那些凭据目录，只能读普通路径：网址、omp 的内部 URI（含 `skill://`）一律拦，`a;b` 这类列表逐个检查——omp 的 `read` 本来能在沙箱外联网，也会把列表拆开读；`README.md:1-20` 这种行号选择照常可用。路径比较前按磁盘上的真实拼写解析，`.GIT` 与 `.git` 同等对待。goal 里直接写明 apply skill 的路径。
- **工具白名单**：lane 里只有 read、bash、edit、write、goal。omp 其余的工具（eval、glob、task 子代理、web_search、交互式 PTY、LSP）都会绕过沙箱或守卫，所以不开。`xd://` 设备（含 MCP 工具）要经 `write` 调用，守卫拒绝任何 `协议://` 写入，所以也调用不到。

启动参数里的 `--approval-mode yolo` 只是关掉 omp 自己"调用工具前问人"的环节——否则用户若把 omp 的默认审批改成会问，无人值守的 lane 会卡在每条 bash 上。它不放开上面任何一样；`--strict` 的问人由守卫发起。omp 进程本身在沙箱之外，它在启动时拉起的 MCP server 与加载的项目扩展也是——包括被派发仓库自带的 `.omp/mcp.json`、`.omp/extensions/`；确认页如实这么说。lane 自己改了这些项目配置时，`launch` 拒绝再启动它，直到用户审过（`--reviewed-config`）。lane 能写共享的包缓存，这意味着它能在缓存里放进你之后在沙箱外构建时会执行的代码——派发的是你愿意让它碰你依赖缓存的 change。"lane 不 push"仍然靠 goal 里写明，加上发布前检查 origin 上是不是已经有了这条分支。

**拿不准就交给人。** lane 在提问、有弹层在等人、goal 被人暂停或放弃、同一个 worktree 里有两个 agent——把原话报给用户，不要替他回答。

## 脚本

机械、易错的操作都在 `lane.py` 里，不要手工重做它们（手工搬目录、拼 refspec、拼启动参数都出过事）。每个子命令打印**一个** JSON；`"ok": false` 时 `error` 写着它为什么拒绝——拒绝是信息，不是要绕过的障碍。

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" <子命令> …
```

| 子命令 | 作用 |
|---|---|
| `plan [<change> …] --executor omp [--no-pr]` | 只读。哪些 change 可派发、不可派发的原因（已有 lane 时附 `lane_executor`）、推导出的分支 / worktree / agent 名、base、发布能做到哪一步 |
| `create <change> --executor omp` | 建 worktree 与 `change/<change>` 分支；change 还没提交时，把它搬进 worktree 成为该分支的首个 commit。base 分支不会被动 |
| `launch <change> --executor omp [--strict] [--reviewed-config]` | 写好 lane 的策略文件，在 lane 的 pane 里启动 omp（工具白名单、lane-guard），**goal 随启动参数一起下达**（`goal_sent: true`）；已经下达过 goal 的 lane 重启时不再带 goal。返回 `state`、`model`、`pane_tail` |
| `prompt <change> --continue \| --resume \| --correct "<text>"` | 发一条后续 prompt。发之前确认身份、确认 lane 空闲、确认没有弹层；发之后确认文字真的提交了（`submitted`）。omp lane 的 `--goal` / `--plain` 一律拒绝——goal 已在 launch 时下达 |
| `list [--table]` | 所有 lane（含 codex 的）的总览与 `verdict`。`--table` 每条 lane 一行，给人看 |
| `record-verify <change>` | 从 stdin 的 JSON 写 `verify.md`（含执行者版本与模型）并提交到 lane 分支 |
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

评审请求的正文永远先落成文件（`handoff.body_file`），再交给任何工具——换工具不用重写，也留了一份记录。

## 派发

1. **计划。** `plan <change…> --executor omp`。不可派发的 change 把 `reason` 原样告诉用户（已有 lane 时说明它由哪个执行者在跑），其余照常继续；`tasks_without_verification` 非空时提醒用户：这些 task 没写怎么验证，验收时只能靠读 diff。
2. **确认一次。** 展示每个 change 的分支、worktree、剩余 task 数、change 目录状态（`untracked` → 会成为 lane 分支的首个 commit；`tracked` → 从当前 HEAD 拉分支）、模型（`doctor` 的 `logins.omp_model`），再加三句话：
   - 姿态——默认：`omp + lane-guard：shell 在 OS 沙箱里跑，越出 lane 的读写与未放行的网络直接拦下、把原因交给模型，工具只开 read / bash / edit / write / goal，不会停下来等你；omp 进程本身不在沙箱里`；`--strict`：`同上，但越出 lane 的文件写入停下来等你批准，我只转达、不代答，lane 会因此停顿`。
   - 做完之后——按 `plan` 返回的 `review` 如实说：我亲手重跑验收、写 `verify.md`、push，然后对 `<pr_base>` 开 draft 评审请求（写明用什么开）；`push-only` / `local-only` 连同 `reason` 一起说明；`undecided` 就在这里把[评审请求工具](#评审请求工具)那个问题一并问掉。不承诺做不到的事。
   - 永远不会发生的事：不动 `<pr_base>`；不 merge、不 archive、不删 worktree；不改你的 omp 配置。
   lane 超过 4 条时提醒：所有 lane 共用 omp 里同一份模型凭据，限流是共享的。用 `AskUserQuestion` 问一次：`按此派发` / `改用 --strict` / `取消`。**得到回答之前不创建任何东西。**
3. **逐个 `create`。** 一条失败就记下原因，继续下一条——一条 lane 失败不中止整次派发，也不要去删它已经建好的东西。记下每次返回的 `new_workspaces`：同一仓库第一次派发时 herdr 会多开一个对应主仓库本身的 workspace，它不属于任何 lane，报告里告诉用户可以自行关闭。
4. **逐个 `launch`——goal 随之下达，不再单独发 goal。** 按 `state` 处理：
   - `ready` / `working` 且 `ok: true`、`goal_sent: true` → 这条 lane 已经开工。
   - `dialog` → 读 `pane_tail`，按「先看再动」处理；认不出就交给用户。
   - `exited` → omp 启动后就退出了，不是"慢"。`pane_tail` 里有真正的报错（常见：默认模型不可用、lane-guard 加载失败）；记为这条 lane 的失败原因，不要原样重试。
   - `launch` 失败并列出 `files` → lane 改动了 omp 启动时会在沙箱外加载的项目配置（`.omp/`、`.claude/`、`mcp.json`、`.mcp.json`、`.vscode/`、`.cursor/`、`.codex/`、`.gemini/`，被 gitignore 的也算）。把清单原样交给用户审；用户看过并同意后，才带 `--reviewed-config` 再 `launch`。
5. **收尾。** 立刻巡检一次；除非 `--no-loop`，用 `Skill` 调用 `loop`，参数 `5m /dispatch:omp status`，告诉用户怎么停。最后报告：每条 lane 的分支 / worktree / 姿态 / 模型 / 启动结果，多出来的 workspace，版本差异，以及"会话结束后 lane 会继续跑，回来执行 `/dispatch:omp status` 即恢复监督"。

## 巡检

`list`（给用户看用 `--table`），然后按每条 lane 的 `verdict` 处理。无变化的 lane 不要去读 pane——巡检会跑很多次，省着用上下文。总览里也会出现 codex 的 lane：按同一张表处理，但往 codex lane 发东西、处理它的弹层时，按 `/dispatch:codex` 的规则来。

| verdict | 做什么 |
|---|---|
| `working` | 不打扰 |
| `claims_done` | [验收与发布](#验收与发布) |
| `verified_unpublished` | 直接 `publish`（上次发布没成） |
| `published` | 只报告 |
| `idle_unfinished` | 先读 pane。lane 在提问或报告阻塞 → 把原话交给用户并 `note … escalate`，不续跑。只是停了 → `prompt --continue`。`nudges_without_progress` ≥ 2 → 不再续跑，上报 |
| `blocked` | 读 pane，把请求原文交给用户。omp lane 在 `--strict` 下的越界询问就是这一类（`agent.status` 写着 `dialog in pane`）。**不代答，不按键** |
| `goal_paused` / `goal_budget_limited` / `goal_dropped` | 上报，不恢复：暂停多半是用户自己按的；`dropped` 是 goal 被放弃 |
| `goal_blocked` / `goal_usage_limited` | 只会出现在 codex lane：前者上报；后者 `prompt --resume`，每次巡检最多一次 |
| `lane_pushed_itself` | lane 越界了。上报；用户明确接受之后才 `publish --ack-remote` |
| `no_agent` | 刚 `create` 完还没启动 → `launch`。否则 omp 已退出 → 上报，由用户决定重新 `launch`（goal 已下达过，会改为续跑）还是进 worktree 原地 `/opsx:apply` |
| `unknown_executor` | lane 里的 agent 不是 codex 或 omp（包括已退役的 pi 留下的 lane），或没有 agent 也没有记录。不碰，上报 |
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

6. `publish <change> --title "<type>(<scope>): <summary>"`。标题用 Conventional Commits，不放 lane 名或分支名。想给 reviewer 一段比 `verify.md` 更好读的摘要，就写进文件用 `--body-file` 传入；其中必须说明代码由 omp（及其模型）编写、在什么姿态下运行。返回里带 `handoff` 的，按[评审请求工具](#评审请求工具)用对应的工具开，再 `note <change> review-url <url>`。
7. push 被拒（non-fast-forward）→ 停下上报，**不 force**。

返工不需要新机制：reviewer 要改什么，就往 lane 的 `tasks.md` 里加 task 或取消勾选——下次巡检它自然变回 `idle_unfinished`，做完后重新验收，同一个评审请求收到新 commit。

## 交还给人

全部 lane 了结后，打印（**不执行**）后续命令，按这个顺序——git 拒绝删除仍被 worktree 检出的分支，所以清理在前：

```bash
herdr worktree remove --workspace <ws>      # 会杀掉其中的 omp，并丢弃该 checkout 里未提交的改动
gh pr merge <number> --squash --delete-branch   # GitLab: glab mr merge <iid>；其它平台：在它的页面上合并
/opsx:archive <change>                      # 时点随项目惯例；OpenSpec 官方推荐在合并之后
```

lane 的策略文件与临时目录留在 `~/.claude/dispatch/<repo-id>/` 下（`<change>-policy.json`、`<change>-tmp/`），可以随时删除。用户让你 archive：不做，指给他项目自己的 `/opsx:archive`。

## 技术事实

下面是 2026-11-02 在 herdr 0.9.0（omp 集成 v9）、omp 18.15.0、sandbox-runtime 0.0.26、glm-5.3 上实测到的。当作提示而不是保证：行为不符时以眼前的 pane 为准，并更新 `references/known-behaviors.md`。

- `--goal` 随启动参数下达，omp 画出界面就开工；没有项目信任框。
- herdr 一启动就报告 omp 的 session（一个 JSONL 路径），所以"有 session"不能证明什么；goal 状态从这个文件里读。一轮结束后 herdr 报 `idle`；herdr 会先于界面报就绪，`launch` 会等界面出来再判断。
- 不加工具白名单时 omp 多出 eval、glob、task、web_search、`xd://ast_edit` 等，它们会绕过沙箱或守卫；`read` 能在沙箱外取回网页、读 `skill://`（跟随软链）、把 `a;b` 拆成几次读——这就是白名单与 `read` 只收单个普通路径的原因。
- 4 个 omp 同时启动、同时请求模型都正常（凭据在 SQLite 里），lane 不需要错开启动。
- lane 里 pip（venv）、uv、npm、pnpm、bun、Go、Maven、Cargo 都能装依赖：lane-guard 在沙箱里替它们设好代理、临时目录与 pnpm store，`mvn` 是一个带 `-gs` 的 shell 函数（这些测于 pi 时期的同一个 lane-guard）。装不上时 lane 会拿到 403 或 `Operation not permitted`，按上报处理。
- 一条 omp lane 完成 2 个小 task 约 76 秒、1.4 万 token（glm-5.3）。

## References 索引

| 文件 | 何时加载 |
|---|---|
| `references/setup.md` | 用户执行 `setup`，或前置检查没过、需要告诉用户怎么补 |
| `references/known-behaviors.md` | 遇到与「技术事实」不符的行为、认不出的弹层或报错、或想确认某个 herdr / omp / lane-guard 行为是否验证过 |
