# Design

## Context

动机见 proposal.md「Why」。这里只记影响做法的现状与约束。

**参照物**：bestony/herdr-dispatch（约 2100 行纯 Markdown 的 Claude Code 插件，无可执行代码）。它的骨架是"Claude 规划 → agent 在 herdr worktree 里执行 → Claude 验收并发布"，状态存在私有的 `state.json` 与 lane 内的 `.dispatch/{TASK.md,progress.md,DONE}`，探针脚本 `lane_state.py` 由模型在运行时现写。

**本仓库的约束**：skill = 目录（`SKILL.md` + `references/` + `scripts/`），在 `.claude-plugin/marketplace.json` 按插件分组注册；文档中文、标识符英文。归档的 `session-insights-parallel` 留下一条教训：`SKILL.md` 是纯 prompt，模型会忽略散文式的条件分支，条件路由必须显式成步骤。

**本 skill 的运行环境不是本仓库**，而是用户的任意目标仓库。默认值按"base 分支受保护、一切经 PR、常用 squash merge"推导，不参考本仓库自身的提交习惯。

### 已实测的事实（2026-09-18）

版本：herdr 0.9.0、openspec 1.13.1、codex 0.154.0（第一轮）/ 0.155.0（第二轮）。以下每条都在 `/tmp` 临时仓库里跑过，结论与版本绑定。

| # | 事实 | 轮次 |
|---|---|---|
| F1 | `openspec instructions apply --change X --json` 返回 `progress{total,complete,remaining}`、`state`（`blocked` / `ready` / `all_done`）、`tasks[]`、`contextFiles`；在 lane worktree 内执行时 root 解析到该 worktree | 1 |
| F2 | `openspec init --tools codex` 只往仓库写 `.agents/skills/openspec-*`，不碰 home；Codex 里的调用形式是 `$openspec-apply-change`（不认 `/opsx:apply`） | 1 |
| F3 | `/goal … $openspec-apply-change <change>` 可组合：codex 先读该 skill 的 `SKILL.md`（链接 worktree 内可发现），按官方流程逐 task 勾选、逐 task commit，结束时自行把 goal 置为 `complete` | 1、2 |
| F4 | 未受信任目录下 codex 默认只读沙箱；此时带 `--add-dir` 会被拒绝并**立刻退出**，herdr 一侧只报 `timeout` | 1 |
| F5 | `--sandbox workspace-write --ask-for-approval on-request --add-dir <主仓库>/.git` 下，lane 能在链接 worktree 里 commit，全程零审批弹层 | 1 |
| F6 | `--approve-for-me`（别名 `--not-so-yolo`，feature `guardian_approval` stable）与 `--sandbox`、yolo **互斥**；与 `--add-dir` 可组合 | 2 |
| F7 | guardian 放行了"写 worktree 之外的路径"和"`git push -u origin <feature 分支>`"，全程不弹给人；被明确告知 Never push 的 3 条 lane 均未 push | 2 |
| F8 | 启动期弹层：codex 升级提示（默认高亮 `Update now`，会执行 `brew upgrade`）、目录 trust 提示。trust 记在**主仓库根**，主仓库已受信任时新 worktree 不再弹 | 1、2 |
| F9 | 3 条 lane 并行约 80 秒全部完成；9 个 task commit 在同一 `.git` 上按秒交错，**锁冲突 0 次**；每条 lane 约 2.7–3.1 万 token | 2 |
| F10 | 不存任何状态文件，仅凭 `git worktree list` + `herdr agent list` + 各 worktree 内的 F1，即可反查出全部 lane 的总览 | 2 |
| F11 | 每个 worktree 内 `openspec list` 只见自己的 change，主 checkout 为空；4 条 lane 分支 `--no-ff` 合并 0 冲突，合并后 `validate --all --strict` 全过 | 2 |
| F12 | `agent_status` 不可靠：同一时刻三条已完成的 lane 分别读出 `done` / `idle` / `working`；`done` 会自行变 `idle` | 1、2 |
| F13 | `herdr worktree create` 首次产生 2 个 workspace（base 仓库 + lane），同仓库后续每次只新增 1 个；`herdr pane read` / `agent read` 返回纯文本；回滚只留约 80 行；`worktree remove` 后 lane 分支与 commit 仍在主仓库 | 1、2 |
| F14 | `~/.codex/goals_1.sqlite` 的 `thread_goals(thread_id,status,tokens_used,time_used_seconds,…)` 是权威 goal 状态；`~/.codex/sqlite/goals_1.sqlite` 存在但为空 | 1 |
| F15 | `herdr agent prompt … --wait` 被中断时，prompt 已送达，中断的只是等待 | 2 |
| F16 | 把 change 的 `.openspec.yaml` 改一行即可在 schema 间切换；change 目录里 OpenSpec 不认识的文件是惰性的，`validate --strict` 照过 | 退出成本实验 |

