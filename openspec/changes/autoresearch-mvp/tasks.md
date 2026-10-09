# Tasks

> 顺序即依赖。1–3 不花任何 LLM 费用；4–6 用 Claude Code 订阅真跑；7–8 把验证过的东西封成 skill。每个 task 的验证写在自己那条里。

## 1. 骨架与契约

- [x] 1.1 建立 `autoresearch/{scripts,references,examples/kata}`；验证：`find autoresearch -type d` 只有这些目录
- [x] 1.2 `scripts/ar.py` 的子命令骨架（`init` / `run` / `status` / `report` / `doctor` / `example`），每个子命令输出一个 JSON、捕获所有异常为 `{"ok": false, "error": …}`，退出码 0 / 1 / 2；验证：`python3.9 -c "import ast; ast.parse(open('autoresearch/scripts/ar.py').read())"` 通过，`ar.py bogus` 退出 2 且输出合法 JSON
- [x] 1.3 `research.json` 的加载与校验（名称、描述、`ar_dir`、`harness`、`subjects[]` 的 `program` / `score` / `gate` / `editable` / `locked` / `depends_on` / `agent_may_score` / 停止条件 / `budget`；`$VAR` 引用解析）；验证：缺 `gate`、`depends_on` 指向不存在的 subject、`$MISSING` 未设置三种情况各返回带路径或变量名的拒绝

## 2. runner 核心（spec `autoresearch-layout` / `autoresearch-round-loop`）

- [x] 2.1 账本读写：checkpoint JSON（spec 全部字段）、`index.json` 的派生与重建、产物目录、run 日志；验证：删除 `index.json` 后 `status` 重建出相同内容（`diff` 为空）
- [x] 2.2 git 操作：分支守卫（`research/<name>`）、干净树检查、`autoresearch/` 内改动的 `ar scorer <subject>` 路径限定提交、`commit --allow-empty -m "ar <id>"`、`revert --no-edit`、空 commit 跳过 revert、revert 失败即停；验证：临时仓库里跑通「keep → discard（有改动）→ discard（空 commit）」三轮，`git log --oneline` 形态与 spec 一致，HEAD 的 tree 等于 best 的 tree
- [x] 2.3 一轮的阶段编排：prompt 组装（稳定前缀 + 动态尾部，K 轮摘要）→ harness → 边界检查（含 untracked）→ gate → score → commit → 结局 → revert → 记账 → 报告 → 停止判断；基线轮；版本切换；`error` 单独计数；验证：用 `shell` adapter 写固定脚本制造「keep / discard / 相等 / 改锁定文件 / gate 失败 / 打分器输出非 JSON / 版本号变更」七种情形，账本里的 status、reason、best 全部符合 spec
- [x] 2.4 停止条件与中断：六种停止条件、第一次 SIGINT 做完本轮、第二次杀进程组、续跑的 HEAD 校验与脏树拒绝；验证：`max_consecutive_discards=3` 下第三次 discard 后退出且 `stopped_reason` 正确；跑到一半 `kill -INT` 后账本完整、再次 `run` 从 `n_next` 继续；`kill -KILL` 后再次 `run` 被拒并列出残留路径

## 3. 玩具验证（不需要模型）

- [x] 3.1 `ar.py example toy <dir>`：生成一个 git 仓库，`shell` harness 是随机扰动 `vec.json` 一个分量的脚本，打分器算与锁定目录里隐藏目标的负距离并给出 `remaining`（偏差最大的分量），gate 校验 JSON；两个 subject 第二个 `depends_on` 第一个；验证：生成后 `doctor` 全绿
- [x] 3.2 跑 50 轮；验证：无人干预跑完或因连续 discard 停止；`git log` 全程 append-only、每个 discard 后紧跟 revert；账本 50 个 checkpoint 文件；期间手工改打分器版本号一次，报告曲线出现第二个色带且 best 被重置；第二个 subject 在第一个没有 keep 时被拒、有 keep 后可跑

## 4. 真 harness（spec `autoresearch-harness`）

- [x] 4.1 `claude` adapter：命令行拼装（`-p` / `--output-format json` / `--max-turns` / `--model` / `--max-budget-usd` / `--dangerously-skip-permissions` / `--no-session-persistence`）、去 `CLAUDECODE`、进程组与超时、JSON 解析与 usage 归一化、非 JSON / `is_error` 的处理；验证：对一个只要求"在 README 末尾加一行"的 prompt 真跑一轮，checkpoint 的 usage 四项为数字、`note` 为模型文本、`harness.session_id` 非空
- [x] 4.2 `codex` adapter：`codex exec --json -o … -s workspace-write -C … --skip-git-repo-check`、最终消息文件读取、JSONL 中 usage 的尝试解析（没有则 `null`）、trust 弹层导致启动即退出的识别；验证：同 4.1 的 prompt 真跑一轮；usage 字段的有无写进 `references/known-behaviors.md`
- [x] 4.3 超时实测：`timeout_sec=20` 配一个会一直跑的 prompt；验证：进程组被杀、无残留子进程（`pgrep -g`）、checkpoint `status=error`、`reason=timeout`、本轮已 revert
- [x] 4.4 prompt 模板 `references/round-prompt.md` 定稿：稳定前缀与动态尾部的分界、规则措辞（一轮一个方向、不 commit、不碰 locked、可跑 gate、结束自述、不留探测文件）；验证：4.1 的真跑里 `claude -p` 的 `usage.cache_read` 在第二轮明显大于第一轮（前缀命中缓存）
- [x] 4.5 第三方端点：用 `harness.env` 接一个 Anthropic 兼容端点（GLM 或 MiniMax，以手头有 key 的为准）跑 4.1 的 prompt；验证：成功则把所需 env 名、模型名写法、usage 字段差异写进 `references/known-behaviors.md`；失败则记录报错与缺什么，不阻塞后续任务

