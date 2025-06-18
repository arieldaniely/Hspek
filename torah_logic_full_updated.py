from datetime import date, timedelta
from ics import Calendar, Event
import json
import os

from pyluach import dates, hebrewcal, parshios
from jinja2 import Environment, FileSystemLoader

# ==================== עזרות גימטריה ====================
class Gematria:
    _hebrew_letters_map = {
        1: 'א', 2: 'ב', 3: 'ג', 4: 'ד', 5: 'ה', 6: 'ו', 7: 'ז', 8: 'ח', 9: 'ט',
        10: 'י', 20: 'כ', 30: 'ל', 40: 'מ', 50: 'נ', 60: 'ס', 70: 'ע', 80: 'פ', 90: 'צ',
        100: 'ק', 200: 'ר', 300: 'ש', 400: 'ת', 500: 'תק', 600: 'תר', 700: 'תש', 800: 'תת', 900: 'תתק'
    }

    _hebrew_letter_values = {
        'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
        'י': 10, 'כ': 20, 'ך': 20, 'ל': 30, 'מ': 40, 'ם': 40, 'נ': 50, 'ן': 50,
        'ס': 60, 'ע': 70, 'פ': 80, 'ף': 80, 'צ': 90, 'ץ': 90, 'ק': 100,
        'ר': 200, 'ש': 300, 'ת': 400
    }

    @classmethod
    def format_hebrew_number(cls, num: int, punctuation: bool = True) -> str:
        """
        ממיר מספר שלם לגימטריה בעברית, עד 9999, עם סימון אלפים כבשנים עבריות.
        לדוגמה (ברירת מחדל עם punctuation=True):
          32   → 'לב'
          2222 → 'ב׳רכב'  (דוגמה שגויה במקור: 2222 צריך להיות ב׳רכב ולא ב׳תתקרב)
          3222 → 'ג׳רכב'  (דוגמה שגויה במקור: 3222 צריך להיות ג׳רכב ולא ג׳תתתרכב)
          5784 → 'ה׳תשפד' (דוגמה שגויה במקור: 5784 צריך להיות ה׳תשפד ולא ה׳תתתתתפד)
        """
        if not isinstance(num, int) or not (1 <= num <= 9999):
            # במקרה של קלט לא תקין, נחזיר את המספר כמחרוזת
            return str(num)

        result = []

        # טיפול באלפים
        thousands = num // 1000
        if thousands > 0:
            # מקרים כמו 1000 -> א׳, 2000 -> ב׳, וכו'.
            # נניח שאלף יחיד נכתב 'א׳' ולא 'תתקק' או משהו דומה
            if thousands in cls._hebrew_letters_map:
                result.append(cls._hebrew_letters_map[thousands] + '׳')
            # אם יש יותר מ-9000 (מקרה שלא נפוץ לרוב), נטפל רק עד 9
            # המקור שלך תומך עד 9999, אז נצמצם את זה לטיפול יחיד
            else: # למקרה שצריך לטפל בערכים מעל 9 אלפים - פה זה לא יקרה כי המקסימום הוא 9
                 pass


        # טיפול בשאר המספר (עד 999)
        remainder = num % 1000
        if remainder == 0 and thousands > 0:
            # אם יש אלפים ואין שארית (לדוגמה 1000, 2000), סיימנו
            pass
        elif remainder == 15:
            result.append('טו')
        elif remainder == 16:
            result.append('טז')
        else:
            # פירוק למאות, עשרות ויחידות
            hundreds = (remainder // 100) * 100
            tens_units = remainder % 100

            if hundreds > 0:
                result.append(cls._hebrew_letters_map.get(hundreds, '')) #get כדי למנוע שגיאה במקרה של 500, 600, 700, 800, 900
            
            # אם יש שאר עשרות ויחידות
            if tens_units > 0 and tens_units != 15 and tens_units != 16:
                tens = (tens_units // 10) * 10
                units = tens_units % 10

                if tens > 0:
                    result.append(cls._hebrew_letters_map.get(tens, ''))
                if units > 0:
                    result.append(cls._hebrew_letters_map.get(units, ''))
            elif remainder == 0:
                pass # במקרה של מספרים עגולים כמו 1000, 2000 וכו' לא נוסיף כלום

        final_string = "".join(result)

        # הוספת גרש כפול (״) לפני האות האחרונה, אם נדרש
        if punctuation and len(final_string) > 1:
            # יש לוודא שהגרש הכפול לא ייכנס בתוך חלק האלפים
            # לדוגמה: 2222 -> ב׳רכב (הגרש לא משפיע על ה-ב')
            # אם final_string מסתיים בגרש של אלפים (׳), לא נוסיף ״
            if final_string[-1] == '׳':
                pass # כבר יש גרש, לא נוסיף כפול
            elif '׳' in final_string: # אם יש גרש של אלפים איפשהו באמצע
                # לדוגמה 'ב׳רכב' -> ב׳רכ״ב
                # נחפש את המיקום של הגרש, ונוסיף את הגרשיים רק אחריו
                parts = final_string.split('׳')
                if len(parts[1]) > 0: # אם יש חלק אחרי הגרש
                     final_string = parts[0] + '׳' + parts[1][:-1] + '״' + parts[1][-1]
                else: # אם אין חלק אחרי הגרש (לדוגמה 1000 -> א׳)
                    pass # לא מוסיפים ״
            elif final_string and final_string[-1] != '׳':
                # טיפול במקרים רגילים ללא אלפים, או כשהחלק המרכזי הוא היחיד
                final_string = final_string[:-1] + '״' + final_string[-1]


        # תיקון מקרים בהם _hebrew_letters_map מביא לת, ר, ק וכו' במאות
        # המפה החדשה מטפלת בזה, אבל לוודא שאין כפילויות
        # לדוגמה 500 לא יהיה תקק
        # אם יש 500 הוא יוכנס כ"תק"
        # אם יש 600 הוא יוכנס כ"תר"
        # וכו'
        # זה כבר טופל במפת האותיות החדשה _hebrew_letters_map

        return final_string

    @classmethod
    def gematria_to_int(cls, hebrew: str) -> int:
        """המרת גימטריה חזרה למספר (סכימת ערכי האותיות בלבד)"""
        total = 0
        i = 0
        # עבור המרה חזרה, נצטרך להתחשב גם בגרש אלפים ובגרש כפול אם הם שם
        # נוריד אותם ונחשב רק את האותיות
        cleaned_hebrew = hebrew.replace('׳', '').replace('״', '')
        for ch in cleaned_hebrew:
            total += cls._hebrew_letter_values.get(ch, 0)
        return total

HEBREW_NUMBERS_AVAILABLE = True

HEBREW_WEEKDAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
HEBREW_MONTH_NAMES = [
    "ניסן", "אייר", "סיון", "תמוז", "אב", "אלול",
    "תשרי", "מרחשון", "כסלו", "טבת", "שבט", "אדר",
    "אדר א'", "אדר ב'"
]

# ==================== כלי עזר ====================
def load_data(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def has_relevant_data_recursive(node, mode):
    """בודק רקורסיבית אם לצומת יש נתונים רלוונטיים לסוג הספירה."""
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
        if isinstance(val, dict):
            if has_relevant_data_recursive(val, mode):
                return True
    return False

def get_length_from_node(node, mode):
    """סופר רקורסיבית את אורך הלימוד מתוך צומת נתון."""
    total = 0
    if not isinstance(node, dict):
        return 0

    # קודם כל סורקים את תתי-הצמתים
    for key, val in node.items():
        if isinstance(val, dict):
            total += get_length_from_node(val, mode)

    # לאחר מכן מוסיפים את הערך של הצומת הנוכחי
    if mode == "פרקים":
        if "פרקים" in node and isinstance(node["פרקים"], int):
            total += node["פרקים"]
        else:
            # אם אין 'פרקים', סופרים מפתחות של "פרק X"
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

def calculate_study_days(start_date, end_date, no_study_weekdays):
    """חשב כמה ימי לימוד יש בין שני תאריכים (לא כולל ימי חופש)"""
    count = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() not in no_study_weekdays:
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
        key=_hebrew_chapter_sort_key
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

def generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, extension):
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
    days = (end_date - start_date).days + 1
    if days > 360:
        years = round(days / 365)
        time_str = "בשנה" if years == 1 else f"ב-{years}-שנים"
    elif 28 < days < 33:
        time_str = "בחודש"
    elif 58 < days < 63:
        time_str = "בחודשיים"
    elif days % 7 == 0:
        weeks = days // 7
        time_str = "בשבוע" if weeks == 1 else f"ב-{weeks}-שבועות"
    else:
        time_str = f"ב-{days}-ימים"
    return f"{title} {time_str}.{extension}"

# ==================== מחשב לוח לימוד ====================
def _generate_study_schedule(start_date, end_date, titles_list, mode, tree_data, no_study_weekdays):
    schedule = []
    study_days_count = calculate_study_days(start_date, end_date, no_study_weekdays)
    if study_days_count == 0:
        return []
    if mode == "פרקים":
        all_units = _collect_all_chapters_for_selection(titles_list, tree_data)
        total_units = len(all_units)
        if total_units == 0: return []
        base_per_day = total_units // study_days_count
        remainder = total_units % study_days_count
        allocations = [base_per_day + (1 if i < remainder else 0) for i in range(study_days_count)]
        unit_idx = 0
        day_idx = 0
        current_date = start_date
        while current_date <= end_date and unit_idx < total_units:
            if current_date.weekday() not in no_study_weekdays:
                num_today = allocations[day_idx]
                if num_today > 0:
                    todays_units = all_units[unit_idx:unit_idx + num_today]
                    first_unit, last_unit = todays_units[0], todays_units[-1]
                    desc = ""
                    if first_unit["book_display_name"] == last_unit["book_display_name"]:
                        desc += f"{first_unit['book_display_name']} – {first_unit['chapter_name']}"
                        if first_unit["chapter_name"] != last_unit["chapter_name"]:
                            desc += f" עד {last_unit['chapter_name']}"
                    else:
                        desc += f"מ-{first_unit['book_display_name']} {first_unit['chapter_name']} עד {last_unit['book_display_name']} {last_unit['chapter_name']}"
                    schedule.append({"date": current_date, "description": desc})
                    unit_idx += num_today
                day_idx += 1
            current_date += timedelta(days=1)
    else:
        all_units = _collect_all_units_for_selection(titles_list, tree_data, mode)
        processed_units = []
        for unit in all_units:
            book_name = unit.get("book_display_name", "לא ידוע")
            unit_num = unit.get("unit_num_int")
            if unit_num is None:
                continue
            hebrew_num = _convert_int_to_hebrew_gematria(unit_num)
            if mode == "עמודים":
                processed_units.append({
                    "book_display_name": book_name, "unit_type": "עמוד",
                    "unit_display_name": f"{hebrew_num}א", "sort_key": unit_num * 2 - 1
                })
                processed_units.append({
                    "book_display_name": book_name, "unit_type": "עמוד",
                    "unit_display_name": f"{hebrew_num}ב", "sort_key": unit_num * 2
                })
            elif mode == "דפים":
                processed_units.append({
                    "book_display_name": book_name, "unit_type": "דף",
                    "unit_display_name": hebrew_num, "sort_key": unit_num
                })
            elif mode == "משניות":
                processed_units.append({
                    "book_display_name": book_name, "unit_type": "משנה",
                    "unit_display_name": hebrew_num, "sort_key": unit_num
                })
        processed_units.sort(key=lambda x: (x["book_display_name"], x["sort_key"]))
        all_units = processed_units
        total_units = len(all_units)
        if total_units == 0: return []
        base_per_day = total_units // study_days_count
        remainder = total_units % study_days_count
        allocations = [base_per_day + (1 if i < remainder else 0) for i in range(study_days_count)]
        unit_idx = 0
        day_idx = 0
        current_date = start_date
        while current_date <= end_date and unit_idx < total_units:
            if current_date.weekday() not in no_study_weekdays:
                num_today = allocations[day_idx]
                if num_today > 0:
                    todays_units = all_units[unit_idx:unit_idx + num_today]
                    first_unit, last_unit = todays_units[0], todays_units[-1]
                    desc = ""
                    if first_unit["book_display_name"] == last_unit["book_display_name"]:
                        desc += f"{first_unit['book_display_name']} – {first_unit['unit_type']} {first_unit['unit_display_name']}"
                        if len(todays_units) > 1 and first_unit["unit_display_name"] != last_unit["unit_display_name"]:
                            desc += f" עד {last_unit['unit_type']} {last_unit['unit_display_name']}"
                    else:
                        desc += f"מ-{first_unit['book_display_name']} {first_unit['unit_type']} {first_unit['unit_display_name']} עד {last_unit['book_display_name']} {last_unit['unit_type']} {last_unit['unit_display_name']}"
                    schedule.append({"date": current_date, "description": desc})
                    unit_idx += num_today
                day_idx += 1
            current_date += timedelta(days=1)
    return schedule

# ==================== יצירת ICS ====================
def write_ics_file(titles_list, mode, start_date, end_date, tree_data, no_study_weekdays_set):
    schedule = _generate_study_schedule(start_date, end_date, titles_list, mode, tree_data, no_study_weekdays_set)
    if not schedule:
        print("אזהרה: לא נוצר לוח לימודים.")
        return None
    cal = Calendar()
    first_title = titles_list[0].split(' / ')[-1] if titles_list else "לימוד"
    event_base_name = f"סדר לימוד: {first_title}"
    if len(titles_list) > 1:
        event_base_name += " ועוד"
    for day_data in schedule:
        e = Event()
        e.name = event_base_name
        e.begin = day_data['date'].strftime('%Y-%m-%d')
        e.make_all_day()
        e.description = day_data['description']
        cal.events.add(e)
    filename = generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, "ics")
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(cal)
        print(f"קובץ ICS נוצר בהצלחה: {full_path}")
        return full_path
    except Exception as e:
        print(f"שגיאה בכתיבת קובץ ICS: {e}")
        return None

def write_bookmark_html(titles_list, mode, start_date, end_date, tree_data, no_study_weekdays_set):
    from collections import defaultdict
    schedule = _generate_study_schedule(start_date, end_date, titles_list, mode, tree_data, no_study_weekdays_set)
    if not schedule:
        print("אזהרה: לא נוצר לוח לימודים.")
        return None

    study_map = {item["date"]: item["description"] for item in schedule}

    # אוספים את כל הימים בטווח, וממפים אותם לשנה וחודש עברי
    day_map = defaultdict(list)
    cur = start_date
    while cur <= end_date:
        g_date = dates.GregorianDate(cur.year, cur.month, cur.day)
        h_date = g_date.to_heb()
        key = (h_date.year, h_date.month)
        day_map[key].append(cur)
        cur += timedelta(days=1)

    # מסדרים לפי סדר כרונולוגי
    # מפת מספור חודשים עבריים בסדר תשרי
    HEB_MONTH_ORDER = {
        7: 1, 8: 2, 9: 3, 10: 4, 11: 5, 12: 6, 13: 7, 1: 8, 2: 9, 3: 10, 4: 11, 5: 12, 6: 13
    }

    sorted_keys = sorted(
        day_map.keys(),
        key=lambda x: (x[0], HEB_MONTH_ORDER.get(x[1], x[1]))
    )

    monthly_schedule = []
    for (h_year, h_month) in sorted_keys:
        # כותרת החודש
        month_name_he = hebrewcal.Month(h_year, h_month).month_name(True)
        year_str = dates.HebrewDate(h_year, h_month, 1).hebrew_date_string(True).split()[-1]
        month_data = {"month_name": f"{month_name_he} {year_str}", "weeks": []}

        # ימים בלוח – לשבץ לפי שבועות (ראשון-שבת)
        days = sorted(day_map[(h_year, h_month)])
        if days:
            # מציאת יום ראשון של השבוע הראשון
            first_day = days[0]
            days_from_sunday = (first_day.weekday() + 1) % 7
            week_start = first_day - timedelta(days=days_from_sunday)
            last_day = days[-1]
            days_to_saturday = (5 - last_day.weekday()) % 7
            schedule_end_date = last_day + timedelta(days=days_to_saturday)

            current_week_start = week_start
            while current_week_start <= schedule_end_date:
                week = []
                for i in range(7):
                    current_day = current_week_start + timedelta(days=i)
                    g_date = dates.GregorianDate(current_day.year, current_day.month, current_day.day)
                    h_d = g_date.to_heb()
                    is_in_month = (h_d.year == h_year and h_d.month == h_month)
                    hebrew_day_number = h_d.hebrew_day() if is_in_month else ""
                    hebrew_date = h_d.hebrew_date_string(True) if is_in_month else ""
                    holiday = h_d.holiday(hebrew=True) if is_in_month else ""
                    parsha = parshios.getparsha_string(g_date, hebrew=True, israel=True) if current_day.weekday() == 5 and is_in_month else None
                    label = holiday or parsha or ""
                    week.append({
                        "is_in_month": is_in_month,
                        "hebrew_date": hebrew_date,
                        "hebrew_day_number": hebrew_day_number,
                        "label": label,
                        "study_portion": study_map.get(current_day, "") if is_in_month else "",
                        "is_shabbat": current_day.weekday() == 5 if is_in_month else False,
                        "is_holiday": bool(holiday) if is_in_month else False
                    })
                month_data["weeks"].append(week)
                current_week_start += timedelta(weeks=1)
        monthly_schedule.append(month_data)

    # טמפלט Jinja2
    env = Environment(loader=FileSystemLoader(os.getcwd()))
    tpl = env.get_template('bookmark_template.html')
    html = tpl.render(
        title=generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, "html").replace('.html', ''),
        date_range=f"{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y}",
        monthly_schedule=monthly_schedule
    )
    out = os.path.join(os.getcwd(), generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, "html"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out

# ==================== שימוש לדוגמה ====================
if __name__ == '__main__':
    try:
        tree_data = load_data('tanakh.json')
    except FileNotFoundError:
        print("שגיאה: קובץ הנתונים tanakh.json לא נמצא. לא ניתן להמשיך.")
        exit()
    titles_to_study = ["תנ\"ך / כתובים / תהילים"]
    study_mode = "פרקים"  # אפשר: "פרקים", "משניות", "דפים", "עמודים"
    start = date(2025, 9, 1)
    end = date(2025, 11, 30)
    example_no_study_days = {5, 6}  # 5=שישי, 6=שבת
    write_ics_file(
        titles_list=titles_to_study,
        mode=study_mode,
        start_date=start,
        end_date=end,
        tree_data=tree_data,
        no_study_weekdays_set=example_no_study_days
    )
    print("-" * 20)
    write_bookmark_html(
        titles_list=titles_to_study,
        mode=study_mode,
        start_date=start,
        end_date=end,
        tree_data=tree_data,
        no_study_weekdays_set=example_no_study_days
    )
