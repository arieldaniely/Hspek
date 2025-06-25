# ==============================================================================
#                                 ייבוא ספריות
# ==============================================================================
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import tkinter as tk
from tkcalendar import DateEntry
from datetime import date, timedelta, datetime
import math
import locale
import os

# ייבוא פונקציות לוגיות מהמודול הנפרד
from torah_logic_full_updated import (
    load_data, get_length_from_node, has_relevant_data_recursive,
    calculate_study_days, write_ics_file,
    write_bookmark_html, is_holiday
)

# ==============================================================================
#                                הגדרות גלובליות
# ==============================================================================
try:
    locale.setlocale(locale.LC_ALL, 'he_IL.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'he_IL')
    except locale.Error:
        pass # אם גם זה נכשל, נמשיך עם הגדרות ברירת המחדל

ctk.set_appearance_mode("system")  # הגדרת ערכת נושא בהתאם למערכת
ctk.set_default_color_theme("blue") # הגדרת צבע ברירת מחדל

DEFAULT_FILE = "torah_tree_data_full.json" # קובץ נתונים ברירת מחדל

# ==============================================================================
#                                 מחלקת האפליקציה הראשית
# ==============================================================================
class TorahTreeApp(ctk.CTk):
    """
    המחלקה הראשית של אפליקציית עץ התורה, המנהלת את ממשק המשתמש והלוגיקה.
    """
    def __init__(self):
        """
        אתחול האפליקציה, הגדרת משתנים ובניית ממשק המשתמש.
        """
        super().__init__() # קריאה לבנאי של המחלקה האב (ctk.CTk)
        self.title("מניין לימוד | חישוב הספק יומי") # הגדרת כותרת החלון
        self.minsize(780, 480) # הגדרת גודל מינימלי לחלון

        # ==================== משתני מצב ו-GUI ====================
        # משתנה לשמירת סוג הספירה הנבחר (פרקים, משניות וכו')
        self.mode = ctk.StringVar(value="פרקים")
        # משתנים לשמירת תאריכי התחלה וסיום
        self.start_date_var = ctk.StringVar(value=date.today().strftime('%Y-%m-%d'))
        self.end_date_var = ctk.StringVar(value=(date.today() + timedelta(days=30)).strftime('%Y-%m-%d'))
        # משתנה לשמירת מספר יחידות הלימוד ביום (במצב הספק יומי)
        self.units_per_day_var = tk.IntVar(value=1)
        # מעקב אחר שינויים בשדה ההספק היומי לעדכון אוטומטי של התצוגה
        self.units_per_day_var.trace_add("write", lambda *args: self.calculate_and_display_daily_progress())
        # משתנה לבחירת מצב הלוח: 0 = חלוקה לפי טווח תאריכים, 1 = לפי הספק יומי קבוע
        self.schedule_mode_var = tk.IntVar(value=0)  # 0 = עד תאריך, 1 = הספק יומי

        # הגדרות לוח שנה
        self.alarm_time_var = ctk.StringVar(value="08:00")
        self.skip_holidays_var = ctk.BooleanVar(value=False)
        # האם לעגל חצאים במספר הדפים כלפי מעלה
        self.round_up_halves_var = ctk.BooleanVar(value=False)
        self.settings_window = None

        days_of_week = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
        self.no_study_days = {day: ctk.BooleanVar(value=(day=="שבת")) for day in days_of_week}
        self.weekday_map = {
            "ראשון": 6, "שני": 0, "שלישי": 1, "רביעי": 2,
            "חמישי": 3, "שישי": 4, "שבת": 5  # Sunday is 6 in Python's weekday()
        }

        self.data = {} # מילון שיחזיק את נתוני הלימוד הנטענים מהקובץ
        self.node_map = {} # מיפוי בין ID של פריט בעץ לנתונים המקוריים שלו
        self.radio_buttons = {} # מילון לאחסון כפתורי הרדיו של סוג הספירה
        self.current_total_content = 0 # משתנה לשמירת האורך הכולל של הפריטים שנבחרו

        self._setup_initial_geometry() # הגדרת גודל חלון ראשוני

        # בניית כל רכיבי הממשק הגרפי
        self.build_gui()

        # טעינת קובץ נתונים ברירת מחדל אם קיים
        if os.path.exists(DEFAULT_FILE):
            self.load_and_build(DEFAULT_FILE)
        else:
            self.disable_all_radio_buttons()
            # הודעה למשתמש אם קובץ הנתונים לא נמצא
            self.tree.insert("", "end", text="לטעינת קובץ נתונים יש ללחוץ על הכפתור למעלה", open=True)

    # ==================== בניית ממשק משתמש ====================
    def build_gui(self):
        """
        בניית כל רכיבי ממשק המשתמש (GUI) של האפליקציה.
        """
        # מסגרת עליונה (Top Frame) - לכפתור טעינת קובץ וכותרת
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=8, pady=(7,3))
        ctk.CTkButton(top_frame, text="נתונים קובץ טען...", command=self.choose_file, width=140).pack(side="right", padx=(0,10))
        ctk.CTkLabel(top_frame, text=r"תאריכים \ סעיף \ קובץ - לימוד מניין", font=ctk.CTkFont(size=19, weight="bold")).pack(side="left", padx=(10,0))

        # MAIN FRAME
        main_frame = ctk.CTkFrame(self, fg_color="#f8fafc")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # מסגרת עץ התצוגה (Tree Frame)
        tree_frame = ctk.CTkFrame(main_frame, fg_color="#e6f0fa", corner_radius=15)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0,18), pady=3)
        tree_frame.grid_rowconfigure(1, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # שדה חיפוש לעץ
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(tree_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 0))
        self.search_entry.bind("<KeyRelease>", self.filter_tree)

        style = ttk.Style(self)
        style.configure("Treeview", font=("Arial", 18), rowheight=30) # הגדלת הפונט והרווח בין השורות
        # יצירת רכיב עץ התצוגה

        self.tree = ttk.Treeview(tree_frame, selectmode="extended", show="tree", height=20) # הגדלת גובה ברירת מחדל
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(4,0), pady=6)
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll_y.grid(row=1, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        scroll_x.grid(row=2, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # לוח בקרה (Control Panel) - מימין לעץ
        ctrl_frame = ctk.CTkFrame(main_frame, fg_color="#f0f8ff", corner_radius=18)
        ctrl_frame.grid(row=0, column=1, sticky="nsew", padx=(0,2), pady=5)
        ctrl_frame.grid_columnconfigure(0, weight=1)

        # קבוצת כפתורי רדיו לבחירת סוג הספירה
        mode_group = ctk.CTkFrame(ctrl_frame, fg_color="#d9e9f6", corner_radius=12)
        ctk.CTkLabel(mode_group, text="לפי סכם", font=ctk.CTkFont(weight="bold")).pack(anchor="ne", padx=8, pady=(4, 0))
        mode_group.grid(row=0, column=0, sticky="ew", pady=7, padx=12)
        for opt in ("פרקים", "משניות", "דפים", "עמודים"):
            rb = ctk.CTkRadioButton(mode_group, text=opt, variable=self.mode, value=opt, command=self.update_sum_and_daily_progress)
            rb.pack(anchor="w", pady=(3,3), padx=10)
            self.radio_buttons[opt] = rb

        # תוויות להצגת האורך הכולל וההספק היומי
        self.sum_label = ctk.CTkLabel(ctrl_frame, text="הכולל האורך: 0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#2b539b")
        self.sum_label.grid(row=1, column=0, sticky="ew", pady=(8,4), padx=10)
        self.daily_progress_label = ctk.CTkLabel(ctrl_frame, text="יומי הספק: N/A", font=ctk.CTkFont(size=13), text_color="#803b99")
        self.daily_progress_label.grid(row=2, column=0, sticky="ew", pady=(0,9), padx=10)
        # מסגרת לבחירת סוג הלוח (לפי טווח תאריכים או הספק יומי)

        schedule_frame = ctk.CTkFrame(ctrl_frame, fg_color="#d9e9f6", corner_radius=12)
        ctk.CTkLabel(schedule_frame, text="בחירת סוג לוח:", font=ctk.CTkFont(weight="bold")).pack(anchor="ne", padx=8, pady=(4, 0))
        schedule_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0,8))

        # רדיו - מצב לוח
        ctk.CTkRadioButton(schedule_frame, text="סיום עד תאריך", variable=self.schedule_mode_var, value=0, command=self.toggle_schedule_mode).pack(anchor="w", pady=(3,3), padx=10)
        ctk.CTkRadioButton(schedule_frame, text="הספק יומי קבוע", variable=self.schedule_mode_var, value=1, command=self.toggle_schedule_mode).pack(anchor="w", pady=(3,3), padx=10)

        # מעקב אחר שינויים בשדות התאריכים לחישוב אוטומטי של ההספק
        self.start_date_var.trace_add("write", lambda *args: self.calculate_and_display_daily_progress())
        self.end_date_var.trace_add("write", lambda *args: self.calculate_and_display_daily_progress())

        # ---- שדות קלט לתאריכים והספק יומי ----

        # תאריך התחלה
        self.start_date_label = ttk.Label(schedule_frame, text="תאריך התחלה:", font=("Arial", 15))
        self.start_date_label.pack(anchor="w", padx=10, pady=(5,0))

        self.start_date_entry = DateEntry(
            schedule_frame,
            textvariable=self.start_date_var,
            width=14,
            date_pattern="yyyy-mm-dd",
            locale='he_IL',
            font=("Arial", 14)
        )
        self.start_date_entry.pack(fill="x", padx=10, pady=(0,5))

        # תאריך סיום
        self.end_date_label = ttk.Label(schedule_frame, text="תאריך סיום:", font=("Arial", 15))
        self.end_date_label.pack(anchor="w", padx=10, pady=(5,0))

        self.end_date_entry = DateEntry(
            schedule_frame,
            textvariable=self.end_date_var,
            width=14,
            date_pattern="yyyy-mm-dd",
            locale='he_IL',
            font=("Arial", 14)
        )
        self.end_date_entry.pack(fill="x", padx=10, pady=(0,5))

        # הספק יומי (יופיע רק במצב הספק יומי)
        self.units_per_day_label = ttk.Label(schedule_frame, text="הספק יומי (יחידות):", font=("Arial", 15))
        self.units_per_day_label.pack(anchor="w", padx=10, pady=(5,0))

        self.units_per_day_entry = ctk.CTkEntry(
            schedule_frame,
            textvariable=self.units_per_day_var,
            width=150,
            font=ctk.CTkFont(size=14)
        )
        self.units_per_day_entry.pack(fill="x", padx=10, pady=(0,5))

        # מסגרת לבחירת ימי חופשה שבועיים
        no_study_frame = ctk.CTkFrame(ctrl_frame, fg_color="#d9e9f6", corner_radius=12)
        ctk.CTkLabel(no_study_frame, text="חופשה ימי", font=ctk.CTkFont(size=13, weight="bold"), anchor="e", justify="right").grid(row=0, column=0, columnspan=4, sticky="e", padx=12, pady=(4, 0))
        days = list(self.no_study_days.keys())
        for i, day in enumerate(days):
            cb = ctk.CTkCheckBox(no_study_frame, text=day, variable=self.no_study_days[day], command=self.calculate_and_display_daily_progress)
            cb.grid(row=(i // 4) + 1, column=i % 4, sticky="w", padx=5, pady=(2,3))
        no_study_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 7))

        # מסגרת לכפתורי הייצוא (ICS ו-HTML)
        button_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        button_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 12))
        button_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(button_frame, text="לקובץ ייצוא ICS", fg_color="#218cfa", hover_color="#186bb7", text_color="white", command=self.export_ics, height=38).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(button_frame, text="HTML צור סימנייה", fg_color="#a6d785", hover_color="#7aa557", text_color="black", command=self.export_html, height=38).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # לחצן קטן לפתיחת תפריט ההגדרות הצדדי
        ctk.CTkButton(
            button_frame,
            text="⚙ הגדרות מיוחדות",
            width=28,
            height=28,
            fg_color="white",
            text_color="black",
            command=self.toggle_settings_panel,
            border_width=0.6,      # הוספה: עובי מסגרת
            border_color="black"
        ).grid(row=1, column=0, columnspan=2, sticky="e", pady=(6, 0))
        # קישור אירוע בחירה בעץ לפונקציה המתאימה

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # הגדרה ראשונית - להציג נכונה את השדות
        self.toggle_schedule_mode()

    # ==================== פונקציות עזר וניהול מצב ====================
    def _setup_initial_geometry(self):
        """
        מגדיר את הגאומטריה הראשונית של החלון הראשי.
        מנסה למרכז את החלון על המסך.
        """
        window_width = 940
        window_height = 590
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)
        self.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

    def toggle_schedule_mode(self):
        """
        מנהל את התצוגה של שדות הקלט בהתאם למצב הלוח שנבחר:
        - "סיום עד תאריך": מציג את שדה תאריך הסיום ומסתיר את שדה ההספק היומי.
        - "הספק יומי קבוע": מסתיר את שדה תאריך הסיום ומציג את שדה ההספק היומי.
        בכל שינוי, קורא לפונקציה לעדכון תווית ההספק/סיום.
        """
        mode = self.schedule_mode_var.get()
        if mode == 0:  # עד תאריך
            # תאריך סיום מוצג, הספק מוסתר
            self.end_date_label.pack(anchor="w", padx=10, pady=(5,0))
            self.end_date_entry.pack(fill="x", padx=10, pady=(0,5))
            self.units_per_day_label.pack_forget()
            self.units_per_day_entry.pack_forget()
        else:  # הספק יומי קבוע
            # תאריך סיום מוסתר, הספק מוצג
            self.end_date_label.pack_forget()
            self.end_date_entry.pack_forget()
            self.units_per_day_label.pack(anchor="w", padx=10, pady=(5,0))
            self.units_per_day_entry.pack(fill="x", padx=10, pady=(0,5))
        self.calculate_and_display_daily_progress() # עדכון התווית בעת שינוי מצב

    def toggle_settings_panel(self):
        """מציג או מסתיר חלון צד להגדרות מיוחדות."""
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
            self.settings_window = None
            return

        self.settings_window = ctk.CTkFrame(self, fg_color="white", width=800)
        self.settings_window.place(relx=1.0, y=0, relheight=1.0, anchor="ne")

        # כפתור סגירה עגול בפינת החלון
        ctk.CTkButton(
            self.settings_window,
            text="✕",
            width=24,
            height=24,
            corner_radius=12,
            command=self.toggle_settings_panel,
            fg_color="#e0e0e0",
            text_color="black"
        ).place(x=6, y=6)

        ctk.CTkLabel(self.settings_window, text="שעת התראה (HH:MM):").pack(pady=(40,0))
        ctk.CTkEntry(self.settings_window, textvariable=self.alarm_time_var).pack(fill="x", padx=10, pady=6)

        ctk.CTkCheckBox(
            self.settings_window,
            text="דלג על חגים",
            variable=self.skip_holidays_var
        ).pack(anchor="w", padx=10, pady=(0,6))

        ctk.CTkCheckBox(
            self.settings_window,
            text="עגל חצאי דפים למעלה",
            variable=self.round_up_halves_var
        ).pack(anchor="w", padx=10, pady=(0,6))

    def choose_file(self):
        """
        פותח דיאלוג לבחירת קובץ JSON ומפעיל את טעינת הנתונים.
        """
        path = filedialog.askopenfilename(title="בחר קובץ JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            self.load_and_build(path)

    def load_and_build(self, path):
        """
        טוען נתונים מקובץ JSON נתון, בונה את עץ התצוגה ומעדכן את ממשק המשתמש.
        """
        self.data = load_data(path)
        if self.data: # אם הטעינה הצליחה והקובץ אינו ריק
            # ניקוי העץ הקיים והמפה
            self.tree.delete(*self.tree.get_children())
            self.node_map.clear()
            # בניית העץ מחדש
            self._build_full_tree_recursive("", self.data)
            self.update_sum_and_daily_progress() # עדכון ראשוני
            if self.tree.get_children(): # אם יש פריטים בעץ לאחר הבנייה
                first_item = self.tree.get_children()[0]
                self.tree.selection_set(first_item) # בחירת הפריט הראשון
                self.tree.focus(first_item) # מיקוד על הפריט הראשון
        else:
            self.tree.delete(*self.tree.get_children())
            self.disable_all_radio_buttons()
            self.sum_label.configure(text="האורך הכולל: 0")
            self.daily_progress_label.configure(text="הספק יומי: N/A")
            self.tree.insert("", "end", text="טעינת הקובץ נכשלה או שהקובץ ריק.", open=True)

    def _build_full_tree_recursive(self, parent_iid, node_data):
        """
        פונקציית עזר רקורסיבית לבניית עץ התצוגה מנתוני ה-JSON.

        Args:
            parent_iid (str): ה-ID של צומת האב בעץ התצוגה.
                              עבור השורש, זהו מחרוזת ריקה.
            node_data (dict or any): הנתונים של הצומת הנוכחי (בדרך כלל מילון).
                                     אם אינו מילון, הרקורסיה נעצרת עבור ענף זה.
        """
        if not isinstance(node_data, dict): return
        for key, val in node_data.items():
            # אל תוסיף לעץ את מפתחות הנתונים עצמם (אורך, משניות וכו')
            if key in ["אורך בדפים", "עמוד אחרון", "משניות", "פרקים"] and not isinstance(val, dict):
                continue
            iid = self.tree.insert(parent_iid, "end", text=key, open=False) # פריטים סגורים כברירת מחדל
            self.node_map[iid] = val # שמירת הנתונים המקוריים של הצומת
            if isinstance(val, dict):
                self._build_full_tree_recursive(iid, val)

    def _node_matches_query(self, node_data, query):
        """בודק אם צומת כלשהו בעץ מכיל את מחרוזת החיפוש."""
        if not isinstance(node_data, dict):
            return False
        for k, v in node_data.items():
            if k in ["אורך בדפים", "עמוד אחרון", "משניות", "פרקים"] and not isinstance(v, dict):
                continue
            if query in k:
                return True
            if isinstance(v, dict) and self._node_matches_query(v, query):
                return True
        return False

    def _build_filtered_tree_recursive(self, parent_iid, node_data, query):
        """בונה את העץ בהתאם למחרוזת חיפוש."""
        if not isinstance(node_data, dict):
            return
        for key, val in node_data.items():
            if key in ["אורך בדפים", "עמוד אחרון", "משניות", "פרקים"] and not isinstance(val, dict):
                continue
            if query in key or self._node_matches_query(val, query):
                iid = self.tree.insert(parent_iid, "end", text=key, open=True)
                self.node_map[iid] = val
                if isinstance(val, dict):
                    self._build_filtered_tree_recursive(iid, val, query)

    def filter_tree(self, event=None):
        """סינון פריטי העץ בהתאם לטקסט החיפוש."""
        query = self.search_var.get().strip()
        self.tree.delete(*self.tree.get_children())
        self.node_map.clear()
        if not query:
            self._build_full_tree_recursive("", self.data)
        else:
            self._build_filtered_tree_recursive("", self.data, query)
        self.update_sum_and_daily_progress()

    def disable_all_radio_buttons(self):
        """
        משבית את כל כפתורי הרדיו לבחירת סוג הספירה.
        """
        for opt in self.radio_buttons:
            self.radio_buttons[opt].configure(state="disabled")

    # ==================== טיפול באירועים ועדכונים ====================
    def on_tree_select(self, event):
        """
        מטפל באירוע בחירת פריט/ים בעץ התצוגה. מעדכן את כפתורי הרדיו ואת סיכום התוכן.
        """
        selected_items = self.tree.selection()
        if not selected_items: # אם אין פריטים נבחרים
            self.disable_all_radio_buttons()
            self.current_total_content = 0
            self.sum_label.configure(text="האורך הכולל: 0")
            self.daily_progress_label.configure(text="הספק יומי: N/A")
            return

        # בדוק אילו סוגי ספירה רלוונטיים לבחירה הנוכחית
        relevant_modes_for_selection = set()
        for iid in selected_items:
            if iid in self.node_map:
                node_data = self.node_map[iid] # קבל את הנתונים המקוריים של הצומת
                for mode_option in ["פרקים", "משניות", "דפים", "עמודים"]:
                    if has_relevant_data_recursive(node_data, mode_option):
                        relevant_modes_for_selection.add(mode_option)
        # עדכון מצב כפתורי הרדיו (הצגה/הסתרה, הפעלה/השבתה)
        current_mode_active = False
        new_default_mode = "" # למקרה שהמצב הנוכחי לא רלוונטי יותר
        for opt in ["פרקים", "משניות", "דפים", "עמודים"]: # סדר קבוע להצגה
            rb = self.radio_buttons[opt]
            if opt in relevant_modes_for_selection:
                rb.pack(anchor="w", pady=(3,3), padx=10) # הצג אם רלוונטי
                rb.configure(state="normal")
                if not new_default_mode: # שמור את האופציה הרלוונטית הראשונה
                    new_default_mode = opt
                if self.mode.get() == opt:
                    current_mode_active = True
            else:
                rb.pack_forget() # הסתר אם לא רלוונטי

        # אם המצב הנוכחי לא רלוונטי, בחר מצב ברירת מחדל חדש אם יש
        if not current_mode_active and relevant_modes_for_selection:
            self.mode.set(new_default_mode)
        elif not relevant_modes_for_selection: # אם אין שום מצב רלוונטי
            self.mode.set("") # נקה את המצב
            self.disable_all_radio_buttons() # השבת את כל הכפתורים
        self.update_sum_and_daily_progress() # עדכון סופי של הסכומים וההספקים

    def update_sum_and_daily_progress(self):
        """
        מעדכן את תווית סיכום האורך הכולל של הפריטים שנבחרו ואת תווית ההספק היומי.
        """
        mode = self.mode.get()
        total = 0
        selected_items = self.tree.selection()

        if not selected_items or not mode: # אם אין בחירה או אין מצב ספירה
            display_total = 0
        else:
            # חישוב האורך הכולל על סמך הפריטים הנבחרים ומצב הספירה
            for iid in selected_items:
                if iid in self.node_map:
                    node = self.node_map[iid]  # השתמש בנתונים המקוריים מהמפה
                    total += get_length_from_node(node, mode)
            display_total = math.ceil(total) if self.round_up_halves_var.get() else total

        self.current_total_content = display_total
        if display_total == int(display_total):
            display_total = int(display_total)
        self.sum_label.configure(text=f"האורך הכולל: {display_total}")
        
        self.calculate_and_display_daily_progress() # קריאה לחישוב והצגת ההספק/סיום

    def parse_date(self, date_str):
        """
        ממיר מחרוזת תאריך לאובייקט date.
        מחזיר None אם הפורמט אינו תקין.
        """
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    # ==================== פונקציות חישוב לוגיות ====================
    def _calculate_projected_end_date(self, start_date_obj, total_material, units_per_day_val, no_study_weekdays_set, skip_holidays=False):
        """
        מחשב את תאריך הסיום המשוער בהינתן תאריך התחלה, כמות חומר, הספק יומי וימי חופשה.

        Args:
            start_date_obj (date): אובייקט תאריך התחלה.
            total_material (int or float): כמות החומר הכוללת ללימוד.
            units_per_day_val (int or float): מספר יחידות לימוד ביום.
            no_study_weekdays_set (set[int]): קבוצת ימי חופשה שבועיים (0=שני, ..., 6=ראשון).
            skip_holidays (bool): האם לדלג על חגים בלוח הלימוד.

        Returns:
            date or None: אובייקט date של תאריך הסיום המשוער, או None אם החישוב נכשל (למשל, הספק 0, כל הימים חופש).
        """
        # בדיקות תקינות קלט
        if units_per_day_val <= 0:
            return None # הספק חייב להיות חיובי

        if total_material == 0: # אם אין חומר ללמוד
            return start_date_obj

        # חישוב מספר ימי הלימוד הנדרשים (עיגול כלפי מעלה)
        study_sessions_needed = math.ceil(total_material / units_per_day_val)

        current_date = start_date_obj
        sessions_counted = 0
        days_iterated = 0 # מונה בטיחות למניעת לולאות אינסופיות
        
        # בדיקה אם בכלל אפשר ללמוד (למקרה שכל ימות השבוע מוגדרים כחופש)
        can_study_at_all = any(i not in no_study_weekdays_set for i in range(7))
        if not can_study_at_all and total_material > 0:
            return None # לא ניתן להתקדם אם כל הימים הם ימי חופש

        while sessions_counted < study_sessions_needed:
            if current_date.weekday() not in no_study_weekdays_set:
                if not (skip_holidays and is_holiday(current_date)):
                    # אם היום הוא יום לימוד, קדם את מונה ימי הלימוד
                    sessions_counted += 1
            
            if sessions_counted == study_sessions_needed: # הגענו למספר ימי הלימוד הנדרש
                break
            
            current_date += timedelta(days=1)
            days_iterated += 1

            # מנגנון בטיחות למקרה של תוכנית ארוכה מאוד או בעיה בחישוב
            if days_iterated > 365 * 50: # מעל 50 שנה
                # במקרה כזה, החישוב כנראה נתקע או שהתוכנית ארוכה מדי
                return None 
        
        return current_date

    def calculate_and_display_daily_progress(self):
        """
        מחשב ומציג את ההספק היומי הנדרש או את תאריך הסיום המשוער, בהתאם למצב שנבחר.
        """
        mode = self.mode.get()
        # אם אין פריטים נבחרים או אין מצב ספירה, נקה את התווית
        if not self.tree.selection() or not mode:
            self.daily_progress_label.configure(text="הספק / סיום: N/A") # שינוי טקסט כללי
            return

        total_content = self.current_total_content
        start_d = self.parse_date(self.start_date_var.get())

        # אם תאריך ההתחלה לא תקין
        if not start_d:
            self.daily_progress_label.configure(text="הספק / סיום: (הכנס תאריך התחלה)")
            return

        # איסוף ימי החופשה מה-checkboxes
        no_study_weekdays = {
            self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
        }

        if self.schedule_mode_var.get() == 0:  # מצב "סיום עד תאריך" -> חישוב הספק יומי
            end_d = self.parse_date(self.end_date_var.get())
            if not end_d:
                # אם תאריך הסיום לא תקין
                self.daily_progress_label.configure(text="הספק יומי: (הכנס תאריך סיום)")
                return
            if start_d > end_d:
                # אם תאריך ההתחלה מאוחר מתאריך הסיום
                self.daily_progress_label.configure(text="הספק יומי: (תאריך התחלה מאוחר מהסיום)")
                return
            
            study_days_count = calculate_study_days(start_d, end_d, no_study_weekdays, self.skip_holidays_var.get())
            if study_days_count > 0:
                daily_progress = total_content / study_days_count
                # הצגת ההספק היומי הנדרש
                self.daily_progress_label.configure(text=f"הספק יומי: {daily_progress:.2f} {mode}")
            else:
                self.daily_progress_label.configure(text="הספק יומי: אין ימי לימוד בתקופה זו")
        
        else:  # מצב "הספק יומי קבוע" -> חישוב תאריך סיום משוער
            units_val = self.units_per_day_var.get()
            if units_val <= 0:
                # אם ההספק היומי אינו חיובי
                self.daily_progress_label.configure(text="תאריך סיום: (הספק חייב להיות > 0)")
                return

            if total_content == 0: # אם אין חומר ללמוד, תאריך הסיום הוא תאריך ההתחלה
                self.daily_progress_label.configure(text=f"תאריך סיום: {start_d.strftime('%d/%m/%Y')} (אין חומר ללמוד)")
                return

            projected_end_date = self._calculate_projected_end_date(start_d, total_content, units_val, no_study_weekdays, self.skip_holidays_var.get())

            if projected_end_date:
                duration_days = (projected_end_date - start_d).days + 1 # כולל יום ההתחלה והסיום
                # הצגת תאריך הסיום המשוער ומשך הלימוד הכולל בימים
                self.daily_progress_label.configure(text=f"תאריך סיום משוער: {projected_end_date.strftime('%d/%m/%Y')}\n({duration_days} ימים)")
            else:
                # יכול לקרות אם אין ימי לימוד אפשריים או שהחישוב נכשל (למשל, הספק נמוך מאוד וחומר רב)
                self.daily_progress_label.configure(text="תאריך סיום: (לא ניתן לחשב / אין ימי לימוד)")

    # ==================== פונקציות ייצוא ====================
    def export_ics(self):
        """
        מייצא את לוח הלימודים לקובץ ICS (iCalendar).
        """
        mode = self.mode.get()
        # בדיקה אם נבחר סוג הספק
        if not mode:
            messagebox.showwarning("אין סוג הספק", "אנא בחר סוג הספק (פרקים, משניות, דפים, עמודים).")
            return

        start_date = self.parse_date(self.start_date_var.get())
        end_date = self.parse_date(self.end_date_var.get()) # נדרש גם אם במצב הספק יומי, לחישוב ראשוני של ימי לימוד

        # בדיקת תקינות תאריך התחלה
        if not start_date:
            messagebox.showerror("שגיאה בתאריך", "אנא הכנס תאריך התחלה תקין.")
            return
        
        # אם במצב "סיום עד תאריך", ודא שתאריך הסיום תקין ומאוחר מתאריך ההתחלה
        if self.schedule_mode_var.get() == 0:
            if not end_date:
                messagebox.showerror("שגיאה בתאריך", "אנא הכנס תאריך סיום תקין.")
                return
            if start_date > end_date:
                messagebox.showerror("שגיאה בתאריכים", "תאריך ההתחלה מאוחר מהסיום.")
                return
        # איסוף ימי החופשה

        no_study_weekdays_set = {
            self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
        }

        # בדיקות נוספות בהתאם למצב הלוח
        # אם במצב "סיום עד תאריך", ודא שיש ימי לימוד
        if self.schedule_mode_var.get() == 0:
            study_days_count = calculate_study_days(start_date, end_date, no_study_weekdays_set, self.skip_holidays_var.get())
            if study_days_count == 0:
                messagebox.showwarning("אין ימי לימוד", "אין ימי לימוד זמינים בתקופה שנבחרה.")
                return
        # אם במצב "הספק יומי", ודא שההספק חיובי
        elif self.schedule_mode_var.get() == 1 and self.units_per_day_var.get() <= 0:
             messagebox.showwarning("הספק לא תקין", "ההספק היומי חייב להיות גדול מאפס.")
             return


        # בניית רשימת הנתיבים המלאים של הפריטים שנבחרו
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("לא נבחרו פריטים", "אנא בחר פריט/ים מהעץ לייצוא.")
            return
        
        # בניית רשימת הנתיבים המלאים של הפריטים שנבחרו בעץ
        selected_titles = []
        for iid in selected_items:
            full_path = []
            current = iid
            while current: # לולאה עד שמגיעים לשורש (שאין לו הורה)
                text = self.tree.item(current)["text"]
                full_path.insert(0, text)
                current = self.tree.parent(current)
            selected_titles.append(" / ".join(full_path))

        # קריאה לפונקציה הלוגית ליצירת קובץ ICS
        try:
            alarm_time = None
            if self.alarm_time_var.get():
                try:
                    alarm_time = datetime.strptime(self.alarm_time_var.get(), "%H:%M").time()
                except ValueError:
                    messagebox.showerror("שגיאה בשעת התראה", "אנא הזן שעה בפורמט HH:MM.")
                    return

            saved_path = write_ics_file(
                titles_list=selected_titles,
                mode=mode,
                start_date=start_date,
                end_date=end_date,  # יישלח גם אם במצב הספק יומי
                tree_data=self.data,
                no_study_weekdays_set=no_study_weekdays_set,
                units_per_day=self.units_per_day_var.get() if self.schedule_mode_var.get() == 1 else None,
                skip_holidays=self.skip_holidays_var.get(),
                alarm_time=alarm_time,
            )
            messagebox.showinfo("הצלחה", f"הקובץ נשמר:\n{saved_path}")
        except Exception as e:
            messagebox.showerror("שגיאה", str(e))

    def export_html(self):
        """
        מייצא את לוח הלימודים כסימנייה לקובץ HTML.
        """
        mode = self.mode.get()
        # בדיקה אם נבחר סוג הספק
        if not mode:
            messagebox.showwarning("אין סוג הספק", "אנא בחר סוג הספק (פרקים, משניות, דפים, עמודים).")
            return

        start_date = self.parse_date(self.start_date_var.get())
        end_date = self.parse_date(self.end_date_var.get()) # נדרש גם אם במצב הספק יומי, לחישוב ראשוני של ימי לימוד

        # בדיקת תקינות תאריך התחלה
        if not start_date:
            messagebox.showerror("שגיאה בתאריך", "אנא הכנס תאריך התחלה תקין.")
            return

        # אם במצב "סיום עד תאריך", ודא שתאריך הסיום תקין ומאוחר מתאריך ההתחלה
        if self.schedule_mode_var.get() == 0:
            if not end_date:
                messagebox.showerror("שגיאה בתאריך", "אנא הכנס תאריך סיום תקין.")
                return
            if start_date > end_date:
                messagebox.showerror("שגיאה בתאריכים", "תאריך ההתחלה מאוחר מהסיום.")
                return
        # איסוף ימי החופשה

        no_study_weekdays_set = {
            self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
        }
        
        # בדיקות נוספות בהתאם למצב הלוח
        # אם במצב "סיום עד תאריך", ודא שיש ימי לימוד
        if self.schedule_mode_var.get() == 0:
            study_days_count = calculate_study_days(start_date, end_date, no_study_weekdays_set, self.skip_holidays_var.get())
            if study_days_count == 0:
                messagebox.showwarning("אין ימי לימוד", "אין ימי לימוד זמינים בתקופה שנבחרה.")
                return
        # אם במצב "הספק יומי", ודא שההספק חיובי
        elif self.schedule_mode_var.get() == 1 and self.units_per_day_var.get() <= 0:
             messagebox.showwarning("הספק לא תקין", "ההספק היומי חייב להיות גדול מאפס.")
             return

        # בניית רשימת הנתיבים המלאים של הפריטים שנבחרו
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("לא נבחרו פריטים", "אנא בחר פריט/ים מהעץ לייצוא.")
            return

        # בניית רשימת הנתיבים המלאים של הפריטים שנבחרו בעץ
        selected_titles = []
        for iid in selected_items:
            full_path = []
            current = iid
            while current:
                text = self.tree.item(current)["text"]
                full_path.insert(0, text)
                current = self.tree.parent(current)
            selected_titles.append(" / ".join(full_path))

        # קריאה לפונקציה הלוגית ליצירת קובץ HTML
        try:
            saved_path = write_bookmark_html(
                titles_list=selected_titles,
                mode=mode,
                start_date=start_date,
                end_date=end_date, # יישלח גם אם במצב הספק יומי
                tree_data=self.data,
                no_study_weekdays_set=no_study_weekdays_set,
                units_per_day=self.units_per_day_var.get() if self.schedule_mode_var.get() == 1 else None,
                skip_holidays=self.skip_holidays_var.get()
            )
            messagebox.showinfo("הצלחה", f"הקובץ HTML נשמר:\n{saved_path}")
            os.startfile(saved_path) # פתיחת הקובץ בדפדפן ברירת המחדל
        except Exception as e:
            messagebox.showerror("שגיאה", str(e))

# ==============================================================================
#                                 הרצת האפליקציה
# ==============================================================================
if __name__ == "__main__":
    # יצירת מופע של האפליקציה והרצתה
    app = TorahTreeApp()
    app.mainloop()