## 5. 报告（spec `autoresearch-report`）

- [x] 5.1 `report` 生成器：单文件 HTML、内嵌 JSON、SVG 折线（版本色带、discard 空心点、crash 红叉）、subject 摘要行、checkpoint 列表与详情面板（全部字段、`details` 表格、`remaining` 折叠）；验证：用 3.2 的账本生成，断网打开，摘要行逐字符合 spec 格式，点击 crash 显示 `No measurement recorded`
- [x] 5.2 每轮结束自动重生成；验证：3.2 再跑 3 轮，报告文件 mtime 随每轮更新

## 6. 示例研究 `examples/kata`（真跑验收）

- [x] 6.1 `ar.py example kata <dir>`：生成 git 仓库——`spec/features.json`（约 12 个 query-string 特性）、subject `cases`（program、校验 expected 的参考实现放锁定目录、覆盖公式 ×1 / ×0.05 / −2、`remaining`）、subject `impl`（`depends_on: cases`，gate `py_compile`，逐 case 子进程打分、`remaining` 带期望/实际摘要）；验证：`doctor` 全绿；两个打分器对空仓库各给出基线分和非空 `remaining`
- [x] 6.2 用 `claude` adapter 跑 `cases` 至少 10 轮（订阅登录，`max_turns` 与 `timeout_sec` 按 4.1 实测定）；验证：无人值守跑完；报告里每轮的 agent 时长、usage、note、`remaining` 递减可见；至少出现一次 discard；记录每轮平均耗时与 cache read 量级
- [x] 6.3 跑 `impl` 至少 8 轮；验证：依赖检查通过、通过 case 数单调不降、`remaining` 里的失败 case 被后续轮次逐步消掉；期间手工给 `cases` 的打分器加一条冗余惩罚并 bump 版本，观察报告色带与 best 重置
- [x] 6.4 把 6.2 / 6.3 观察到的行为（限流、超时、agent 留临时文件、prompt 缓存命中率、每轮费用量级）写进 `references/known-behaviors.md`，每条带日期与版本；验证：文件里每条以 `(日期, 版本)` 开头，"没验证过的说法"单列

## 7. skill 封装（spec `autoresearch-skill`）

- [x] 7.1 `SKILL.md`：frontmatter（第三人称 description、中英触发词、`argument-hint`）、定位、子命令表、前置检查（`doctor`，只检查不安装）、原则（程序驱动外环、一切由打分器驱动、人只改文件、harness 无状态）各带为什么、脚本表、`init` 的引导问题、`run` 的前台 / 后台用法、人工介入流程、技术事实、References 索引；验证：总长 < 300 行；无指向目录外的链接；无开发过程编号
- [x] 7.2 `init` 子命令：生成 `research.json` 与 subject 骨架（可直接跑的 `score` / `gate` 模板、带 `_doc` 的字段说明）、不覆盖已有文件；验证：空仓库 `init` 后 `run` 直接得到基线 checkpoint；再次 `init` 报告 skipped
- [x] 7.3 `references/scorer-guide.md`：打分器契约、视频里的坑（无评分项的维度不会被投入、打分器不敏感则假进步、组合覆盖低权重、冗余扣分、LLM judge 的随机性与成本、`remaining` 怎么从度量里导出）；`references/round-prompt.md`；`references/known-behaviors.md`；验证：`skill-craft/scripts/check.py autoresearch` 的 `flags` 为空

## 8. 文档登记与收尾

- [x] 8.1 `.claude-plugin/marketplace.json` 新增插件 `autoresearch`，`metadata.version` 提到 0.7.0；`CLAUDE.md`、`README.md`（Skills 表、插件表、仓库结构、前置要求）、`CHANGELOG.md`；验证：`jq -e '.plugins[] | select(.name=="autoresearch") | .skills == ["./autoresearch"]'` 为 true；三处文档都出现 `autoresearch`
- [x] 8.2 新会话只凭 description 触发：在另一个仓库里说"我想让 agent 自动迭代这个打分器"或"auto research 跑起来"；验证：skill 被触发并进入 `init` 引导
- [x] 8.3 退出成本：对 kata 仓库执行文档里的退出步骤（删分支、删 `autoresearch/`、删 `.ar`）；验证：仓库 `git status` 干净、`git branch` 无 `research/*`、父目录无 `.ar`

