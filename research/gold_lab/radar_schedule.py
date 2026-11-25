"""Prepare a disabled radar task, or explicitly register the selected pilot on Windows."""

import argparse
from pathlib import Path
import subprocess
import sys

from .data import ROOT, write_atomic
from .radar import ROOT as CACHE
from .radar_model import load_frozen
from .schedule import definition

TASK = "AurumAI-Risk-Radar-Pilot"


def artifact(python, *, activate=False, telegram=False):
    args = "-m research.gold_lab.radar once --cohort pilot"
    if telegram:
        args += " --send-research-telegram"
    # The extra hour and quarter lets the last forecast mature and writes the
    # daily summary at 00:15 Tripoli. New issuance still closes at 23:00.
    return definition(
        python, ROOT, arguments=args, duration="PT15H16M", enabled=activate
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "activate", "stop"])
    parser.add_argument("--telegram", action="store_true")
    args = parser.parse_args()
    if args.telegram and args.action != "activate":
        parser.error("--telegram requires activate")
    if args.action == "stop":
        subprocess.run(["schtasks.exe", "/Change", "/TN", TASK, "/Disable"], check=True)
        return
    load_frozen()
    activate = args.action == "activate"
    path = CACHE / ("radar-active.xml" if activate else "radar-disabled.xml")
    write_atomic(
        path, artifact(Path(sys.executable), activate=activate, telegram=args.telegram)
    )
    if activate:
        subprocess.run(
            ["schtasks.exe", "/Create", "/TN", TASK, "/XML", str(path), "/F"], check=True
        )
    print(path)


if __name__ == "__main__":
    main()