## Goals / Non-Goals

**Goals:**

- 一条命令把已 propose 的 change 派给 codex，在隔离 worktree 里执行标准 apply；多个 change 并行。
- 工作态（计划、清单、进度、完成声明）只有 OpenSpec 一份真相。
- 离开本机的东西都经过调度者亲手验证；merge、archive、清理留给人。
- 目标仓库零残留，卸载插件即退出。
- 用一次真实的小 change 端到端试运行作为 MVP 验收。

**Non-Goals:**

- opencode / grok 等其它执行者（目录按执行者分开，日后增量添加）。
- 自定义 OpenSpec schema（见 D3）。
- 在一个 change 内部再拆 lane——change 内的并行由 lane 内的 agent 自己用 subagent 解决。
- 解析 codex rollout、按 context 占用率主动 compact、3 次 compaction 后重启线程。
- lane 反向通知调度者（notify-back）。
- 自动 merge、自动 archive、自动删除 worktree 或分支。
- yolo 姿态。
- 把 skill 做成多个互相引用的目录。只做一个自包含的 skill 目录。

## Decisions

### D1 lane = 一个 change

OpenSpec 官方 team-workflow 明言 "One change, one owner"；`tasks.md` 单一写者；CLI 的 tasks JSON 是扁平的，没有"任务组"这个一等概念。并行度 = 同时在飞的 change 数，"能否并行"的判断前移到 propose 阶段的拆分。

*否决*：lane = change 内的任务组。会让 N 个 worktree 同写一个 `tasks.md`，还要自己解析分组并聚合进度。

### D2 显式入口 `/dispatch:codex`，不借 `/opsx:apply` 分流

曾考虑用 schema 的 `apply.instruction` 让 `/opsx:apply` 自动分流到派发。否决原因：OpenSpec 生成的 apply skill 第 6 步写死了"自己动手改代码"，而官方对 instruction 的定性是 "prompt-level behavior contracts, not enforceable checks"——桥接成败取决于模型是否遵从；且 lane 内的 codex 会读到同一条"去派发"的 instruction，形成递归。显式命令行为确定，语义也直白：`/opsx:apply` = 我在这里做，`/dispatch:codex` = 派给 codex 做。同一仓库里每个 change 各选各的。

我们不修改、不覆盖任何 OpenSpec 生成的命令或 skill（`openspec update` 会覆盖它们）。

### D3 MVP 不带自定义 schema

调研过"fork spec-driven + 新增 `dispatch` / `verify` 两个 artifact"的方案，技术上可行（F16，且 `apply.requires` 能被 CLI 原生强制）。搁置原因：schema 格式没有 `extends`，只能整份 fork，上游那几段很长的 instruction 经常修订，会持续漂移；`openspec schema` 仍标 experimental；setup 需要往用户仓库写文件。有了 D2 的显式入口，schema 只剩"让 `isComplete` 等于已验证"这一点收益。

日后若需要，只加一个 `verify` artifact 即可，届时用脚本机械生成（fork 上游 + 追加增量），中途给已有 change 补 schema 只改一行。

### D4 propose commit 落在 lane 分支；base 分支永不被写

| 派发时 change 目录的状态 | 动作 |
|---|---|
| 主 checkout 里未跟踪 | fetch 后从 `origin/<当前分支>` 拉 lane 分支；把目录 `mv` 进 worktree，作为首个 commit：`docs(openspec): propose <change>`（`git commit -- <path>`，路径限定，避免带上 index 里别的暂存内容） |
| 已跟踪且干净 | 从本地 HEAD 拉 lane 分支，不产生 propose commit；PR base = 当前分支名，它不在 origin 上则降级为只 push |
| 已跟踪但有未提交修改 | 拒绝该 lane，请用户先提交或丢弃 |

用 `mv` 不用 `cp`：留在主 checkout 的副本永远不会被勾选，是第二份"真相"，日后 pull 还会撞上 `untracked working tree files would be overwritten`。

