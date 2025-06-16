from datetime import date, timedelta
from ics import Calendar, Event
import json
import os

# --- הוספות חדשות ---
from pyluach import dates
from jinja2 import Environment, FileSystemLoader
# --------------------

# נסיון לייבא את ספריית gematria, שמשמשת להמרת מספרים לאותיות עבריות
try:
    from gematria import gematria
    HEBREW_NUMBERS_AVAILABLE = True
except ImportError:
    HEBREW_NUMBERS_AVAILABLE = False

# רשימת שמות ימי השבוע בעברית (0=ראשון, 1=שני, ..., 6=שבת)
# הערה: המתודה weekday() של pyluach.HebrewDate מחזירה 1 לראשון ו-7 לשבת.
# לכן, נצטרך להחסיר 1 מהתוצאה כדי להתאים לאינדקסים של רשימת פייתון (0-6).
HEBREW_WEEKDAY_NAMES = [
    "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"
]

# רשימת שמות חודשים עבריים (אינדקס 0 עבור ניסן, עד 12 עבור אדר ב')
# pyluach.HebrewDate.month מחזיר 1 עבור ניסן, 12 עבור אדר, 13 עבור אדר ב'
# אז נצטרך להחסיר 1 מהתוצאה של .month()
HEBREW_MONTH_NAMES = [
    "ניסן", "אייר", "סיון", "תמוז", "אב", "אלול",
    "תשרי", "מרחשון", "כסלו", "טבת", "שבט", "אדר",
    "אדר א'", "אדר ב'" # אדר א' ואדר ב' נחשבים חודשים 12 ו-13, בהתאמה.
                       # pyluach מחזיר 12 לאדר רגיל או אדר א', ו-13 לאדר ב'.
                       # נוודא שזה עובד נכון עם ה-index - 1
]


def load_data(path):
    """טוען קובץ JSON ומחזיר נתונים כמילון."""
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
    """מחשב את מספר ימי הלימוד הפעילים בטווח תאריכים."""
    count = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() not in no_study_weekdays:
            count += 1
        current_date += timedelta(days=1)
    return count

def _convert_int_to_hebrew_gematria(num):
    """ממיר מספר שלם לייצוג גימטרי באותיות עבריות."""
    if HEBREW_NUMBERS_AVAILABLE:
        try:
            return gematria.format_hebrew_number(num, punctuation=False)
        except Exception:
            return str(num)
    return str(num)

def _hebrew_chapter_sort_key(chap_str):
    """מפתח מיון לפרקים עם גימטריה."""
    if HEBREW_NUMBERS_AVAILABLE:
        try:
            num_part = chap_str.split()[-1]
            return gematria.gematria_to_int(num_part)
        except Exception:
            return chap_str
    return chap_str

def _get_node_from_path(path_parts, tree_data):
    """מחזיר צומת בעץ הנתונים לפי נתיב."""
    node = tree_data
    for part in path_parts:
        node = node.get(part)
        if node is None:
            return None
    return node

def _recursive_collect_chapters(node_data, path_parts, out_list):
    """אוסף רקורסיבית את כל הפרקים הניתנים ללימוד מצומת נתון."""
    if not isinstance(node_data, dict):
        return
    book_name = " / ".join(path_parts)
    explicit_keys = sorted([k for k, v in node_data.items() if k.startswith("פרק ") and isinstance(v, dict)], key=_hebrew_chapter_sort_key)
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
    """אוסף את כל הפרקים עבור פריטים נבחרים."""
    collected = []
    for title_path_str in titles_list:
        path_parts = title_path_str.split(" / ")
        node = _get_node_from_path(path_parts, tree_data)
        if node:
            _recursive_collect_chapters(node, path_parts, collected)
    return collected

# --- פונקציה חדשה: איסוף יחידות לימוד בודדות (משניות/דפים) ---
def _recursive_collect_units(node_data, path_parts, out_list, mode):
    """אוסף רקורסיבית את כל היחידות הניתנות ללימוד (משנה/דף) מצומת נתון."""
    if not isinstance(node_data, dict):
        return

    full_path_str = " / ".join(path_parts)

    if mode == "משניות":
        if "משניות" in node_data and isinstance(node_data["משניות"], int):
            for i in range(1, node_data["משניות"] + 1):
                out_list.append({"book_display_name": full_path_str, "unit_type": "משנה", "unit_num_int": i})
        elif any(k.startswith("פרק ") and isinstance(v, dict) for k, v in node_data.items()):
            # נסה לאסוף מכל פרק עם מספר המשניות שמופיע שם
            for k, v in node_data.items():
                if k.startswith("פרק ") and isinstance(v, dict) and "משניות" in v:
                    for i in range(1, v["משניות"] + 1):
                        prk_name = full_path_str + " / " + k
                        out_list.append({"book_display_name": prk_name, "unit_type": "משנה", "unit_num_int": i})

    elif mode in ("דפים", "עמודים"):
        if "אורך בדפים" in node_data and isinstance(node_data["אורך בדפים"], (int, float)):
            start_page = node_data.get("עמוד ראשון", 2) # קונבנציית דף ב' (למקרה שלא מצוין עמוד ראשון)
            for i in range(int(node_data["אורך בדפים"])):
                daf_num = start_page + i
                out_list.append({"book_display_name": full_path_str, "unit_type": "דף", "unit_num_int": daf_num})
    
    # ממשיכים לסרוק תתי-צמתים
    for key, val in node_data.items():
        if isinstance(val, dict) and not key.startswith("פרק "): # לא נכנסים ל"פרק X"
            _recursive_collect_units(val, path_parts + [key], out_list, mode)

