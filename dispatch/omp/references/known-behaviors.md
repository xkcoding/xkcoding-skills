# 已知行为——herdr / omp / lane-guard / openspec

这个 skill 靠几个外部工具的行为立足，而它们都会随版本变——omp 尤其快（18.x）。下面每条都标了发现日期与当时的版本。**当作可能有效的提示，而不是保证**：照它操作却失败了，就以眼前的 pane 为准处理，然后回来更新这份文件——只写验证过的事实，不写猜测。

## omp

- (2026-11-02, omp 18.15.0) omp 跑在 bun 上（`#!/usr/bin/env bun`，`engines.bun >= 1.4.4`），用 `bun install -g @oh-my-pi/pi-coding-agent` 安装；配置、凭据、session 都在 `~/.omp/agent/`，凭据在 SQLite（`agent.db`）里。
- (2026-11-02, omp 18.15.0) `herdr agent start --kind omp --pane <p> -- --tools read,bash,edit,write,goal --no-pty --no-lsp -e <lane-guard> --lane-policy <file> --goal "<goal 文本>"`：omp 画出界面即开工，不需要再发 prompt；没有项目信任框。2 task 的 change 76 秒、约 1.36 万 token（glm-5.3），每 task 一个含 `tasks.md` 勾选的 commit。
- (2026-11-02, omp 18.15.0) omp 读 skill 走 `read skill://openspec-apply-change`；发现 `.omp/skills`、`.agents/skills`、`.claude/skills` 三处。
- (2026-11-02, omp 18.15.0) goal 状态在 session JSONL：`type:"mode_change"` 行的 `data.goal`（`id`、`objective`、`status`、`tokensUsed`、`timeUsedSeconds`、`createdAt`、`updatedAt`）；`status` 取值 `active` / `paused` / `complete` / `budget-limited` / `dropped`（源码）。完成时另有 `type:"custom"`、`customType:"goal-completed"`；完成后还有 `data.goal` 为 null 的 `mode_change`。实测只见过 `active` 与 `complete`。
- (2026-11-02, omp 18.15.0) 不传 `--tools` 时模型可用 `read, bash, edit, eval, glob, grep, task, wait, todo, web_search, write` 及 `xd://ast_edit`、`xd://debug`。其中 `web_search` 在 omp 进程里联网；`glob` 不在守卫名单；`xd://ast_edit` 绕过 write / edit 守卫；`task` 子代理加载了 lane-guard 却没有 `--lane-policy`，靠"无策略即拒绝"才没漏。传 `--tools read,bash,edit,write`（加 `goal`）后只剩这几个。
- (2026-11-02, omp 18.15.0) `read` 支持 `http(s)://`、`www.` 与内部 URI（`agent artifact attachment cfg conflict history issue local mcp memory mr omp out pr proc rule security skill ssh vault xd`），都在 omp 进程里执行。实测 `read https://example.com` 取回网页，同一 lane 里 bash 的 `curl` 被沙箱拒（403）。所以守卫对读取只放行普通路径与 `skill://`。
- (2026-11-02, omp 18.15.0) `tools.approvalMode` 的默认值是 `yolo`（源码 `tools/settings.ts`）；用户可改成 `always-ask` / `always-ask-cached` / `write`，后三者在 bash 前会弹确认。lane 启动时显式传 `--approval-mode yolo`。
- (2026-11-02, omp 18.15.0) 4 个 omp 同时启动、同时请求模型：全部正常，没有 pi 那种配置锁冲突。
- (2026-11-02, omp 18.15.0) 界面：工作中有一行 `Working…`，底栏首段是转圈符加秒数（`⠧ 4s · GLM-5.3 · Goal 0 · <dir> · <branch> · 0.6%/1M`）；空闲时输入框是两条 `───` 之间的 `❯`，底栏首段换成静态图标；上边框可能带会话标题（`─── 󰗇 GREET: … ─`）；扩展状态行（`🔒 lane-guard: …`）在最后。启动时先画大字 banner 和一条 Tip。
- (2026-11-02, omp 18.15.0) print 模式下 stdin 不是终端时 omp 卡在 `readPipedInput`，要 `< /dev/null`（只影响探针，lane 是交互模式）。
- (2026-11-02, omp 18.15.0) 默认模型在 `omp config get modelRoles` 的 `default`；`omp models --json` 返回 `{"models":[{"provider","id","name",…}]}`，即已登录 provider 下可用的模型。

## herdr（对 omp）

- (2026-11-02, herdr 0.9.0 + omp 集成 v9) herdr 的 omp 集成由 `herdr integration install omp` 写到 `~/.omp/agent/extensions/herdr-omp-agent-state.ts`；`herdr integration status` 里显示 `omp: current (v9)`。
- (2026-11-02, herdr 0.9.0) herdr 一启动就报告 omp 的 session，`kind:"path"`，值是 `~/.omp/agent/sessions/<cwd 编码>/<时间>_<id>.jsonl`。所以"有 session"不证明 goal 下达过——omp 的 goal 在 launch 时随参数下达，以 bookkeeping 的记录为准。
- (2026-11-02, herdr 0.9.0) omp 一轮结束后 agent 状态是 `idle`（pi 是 `done`）；herdr 先于 omp 画出界面就报就绪，`launch` 最多等 90 秒看到可识别的 pane。

## lane-guard（sandbox-runtime 0.0.26）

同一个 lane-guard 先在 pi 上做过完整测试，标 "pi 1.4.0" 的条目来自那时；它经 omp 的 pi 兼容层加载，标 "omp" 的条目是在 omp 上复测的。

