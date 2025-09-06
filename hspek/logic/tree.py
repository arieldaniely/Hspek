"""Core study scheduling and tree traversal logic."""

from datetime import date, timedelta
import json
import re
from pyluach import dates, hebrewcal, parshios

from hspek.utils import resource_path
from .gematria import Gematria, HEBREW_NUMBERS_AVAILABLE

HEBREW_WEEKDAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
HEBREW_MONTH_NAMES = [
    "ניסן",
    "אייר",
    "סיון",
    "תמוז",
    "אב",
    "אלול",
    "תשרי",
    "מרחשון",
    "כסלו",
    "טבת",
    "שבט",
    "אדר",
    "אדר א'",
    "אדר ב'",
]

TORAH_TREE_CACHE = None


def detect_content_category(unit: dict) -> str | None:
    """Return 'tanakh', 'mishnah' or 'talmud' based on the unit path."""
    path = unit.get("book_display_name", "")
    if not path:
        return None
    first = path.split(" / ")[0]
    if first.startswith("משנה"):
        return "mishnah"
    if "תלמוד" in first:
        return "talmud"
    if first in ("תנך", "תנ" "ך"):
        return "tanakh"
    return None


def get_israeli_national_holiday_on_gregorian_date(gregorian_date_to_check: date, hebrew_year: int) -> str | None:
    """Return national Israeli holiday name for a Gregorian date if any."""
    hd_iyar_5_original = dates.HebrewDate(hebrew_year, 2, 5)
    gd_iyar_5_original = hd_iyar_5_original.to_pydate()
    weekday_iyar_5_original = gd_iyar_5_original.weekday()

    actual_hd_yom_haatzmaut = hd_iyar_5_original
    if weekday_iyar_5_original == 4:
        actual_hd_yom_haatzmaut = dates.HebrewDate(hebrew_year, 2, 4)
    elif weekday_iyar_5_original == 5:
        actual_hd_yom_haatzmaut = dates.HebrewDate(hebrew_year, 2, 3)
    elif weekday_iyar_5_original == 0:
        actual_hd_yom_haatzmaut = dates.HebrewDate(hebrew_year, 2, 6)

    actual_gd_yom_haatzmaut = actual_hd_yom_haatzmaut.to_pydate()
    actual_gd_yom_hazikaron = actual_gd_yom_haatzmaut - timedelta(days=1)

    if gregorian_date_to_check == actual_gd_yom_hazikaron:
        return "יום הזיכרון"
    if gregorian_date_to_check == actual_gd_yom_haatzmaut:
        return "יום העצמאות"

    hd_iyar_28_original = dates.HebrewDate(hebrew_year, 2, 28)
    gd_iyar_28_original = hd_iyar_28_original.to_pydate()
    weekday_iyar_28_original = gd_iyar_28_original.weekday()
    actual_hd_yom_yerushalayim = hd_iyar_28_original
    if weekday_iyar_28_original == 4:
        actual_hd_yom_yerushalayim = dates.HebrewDate(hebrew_year, 2, 27)
    elif weekday_iyar_28_original == 5:
        actual_hd_yom_yerushalayim = dates.HebrewDate(hebrew_year, 2, 29)
    actual_gd_yom_yerushalayim = actual_hd_yom_yerushalayim.to_pydate()
    if gregorian_date_to_check == actual_gd_yom_yerushalayim:
        return "יום ירושלים"
    return None


def is_holiday(gregorian_date: date) -> bool:
    """Return True if ``gregorian_date`` is a Jewish holiday."""
    g_date = dates.GregorianDate(gregorian_date.year, gregorian_date.month, gregorian_date.day)
    h_d = g_date.to_heb()
    regular_holiday = h_d.holiday(hebrew=True, israel=True)
    national = get_israeli_national_holiday_on_gregorian_date(gregorian_date, h_d.year)
    return bool(regular_holiday or national)