lane 分支名：`change/<change-name>`，冲突时追加短后缀。

*否决*：把 propose commit 落在 base 上再 push。受保护的 base 推不上去；不 push 则 squash/rebase 合并后本地 base 的那个 commit 成孤儿，下次 pull 在 `tasks.md` 上 add/add 冲突。

### D5 lane 内跑官方 apply skill

prompt 为 `/goal Apply the OpenSpec change <c> by using $openspec-apply-change <c>. …` 加 lane 边界（F3）。前置条件：目标仓库的 `.agents/skills/openspec-apply-change/` 已提交（F2），派发前检查，缺失则停并引导用户运行 `openspec init --tools codex`。

好处：apply 的语义完全跟随上游，我们不维护一份会漂移的 brief。代价：官方 skill 写死了 "Pause if unclear → ask for clarification"，无人值守的 lane 会因此合理地停住——由 D8 的"先读 pane 再决定续跑"承接。

*备选（记录，不实现）*：不依赖 `.agents/skills/`，直接让 codex 执行 `openspec instructions apply --json` 并照做。

### D6 默认姿态 `--approve-for-me`；`--strict` 可选；不提供 yolo

```
默认:    --no-alt-screen --approve-for-me --add-dir <主仓库>/.git
--strict: --no-alt-screen --sandbox workspace-write --ask-for-approval on-request --add-dir <主仓库>/.git
```

- `--add-dir <主仓库>/.git` 必须有：链接 worktree 的 git 元数据在主仓库的 `.git/worktrees/<name>/`，对象与 ref 写在公共目录，不给就无法 commit。授权范围是整个 `.git`，缩不到子目录（对象库与 ref 是共用的）。
- 严格模式必须**显式**传 `--sandbox`（F4），不能依赖默认值。默认模式**不能**再传 `--sandbox`（F6 互斥）。
- 严格模式下调度者不替用户答审批，只上报（见 D8），所以会更慢——这是该姿态的固有代价。

### D7 "lane 不 push" 靠我们自己守

guardian 防的是外泄、凭证探测、破坏性操作，对"只影响一个用户自有 feature 分支"的 git 操作（含 push）判低/中风险并放行（F7，亦见 codex 源码 `codex-rs/prompts/templates/guardian/policy.md`）。因此：

1. goal 文本里明写 "Never push, never merge, never open a pull request"（F7 中三条 lane 均遵守）。
2. 调度者发布前先 `git ls-remote --heads origin <lane 分支>`：分支已在 origin 上而不是调度者推的 → 标记为越界，交用户裁决。

### D8 无状态巡检 + 一份可丢弃的本机簿记

每次巡检从三处反查（F10）：`git worktree list --porcelain`（lane 集合与分支）、`herdr agent list`（状态，仅作辅助，F12）、各 lane worktree 内的 `openspec instructions apply --json`（n/m 与 `state`）。**读进度时 cwd 永远是 lane 的 worktree**，主 checkout 里的副本可能是过期的。

完成判据：`state == all_done` 且工作树干净且 agent 不在 turn 中。`agent_status` 单独不构成任何结论。

`lane.py list` 里还带一个只读探针（Python 标准库 `sqlite3`，`mode=ro`），按 session id 读 F14 的 goal 状态，用来区分"被限流 / 被人暂停 / 模型自判 blocked"与"真的卡住"——否则这几种情况在外面看起来一样，会被无意义地 nudge。脚本**随仓库发布**，不在运行时让模型现写。

反查不出来的东西放进 `~/.claude/dispatch/<repo-id>/bookkeeping.json`：lane 的 session id、启动时的姿态与 PR base、goal 发出的时间、nudge 记录、已上报过的问题、发布尝试次数。删掉它不丢任何工作态——连"已发布"也能反查：远端 lane 分支指向的 sha 等于 lane 的 HEAD，且该 HEAD 的验证记录有效，就是已发布（实测：删除簿记前后的总览逐字一致）。

goal 发出的时间之所以要记：herdr 要到首个 turn 结束才报告 session id，在那之前"有没有发过 goal"无从反查。第一版脚本就因此把 goal 发了两遍（codex 在 turn 中丢弃了第二条，未造成损害）。现在三层防线：agent 为 `working` 时一律不发；pane 出现 `esc to interrupt` 判为工作中；发出时记一笔。

