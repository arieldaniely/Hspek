import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import json
from datetime import date, timedelta
from ics import Calendar, Event
from tkcalendar import DateEntry
import locale
import os

ctk.set_appearance_mode("system")  # אפשר גם "dark" או "light"
ctk.set_default_color_theme("blue")  # אפשר גם "green", "dark-blue"

# עברית לתאריכים במערכת
try:
    locale.setlocale(locale.LC_ALL, 'he_IL.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'he_IL')
    except locale.Error:
        pass

DEFAULT_FILE = "torah_tree_data_full.json"

def load_data(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("שגיאה", f"שגיאה בטעינת קובץ הנתונים:\n{e}")
        return {}

def has_relevant_data_recursive(node, mode):
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

class TorahTreeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("מניין לימוד | חישוב הספק יומי")
        self.geometry("940x560")
        self.minsize(780, 480)

        self.mode = ctk.StringVar(value="פרקים")
        self.start_date_var = ctk.StringVar(value=date.today().strftime('%Y-%m-%d'))
        self.end_date_var = ctk.StringVar(value=(date.today() + timedelta(days=30)).strftime('%Y-%m-%d'))

        days_of_week = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
        self.no_study_days = {day: ctk.BooleanVar(value=(day=="שבת")) for day in days_of_week}
        self.weekday_map = {
            "ראשון": 6, "שני": 0, "שלישי": 1, "רביעי": 2,
            "חמישי": 3, "שישי": 4, "שבת": 5
        }

        self.data = {}
        self.node_map = {}
        self.radio_buttons = {}
        self.current_total_content = 0

        # ---------- Top bar ----------
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=8, pady=(7,3))
        ctk.CTkButton(top_frame, text="טען קובץ נתונים...", command=self.choose_file, width=140).pack(side="right", padx=(0,10))
        ctk.CTkLabel(top_frame, text="מניין לימוד - בחר קובץ / סעיף / תאריכים", font=ctk.CTkFont(size=19, weight="bold")).pack(side="left")

        # ---------- Main frame ----------
        main_frame = ctk.CTkFrame(self, fg_color="#f8fafc")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # ---------- TreeView ----------
        tree_frame = ctk.CTkFrame(main_frame, fg_color="#e6f0fa", corner_radius=15)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0,18), pady=3)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, selectmode="extended", show="tree", height=20)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(4,0), pady=6)
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # ---------- Control Panel ----------
        ctrl_frame = ctk.CTkFrame(main_frame, fg_color="#f0f8ff", corner_radius=18)
        ctrl_frame.grid(row=0, column=1, sticky="nsew", padx=(0,2), pady=5)
        ctrl_frame.grid_columnconfigure(0, weight=1)

        # -- סוג ספירה --
        mode_group = ctk.CTkLabelFrame(ctrl_frame, text="סכם לפי", fg_color="#d9e9f6", corner_radius=12)
        mode_group.grid(row=0, column=0, sticky="ew", pady=7, padx=12)
        for opt in ("פרקים", "משניות", "דפים", "עמודים"):
            rb = ctk.CTkRadioButton(mode_group, text=opt, variable=self.mode, value=opt, command=self.update_sum_and_daily_progress)
            rb.pack(anchor="w", pady=1)
            self.radio_buttons[opt] = rb

        # -- תוצאות --
        self.sum_label = ctk.CTkLabel(ctrl_frame, text="האורך הכולל: 0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#2b539b")
        self.sum_label.grid(row=1, column=0, sticky="ew", pady=(8,4))
        self.daily_progress_label = ctk.CTkLabel(ctrl_frame, text="הספק יומי: N/A", font=ctk.CTkFont(size=13), text_color="#803b99")
        self.daily_progress_label.grid(row=2, column=0, sticky="ew", pady=(0,9))

        # -- תאריכים --
        date_frame = ctk.CTkLabelFrame(ctrl_frame, text="הגדר טווח לימוד", fg_color="#d9e9f6", corner_radius=12)
        date_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0,8))
        ttk.Label(date_frame, text="תאריך התחלה:").pack(anchor="w")
        self.start_date_entry = DateEntry(date_frame, textvariable=self.start_date_var, width=14, date_pattern="yyyy-mm-dd", locale='he_IL')
        self.start_date_entry.pack(fill="x", pady=2)
        ttk.Label(date_frame, text="תאריך סיום:").pack(anchor="w")
        self.end_date_entry = DateEntry(date_frame, textvariable=self.end_date_var, width=14, date_pattern="yyyy-mm-dd", locale='he_IL')
        self.end_date_entry.pack(fill="x", pady=2)

        self.start_date_var.trace_add("write", lambda *args: self.calculate_and_display_daily_progress())
        self.end_date_var.trace_add("write", lambda *args: self.calculate_and_display_daily_progress())

        # -- ימי חופשה --
        no_study_frame = ctk.CTkLabelFrame(ctrl_frame, text="ימי חופשה", fg_color="#d9e9f6", corner_radius=12)
        no_study_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0,7))
        days = list(self.no_study_days.keys())
        for i, day in enumerate(days):
            cb = ctk.CTkCheckBox(no_study_frame, text=day, variable=self.no_study_days[day], command=self.calculate_and_display_daily_progress)
            cb.grid(row=i // 4, column=i % 4, sticky="w", padx=1, pady=2)

        # -- כפתורים --
        btn_calc = ctk.CTkButton(ctrl_frame, text="חשב אורך", fg_color="#cce5ff", text_color="#1f4788", command=self.update_sum_and_daily_progress, height=38)
        btn_calc.grid(row=5, column=0, sticky="ew", padx=20, pady=(10,2))
        btn_export = ctk.CTkButton(ctrl_frame, text="ייצוא לקובץ ICS", fg_color="#218cfa", hover_color="#186bb7", text_color="white", command=self.generate_ics, height=38)
        btn_export.grid(row=6, column=0, sticky="ew", padx=20, pady=(0,12))

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        if os.path.exists(DEFAULT_FILE):
            self.load_and_build(DEFAULT_FILE)
        else:
            self.disable_all_radio_buttons()
            self.tree.insert("", "end", text="לטעינת קובץ נתונים יש ללחוץ על הכפתור למעלה", open=True)

    def choose_file(self):
        path = filedialog.askopenfilename(title="בחר קובץ JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            self.load_and_build(path)

    def load_and_build(self, path):
        self.data = load_data(path)
        if self.data:
            self.tree.delete(*self.tree.get_children())
            self.node_map.clear()
            self._build_full_tree_recursive("", self.data)
            self.update_sum_and_daily_progress()
            if self.tree.get_children():
                first_item = self.tree.get_children()[0]
                self.tree.selection_set(first_item)
                self.tree.focus(first_item)
            else:
                self.disable_all_radio_buttons()
                self.sum_label.configure(text="האורך הכולל: 0")
                self.daily_progress_label.configure(text="הספק יומי: N/A")
        else:
            self.tree.delete(*self.tree.get_children())
            self.disable_all_radio_buttons()
            self.sum_label.configure(text="האורך הכולל: 0")
            self.daily_progress_label.configure(text="הספק יומי: N/A")
            self.tree.insert("", "end", text="טעינת הקובץ נכשלה או שהקובץ ריק.", open=True)

    def _build_full_tree_recursive(self, parent_iid, node_data):
        if not isinstance(node_data, dict): return
        for key, val in node_data.items():
            if key in ["אורך בדפים", "עמוד אחרון", "משניות", "פרקים"] and not isinstance(val, dict):
                continue
            iid = self.tree.insert(parent_iid, "end", text=key, open=False)
            self.node_map[iid] = val
            if isinstance(val, dict):
                self._build_full_tree_recursive(iid, val)

    def disable_all_radio_buttons(self):
        for opt in self.radio_buttons:
            self.radio_buttons[opt].configure(state="disabled")

    def on_tree_select(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            self.disable_all_radio_buttons()
            self.current_total_content = 0
            self.sum_label.configure(text="האורך הכולל: 0")
            self.daily_progress_label.configure(text="הספק יומי: N/A")
            return

        relevant_modes_for_selection = set()
        for iid in selected_items:
            if iid in self.node_map:
                node_data = self.node_map[iid]
                for mode_option in ["פרקים", "משניות", "דפים", "עמודים"]:
                    if has_relevant_data_recursive(node_data, mode_option):
                        relevant_modes_for_selection.add(mode_option)
        current_mode_active = False
        new_default_mode = ""
        for opt in ["פרקים", "משניות", "דפים", "עמודים"]:
            if opt in relevant_modes_for_selection:
                self.radio_buttons[opt].configure(state="normal")
                if not new_default_mode:
                    new_default_mode = opt
                if self.mode.get() == opt:
                    current_mode_active = True
            else:
                self.radio_buttons[opt].configure(state="disabled")
        if not current_mode_active and relevant_modes_for_selection:
            self.mode.set(new_default_mode)
        elif not relevant_modes_for_selection:
            self.mode.set("")
            self.disable_all_radio_buttons()
        self.update_sum_and_daily_progress()

    def update_sum_and_daily_progress(self):
        mode = self.mode.get()
        total = 0
        selected_items = self.tree.selection()
        if not selected_items or not mode:
            self.current_total_content = 0
            self.sum_label.configure(text="האורך הכולל: 0")
        else:
            for iid in selected_items:
                if iid in self.node_map:
                    node = self.node_map[iid]
                    total += get_length_from_node(node, mode)
            self.current_total_content = total
            self.sum_label.configure(text=f"האורך הכולל: {self.current_total_content}")
        self.calculate_and_display_daily_progress()

    def parse_date(self, date_str):
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    def calculate_and_display_daily_progress(self):
        mode = self.mode.get()
        if not self.tree.selection() or not mode:
            self.daily_progress_label.configure(text="הספק יומי: N/A")
            return
        total_content = self.current_total_content
        start_d = self.parse_date(self.start_date_var.get())
        end_d = self.parse_date(self.end_date_var.get())
        if not start_d or not end_d:
            self.daily_progress_label.configure(text="הספק יומי: (הכנס תאריכים)")
            return
        if start_d > end_d:
            self.daily_progress_label.configure(text="הספק יומי: (תאריך התחלה מאוחר מהסיום)")
            return
        study_days_count = self._get_study_days_count(start_d, end_d)
        if study_days_count > 0:
            daily_progress = total_content / study_days_count
            self.daily_progress_label.configure(text=f"הספק יומי: {daily_progress:.2f} {mode}")
        else:
            self.daily_progress_label.configure(text="הספק יומי: אין ימי לימוד בתקופה זו")

    def _get_study_days_count(self, start_date, end_date):
        count = 0
        current_date = start_date
        no_study_weekday_nums = {self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()}
        while current_date <= end_date:
            if current_date.weekday() not in no_study_weekday_nums:
                count += 1
            current_date += timedelta(days=1)
        return count

    def generate_ics(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("אין בחירה", "אנא בחר פריטים ללימוד מהעץ.")
            return
        mode = self.mode.get()
        if not mode:
            messagebox.showwarning("אין סוג הספק", "אנא בחר סוג הספק (פרקים, משניות, דפים, עמודים).")
            return
        total_content = self.current_total_content
        start_date = self.parse_date(self.start_date_var.get())
        end_date = self.parse_date(self.end_date_var.get())
        if not start_date or not end_date:
            messagebox.showerror("שגיאה בתאריך", "אנא הכנס תאריך התחלה/סיום תקין (YYYY-MM-DD).")
            return
        if start_date > end_date:
            messagebox.showerror("שגיאה בתאריכים", "תאריך ההתחלה אינו יכול להיות מאוחר מתאריך הסיום.")
            return
        study_days_count = self._get_study_days_count(start_date, end_date)
        if study_days_count == 0:
            messagebox.showwarning("אין ימי לימוד", "אין ימי לימוד זמינים בתקופה שנבחרה לאחר סינון הימים ללא לימוד.")
            return
        daily_amount = total_content / study_days_count
        cal = Calendar()
        current_study_unit = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() not in ({self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()}):
                if current_study_unit >= total_content:
                    break
                e = Event()
                e.name = f"לימוד {mode}"
                e.begin = current_date.strftime('%Y-%m-%d 09:00:00')
                e.end = current_date.strftime('%Y-%m-%d 10:00:00')
                start_range = current_study_unit
                end_range = min(current_study_unit + daily_amount, total_content)
                e.description = f"הספק יומי: {daily_amount:.2f} {mode}\nמ-{start_range:.2f} עד {end_range:.2f} {mode}"
                cal.events.add(e)
                current_study_unit = end_range
            current_date += timedelta(days=1)
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".ics", filetypes=[("ICS files", "*.ics"), ("All files", "*.*")], title="שמור קובץ יומן ICS")
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(cal)
                messagebox.showinfo("הצלחה", f"קובץ ICS נוצר בהצלחה ב: {file_path}")
        except Exception as e:
            messagebox.showerror("שגיאה", f"שגיאה ביצירת קובץ ICS: {e}")

if __name__ == "__main__":
    app = TorahTreeApp()
    app.mainloop()