def _collect_all_units_for_selection(titles_list, tree_data, mode):
    """אוסף את כל היחידות (משניות/דפים) עבור פריטים נבחרים."""
    collected = []
    for title_path_str in titles_list:
        path_parts = title_path_str.split(" / ")
        node = _get_node_from_path(path_parts, tree_data)
        if node:
            _recursive_collect_units(node, path_parts, collected, mode)
    return collected


def find_exact_whole_branch(titles_list, tree_data):
    """מוצא את הנתיב המשותף הגבוה ביותר של כל הפריטים שנבחרו."""
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
    
    if not isinstance(node, dict):
        return " / ".join(common_path)

    selected_last_parts = {p[len(common_path)] for p in split_paths if len(p) > len(common_path)}
    all_children = {key for key, val in node.items() if isinstance(val, dict) and not key.startswith("פרק")}

    if selected_last_parts and selected_last_parts == all_children:
        return " / ".join(common_path)
        
    if not selected_last_parts:
        return " / ".join(common_path)

    return None

def generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, extension):
    """יוצר שם קובץ חכם ומתאר. מקבל את סיומת הקובץ כפרמטר."""
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
    elif days > 28 and days < 33:
        time_str = "בחודש"
    elif days > 58 and days < 63:
        time_str = "בחודשיים"
    elif days % 7 == 0:
        weeks = days // 7
        time_str = "בשבוע" if weeks == 1 else f"ב-{weeks}-שבועות"
    else:
        time_str = f"ב-{days}-ימים"

    return f"{title} {time_str}.{extension}"


