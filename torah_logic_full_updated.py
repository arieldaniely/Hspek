from datetime import date, timedelta, datetime, time
from ics import Calendar, Event, DisplayAlarm
import json
import os
import re
from urllib.parse import quote_plus, quote

from pyluach import dates, hebrewcal, parshios
from jinja2 import Environment, FileSystemLoader
from collections import defaultdict

# כתובת ברירת מחדל לפתיחת חומר הלימוד היומי
# {ref} מוחלף בהפניה המדויקת בספריא (לדוגמה "בראשית.א-ב")
DEFAULT_LESSON_LINK = "https://www.sefaria.org.il/{ref}"

# ==================== עזרות גימטריה ====================
class Gematria:
    """
    מחלקה המספקת כלי עזר לעבודה עם גימטריה עברית.
    כולל המרה ממספר לגימטריה וההפך.
    """
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
        ממיר מספר שלם לגימטריה עברית.

        תומך במספרים עד 9999.
        אלפים מסומנים עם גרש (למשל, 1000 -> 'א׳', 5784 -> 'ה׳תשפד').
        כולל טיפול מיוחד למספרים 15 ('טו') ו-16 ('טז').
        אופציונלית מוסיף גרשיים לפני האות האחרונה אם המספר מורכב מיותר מאות אחת.

        Args:
            num (int): המספר השלם להמרה.
            punctuation (bool, optional): האם להוסיף גרשיים. ברירת מחדל True.

        Returns:
            str: המספר בייצוג גימטריה עברית, או המספר כמחרוזת אם הקלט אינו תקין.
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
            if thousands in cls._hebrew_letters_map: # תומך באלפים בודדים (1-9)
                result.append(cls._hebrew_letters_map[thousands] + '׳')


        # טיפול בשאר המספר (עד 999)
        remainder = num % 1000
        if remainder == 0 and thousands > 0:
            # אם יש אלפים ואין שארית (לדוגמה 1000, 2000), סיימנו
            pass
        elif remainder == 15: # טיפול מיוחד ל-15
            result.append('טו')
        elif remainder == 16: # טיפול מיוחד ל-16
            result.append('טז')
        else:
            # פירוק למאות, עשרות ויחידות
            hundreds = (remainder // 100) * 100
            tens_units = remainder % 100

            if hundreds > 0:
                result.append(cls._hebrew_letters_map.get(hundreds, '')) # הוספת אותיות המאות
            
            # אם יש שאר עשרות ויחידות
            if tens_units > 0 and tens_units != 15 and tens_units != 16:
                tens = (tens_units // 10) * 10
                units = tens_units % 10

                if tens > 0:
                    result.append(cls._hebrew_letters_map.get(tens, '')) # הוספת אותיות העשרות
                if units > 0:
                    result.append(cls._hebrew_letters_map.get(units, '')) # הוספת אותיות היחידות
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

        return final_string

    @classmethod
    def gematria_to_int(cls, hebrew: str) -> int:
        """
        ממיר מחרוזת גימטריה עברית למספר שלם.

        מתעלם מגרש (׳) ומגרשיים (״) לצורך החישוב.
        סוכם את הערכים המספריים של כל אות עברית במחרוזת.

        Args:
            hebrew (str): המחרוזת בגימטריה עברית.

        Returns:
            int: הערך המספרי השלם של הגימטריה.
        """
        total = 0
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

# ==================== פונקציות עזר לחגים לאומיים ====================
def get_israeli_national_holiday_on_gregorian_date(gregorian_date_to_check: date, hebrew_year: int) -> str | None:
    """
    בודק האם תאריך גרגוריאני נתון הוא יום הזיכרון, יום העצמאות או יום ירושלים
    בשנה עברית מסוימת, תוך התחשבות בדחיות.

    Args:
        gregorian_date_to_check (date): התאריך הגרגוריאני לבדיקה.
        hebrew_year (int): השנה העברית לבדיקת החגים.

    Returns:
        str | None: שם החג אם הוא חל בתאריך הנתון, אחרת None.
    """

    # --- יום הזיכרון ויום העצמאות ---
    # יום העצמאות חל במקור בה' באייר. יום הזיכרון יום לפניו.
    # חודש אייר הוא החודש השני לפי ספירת חודשי השנה של pyluach (ניסן=1)
    
    # קביעת ה' באייר המקורי
    hd_iyar_5_original = dates.HebrewDate(hebrew_year, 2, 5)
    gd_iyar_5_original = hd_iyar_5_original.to_pydate()
    weekday_iyar_5_original = gd_iyar_5_original.weekday()  # שני=0, שלישי=1 ... שישי=4, שבת=5, ראשון=6

    actual_hd_yom_haatzmaut = hd_iyar_5_original

    # כללי דחייה/הקדמה ליום העצמאות:
    if weekday_iyar_5_original == 4:  # אם ה' באייר הוא יום שישי
        # יום העצמאות מוקדם ליום חמישי, ד' באייר
        actual_hd_yom_haatzmaut = dates.HebrewDate(hebrew_year, 2, 4)
    elif weekday_iyar_5_original == 5:  # אם ה' באייר הוא שבת
        # יום העצמאות מוקדם ליום חמישי, ג' באייר
        actual_hd_yom_haatzmaut = dates.HebrewDate(hebrew_year, 2, 3)
    elif weekday_iyar_5_original == 0:  # אם ה' באייר הוא יום שני (כלומר ד' באייר, יום הזיכרון המקורי, הוא ראשון)
        # יום העצמאות נדחה ליום שלישי, ו' באייר (כדי למנוע חילול שבת בהכנות ליום הזיכרון)
        actual_hd_yom_haatzmaut = dates.HebrewDate(hebrew_year, 2, 6)

    # חישוב התאריך הגרגוריאני הסופי של יום העצמאות ויום הזיכרון
    actual_gd_yom_haatzmaut = actual_hd_yom_haatzmaut.to_pydate()
    actual_gd_yom_hazikaron = actual_gd_yom_haatzmaut - timedelta(days=1)

    if gregorian_date_to_check == actual_gd_yom_hazikaron:
        return "יום הזיכרון"
    if gregorian_date_to_check == actual_gd_yom_haatzmaut:
        return "יום העצמאות"

    # --- יום ירושלים ---
    # יום ירושלים חל במקור בכ"ח באייר
    hd_iyar_28_original = dates.HebrewDate(hebrew_year, 2, 28)
    gd_iyar_28_original = hd_iyar_28_original.to_pydate()
    weekday_iyar_28_original = gd_iyar_28_original.weekday()

    actual_hd_yom_yerushalayim = hd_iyar_28_original

    # כללי דחייה/הקדמה ליום ירושלים:
    if weekday_iyar_28_original == 4:  # אם כ"ח באייר הוא יום שישי
        # יום ירושלים מוקדם ליום חמישי, כ"ז באייר
        actual_hd_yom_yerushalayim = dates.HebrewDate(hebrew_year, 2, 27)
    elif weekday_iyar_28_original == 5: # אם כ"ח באייר הוא שבת
        # יום ירושלים נדחה ליום ראשון, כ"ט באייר (לפי הנוהג המקובל)
        actual_hd_yom_yerushalayim = dates.HebrewDate(hebrew_year, 2, 29)
        
    actual_gd_yom_yerushalayim = actual_hd_yom_yerushalayim.to_pydate()
    if gregorian_date_to_check == actual_gd_yom_yerushalayim:
        return "יום ירושלים"

    return None

# ==================== בדיקת חגים ====================
def is_holiday(gregorian_date: date) -> bool:
    """בודק אם תאריך גרגוריאני כלשהו הוא חג או מועד ישראלי (לא כולל שבת)."""
    g_date = dates.GregorianDate(gregorian_date.year, gregorian_date.month, gregorian_date.day)
    h_d = g_date.to_heb()
    regular_holiday = h_d.holiday(hebrew=True, israel=True)
    national = get_israeli_national_holiday_on_gregorian_date(gregorian_date, h_d.year)
    return bool(regular_holiday or national)

# ==================== כלי עזר ====================
def load_data(path):
    """
    טוען נתונים מקובץ JSON.

    Args:
        path (str): הנתיב לקובץ ה-JSON.

    Returns:
        dict: מילון המכיל את נתוני ה-JSON, או None אם הקובץ לא נמצא או שיש שגיאה בטעינה.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def has_relevant_data_recursive(node, mode):
    """
    בודק באופן רקורסיבי האם לצומת (node) או לאחד מצאצאיו יש נתונים רלוונטיים לסוג הספירה (mode).

    Args:
        node (dict or any): הצומת הנוכחי לבדיקה (בדרך כלל מילון המייצג חלק מעץ הנתונים).
        mode (str): סוג הספירה ("פרקים", "משניות", "דפים", "עמודים").

    Returns:
        bool: True אם נמצאו נתונים רלוונטיים, False אחרת.
    """
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
        # מדלגים על מפתחות שאינם מייצגים תתי-ענפים לצורך הרקורסיה
        if key in ["אורך בדפים", "עמוד אחרון", "משניות", "פרקים"] and not isinstance(val, dict):
            continue
        if isinstance(val, dict):
            # קריאה רקורסיבית עבור תתי-צמתים
            if has_relevant_data_recursive(val, mode):
                return True
    return False

def get_length_from_node(node, mode):
    """
    מחזיר את האורך הכולל (מספר יחידות) עבור צומת נתון וכל תתי-הצמתים שלו,
    בהתאם לסוג הספירה (mode).

    Args:
        node (dict or any): הצומת הנוכחי לחישוב (בדרך כלל מילון).
        mode (str): סוג הספירה ("פרקים", "משניות", "דפים", "עמודים").
    Returns:
        int or float: האורך הכולל של היחידות בצומת ובתתי-הצמתים שלו.
    """
    total = 0
    if not isinstance(node, dict):
        return 0

    # קודם כל סורקים את תתי-הצמתים
    for key, val in node.items():
        if isinstance(val, dict):
            # סכימה רקורסיבית של אורכים מתתי-צמתים
            total += get_length_from_node(val, mode)

    # לאחר מכן מוסיפים את הערך של הצומת הנוכחי
    if mode == "פרקים":
        if "פרקים" in node and isinstance(node["פרקים"], int):
            total += node["פרקים"]
        else:
            # אם אין מפתח "פרקים" מפורש, סופרים תתי-צמתים ששמם מתחיל ב"פרק "
            total += sum(1 for key, val in node.items() if key.startswith("פרק ") and isinstance(val, dict))
    elif mode == "משניות":
        if "משניות" in node and isinstance(node["משניות"], int):
            total += node["משניות"]
    elif mode == "דפים":
        if "אורך בדפים" in node and isinstance(node["אורך בדפים"], (int, float)):
            total += node["אורך בדפים"]
    elif mode == "עמודים":
        if "אורך בדפים" in node and isinstance(node["אורך בדפים"], (int, float)):
            total += node["אורך בדפים"] * 2 # כל דף הוא שני עמודים

    return total

def calculate_study_days(start_date, end_date, no_study_weekdays, skip_holidays=False):
    """
    מחשב את מספר ימי הלימוד הפנויים בטווח תאריכים נתון,
    בניכוי ימי חופשה שבועיים וחגים.

    Args:
        start_date (date): תאריך התחלת הטווח.
        end_date (date): תאריך סיום הטווח (כולל).
        no_study_weekdays (set[int]): קבוצת מספרים המייצגים ימים בשבוע בהם אין לימוד
                                      (0=שני, 1=שלישי, ..., 6=ראשון).
        skip_holidays (bool, optional): האם לדלג על חגים בלוח הלימוד.
    Returns:
        int: מספר ימי הלימוד הפנויים.
    """
    count = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() not in no_study_weekdays:
            if not (skip_holidays and is_holiday(current_date)):
                count += 1
        current_date += timedelta(days=1)
    return count

def _convert_int_to_hebrew_gematria(num):
    """
    פונקציית עזר להמרת מספר שלם לגימטריה עברית ללא פיסוק.
    משתמשת במחלקת Gematria.

    Args:
        num (int): המספר להמרה.
    Returns:
        str: המספר בגימטריה, או כמחרוזת אם ההמרה נכשלת.
    """
    if HEBREW_NUMBERS_AVAILABLE:
        try:
            return Gematria.format_hebrew_number(num, punctuation=False)
        except Exception:
            return str(num)
    return str(num)

def _hebrew_chapter_sort_key(chap_str):
    """
    פונקציית מפתח למיון שמות פרקים בעברית (למשל, "פרק א", "פרק יא").
    ממירה את החלק המספרי של שם הפרק למספר שלם לצורך מיון נכון.

    Args:
        chap_str (str): שם הפרק (למשל, "פרק א'").

    Returns:
        int or str: הערך המספרי של הפרק אם ההמרה הצליחה, אחרת המחרוזת המקורית.
    """
    if HEBREW_NUMBERS_AVAILABLE:
        try:
            num_part = chap_str.split()[-1]
            return Gematria.gematria_to_int(num_part)
        except Exception:
            return chap_str
    return chap_str

def _get_node_from_path(path_parts, tree_data):
    """
    מאחזר צומת ספציפי מעץ הנתונים על פי נתיב נתון.

    Args:
        path_parts (list[str]): רשימת חלקי הנתיב לצומת המבוקש.
        tree_data (dict): מילון המייצג את כלל עץ הנתונים.

    Returns:
        dict or None: הצומת המבוקש אם נמצא, אחרת None.
    """
    node = tree_data
    for part in path_parts:
        node = node.get(part)
        if node is None:
            return None
    return node

def _recursive_collect_chapters(node_data, path_parts, out_list):
    """
    אוסף באופן רקורסיבי את כל הפרקים מצומת נתון ומתתי-הצמתים שלו.
    הפרקים נאספים עם שם הספר המלא שלהם.

    Args:
        node_data (dict): הצומת הנוכחי בעץ הנתונים.
        path_parts (list[str]): רשימת חלקי הנתיב עד לצומת הנוכחי (משמש לבניית שם הספר).
        out_list (list[dict]): רשימה אליה יתווספו הפרקים שנאספו.
                               כל פריט ברשימה הוא מילון עם "book_display_name" ו-"chapter_name".
    """
    if not isinstance(node_data, dict):
        return
    book_name = " / ".join(path_parts)
    explicit_keys = sorted(
        # איסוף מפתחות שמתחילים ב "פרק " ומייצגים פרקים מפורשים
        [k for k, v in node_data.items() if k.startswith("פרק ") and isinstance(v, dict)],
        key=_hebrew_chapter_sort_key
    )
    if explicit_keys:
        for chap_key in explicit_keys:
            out_list.append({"book_display_name": book_name, "chapter_name": chap_key})
    elif "פרקים" in node_data and isinstance(node_data["פרקים"], int):
        # אם יש מפתח "פרקים" עם מספר, מייצרים שמות פרקים גנריים
        num_chaps = node_data["פרקים"]
        for i in range(1, num_chaps + 1):
            hebrew_num = _convert_int_to_hebrew_gematria(i)
            out_list.append({"book_display_name": book_name, "chapter_name": f"פרק {hebrew_num}"})
    
    # קריאה רקורסיבית לתתי-צמתים שאינם פרקים מפורשים
    for key, val in node_data.items():
        if isinstance(val, dict) and not key.startswith("פרק "):
            _recursive_collect_chapters(val, path_parts + [key], out_list)

def _collect_all_chapters_for_selection(titles_list, tree_data):
    """
    אוסף את כל הפרקים הרלוונטיים לבחירה הנוכחית של המשתמש בעץ.

    Args:
        titles_list (list[str]): רשימת הנתיבים המלאים של הפריטים שנבחרו בעץ.
        tree_data (dict): מילון המייצג את כלל עץ הנתונים.
    Returns:
        list[dict]: רשימת כל הפרקים שנאספו, כאשר כל פריט הוא מילון.
    """
    collected = []
    for title_path_str in titles_list:
        path_parts = title_path_str.split(" / ")
        node = _get_node_from_path(path_parts, tree_data)
        if node:
            _recursive_collect_chapters(node, path_parts, collected)
    return collected

def _recursive_collect_units(node_data, path_parts, out_list, mode):
    """
    אוסף באופן רקורסיבי יחידות לימוד (משניות, דפים) מצומת נתון ומתתי-הצמתים שלו.

    Args:
        node_data (dict): הצומת הנוכחי בעץ הנתונים.
        path_parts (list[str]): רשימת חלקי הנתיב עד לצומת הנוכחי.
        out_list (list[dict]): רשימה אליה יתווספו היחידות שנאספו.
                               כל פריט הוא מילון עם פרטי היחידה.
        mode (str): סוג היחידות לאיסוף ("משניות", "דפים", "עמודים").
    """
    if not isinstance(node_data, dict):
        return
    full_path_str = " / ".join(path_parts)

    if mode == "משניות":
        if "משניות" in node_data and isinstance(node_data["משניות"], int):
            for i in range(1, node_data["משניות"] + 1):
                # הוספת משניות אם הצומת עצמו מגדיר מספר משניות
                out_list.append({"book_display_name": full_path_str, "unit_type": "משנה", "unit_num_int": i})
        elif any(k.startswith("פרק ") and isinstance(v, dict) for k, v in node_data.items()):
            for k, v in node_data.items():
                if k.startswith("פרק ") and isinstance(v, dict) and "משניות" in v:
                    for i in range(1, v["משניות"] + 1):
                        prk_name = full_path_str + " / " + k
                        out_list.append({"book_display_name": prk_name, "unit_type": "משנה", "unit_num_int": i})
    
    elif mode in ("דפים", "עמודים"):
        if "אורך בדפים" in node_data and isinstance(node_data["אורך בדפים"], (int, float)):
            start_page = node_data.get("עמוד ראשון", 2) # דף ברירת מחדל להתחלה הוא ב'
            for i in range(int(node_data["אורך בדפים"])):
                daf_num = start_page + i
                # עבור "דפים" ו"עמודים", היחידה הבסיסית היא דף. "עמודים" יטופל בהמשך.
                out_list.append({"book_display_name": full_path_str, "unit_type": "דף", "unit_num_int": daf_num})
    
    # קריאה רקורסיבית לתתי-צמתים שאינם פרקים מפורשים (עבור מבנים מקוננים)
    for key, val in node_data.items():
        if isinstance(val, dict) and not key.startswith("פרק "):
            _recursive_collect_units(val, path_parts + [key], out_list, mode)

def _collect_all_units_for_selection(titles_list, tree_data, mode):
    """
    אוסף את כל יחידות הלימוד (משניות, דפים) הרלוונטיות לבחירה הנוכחית של המשתמש.

    Args:
        titles_list (list[str]): רשימת הנתיבים המלאים של הפריטים שנבחרו בעץ.
        tree_data (dict): מילון המייצג את כלל עץ הנתונים.
        mode (str): סוג היחידות לאיסוף ("משניות", "דפים", "עמודים").

    Returns:
        list[dict]: רשימת כל היחידות שנאספו.
    """
    collected = []
    for title_path_str in titles_list:
        path_parts = title_path_str.split(" / ")
        node = _get_node_from_path(path_parts, tree_data)
        if node:
            # קריאה לפונקציה הרקורסיבית עבור כל פריט שנבחר
            _recursive_collect_units(node, path_parts, collected, mode)
    return collected

def find_exact_whole_branch(titles_list, tree_data):
    """
    בודק האם רשימת הפריטים שנבחרו מייצגת ענף שלם ומדויק בעץ הנתונים.
    ענף שלם משמעו שנבחר צומת אב וכל ילדיו הישירים (שאינם פרקים).

    Args:
        titles_list (list[str]): רשימת הנתיבים המלאים של הפריטים שנבחרו.
        tree_data (dict): מילון המייצג את כלל עץ הנתונים.

    Returns:
        str or None: הנתיב המלא לענף המשותף אם נמצא ענף שלם, אחרת None.
    """
    if not titles_list:
        return None
    split_paths = [title.split(" / ") for title in titles_list] # פיצול כל נתיב לחלקיו
    common_path = []
    for level in zip(*split_paths):
        if len(set(level)) == 1:
            common_path.append(level[0])
        else:
            break
    if not common_path:
        # אם אין נתיב משותף כלל, והיו יותר מבחירה אחת, זה לא ענף שלם
        if len(split_paths) > 1:
            return None
        # אם הייתה בחירה בודדת, הנתיב המשותף הוא הנתיב של הבחירה
        common_path = split_paths[0]

    # ניווט לצומת המשותף
    node = tree_data
    for part in common_path:
        if part in node:
            node = node[part]
        else:
            return None # נתיב לא תקין

    # בדיקה האם כל הילדים של הצומת המשותף נבחרו
    selected_last_parts = {p[len(common_path)] for p in split_paths if len(p) > len(common_path)}
    # ילדים פוטנציאליים של הצומת (לא כולל "פרק X" כי הם לא נחשבים תתי-ענפים לבחירה)
    all_children = {key for key, val in node.items() if isinstance(val, dict) and not key.startswith("פרק")}

    if selected_last_parts and selected_last_parts == all_children:
        # אם נבחרו חלקים נוספים והם בדיוק כל הילדים של הצומת המשותף
        return " / ".join(common_path)
    if not selected_last_parts:
        # אם לא נבחרו חלקים נוספים, זה אומר שהצומת המשותף עצמו נבחר (כעלה או כצומת אב יחיד)
        return " / ".join(common_path)
    
    return None

#==================== יוצר שם חכם ====================
def generate_smart_filename(titles_list, mode, start_date, end_date, tree_data, extension, units_per_day=None):
    """
    יוצר שם קובץ חכם ואינפורמטיבי עבור קובץ הלימוד (ICS או HTML).

    Args:
        titles_list (list[str]): רשימת הנתיבים המלאים של הפריטים שנבחרו בעץ.
        mode (str): סוג הלימוד (פרקים, משניות, דפים, עמודים).
        start_date (date): תאריך התחלת הלימוד.
        end_date (date): תאריך סיום הלימוד (רלוונטי אם units_per_day הוא None).
        tree_data (dict): מבנה הנתונים המלא של עץ הלימוד.
        extension (str): סיומת הקובץ הרצויה (למשל, "ics" או "html").
        units_per_day (int, optional): מספר יחידות לימוד ביום (אם רלוונטי). ברירת מחדל None.

    Returns:
        str: שם הקובץ שנוצר.
    """
    # נסיון למצוא שם ראשי על בסיס בחירה של ענף שלם
    exact_branch = find_exact_whole_branch(titles_list, tree_data)

    if exact_branch:
        # אם נבחר ענף שלם, השם הראשי יהיה שם הענף
        title = exact_branch.split(" / ")[-1]
    else:
        # אם נבחרו פריטים מרובים או חלקיים, נבנה שם מורכב יותר
        names = [t.split(" / ")[-1] for t in titles_list]
        unique_names = list(dict.fromkeys(names)) # הסרת כפילויות בשמות

        if len(unique_names) == 1:
            title = f"{unique_names[0]} (חלקים)"
        elif len(unique_names) == 2:
            title = f"{unique_names[0]} ו{unique_names[1]}"
        elif len(unique_names) >= 3:
            title = f"{unique_names[0]}, {unique_names[1]} ועוד"
        else:
            title = "לימוד" # שם ברירת מחדל אם אין כותרות

    # יצירת מחרוזת המתארת את משך הזמן או ההספק
    if units_per_day:
        # אם הוגדר הספק יומי, נשתמש בו
        time_str = f"{units_per_day} {mode} ליום"
    else:
        # אחרת, נחשב את משך הזמן על פי תאריכי ההתחלה והסיום
        days = (end_date - start_date).days + 1
        if days > 360:
            years = round(days / 365)
            time_str = "בשנה" if years == 1 else f"ב-{years}-שנים"
        elif 28 < days < 33: # טווח של חודש בערך
            time_str = "בחודש"
        elif 58 < days < 63: # טווח של חודשיים בערך
            time_str = "בחודשיים"
        elif (days % 30) <= 3 or (days % 30) >= 27: # טווח של חודשים שלמים בערך
            time_str = f"ב{days // 30} חודשים"
        elif days % 7 == 0: # אם מתחלק בדיוק בשבועות
            weeks = days // 7
            if weeks == 2:
                time_str = "בשבועיים"
            else:
                time_str = "בשבוע" if weeks == 1 else f"ב-{weeks}-שבועות"
        else:
            time_str = f"ב-{days}-ימים"
    # הרכבת שם הקובץ הסופי
    return f"{title} {time_str}.{extension}"

# ==================== מחשב לוח לימוד ====================
def _generate_study_schedule(
        start_date,
        end_date,
        titles_list,
        mode,
        tree_data,
        no_study_weekdays,
        units_per_day=None,
        skip_holidays=False
    ):
    """
    מייצר את לוח הלימודים המפורט יום אחר יום.

    Args:
        start_date (date): תאריך התחלת הלימוד.
        end_date (date): תאריך סיום הלימוד (במצב חלוקה לפי טווח).
        titles_list (list[str]): רשימת הנתיבים של הפריטים הנלמדים.
        mode (str): סוג הלימוד ("פרקים", "משניות", "דפים", "עמודים").
        tree_data (dict): עץ הנתונים המלא.
        no_study_weekdays (set[int]): קבוצת ימי חופשה שבועיים.
        units_per_day (int, optional): מספר יחידות לימוד ביום (במצב הספק קבוע).
                                       אם None, הלימוד מחולק על פני טווח התאריכים.
        skip_holidays (bool, optional): האם לדלג על חגים בלוח הלימוד.
    Returns:
        list[dict]: רשימת אירועי לימוד. כל פריט מכיל:
            - ``date``: התאריך הגרגוריאני.
            - ``description``: תיאור הלימוד ליום.
            - ``first_unit`` ו-``last_unit``: פרטי היחידות הפותחות והחותמות
              את הלימוד באותו יום.
    """
    schedule = []

    # בחירת אוסף יחידות לפי מצב
    if mode == "פרקים":
        all_units = _collect_all_chapters_for_selection(titles_list, tree_data)
    else:
        all_units = _collect_all_units_for_selection(titles_list, tree_data, mode)
        # המשך העיבוד ל"עמודים"/"דפים"/"משניות" (כמו בקוד שלך):
        if mode in ("עמודים", "דפים", "משניות"):
            processed_units = []
            for unit in all_units:
                book_name = unit.get("book_display_name", "לא ידוע")
                unit_num = unit.get("unit_num_int")
                if unit_num is None:
                    continue
                hebrew_num = _convert_int_to_hebrew_gematria(unit_num)
                if mode == "עמודים":
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "עמוד",
                        "unit_display_name": f"{hebrew_num}.",
                        "sort_key": unit_num * 2 - 1,  # עמוד א'
                        "unit_num_int": unit_num,
                        "side": "a",
                    })
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "עמוד",
                        "unit_display_name": f"{hebrew_num}:",
                        "sort_key": unit_num * 2,  # עמוד ב'
                        "unit_num_int": unit_num,
                        "side": "b",
                    })
                elif mode == "דפים":
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "דף",
                        "unit_display_name": hebrew_num,
                        "sort_key": unit_num,
                        "unit_num_int": unit_num,
                    })
                elif mode == "משניות":
                    processed_units.append({
                        "book_display_name": book_name,
                        "unit_type": "משנה",
                        "unit_display_name": hebrew_num,
                        "sort_key": unit_num,
                        "unit_num_int": unit_num,
                    })
            # processed_units.sort(key=lambda x: (x["book_display_name"], x["sort_key"])) # מיון היחידות
            all_units = processed_units

    total_units = len(all_units)
    if total_units == 0:
        return []

    current_date = start_date
    day_idx = 0
    unit_idx = 0

    if units_per_day is None:
        # מצב רגיל: מחלקים לפי מספר ימי לימוד בפועל בין התאריכים
        study_days_count = calculate_study_days(start_date, end_date, no_study_weekdays, skip_holidays)
        if study_days_count == 0:
            return []
        base_per_day = total_units // study_days_count
        remainder = total_units % study_days_count # יחידות עודפות לחלוקה
        allocations = [base_per_day + (1 if i < remainder else 0) for i in range(study_days_count)]

        while current_date <= end_date and unit_idx < total_units:
            # לולאה על כל יום בטווח התאריכים
            if current_date.weekday() not in no_study_weekdays and not (skip_holidays and is_holiday(current_date)):
                num_today = allocations[day_idx]
                if num_today > 0:
                    todays_units = all_units[unit_idx:unit_idx + num_today]
                    first_unit, last_unit = todays_units[0], todays_units[-1]
                    desc = build_description(first_unit, last_unit, mode)
                    schedule.append({
                        "date": current_date,
                        "description": desc,
                        "first_unit": first_unit,
                        "last_unit": last_unit,
                        "units": todays_units,
                    })
                    unit_idx += num_today
                day_idx += 1 # קדם אינדקס יום לימוד
            current_date += timedelta(days=1)
    else:
        # מצב הספק יומי קבוע
        while unit_idx < total_units:
            if current_date.weekday() not in no_study_weekdays and not (skip_holidays and is_holiday(current_date)):
                # לוקחים units_per_day יחידות או פחות אם זה סוף הרשימה
                todays_units = all_units[unit_idx:unit_idx + units_per_day]
                first_unit, last_unit = todays_units[0], todays_units[-1]
                desc = build_description(first_unit, last_unit, mode)
                schedule.append({
                    "date": current_date,
                    "description": desc,
                    "first_unit": first_unit,
                    "last_unit": last_unit,
                    "units": todays_units,
                })
                unit_idx += len(todays_units)
            current_date += timedelta(days=1)

    return schedule

# פונקציה עזר משותפת לבניית התיאור
def build_description(first_unit, last_unit, mode):
    """
    בונה את מחרוזת התיאור עבור יום לימוד, על סמך היחידה הראשונה והאחרונה הנלמדות באותו יום.

    Args:
        first_unit (dict): פרטי היחידה הראשונה ליום.
        last_unit (dict): פרטי היחידה האחרונה ליום.
        mode (str): סוג הלימוד.

    Returns:
        str: מחרוזת התיאור.
    """
    if mode == "פרקים":
        if first_unit["book_display_name"] == last_unit["book_display_name"]:
            desc = f"{first_unit['book_display_name']} – {first_unit['chapter_name']}"
            if first_unit["chapter_name"] != last_unit["chapter_name"]:
                desc += f" עד {last_unit['chapter_name']}"
        else:
            desc = f"מ-{first_unit['book_display_name']} {first_unit['chapter_name']} עד {last_unit['book_display_name']} {last_unit['chapter_name']}"
    else:
        if first_unit["book_display_name"] == last_unit["book_display_name"]:
            desc = f"{first_unit['book_display_name']} – {first_unit['unit_type']} {first_unit['unit_display_name']}"
            if first_unit["unit_display_name"] != last_unit["unit_display_name"]:
                desc += f" עד {last_unit['unit_type']} {last_unit['unit_display_name']}"
        else:
            desc = f"מ-{first_unit['book_display_name']} {first_unit['unit_type']} {first_unit['unit_display_name']} עד {last_unit['book_display_name']} {last_unit['unit_type']} {last_unit['unit_display_name']}"
    return desc

TORAH_TREE_CACHE = None

def _load_torah_tree():
    """Load and cache the main Torah tree data used for book lengths."""
    global TORAH_TREE_CACHE
    if TORAH_TREE_CACHE is None:
        with open("torah_tree_data_full.json", "r", encoding="utf-8") as f:
            TORAH_TREE_CACHE = json.load(f)
    return TORAH_TREE_CACHE

def build_sefaria_ref(first_unit: dict, last_unit: dict, mode: str) -> str | list[str] | None:
    """Construct Sefaria reference(s).

    ``mode`` indicates the unit granularity (פרקים/משניות/דפים/עמודים) only.
    The content category (Tanakh/Mishnah/Talmud) is detected from the path of
    ``first_unit``.  When the portion spans two different books, two references
    are returned.
    """
    with open("sefaria_masechet_map.json", "r", encoding="utf-8") as f:
        SEFARIA_MASECHET_MAP = json.load(f)

    def detect_category(unit: dict) -> str | None:
        """Return 'tanakh', 'mishnah' or 'talmud' based on the unit path."""
        path = unit.get("book_display_name", "")
        if not path:
            return None
        first = path.split(" / ")[0]
        if first.startswith("משנה"):
            return "mishnah"
        if "תלמוד" in first:
            return "talmud"
        if first in ("תנך", "תנ""ך"):
            return "tanakh"
        return None

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

    category = detect_category(first_unit)
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
        category2 = detect_category(last_unit)
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
            last_ch_num = max(
                Gematria.gematria_to_int(k.split()[-1]) for k in ch_keys
            )
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
                f"{book2}.{start_second}-{end_second}" if end_second != start_second else f"{book2}.{start_second}"
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

# ==================== יצירת ICS ====================
def write_ics_file(
    titles_list,
    mode,
    start_date,
    end_date,
    tree_data,
    no_study_weekdays_set,
    units_per_day=None,
    skip_holidays=False,
    alarm_time: time | None = None,
    link_template: str = DEFAULT_LESSON_LINK,
):
    """
    יוצר קובץ ICS (קובץ לוח שנה) המכיל את אירועי הלימוד.

    Args:
        titles_list (list[str]): רשימת הנתיבים של הפריטים הנלמדים.
        mode (str): סוג הלימוד.
        start_date (date): תאריך התחלת הלימוד.
        end_date (date): תאריך סיום הלימוד (במצב חלוקה לפי טווח).
        tree_data (dict): עץ הנתונים המלא.
        no_study_weekdays_set (set[int]): קבוצת ימי חופשה שבועיים.
        units_per_day (int, optional): הספק יומי (אם רלוונטי).
        skip_holidays (bool, optional): האם לדלג על חגים בלוח הלימוד.
        alarm_time (datetime.time | None, optional): שעת התראה לאירוע. אם ``None`` לא תוגדר התראה.
        link_template (str, optional):
            תבנית קישור בה יוחלף ``{ref}`` בהפניה המדויקת בספריא.
            ברירת המחדל היא ``DEFAULT_LESSON_LINK``.

    Returns:
        str or None: הנתיב המלא לקובץ ה-ICS שנוצר, או None אם אירעה שגיאה.
    """
    schedule = _generate_study_schedule(
        start_date,
        end_date,
        titles_list,
        mode,
        tree_data,
        no_study_weekdays_set,
        units_per_day,
        skip_holidays,
    )

    if not schedule:
        print("אזהרה: לא נוצר לוח לימודים.")
        return None

    actual_end_date = schedule[-1]["date"] if units_per_day else end_date
    cal = Calendar() # יצירת אובייקט לוח שנה

    # קביעת שם בסיסי לאירוע
    first_title = titles_list[0].split(' / ')[-1] if titles_list else "לימוד"
    event_base_name = f"סדר לימוד: {first_title}"
    if len(titles_list) > 1:
        event_base_name += " ועוד"
    # יצירת אירועים בלוח השנה
    for day_data in schedule:
        ref = build_sefaria_ref(day_data["first_unit"], day_data["last_unit"], mode)
        links = []
        if ref:
            if isinstance(ref, list):
                links = [link_template.format(ref=quote(r, safe='.-_%')) for r in ref]
            else:
                links = [link_template.format(ref=quote(ref, safe='.-_%'))]
        e = Event()
        e.name = event_base_name
        e.begin = day_data['date'].strftime('%Y-%m-%d')
        e.make_all_day()
        if alarm_time:
            alarm_dt = datetime.combine(day_data['date'], alarm_time)
            e.alarms = [DisplayAlarm(trigger=alarm_dt)]
        if links:
            e.description = day_data['description'] + "\n" + "\n".join(links)
            e.url = links[0]
        else:
            e.description = day_data['description']
        cal.events.add(e)

    # יצירת שם קובץ חכם
    filename = generate_smart_filename(titles_list, mode, start_date, actual_end_date, tree_data, "ics", units_per_day)
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    # כתיבת הקובץ
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(cal)
        print(f"קובץ ICS נוצר בהצלחה: {full_path}")
        return full_path
    except Exception as e:
        print(f"שגיאה בכתיבת קובץ ICS: {e}")
        return None

def write_bookmark_html(
    titles_list,
    mode,
    start_date,
    end_date,
    tree_data,
    no_study_weekdays_set,
    units_per_day=None,
    skip_holidays=False,
    link_template: str = DEFAULT_LESSON_LINK,
):
    """
    יוצר קובץ HTML (דף סימנייה) המציג את לוח הלימודים בצורה חודשית.

    Args:
        titles_list (list[str]): רשימת הנתיבים של הפריטים הנלמדים.
        mode (str): סוג הלימוד.
        start_date (date): תאריך התחלת הלימוד.
        end_date (date): תאריך סיום הלימוד (במצב חלוקה לפי טווח).
        tree_data (dict): עץ הנתונים המלא.
        no_study_weekdays_set (set[int]): קבוצת ימי חופשה שבועיים.
        units_per_day (int, optional): הספק יומי (אם רלוונטי).
        skip_holidays (bool, optional): האם לדלג על חגים בלוח הלימוד.
        link_template (str, optional):
            תבנית קישור בה יוחלף ``{ref}`` בהפניה המדויקת בספריא.
            ברירת המחדל היא ``DEFAULT_LESSON_LINK``.

    Returns:
        str or None: הנתיב המלא לקובץ ה-HTML שנוצר, או None אם אירעה שגיאה.
    """
    schedule = _generate_study_schedule(start_date, end_date, titles_list, mode, tree_data, no_study_weekdays_set, units_per_day, skip_holidays)

    if not schedule:
        print("אזהרה: לא נוצר לוח לימודים.")
        return None

    actual_end_date = schedule[-1]["date"] if units_per_day else end_date
    # מיפוי תאריכים לתיאורי הלימוד והקישורים שלהם
    study_map = {}
    for item in schedule:
        orig_ref = build_sefaria_ref(item["first_unit"], item["last_unit"], mode)
        orig_link = ""
        if orig_ref:
            if isinstance(orig_ref, list):
                orig_link = link_template.format(ref=quote(orig_ref[0], safe='.-_%'))
            else:
                orig_link = link_template.format(ref=quote(orig_ref, safe='.-_%'))

        unit_links = []
        for unit in item.get("units", []):
            ref = build_sefaria_ref(unit, unit, mode)
            if ref:
                if isinstance(ref, list):
                    unit_links.extend(
                        [link_template.format(ref=quote(r, safe='.-_%')) for r in ref]
                    )
                else:
                    unit_links.append(link_template.format(ref=quote(ref, safe='.-_%')))

        study_map[item["date"]] = {
            "desc": item["description"],
            "links": unit_links,
            "orig_link": orig_link,
        }

    # אוספים את כל הימים בטווח, וממפים אותם לשנה וחודש עברי
    day_map = defaultdict(list)
    cur = start_date
    while cur <= actual_end_date:
        g_date = dates.GregorianDate(cur.year, cur.month, cur.day)
        # המרה לתאריך עברי
        h_date = g_date.to_heb()
        key = (h_date.year, h_date.month)
        day_map[key].append(cur)
        cur += timedelta(days=1)

    # סדר עברי של חודשים
    HEB_MONTH_ORDER = {7: 1, 8: 2, 9: 3, 10: 4, 11: 5, 12: 6, 13: 7, 1: 8, 2: 9, 3: 10, 4: 11, 5: 12, 6: 13}
    sorted_keys = sorted(day_map.keys(), key=lambda x: (x[0], HEB_MONTH_ORDER.get(x[1], x[1])))


    monthly_schedule = []
    for (h_year, h_month) in sorted_keys:
        month_name_he = hebrewcal.Month(h_year, h_month).month_name(True)
        year_str = dates.HebrewDate(h_year, h_month, 1).hebrew_date_string(True).split()[-1]
        month_data = {"month_name": f"{month_name_he} {year_str}", "weeks": []}
        days = sorted(day_map[(h_year, h_month)])
        # בניית מבנה שבועות עבור כל חודש
        if days:
            first_day = days[0]
            days_from_sunday = (first_day.weekday() + 1) % 7
            week_start = first_day - timedelta(days=days_from_sunday)
            last_day = days[-1]
            days_to_saturday = (5 - last_day.weekday()) % 7
            schedule_end_date = last_day + timedelta(days=days_to_saturday)
            current_week_start = week_start
            while current_week_start <= schedule_end_date:
                # לולאה על כל שבוע בחודש
                week = []
                for i in range(7):
                    current_day = current_week_start + timedelta(days=i)
                    g_date = dates.GregorianDate(current_day.year, current_day.month, current_day.day)
                    h_d = g_date.to_heb()
                    is_in_month = (h_d.year == h_year and h_d.month == h_month)
                    hebrew_day_number = h_d.hebrew_day() if is_in_month else ""
                    hebrew_date = h_d.hebrew_date_string(True) if is_in_month else ""

                    # איסוף חגים רגילים וחגים לאומיים
                    holiday_parts = []
                    if is_in_month:
                        regular_holiday = h_d.holiday(hebrew=True, israel=True)
                        if regular_holiday:
                            holiday_parts.append(regular_holiday)
                        # קריאה נכונה לפונקציה עם שני הארגומנטים הנדרשים
                        national_holiday = get_israeli_national_holiday_on_gregorian_date(current_day, h_year)
                        if national_holiday:
                            holiday_parts.append(national_holiday)
                    holiday = ", ".join(holiday_parts) if holiday_parts else ""

                    parsha = parshios.getparsha_string(g_date, hebrew=True, israel=True) if current_day.weekday() == 5 and is_in_month else None
                    label = holiday or parsha or ""
                    study_info = study_map.get(current_day)
                    week.append({
                        "is_in_month": is_in_month,
                        "hebrew_date": hebrew_date,
                        "hebrew_day_number": hebrew_day_number,
                        "label": label,
                        "study_portion": study_info["desc"] if is_in_month and study_info else "",
                        "links": study_info["links"] if is_in_month and study_info else [],
                        "orig_link": study_info["orig_link"] if is_in_month and study_info else "",
                        "is_shabbat": current_day.weekday() == 5 if is_in_month else False,
                        "is_holiday": bool(holiday) if is_in_month else False
                    })
                month_data["weeks"].append(week)
                current_week_start += timedelta(weeks=1)
        monthly_schedule.append(month_data)

    # טעינת תבנית HTML ורינדור
    env = Environment(loader=FileSystemLoader(os.getcwd()))
    tpl = env.get_template('bookmark_template.html')
    filename = generate_smart_filename(titles_list, mode, start_date, actual_end_date, tree_data, "html", units_per_day)
    html = tpl.render(
        title=filename.replace('.html', ''),
        date_range=f"{start_date:%d/%m/%Y} - {actual_end_date:%d/%m/%Y}",
        monthly_schedule=monthly_schedule,
        heb_weekday_names=HEBREW_WEEKDAY_NAMES # הוספת שמות ימות השבוע לתבנית
    )
    # שמירת קובץ ה-HTML
    out = os.path.join(os.getcwd(), filename)
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
        no_study_weekdays_set=example_no_study_days,
        skip_holidays=False
    )
    print("-" * 20)
    write_bookmark_html(
        titles_list=titles_to_study,
        mode=study_mode,
        start_date=start,
        end_date=end,
        tree_data=tree_data,
        no_study_weekdays_set=example_no_study_days,
        skip_holidays=False
    )
