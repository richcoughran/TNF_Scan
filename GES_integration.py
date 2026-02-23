#!/usr/bin/env python3
"""
GES Integration: Automates Google Chrome interactions for GES barcode processing.
"""
from __future__ import annotations

import subprocess
import sys
import time


def mark_as_shot_GES(lot_num: str) -> None:
    """
    Process a GES barcode scan by automating Google Chrome interactions.

    This function:
    1. Activates Chrome and sets the barcode value in the search field
    2. Clicks the search button
    3. Waits 5 seconds
    4. Clicks the checkmark and primary button

    Args:
        lot_num: The GES lot number / barcode value to process.
    """
    if sys.platform != "darwin":
        print("mark_as_shot_GES: AppleScript automation is only supported on macOS.")
        return
    # Escape the barcode for JavaScript (escape quotes and backslashes)
    escaped_lot_num = lot_num.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
    
    # First osascript command: Set search field value and click search button
    script1 = f'''
        tell application "Google Chrome" to activate
        tell application "Google Chrome" to tell active tab in front window to execute javascript "document.getElementsByClassName('srchText')[0].value = '{escaped_lot_num}'; document.getElementsByClassName('srchButton')[0].click();"
    '''
    
    try:
        result1 = subprocess.run(
            ["osascript", "-e", script1],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result1.returncode != 0:
            print("Warning: Chrome automation step 1 failed.")
            if result1.stderr:
                print("  osascript stderr (step 1):", result1.stderr.strip())
            if result1.stdout:
                print("  osascript stdout (step 1):", result1.stdout.strip())
    except subprocess.TimeoutExpired:
        print("Warning: Chrome automation timed out on first step.")
    except FileNotFoundError:
        print('Warning: "osascript" command not found. Is AppleScript available on this system?')
    except Exception as e:
        print(f"Warning: Error executing first Chrome automation: {e}")
    
    # Wait 5 seconds
    time.sleep(5)
    
    # Second osascript command: Click checkmark
    script2a = '''
        tell application "Google Chrome" to activate
        tell application "Google Chrome" to tell active tab in front window to execute javascript "document.getElementsByClassName('checkmark')[0].click();"
    '''
    
    try:
        result2 = subprocess.run(
            ["osascript", "-e", script2a],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result2.returncode != 0:
            print("Warning: Chrome automation step 2 (checkmark) failed.")
            if result2.stderr:
                print("  osascript stderr (step 2):", result2.stderr.strip())
            if result2.stdout:
                print("  osascript stdout (step 2):", result2.stdout.strip())
    except subprocess.TimeoutExpired:
        print("Warning: Chrome automation timed out on checkmark click.")
    except FileNotFoundError:
        print('Warning: "osascript" command not found during checkmark click.')
    except Exception as e:
        print(f"Warning: Error executing checkmark click: {e}")
    
    # Third osascript command: Click primary button
    # Comment out the try/except block below to disable this step for testing
    script2b = '''
        tell application "Google Chrome" to activate
        tell application "Google Chrome" to tell active tab in front window to execute javascript "document.getElementsByClassName('Primary vertMarginSml SubChoiceHide')[0].click();"
    '''
    
    try:
        result3 = subprocess.run(
            ["osascript", "-e", script2b],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result3.returncode != 0:
            print("Warning: Chrome automation step 3 (primary button) failed.")
            if result3.stderr:
                print("  osascript stderr (step 3):", result3.stderr.strip())
            if result3.stdout:
                print("  osascript stdout (step 3):", result3.stdout.strip())
    except subprocess.TimeoutExpired:
        print("Warning: Chrome automation timed out on primary button click.")
    except FileNotFoundError:
        print('Warning: "osascript" command not found during primary button click.')
    except Exception as e:
        print(f"Warning: Error executing primary button click: {e}")