# --- פונקציה חדשה: מחשבת את לוח הלימוד ומחזירה מבנה נתונים ---
def _generate_study_schedule(start_date, end_date, titles_list, mode, tree_data, no_study_weekdays):
    """
    מחשבת את לוח הלימוד היומי ומחזירה רשימה של מילונים,
    כל מילון מייצג יום לימוד.
    """
    schedule = []
    study_days_count = calculate_study_days(start_date, end_date, no_study_weekdays)
    if study_days_count == 0:
        return []

    # קביעת שם בסיס
    first_title = titles_list[0].split(' / ')[-1] if titles_list else "לימוד"
    event_base_name = f"לימוד: {first_title}"
    if len(titles_list) > 1:
        event_base_name += " ועוד"

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
                    todays_units = all_units[unit_idx : unit_idx + num_today]
                    
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

    else:  # מצבים אחרים: משניות, דפים, עמודים
        all_units = _collect_all_units_for_selection(titles_list, tree_data, mode)
        print(f"[DEBUG] מצב: {mode}, מספר יחידות שהוחזרו: {len(all_units)}")
        if not all_units:
            print("[ERROR] לא הוחזרו כלל יחידות ללימוד – בדוק את הנתונים או את בחירת הענף.")

        # המרה לגימטריה והוספת פרטים ספציפיים למצב
        processed_units = []
        for i, unit in enumerate(all_units):
            try:
                book_name = unit.get("book_display_name", "לא ידוע")
                unit_num = unit.get("unit_num_int")
                if unit_num is None:
                    raise ValueError("unit_num_int חסר")

                hebrew_num = _convert_int_to_hebrew_gematria(unit_num)

                if mode == "עמודים":
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "עמוד",
                        "unit_display_name": f"{hebrew_num}א",
                        "sort_key": unit_num * 2 - 1
                    })
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "עמוד",
                        "unit_display_name": f"{hebrew_num}ב",
                        "sort_key": unit_num * 2
                    })
                elif mode == "דפים":
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "דף",
                        "unit_display_name": hebrew_num,
                        "sort_key": unit_num
                    })
                elif mode == "משניות":
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "משנה",
                        "unit_display_name": hebrew_num,
                        "sort_key": unit_num
                    })
            except Exception as e:
                print(f"[ERROR] יחידה {i} לא תקינה: {unit}")
                print(f"[EXCEPTION] {e}")

        print(f"[DEBUG] מספר יחידות לאחר עיבוד: {len(processed_units)}")

        if len(processed_units) == 0:
            print("[WARNING] לא נוצרו יחידות לעיבוד. ייתכן שהמבנה אינו תואם או שחסרים ערכים חיוניים.")

        # בדיקת דוגמה ראשונה (אם קיימת)
        if processed_units:
            print("[DEBUG] דוגמה ליחידה שעובדה:", processed_units[0])

        # מיון לפי שם ספר ומספר
        try:
            processed_units.sort(key=lambda x: (x["book_display_name"], x["sort_key"]))
        except Exception as e:
            print("[ERROR] כשל במיון היחידות:", e)

        all_units = processed_units  # נשתמש ברשימה המעובדת


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
                    todays_units = all_units[unit_idx : unit_idx + num_today]
                    
                    first_unit, last_unit = todays_units[0], todays_units[-1]
                    
                    desc = ""
                    # אם באותו ספר/מסכת
                    if first_unit["book_display_name"] == last_unit["book_display_name"]:
                        desc += f"{first_unit['book_display_name']} – {first_unit['unit_type']} {first_unit['unit_display_name']}"
                        # אם יש יותר מיחידה אחת או שהיחידות שונות (כמו עמוד א' ודף ב')
                        if len(todays_units) > 1 and first_unit["unit_display_name"] != last_unit["unit_display_name"]:
                             desc += f" עד {last_unit['unit_type']} {last_unit['unit_display_name']}"
                        # מקרים מיוחדים לדפים ועמודים שצריך לציין טווח גם אם מספר הדף זהה
                        elif len(todays_units) == 2 and mode == "עמודים" and first_unit["book_display_name"] == last_unit["book_display_name"]:
                            desc = f"{first_unit['book_display_name']} – {first_unit['unit_type']} {first_unit['unit_display_name']} עד {last_unit['unit_type']} {last_unit['unit_display_name']}"
                        elif len(todays_units) > 1: # אם יותר מיחידה אחת באותו ספר
                            desc += f" עד {last_unit['unit_type']} {last_unit['unit_display_name']}"

                    else:
                        # אם עוברים בין ספרים/מסכתות
                        desc += f"מ-{first_unit['book_display_name']} {first_unit['unit_type']} {first_unit['unit_display_name']} עד {last_unit['book_display_name']} {last_unit['unit_type']} {last_unit['unit_display_name']}"
                    
                    schedule.append({"date": current_date, "description": desc})
                    unit_idx += num_today
                day_idx += 1
            current_date += timedelta(days=1)
            
    return schedule

# --- פונקציה מעודכנת ליצירת ICS ---
def write_ics_file(titles_list, mode, start_date, end_date, tree_data, no_study_weekdays_set):
    """יוצרת וכותבת קובץ ICS על בסיס לוח הלימודים."""
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

