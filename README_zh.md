# Schedule Everything (晨钟暮鼓)

[![CI](https://github.com/sergiudm/schedule-everything/actions/workflows/tests.yml/badge.svg)](https://github.com/sergiudm/schedule-everything/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/schedule-management.svg)](https://pypi.org/project/schedule-management)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue)](https://sergiudm.github.io/schedule-everything/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sergiudm/schedule-everything)
[English Version](README.md)

一种简单而强大的方式，帮助你在 **本地** 管理每日日程，并通过**持久化提醒**确保你按时执行健康习惯、专注工作和规律休息。

`reminder setup` 现在采用“先画像、后排程”的流程：它会先在与 `settings.toml`
同目录的位置读取或生成 `profile.md`，持续追问直到用户画像足够完整，再据此生成日程。

<table>
  <tr>
    <td>
      <img src="assets/rmd_add.gif" alt="Add Schedule" width="100%">
    </td>
    <td>
      <img src="assets/rmd_view.gif" alt="View Schedule" width="100%">
    </td>
  </tr>
</table>

---

## ✨ 功能亮点

- **TOML 配置**：使用清晰、易读且适合版本控制的 TOML 文件定义日程。
- **双重提醒**：持久化通知（模态弹窗）+ 声音提示，确保你不会错过任何提醒。
- **智能循环**：自动在**奇数周**和**偶数周**日程之间切换。
- **灵活事件**：支持时间段（如番茄钟）、特定时间点提醒和每日重复例程。
- **CLI 工具套件**：集成了任务管理、习惯追踪和截止日期监控的命令行工具。
- **AI 驱动**：支持使用 LLM 从任意文本描述轻松生成配置。

## 基于研究的健康排程原则

当用户没有明确给出偏好时，初始化助手会使用一些基于研究的通用默认原则：

- 优先保护充足睡眠，而不是长期靠压缩睡眠换更多工作时间
- 优先保持相对规律的睡眠时点，而不是工作日和周末大幅波动
- 在一周内稳定安排运动和活动量
- 对长时间久坐的工作安排短暂活动或恢复性休息
- 在有弹性时，尽量把高强度认知工作和白天光照放在更早的时间段

这些原则是面向一般人群的排程启发，不构成医疗建议。如果用户有医生建议、残障需求、轮班现实、照护责任或其他硬性约束，应以这些现实约束为准。

相关论文与指南：

- Watson NF, Badr MS, Belenky G, et al. Recommended Amount of Sleep for a Healthy Adult: A Joint Consensus Statement of the American Academy of Sleep Medicine and Sleep Research Society. [AASM 共识 PDF](https://aasm.org/resources/pdf/pressroom/adult-sleep-duration-consensus.pdf) / [AASM advisory](https://aasm.org/advocacy/position-statements/adult-sleep-duration-health-advisory/)
- Sletten TL, Weaver MD, Foster RG, et al. The importance of sleep regularity: a consensus statement of the National Sleep Foundation sleep timing and variability panel. [Sleep Health, 2023](https://doi.org/10.1016/j.sleh.2023.07.016)
- World Health Organization. Physical activity recommendations for adults. [WHO 指南](https://www.who.int/initiatives/behealthy/physical-activity)
- Albulescu P, Macsinga I, Rusu A, et al. "Give me a break!" A systematic review and meta-analysis on the efficacy of micro-breaks for increasing well-being and performance. [PLOS ONE, 2022](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272460)
- Figueiro MG, Steverson B, Heerwagen J, et al. The impact of daytime light exposures on sleep and mood in office workers. [Sleep Health, 2017](https://doi.org/10.1016/j.sleh.2017.03.005)

---

## 🚀 快速开始

### 1. 初始化配置
复制模板文件到 `config/` 目录：

```bash
cp config/settings_template.toml config/settings.toml
cp config/week_schedule_template.toml config/odd_weeks.toml
cp config/week_schedule_template.toml config/even_weeks.toml
```

### 2. 编辑配置
在 `config/` 目录中定义你的日常安排。
- **`settings.toml`**：全局设置和可复用的时间块（例如 `pomodoro = 25`）。
- **`odd_weeks.toml` / `even_weeks.toml`**：你的每日日程表。
- **`synced_schedule.toml`**：由 `reminder sync` 生成并确认后的当日 overlay，用来给今天的 pomodoro/potato 自动写入具体任务标题。

**日程条目示例：**
```toml
[monday]
"09:00" = "pomodoro"                              # 可复用时间块（开始 + 结束提醒）
"14:00" = { block = "meeting", title = "同步会" }  # 带自定义标题的时间块
"22:00" = "该睡觉了 😴"                            # 简单的时间点提醒
```

> [!TIP]
> 查看 [这里](docs/prompt) 可以在几秒内生成你的日程配置。只需描述你的日常安排，LLM 即可为你创建结构化、可直接使用的配置文件。

### 3. 安装
运行安装脚本以设置后台服务：

```bash
./install.sh
```
*请按照输出提示加载 launchd 代理（如果需要）。*

### 4. 可选：交互式 AI 初始化
你可以使用新的初始化向导来配置模型信息，并交互式创建/修改日程：

```bash
reminder setup
```

该向导由 OpenCode（`opencode run`）驱动。请先安装 OpenCode CLI（仓库已内置子模块）：

```bash
./third_party/opencode/install --no-modify-path
```

该向导会将模型配置保存到 `~/.schedule_management/llm.toml`，检测本机是否已有完整配置，并通过 OpenCode 根据结果引导你创建或调整日程。
在新建日程模式下，它会先读取或创建与 `settings.toml` 同目录的 `profile.md`，持续追问并完善用户画像；当画像足够完整后，先给出纯文本日程摘要供你确认，最后才生成 TOML 配置文件。
在修改模式下，它也会优先读取 `profile.md`，让后续改动与用户长期画像保持一致。
当用户没有说清楚细节时，排程器会回退到基于研究的默认原则，例如睡眠规律、活动量、久坐休息和白天光照。

当你已经有任务列表时，也可以运行下面的命令，让 LLM 为今天的 pomodoro/potato 自动分配具体任务，并先给你预览：

```bash
reminder sync
```

---

## 🛠️ CLI 参考

将以下内容添加到你的 Shell 配置文件（例如 `~/.zshrc`）以使用 `reminder` 命令：

```bash
export PATH="$HOME/schedule_management:$PATH"
export REMINDER_CONFIG_DIR="$HOME/schedule_management/config"
alias reminder="$HOME/schedule_management/reminder"
```

### 命令概览

| 类别         | 命令                              | 说明                             |
| ------------ | --------------------------------- | -------------------------------- |
| **系统**     | `reminder update`                 | 重新加载配置并重启后台服务       |
|              | `reminder setup`                  | 基于 OpenCode 的交互式 AI 初始化（先构建/完善 profile.md，再基于研究启发生成摘要与日程，并可按需结合本地文件进行推理） |
|              | `reminder sync`                   | 用 LLM 生成并确认今天的 pomodoro/potato 任务分配 |
|              | `reminder status [-v]`            | 显示即将到来的事件（或完整日程），有同步结果时也会显示具体任务标题 |
|              | `reminder view`                   | 生成并查看 PDF 格式日程可视化界面 |
|              | `reminder edit <file>`            | 直接编辑配置文件                 |
|              | `reminder stop`                   | 停止提醒服务                     |
| **任务**     | `reminder add "任务" <1-10>`      | 添加/更新任务及其重要性          |
|              | `reminder ls`                     | 按重要性列出任务                 |
|              | `reminder rm "任务"` / `rm <id>`  | 按名称或 ID 删除任务             |
| **截止日期** | `reminder ddl`                    | 显示截止日期及紧急状态           |
|              | `reminder ddl add "名称" "MM.DD"` | 添加或更新截止日期               |
|              | `reminder ddl rm <events...>`     | 取消或移除截止日期               |
| **习惯**     | `reminder track [ids...]`         | 记录今天完成的习惯（不传 ID 会弹出窗口）            |
| **报告**     | `reminder report <type>`          | 生成每周或每月（weekly或monthly）的 PDF 报告        |

### 使用示例

```bash
# 添加高优先级任务
reminder add "完成报告" 9

# 为今天的专注时间块生成具体任务分配
reminder sync

# 记录习惯（不需要输入 ID，会弹出窗口）
reminder track

# 启动交互式初始化向导
reminder setup
```

也可以在 `config/settings.toml` 里设置自动弹窗时间：`[tasks].habit_prompt = "HH:MM"`。

---

## 📄 为什么选择 TOML？

市面上已有许多日程管理或提醒工具，但它们大多依赖**图形界面（GUI）**或**私有格式**，难以实现自动化、版本控制和深度定制。

本工具选择 **TOML 作为配置语言**，原因如下：

### ✅ 易读易写  
TOML 语法简洁清晰，无需处理 JSON 的括号或 YAML 的缩进问题，即使是非程序员也能轻松上手。

### ✅ 适合版本控制  
你的日程就是代码。你可以将其存入 Git，追踪变更历史、回滚错误，或通过 `git pull` 轻松同步到多台设备。

### ✅ 可移植且可复现  
想把你的理想开发者日程分享给同事？只需发送 TOML 文件，对方几秒内即可复现整套安排，无需在图形界面中逐项点击。

### ✅ 可组合、可复用  
在 `settings.toml` 中定义一次 `pomodoro = 25`，即可在多天、多周中复用。若想将所有工作块从 25 分钟调整为 30 分钟？只需修改一行，无需逐个编辑日历条目。

### ✅ 无厂商锁定  
你的数据完全由你掌控——无需账号、无需订阅、不依赖云端。可用任意文本编辑器修改，备份到任何地方。

### 🤖 AI 驱动的灵活性  
借助**大模型（LLM）**，你可以轻松将几乎任何形式的日程信息转换为有效的 TOML 配置——无论是 **Google 日历导出**、**团队共享时间表截图**、**PDF 日程表**，甚至**手写笔记**。只需粘贴原始数据或用自然语言描述你的日常安排，LLM 即可秒级生成结构化、可直接使用的配置文件。

---



## 🗺️ 未来计划

- [x] 时间点提醒
- [x] 默认日程模板
- [x] 日程可视化
- [x] 安装脚本
- [x] 跳过某天逻辑
- [x] CLI 工具
- [x] 具有重要性级别的任务管理系统
- [x] 截止日期管理系统
- [x] 用于 LLM 生成 TOML 配置的提示词
- [ ] 更美观的提醒UI
- [ ] **跨平台支持**（Linux & Windows）

---

## 📄 许可证

本项目采用 **MIT 许可证** 发布。详情请参见 [LICENSE](LICENSE) 文件。
