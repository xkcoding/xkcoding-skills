# 已知行为——herdr / pi / lane-guard / openspec

这个 skill 靠几个外部工具的行为立足，而它们都会随版本变。下面每条都标了发现日期与当时的版本。**当作可能有效的提示，而不是保证**：照它操作却失败了，就以眼前的 pane 为准处理，然后回来更新这份文件——只写验证过的事实，不写猜测。

## pi

- (2026-10-29, pi 1.3.0) `herdr agent start --kind pi --pane <p> -- -e npm:pi-codex-goal@0.6.1 --approve --tui-mode regular` 一次就绪。`-e npm:` 把扩展装进 pi 自己的临时目录（`~/.pi/agent/tmp/extensions/npm/<hash>`），不改 `settings.json`、不出现在 `pi list` 里。
- (2026-10-29, pi 1.3.0) `--approve` 只对本次运行信任项目资源：不弹信任框，`.pi/skills/` 与 `.agents/skills/` 下的 `openspec-apply-change` 都能被发现，`~/.pi/agent/trust.json` 不会被创建。两处有同名 skill 时只保留先发现的那份，启动输出里另一份标为 `(skipped)`。
- (2026-10-29, pi 1.3.0) pi 没有 `$skill` 写法；`/skill:name` 只在一条消息开头生效，放进 goal 的 objective 里不展开。objective 写成"use the openspec-apply-change skill (read its SKILL.md first and follow it)"，模型照做。
- (2026-11-02, pi 1.4.0) 交互模式的 pi 读不到 key 时**不退出**：界面照常就绪，底栏统计行是 `0.0%/0 (auto)`、模型位是 `unknown`；发 prompt 后输出 `Error: No API key found for the selected model.`，lane 回到空闲。print 模式（`pi -p`）则打印同一句并以 1 退出。
- (2026-10-29 源码, pi 1.4.0) `dist/core/auth-storage.js`、`settings-manager.js`、`trust-manager.js` 对 `auth.json` / `settings.json` / `trust.json` 的同步锁是 proper-lockfile `lockSync`，重试 10 次 × 20ms，约 200ms 拿不到就抛 `ELOCKED`。另一个会话实地遇到过：同时启动多个 pi，部分进程读不到 key；启动之间隔 4 秒即恢复。结合上一条，lane 里的表现是"带着 `unknown` 模型起来"，`launch` 据此重启一次。
- (2026-11-02, pi 1.4.0) 项目信任弹层：`Trust project folder?`、路径、说明，选项行以 `→ ` 标高亮项（默认 `Trust`），末行 `↑↓ navigate  enter select  escape/ctrl+c cancel`。lane 用 `--approve` 不会遇到；见到就是启动参数被改了。
- (2026-11-02, pi 1.4.0) 升级后的第一次启动会把整段 changelog 打进 pane；有新版本时有 `Update Available` 横幅。两者都不接受输入、不挡输入框。
- (2026-10-29, pi 1.3.0) 界面：工作中输入框的上边框带转圈符，形如 `── ⠙ Working ──`；空闲时两条 `───` 之间为空；底栏是 `<cwd> (<branch>)` 加统计行（`…%/1.0M (auto)   <model> • <thinking>`），扩展状态行（如 `🔒 lane-guard: …`）与 goal 行（`Pursuing goal` / `Goal achieved (2m)`）在其后；退出后打印 `To resume this session: pi --session <id>`。

## pi-codex-goal

- (2026-10-29, 0.6.1 on pi 1.3.0) `/goal <objective>` 直接回 `Goal set.`，没有确认框。模型逐 task 勾选、显式 `git add`、每 task 一个 commit，最后调 `update_goal` 置为 `complete`。2 个小 task：130 秒、1.86 万 token；4 条 1-task lane 并行时各约 1 分钟。
- (2026-10-29, 0.6.1) goal 状态在 session JSONL：`type:"custom"`、`customType:"pi-codex-goal"`；`data.kind` 为 `usage`（带 `status`、`usage.tokensUsed`、`usage.activeSeconds`）或 `set`（`data.goal.status`）。创建与完成各有一条 `set`（`active` → `complete`），同属一个 `goalId`；`custom_message` 里另有一条 `command_start`。
- (2026-10-29, 0.6.1 README) 它自己对 provider 限流排队重试，所以 pi lane 不会出现 `usage_limited`；`blocked` 必须显式 `/goal resume`；`complete` 是终态。