巡检纪律（借鉴 herdr-dispatch）：发任何输入前先读 pane，有选择列表就不发；只动能对应到本仓库 lane worktree 的 agent；永不 `focus`，永不 `server stop`；空闲且有剩余 task 时先读 pane——lane 在提问就把原话上报，否则才发一条续跑 prompt；连续两次 nudge 无新 commit、n/m 不变就停止并上报。

定时：派发后用 `/loop 5m /dispatch:status` 武装；所有 lane 已发布 / 失败 / 用户暂停 / 等用户时自停。会话结束则定时器随之消失，lane 继续跑，用户在新会话里执行 `/dispatch:status` 即恢复监督。

### D9 验证记录是 change 目录里的普通文件 `verify.md`；PR 默认 draft

调度者在 lane worktree 内亲手重跑每个 task 写明的验证（OpenSpec 的 tasks 模板要求每个 task 自带验证方式）、`openspec validate <change> --strict`、工作树干净、有 propose 之外的 commit。通过后写 `openspec/changes/<change>/verify.md`（验证时的 sha、逐 task 结果、lane 报告的偏离、执行者 + 版本 + 姿态）并提交到 lane 分支，再发布。它对 OpenSpec 是惰性文件（F16），在 git 里、在 PR diff 里，无 origin 的降级场景下也是"已验证"的落点。验证后若 lane 分支又多了别的 commit，验证作废重做。

发布沿用 herdr-dispatch 的做法：显式 refspec `refs/heads/<b>:refs/heads/<b>`、不 force、不 `--no-verify`、先 `gh pr list --head` 复用已有 PR、`gh pr create` 全参数显式 + `--body-file`（任何缺省都会触发交互式提问而挂死）、三次失败后把命令交还用户。

PR 默认开成 **draft**，`--ready` 才开成 ready：ready 会通知 CODEOWNERS 并触发 CI，是更外向的动作；MVP 试运行期取保守默认，试运行后回看。

### D10 merge / archive / 清理只打印命令

报告末尾按安全顺序打印（不执行）：`herdr worktree remove --workspace <ws>` → `gh pr merge` → `/opsx:archive`。archive 时点跟随项目惯例，官方推荐合并之后；本 skill 对此不表态也不执行。

返工不需要新状态：在 lane 的 `tasks.md` 里加 task 或取消勾选 → `remaining > 0` → 下次巡检自然续跑 → 重新验证 → 同一个 PR 更新。

### D11 依赖检测分两个时机

setup（一次性、用户在场）：逐项展示准确的安装命令、逐项征得同意后才执行，不用 sudo；凭证登录、"在 herdr pane 内"、`openspec init` 只引导不代办；检测一律跑 `<tool> --version`，不用 `command -v`（实测到过存在但不可运行的 shim）。派发前：只检查不安装，缺必需项即停并指向 setup；`gh` 缺失不算停，算发布降级并在确认页说明。

### D12 打包：一个自包含的 skill，子命令路由

```
dispatch/
├── README.md                       # 面向用户
└── codex/                          # /dispatch:codex
    ├── SKILL.md                    # 调度哲学 + 子命令路由 + 派发 / 巡检 / 验收发布 + 技术事实（< 300 行）
    ├── scripts/
    │   ├── doctor.sh               # 环境体检 → JSON
    │   └── lane.py                 # plan / create / launch / prompt / list / record-verify / publish / note
    └── references/
        ├── setup.md                # 仅 setup 子命令或前置检查失败时加载
        └── known-behaviors.md      # 带日期与版本的 herdr / codex / openspec 行为记录
```

入口 `/dispatch:codex <change…>`，子命令 `status`、`setup`；定时巡检为 `/loop 5m /dispatch:codex status`。`marketplace.json` 新增插件 `dispatch`，`skills` 只列 `./dispatch/codex`。日后加执行者 = 新增一个同样自包含的 `dispatch/<agent>/`，共用的约定内联，不抽公共目录。

*第一版（已推翻）*：3 个 skill（`codex` / `status` / `setup`）+ `_shared/`，章节号 §0–§9 横跨 5 个文件，靠 `../_shared/` 互相引用。用户评审后指出"taste 不好、不是最佳实践"。对照本机的 web-access、baoyu-skills 及其引用的 Anthropic skill authoring best practices，问题是结构性的：skill 目录应当自包含（baoyu 明文："Never link from SKILL.md to files outside the skill's own directory"）、references 只一层、多入口用子命令而不是互相引用的多个 skill。那一版是照搬了 herdr-dispatch 的**形式**。

