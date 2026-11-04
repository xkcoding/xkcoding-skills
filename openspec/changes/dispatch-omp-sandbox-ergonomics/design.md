# Design

## Context

动机见 proposal.md「Why」，要求见 `specs/dispatch-executors/spec.md`。这里只记影响做法的现状与约束。

**现状**：`lane.py` 的 `guard_policy` 写出策略文件（`allowWrite` / `denyWrite` / `denyRead` / `allowedDomains` / `tmpDir` / `env`）。lane-guard 的 `session_start` 把其中的 `allowedDomains` 与三张路径表交给 `SandboxManager.initialize({ network, filesystem })`；文件守卫用同一份 `allowWrite` / `denyWrite` 判断 `write` / `edit`。所以沙箱与守卫只要从一处放宽，就同时放宽。

### 已实测或从源码确认的事实（2026-11-04，sandbox-runtime 0.0.26，macOS）

| # | 事实 |
|---|---|
| S1 | 真实 lane（aimicontextstudio `agent-eval-runner-dedicated-models`，pi 1.5.0 + 同一个 lane-guard，2026-11-02）session 里全部 19 次 `Operation not permitted`，只出自两处：写 `/tmp/DebugFreezeTest.java`；测试里起本地服务（`JevDecisionClientTest.start:57 » Socket Operation not permitted`，以及 python `bind failed: [Errno 1]`）。没有网络被拒（`403`、`CONNECT tunnel failed`）的记录 |
| S2 | sandbox-runtime 的 `network.allowLocalBinding`（可选布尔）在 macOS 生成 `(allow network-bind (local ip "localhost:*"))` 及同范围的 inbound / outbound 规则（`macos-sandbox-utils.js`）；不开时 Seatbelt `deny default`，任何 bind 都被拒 |
| S3 | Linux 上 sandbox-runtime 用 `bwrap --unshare-net`，网络在独立命名空间里，外网只能走 socat 桥到代理；`allowLocalBinding` 不出现在 `linux-sandbox-utils.js`。命名空间内的 loopback 本来可用，宿主机 `localhost` 上的服务够不着。**未实测** |
| S4 | sandbox-runtime 里 `denyWrite` 优先于 `allowWrite`：放行 `/tmp` 后若再禁写其中的仓库，lane 自己要写的 worktree 与 git 部分也一并被禁，没法再放回来 |
| S5 | macOS 的 `/tmp` 是指向 `/private/tmp` 的软链；守卫比较路径前会解析软链，策略里应写真实路径 |

## Goals / Non-Goals

**Goals:** 让 S1 那两类卡点在 omp lane 里消失，边界的其余部分（git 重定向、凭据禁读、外网白名单、文件守卫）一字不动。

**Non-Goals:**
- 按仓库或按机器追加可写目录与域名的配置（如访问内网）——没有证据需要，等遇到再加。
- 开放 Unix domain socket（Docker、ssh-agent 等）——会让 lane 碰到本机的高权限服务。
- 改变 codex lane 的任何行为。

## Decisions

### D1 `localhost` 端口一律放开，不设开关

策略文件新增 `allowLocalBinding: true`，lane-guard 原样传给 `SandboxManager.initialize({ network: { allowedDomains, deniedDomains: [], allowLocalBinding } })`。`loadPolicy` 接受这个可选布尔；旧策略文件没有这个字段时按 `false` 处理（与现在行为一致）。

- **备选：`launch --allow-local-ports` 按需打开。** 否决：起本地服务的测试很常见（S1 的就是普通单元测试），派发时用户无从预判哪个 change 会需要，结果只是把卡点从运行时挪到派发时。
- **备选：只放 bind 不放 outbound。** 否决：测试要连自己起的服务，S2 的三条规则本来就是一组。

代价写进文档：lane 能连本机 `localhost` 上开着的服务（本地数据库、模型服务等）。

### D2 `/tmp` 按真实路径放行；仓库在 `/tmp` 下时不放

`guard_policy` 把 `real("/tmp")` 加进 `allowWrite`，前提是主 checkout、lane worktree、公共 git 目录三者都不在它下面；否则不加。判断由 `lane.py` 里一个小函数完成，`guard_policy` 与 `launch` 共用，`launch` 据此输出 `system_tmp` 与原因（D3）。由于 S4，这是唯一不破坏 F3（git 重定向）防护的做法：放行 `/tmp` 会连带放行 `/tmp` 下的主 checkout 与 `.git`。

- **备选：让模型别写 `/tmp`（goal 里加一句）。** 否决：S1 里 `$TMPDIR` 早已指向 lane 自己的目录，模型仍手写 `/tmp`；写进 goal 也只是请求。
- **备选：把 `/tmp` 软链/重定向到 lane 的临时目录。** 否决：Seatbelt 不能重映射路径；改系统 `/tmp` 不可能。

文件守卫因为与沙箱共用 `allowWrite`，`write` / `edit` 到 `/tmp` 也随之放行——与 shell 一致，模型不会遇到"bash 能写、write 不能写"。

### D3 校验与报告

`launch` 的返回里加 `system_tmp`（`"open"` / `"closed"`）；`closed` 时附 `system_tmp_reason`（哪一个路径在 `/tmp` 下）。lane-guard 底栏状态行不变。

## Risks / Trade-offs

- [lane 能连本机 `localhost` 服务（含本地数据库），可读写其中数据] → 文档写明；外网仍只走包源白名单，数据出不了本机。
- [lane 能改删其他程序放在 `/tmp` 的文件] → `/tmp` 本来就是共享且全员可写的；文档写明。
- [其他仓库的 lane worktree 恰好在 `/tmp` 下时，本 lane 可写到它] → 只检查本仓库的三个路径；这种布局只出现在实验里，文档写明"不要把要派发的仓库放在 `/tmp`"。
- [Linux 上行为与 macOS 不同（S3）] → 列入 known-behaviors 的未验证项。

## Migration Plan

已有 lane 的策略文件在下次 `launch` 时重写，自动获得新放行；正在运行的 omp 用的是启动时的策略，重启 lane 才生效。回滚：还原 `guard_policy` 与 lane-guard 的两处改动即可，策略字段可选、向后兼容。
