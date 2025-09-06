"""Export study schedules to ICS, HTML and PDF."""

from datetime import datetime, time
import os
from urllib.parse import quote
from collections import defaultdict

from ics import Calendar, Event, DisplayAlarm
from jinja2 import Environment, FileSystemLoader

from hspek.utils import resource_path
from .tree import (
    detect_content_category,
    build_sefaria_ref,
    generate_smart_filename,
    _generate_study_schedule,
    HEBREW_WEEKDAY_NAMES,
)

DEFAULT_LESSON_LINK = "https://www.sefaria.org.il/he/{ref}"


def write_ics_file(
    titles_list,
    mode,
    start_date,
    end_date,
    tree_data,
    no_study_weekdays_set,
    units_per_day=None,
    skip_holidays=False,
    link_template: str = DEFAULT_LESSON_LINK,
    alarm_time: time | None = None,
    balance_chapters_by_mishnayot: bool = False,
):
    """Create an ICS calendar file for the study schedule."""
    schedule = _generate_study_schedule(
        start_date,
        end_date,
        titles_list,
        mode,
        tree_data,
        no_study_weekdays_set,
        units_per_day,
        skip_holidays,
        balance_chapters_by_mishnayot,
    )
    if not schedule:
        print("אזהרה: לא נוצר לוח לימודים.")
        return None
    actual_end_date = schedule[-1]["date"] if units_per_day else end_date
    cal = Calendar()
    first_title = titles_list[0].split(" / ")[-1] if titles_list else "לימוד"
    event_base_name = f"סדר לימוד: {first_title}"
    if len(titles_list) > 1:
        event_base_name += " ועוד"
    for day_data in schedule:
        ref = build_sefaria_ref(day_data["first_unit"], day_data["last_unit"], mode)
        links = []
        if ref:
            if isinstance(ref, list):
                links = [link_template.format(ref=quote(r, safe=".-_%")) for r in ref]
            else:
                links = [link_template.format(ref=quote(ref, safe=".-_%"))]
        e = Event()
        e.name = event_base_name
        e.begin = day_data["date"].strftime("%Y-%m-%d")
        e.make_all_day()
        if alarm_time:
            alarm_dt = datetime.combine(day_data["date"], alarm_time)
            e.alarms = [DisplayAlarm(trigger=alarm_dt)]
        if links:
            e.description = day_data["description"] + "\n" + "\n".join(links)
            e.url = links[0]
        else:
            e.description = day_data["description"]
        cal.events.add(e)
    filename = generate_smart_filename(
        titles_list, mode, start_date, actual_end_date, tree_data, "ics", units_per_day
    )
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    try:
        with open(resource_path(full_path), "w", encoding="utf-8") as f:
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
    balance_chapters_by_mishnayot: bool = False,
    pdf_mode: bool = False,
):
    """Create an HTML bookmark page for the study schedule."""
    schedule = _generate_study_schedule(
        start_date,
        end_date,
        titles_list,
        mode,
        tree_data,
        no_study_weekdays_set,
        units_per_day,
        skip_holidays,
        balance_chapters_by_mishnayot,
    )
    if not schedule:
        print("אזהרה: לא נוצר לוח לימודים.")
        return None
    actual_end_date = schedule[-1]["date"] if units_per_day else end_date
    study_map = {}
    for item in schedule:
        orig_ref = build_sefaria_ref(item["first_unit"], item["last_unit"], mode)
        orig_link = ""
        if orig_ref:
            if isinstance(orig_ref, list):
                orig_link = link_template.format(ref=quote(orig_ref[0], safe=".-_%"))
            else:
                orig_link = link_template.format(ref=quote(orig_ref, safe=".-_%"))
        unit_links = []
        for unit in item.get("units", []):
            ref = build_sefaria_ref(unit, unit, mode)
            if ref:
                if isinstance(ref, list):
                    unit_links.extend([link_template.format(ref=quote(r, safe=".-_%")) for r in ref])
                else:
                    unit_links.append(link_template.format(ref=quote(ref, safe=".-_%")))
        study_map[item["date"]] = {
            "desc": item["description"],
            "links": unit_links,
            "orig_link": orig_link,
            "category": detect_content_category(item["first_unit"]),
        }
    day_map = defaultdict(list)
    cur = start_date
    while cur <= actual_end_date:
        g_date = dates.GregorianDate(cur.year, cur.month, cur.day)
        h_date = g_date.to_heb()
        key = (h_date.year, h_date.month)
        day_map[key].append(cur)
        cur += timedelta(days=1)
    HEB_MONTH_ORDER = {7:1,8:2,9:3,10:4,11:5,12:6,13:7,1:8,2:9,3:10,4:11,5:12,6:13}
    sorted_keys = sorted(day_map.keys(), key=lambda x: (x[0], HEB_MONTH_ORDER.get(x[1], x[1])))
    monthly_schedule = []
    for h_year, h_month in sorted_keys:
        month_name_he = hebrewcal.Month(h_year, h_month).month_name(True)
        year_str = dates.HebrewDate(h_year, h_month, 1).hebrew_date_string(True).split()[-1]
        month_data = {"month_name": f"{month_name_he} {year_str}", "weeks": []}
        days = sorted(day_map[(h_year, h_month)])
        if days:
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
                    is_in_month = h_d.year == h_year and h_d.month == h_month
                    hebrew_day_number = h_d.hebrew_day() if is_in_month else ""
                    hebrew_date = h_d.hebrew_date_string(True) if is_in_month else ""
                    holiday_parts = []
                    if is_in_month:
                        regular_holiday = h_d.holiday(hebrew=True, israel=True)
                        if regular_holiday:
                            holiday_parts.append(regular_holiday)
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
                        "study_portion": (study_info["desc"] if is_in_month and study_info else ""),
                        "links": (study_info["links"] if is_in_month and study_info else []),
                        "orig_link": (study_info["orig_link"] if is_in_month and study_info else ""),
                        "category": (study_info["category"] if is_in_month and study_info else ""),
                        "is_shabbat": (current_day.weekday() == 5 if is_in_month else False),
                        "is_holiday": bool(holiday) if is_in_month else False,
                    })
                month_data["weeks"].append(week)
                current_week_start += timedelta(weeks=1)
        monthly_schedule.append(month_data)
    env = Environment(loader=FileSystemLoader(os.getcwd()))
    template_name = "bookmark_template_pdf.html" if pdf_mode else "bookmark_template.html"
    tpl = env.get_template(template_name)
    filename = generate_smart_filename(
        titles_list, mode, start_date, actual_end_date, tree_data, "html", units_per_day
    )
    html = tpl.render(
        title=filename.replace(".html", ""),
        date_range=f"{start_date:%d/%m/%Y} - {actual_end_date:%d/%m/%Y}",
        monthly_schedule=monthly_schedule,
        heb_weekday_names=HEBREW_WEEKDAY_NAMES,
    )
    out = os.path.join(os.getcwd(), filename)
    with open(resource_path(out), "w", encoding="utf-8") as f:
        f.write(html)
    return out


