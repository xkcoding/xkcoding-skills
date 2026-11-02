# setup — 环境检测与上手引导

`/dispatch:omp setup` 是**唯一**允许安装东西的地方，而且只在用户逐项同意之后。

## 体检

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/doctor.sh" --executor omp
```

在用户想派发的那个仓库里运行，仓库相关的检查才有意义。给用户一张表：工具 / 状态 / 版本或报错。必需：`openspec`、`herdr`、`omp`、`npm`（只用来装下面的沙箱依赖）、`rg`、`sandbox_runtime`（lane-guard 的沙箱依赖，装在本 skill 目录里）、`git`、`jq`、`python3`；Linux 上还有 `bwrap`、`socat`。可选：`gh`、`glab`——它们只用于"开评审请求"，而且只在代码托管在 GitHub / GitLab 时才用得上。

`env.sandbox_platform` 不是 macOS（`darwin…`）或 Linux：说明这台机器上没有 OS 沙箱，`/dispatch:omp` 不可用，到此为止。

## 缺失的工具：逐项问，同意才装

每个缺失项单独问一次（`AskUserQuestion`：`执行这条命令` / `我自己装，先跳过`），问题里写出将要执行的准确命令。同意 → 执行**恰好那一条**，再重跑体检确认。拒绝 → 机器保持原样，把命令留在输出里，继续下一项。不用 `sudo`；装失败就如实报告输出，不换别的办法硬装。

先用 `brew --version` 能不能跑来决定用哪一列。

| 缺失项 | 有 Homebrew | 没有 Homebrew |
|---|---|---|
| sandbox_runtime | `cd "${CLAUDE_SKILL_DIR}/scripts/lane-guard" && npm ci --no-audit --no-fund` | 同左 |
| omp | `bun install -g @oh-my-pi/pi-coding-agent`（omp 跑在 bun ≥ 1.4.4 上；没有 bun 先 `brew install oven-sh/bun/bun`） | `bun install -g @oh-my-pi/pi-coding-agent`；没有 bun 指向 https://bun.sh |
| npm | `brew install node` | 指向 https://nodejs.org，或用户已有的 nvm / fnm |
| rg | `brew install ripgrep` | 请用户用系统包管理器安装 `ripgrep` |
| bwrap / socat（仅 Linux） | 不代装 | 请用户用系统包管理器安装 `bubblewrap`、`socat`（需要 sudo，本 skill 不执行） |
| openspec | `npm install -g @fission-ai/openspec@latest` | 同左 |
| herdr | `brew install herdr` | 指向 https://herdr.dev |
| gh（仓库在 GitHub 时才需要） | `brew install gh` | 指向 https://cli.github.com |
| glab（仓库在 GitLab 时才需要） | `brew install glab` | 指向 https://gitlab.com/gitlab-org/cli |
| jq | `brew install jq` | 请用户用系统包管理器安装 |
| python3 | `brew install python` | 请用户用系统包管理器安装 |
| git | 不代装 | 不代装 |

`sandbox_runtime` 只装进本 skill 自己的 `scripts/lane-guard/node_modules/`：不装全局，不碰目标仓库。`npm ci` 严格按随 skill 发布的 lockfile 安装；用户配了 npm 镜像时 npm 会自动改走镜像。插件每升级一次，安装目录就换一个版本号路径，这一步要重做一次。

## 只引导、不代办

| 体检字段 | 告诉用户 |
|---|---|
| `logins.omp_model` 为空 | omp 还没有默认模型。请自己运行 `omp login` 登录 provider，再在 `omp` 里用 `/model` 选一个默认模型（会写进 omp 的 `modelRoles.default`） |
| `logins.omp_model_ready: false` | omp 的默认模型（`logins.omp_model`）不在已登录 provider 提供的模型里。请自己 `omp login`，或在 omp 里换一个默认模型；`omp models` 可以看到当前可用的。不经手、不打印任何凭据 |
| `env.herdr_omp_integration: false` | herdr 的 omp 集成没装或过期，巡检读不到 omp 的状态与 session。请自己运行 `herdr integration install omp`（它会在 `~/.omp/agent/extensions/` 下写一个文件） |
| `logins.gh_authenticated: false` | 可选，仅 GitHub 仓库相关。请自己运行 `gh auth login`；不登录也能用，只是 lane 验证后只 push、不开 PR。GitLab 对应 `glab auth login --hostname <host>` |
| `env.in_herdr_pane: false` | 派发需要 Claude Code 跑在 herdr pane 里：先运行 `herdr`，再在其中启动 `claude` |
| `repo.has_openspec_dir: false` | 请自己运行 `openspec init --tools claude,oh-my-pi`（它是交互式的） |
| `repo.omp_apply_skill_tracked: false` | 请自己运行 `openspec init --tools oh-my-pi`（或 `openspec update`），并把 `.omp/` **提交**——lane 是从 git 拉出来的，没提交的文件 lane 里看不到。仓库已经提交过 `.agents/skills/`（codex）或 `.claude/skills/` 里的 `openspec-apply-change` 的话，omp 也能用，这一项本就为 true |
| `repo.is_main_checkout: false` | 派发要从主 checkout 发起，不是从某个 worktree |

不登录、不经手凭证、不替用户选模型、不启动 herdr、不装 herdr 集成、不替用户初始化或提交、不改用户的 omp 配置。

## 评审请求用什么开

在目标仓库里运行 `python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge` 看这个远端会怎么走。host 认不出来（内部平台）时问用户一次：用 `glab`、交给运行时里现有的某个 MR 工具或 skill、还是不开。然后记住：

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge --set handoff --tool <工具或 skill 名>   # 例：内部平台的 MR skill
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge --set glab                           # 自建 GitLab，host 名里没有 gitlab 字样
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge --forget
```

