import os
from datetime import date
from flask import Flask, render_template, request, send_file, flash

from torah_logic_full_updated import (
    load_data,
    write_bookmark_html,
    write_ics_file,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hspek-secret'

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'torah_tree_data_full.json')
TREE_DATA = load_data(DATA_PATH)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            titles = [t.strip() for t in request.form.get('titles', '').splitlines() if t.strip()]
            mode = request.form['mode']
            start_date = date.fromisoformat(request.form['start_date'])
            end_date = date.fromisoformat(request.form['end_date'])
            schedule_mode = request.form.get('schedule_mode', 'range')
            units_per_day = int(request.form.get('units_per_day', 1)) if schedule_mode == 'daily' else None
            skip_holidays = request.form.get('skip_holidays') == 'on'
            balance = request.form.get('balance_mishnayot') == 'on'
            output_format = request.form.get('output_format', 'html')

            no_study_days = set()

            if output_format == 'html':
                path = write_bookmark_html(
                    titles_list=titles,
                    mode=mode,
                    start_date=start_date,
                    end_date=end_date,
                    tree_data=TREE_DATA,
                    no_study_weekdays_set=no_study_days,
                    units_per_day=units_per_day,
                    skip_holidays=skip_holidays,
                    balance_chapters_by_mishnayot=balance,
                )
            else:
                path = write_ics_file(
                    titles_list=titles,
                    mode=mode,
                    start_date=start_date,
                    end_date=end_date,
                    tree_data=TREE_DATA,
                    no_study_weekdays_set=no_study_days,
                    units_per_day=units_per_day,
                    skip_holidays=skip_holidays,
                    alarm_time=None,
                    balance_chapters_by_mishnayot=balance,
                )

            if path:
                return send_file(path, as_attachment=True)
            else:
                flash('לא נוצר קובץ.')
        except Exception as e:
            flash(str(e))

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