- (2026-11-02, omp 18.15.0) lane-guard 经 omp 的兼容层（`@earendil-works/pi-coding-agent` 被映射到 omp 的实现）加载：注册的 `bash` 替换了 omp 原生的 bash（越界写 `Operation not permitted`），`tool_call` 守卫对 `write` / `read` 生效，越界 `write` 与读禁读目录都被拦且诱饵内容没进事件流。
- (2026-11-02, pi 1.4.0, macOS) 可写 = worktree + 主仓库 `.git` + 包缓存，denyWrite = `.git/hooks`、`.git/config` 时：worktree 内 `git commit` 成功；bash 写主 checkout、写 `.git/hooks` 均 `Operation not permitted`；`write` 越界、`edit` 改 `.git/config` 被守卫拦下且模型收到原因；经 `/tmp` 软链别名写 worktree 成功；未放行域名 `CONNECT tunnel failed, response 403`；本机 npm 源 200。
- (2026-11-02, git 2.x + sandbox-runtime 0.0.26) 只禁写 `.git/hooks` 与 `.git/config` 不够：lane 在沙箱里把 worktree 的 `.git` 指针改成 `gitdir: ./evil`，在 evil 的 config 里设 `core.fsmonitor`，沙箱外的下一次 `git status` 就以用户权限执行了它。所以策略还禁写 worktree 的 `.git` 与管理目录里的 `commondir` / `gitdir` / `config.worktree`，`lane.py` 的 git 一律带 `-c core.fsmonitor=false`。
- (2026-11-02, sandbox-runtime 0.0.26, macOS) 只放行 `~/.npm` / `~/.cache` / `~/Library/Caches` 时各包管理器各卡在一处：pnpm（Node 内置 `fetch` 默认不读 `HTTPS_PROXY`；store 在 `~/Library/pnpm/store`）、bun（`$TMPDIR` 不可写；npmmirror 的包文件在 `cdn.npmmirror.com`）、Go（`goproxy.cn` 403；`$GOPATH/pkg` 不可写）、Cargo（`index.crates.io` 403；`~/.cargo/registry` 不可写）、Maven 3.8.6（`~/.m2/repository` 不可写；镜像 403；wagon 只认 settings 的 `<proxies>`；JVM 要 `-Djava.net.preferIPv4Stack=true`）。沙箱里的代理是 `HTTP(S)_PROXY=http://localhost:<port>`。
- (2026-11-02, pi 1.4.0 + lane-guard) 补上缓存目录、源与沙箱内环境后，在真实 lane 里各装一个本机缓存里没有的依赖全部成功：pip 25.0.1（venv）、uv 0.6.5、npm 11.19.1、pnpm 11.15.1、bun 1.3.6、go 1.26.3、Maven 3.8.6 + OpenJDK 21（`mvn` 是 lane-guard 导出的带 `-gs` 的函数）、cargo 1.91.1。
- (2026-11-02, pnpm 11.15.1) 沙箱里 pnpm 默认把 store 建在 worktree 的 `.pnpm-store/`；pnpm 11 只认 `pnpm_config_store_dir`。lane-guard 导出它（和 `npm_config_store_dir`）。
- (2026-11-02, bun 1.3.6) 装一个未缓存的小包 3.4 秒；`bun init` 顺带拉 TypeScript 等依赖，在沙箱里用了约 6 分钟。
- (2026-11-02, sandbox-runtime 0.0.26) 沙箱里 `git init`（含 `cargo init` 默认那次）失败：`.git/hooks` 被强制禁写；`cargo init` 要加 `--vcs none`。
- (2026-11-02, pi 1.4.0) 策略文件损坏时底栏显示 `⛔ lane-guard: shell refused (…)`，bash 返回 `lane-guard refused the shell command: …`，没有命令在沙箱外执行。
- (2026-11-02, pi 1.4.0) `ctx.ui.confirm` 默认高亮 `Yes`，所以 `--strict` 的询问用 `ctx.ui.select(…, ["Deny", "Allow"])`：回车 = Deny，模型收到 "a human declined it" 后照常继续。
- (2026-11-02, lane-guard 确定性测试) 用模拟扩展接口的测试验过 27 种读写目标：各种 `协议://`（大小写不敏感）与 `www.` 的读取、`xd://` / `local://` 的写入被拦；`skill://` 与 worktree 内普通路径放行；禁读目录直接读、经软链读、`~` 展开、`grep` / `find` 搜祖先目录都被拦。
- (2026-11-02, glm-5.3) 让模型读工作区外一个名为 secret 的文件，模型自己拒绝了——那是模型的判断，不是边界。

## openspec

- (2026-11-02, openspec 1.12.0) `openspec init --tools oh-my-pi` 写 `.omp/skills/openspec-*` 与 `.omp/commands/opsx-*.md`，不碰 home 目录。

## 没验证过的说法

遇到时小心处理，验证之后挪到上面。

- omp 的选择框 / 确认框（`--strict` 下 lane-guard 询问）在 omp 里长什么样、herdr 那时报什么状态；omp 退出后的 pane。
- goal 的 `paused` / `budget-limited` / `dropped` 在真实 lane 里出现时的样子。
- 用户为 omp 配置了 MCP server 时，工具白名单是否仍把 MCP 工具全挡住。
- Linux（bubblewrap）上的 lane-guard：以上沙箱事实都只在 macOS 上测过。
- Gradle、yarn 没测过；Maven 3.9+ 的 `./mvnw` 经 `MAVEN_ARGS` 带 `-gs` 的路径没测过。
- 长任务下 context 占满、compaction、provider 限流时 omp lane 的表现。
