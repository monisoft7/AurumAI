"""Prepare (only write XML) a disabled Task Scheduler definition on the durable Windows host."""

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from .data import CACHE, ROOT, write_atomic


def definition(python, root):
    ns = "http://schemas.microsoft.com/windows/2004/02/mit/task"
    ET.register_namespace("", ns)
    task = ET.Element("Task", xmlns=ns, version="1.2")

    def node(parent, name, text=None, **attrs):
        elem = ET.SubElement(parent, name, attrs)
        elem.text = text
        return elem

    trigger = node(node(task, "Triggers"), "CalendarTrigger")
    repeat = node(trigger, "Repetition")
    node(repeat, "Interval", "PT15M")
    node(repeat, "Duration", "PT14H1M")
    node(trigger, "StartBoundary", "2026-01-05T07:00:00Z")
    week = node(trigger, "ScheduleByWeek")
    days = node(week, "DaysOfWeek")
    for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        node(days, day)
    node(week, "WeeksInterval", "1")
    principal = node(node(task, "Principals"), "Principal", id="Research")
    node(principal, "LogonType", "InteractiveToken")
    node(principal, "RunLevel", "LeastPrivilege")
    settings = node(task, "Settings")
    node(settings, "MultipleInstancesPolicy", "IgnoreNew")
    node(settings, "StartWhenAvailable", "false")
    node(settings, "Enabled", "false")
    node(settings, "ExecutionTimeLimit", "PT5M")
    action = node(node(task, "Actions", Context="Research"), "Exec")
    node(action, "Command", str(python))
    node(action, "Arguments", "-m research.gold_lab.shadow once")
    node(action, "WorkingDirectory", str(root))
    return ET.tostring(task, encoding="utf-16", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CACHE / "shadow-disabled.xml")
    args = parser.parse_args()
    write_atomic(args.output, definition(sys.executable, ROOT))
    print(args.output)
