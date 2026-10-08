# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-10-08

### Added

- **autoresearch**（新 Skill，新插件 `autoresearch`）：把一个可度量的长期目标交给会话之外的循环，几十轮无人值守地迭代
  - 循环是一个独立进程（`scripts/ar.py`，纯 Python 标准库，兼容 3.9），不依赖 Claude Code 会话：每轮组装 prompt → 拉起无状态 harness → 边界检查 → gate → score → commit → 判定 → 不是 keep 就 `git revert` → 记账 → 报告 → 判断停止
  - 四种结局：keep / discard / crash（改了锁定路径或 gate 失败，不打分）/ error（harness 或打分器坏了，不占 discard 配额）
  - git 当实验日志：每轮一个 commit（`--allow-empty`），失败的轮次 revert 而不是 reset，历史里留得住；空轮次不 revert
  - 打分器契约 `{score, version, details, remaining}`：自报版本，只在同版本内比较，换版本自动重测基线并在报告里换色带；`remaining` 是无状态 harness 的状态载体
  - 三种 harness：`claude`（`claude -p`，`--max-turns` / `--max-budget-usd` 截断的轮次照常打分）、`codex`（`codex exec --json`）、`shell`（任意命令，自测与自定义用）；超时杀整个进程组，`harness.env` 的 `$VAR` 透传第三方端点凭据
  - 运行锁（同一研究同时只能有一个 run）、`research.json` 拼错的键拒绝而不是静默忽略、解析不了的 checkpoint 拒绝 run 而不是悄悄跳过
  - 账本在仓库旁的 `<research>.ar/`，`index.json` 可从 checkpoint 文件完全重建；报告是单文件 HTML（内嵌 JSON + SVG 曲线，版本色带、discard 空心点、crash 红叉），每轮重新生成
  - 四个示例研究：`example toy`（不需要模型，验证机制）、`example kata`（两 subject，先写用例再写实现）、`example compress`（有梯度：单文件纯 Python 编解码器压固定语料，分数 = 压缩字节 + 编解码器自身字节）、`example retrieval`（两级管线：召回率 / 召准率 → 选用率，held-out 打分，公开 / 隐藏差距即过拟合）；模板可带 `setup.py` 在生成时产数据
  - 需要 python3 ≥ 3.9、git ≥ 2.23，以及 `claude` 或 `codex` CLI 之一；目标仓库只多出一个 `autoresearch/` 定义目录和一条 `research/<name>` 分支

## [0.6.0] - 2026-09-19

### Added

- **skill-craft**（新 Skill，productivity-skills 插件）：写 skill，以及诊断、改造、体检写坏的 skill 和 prompt
  - 六条原则取代旧的五项检查清单：只给事实和约束、锚定思维不锚定行为、确定性的活进脚本、一个目录就是全世界、外部行为标日期和版本、对着现实测
  - `scripts/check.py`（纯标准库）做结构体检：frontmatter、跨目录链接、死链、孤儿文件、reference 成链、脚本语法、作者机器的绝对路径；只测量不判断，已对本机十余个真实 skill 校准误报
  - `references/antipatterns.md` 12 条反模式带 BAD/GOOD；`references/writing.md` 给从零写的结构决策
  - 明确记入品味类 skill 的例外：具体数值是承重的，不要当"过度详细"精简（v0.3.0 踩过）

### Removed

- **skill-audit**：由 skill-craft 取代。旧版只有审计清单、没有脚本、没覆盖结构与测试维度，且自身就是"怎么做"式的清单而非原则

## [0.5.0] - 2026-09-19

### Added

