# dispatch

把 OpenSpec change 交给外部 coding agent，在隔离的 git worktree 里执行。目前有两个执行者：codex（`/dispatch:codex`）与 omp，即 oh-my-pi（`/dispatch:omp`）。

```
/opsx:propose  →  你 review 计划  →  /dispatch:codex|omp <change> [<change> …]
                                          每个 change 一条 lane：worktree + 分支 + codex 或 omp
                                          lane 里跑的是标准的 OpenSpec apply
                                          ↓
                          Claude 巡检 → 亲手重跑验收 → verify.md → push → draft 评审请求（PR / MR）
                                          ↓
                          你 review  →  你 merge  →  你 /opsx:archive
```

`/opsx:apply` = Claude 在这里做；`/dispatch:codex` = 派给 codex 做；`/dispatch:omp` = 派给 omp 做（模型用 omp 自己的配置，可以是 GLM 等第三方模型）。同一个仓库里每个 change 各选各的。

## 两个入口，一份引擎

两种执行者的 lane 共用同一个 `<repo>.lanes/` 目录和 `change/` 分支前缀，所以**任一入口的 `status` 都管仓库里全部 lane**，并按每条 lane 自己的执行者判断（执行者先看 herdr 报告的 agent 类型，没有 agent 再看本机记录，都没有就标为 unknown、不去碰它）。`lane.py` 与 `doctor.sh` 在 `codex/scripts/` 和 `omp/scripts/` 里各有一份、逐字节相同：skill 目录必须自包含，又不能让两个入口对同一条 lane 判断不一。改引擎只改 `codex/scripts/`，然后运行 `dispatch/sync-engine.sh`；`dispatch/sync-engine.sh --check` 不一致时非零退出。执行者相关的部分都在 `lane.py` 的 `EXECUTORS` 表里。

## 为什么不直接用 herdr-dispatch

