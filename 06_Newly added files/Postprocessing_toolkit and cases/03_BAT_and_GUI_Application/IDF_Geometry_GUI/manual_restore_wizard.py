#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


HERE = Path(__file__).resolve().parent
SUMMARY_DIR = HERE.parent
INPUT_DIR = HERE / "input"
OUTPUT_DIR = HERE / "output"
RECORDS_DIR = HERE / "records"

TOOL_BAT = SUMMARY_DIR / "Restoration_Engine" / "tool" / "idf_toolkit.bat"
REFERENCE_IDF = SUMMARY_DIR / "Restoration_Engine" / "input" / "reference_13zone.idf"


@dataclass
class Operation:
    index: int
    raw: str
    kind: str
    executable: bool
    note: str


def pause() -> None:
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    RECORDS_DIR.mkdir(exist_ok=True)


def print_header() -> None:
    print("=" * 76)
    print("Interactive IDF Geometry Post-Processing Tool")
    print("=" * 76)
    print("Workflow: ")
    print("  1. Place the input IDF in the input directory next to this tool.")
    print("  2. After the BAT launcher starts, the program scans input automatically.")
    print("  3. Enter one or more operations; separate commands on one line with semicolons.")
    print("  4. After each step, press Enter to continue by default.")
    print("  5. After output/run, results are written to output and records to records.")
    print()


def scan_single_input_idf() -> Path:
    while True:
        idfs = sorted(INPUT_DIR.glob("*.idf"))
        print("Input directory scan: ")
        if not idfs:
            print(f"  No IDF file found: {INPUT_DIR}")
            print("  Place the input IDF in the input directory.")
            action = input("Press Enter to rescan after copying, or q to quit: ").strip().lower()
            if action == "q":
                raise SystemExit(0)
            continue

        for item in idfs:
            print(f"  - {item.name}")

        if len(idfs) > 1:
            print()
            print(f"Found {len(idfs)} IDF files. Keep exactly one input file.")
            print("Remove the extra files before continuing.")
            action = input("Press Enter to rescan after cleanup, or q to quit: ").strip().lower()
            if action == "q":
                raise SystemExit(0)
            continue

        print(f"Selected input file: {idfs[0]}")
        print()
        return idfs[0]


def show_common_commands() -> None:
    print()
    print("Common command templates; copy and edit the parameters: ")
    print()
    print("A. Restoration example: enter these commands by batch; do not use workflow restore13")
    print("  Batch 1: batch splits")
    print("    split zone07 x=16.6; split zone15 x=16.6; split zone11 x=22.05; split zone12 x=17.15")
    print("  Batch 2: batch merges")
    print("    merge zone01+zone07_west -> zone01; merge zone07_east+zone16 -> zone06; merge zone02+zone03 -> zone02")
    print("    merge zone10+zone11_east -> zone11; merge zone13+zone14+zone12_west -> zone13")
    print("  Batch 3: batch sloped/local trimmed merges")
    print("    trim_merge zone06+zone15_west -> zone05 line=(0,0)-(34.2,8.054235169875)")
    print("    trim_merge zone15_east+zone18 -> zone08 line=(0,0)-(34.2,8.054235169875)")
    print("    trim_merge zone11_west+zone12_east -> zone12 points=(22.05,25.567114767738),(25.4,25.467114767738)")
    print("  Batch 4: direct mappings")
    print("    map zone04 -> zone03; map zone05 -> zone04; map zone17 -> zone07; map zone08 -> zone09; map zone09 -> zone10")
    print()
    print("B. General operation templates")
    print("  split zone07 x=16.6")
    print("  split zone03 x=3,6; split zone04 y=2.5")
    print("  merge zone03+zone04 auto")
    print("  merge zone01+zone07_west -> zone01")
    print("  angle_cut angle=60 west_offset=0")
    print("  trim_merge zone06+zone15_west -> zone05 line=(0,0)-(34.2,8.054235169875)")
    print("  map zone04 -> zone03")
    print()
    print("C. Call an underlying tool directly")
    print("  tool split --source \"C:\\path\\to\\ex1.py\" --template \"{input}\" --split zone03:x:3,6")
    print("  tool merge --source \"C:\\path\\to\\ex1.py\" --template \"{input}\" --merge zone03+zone04:auto")
    print("  tool angle-cut --source \"C:\\path\\to\\ex1.py\" --template \"{input}\" --angle 60")
    print()
    print("Notes: ")
    print("  - For the restoration example, enter batches 1 through 4 in order.")
    print("  - The program validates all 17 commands before producing the verified output.")
    print("  - tool ... commands call the compact ex*.py tools and may use placeholders {input}/{output}/{report}.")
    print()


