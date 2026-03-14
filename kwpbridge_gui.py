"""
KWPBridge GUI entry point for PyInstaller.

This is a top-level script (not inside any package) so PyInstaller
can freeze it without relative import issues.
"""
import sys
import os

# When frozen by PyInstaller, sys._MEIPASS is the temp dir
# Add it to path so kwpbridge package is found
if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    sys.path.insert(0, base)

from kwpbridge.gui.main import main

if __name__ == "__main__":
    main()
