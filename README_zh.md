# 晨钟暮鼓

[![CI](https://github.com/sergiudm/schedule_management/actions/workflows/tests.yml/badge.svg)](https://github.com/sergiudm/schedule_management/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

[English Version](README.md)

本项目提供了一种简单而强大的方式，帮助你在 **本地** 上管理每日日程，并通过**持久化提醒**确保你按时执行健康习惯、专注工作和规律休息。该工具使用 Python 编写，让你时刻保持节奏, J人福利！

> [!NOTE]
> 当前版本专为 **macOS和Linux** 优化。未来计划支持 Windows。

---

## ✨ 功能亮点

- **高度可定制的日程**：使用直观的 TOML 配置文件定义你的日常安排。
- **双重提醒机制**：每次提醒都会同时触发**声音提示**和**模态弹窗**。
- **持续提醒**：警报会不断重复，直到你手动关闭——非常适合督促自己养成习惯。
- **智能周循环**：基于 ISO 周编号，自动在**奇数周**和**偶数周**日程之间切换。
- **灵活的事件类型**：
  - **时间段事件**（如 Pomodoro 番茄钟，包含开始和结束提醒）
  - **时间点提醒**（一次性通知）
  - **通用事件**（适用于所有日期）
- **命令行工具（CLI）**：提供简洁易用的命令行接口，方便查看和管理日程。
- **开机自启（通过 `launchd`）**：系统启动后自动在后台静默运行。

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

## 🧠 工作原理

核心脚本 [`reminder_macos.py`](https://github.com/sergiudm/schedule_management/blob/main/src/schedule_management/reminder_macos.py) 会持续监控系统时间，并与你配置的日程进行比对。当当前时间匹配某个事件时，即触发提醒。

支持以下功能：
- **时间段事件**：具有明确持续时间的活动（如 25 分钟番茄钟 → 触发开始和结束提醒）
- **时间点提醒**：即时通知（如 22:45 提醒"该睡觉了！"）
- **周循环切换**：使用 ISO 周编号自动在 `odd_weeks.toml` 和 `even_weeks.toml` 之间切换
- **通用事件区段**：适用于每天的重复事件（如每晚的放松例行程序）

---

## 快速开始
### 配置说明

所有配置文件位于项目根目录下的 `config/` 文件夹中。请使用提供的模板快速开始。

> [!TIP]
> 查看[这里](https://github.com/sergiudm/schedule_management/blob/main/docs/prompt)可以在几秒内生成你的日程配置。只需描述你的日常安排，LLM 即可为你创建结构化、可直接使用的配置文件。

#### 1. 全局设置（`settings.toml`）

在此配置全局行为、可复用的时间块和提醒消息：

```toml
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"
alarm_interval = 5        # 重复提醒间隔（秒）
max_alarm_duration = 300  # 最长提醒时长（5 分钟）

[time_blocks]
pomodoro = 25
long_break = 40
meeting = 50
exercise = 30
lunch = 60
napping = 30

[time_points]
go_to_bed = "上床睡觉 😴 该休息了！"
summary_time = "今天的工作结束 🎉, 总结一下"
```

#### 2. 周计划（`odd_weeks.toml` 与 `even_weeks.toml`）

通过按天划分的区段和 `[common]` 通用区段定义你的每周节奏。

##### 支持的事件类型：

| 类型 | 示例 | 说明 |
|------|--------|-------------|
| **时间段引用** | `"09:00" = "pomodoro"` | 触发开始+结束提醒（25 分钟） |
| **时间点引用** | `"22:45" = "go_to_bed"` | 一次性提醒 |
| **直接消息** | `"12:00" = "Lunch time! 🍽️"` | 立即弹出自定义文本提醒 |
| **带标题的时间块** | `"14:00" = { block = "meeting", title = "团队站会" }` | 为时间段添加自定义标题 |

##### 示例日程：

```toml
[monday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"13:00" = { block = "meeting", title = "Sprint 规划会" }

[common]  # 适用于所有日期
"19:30" = "pomodoro"
"21:00" = "summary_time"
"22:45" = "go_to_bed"
```

> [!WARNING]  
> **请避免时间段重叠！** 例如，09:00 开始的 25 分钟番茄钟会在 09:25 结束。请勿在此期间安排其他时间段事件，否则可能导致提醒冲突。

---

#### 🚀 设置

1. **初始化配置文件**：
   ```bash
   cp config/settings_template.toml config/settings.toml
   cp config/week_schedule_template.toml config/odd_weeks.toml
   cp config/week_schedule_template.toml config/even_weeks.toml
   ```

2. **编辑 `config/` 目录下的 TOML 文件**，按你的习惯调整日程。

> [!IMPORTANT]  
> 系统实际读取以下文件：  
> - `config/settings.toml`  
> - `config/odd_weeks.toml`  
> - `config/even_weeks.toml`  
> 模板文件仅作参考，不会被程序读取。

---

### 📦 部署方式

```bash
./install.sh
```
> [!NOTE]
> 根据脚本输出的指引，你可能需要运行 `launchctl load ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist`。然后运行 `launchctl list|grep schedule` 检查服务是否正在运行。

卸载方法：
```bash
launchctl unload ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist
rm -rf "$HOME/schedule_management"
```

---

### 🛠️ 命令行工具（CLI）

运行安装脚本（`install.sh`）后，你将获得 `reminder` 命令。

#### 设置（添加到 Shell 配置）
将以下内容加入 `~/.zshrc` 或 `~/.bash_profile`：

```bash
export PATH="$HOME/schedule_management:$PATH"
export REMINDER_CONFIG_DIR="$HOME/schedule_management/config"
alias reminder="$HOME/schedule_management/reminder"
```

然后重载 Shell 配置：
```bash
source ~/.zshrc  # 或 source ~/.bash_profile
```

#### 常用命令

##### 日程管理
| 命令 | 说明 |
|------|------|
| `reminder update` | 重新加载配置并重启后台服务 |
| `reminder view` | 生成日程可视化图表 |
| `reminder status` | 显示即将到来的下一项事件 |
| `reminder status -v` | 显示完整日程详情 |
| `reminder stop` | 停止后台提醒服务 |

##### 任务管理
| 命令 | 说明 |
|------|------|
| `reminder add "任务描述" 重要性` | 添加新任务或更新现有任务的重要性级别 |
| `reminder rm "任务描述"` | 根据描述删除任务 |
| `reminder ls` | 按重要性排序显示所有任务（重要性高的优先） |

**任务管理示例：**
```bash
# 添加具有重要性级别的任务（数字越大越重要）
reminder add "生物作业" 8
reminder add "买菜" 3
reminder add "给妈妈打电话" 5

# 更新现有任务（替换旧的重要性级别）
reminder add "生物作业" 10

# 查看按重要性排序的所有任务
reminder ls

# 删除特定任务
reminder rm "买菜"
```

> [!TIP]
> **任务管理功能：**
> - **无重复**：添加已存在的任务名称会更新其重要性级别
> - **智能排序**：任务始终按重要性显示（重要性高的优先）
> - **持久化**：任务存储在 `config/tasks.json` 中，跨 CLI 会话持久保存
> - **时间戳**：每个任务都包含创建/更新时间供参考

---

## 🗺️ 未来计划

- [x] 时间点提醒
- [x] 默认日程模板
- [x] 日程可视化
- [x] 安装脚本
- [x] 跳过某天逻辑
- [x] CLI 工具
- [x] 具有重要性级别的任务管理系统
- [x] 用于 LLM 生成 TOML 配置的提示词
- [ ] 更美观的提醒UI
- [ ] **跨平台支持**（Linux & Windows）

---

## 📄 许可证

本项目采用 **MIT 许可证** 发布。详情请参见 [LICENSE](LICENSE) 文件。

---

> 💡 **小贴士**：搭配数字健康习惯使用效果更佳——记得多喝水、定时拉伸、真正休息！未来的你会感谢现在的自己。