def load_data(path: str) -> dict:
    """Load JSON data from ``path``."""
    with open(resource_path(path), encoding="utf-8") as f:
        return json.load(f)


def has_relevant_data_recursive(node, mode: str) -> bool:
    """Recursively check if ``node`` or its children contain data for ``mode``."""
    if not isinstance(node, dict):
        return False
    if mode == "פרקים":
        if "פרקים" in node and isinstance(node["פרקים"], int):
            return True
        for key, val in node.items():
            if key.startswith("פרק ") and isinstance(val, dict):
                return True
    elif mode == "משניות":
        if "משניות" in node and isinstance(node["משניות"], int):
            return True
    elif mode in ("דפים", "עמודים"):
        if "אורך בדפים" in node and isinstance(node["אורך בדפים"], (int, float)):
            return True
    for key, val in node.items():
        if key in ["אורך בדפים", "עמוד אחרון", "משניות", "פרקים"] and not isinstance(val, dict):
            continue
        if isinstance(val, dict) and has_relevant_data_recursive(val, mode):
            return True
    return False


def get_length_from_node(node, mode: str):
    """Return total number of study units under ``node`` for ``mode``."""
    total = 0
    if not isinstance(node, dict):
        return 0
    for key, val in node.items():
        if isinstance(val, dict):
            total += get_length_from_node(val, mode)
    if mode == "פרקים":
        if "פרקים" in node and isinstance(node["פרקים"], int):
            total += node["פרקים"]
        else:
            total += sum(1 for key, val in node.items() if key.startswith("פרק ") and isinstance(val, dict))
    elif mode == "משניות":
        if "משניות" in node and isinstance(node["משניות"], int):
            total += node["משניות"]
    elif mode == "דפים":
        if "אורך בדפים" in node and isinstance(node["אורך בדפים"], (int, float)):
            total += node["אורך בדפים"]
    elif mode == "עמודים":
        if "אורך בדפים" in node and isinstance(node["אורך בדפים"], (int, float)):
            total += node["אורך בדפים"] * 2
    return total


def calculate_study_days(start_date: date, end_date: date, no_study_weekdays: set[int], skip_holidays: bool = False) -> int:
    """Compute number of study days between ``start_date`` and ``end_date``."""
    count = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() not in no_study_weekdays:
            if not (skip_holidays and is_holiday(current_date)):
                count += 1
        current_date += timedelta(days=1)
    return count


def _convert_int_to_hebrew_gematria(num):
    if HEBREW_NUMBERS_AVAILABLE:
        try:
            return Gematria.format_hebrew_number(num, punctuation=False)
        except Exception:
            return str(num)
    return str(num)


def _hebrew_chapter_sort_key(chap_str):
    if HEBREW_NUMBERS_AVAILABLE:
        try:
            num_part = chap_str.split()[-1]
            return Gematria.gematria_to_int(num_part)
        except Exception:
            return chap_str
    return chap_str


def _get_node_from_path(path_parts, tree_data):
    node = tree_data
    for part in path_parts:
        node = node.get(part)
        if node is None:
            return None
    return node


def _recursive_collect_chapters(node_data, path_parts, out_list):
    if not isinstance(node_data, dict):
        return
    book_name = " / ".join(path_parts)
    explicit_keys = sorted(
        [k for k, v in node_data.items() if k.startswith("פרק ") and isinstance(v, dict)],
        key=_hebrew_chapter_sort_key,
    )
    if explicit_keys:
        for chap_key in explicit_keys:
            out_list.append({"book_display_name": book_name, "chapter_name": chap_key})
    elif "פרקים" in node_data and isinstance(node_data["פרקים"], int):
        num_chaps = node_data["פרקים"]
        for i in range(1, num_chaps + 1):
            hebrew_num = _convert_int_to_hebrew_gematria(i)
            out_list.append({"book_display_name": book_name, "chapter_name": f"פרק {hebrew_num}"})
    for key, val in node_data.items():
        if isinstance(val, dict) and not key.startswith("פרק "):
            _recursive_collect_chapters(val, path_parts + [key], out_list)