## 复核记录（2026-10-08，实现完成后的 review）

- 4.1 当时记下的"Claude Code 2.1.294 已无 `--max-turns`"是错的：官方 CLI reference 明说 `--help` 不列全部 flag。实测 `--max-turns` / `--max-budget-usd` 均有效，触发时退出码 1、`subtype` 为 `error_max_turns` / `error_max_budget_usd`。adapter 改为直接传文档里的 flag，截断轮次照常打分（`harness.cut_off`），不再记 error。"`CLAUDECODE` 必须去掉否则出错"同样未能复现，降级为"仍去掉，但不是为了绕开故障"。
- 7.1 `SKILL.md` 按 skill-craft 重写：从"描述 ar.py 是什么"改为"出现 X → 做 Y"的流程（init 八步含开循环前手跑验证、status 字段表、卡住时的判断依据），去掉重复的脚本表与论证式散文，157 → 155 行但内容换了大半。
- 7.3 `references/round-prompt.md` 删除，操作性内容并入 `SKILL.md`「agent 每轮看到什么」；`known-behaviors.md` 改中文并修正上述事实；`scorer-guide.md` 新增「开循环之前手跑三次」。
- 脚本新增：运行锁 `run.lock`（`status` 报告 `active_run`）、`research.json` 未知键拒绝、解析不了的 checkpoint 拒绝 `run`、`init` 不再默认串 `depends_on`、toy 示例从内嵌字符串搬到 `examples/toy/`、用法错误 JSON 带 argparse 原因、`--repo` 不存在时一句话拒绝、prompt 里 `# Subject:` 不再重复。全部对 toy / kata 真跑验证。
- 示例从两个增为四个：`compress`（单文件纯 Python 编解码器压固定语料，分数 = 压缩字节 + 编解码器自身字节，`direction: min`，gate 禁 `zlib` 等模块、只允许 `codec.py` 变动、往返校验）和 `retrieval`（召回 → 选用两级管线，held-out 打分，公开 / 隐藏差距即过拟合，`select` 的 ceiling 来自 `recall`）。示例生成通用化：`examples/<name>/autoresearch/setup.py` 在生成时产数据，`ar.py` 不再含任何示例专用代码。真跑：retrieval 两级各一轮接近打满、按连续 discard 自动停（$7.64）；compress 用 sonnet 跑几十轮持续有梯度（opus 一轮 $3.20，sonnet 中位 $0.31）。
- 报告（`report.py`）重做并改中文：六张状态卡、穿过 keep 轮次的单调三次样条曲线、#0 基线自动移出坐标轴、最佳轮次的 details / remaining 面板、一行一轮可展开；运行状态来自 `run.lock`。crash / error 的原因现在进下一轮的 prompt（否则 agent 会重复同一个 crash）。
- （2026-10-09）第二次精简（`173f867`）：按"删掉这句，agent 会做得不一样吗"过一遍，`SKILL.md` 168 → 120 行（init 改七步；删 `status` 字段表与「agent 每轮看到什么」一节，改为让用户看 `--dry-prompt`；技术事实只留会改变会话做法的两条），`scorer-guide.md` 89 → 64，`known-behaviors.md` 54 → 42。上面 7.1 / 7.3 两条与前一条复核里的"八步"、"字段表"、"agent 每轮看到什么"以此为准。
- （2026-10-09）spec delta 对齐实现：harness 的截断轮次（`error_max_turns` / `error_max_budget_usd` 退出码 1 仍打分，记 `harness.cut_off`）；round-loop 的运行锁、坏 checkpoint 拒绝、打分器改动后先重测基线（`--rounds 0`）、`direction`、上限放宽后继续；layout 的未知键拒绝；skill 的 `example` 子命令与模板 `setup.py`、开循环前手跑；report 的中文文案、状态卡、单调三次样条、基线自动移出坐标轴、最佳轮次面板、行内展开。
- （2026-10-10）报告重做：用户反馈"静态页面不方便、样式不好看、不够直观"。先做交互原型（`/tmp/ar-runs/proto`，用 compress / retrieval 真实账本）两轮迭代定稿：视觉体系照搬 hiwork-eval-web 的 token 与组件（`--ar-*`、浮起面板、胶囊控件、安静的表格、颜色只表达含义、例外才显示），图表换 Apache ECharts 5.6.0（内嵌，`scripts/vendor/`），默认对数轴、始终画基线、不做缩放，文案改成产品口径；报告只摆事实、不下判断（诊断规则留在 SKILL.md）。实现：`report.py` 重写；`ar.py` 加 `serve`（固定 URL，页面轮询 `/data.json`，`serve.lock`，三处输出带 `url`）、每轮开始写 `run.lock` 的 `round` / `round_started` 并生成一次报告、提交后存 `changes.patch`。toy 真跑验证：页面不刷新即从空闲变为"第 #4 轮进行中"、行数随轮次增长。
