from datetime import date
from pathlib import Path
from test_torah_tree import load_module
import shutil
import os
import pytest
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from hspek.utils.paths import resource_path


def test_write_bookmark_pdf(tmp_path):
    module = load_module()
    tree = {"t": {"פרקים": 1}}
    old_cwd = os.getcwd()
    map_src = Path(resource_path("sefaria_masechet_map.json"))
    tree_src = Path(resource_path("torah_tree_data_full.json"))
    tpl_src = Path(resource_path("bookmark_template.html"))
    pdf_path = None
    try:
        os.chdir(tmp_path)
        if map_src.exists():
            Path(tmp_path / "sefaria_masechet_map.json").write_bytes(map_src.read_bytes())
        if tree_src.exists():
            Path(tmp_path / "torah_tree_data_full.json").write_bytes(tree_src.read_bytes())
        if tpl_src.exists():
            Path(tmp_path / "bookmark_template.html").write_bytes(tpl_src.read_bytes())
        # Skip if no Chromium/Chrome is available
        if not (
            os.environ.get("CHROME_PATH")
            or shutil.which("chromium-browser")
            or shutil.which("google-chrome")
            or shutil.which("chromium")
            or shutil.which("chrome")
        ):
            pytest.skip("Chrome/Chromium not available")

        pdf_path = module.write_bookmark_pdf(
            titles_list=["t"],
            mode="פרקים",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            tree_data=tree,
            no_study_weekdays_set=set(),
        )
    finally:
        os.chdir(old_cwd)
    assert pdf_path is not None
    assert Path(pdf_path).exists()