def _collect_all_chapters_for_selection(titles_list, tree_data):
    collected = []
    for title_path_str in titles_list:
        path_parts = title_path_str.split(" / ")
        node = _get_node_from_path(path_parts, tree_data)
        if node:
            _recursive_collect_chapters(node, path_parts, collected)
    return collected


def _recursive_collect_units(node_data, path_parts, out_list, mode):
    if not isinstance(node_data, dict):
        return
    full_path_str = " / ".join(path_parts)
    if mode == "משניות":
        if "משניות" in node_data and isinstance(node_data["משניות"], int):
            for i in range(1, node_data["משניות"] + 1):
                out_list.append({"book_display_name": full_path_str, "unit_type": "משנה", "unit_num_int": i})
        elif any(k.startswith("פרק ") and isinstance(v, dict) for k, v in node_data.items()):
            for k, v in node_data.items():
                if k.startswith("פרק ") and isinstance(v, dict) and "משניות" in v:
                    for i in range(1, v["משניות"] + 1):
                        prk_name = full_path_str + " / " + k
                        out_list.append({"book_display_name": prk_name, "unit_type": "משנה", "unit_num_int": i})
    elif mode in ("דפים", "עמודים"):
        if "אורך בדפים" in node_data and isinstance(node_data["אורך בדפים"], (int, float)):
            start_page = node_data.get("עמוד ראשון", 2)
            for i in range(int(node_data["אורך בדפים"])):
                daf_num = start_page + i
                out_list.append({"book_display_name": full_path_str, "unit_type": "דף", "unit_num_int": daf_num})
    for key, val in node_data.items():
        if isinstance(val, dict) and not key.startswith("פרק "):
            _recursive_collect_units(val, path_parts + [key], out_list, mode)


def _collect_all_units_for_selection(titles_list, tree_data, mode):
    collected = []
    for title_path_str in titles_list:
        path_parts = title_path_str.split(" / ")
        node = _get_node_from_path(path_parts, tree_data)
        if node:
            _recursive_collect_units(node, path_parts, collected, mode)
    return collected


def find_exact_whole_branch(titles_list, tree_data):
    if not titles_list:
        return None
    split_paths = [title.split(" / ") for title in titles_list]
    common_path = []
    for level in zip(*split_paths):
        if len(set(level)) == 1:
            common_path.append(level[0])
        else:
            break
    if not common_path:
        if len(split_paths) > 1:
            return None
        common_path = split_paths[0]
    node = tree_data
    for part in common_path:
        if part in node:
            node = node[part]
        else:
            return None
    selected_last_parts = {p[len(common_path)] for p in split_paths if len(p) > len(common_path)}
    all_children = {key for key, val in node.items() if isinstance(val, dict) and not key.startswith("פרק")}
    if selected_last_parts and selected_last_parts == all_children:
        return " / ".join(common_path)
    if not selected_last_parts:
        return " / ".join(common_path)
    return None


def generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, extension, units_per_day=None):
    exact_branch = find_exact_whole_branch(titles_list, tree_data)
    if exact_branch:
        title = exact_branch.split(" / ")[-1]
    else:
        names = [t.split(" / ")[-1] for t in titles_list]
        unique_names = list(dict.fromkeys(names))
        if len(unique_names) == 1:
            title = f"{unique_names[0]} (חלקים)"
        elif len(unique_names) == 2:
            title = f"{unique_names[0]} ו{unique_names[1]}"
        elif len(unique_names) >= 3:
            title = f"{unique_names[0]}, {unique_names[1]} ועוד"
        else:
            title = "לימוד"
    if units_per_day:
        if units_per_day == 1:
            singular_map = {"פרקים": "פרק", "משניות": "משנה", "דפים": "דף", "עמודים": "עמוד"}
            unit_name = singular_map.get(mode, mode.rstrip("ים"))
            time_str = f"{unit_name} ליום"
        else:
            time_str = f"{units_per_day} {mode} ליום"
    else:
        days = (end_date - start_date).days + 1
        approx_months = round(days / 30)
        if approx_months >= 1 and abs(days - approx_months * 30) <= 5:
            if approx_months > 0 and approx_months % 12 == 0:
                approx_years = round(approx_months / 12)
                if approx_years == 1:
                    time_str = "בשנה"
                elif approx_years == 2:
                    time_str = "בשנתיים"
                else:
                    time_str = f"ב-{approx_years} שנים"
            elif approx_months == 1:
                time_str = "בחודש"
            elif approx_months == 2:
                time_str = "בחודשיים"
            else:
                time_str = f"ב-{approx_months} חודשים"
        elif days % 7 == 0:
            weeks = days // 7
            if weeks == 2:
                time_str = "בשבועיים"
            else:
                time_str = "בשבוע" if weeks == 1 else f"ב-{weeks}-שבועות"
        else:
            time_str = f"ב-{days}-ימים"
    return f"{title} {time_str}.{extension}"


def _generate_study_schedule(start_date, end_date, titles_list, mode, tree_data, no_study_weekdays, units_per_day=None, skip_holidays=False, balance_chapters_by_mishnayot=False):
    schedule = []
    if mode == "פרקים":
        all_units = _collect_all_chapters_for_selection(titles_list, tree_data)
    else:
        all_units = _collect_all_units_for_selection(titles_list, tree_data, mode)
        if mode in ("עמודים", "דפים", "משניות"):
            processed_units = []
            for unit in all_units:
                book_name = unit.get("book_display_name", "לא ידוע")
                unit_num = unit.get("unit_num_int")
                if unit_num is None:
                    continue
                hebrew_num = _convert_int_to_hebrew_gematria(unit_num)
                if mode == "עמודים":
                    processed_units.append({"book_display_name": book_name, "unit_type": "עמוד", "unit_display_name": f"{hebrew_num}.", "sort_key": unit_num * 2 - 1, "unit_num_int": unit_num, "side": "a"})
                    processed_units.append({"book_display_name": book_name, "unit_type": "עמוד", "unit_display_name": f"{hebrew_num}:", "sort_key": unit_num * 2, "unit_num_int": unit_num, "side": "b"})
                elif mode == "דפים":
                    processed_units.append({"book_display_name": book_name, "unit_type": "דף", "unit_display_name": hebrew_num, "sort_key": unit_num, "unit_num_int": unit_num})
                elif mode == "משניות":
                    processed_units.append({"book_display_name": book_name, "unit_type": "משנה", "unit_display_name": hebrew_num, "sort_key": unit_num, "unit_num_int": unit_num})
            all_units = processed_units
    total_units = len(all_units)
    if total_units == 0:
        return []
    current_date = start_date
    day_idx = 0
    unit_idx = 0
    if units_per_day is None:
        study_days_count = calculate_study_days(start_date, end_date, no_study_weekdays, skip_holidays)
        units_per_day_effective = total_units / study_days_count
    else:
        units_per_day_effective = units_per_day
    while unit_idx < total_units:
        if current_date.weekday() in no_study_weekdays or (skip_holidays and is_holiday(current_date)):
            current_date += timedelta(days=1)
            continue
        units_today = units_per_day_effective if units_per_day is not None else total_units / calculate_study_days(start_date, end_date, no_study_weekdays, skip_holidays)
        units_today = max(1, int(round(units_today)))
        first_unit = all_units[unit_idx]
        last_unit = all_units[min(unit_idx + units_today - 1, total_units - 1)]
        day_units = all_units[unit_idx : unit_idx + units_today]
        schedule.append({
            "date": current_date,
            "description": _build_description(day_units, mode),
            "first_unit": first_unit,
            "last_unit": last_unit,
            "units": day_units,
        })
        unit_idx += units_today
        current_date += timedelta(days=1)
    return schedule