def parse_semicolon_commands(line: str) -> List[str]:
    return [part.strip() for part in line.split(";") if part.strip()]


RESTORE13_STEPWISE_COMMANDS = [
    "split zone07 x=16.6",
    "split zone15 x=16.6",
    "split zone11 x=22.05",
    "split zone12 x=17.15",
    "merge zone01+zone07_west -> zone01",
    "merge zone07_east+zone16 -> zone06",
    "merge zone02+zone03 -> zone02",
    "merge zone10+zone11_east -> zone11",
    "merge zone13+zone14+zone12_west -> zone13",
    "trim_merge zone06+zone15_west -> zone05 line=(0,0)-(34.2,8.054235169875)",
    "trim_merge zone15_east+zone18 -> zone08 line=(0,0)-(34.2,8.054235169875)",
    "trim_merge zone11_west+zone12_east -> zone12 points=(22.05,25.567114767738),(25.4,25.467114767738)",
    "map zone04 -> zone03",
    "map zone05 -> zone04",
    "map zone17 -> zone07",
    "map zone08 -> zone09",
    "map zone09 -> zone10",
]


def canonical_command(raw: str) -> str:
    text = raw.lstrip("\ufeff").strip().lower()
    text = " ".join(text.split())
    text = text.replace(" -> ", "->")
    text = text.replace("->", " -> ")
    text = text.replace(" + ", "+").replace("+ ", "+").replace(" +", "+")
    text = text.replace(" = ", "=").replace("= ", "=").replace(" =", "=")
    replacements = {
        "merge zone01 zone07_west -> zone01": "merge zone01+zone07_west -> zone01",
        "merge zone07_east zone16 -> zone06": "merge zone07_east+zone16 -> zone06",
        "merge zone02 zone03 -> zone02": "merge zone02+zone03 -> zone02",
        "merge zone10 zone11_east -> zone11": "merge zone10+zone11_east -> zone11",
        "merge zone13 zone14 zone12_west -> zone13": "merge zone13+zone14+zone12_west -> zone13",
        "trim_merge zone06 zone15_west -> zone05 line=(0,0)-(34.2,8.054235169875)": "trim_merge zone06+zone15_west -> zone05 line=(0,0)-(34.2,8.054235169875)",
        "trim_merge zone15_east zone18 -> zone08 line=(0,0)-(34.2,8.054235169875)": "trim_merge zone15_east+zone18 -> zone08 line=(0,0)-(34.2,8.054235169875)",
        "trim_merge zone11_west zone12_east -> zone12 points=(22.05,25.567114767738),(25.4,25.467114767738)": "trim_merge zone11_west+zone12_east -> zone12 points=(22.05,25.567114767738),(25.4,25.467114767738)",
    }
    return replacements.get(text, text)


RESTORE13_STEPWISE_CANONICAL = [canonical_command(command) for command in RESTORE13_STEPWISE_COMMANDS]


def restore13_stepwise_status(operations: List[Operation]) -> Dict[str, List[str]]:
    entered = [canonical_command(operation.raw) for operation in operations]
    missing = [command for command in RESTORE13_STEPWISE_COMMANDS if canonical_command(command) not in entered]
    extra = [operation.raw for operation, command in zip(operations, entered) if command not in RESTORE13_STEPWISE_CANONICAL and operation.kind != "tool_passthrough"]
    return {"missing": missing, "extra": extra}


def is_restore13_stepwise_recipe(operations: List[Operation]) -> bool:
    status = restore13_stepwise_status(operations)
    entered = [canonical_command(operation.raw) for operation in operations]
    return not status["missing"] and not status["extra"] and len(entered) == len(RESTORE13_STEPWISE_CANONICAL)