# --- פונקציה חדשה ליצירת סימנייה ---
def write_bookmark_html(titles_list, mode, start_date, end_date, tree_data, no_study_weekdays_set):
    """יוצרת וכותבת קובץ HTML של סימנייה מעוצבת."""
    schedule = _generate_study_schedule(start_date, end_date, titles_list, mode, tree_data, no_study_weekdays_set)
    if not schedule:
        print("אזהרה: לא נוצר לוח לימודים.")
        return None

    # הכנת הנתונים עבור תבנית ה-HTML
    study_day_map = {item['date']: item['description'] for item in schedule}
    monthly_schedule = []
    
    current_date = start_date
    while current_date <= end_date:
        # התחלת חודש חדש
        month_start = date(current_date.year, current_date.month, 1)
        h_date_month_start = dates.GregorianDate(month_start.year, month_start.month, month_start.day).to_heb()
        
        # שנה עברית באותיות (ה'תשפ"ה)
        hebrew_year_str = str(h_date_month_start.year) # ברירת מחדל: מספר
        if HEBREW_NUMBERS_AVAILABLE:
            try:
                # השתמש ב-format_hebrew_number וטפל בהוספת ה'
                # format_hebrew_number יכולה להחזיר 'א', 'ב' וכו'.
                # לכן נוסיף ה' רק אם המספר הוא לפחות דו-ספרתי בגימטריה (כדי למנוע ה'א', ה'ב')
                formatted_year_part = gematria.format_hebrew_number(h_date_month_start.year, punctuation=False)
                if len(formatted_year_part) > 1: # אם זה לא תו יחיד כמו 'א'
                    hebrew_year_str = "ה'" + formatted_year_part
                else: # עבור שנים חד ספרתיות כמו א', ב', וכו'
                    hebrew_year_str = formatted_year_part
            except Exception as e:
                # אם יש שגיאה, נשאר עם הייצוג המספרי של השנה
                print(f"Error formatting Hebrew year: {e}")
                pass
        
        # שם חודש עברי מהרשימה שלנו
        # pyluach.month() מחזיר 1-13 (ניסן=1, אדר=12, אדר ב'=13)
        # אז נחסיר 1 לאינדקס רשימה
        hebrew_month_name = HEBREW_MONTH_NAMES[h_date_month_start.month - 1] 
        
        month_name = f"{hebrew_month_name} {hebrew_year_str}"
        
        month_data = {"month_name": month_name, "weeks": []}
        
        # מצא את יום ראשון של השבוע הראשון בחודש
        # מתחיל מהשבוע של היום הראשון בחודש, או מיום ראשון לפניו
        cal_start_date = month_start - timedelta(days=(month_start.weekday() + 1) % 7)
        
        month_ended = False
        while not month_ended:
            week = []
            for i in range(7):
                day = cal_start_date + timedelta(days=i)
                h_date = dates.GregorianDate(day.year, day.month, day.day).to_heb()
                
                day_info = {
                    "is_in_month": day.month == month_start.month,
                    "hebrew_date": HEBREW_WEEKDAY_NAMES[h_date.weekday() - 1],
                    "study_portion": study_day_map.get(day)
                }
                week.append(day_info)

                # תנאי עצירה עבור השבועות: אם עברנו את החודש המקורי וגם את תאריך הסיום הכללי
                if day.month != month_start.month and day >= month_start:
                    if day.month == current_date.month and day.day == current_date.day: # ודא שאתה לא עובר את תאריך הסיום
                        pass # נמשיך אם זה עדיין בטווח התאריכים הכללי
                    else:
                        month_ended = True
                
            month_data["weeks"].append(week)
            cal_start_date += timedelta(weeks=1)
            # אם עברנו את תאריך הסיום הכללי, צא מלולאת החודשים
            if cal_start_date > end_date and not month_ended: # בדוק גם אם החודש נגמר
                 month_ended = True # סמן חודש כגמור אם עברנו את תאריך הסיום
            
        # ודא שלא מוסיפים חודשים ריקים בסוף
        if month_data["weeks"]:
            monthly_schedule.append(month_data)
        
        # קפוץ לתחילת החודש הבא
        next_month_year = month_start.year if month_start.month < 12 else month_start.year + 1
        next_month = month_start.month + 1 if month_start.month < 12 else 1
        current_date = date(next_month_year, next_month, 1)
        
    # טעינת התבנית ורינדור ה-HTML
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('bookmark_template.html')

    filename_base = generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, "html")
    title = filename_base.replace('.html', '')
    date_range_str = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    
    html_content = template.render(
        title=title,
        date_range=date_range_str,
        monthly_schedule=monthly_schedule
    )

    # כתיבת הקובץ
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename_base)
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"קובץ סימנייה נוצר בהצלחה: {full_path}")
        return full_path
    except Exception as e:
        print(f"שגיאה בכתיבת קובץ HTML: {e}")
        return None


# --- דוגמת שימוש ---
if __name__ == '__main__':
    # טעינת הנתונים (יש לוודא שקובץ ה-JSON נמצא באותה תיקייה)
    # נניח ששם הקובץ הוא tanakh.json
    try:
        tree_data = load_data('tanakh.json')
    except FileNotFoundError:
        print("שגיאה: קובץ הנתונים tanakh.json לא נמצא. לא ניתן להמשיך.")
        exit()

    # הגדרות הלימוד
    # לדוגמה: לימוד כל ספר תהילים בפרקים
    titles_to_study = ["תנ\"ך / כתובים / תהילים"] # או למשל: ["משנה / סדר זרעים / ברכות"]
    study_mode = "פרקים" # אפשרויות: "פרקים", "משניות", "דפים", "עמודים"
    start = date(2025, 9, 1)
    end = date(2025, 11, 30)
    
    # ימי חופש לדוגמה (שבת ושישי)
    example_no_study_days = {5, 4} # 5=שישי, 6=שבת (עבור weekday() 0=שני...6=שבת)

    # --- יצירת הפלטים ---
    
    # 1. יצירת קובץ ICS
    write_ics_file(
        titles_list=titles_to_study,
        mode=study_mode,
        start_date=start,
        end_date=end,
        tree_data=tree_data,
        no_study_weekdays_set=example_no_study_days
    )

    print("-" * 20)

    # 2. יצירת סימניית HTML
    write_bookmark_html(
        titles_list=titles_to_study,
        mode=study_mode,
        start_date=start,
        end_date=end,
        tree_data=tree_data,
        no_study_weekdays_set=example_no_study_days
    )