选择按 host 存在 `~/.claude/dispatch/forges.json`，与 `/dispatch:codex` 共用，同一个 host 以后不再问。

## 版本差异

`tools.*.version` 与 `verified_against` 不同的，每个工具报告一行（"omp 18.16.0，本 skill 验证于 18.15.0"）。不阻塞，不建议降级。omp 迭代很快，版本不同时更要留意 `references/known-behaviors.md` 里的界面与 session 格式。`sandbox_runtime` 例外：版本不等于 lockfile 里的版本时它直接是 `ok: false`，重跑上表那条 `npm ci` 即可。

## 上手引导

体检之后给出下面这些。保持简短。

**日常流程**

```
/opsx:propose <想做的事>              照常规划；想并行就拆成几个互不相干的 change
        ↓  你 review 计划
/dispatch:omp <change> [<change> …]
        ↓  确认一次 → 每个 change 一条 lane，omp 启动即开工
        ↓  每 5 分钟自动巡检；lane 做完后我亲手重跑验收、写 verify.md、push、开 draft 评审请求（PR / MR）
你 review → 你 merge → 你 /opsx:archive
```

**lane 的边界**：omp 自己不带 OS 沙箱。lane 里的 shell 命令由 lane-guard 放进 OS 沙箱（macOS Seatbelt / Linux bubblewrap）：只能写这条 lane 的 worktree、仓库的 `.git`（`hooks` 与 `config` 除外）、各包管理器的缓存（npm、pnpm、bun、pip / uv、Go、Maven、Cargo）和 lane 自己的临时目录；网络只放行公共包源和你本机为 npm / pip / Go / Maven / Cargo 配置的源。Maven 本地仓库、Go 模块缓存这类共享缓存因此可被 lane 写入——也就是说 lane 能在里面放进你之后在沙箱外构建时会执行的代码。`write` / `edit` 越界会被拦下；`read` 读不到凭据目录，也读不了网址与 omp 的内部 URI；`--strict` 下越界写改为问你，默认选项是拒绝。lane 只开 read / bash / edit / write / goal 五个工具；启动参数里的 `--approval-mode yolo` 只关掉 omp 自己的"问人"环节，不放开以上任何一样。omp 进程本身不在沙箱里。

**会话结束之后**：定时巡检活在当前会话里，会话结束它就没了；lane 里的 omp 会继续干活，只是没人盯。回来后在同一个仓库、herdr pane 内执行 `/dispatch:omp status`（或 `/dispatch:codex status`，两者都看全部 lane），监督即恢复——状态全部现查，不依赖上一个会话。

**从 `/dispatch:pi` 迁过来**：pi 执行者已退役。旧版派发的 pi lane 在这里显示为 `unknown_executor`，巡检不再操纵它们：进到 `<repo>.lanes/<change>/` 原地 `/opsx:apply` 收尾，或 `herdr worktree remove` 后用 `/dispatch:omp` 重新派发。

**怎么退出**

- 这个 skill **没有往你的仓库里装任何东西**：没有 schema，没改 `openspec/config.yaml`，没有 git hook。卸载插件就是全部的退出手续。
- 留下的只有普通的 git 产物：`change/*` 分支、它们的 commit（每个 change 目录下多一份 `verify.md`，对 OpenSpec 是惰性文件）和评审请求。
- 正在跑的 lane 也能半路退出：分支是普通分支，进度就在 `tasks.md` 里。进到那个 worktree，原地 `/opsx:apply` 接着做。
- 本机上属于本 skill 的只有 `~/.claude/dispatch/`（bookkeeping、评审正文、每条 lane 的策略文件与临时目录）和本 skill 目录里的 `node_modules/`，随时可删，不丢任何进度。omp 自己会在 `~/.omp/agent/sessions/` 下保存每条 lane 的 session，那是 omp 的地盘，按 omp 的方式管理。
