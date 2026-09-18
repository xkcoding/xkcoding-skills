# setup — 环境检测与上手引导

`/dispatch:codex setup` 是**唯一**允许安装东西的地方，而且只在用户逐项同意之后。

## 体检

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/doctor.sh"
```

在用户想派发的那个仓库里运行，仓库相关的检查才有意义。给用户一张表：工具 / 状态 / 版本或报错。必需：`openspec`、`herdr`、`codex`、`git`、`jq`、`python3`。可选：`gh`、`glab`——它们只用于"开评审请求"，而且只在代码托管在 GitHub / GitLab 时才用得上；托管在内部平台的仓库两个都不需要。

## 缺失的工具：逐项问，同意才装

每个缺失的工具单独问一次（`AskUserQuestion`：`执行这条命令` / `我自己装，先跳过`），问题里写出将要执行的准确命令。同意 → 执行**恰好那一条**，再重跑体检确认。拒绝 → 机器保持原样，把命令留在输出里，继续下一项。不用 `sudo`；装失败就如实报告输出，不换别的办法硬装。

先用 `brew --version` 能不能跑来决定用哪一列。

| 工具 | 有 Homebrew | 没有 Homebrew |
|---|---|---|
| openspec | `npm install -g @fission-ai/openspec@latest` | 同左 |
| herdr | `brew install herdr` | 指向 https://herdr.dev |
| codex | `brew install --cask codex` | `npm install -g @openai/codex` |
| gh（仓库在 GitHub 时才需要） | `brew install gh` | 指向 https://cli.github.com |
| glab（仓库在 GitLab 时才需要） | `brew install glab` | 指向 https://gitlab.com/gitlab-org/cli |
| jq | `brew install jq` | 请用户用系统包管理器安装 |
| python3 | `brew install python` | 请用户用系统包管理器安装 |
| git | 不代装 | 不代装 |

## 只引导、不代办

| 体检字段 | 告诉用户 |
|---|---|
| `logins.codex_logged_in: false` | 请自己运行 `codex login`（在提示符输入 `! codex login` 可让输出留在本会话） |
| `logins.gh_authenticated: false` | 可选，仅 GitHub 仓库相关。请自己运行 `gh auth login`；不登录也能用，只是 lane 验证后只 push、不开 PR。GitLab 对应 `glab auth login --hostname <host>` |
| `env.in_herdr_pane: false` | 派发需要 Claude Code 跑在 herdr pane 里：先运行 `herdr`，再在其中启动 `claude` |
| `repo.has_openspec_dir: false` | 请自己运行 `openspec init --tools claude,codex`（它是交互式的） |
| `repo.codex_apply_skill_tracked: false` | 请自己运行 `openspec init --tools codex`（或 `openspec update`），并把 `.agents/skills/` **提交**——lane 是从 git 拉出来的，没提交的文件 lane 里看不到 |
| `repo.is_main_checkout: false` | 派发要从主 checkout 发起，不是从某个 worktree |

不登录、不经手凭证、不启动 herdr、不替用户初始化或提交。

## 评审请求用什么开

在目标仓库里运行 `python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge` 看这个远端会怎么走。host 认不出来（内部平台）时问用户一次：用 `glab`、交给运行时里现有的某个 MR 工具或 skill、还是不开。然后记住：

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge --set handoff --tool <工具或 skill 名>   # 例：内部平台的 MR skill
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge --set glab                           # 自建 GitLab，host 名里没有 gitlab 字样
python3 "${CLAUDE_SKILL_DIR}/scripts/lane.py" forge --forget
```

选择按 host 存在 `~/.claude/dispatch/forges.json`，同一个 host 的所有仓库共用，以后不再问。

## 版本差异

`tools.*.version` 与 `verified_against` 不同的，每个工具报告一行（"codex 0.157.0，本 skill 验证于 0.155.0"）。不阻塞，不建议降级。

## 上手引导

体检之后给出下面这些。保持简短。

**日常流程**

```
/opsx:propose <想做的事>              照常规划；想并行就拆成几个互不相干的 change
        ↓  你 review 计划
/dispatch:codex <change> [<change> …]
        ↓  确认一次 → 每个 change 一条 lane
        ↓  每 5 分钟自动巡检；lane 做完后我亲手重跑验收、写 verify.md、push、开 draft 评审请求（PR / MR）
你 review → 你 merge → 你 /opsx:archive
```

**会话结束之后**：定时巡检活在当前会话里，会话结束它就没了；lane 里的 codex 会继续干活，只是没人盯。回来后在同一个仓库、herdr pane 内执行 `/dispatch:codex status`，监督即恢复——状态全部现查，不依赖上一个会话。

**怎么退出**

- 这个 skill **没有往你的仓库里装任何东西**：没有 schema，没改 `openspec/config.yaml`，没有 git hook。卸载插件就是全部的退出手续。
- 留下的只有普通的 git 产物：`change/*` 分支、它们的 commit（每个 change 目录下多一份 `verify.md`，对 OpenSpec 是惰性文件）和评审请求。
- 正在跑的 lane 也能半路退出：分支是普通分支，进度就在 `tasks.md` 里。进到那个 worktree，原地 `/opsx:apply` 接着做。
- 本机上属于本 skill 的只有 `~/.claude/dispatch/`，随时可删，不丢任何进度。