def _build_description(day_units, mode):
    first = day_units[0]
    last = day_units[-1]
    if first == last:
        return _format_unit(first, mode)
    return f"{_format_unit(first, mode)} - {_format_unit(last, mode)}"


def _format_unit(unit, mode):
    if mode == "פרקים":
        return f"{unit['book_display_name']} / {unit['chapter_name']}"
    elif mode in ("משניות", "דפים", "עמודים"):
        return f"{unit['book_display_name']} {unit.get('unit_display_name', '')}".strip()
    return str(unit)


def _load_torah_tree():
    global TORAH_TREE_CACHE
    if TORAH_TREE_CACHE is None:
        with open(resource_path("torah_tree_data_full.json"), "r", encoding="utf-8") as f:
            TORAH_TREE_CACHE = json.load(f)
    return TORAH_TREE_CACHE


def build_sefaria_ref(
    first_unit: dict, last_unit: dict, mode: str
) -> str | list[str] | None:
    """Construct Sefaria reference(s).

    ``mode`` indicates the unit granularity (פרקים/משניות/דפים/עמודים) only.
    The content category (Tanakh/Mishnah/Talmud) is detected from the path of
    ``first_unit``.  When the portion spans two different books, two references
    are returned.
    """
    with open(resource_path("sefaria_masechet_map.json"), "r", encoding="utf-8") as f:
        SEFARIA_MASECHET_MAP = json.load(f)

    def extract(unit):
        name = unit.get("book_display_name", "")
        parts = name.split(" / ")
        book = chap = None
        if parts:
            if parts[-1].startswith("פרק "):
                chap = parts[-1].split()[-1]
                book = parts[-2] if len(parts) > 1 else None
            else:
                book = parts[-1]
                if mode == "פרקים" and "chapter_name" in unit:
                    chap = unit["chapter_name"].split()[-1]
        return book, chap

    sb, sch = extract(first_unit)
    eb, ech = extract(last_unit)
    if not sb:
        return None
    cross_book = eb and eb != sb

    category = detect_content_category(first_unit)
    book = sb
    if category == "talmud":
        masechet = book.replace("מסכת ", "")
        book = SEFARIA_MASECHET_MAP.get(masechet)
        if not book:
            return None
    elif category == "mishnah":
        if not book.startswith("משנה_"):
            book = f"משנה_{book}"

    if cross_book:
        tree = _load_torah_tree()
        first_path_parts = first_unit["book_display_name"].split(" / ")
        if first_path_parts[-1].startswith("פרק "):
            first_path_parts = first_path_parts[:-1]
        first_node = _get_node_from_path(first_path_parts, tree)
        if not first_node:
            return None

        # map second book name
        category2 = detect_content_category(last_unit)
        book2 = eb
        if category2 == "talmud":
            masechet = book2.replace("מסכת ", "")
            book2 = SEFARIA_MASECHET_MAP.get(masechet)
            if not book2:
                return None
        elif category2 == "mishnah":
            if not book2.startswith("משנה_"):
                book2 = f"משנה_{book2}"

        if mode == "פרקים":
            last_chap_num = None
            if "פרקים" in first_node and isinstance(first_node["פרקים"], int):
                last_chap_num = first_node["פרקים"]
            else:
                ch_keys = [k for k in first_node if k.startswith("פרק ")]
                if ch_keys:
                    last_chap_num = max(
                        Gematria.gematria_to_int(k.split()[-1]) for k in ch_keys
                    )
            if last_chap_num is None:
                return None

            end_first = _convert_int_to_hebrew_gematria(last_chap_num)
            s = first_unit.get("chapter_name", "").split()[-1]
            if not s or not ech:
                return None

            ref1 = f"{book}.{s}" if s == end_first else f"{book}.{s}-{end_first}"
            ref2 = f"{book2}.א" if ech == "א" else f"{book2}.א-{ech}"
            return [ref1, ref2]

        if mode == "משניות":
            ch_keys = [k for k in first_node if k.startswith("פרק ")]
            if not ch_keys:
                return None
            last_ch_num = max(Gematria.gematria_to_int(k.split()[-1]) for k in ch_keys)
            end_ch_name = _convert_int_to_hebrew_gematria(last_ch_num)
            last_ch_node = first_node.get(f"פרק {end_ch_name}")
            if not isinstance(last_ch_node, dict) or "משניות" not in last_ch_node:
                return None
            last_mish = last_ch_node["משניות"]
            s_m = first_unit.get("unit_num_int")
            if sch is None or s_m is None or ech is None or last_mish is None:
                return None
            ref1 = f"{book}.{sch}.{s_m}-{end_ch_name}.{last_mish}"
            ref2 = (
                f"{book2}.א.1"
                if ech == "א" and last_unit.get("unit_num_int") == 1
                else f"{book2}.א.1-{ech}.{last_unit.get('unit_num_int')}"
            )
            return [ref1, ref2]

        if mode == "דפים":
            end_str = first_node.get("עמוד אחרון")
            if not end_str:
                return None
            m = re.match(r"(\d+)([ab])", end_str)
            if not m:
                return None
            end_page = int(m.group(1))
            end_side = m.group(2)
            s_d = first_unit.get("unit_num_int")
            e_d = last_unit.get("unit_num_int")
            if s_d is None or e_d is None:
                return None
            ref1 = f"{book}.{s_d}a-{end_page}{end_side}"
            ref2 = f"{book2}.2a-{e_d}b" if e_d != 2 else f"{book2}.2a"
            return [ref1, ref2]

        if mode == "עמודים":
            end_str = first_node.get("עמוד אחרון")
            if not end_str:
                return None
            m = re.match(r"(\d+)([ab])", end_str)
            if not m:
                return None
            end_page = int(m.group(1))
            end_side = m.group(2)
            s_d = first_unit.get("unit_num_int")
            s_side = first_unit.get("side")
            e_d = last_unit.get("unit_num_int")
            e_side = last_unit.get("side")
            if None in (s_d, s_side, e_d, e_side):
                return None
            ref1 = f"{book}.{s_d}{s_side}-{end_page}{end_side}"
            start_second = "2a"
            end_second = f"{e_d}{e_side}"
            ref2 = (
                f"{book2}.{start_second}-{end_second}"
                if end_second != start_second
                else f"{book2}.{start_second}"
            )
            return [ref1, ref2]

    if mode == "פרקים":
        s = first_unit.get("chapter_name", "").split()[-1]
        e = last_unit.get("chapter_name", "").split()[-1]
        if not s or not e:
            return None
        ref = f"{book}.{s}" if s == e else f"{book}.{s}-{e}"
        return ref

    if mode == "משניות":
        s_m, e_m = first_unit.get("unit_num_int"), last_unit.get("unit_num_int")
        if sch is None or s_m is None or e_m is None:
            return None
        if sch == ech:
            ref = f"{book}.{sch}.{s_m}" if s_m == e_m else f"{book}.{sch}.{s_m}-{e_m}"
        else:
            if ech is None:
                return None
            ref = f"{book}.{sch}.{s_m}-{ech}.{e_m}"
        return ref

    if mode == "דפים":
        s_d, e_d = first_unit.get("unit_num_int"), last_unit.get("unit_num_int")
        if s_d is None or e_d is None:
            return None
        ref = f"{book}.{s_d}a" if s_d == e_d else f"{book}.{s_d}a-{e_d}b"
        return ref

    if mode == "עמודים":
        s_d, e_d = first_unit.get("unit_num_int"), last_unit.get("unit_num_int")
        s_side, e_side = first_unit.get("side"), last_unit.get("side")
        if None in (s_d, e_d, s_side, e_side):
            return None
        start = f"{s_d}{s_side}"
        end = f"{e_d}{e_side}"
        ref = f"{book}.{start}" if start == end else f"{book}.{start}-{end}"
        return ref

    return None
