#!/usr/bin/env python3
"""
TNF_Scan: select a working directory, scan GES BARCODE, build Capture folders.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from GES_integration import mark_as_shot_GES
from setNextCaptureFolder import setNextCaptureFolder

GES_BARCODE_KEYS = ("ges barcode", "gesbarcode", "ges_barcode")
LOT_KEYS = ("lot #", "lot#", "lot number", "lot no", "lot")
IMAGE_KEYS = ("image file name", "image filename", "image_name")


def prompt_for_working_directory() -> Path:
    """macOS-friendly directory picker with CLI fallback."""
    if sys.platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(
                [
                    "osascript", "-e",
                    'return POSIX path of (choose folder with prompt "Select the session folder")',
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0 and result.stdout.strip():
                p = Path(result.stdout.strip().rstrip()).resolve()
                if p.is_dir():
                    return p
        except Exception:
            pass
    else:
        try:
            os.environ["TK_SILENCE_DEPRECATION"] = "1"
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.update()
            selected = filedialog.askdirectory(title="Select the session folder")
            root.destroy()
            if selected:
                p = Path(selected).expanduser().resolve()
                if p.is_dir():
                    return p
        except Exception:
            pass

    while True:
        raw = input("Enter the full path to the session folder: ").strip()
        if not raw:
            print("Please enter a path (or press Ctrl+C to cancel).")
            continue
        p = Path(raw).expanduser()
        try:
            p = p.resolve()
        except Exception:
            print(f"Couldn't resolve path: {p}")
            continue
        if not p.exists():
            create = input(f"Folder does not exist. Create it?\n  {p}\n(y/N): ").strip().lower()
            if create == "y":
                try:
                    p.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    print(f"Failed to create folder: {e}")
                    continue
            else:
                continue
        if not p.is_dir():
            print("That path is not a directory. Try again.")
            continue
        return p


def pick_csv_file(working_dir: Path) -> Path:
    """Choose a CSV in working_dir (auto-picks if only one)."""
    csvs = sorted(working_dir.glob("*.csv"))
    if len(csvs) == 1:
        print(f"Using CSV: {csvs[0].name}")
        return csvs[0]
    if len(csvs) == 0:
        path = input("No CSV found. Enter path to CSV: ").strip()
        return Path(path).expanduser().resolve()
    print("Multiple CSV files found:")
    for idx, p in enumerate(csvs, 1):
        print(f"  {idx}. {p.name}")
    while True:
        choice = input("Select CSV by number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(csvs):
            return csvs[int(choice) - 1]
        print("Invalid choice, try again.")


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            normalized = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
            rows.append(normalized)
        return rows


def first_match_lot(rows: list[dict[str, str]], scanner_input: str) -> str | None:
    """Return lot number from the first row whose GES BARCODE contains scanner_input."""
    s = scanner_input.lower()
    for row in rows:
        ge_val = next((row.get(k, "") for k in GES_BARCODE_KEYS if k in row), "")
        if s in ge_val.lower():
            lot_val = next((row.get(k, "") for k in LOT_KEYS if k in row), "")
            if lot_val:
                return lot_val
    return None


def rows_for_lot(rows: list[dict[str, str]], lot_num: str) -> list[dict[str, str]]:
    target = lot_num.lower()
    matches = []
    for row in rows:
        lot_val = next((row.get(k, "") for k in LOT_KEYS if k in row), "")
        if target == lot_val.lower():
            matches.append(row)
    return matches


def safe_name(name: str) -> str:
    return name.replace("/", "-").replace("\\", "-")


def next_counter(capture_dir: Path) -> int:
    max_seen = 0
    if not capture_dir.exists():
        return 1
    for child in capture_dir.iterdir():
        if child.is_dir():
            prefix = child.name.split("_", 1)[0]
            if len(prefix) == 3 and prefix.isdigit():
                max_seen = max(max_seen, int(prefix))
    return max_seen + 1


def process_one(
    scanner_input: str,
    rows: list[dict[str, str]],
    working_dir: Path,
    csv_path: Path,
) -> tuple[Path | None, Path | None, list[dict[str, str]] | None, list[Path] | None]:
    """Handle a single scan and folder creation. Returns (lot_folder, new_csv_path, new_rows, subfolders).
    If no match and CSV is missing, new_csv_path and new_rows are the re-picked CSV; otherwise they are None.
    subfolders is the list of subfolders created under lot_folder (None when no lot_folder)."""
    lot_num = first_match_lot(rows, scanner_input)
    if not lot_num:
        print(f"No rows found in {csv_path} where GES BARCODE contains: {scanner_input}")
        if not csv_path.exists():
            print("CSV file no longer exists. Choosing CSV again.")
            new_path = pick_csv_file(working_dir)
            new_rows = load_rows(new_path)
            return (None, new_path, new_rows, None)
        return (None, None, None, None)
    # print(f"Matched LOT #: {lot_num}")

    capture_dir = working_dir / "Capture"
    capture_dir.mkdir(exist_ok=True)

    counter = next_counter(capture_dir)
    lot_folder_name = f"{counter:03d}_{safe_name(lot_num)}"
    lot_folder = capture_dir / lot_folder_name
    lot_folder.mkdir(exist_ok=True)
    print(f"-{lot_folder.name}")

    matching_rows = rows_for_lot(rows, lot_num)
    subfolders_created: list[Path] = []
    if not matching_rows:
        print("No rows found with that LOT # for subfolder creation.")
        return (lot_folder, None, None, subfolders_created)

    for row in matching_rows:
        image_name = next((row.get(k, "") for k in IMAGE_KEYS if k in row), "")
        if not image_name:
            continue
        subfolder = lot_folder / safe_name(image_name)
        subfolder.mkdir(exist_ok=True)
        subfolders_created.append(subfolder)
        print(f"--{subfolder.name}")

    # Mark as shot in GES after successful folder creation
    mark_as_shot_GES(lot_num)
    return (lot_folder, None, None, subfolders_created)


def add_subfolder(lot_folder: Path, folder_name: str) -> None:
    """Add an additional subfolder to the last created lot_folder."""
    if not lot_folder or not lot_folder.exists():
        print("No previous lot folder found. Please scan a GES BARCODE first.")
        return
    
    # Extract lot name without the counter prefix (e.g., "001_LotName" -> "LotName")
    lot_name = lot_folder.name
    if "_" in lot_name:
        lot_name = lot_name.split("_", 1)[1]  # Take everything after the first underscore
    
    subfolder_name = f"{lot_name}-{safe_name(folder_name)}"
    subfolder = lot_folder / subfolder_name
    subfolder.mkdir(exist_ok=True)
    print(f"--{subfolder.name}") 


def main() -> int:
    working_dir = prompt_for_working_directory()
    os.chdir(working_dir)
    print(f"\nTNF_Scan working directory:\n  {working_dir}")

    csv_path = pick_csv_file(working_dir)
    rows = load_rows(csv_path)

    print("Scan or enter GES BARCODE. Type 'exit' to quit.")
    print("Type 'add <name>' to add a subfolder to the last created lot folder.")
  
    last_lot_folder: Path | None = None
    
    while True:
      
        scanner_input = input().strip()

        if scanner_input.lower() == "exit":
            print("Exiting.")
            break
        if not scanner_input:
            continue  # ignore blanks without prompting

        # Check for "add x" command
        if scanner_input.lower().startswith("add "):
            folder_name = scanner_input[4:].strip()  # Remove "add " prefix
            if folder_name:
                add_subfolder(last_lot_folder, folder_name)
            else:
                print("Please provide a folder name after 'add' (e.g., 'add x').")
            continue

        # Process normal GES BARCODE scan
        lot_folder, new_csv_path, new_rows, subfolders = process_one(
            scanner_input, rows, working_dir, csv_path
        )
        if new_csv_path is not None and new_rows is not None:
            csv_path = new_csv_path
            rows = new_rows
        if lot_folder is not None:
            last_lot_folder = lot_folder
            setNextCaptureFolder(working_dir, lot_folder, subfolders or [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())