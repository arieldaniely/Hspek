import types
import pytest
from pathlib import Path

from hspek.logic import tree, exporters


def load_module():
    """Provide a unified interface similar to the old monolithic module."""
    return types.SimpleNamespace(
        get_length_from_node=tree.get_length_from_node,
        build_sefaria_ref=tree.build_sefaria_ref,
        write_bookmark_pdf=exporters.write_bookmark_pdf,
    )


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