思路借鉴自 [bestony/herdr-dispatch](https://github.com/bestony/herdr-dispatch)，区别在状态归谁管：它自带一套私有协议（`.dispatch/TASK.md`、`progress.md`、`DONE`、`state.json`），这里**进度只认 OpenSpec**——计划是 change 的 artifact，进度是 lane 里那份 `tasks.md`，完成声明是 `state: all_done`。lane 的总览每次都从 git、herdr、openspec 现查，不存状态文件。

## 安装

```
/plugin marketplace add xkcoding/xkcoding-skills
/plugin install dispatch@xkcoding-skills
```

然后在目标仓库里执行 `/dispatch:codex setup` 或 `/dispatch:omp setup`：它逐项检测依赖，缺的工具会展示准确的安装命令并逐项征得同意后才装；登录、进入 herdr pane、初始化 OpenSpec 这几件事只告诉你该运行什么，不替你做。

## 前置条件

| 需要 | 原因 |
|---|---|
| [herdr](https://herdr.dev)，且 Claude Code 跑在 herdr pane 里 | lane 的 worktree、workspace、pane 都由它创建 |
| codex CLI，已登录（`dispatch:codex`） | 执行者 |
| omp（跑在 bun 上），默认模型有可用凭据，herdr 的 omp 集成已装；npm、ripgrep；macOS 或 Linux（Linux 另需 bubblewrap、socat）（`dispatch:omp`） | 执行者，及其沙箱（lane-guard 的 sandbox-runtime 依赖由 setup 征得同意后装进 skill 目录） |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) CLI | 进度与状态的唯一来源 |
| 目标仓库已执行 `openspec init --tools codex`（或 `--tools oh-my-pi`），且 `.agents/skills/`（或 `.omp/skills/`）**已提交** | lane 里的 agent 靠它跑 OpenSpec apply；lane 从 git 拉出，没提交的文件它看不到。omp 认 `.omp`、`.agents`、`.claude` 三处 |
| `git`、`jq`、`python3` | 脚本运行时 |
| `gh` 或 `glab`，已登录（可选，视托管平台而定） | 只用于开评审请求。仓库在内部平台时两个都不需要，见下面「评审请求不绑定 GitHub」 |

## 用法

```
/dispatch:codex add-owner-filter fix-ws-timeout      # 派发两个 change 给 codex，并行
/dispatch:omp add-export-csv                          # 派发给 omp
/dispatch:codex                                       # 列出可派发的 change 让你选
/dispatch:codex status                                # 巡检一次（codex 和 omp 的 lane 都在内）；会话结束后回来用它恢复监督
/dispatch:codex setup                                 # 环境检测与引导
```

| Flag | 含义 | 默认 |
|---|---|---|
| `--strict` | 越出沙箱的操作停下来等你批准 | 关 |
| `--ready` | 评审请求开成 ready for review | 关（开 draft） |
| `--no-pr` | 只 push，不开评审请求 | 关 |
| `--no-loop` | 不武装每 5 分钟一次的定时巡检 | 关 |

派发前会展示一次确认：每个 change 的分支、worktree、剩余 task 数、姿态、做完之后会发生什么。你点头之前不创建任何东西。

### 姿态

| 姿态 | codex 参数 | 越出沙箱的操作 |
|---|---|---|
| 默认 | `--approve-for-me` | 由 codex 的审查模型自动判定，不等你 |
| `--strict` | `--sandbox workspace-write --ask-for-approval on-request` | 停下来等你批准；Claude 只转达，不代答 |

两种姿态都保留沙箱，都额外授予 lane 对主仓库 `.git` 的写权限——链接 worktree 的 git 元数据在那里，不给就无法 commit。

omp 自身没有 OS 沙箱；omp lane 的边界由随 skill 发布的 lane-guard 扩展（omp 经 pi 兼容层加载）和一份工具白名单给出：

| 姿态 | 越出 lane 的文件写入 | shell 命令 |
|---|---|---|
| 默认 | 拦下，原因交给模型，lane 不停；`read` 读不到各类凭据目录（`~/.npmrc` 除外），只读普通路径，读不了网址与 omp 的内部 URI；多文件、移动、改名的 edit 与经软链、换大小写的路径都按真实目标检查 | 一律在 OS 沙箱里（macOS Seatbelt / Linux bubblewrap）：只可写 lane worktree、主仓库 `.git` 里 commit 要写的部分（objects、refs、reflog、LFS）与本 lane 的管理目录、各包管理器缓存（npm、pnpm store、bun、pip / uv、`$GOPATH/pkg`、Maven 本地仓库、`~/.cargo/registry` 与 `git`）、lane 私有的临时目录和 `/tmp`（仓库本身在 `/tmp` 下时不放）；可在本机端口上监听与互连（测试起本地服务）；连别的主机只放行公共包源与本机为 npm / pip / Go / Maven / Cargo 配置的源；不走代理的工具由 lane-guard 在沙箱里配好（Node 的 `fetch`、JVM、Maven 的 settings）；沙箱起不来时一律拒绝，不会裸跑 |
| `--strict` | 弹给你批准，默认选项是拒绝；Claude 只转达，不代答 | 同上 |

lane 里只开 read、bash、edit、write、goal 五个工具（外加 `--no-pty --no-lsp`）：omp 其余的工具（eval、glob、task 子代理、web_search 等）会绕过沙箱或守卫。`xd://` 设备与 MCP 工具要经 `write` 调用，守卫拒绝任何 `协议://` 写入，所以也调用不到。启动参数里的 `--approval-mode yolo` 只关掉 omp 自己"调用工具前问人"的环节，不放开上面任何一样。goal 随启动参数下达，你的 omp 配置不会被改动；omp 没有配置锁，多条 lane 同时启动没问题。

omp 进程本身在沙箱之外，它启动时拉起的 MCP server、加载的项目扩展也是——包括被派发仓库自带的 `.omp/mcp.json`、`.omp/extensions/`。派发不信任的仓库前先看一眼 `.omp/` 与 `.claude/`；lane 自己改了这些项目配置（还有 `mcp.json`、`.vscode/` 等）时，`launch` 拒绝再启动它，等你审过。

放开本机端口与 `/tmp` 的代价：lane 能连你本机上开着的服务（本地数据库、模型服务），它绑在 `0.0.0.0` 上的测试服务运行期间局域网可达（开着 macOS 防火墙时会拦），也能改删别的程序放在 `/tmp` 里的文件。不要把要派发的仓库放在 `/tmp` 或 `$TMPDIR` 下。

**沙箱关不掉。** 默认姿态已经不需要人盯着批准，没有理由再把沙箱或守卫也关掉。

codex 这边需要知道的一点：它的自动审查拦的是破坏性操作和数据外泄，它**不会**拦住 lane push 自己的 feature 分支（实测如此）。"lane 不 push"靠 goal 文本里的明确约束，加上发布前检查 origin 上是否已经出现这条分支；出现了会标为 `lane_pushed_itself` 交给你裁决。

### 评审请求不绑定 GitHub

push 是纯 git，任何托管都一样；只有"开评审请求"取决于代码放在哪：

| 远端 host | 怎么开 |
|---|---|
| `github.com` | `gh pr create`（脚本内置） |
| 名字里带 `gitlab` | `glab mr create`（脚本内置） |
| 其它（内部平台、自建实例） | 第一次遇到时问你一次：用 `glab`、交给运行时里现有的某个 MR 工具或 skill、还是不开。**选择按 host 记住**（`~/.claude/dispatch/forges.json`），以后不再问 |

交给别的工具时，脚本只 push，并交出一份与平台无关的交接包——远端地址、源分支、目标分支、标题、正文文件、是否 draft——Claude 再用你指定的那个工具 / skill 去开，并把地址记回总览里。正文永远先落成文件，换工具不用重写。

平时不用自己敲命令——第一次派发时 Claude 会问，或者直接告诉它"这个仓库的评审请求用 `<你的 MR skill>` 开，记住"。底下对应的是：

```bash
lane.py forge                                          # 看这个仓库会怎么走
lane.py forge --set handoff --tool <你的 MR skill 名>   # 记住
lane.py forge --forget                                 # 忘掉
```

### 它永远不会做的事

- commit 或 push base 分支。未提交的 change 会成为 **lane 分支**的首个 commit（`docs(openspec): propose <change>`）。
- force-push、`--no-verify`、push lane 分支以外的任何分支。
- 把没有亲手验证过的东西 push 出去。
- merge、archive、删除 worktree 或分支——这些命令最后打印给你。
- 替你回答审批请求、替你接受会写入配置的弹层、替你升级 codex。
- 往你的仓库里安装任何东西。

## 留在磁盘上的东西

```
<repo>.lanes/<change>/                    lane 的 worktree（与仓库同级）
  └── openspec/changes/<change>/verify.md   验证记录，随 lane 分支进评审请求；对 OpenSpec 是惰性文件
~/.claude/dispatch/<repo-id>/bookkeeping.json   反查不出来的几样东西（session id、姿态、续跑次数、已上报的问题、评审请求地址）
~/.claude/dispatch/<repo-id>/<change>-review.md  评审请求的正文
~/.claude/dispatch/<repo-id>/<change>-policy.json  omp lane 的沙箱与读写策略（launch 时生成）
~/.claude/dispatch/forges.json                   每个 host 用什么开评审请求（你的偏好）
```

`bookkeeping.json` 可以随时删除：每条 lane 的进度、commit、树状态、是否已发布，照样报得对。

## 已知限制

- 只验证过小任务。长任务下 context 占满、compaction、账号限流的表现还没见过；这一版不主动 compact。
- 官方 apply skill 在"任务不清楚"或"遇到阻塞"时会停下来等人。巡检会先看 lane 是不是在提问，是就把原话交给你，而不是盲目续跑。
- 新 worktree 里没有未跟踪的文件（`node_modules`、`.env`）。依赖由 lane 自己装；密钥不会被复制过去。
- 多个 change 改同一个代码文件：合并时按普通 git 冲突处理，最好在 propose 阶段就拆开。多个 change 改同一个 capability spec：按 OpenSpec 官方说法，在 archive 时以 `specs/` 冲突的形式出现。
- 所有 codex lane 共用一个 codex 账号，所有 omp lane 共用 omp 里同一份模型凭据，限流窗口各自共享。
- omp lane 只支持 macOS 与 Linux（没有 OS 沙箱的平台不派发）；沙箱行为目前只在 macOS 上实测过。omp lane 能写你共享的包缓存（包括 Maven 本地仓库、Go 模块缓存、`~/.cargo` 的 registry / git、`~/.cache`）——为了让 lane 装得了依赖，这是有意的取舍。它的代价不只是缓存可能被写坏：lane 可以在缓存里放进代码，等你之后在沙箱外运行 `mvn`、`cargo` 或 pre-commit 时被执行。实测能装（当时测于 pi，同一个 lane-guard）：pip、uv、npm、pnpm、bun、Go、Maven 3.8、Cargo；Gradle、yarn 未测。
- pi 执行者已退役。旧版派发的 pi lane 显示为 `unknown_executor`，巡检不向它发送任何输入：进到 `<repo>.lanes/<change>/` 原地 `/opsx:apply` 收尾，或移除 worktree 后用 `/dispatch:omp` 重新派发。
- herdr、codex、omp 的行为会随版本变（omp 迭代尤其快）。各 skill 的 `references/known-behaviors.md` 里每条都标了日期与版本；版本不一致时只提醒一行，不阻塞。
- 只支持作为插件安装；定时巡检活在当前 Claude 会话里，会话结束后用 `status` 恢复。

## 退出方式

- 目标仓库里**没有任何属于本插件的文件**：没有 schema，没改 `openspec/config.yaml`，没有 hook。卸载插件就是全部手续。
- 留下的只有普通的 git 产物：`change/*` 分支、commit、评审请求。
- 正在跑的 lane 也能半路退出：进到 `<repo>.lanes/<change>/`，原地 `/opsx:apply` 接着做——进度就在那份 `tasks.md` 里。

## 目录

```
dispatch/
├── sync-engine.sh          # codex/scripts 的引擎 → 其他执行者；--check 校验一致
├── codex/                  # /dispatch:codex，自包含 skill
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── doctor.sh       # 环境体检 → JSON（--executor codex|omp）
│   │   └── lane.py         # plan / create / launch / prompt / list / record-verify / publish / forge / note
│   └── references/
│       ├── setup.md
│       └── known-behaviors.md
└── omp/                    # /dispatch:omp，自包含 skill
    ├── SKILL.md
    ├── scripts/
    │   ├── doctor.sh       # 与 codex 的逐字节相同
    │   ├── lane.py         # 与 codex 的逐字节相同
    │   └── lane-guard/     # omp 经 pi 兼容层加载的扩展：OS 沙箱 + 读写守卫（index.ts、package.json、package-lock.json）
    └── references/
        ├── setup.md
        └── known-behaviors.md
```

以后加执行者 = 在 `lane.py` 的 `EXECUTORS` 里加一行、在 `doctor.sh` 里加它的检测，新增一个同样自包含的 `dispatch/<agent>/`，并把它加进 `sync-engine.sh` 的目标列表。