- **dispatch:codex**（新 Skill，新插件 `dispatch`）：把已 propose 的 OpenSpec change 派发给 codex，在 herdr 的隔离 worktree 里执行标准 apply
  - 每个 change 一条 lane，多个 change 并行；进度只认 OpenSpec 的 `tasks.md`，不引入私有状态协议
  - 默认姿态为 codex 的 `--approve-for-me`（自动审查 + 沙箱），`--strict` 可选，不提供 yolo
  - 调度者亲手重跑验收、写 `verify.md`、push 分支、开 draft 评审请求；merge / archive / 清理只打印命令
  - 评审请求不绑定 GitHub：`github.com` 用 `gh`，GitLab 用 `glab`，内部平台交给运行时里现有的 MR 工具或 skill（脚本交出与平台无关的交接包）；认不出的 host 只问一次，选择按 host 记住
  - 机械操作收在 `scripts/lane.py`（纯 Python 标准库），状态全部从 git + herdr + openspec 现查
  - 子命令 `status`（巡检）、`setup`（环境检测、征得同意后协助安装、上手与退出引导）
  - 目标仓库零安装物，卸载插件即退出
  - 需要 herdr、codex CLI、OpenSpec CLI，且 Claude Code 跑在 herdr pane 内

## [0.4.0] - 2026-06-25

### Added

- **md-image-rehost**（新 Skill，dev-skills 插件）：抽取 Markdown 里的图片，sharp 压缩后转存到自有阿里云 OSS/CDN（ali-oss），就地替换链接
  - 远程外链 + 本地相对路径图片默认都上传（`--skip-local` 仅处理远程）
  - GIF 取首帧静态图，适配阿里云 OSS「原图保护 + 仅样式访问」（动图 WebP 经样式会 `BadWebPImage` 400）
  - 对象键镜像源文件位置 `<项目名>/<md 相对路径>/<内容哈希>.<ext>`，`HEAD` 去重
  - 凭证走环境变量 / `~/.config/md-image-rehost.env` 自动加载，不入库
  - 需 Node.js ≥ 18，首次 `npm install`

## [0.3.1] - 2026-04-30

### Fixed

- **dark-luxury-editorial**: 回滚到 upstream 原始 skill 包内容（字节级一致），仅保留 `name` 字段重命名
  - 原因：v0.3.0 集成时用 skill-audit 做的"质量调优"（精简 non-negotiables、合并决策矩阵、软化约束词）实际跑了一次输出后用户反馈"效果不行"
  - 教训：美学/品味类 skill 的"过度详细"是 load-bearing，不要按 skill-audit 的反模式标准去精简
  - 移除 `agents/openai.yaml`（OpenAI Codex 平台元数据，对 Claude Code 无效）

## [0.3.0] - 2026-04-30

### Added

- **skill-audit**: 新增 Agent Skill/Prompt 质量审计 skill
  - 五项反模式检查：事实/推断混淆、行为锚定、过度详细、排他性分类、自由度匹配
  - 注册到 `productivity-skills` 插件组
- **dark-luxury-editorial**: 新增暗黑奢华杂志风网页生成 skill
  - 把旅行文本/路书/游记转成 React + Tailwind 编辑型网页
  - 8 个分主题 references（benchmark 视觉基线、brief→site 工作流、intent→行程规划、图片与音频管线、实现 recipes、editorial 文案、failure modes/QA、产品演进）
  - 注册到新增的 `design-skills` 插件组

## [0.2.0] - 2026-03-06

### Added

- **agent-team-setup**: 新增 Agent Teams 环境配置 skill
  - `SKILL.md`: 4 步向导（检测 → 配置 → 验证 → 指南）+ 子命令路由（doctor/enable/guide）
  - `scripts/doctor.sh`: 环境诊断脚本，检测 15 项依赖并输出 JSON 报告
  - `references/agent-teams-guide.md`: Agent Teams 使用指南和最佳实践
  - 注册到 `dev-skills` 插件组

## [0.1.0] - 2026-02-18

### Added

- **desktop-kit**: 将任意 Web App 打包为 macOS 桌面客户端（基于 Wails v2）
- **session-insights**: 分析 Claude Code 会话数据，生成带 Mermaid 图表的 Markdown 洞察报告
- 初始化 marketplace.json，拆分为 `dev-skills` 和 `productivity-skills` 两个插件组
