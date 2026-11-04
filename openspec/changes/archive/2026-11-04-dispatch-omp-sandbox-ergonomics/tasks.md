# Tasks

> 顺序即依赖。1–3 不花模型费用；4 在一次性仓库 + herdr 里真跑一条 omp lane（用户在 omp 里设的默认模型）；5 是文档。改动都在 `feat/dispatch-omp-sandbox-ergonomics` 上，引擎只改 `dispatch/codex/scripts/` 再运行 `dispatch/sync-engine.sh`。

## 0. 前置

- [x] 0.1 本 change 目录作为分支上的首个 commit（`docs(openspec): propose dispatch-omp-sandbox-ergonomics`）；验证：`git branch --show-current` 为 `feat/dispatch-omp-sandbox-ergonomics`，`openspec validate dispatch-omp-sandbox-ergonomics --strict` 通过

## 1. 引擎（spec `dispatch-executors`；design D1、D2、D3）

- [x] 1.1 `lane.py` 新增判断 `/tmp` 能否放行的小函数（主 checkout、worktree、公共 git 目录任一在 `real("/tmp")` 下即不放，返回原因）；`guard_policy` 据此把 `real("/tmp")` 加进 `allowWrite`，并写 `allowLocalBinding: true`；`launch` 输出 `system_tmp`（`open` / `closed`）与 `system_tmp_reason`；验证：对仓库在 `/tmp` 外与在 `/tmp` 下的两个构造 lane 调 `guard_policy`，前者 `allowWrite` 含 `/private/tmp`（macOS）、后者不含且原因指向主 checkout；两者 `denyWrite` / `denyRead` / `allowedDomains` 与改动前逐项相同；`dispatch/sync-engine.sh --check` 通过
- [x] 1.2 codex 不受影响；验证：`EXECUTORS["codex"]["policy"]` 仍为 `None`，codex 的启动参数与 goal 文本与改动前逐字节相同

## 2. lane-guard（design D1）

- [x] 2.1 `loadPolicy` 接受可选布尔 `allowLocalBinding`（其他类型报错，缺省为 `false`），`session_start` 把它放进 `SandboxManager.initialize` 的 `network`；验证：桩接口的确定性测试里，带 `true` / 缺省 / 非布尔三种策略分别得到 `allowLocalBinding: true` / `false` / 拒绝并 fail closed；上一轮的 40 个守卫用例与 `/tmp/x` 的 `write` 放行用例全部通过

## 3. 沙箱实测（sandbox-runtime CLI + 由 `guard_policy` 生成的真实策略，真实 git worktree，macOS）

- [x] 3.1 验证：本地服务测试——`python3 -m http.server` 绑 `127.0.0.1` 后 `curl localhost:<port>` 成功；连局域网里的其他主机（网关）失败（绑 `0.0.0.0` 在 macOS 上会成功，见 design S2）；`echo x > /tmp/<name>` 成功；未放行域名仍 `403`；commit、建删分支、stash 仍成功；写主仓库 `commondir`、其他 lane 的管理文件、hooks、config 仍 `Operation not permitted`；读 `~/.ssh` 仍被拒
- [x] 3.2 验证：仓库放在 `/tmp` 下时，策略不含 `/tmp`，`echo x > /tmp/<name>` 失败、写主 checkout 失败、lane worktree 内 commit 成功

## 4. 真跑（一次性仓库 + herdr）

- [x] 4.1 一个 1 task 的 change：写一个起 `localhost` HTTP 服务并请求它的测试，测试过程中往 `/tmp` 写一个临时文件，按 `/dispatch:omp` 的流程 `create` → `launch` → `list` 直到 `claims_done`；验证：session 里没有 `Operation not permitted`，测试在 lane 里通过，每 task 一个 commit；`launch` 返回 `system_tmp: "open"`
- [x] 4.2 清理：`herdr worktree remove --force`、关闭实验仓库的 workspace、删实验目录、本机记录与对应 omp session；验证：`herdr workspace list` 只剩用户自己的 workspace，`/tmp` 无实验目录

## 5. 文档

- [x] 5.1 `dispatch/omp/SKILL.md`、`references/setup.md` 的边界段写明 `/tmp` 可写（仓库在 `/tmp` 下时不放）与 `localhost` 端口可用及其代价；`references/known-behaviors.md` 记 S1–S3 与第 3、4 组的实测结果（带日期版本），Linux 行为列入未验证；同时删掉"没验证过的说法"里已在 dispatch-omp 4.3 验证过的那条（`--strict` 询问框与 omp 退出后的 pane）；`dispatch/README.md` 姿态表、`CHANGELOG.md` Unreleased 同步；验证：`python3 skill-craft/scripts/check.py dispatch/omp` 无 flags，`openspec validate --all --strict` 通过
