---
name: skill-craft
description: >-
  Writes and improves Agent Skills and prompts. Diagnoses why a skill produces wrong or timid agent behaviour, rewrites the parts that cause it, and checks a skill directory for the structural faults that break it silently — links leaving the directory, dead references, absolute paths from the author's machine, scripts that do not parse.
  Use when the user wants to write a new skill, review or optimize an existing skill or prompt, asks why a skill behaves badly or gets ignored, asks how an instruction should be worded, or says 写 skill / 审查 skill / 优化 prompt / skill 效果不好 / 这个 skill 写得不好.
metadata:
  author: xkcoding
  version: "1.0.0"
---

# skill-craft — 写 skill，和把写坏的 skill 救回来

skill 是写给一个聪明的执行者看的。它已经会推理、会查资料、会在受阻时换路子。你写的每一句话，要么给它**它不知道的事实与约束**，要么就是在替它做决定——而替它做的决定，就是它能力的天花板。

用用户的语言回复。

## 怎么用

| 输入 | 做什么 |
|---|---|
| 一个 skill 的路径或名字 | [审查](#审查一个已有的-skill) |
| "帮我写个 skill 做 X" | [写一个新的](#写一个新的)，先读 `references/writing.md` |
| 一句指令该怎么写、某个反模式怎么改 | 直接按[原则](#六条原则)答，必要时读 `references/antipatterns.md` |
| 不确定是哪种 | 先跑一次检查脚本，用结果开场 |

## 六条原则

这六条是判断依据，不是检查清单。改任何一条指令之前，先问它违反了哪一条、为什么。

**1. 只给事实和约束，策略让它自己权衡。** 两类内容效果完全不同：

| | 技术事实 | 我的推断 |
|---|---|---|
| 例 | "凭记忆构造的 URL 参数常缺必要字段，会被拦" | "所以优先走 UI 操作" |
| 作用 | 推理的**原料** | 推理的**天花板** |

写下推断，agent 就会把它当硬规则执行，哪怕眼前的情况明明不适用。写下事实，它自己会在合适的时候得出同样的结论，并在不合适的时候绕开。
问自己：**这是客观限制，还是我从限制里推出来的偏好？**

**2. 锚定思维，不锚定行为。** "像人一样浏览网页"会让它去模拟鼠标轨迹；"像人一样思考"保留策略，执行自由。
问自己：**我描述的是"怎么做"，还是"怎么想"？**

**3. 确定性的活进脚本，判断留给模型。** 机械且易错的步骤——拼命令行参数、搬文件、解析输出、守卫前置条件——写成脚本，输出结构化结果，失败时说清为什么拒绝。散文里的 shell 片段每次都要被重新敲一遍，每次都可能敲错。
反过来也成立：**需要判断的事不要写成脚本**——读一屏文字决定是提问还是重试，这类事脚本做不了。
问自己：**这一步换成脚本会更可靠吗？还是它本来就需要看一眼再决定？**

**4. 一个 skill 目录就是它的全世界。** 它可能被单独复制到别的项目、被别的 agent 加载。不要链接到目录之外的任何文件，不要指望仓库里的兄弟目录还在。共用的约定就地内联一份，宁可重复。多个入口用**子命令**，不要拆成互相引用的多个 skill。

**5. 外部工具的行为标上日期和版本。** CLI 会变、弹层会变、API 字段会变。写成"某年某月在某版本上观察到"的事实清单，并明说：**当提示，不当保证；不符就以眼前看到的为准，然后回来更新这份记录。** 没验证过的说法单独列，并写明不成立时怎么办。

**6. 对着现实测，别对着文本想。** 读代码找不到的问题，跑一遍就现形。写完 skill 要用真实输入走一遍完整流程；脚本要对真实的外部工具跑，不是 mock。

### 一个例外：品味类 skill

美学、文风、视觉这类 skill，那些看起来"过度详细"的具体数值——间距、字重、配色、节奏——**就是它的内容本身**。把它们按原则 1 精简成"保持克制优雅"，skill 就废了（本仓库真实踩过）。

判断方法：**删掉这个细节，还能得到同样的结果吗？** 能，是冗余；不能，它是承重的。品味类 skill 的细节通常承重。

## 审查一个已有的 skill

**第一步：跑检查脚本。** 它只测量，不下判断。

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check.py" <skill 目录> [<skill 目录> …]
python3 "${CLAUDE_SKILL_DIR}/scripts/check.py" --table <目录> …     # 给人看的一行摘要
```

`flags` 里的都是**确定的毛病**，跟 skill 属于哪一类无关，逐条修：链接指到目录之外、死链、没人引用的文件、reference 互相链接成链、脚本语法错、frontmatter 坏掉、写死了作者机器上的绝对路径。

其余字段是**判断材料，不是结论**。`skill_md_lines` 大不等于坏——品味类 skill 本来就长；`step_lines` 多不等于过度详细——脆弱的操作本来就该给步骤。拿它们配合下面的判断用。

**第二步：判断脚本测不出来的。** 通读 SKILL.md，对每一处可疑的地方问：

- 这句是事实还是我的推断？（原则 1）
- 锚的是思维还是行为？（原则 2）
- 这段散文步骤是不是该变成脚本？反过来，有没有把需要判断的事硬写成了固定流程？（原则 3）
- 用词是否暗示排他？"你可以用这些**通道**：A / B / C"读起来像单选；"可用工具：A、B、C，可组合"才是原意。
- 详细程度配得上任务的脆弱性吗？多种方案皆可 → 给目标和约束；有推荐模式 → 给模板和示例；操作脆弱 → 给具体命令。
- 外部行为有没有标日期和版本？（原则 5）
- 这是品味类 skill 吗？是的话，别动那些具体数值。

细节和更多 BAD/GOOD 对照见 `references/antipatterns.md`。

**第三步：给出发现。** 每条发现必须包含三样：**在哪**（文件加行号或小节名）、**为什么是问题**（对应哪条原则，会导致什么行为）、**改成什么**（直接给改写后的句子，不是"建议优化"）。

按影响排序：会导致错误行为的排在最前，其次是会限制能力的，最后是整洁问题。没问题就说没问题——不要为了凑数编发现。

改动较多时，先把发现列给用户确认，再动手改。

## 写一个新的

读 `references/writing.md`，它给的是结构决策：放哪、frontmatter 怎么写、什么进脚本、references 怎么切、怎么测。

动手前先问清楚三件事，答不上来就先问用户：

1. **触发场景**——用户会怎么开口？这决定 `description` 怎么写，而 `description` 决定这个 skill 会不会被想起来。
2. **哪些步骤脆弱**——错一次就得重来的，进脚本。
3. **成功长什么样**——没有这个，写完没法验证。

## 收尾

改完任何 skill，重跑一次检查脚本确认 `flags` 已清空。改了脚本就对真实输入跑一遍。

**不要替用户提交。** 改了哪些文件、还剩什么没做，说清楚就行。

## References 索引

| 文件 | 何时加载 |
|---|---|
| `references/writing.md` | 要从零写一个新 skill，或要大改一个 skill 的结构时 |
| `references/antipatterns.md` | 审查时要逐条比对反模式，或想给某条发现找一个 BAD/GOOD 对照时 |