### D13 确定性的活进脚本，SKILL.md 只编排

凡是机械且易碎的操作都在 `scripts/lane.py` 里（纯 Python 标准库，每个子命令输出一个 JSON，拒绝时 `ok:false` + `error`）：推导名字与冲突处理、准入判定、建 worktree 与路径限定的 propose commit（带守卫与失败回滚）、按姿态拼启动参数、发 prompt 前的身份确认 / 空闲确认 / 弹层确认、goal 文本（脚本持有，经 argv 传给 herdr，不过 shell，`$openspec-apply-change` 不会被展开）、lane 总览与 `verdict`、写 `verify.md`、越界检测 + 显式 refspec push + PR 复用。

留给模型的只有需要判断的事：读弹层选哪一项、lane 停住时是在提问还是只是停了、逐 task 验收、PR 标题与摘要、什么时候交给人。

依据：第一版把这些写成"散文 + shell 片段"让模型每次重敲。实现期间我自己的测试脚本就照着流程出了错——`herdr worktree create` 失败后仍执行了后面的 `mv`，把 change 目录搬进了一个不是 worktree 的普通目录。脚本化之后这类错误由守卫拦住，且每个子命令都在临时仓库里对真实的 herdr / codex 跑过。

### D14 SKILL.md 的写法

- 先立心法（「调度哲学」六条，每条带为什么），再给流程；相信 agent 聪明，只写它不知道的。目标 < 300 行（现 165 行）。
- 顶部一张子命令表做显式路由，不写散文式条件分支（呼应归档的 `session-insights-parallel` 的教训）。
- 巡检按 `lane.py list` 给出的 `verdict` 查表处置。
- 外部工具的行为写成朴素的「技术事实」清单，标日期与版本，"当提示不当保证；不成立就以眼前的 pane 为准，并更新 `known-behaviors.md`"。不在 skill 文本里使用任何开发过程的编号。
- 脚本路径用 `${CLAUDE_SKILL_DIR}`；末尾放「References 索引：文件 | 何时加载」。
- prompt 调用失败、超时或被中断后，先看 lane 实际怎样了再决定（F15）。
- 启动期弹层通用处理：先读，再选"对用户机器无改动、不写入偏好"的那一项；会写入设置的（trust）先问用户；认不出的交给用户。升级提示每逢新版本都会回来，不能只认某一个弹层。

### D15 评审请求不绑定 GitHub

第一版把"开 PR"写死成了 `gh`——等于默认目标仓库在 GitHub 上，而这个 skill 面向任意仓库（用户的内部仓库用 GitLab，或用内部平台的 MR 工具）。拆成两段：

1. **push**：纯 git，任何托管都一样，留在 `lane.py`（越界检测、显式 refspec、不 force、不动 base）。
2. **开评审请求（PR / MR）**：按 `origin` 的 host 选工具。`github.com` → `gh`；host 名含 `gitlab` → `glab`；其它 host → 用户为该 host 做过的选择；没有选择 → `undecided`，在派发确认页里问一次。

| 工具 | 由谁调用 | 为什么 |
|---|---|---|
| `gh` / `glab` | `lane.py` 内置 | 它们是确定性的 CLI，但缺参数就会进入交互式提问、在非交互调用里挂死——这种坑适合由脚本全参数显式地踩平 |
| 运行时里的 MR 工具或 skill（如内部平台的 MR skill） | 调度者（模型），经 `Skill` 调用 | 脚本调不了 skill；而且这样 dispatch 不必懂任何内部平台，换平台不用改它 |

两者之间的接口是一份**与平台无关的交接包**：`remote_url` / `source_branch` / `target_branch` / `title` / `body_file` / `draft`（实测与某内部 MR skill 的创建入参一一对应）。正文永远先落成文件再交给任何工具——借鉴 baoyu-skills 处理图像生成后端的做法（不写死后端；先把 prompt 写成文件，再调用运行时里有的那个后端）。别的工具开出来的评审请求，用 `note <change> review-url <url>` 记回簿记，总览里就看得到。

**选择按 host 记住**（用户决定）：存在 `~/.claude/dispatch/forges.json`，键是 host，同一 host 的所有仓库共用；`lane.py forge --set … / --forget` 修改。理由：内部仓库的 host 是固定的，每次派发都问一遍是纯打扰。它是用户偏好，不是工作态——删掉的后果只是再被问一次。

