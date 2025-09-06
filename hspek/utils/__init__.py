"""Utility functions for hspek."""
import os
import sys


def resource_path(filename: str) -> str:
    """Return path to a bundled resource.

    When running as a PyInstaller bundle the files are unpacked to a
    temporary directory accessible via ``sys._MEIPASS``. This helper ensures
    resources are located correctly both when running from source and from a
    packaged executable.
    """
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, filename)
