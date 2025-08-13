import time
import subprocess
from datetime import datetime

# ===== 配置 =====
SOUND_FILE = "/System/Library/Sounds/Ping.aiff"  # 可以换成其他音效
ALARM_INTERVAL = 30   # 闹铃间隔秒数
MAX_ALARM_DURATION = 5 * 60  # 闹铃最长持续秒数（这里是 5 分钟）

# 时间表
schedule = {
    "08:05": "起床啦！",
    "08:30": "早餐时间 🍳",
    "09:10": "第1个番茄",
    "09:35": "第1个番茄结束,休息5min",
    "09:40": "第2个番茄",
    "10:10": "休息一下 🚶 散步或适量运动",
    "10:50": "第3个番茄",
    "11:25": "第3个番茄结束,休息5min",
    "11:30": "第4个番茄",
    "11:55": "第4个番茄结束,休息5min",
    "12:00": "第5个番茄",
    "12:30": "上午工作结束，午餐时间 🍚",
    "14:00": "第6个番茄",
    "14:25": "第6个番茄结束,休息5min",
    "14:30": "第7个番茄",
    "15:00": "休息一下 🚶 散步或适量运动",
    "16:30": "第8个番茄",
    "16:55": "第8个番茄结束,休息5min",
    "17:00": "第9个番茄",
    "17:25": "第9个番茄结束,休息5min",
    "17:30": "第10个番茄",
    "18:00": "第10个番茄结束,休息",
    "18:30": "晚餐时间 🍽️",
    "20:00": "第11个番茄",
    "20:25": "第11个番茄结束,休息5min",
    "20:30": "第12个番茄",
    "21:00": "今天的工作结束 🎉, 总结一下",
    "22:45": "上床睡觉 😴"
}

# ===== 方法 =====
def play_sound():
    subprocess.Popen(["afplay", SOUND_FILE])

def show_dialog(message):
    # 返回 AppleScript 对话框的用户点击结果
    result = subprocess.run([
        "osascript", "-e",
        f'display dialog "{message}" buttons {{"停止闹铃"}} default button "停止闹铃"'
    ], capture_output=True, text=True)
    return result.stdout.strip()

def alarm(title, message):
    start_time = time.time()
    while True:
        # 播放声音
        play_sound()
        # 弹窗（阻塞等待用户点击）
        button = show_dialog(message)
        if "停止闹铃" in button:
            break
        # 检查是否超过最大闹铃时间
        if time.time() - start_time > MAX_ALARM_DURATION:
            break
        time.sleep(ALARM_INTERVAL)

# ===== 主循环 =====
notified_today = set()

while True:
    now = datetime.now().strftime("%H:%M")
    if now in schedule and now not in notified_today:
        alarm("作息提醒", schedule[now])
        notified_today.add(now)

    if now == "00:00":
        notified_today.clear()

    time.sleep(10)
