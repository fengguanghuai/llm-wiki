"""Configurable scheduled sync task generator (v1.0 · #162).

Generates OS-specific scheduled task definitions from a single config.
Users pick a cadence (daily/weekly/hourly) and a time, and this module
emits a ready-to-install config for:

  - macOS launchd (``.plist``)
  - Linux systemd timer + service (``.timer`` + ``.service``)
  - Windows Task Scheduler (``.xml``)

Reads schedule from ``sessions_config.json``::

    "scheduled_sync": {
      "enabled": false,
      "cadence": "daily",        // daily | weekly | hourly
      "hour": 3,                 // 0-23 (for daily/weekly)
      "minute": 0,               // 0-59
      "weekday": 0,              // 0=Sunday (weekly only)
      "working_dir": "/path/to/llm-wiki",
      "llmwiki_bin": "/usr/local/bin/llmwiki"
    }
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Optional


def load_sync_schedule(config: dict[str, Any]) -> dict[str, Any]:
    """Extract scheduled_sync config with defaults."""
    sc = config.get("scheduled_sync", {})
    return {
        "enabled": sc.get("enabled", False),
        "cadence": sc.get("cadence", "daily").lower(),
        "hour": int(sc.get("hour", 3)),
        "minute": int(sc.get("minute", 0)),
        "weekday": int(sc.get("weekday", 0)),
        "working_dir": sc.get("working_dir", str(Path.home() / "llm-wiki")),
        "llmwiki_bin": sc.get("llmwiki_bin", "/usr/local/bin/llmwiki"),
    }


def detect_platform() -> str:
    """Return ``macos``, ``linux``, ``windows``, or ``unknown``."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return "unknown"


# ─── launchd (macOS) ──────────────────────────────────────────────────

def render_launchd_plist(sched: dict[str, Any]) -> str:
    """Render a launchd .plist from schedule config."""
    hour = sched["hour"]
    minute = sched["minute"]
    interval_xml = f"""<dict>
      <key>Hour</key>
      <integer>{hour}</integer>
      <key>Minute</key>
      <integer>{minute}</integer>
    </dict>"""
    if sched["cadence"] == "weekly":
        interval_xml = f"""<dict>
      <key>Weekday</key>
      <integer>{sched["weekday"]}</integer>
      <key>Hour</key>
      <integer>{hour}</integer>
      <key>Minute</key>
      <integer>{minute}</integer>
    </dict>"""
    elif sched["cadence"] == "hourly":
        interval_xml = """<integer>3600</integer>"""

    interval_key = (
        "StartInterval" if sched["cadence"] == "hourly" else "StartCalendarInterval"
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.llmwiki.sync</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sched["llmwiki_bin"]}</string>
    <string>sync</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{sched["working_dir"]}</string>
  <key>{interval_key}</key>
  {interval_xml}
  <key>StandardOutPath</key>
  <string>/tmp/llmwiki-sync.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/llmwiki-sync.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
"""


# ─── systemd (Linux) ──────────────────────────────────────────────────

def render_systemd_service(sched: dict[str, Any]) -> str:
    return f"""[Unit]
Description=llmwiki scheduled sync
After=network.target

[Service]
Type=oneshot
WorkingDirectory={sched["working_dir"]}
ExecStart={sched["llmwiki_bin"]} sync
StandardOutput=append:/tmp/llmwiki-sync.log
StandardError=append:/tmp/llmwiki-sync.log

[Install]
WantedBy=multi-user.target
"""


_WEEKDAYS_SYSTEMD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def render_systemd_timer(sched: dict[str, Any]) -> str:
    cadence = sched["cadence"]
    hour = sched["hour"]
    minute = sched["minute"]

    if cadence == "hourly":
        on_calendar = "hourly"
    elif cadence == "weekly":
        wd = _WEEKDAYS_SYSTEMD[sched["weekday"] % 7]
        on_calendar = f"{wd} *-*-* {hour:02d}:{minute:02d}:00"
    else:  # daily
        on_calendar = f"*-*-* {hour:02d}:{minute:02d}:00"

    return f"""[Unit]
Description=llmwiki scheduled sync timer

[Timer]
OnCalendar={on_calendar}
Persistent=true
Unit=llmwiki-sync.service

[Install]
WantedBy=timers.target
"""


# ─── Task Scheduler (Windows) ─────────────────────────────────────────

def render_windows_task(sched: dict[str, Any]) -> str:
    cadence = sched["cadence"]
    hour = sched["hour"]
    minute = sched["minute"]
    start_time = f"2026-04-01T{hour:02d}:{minute:02d}:00"

    if cadence == "hourly":
        trigger = f"""    <TimeTrigger>
      <Repetition>
        <Interval>PT1H</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>{start_time}</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>"""
    elif cadence == "weekly":
        trigger = f"""    <CalendarTrigger>
      <StartBoundary>{start_time}</StartBoundary>
      <ScheduleByWeek>
        <DaysOfWeek><Sunday /></DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>"""
    else:
        trigger = f"""    <CalendarTrigger>
      <StartBoundary>{start_time}</StartBoundary>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>"""

    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
{trigger}
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>{sched["llmwiki_bin"]}</Command>
      <Arguments>sync</Arguments>
      <WorkingDirectory>{sched["working_dir"]}</WorkingDirectory>
    </Exec>
  </Actions>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
</Task>
"""


# ─── Dispatch ─────────────────────────────────────────────────────────

def generate(
    platform_name: str,
    config: dict[str, Any],
) -> dict[str, str]:
    """Return a dict mapping output filename → content for the platform.

    Platforms: ``macos``, ``linux``, ``windows``.
    """
    sched = load_sync_schedule(config)
    if platform_name == "macos":
        return {"com.llmwiki.sync.plist": render_launchd_plist(sched)}
    if platform_name == "linux":
        return {
            "llmwiki-sync.service": render_systemd_service(sched),
            "llmwiki-sync.timer": render_systemd_timer(sched),
        }
    if platform_name == "windows":
        return {"llmwiki-sync-task.xml": render_windows_task(sched)}
    return {}


def install_instructions(platform_name: str) -> str:
    """Return copy-paste install instructions for the platform."""
    if platform_name == "macos":
        return (
            "# macOS (launchd)\n"
            "cp com.llmwiki.sync.plist ~/Library/LaunchAgents/\n"
            "launchctl load ~/Library/LaunchAgents/com.llmwiki.sync.plist\n"
            "# Verify: launchctl list | grep llmwiki\n"
        )
    if platform_name == "linux":
        return (
            "# Linux (systemd user unit)\n"
            "mkdir -p ~/.config/systemd/user\n"
            "cp llmwiki-sync.service llmwiki-sync.timer ~/.config/systemd/user/\n"
            "systemctl --user daemon-reload\n"
            "systemctl --user enable --now llmwiki-sync.timer\n"
            "# Verify: systemctl --user list-timers | grep llmwiki\n"
        )
    if platform_name == "windows":
        return (
            "# Windows (Task Scheduler)\n"
            "schtasks /Create /XML llmwiki-sync-task.xml /TN \\llmwiki\\sync\n"
            "# Verify: schtasks /Query /TN \\llmwiki\\sync\n"
        )
    return "# Unsupported platform\n"
