import importlib.util
import sys
import types
from pathlib import Path
import pytest


def load_module():
    path = Path(__file__).resolve().parents[1] / "torah_logic_full_updated.py"

    # Stub external GUI/ICS dependencies so the module can be imported
    if 'customtkinter' not in sys.modules:
        ctk = types.ModuleType('customtkinter')
        ctk.set_appearance_mode = lambda *a, **k: None
        ctk.set_default_color_theme = lambda *a, **k: None
        ctk.CTk = type('CTk', (), {})
        ctk.StringVar = lambda *a, **k: None
        mock_widget = type('MockWidget', (), {})
        # Provide common widget classes used in the application
        for name in [
            'CTkFrame', 'CTkButton', 'CTkLabel', 'CTkRadioButton',
            'CTkLabelFrame', 'CTkCheckBox', 'CTkFont'
        ]:
            setattr(ctk, name, mock_widget)
        sys.modules['customtkinter'] = ctk

    if 'tkcalendar' not in sys.modules:
        tkcalendar = types.ModuleType('tkcalendar')
        tkcalendar.DateEntry = type('DateEntry', (), {})
        sys.modules['tkcalendar'] = tkcalendar

    if 'ics' not in sys.modules:
        ics = types.ModuleType('ics')
        ics.Calendar = type('Calendar', (), {})
        ics.Event = type('Event', (), {})
        alarm_module = types.ModuleType('ics.alarm')
        alarm_module.DisplayAlarm = type('DisplayAlarm', (), {})
        ics.alarm = alarm_module
        sys.modules['ics'] = ics
        sys.modules['ics.alarm'] = alarm_module

    if 'tkinter' not in sys.modules:
        tk = types.ModuleType('tkinter')
        tk.ttk = types.ModuleType('ttk')
        tk.filedialog = types.ModuleType('filedialog')
        tk.messagebox = types.ModuleType('messagebox')
        sys.modules['tkinter'] = tk
        sys.modules['tkinter.ttk'] = tk.ttk
        sys.modules['tkinter.filedialog'] = tk.filedialog
        sys.modules['tkinter.messagebox'] = tk.messagebox

    spec = importlib.util.spec_from_file_location('torah_tree', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='session')
def torah_tree():
    return load_module()


@pytest.fixture()
def sample_tree():
    return {
        "t1": {
            "פרקים": 3,
            "child1": {"פרקים": 2},
            "child2": {
                "פרק א": {},
                "פרק ב": {}
            }
        },
        "t2": {
            "פרק א": {"משניות": 5},
            "פרק ב": {"משניות": 3},
            "child": {
                "פרק א": {"משניות": 1}
            }
        },
        "t3": {
            "אורך בדפים": 10,
            "child": {"אורך בדפים": 5}
        },
        "t4": {"אורך בדפים": 3}
    }


def test_get_length_parakim(torah_tree, sample_tree):
    assert torah_tree.get_length_from_node(sample_tree, "פרקים") == 10


def test_get_length_mishnayot(torah_tree, sample_tree):
    assert torah_tree.get_length_from_node(sample_tree, "משניות") == 9


def test_get_length_dapim(torah_tree, sample_tree):
    assert torah_tree.get_length_from_node(sample_tree, "דפים") == 18


def test_get_length_amudim(torah_tree, sample_tree):
    assert torah_tree.get_length_from_node(sample_tree, "עמודים") == 36


def test_build_sefaria_ref_detects_category(torah_tree):
    first = {
        "book_display_name": "משנה / זרעים / ברכות",
        "chapter_name": "פרק א",
    }
    last = {
        "book_display_name": "משנה / זרעים / ברכות",
        "chapter_name": "פרק ב",
    }
    ref = torah_tree.build_sefaria_ref(first, last, "פרקים")
    assert ref == "משנה_ברכות.א-ב"