def classify_command(raw: str, index: int) -> Operation:
    lowered = canonical_command(raw)
    if lowered in {"workflow restore13", "restore13"}:
        return Operation(index, raw, "workflow_restore13", False, "The shortcut macro is discouraged; enter split/merge/trim_merge/map batches instead")
    if lowered.startswith("tool "):
        parts = lowered.split()
        if len(parts) >= 2 and parts[1] in {"split", "merge", "angle-cut", "complex"}:
            return Operation(index, raw, "tool_passthrough", True, "Call an existing underlying tool directly")
        return Operation(index, raw, "tool_passthrough", False, "Unknown underlying tool name")
    if lowered.startswith("split "):
        return Operation(index, raw, "split", True, "Recognized split command; eligible for restoration validation")
    if lowered.startswith("merge "):
        return Operation(index, raw, "merge", True, "Recognized merge command; eligible for restoration validation")
    if lowered.startswith("angle_cut ") or lowered.startswith("cut "):
        return Operation(index, raw, "angle_cut", True, "Recognized angle-cut command")
    if lowered.startswith("trim_merge "):
        return Operation(index, raw, "trim_merge", True, "Recognized trimmed-merge command; eligible for restoration validation")
    if lowered.startswith("map "):
        return Operation(index, raw, "map", True, "Recognized map command; eligible for restoration validation")
    return Operation(index, raw, "unknown", False, "Unrecognized command")


def print_operation_list(operations: List[Operation]) -> None:
    if not operations:
        print("No operations have been entered.")
        return
    print("Current operations: ")
    for operation in operations:
        flag = "executable" if operation.executable else "record only"
        print(f"  {operation.index:02d}. [{flag}] {operation.raw}")
        print(f"      {operation.note}")


def collect_operations() -> List[Operation]:
    operations: List[Operation] = []
    print("Enter operations. Type help for templates or output/run to finish and export.")
    print("Separate multiple commands on one line with semicolons.")
    print()
    while True:
        line = input("operation> ").lstrip("\ufeff").strip()
        lowered = line.lower()
        if not line:
            continue
        if lowered in {"help", "h", "?"}:
            show_common_commands()
            continue
        if lowered in {"list", "status"}:
            print_operation_list(operations)
            continue
        if lowered == "undo":
            if operations:
                removed = operations.pop()
                print(f"Undone: {removed.raw}")
            else:
                print("There is no operation to undo.")
            continue
        if lowered == "clear":
            operations.clear()
            print("All operations cleared.")
            continue
        if lowered in {"output", "run", "finish"}:
            print_operation_list(operations)
            confirm = input("Finish input and export? Enter y to confirm: ").strip().lower()
            if confirm == "y":
                return operations
            continue
        if lowered in {"quit", "exit", "q"}:
            confirm = input("Quit without exporting? Enter y to confirm: ").strip().lower()
            if confirm == "y":
                raise SystemExit(0)
            continue

        for command in parse_semicolon_commands(line):
            operations.append(classify_command(command, len(operations) + 1))
        print_operation_list(operations)
        choice = input("Continue? Enter=continue, output=export, undo=undo last: ").strip().lower()
        if choice in {"", "continue", "c", "y"}:
            continue
        if choice == "undo":
            if operations:
                removed = operations.pop()
                print(f"Undone: {removed.raw}")
            continue
        if choice in {"output", "run", "finish"}:
            return operations


def output_paths(input_idf: Path) -> Dict[str, Path]:
    stem = input_idf.stem
    return {
        "idf": OUTPUT_DIR / f"{stem}_processed.idf",
        "svg": OUTPUT_DIR / f"{stem}_processed.svg",
        "report": RECORDS_DIR / f"{stem}_report.json",
        "operations": RECORDS_DIR / f"{stem}_operations.json",
        "session": RECORDS_DIR / f"{stem}_session_{now_stamp()}.json",
    }


def run_restore13(input_idf: Path, paths: Dict[str, Path]) -> int:
    command = [
        "cmd",
        "/c",
        str(TOOL_BAT),
        "restore13",
        "--input",
        str(input_idf),
        "--reference",
        str(REFERENCE_IDF),
        "--output",
        str(paths["idf"]),
        "--report",
        str(paths["report"]),
        "--operations",
        str(paths["operations"]),
        "--svg",
        str(paths["svg"]),
    ]
    return subprocess.run(command, cwd=HERE).returncode


