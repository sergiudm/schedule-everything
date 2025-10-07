
---
sidebar_position: 4
---

# Configuration Templates

This page provides ready-to-use configuration templates for different use cases and lifestyles.

## Developer Template

Perfect for software developers following agile methodologies.

### settings.toml
```toml
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"
alarm_interval = 5
max_alarm_duration = 300

[time_blocks]
pomodoro = 25
long_break = 40
short_break = 5
meeting = 50
code_review = 30
planning = 20
standup = 15
deep_work = 90

[time_points]
go_to_bed = "Time to wind down and get ready for bed 😴"
summary_time = "Great work today! Time to summarize your accomplishments 🎉"
standup_time = "Daily standup meeting starts now 👥"
code_review_time = "Time to review pull requests 🔍"
lunch_time = "Lunch break! Time to recharge 🍽️"
```

### odd_weeks.toml
```toml
[monday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"10:30" = "pomodoro"
"11:30" = "long_break"
"13:00" = { block = "standup", title = "Team Standup" }
"14:00" = "pomodoro"
"15:00" = "long_break"
"16:00" = "pomodoro"

[tuesday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"10:30" = "pomodoro"
"11:30" = "long_break"
"14:00" = { block = "planning", title = "Sprint Planning" }
"15:00" = "pomodoro"
"16:00" = "long_break"

[wednesday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"10:30" = "pomodoro"
"11:30" = "long_break"
"13:00" = { block = "standup", title = "Team Standup" }
"14:00" = "pomodoro"

[thursday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"10:30" = "pomodoro"
"11:30" = "long_break"
"15:00" = { block = "code_review", title = "Code Review Session" }

[friday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"10:30" = "pomodoro"
"11:30" = "long_break"
"14:00" = { block = "meeting", title = "Demo Day" }
"15:00" = "pomodoro"

[common]
"12:00" = "lunch_time"
"15:30" = "Time to stretch and hydrate 🧘"
"21:00" = "summary_time"
"22:45" = "go_to_bed"
```

## Student Template

Ideal for students managing classes, study sessions, and assignments.

### settings.toml
```toml
[settings]
sound_file = "/System/Library/Sounds/Glass.aiff"
alarm_interval = 5
max_alarm_duration = 300

[time_blocks]
study_session = 45
short_break = 10
long_break = 30
class_time = 90
lab_session = 120
review_session = 30
group_study = 60

[time_points]
wake_up = "Good morning! Time to start your day 📚"
class_reminder = "Class starts soon! Get ready 🎓"
study_time = "Time to focus on your studies 📖"
lunch_time = "Lunch break! Time to recharge 🍽️"
dinner_time = "Dinner time! Take a break 🍽️"
bed_time = "Time to rest and prepare for tomorrow 😴"
assignment_due = "Don't forget about your assignment! 📝"
```

### even_weeks.toml
```toml
[monday]
"07:00" = "wake_up"
"08:00" = "class_reminder"
"09:00" = { block = "class_time", title = "Mathematics Lecture" }
"11:00" = "short_break"
"11:30" = { block = "study_session", title = "Math Study Session" }
"13:00" = "l