import importlib.util
import sys
import types
from pathlib import Path
import pytest


def load_module():
    path = Path(__file__).resolve().parents[1] / "torah_logic_full_updated.py"

    # Stub external GUI/ICS dependencies so the module can be imported
    if "customtkinter" not in sys.modules:
        ctk = types.ModuleType("customtkinter")
        ctk.set_appearance_mode = lambda *a, **k: None
        ctk.set_default_color_theme = lambda *a, **k: None
        ctk.CTk = type("CTk", (), {})
        ctk.StringVar = lambda *a, **k: None
        mock_widget = type("MockWidget", (), {})
        # Provide common widget classes used in the application
        for name in [
            "CTkFrame",
            "CTkButton",
            "CTkLabel",
            "CTkRadioButton",
            "CTkLabelFrame",
            "CTkCheckBox",
            "CTkFont",
        ]:
            setattr(ctk, name, mock_widget)
        sys.modules["customtkinter"] = ctk

    if "tkcalendar" not in sys.modules:
        tkcalendar = types.ModuleType("tkcalendar")
        tkcalendar.DateEntry = type("DateEntry", (), {})
        sys.modules["tkcalendar"] = tkcalendar

    if "ics" not in sys.modules:
        ics = types.ModuleType("ics")
        ics.Calendar = type("Calendar", (), {})
        ics.Event = type("Event", (), {})
        ics.DisplayAlarm = type("DisplayAlarm", (), {})
        sys.modules["ics"] = ics

    if "tkinter" not in sys.modules:
        tk = types.ModuleType("tkinter")
        tk.ttk = types.ModuleType("ttk")
        tk.filedialog = types.ModuleType("filedialog")
        tk.messagebox = types.ModuleType("messagebox")
        sys.modules["tkinter"] = tk
        sys.modules["tkinter.ttk"] = tk.ttk
        sys.modules["tkinter.filedialog"] = tk.filedialog
        sys.modules["tkinter.messagebox"] = tk.messagebox

    if "pyppeteer" not in sys.modules:

        async def fake_launch(*args, **kwargs):
            class FakePage:
                async def goto(self, url):
                    pass

                async def pdf(self, opts):
                    Path(opts["path"]).write_bytes(b"%PDF-1.4\n%fake")

            class FakeBrowser:
                async def newPage(self):
                    return FakePage()

                async def close(self):
                    pass

            return FakeBrowser()

        fake = types.ModuleType("pyppeteer")
        fake.launch = fake_launch
        sys.modules["pyppeteer"] = fake

    spec = importlib.util.spec_from_file_location("torah_tree", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def torah_tree():
    return load_module()


@pytest.fixture()
def sample_tree():
    return {
        "t1": {
            "פרקים": 3,
            "child1": {"פרקים": 2},
            "child2": {"פרק א": {}, "פרק ב": {}},
        },
        "t2": {
            "פרק א": {"משניות": 5},
            "פרק ב": {"משניות": 3},
            "child": {"פרק א": {"משניות": 1}},
        },
        "t3": {"אורך בדפים": 10, "child": {"אורך בדפים": 5}},
        "t4": {"אורך בדפים": 3},
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


def test_build_sefaria_ref_cross_book(torah_tree):
    first = {
        "book_display_name": "תנך / תורה / בראשית",
        "chapter_name": "פרק נ",
    }
    last = {
        "book_display_name": "תנך / תורה / שמות",
        "chapter_name": "פרק ב",
    }
    ref = torah_tree.build_sefaria_ref(first, last, "פרקים")
    assert ref == ["בראשית.נ", "שמות.א-ב"]


def test_build_sefaria_ref_cross_book_talmud_daf(torah_tree):
    first = {
        "book_display_name": "תלמוד בבלי / ברכות",
        "unit_num_int": 63,
    }
    last = {
        "book_display_name": "תלמוד בבלי / שבת",
        "unit_num_int": 3,
    }
    ref = torah_tree.build_sefaria_ref(first, last, "דפים")
    assert ref == ["Berakhot.63a-64a", "Shabbat.2a-3b"]


def test_build_sefaria_ref_cross_book_mishnah(torah_tree):
    first = {
        "book_display_name": "משנה / זרעים / ברכות / פרק ט",
        "unit_num_int": 4,
    }
    last = {
        "book_display_name": "משנה / זרעים / פאה / פרק א",
        "unit_num_int": 2,
    }
    ref = torah_tree.build_sefaria_ref(first, last, "משניות")
    assert ref == ["משנה_ברכות.ט.4-ט.5", "משנה_פאה.א.1-א.2"]
