import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
from tkcalendar import DateEntry
from datetime import date, timedelta
import locale
import os

from torah_logic_full_updated import (
    load_data, get_length_from_node, has_relevant_data_recursive,
    calculate_study_days, write_ics_file,
    write_bookmark_html
)

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

try:
    locale.setlocale(locale.LC_ALL, 'he_IL.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'he_IL')
    except locale.Error:
        pass

DEFAULT_FILE = "torah_tree_data_full.json"

class TorahTreeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("מניין לימוד | חישוב הספק יומי")
        self.geometry("940x590")
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

        self.build_gui()

        if os.path.exists(DEFAULT_FILE):
            self.load_and_build(DEFAULT_FILE)
        else:
            self.disable_all_radio_buttons()
            self.tree.insert("", "end", text="לטעינת קובץ נתונים יש ללחוץ על הכפתור למעלה", open=True)

    def build_gui(self):
        # TOP FRAME
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=8, pady=(7,3))
        ctk.CTkButton(top_frame, text="נתונים קובץ טען...", command=self.choose_file, width=140).pack(side="right", padx=(0,10))
        ctk.CTkLabel(top_frame, text=r"תאריכים \ סעיף \ קובץ - לימוד מניין", font=ctk.CTkFont(size=19, weight="bold")).pack(side="left")

        # MAIN FRAME
        main_frame = ctk.CTkFrame(self, fg_color="#f8fafc")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # TREE FRAME
        tree_frame = ctk.CTkFrame(main_frame, fg_color="#e6f0fa", corner_radius=15)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0,18), pady=3)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style(self)
        style.configure("Treeview", font=("Arial", 18), rowheight=30)

        self.tree = ttk.Treeview(tree_frame, selectmode="extended", show="tree", height=20)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(4,0), pady=6)
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # CONTROL PANEL
        ctrl_frame = ctk.CTkFrame(main_frame, fg_color="#f0f8ff", corner_radius=18)
        ctrl_frame.grid(row=0, column=1, sticky="nsew", padx=(0,2), pady=5)
        ctrl_frame.grid_columnconfigure(0, weight=1)

        # סוג ספירה
        mode_group = ctk.CTkFrame(ctrl_frame, fg_color="#d9e9f6", corner_radius=12)
        ctk.CTkLabel(mode_group, text="לפי סכם", font=ctk.CTkFont(weight="bold")).pack(anchor="ne", padx=8, pady=(4, 0))
        mode_group.grid(row=0, column=0, sticky="ew", pady=7, padx=12)
        for opt in ("פרקים", "משניות", "דפים", "עמודים"):
            rb = ctk.CTkRadioButton(mode_group, text=opt, variable=self.mode, value=opt, command=self.update_sum_and_daily_progress)
            rb.pack(anchor="w", pady=1)
            self.radio_buttons[opt] = rb

        self.sum_label = ctk.CTkLabel(ctrl_frame, text="הכולל האורך: 0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#2b539b")
        self.sum_label.grid(row=1, column=0, sticky="ew", pady=(8,4))
        self.daily_progress_label = ctk.CTkLabel(ctrl_frame, text="יומי הספק: N/A", font=ctk.CTkFont(size=13), text_color="#803b99")
        self.daily_progress_label.grid(row=2, column=0, sticky="ew", pady=(0,9))

        # תאריכים
        date_frame = ctk.CTkFrame(ctrl_frame, fg_color="#d9e9f6", corner_radius=12)
        ctk.CTkLabel(date_frame, text="לימוד טווח הגדר", font=ctk.CTkFont(weight="bold")).pack(anchor="ne", padx=8, pady=(4, 0))
        date_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0,8))
        ttk.Label(date_frame, text="תאריך התחלה:", font=("Arial", 15)).pack(anchor="w")
        self.start_date_entry = DateEntry(date_frame, textvariable=self.start_date_var, width=14, date_pattern="yyyy-mm-dd", locale='he_IL', font=("Arial", 14))
        self.start_date_entry.pack(fill="x", pady=2)
        ttk.Label(date_frame, text="תאריך סיום:", font=("Arial", 15)).pack(anchor="w")
        self.end_date_entry = DateEntry(date_frame, textvariable=self.end_date_var, width=14, date_pattern="yyyy-mm-dd", locale='he_IL', font=("Arial", 14))
        self.end_date_entry.pack(fill="x", pady=2)

        self.start_date_var.trace_add("write", lambda *args: self.calculate_and_display_daily_progress())
        self.end_date_var.trace_add("write", lambda *args: self.calculate_and_display_daily_progress())

        # ימי חופשה
        no_study_frame = ctk.CTkFrame(ctrl_frame, fg_color="#d9e9f6", corner_radius=12)
        ctk.CTkLabel(no_study_frame, text="חופשה ימי", font=ctk.CTkFont(size=13, weight="bold"), anchor="e", justify="right").grid(row=0, column=0, columnspan=4, sticky="e", padx=12, pady=(4, 0))
        days = list(self.no_study_days.keys())
        for i, day in enumerate(days):
            cb = ctk.CTkCheckBox(no_study_frame, text=day, variable=self.no_study_days[day], command=self.calculate_and_display_daily_progress)
            cb.grid(row=(i // 4) + 1, column=i % 4, sticky="w", padx=1, pady=2)
        no_study_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 7))

        # כפתורים
        #ctk.CTkButton(ctrl_frame, text="אורך חשב", fg_color="#cce5ff", text_color="#1f4788", command=self.update_sum_and_daily_progress, height=38).grid(row=5, column=0, sticky="ew", padx=20, pady=(10,2))
        ctk.CTkButton(ctrl_frame, text="לקובץ ייצוא ICS", fg_color="#218cfa", hover_color="#186bb7", text_color="white", command=self.export_ics, height=38).grid(row=6, column=0, sticky="ew", padx=20, pady=(0,12))
        ctk.CTkButton(ctrl_frame, text="HTML צור סימנייה", fg_color="#a6d785", hover_color="#7aa557", text_color="black", command=self.export_html, height=38).grid(row=7, column=0, sticky="ew", padx=20, pady=(0,12))

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

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
        study_days_count = calculate_study_days(start_d, end_d, {
            self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
        })
        if study_days_count > 0:
            daily_progress = total_content / study_days_count
            self.daily_progress_label.configure(text=f"הספק יומי: {daily_progress:.2f} {mode}")
        else:
            self.daily_progress_label.configure(text="הספק יומי: אין ימי לימוד בתקופה זו")

    def export_ics(self):
        mode = self.mode.get()
        if not mode:
            messagebox.showwarning("אין סוג הספק", "אנא בחר סוג הספק (פרקים, משניות, דפים, עמודים).")
            return

        total_content = self.current_total_content # This variable is not used in the call to write_ics_file, it's just for display
        start_date = self.parse_date(self.start_date_var.get())
        end_date = self.parse_date(self.end_date_var.get())
        if not start_date or not end_date:
            messagebox.showerror("שגיאה בתאריך", "אנא הכנס תאריך התחלה/סיום תקין.")
            return
        if start_date > end_date:
            messagebox.showerror("שגיאה בתאריכים", "תאריך ההתחלה מאוחר מהסיום.")
            return

        study_days_count = calculate_study_days(start_date, end_date, {
            self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
        })
        if study_days_count == 0:
            messagebox.showwarning("אין ימי לימוד", "אין ימי לימוד זמינים בתקופה.")
            return

        # בניית רשימת הנתיבים המלאים
        selected_items = self.tree.selection()
        selected_titles = []
        for iid in selected_items:
            full_path = []
            current = iid
            while current:
                text = self.tree.item(current)["text"]
                full_path.insert(0, text)
                current = self.tree.parent(current)
            selected_titles.append(" / ".join(full_path))

        try:
            # Corrected: Call write_ics_file directly
            saved_path = write_ics_file(
                titles_list=selected_titles,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                tree_data=self.data, # זה בסדר
                no_study_weekdays_set={ # הוסף את השורה הזו ואת הסוגריים המסולסלים
                    self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
                }
            )
            messagebox.showinfo("הצלחה", f"הקובץ נשמר:\n{saved_path}")
        except Exception as e:
            messagebox.showerror("שגיאה", str(e))

    def export_html(self):
        mode = self.mode.get()
        if not mode:
            messagebox.showwarning("אין סוג הספק", "אנא בחר סוג הספק (פרקים, משניות, דפים, עמודים).")
            return

        total_content = self.current_total_content # This variable is not used in the call to write_bookmark_html, it's just for display
        start_date = self.parse_date(self.start_date_var.get())
        end_date = self.parse_date(self.end_date_var.get())
        if not start_date or not end_date:
            messagebox.showerror("שגיאה בתאריך", "אנא הכנס תאריך התחלה/סיום תקין.")
            return
        if start_date > end_date:
            messagebox.showerror("שגיאה בתאריכים", "תאריך ההתחלה מאוחר מהסיום.")
            return

        study_days_count = calculate_study_days(start_date, end_date, {
            self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
        })
        if study_days_count == 0:
            messagebox.showwarning("אין ימי לימוד", "אין ימי לימוד זמינים בתקופה.")
            return

        # בניית רשימת הנתיבים המלאים
        selected_items = self.tree.selection()
        selected_titles = []
        for iid in selected_items:
            full_path = []
            current = iid
            while current:
                text = self.tree.item(current)["text"]
                full_path.insert(0, text)
                current = self.tree.parent(current)
            selected_titles.append(" / ".join(full_path))

        try:
            # Corrected: Call write_bookmark_html directly
            saved_path = write_bookmark_html(
                titles_list=selected_titles,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                tree_data=self.data, # זה בסדר
                no_study_weekdays_set={ # הוסף את השורה הזו ואת הסוגריים המסולסלים
                    self.weekday_map[day] for day, var in self.no_study_days.items() if var.get()
                }
            )
            messagebox.showinfo("הצלחה", f"הקובץ HTML נשמר:\n{saved_path}")
        except Exception as e:
            messagebox.showerror("שגיאה", str(e))


if __name__ == "__main__":
    app = TorahTreeApp()
    app.mainloop()
