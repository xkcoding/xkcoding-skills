# xkcoding-skills

个人 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) Skills 仓库。每个 Skill 赋予 Claude Code Agent 一项专业能力。

## Skills

| Skill | 描述 | 状态 |
|-------|------|------|
| [desktop-kit](desktop-kit/) | 将任意 Web App 打包为 macOS 桌面客户端 | MVP |

## 安装

### 全局安装（所有项目可用）

```bash
git clone https://github.com/xkcoding/xkcoding-skills.git ~/xkcoding-skills

# 安装你需要的 Skill（以 desktop-kit 为例）
mkdir -p ~/.claude/skills
cp -r ~/xkcoding-skills/desktop-kit ~/.claude/skills/desktop-kit
```

### 项目级安装（仅当前项目可用）

```bash
cd /path/to/your-project

mkdir -p .claude/skills
cp -r /path/to/xkcoding-skills/desktop-kit .claude/skills/desktop-kit
```

### 符号链接（适合本仓库开发者）

```bash
ln -s /path/to/xkcoding-skills/desktop-kit ~/.claude/skills/desktop-kit
```

### 验证

启动新的 Claude Code 会话，输入 `/` 后查看自动补全列表中是否出现对应 Skill 名称。

## 仓库结构

```
xkcoding-skills/
├── .claude-plugin/
│   └── marketplace.json         # Skills 注册清单
├── CLAUDE.md                    # Claude Code 项目指令
├── README.md                    # ← 你在这里
│
├── desktop-kit/                 # Skill: Web → macOS Desktop
│   ├── README.md                # Skill 详细文档
│   ├── SKILL.md                 # Skill 入口（Agent 指令）
│   ├── DESIGN.md                # 设计文档
│   ├── TESTING.md               # 测试流程
│   ├── scripts/                 # 工具脚本
│   └── references/              # 知识文档
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
- [ ] **desktop-kit P2** — CHANGELOG → appcast、更多框架检测

## License

MIT
