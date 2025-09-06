import os
import sys

def resource_path(filename: str) -> str:
    """Return absolute path to a resource file, compatible with PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)