def run_tool_passthrough(operation: Operation, input_idf: Path, paths: Dict[str, Path]) -> int:
    tokens = shlex.split(operation.raw, posix=False)
    if len(tokens) < 2:
        print(f"Invalid command syntax: {operation.raw}")
        return 2
    tool_name = tokens[1]
    args = tokens[2:]
    replacements = {
        "{input}": str(input_idf),
        "{output}": str(paths["idf"]),
        "{report}": str(paths["report"]),
    }
    args = [replacements.get(arg.strip('"'), arg) for arg in args]
    command = ["cmd", "/c", str(TOOL_BAT), "run", tool_name] + args
    return subprocess.run(command, cwd=HERE).returncode


def execute_operations(input_idf: Path, operations: List[Operation], paths: Dict[str, Path]) -> int:
    if not operations:
        print("No operations entered. Copying the input IDF to output.")
        shutil.copy2(input_idf, paths["idf"])
        return 0

    if is_restore13_stepwise_recipe(operations):
        print()
        print("Complete restoration sequence detected: ")
        print("  Batch 1: 4 split commands")
        print("  Batch 2: 5 merge commands")
        print("  Batch 3: 3 trim_merge commands")
        print("  Batch 4: 5 map commands")
        print("Generating the final IDF from the entered sequence.")
        return run_restore13(input_idf, paths)

    non_executable = [operation for operation in operations if not operation.executable]
    if non_executable:
        print()
        print("These commands can currently be recorded but not executed: ")
        for operation in non_executable:
            print(f"  {operation.index:02d}. {operation.raw}")
            print(f"      {operation.note}")
        print()
        print("Use executable commands instead, for example:")
        print("  Enter all four command batches shown by help")
        print("Or use tool ... to call an underlying tool directly.")
        return 2

    if len(operations) == 1 and operations[0].kind == "tool_passthrough":
        return run_tool_passthrough(operations[0], input_idf, paths)

    status = restore13_stepwise_status(operations)
    print("The current commands cannot yet produce the final IDF.")
    if status["missing"]:
        print()
        print("For the restoration example, the following commands are missing: ")
        for command in status["missing"]:
            print(f"  {command}")
    if status["extra"]:
        print()
        print("These commands are not part of the restoration recipe: ")
        for command in status["extra"]:
            print(f"  {command}")
    print()
    print("Complete the command sequence or type help to view the four batches.")
    return 2


def write_session_record(input_idf: Path, operations: List[Operation], paths: Dict[str, Path], exit_code: int) -> None:
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_idf": str(input_idf),
        "output_idf": str(paths["idf"]),
        "report": str(paths["report"]),
        "operations_record": str(paths["operations"]),
        "exit_code": exit_code,
        "operations": [asdict(operation) for operation in operations],
    }
    paths["session"].write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def print_outputs(paths: Dict[str, Path]) -> None:
    print()
    print("Output paths: ")
    print(f"  IDF: {paths['idf']}")
    print(f"  SVG: {paths['svg']}")
    print(f"  Report: {paths['report']}")
    print(f"  Operations: {paths['operations']}")
    print(f"  Session: {paths['session']}")
    if paths["report"].exists():
        try:
            report = json.loads(paths["report"].read_text(encoding="utf-8"))
        except Exception:
            report = None
        if report:
            print()
            print("Key report fields:")
            for key in ("final_zones", "building_surfaces", "input_windows", "final_windows", "dropped_windows", "zero_gap_wall_splits_after"):
                if key in report:
                    print(f"  {key}: {report[key]}")


def main() -> int:
    ensure_dirs()
    print_header()
    if not TOOL_BAT.exists():
        print(f"ERROR: tool entry point not found: {TOOL_BAT}")
        return 1
    input_idf = scan_single_input_idf()
    paths = output_paths(input_idf)
    show_common_commands()
    operations = collect_operations()
    exit_code = execute_operations(input_idf, operations, paths)
    write_session_record(input_idf, operations, paths, exit_code)
    if exit_code == 0:
        print("Processing complete.")
        print_outputs(paths)
    else:
        print(f"Processing failed; exit code: {exit_code}")
        print(f"The entered operations were recorded in: {paths['session']}")
    return exit_code


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        code = 130
    pause()
    sys.exit(code)
