# xkcoding-skills

个人 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) Skills 仓库。每个 Skill 赋予 Claude Code Agent 一项专业能力。

## Skills

| Skill | 描述 | 状态 |
|-------|------|------|
| [desktop-kit](desktop-kit/) | 将任意 Web App 打包为 macOS 桌面客户端 | MVP |
| [session-insights](session-insights/) | 分析 Claude Code 会话数据，生成 Mermaid 图表洞察报告（支持并行分析） | Stable |

## 前置要求

- Python 3（标准库，无外部依赖）
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI 已安装

## 安装

### 方式一：Plugin Marketplace（推荐）

在 Claude Code 中运行：

```bash
/plugin marketplace add xkcoding/xkcoding-skills
```

然后安装插件：

```bash
# 安装全部
/plugin install dev-skills@xkcoding-skills
/plugin install productivity-skills@xkcoding-skills

# 或按需安装
/plugin install productivity-skills@xkcoding-skills
```

### 可用插件

| 插件 | 说明 | 包含 Skills |
|------|------|-------------|
| **dev-skills** | 开发技能 — 打包、构建、脚手架 | [desktop-kit](desktop-kit/) |
| **productivity-skills** | 效能技能 — 洞察、复盘、工作流优化 | [session-insights](session-insights/) |

也可以直接告诉 Claude Code：

> 请帮我安装 github.com/xkcoding/xkcoding-skills 中的 Skills

### 方式二：手动安装（全局）

```bash
git clone https://github.com/xkcoding/xkcoding-skills.git ~/xkcoding-skills

# 安装你需要的 Skill（以 session-insights 为例）
mkdir -p ~/.claude/skills
cp -r ~/xkcoding-skills/session-insights ~/.claude/skills/session-insights
```

### 方式三：手动安装（项目级）

```bash
cd /path/to/your-project

mkdir -p .claude/skills
cp -r /path/to/xkcoding-skills/session-insights .claude/skills/session-insights
```

### 方式四：符号链接（适合本仓库开发者）

```bash
ln -s /path/to/xkcoding-skills/session-insights ~/.claude/skills/session-insights
```

### 更新

通过 Marketplace 安装的用户：

1. 在 Claude Code 中运行 `/plugin`
2. 切换到 **Marketplaces** 标签
3. 选择 **xkcoding-skills** → **Update marketplace**

手动安装的用户重新 `git pull && cp -r` 即可。

### 验证

启动新的 Claude Code 会话，输入 `/` 后查看自动补全列表中是否出现对应 Skill 名称。

## 仓库结构

```
xkcoding-skills/
├── .claude-plugin/
│   └── marketplace.json         # Skills 注册清单
├── CLAUDE.md                    # Claude Code 项目指令
├── README.md                    # <- 你在这里
│
├── desktop-kit/                 # Skill: Web -> macOS Desktop
│   ├── README.md                # Skill 详细文档
│   ├── SKILL.md                 # Skill 入口（Agent 指令）
│   ├── DESIGN.md                # 设计文档
│   ├── TESTING.md               # 测试流程
│   ├── scripts/                 # 工具脚本
│   └── references/              # 知识文档
│
├── session-insights/            # Skill: 会话洞察分析
│   ├── README.md                # Skill 详细文档
│   ├── SKILL.md                 # Skill 入口（Agent 指令）
│   ├── references/              # 并行模式指令等知识文档
│   └── scripts/                 # 数据提取 + 并行分析脚本
│
└── openspec/                    # OpenSpec 变更管理
    └── changes/
```

## 开发规范

### Skill 目录约定

```
<skill-name>/
├── README.md             # Skill 文档（面向用户）
├── SKILL.md              # Agent 指令入口，含 YAML frontmatter（name + description）
├── DESIGN.md             # 设计文档（面向开发者，可选）
├── TESTING.md            # 测试流程（可选）
├── scripts/              # 可执行工具脚本
└── references/           # Agent 按需加载的知识文档
```

### 通用规则

- Skill 入口必须是 `SKILL.md`，YAML frontmatter 中包含 `name` 和 `description`
- 知识文档放 `references/`，Agent 按需读取，避免 context 膨胀
- 可执行脚本放 `scripts/`，用于 Agent 无法直接完成的操作
- Skills 注册在 `.claude-plugin/marketplace.json`
- 中文注释和文档，代码标识符保持英文

### 新增 Skill

1. 创建 `<skill-name>/` 目录
2. 编写 `SKILL.md`（含 YAML frontmatter）
3. 在 `.claude-plugin/marketplace.json` 的 `skills` 数组中添加路径
4. 编写 `README.md` 说明用法

## 路线图

- [x] **desktop-kit MVP** — Wails 壳、图标、DMG、构建脚本
- [ ] **desktop-kit P1** — Sparkle 自动更新、发布脚本、故障排查
- [ ] **desktop-kit P2** — CHANGELOG -> appcast、更多框架检测
- [x] **session-insights MVP** — 会话数据提取、Mermaid 报告生成、summary/detailed 模式
- [x] **session-insights 并行分析** — 分批并行 + 后台执行 + 进度反馈

## License

MIT