def write_bookmark_pdf(
    titles_list,
    mode,
    start_date,
    end_date,
    tree_data,
    no_study_weekdays_set,
    units_per_day=None,
    skip_holidays=False,
    link_template: str = DEFAULT_LESSON_LINK,
    balance_chapters_by_mishnayot: bool = False,
):
    """Create a PDF bookmark file from the study schedule using ``pyppeteer``."""
    html_path = write_bookmark_html(
        titles_list,
        mode,
        start_date,
        end_date,
        tree_data,
        no_study_weekdays_set,
        units_per_day=units_per_day,
        skip_holidays=skip_holidays,
        link_template=link_template,
        balance_chapters_by_mishnayot=balance_chapters_by_mishnayot,
        pdf_mode=True,
    )
    if not html_path:
        return None
    pdf_path = html_path.replace(".html", ".pdf")

    async def _convert():
        import shutil
        from pyppeteer import launch

        os.environ.setdefault("PYPPETEER_SKIP_CHROMIUM_DOWNLOAD", "1")
        exe_path = (
            os.environ.get("CHROME_PATH")
            or shutil.which("chromium-browser")
            or shutil.which("google-chrome")
            or shutil.which("chromium")
            or shutil.which("chrome")
            or "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        )
        if not exe_path or not os.path.exists(exe_path):
            raise RuntimeError(f"Chrome/Chromium not found at: {exe_path}")
        browser = await launch(executablePath=exe_path, headless=True, args=["--no-sandbox"])
        page = await browser.newPage()
        await page.goto(f"file://{html_path}")
        await page.pdf({"path": pdf_path, "printBackground": True})
        await browser.close()

    try:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_convert())
        return pdf_path
    except Exception as e:
        print(f"שגיאה ביצירת קובץ PDF: {e}")
        return None