"是否已发布"本来就不依赖评审请求：远端 lane 分支的 sha 等于 lane 已验证的 HEAD 即为已发布（D8）。所以 handoff 路径下即使地址没记回来，状态也是对的。

*未验证*：`glab` 这条路径只核对过 `--help`（1.113.0），没有对真实的 GitLab 跑过；MR 的 JSON 字段按 GitLab API 约定取。记在 `references/known-behaviors.md`，试运行时补测。

*否决*：(a) 继续只支持 `gh`——对内部仓库等于只能 push。(b) 为每个内部平台在脚本里写适配器——dispatch 会被迫了解一堆它不该知道的平台，且用户的平台我们根本看不到。(c) 全部交给模型临场发挥——`gh` / `glab` 的交互式挂死是已知的确定性陷阱，不该每次重新踩。

### 借鉴与不借鉴（对照 herdr-dispatch）

借鉴：调度者规划/验证/发布而 lane 只执行；声明 ≠ 结论；以磁盘为准；prompt guard；启动后自行确认就绪；只动自己创建的东西；永不 focus；幂等发布与降级留痕；反死循环计数；断言带版本标注；goal sqlite 作权威状态。

不借鉴：它的**形式**（多文件、连续章节号的散文式流程）；`.dispatch/` 私有协议与 `state.json`；派发时现写计划与验收；默认 yolo；运行时现写探针脚本；引用作者私人 `~/CLAUDE.md` 的 `.gitlock` 协议（F9 证明不需要）；notify-back（是反向注入通道，沙箱内多半也发不出）；16 lane × 多执行者。

## Risks / Trade-offs

- [外部 CLI 行为漂移：herdr、codex 的 `--approve-for-me` 与 `/goal`、OpenSpec 生成的 apply skill] → 断言带版本标注；版本不一致只报告一行不阻塞；driver 只有 codex 一份要跟。
- [guardian 是 LLM，判定非确定；该 flag 很新] → 不把流程边界寄托在它身上（D7）；提供 `--strict`。
- [`--add-dir` 授权整个主仓库 `.git`，lane 理论上能动别的 ref] → 已知并接受；比无沙箱强得多；发布前的越界检测能发现被推走的分支。
- [未覆盖：真实规模任务] context 占满、compaction、限流、官方 skill 的"停下来问人"均未触发过 → 试运行重点观察；MVP 不做主动 compact。
- [未覆盖：多个 change 改同一代码文件 / 同一 capability spec] → 前者靠 propose 阶段拆分避免，合并时按普通 git 冲突处理；后者按官方说法在 archive 时以 `specs/` 冲突暴露，archive 是人工步骤。
- [未覆盖：guardian 拒绝时的表现（回给模型还是弹给人）、严格模式下审批上报的体验、goal 不可用时的回退路径] → 试运行补测，结论回填 driver。
- [handoff 路径依赖调度者正确调用另一个 skill，不如脚本确定；`glab` 路径未对真实 GitLab 验证] → 交接包字段固定且先落成文件；"已发布"的判定不依赖评审请求地址；`glab` 在试运行补测。
- [巡检的 token 成本] 每 5 分钟一次，N 条 lane → 每次只输出每 lane 一行；无变化的 lane 不读 pane。
- [trust 弹层被接受后写入用户的 codex 配置] → 接受前先问用户（D13）。
- [herdr 名称上限 32 字符] → 超长 change 名截断并加后缀，映射仍可由 worktree 路径反查。
- [会话结束后无人监督] → lane 继续跑；`/dispatch:status` 恢复。确认页与引导里写明。

## Migration Plan

纯新增，无迁移。上线 = 合并本变更后 `marketplace.json` 多一个插件。回滚 = 移除该插件条目与 `dispatch/` 目录。对用户目标仓库：无安装物，退出 = 卸载插件；在途 lane 的分支是普通 git 分支，进到 worktree 原地 `/opsx:apply` 即可接着做。

## Open Questions

- 是否给 lane 的 worktree 配一个无效的 pushurl，从机制上拦住 lane 自行 push（需要 `extensions.worktreeConfig`，未验证；不影响 MVP，D7 的两层已覆盖）。
- PR 默认 draft 还是 ready：MVP 取 draft，试运行后回看。
- 是否需要按 context 占用率主动 compact：取决于试运行里长任务的表现。