## herdr（对 pi）

- (2026-10-29, herdr 0.9.0) herdr 的 pi 集成（`~/.pi/agent/extensions/herdr-agent-state.ts`，由 herdr 安装）在**首个 turn 之前**就报告 session，`kind:"path"`，值是 session JSONL 的路径。所以对 pi 来说"有 session"不证明 goal 发过。
- (2026-10-29, herdr 0.9.0) pi 一轮结束后 agent 状态是 `done`，不是 `idle`；`herdr agent wait --until idle` 会超时，要等 `done`。
- (2026-11-02, herdr 0.9.0 + pi 1.4.0) pi 的选择框等人期间，herdr 报的状态是 `working`，不是 `blocked`。`list` 因此对 pi lane 读一次 pane，见到选择框就判 `blocked`。
- (2026-10-29, herdr 0.9.0) `agent start` 后立刻 `agent prompt`：出现过文字留在输入框、没有提交的情况，补一次回车即开始工作。2026-11-02 重跑未复现；`prompt` 的核对 + 补回车逻辑实测可用。
- (2026-11-02, herdr 0.9.0 + pi 1.4.0) pi 启动时还要拉扩展或工具（新配置目录下载 fd、首次拉 goal 扩展）时，`agent start` 先于界面画出就报就绪；`launch` 因此最多等 90 秒看到可识别的 pane 再判断。
- (2026-11-02, herdr 0.9.0 + pi 1.4.0) 真实配置下 4 条 lane 由 `launch` 依次启动：相邻就绪间隔约 7 秒、goal 间隔约 4.3 秒，全部一次成功，没有触发重启。

## lane-guard（sandbox-runtime 0.0.26）

