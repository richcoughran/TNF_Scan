#!/usr/bin/env python3
"""
GES Integration: Automates Google Chrome interactions for GES barcode processing.
"""
from __future__ import annotations

import subprocess
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
        barcode: The GES barcode value to process
    """
    # Escape the barcode for JavaScript (escape quotes and backslashes)
    escaped_lot_num = lot_num.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
    
    # First osascript command: Set search field value and click search button
    script1 = f'''
        tell application "Google Chrome" to activate
        tell application "Google Chrome" to tell active tab in front window to execute javascript "document.getElementsByClassName('srchText')[0].value = '{escaped_lot_num}'; document.getElementsByClassName('srchButton')[0].click();"
    '''
    
    try:
        subprocess.run(
            ["osascript", "-e", script1],
            capture_output=True,
            check=False,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        print("Warning: Chrome automation timed out on first step")
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
        subprocess.run(
            ["osascript", "-e", script2a],
            capture_output=True,
            check=False,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        print("Warning: Chrome automation timed out on checkmark click")
    except Exception as e:
        print(f"Warning: Error executing checkmark click: {e}")
    
    # Third osascript command: Click primary button
    # Comment out the try/except block below to disable this step for testing
    script2b = '''
        tell application "Google Chrome" to activate
        tell application "Google Chrome" to tell active tab in front window to execute javascript "document.getElementsByClassName('Primary vertMarginSml SubChoiceHide')[0].click();"
    '''
    
    try:
        subprocess.run(
            ["osascript", "-e", script2b],
            capture_output=True,
            check=False,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        print("Warning: Chrome automation timed out on primary button click")
    except Exception as e:
        print(f"Warning: Error executing primary button click: {e}")