- (2026-11-02, pi 1.4.0, macOS) 可写 = worktree + 主仓库 `.git` + 包缓存，denyWrite = `.git/hooks`、`.git/config` 时：worktree 内 `git commit` 成功；bash 写主 checkout、写 `.git/hooks` 均 `Operation not permitted`；`write` 越界、`edit` 改 `.git/config` 被守卫拦下且模型收到原因、未绕；经 `/tmp` 软链别名写 worktree 成功；未放行域名 `CONNECT tunnel failed, response 403`；本机 npm 源 200；`npm install` 成功。
- (2026-11-02, sandbox-runtime 0.0.26) 可写范围只有工作目录时 `npm install` 失败：要写 `~/.npm` 缓存。所以策略里放行了包管理器缓存。
- (2026-11-02, sandbox-runtime 0.0.26, macOS) 只放行 `~/.npm` / `~/.cache` / `~/Library/Caches` 时，各工具各卡在一处：pnpm（Node 内置 `fetch` 默认不读 `HTTPS_PROXY`，报 `fetch failed`；store 在 `~/Library/pnpm/store`）、bun（`$TMPDIR` 不可写；npmmirror 的包文件在 `cdn.npmmirror.com`）、Go（`goproxy.cn` 403；`$GOPATH/pkg` 里的模块缓存与 `sumdb` 不可写）、Cargo（`index.crates.io` 403；`~/.cargo/registry` 不可写）、Maven 3.8.6（`~/.m2/repository` 不可写；镜像 403；wagon 不读 JVM 的 `http(s).proxyHost`，只认 settings 的 `<proxies>`；JVM 默认 IPv6 socket 连不上沙箱代理，`Operation not permitted`，要 `-Djava.net.preferIPv4Stack=true`）。沙箱里的代理是 `HTTP(S)_PROXY=http://localhost:<port>`。
- (2026-11-02, pi 1.4.0 + lane-guard，经 pi 的 `!` 命令在真实 lane 里装各一个本机缓存里没有的依赖) 全部成功：pip 25.0.1（python 3.14 venv）、uv 0.6.5、npm 11.19.1、pnpm 11.15.1、bun 1.3.6、go 1.26.3（GOPROXY=goproxy.cn）、Maven 3.8.6 + OpenJDK 21（aliyun 镜像，`mvn` 为 lane-guard 导出的带 `-gs` 的函数，3.5 秒）、cargo 1.91.1。worktree 里除探针目录外无改动。
- (2026-11-02, pnpm 11.15.1) 沙箱里 pnpm 默认把 store 建在 worktree 的 `.pnpm-store/`（沙箱外同一项目用的是 `~/Library/pnpm/store`），会让工作区变脏。pnpm 11 只认 `pnpm_config_store_dir`，`npm_config_store_dir` 无效；lane-guard 两个都导出。
- (2026-11-02, bun 1.3.6) 装一个未缓存的小包 3.4 秒；`bun init` 会顺带拉 TypeScript 等依赖，在沙箱里用了约 6 分钟。
- (2026-11-02, sandbox-runtime 0.0.26) 沙箱里 `git init`（含 `cargo init` 默认的那次）失败：`.git/hooks` 被强制禁写。lane 本就在现成仓库里，`cargo init` 要加 `--vcs none`。
- (2026-11-02, pi 1.4.0) 策略文件损坏时底栏显示 `⛔ lane-guard: shell refused (…)`，bash 调用返回 `lane-guard refused the shell command: …`，没有任何命令在沙箱外执行。
- (2026-11-02, pi 1.4.0) `ctx.ui.confirm` 默认高亮 `→ Yes`，一个多余的回车就会放行；所以 `--strict` 的询问改用 `ctx.ui.select(…, ["Deny", "Allow"])`。实测：弹层样式同信任框（`↑↓ navigate  enter select …`），回车 = Deny，模型收到 "a human declined it" 后照常继续。
- (2026-11-02, git 2.x + sandbox-runtime 0.0.26，PR 审查发现并复现) 只禁写 `.git/hooks` 与 `.git/config` 不够：lane 在沙箱里把 worktree 的 `.git` 指针改成 `gitdir: ./evil`，在 evil 的 config 里设 `core.fsmonitor`，沙箱外的下一次 `git status` 就以用户权限执行了它。现在策略还禁写 worktree 的 `.git` 与管理目录里的 `commondir` / `gitdir` / `config.worktree`（改写、删除、改名都被拒，lane 自己 commit 不受影响），`lane.py` 的 git 一律带 `-c core.fsmonitor=false`。
- (2026-11-02, pi 1.4.0) pi 默认启用的内置工具只有 `read`、`bash`、`edit`、`write`，`grep` / `find` / `ls` 默认不开。`read` 在 pi 进程里执行、不经沙箱，沙箱的 `denyRead` 管不到它，所以守卫对 `read` / `grep` / `find` / `ls` 另行执行同一份禁读名单（经软链、`~` 展开、`grep` / `find` 搜祖先目录都算）；用模拟 pi 接口的确定性测试验过 13 种情形。
- (2026-11-02, glm-5.3) 让模型读工作区外一个名为 secret 的文件、或建一条指向它的软链，模型自己拒绝了——那是模型的判断，不是边界；边界见上一条。
- (2026-10-29, pi 官方示例) pi 自带的 sandbox 示例只替换 `bash`；`write` 越界会成功。所以守卫必须单独拦 `write` / `edit`。示例的配置合并按键浅合并，而且会读 `<cwd>/.pi/sandbox.json`——lane-guard 只读 `--lane-policy`。

## openspec

- (2026-10-29, openspec 1.12.0) `openspec init --tools pi` 写 `.pi/skills/openspec-*` 与 `.pi/prompts/opsx-*.md`，不碰 home 目录。

## 没验证过的说法

遇到时小心处理，验证之后挪到上面。

- pi-codex-goal 的 `paused` / `blocked` / `waiting` / `budget-limited` 在真实 lane 里出现时的样子（只见过 `active` 与 `complete`；解析按 README 与连字符 / 驼峰两种写法都兼容）。
- 真正的配置锁冲突在交互 lane 里就是"`unknown` 模型"（复现用的是空 `auth.json`，两者表象相同；4 条串行启动的实测没有撞上锁）。
- `--offline` 能否在 goal 扩展已缓存时省掉启动期的网络请求、又不妨碍首次拉取。
- 长任务下 context 占满、compaction、provider 限流时 pi lane 的表现。
- Linux（bubblewrap）上的 lane-guard：以上沙箱事实都只在 macOS 上测过。
- Gradle、yarn（本机 yarn 是未激活的 corepack shim）没测过；Maven 3.9+ 的 `./mvnw` 经 `MAVEN_ARGS` 带 `-gs` 的路径没测过（本机是 3.8.6，只验证了 `mvn` 函数）。
- lane 里第一次 `go get` 用了 8 分钟以上，之后同样的操作 29 秒；原因没查实（猜测首次拉 checksum 数据库或某次连接超时）。
