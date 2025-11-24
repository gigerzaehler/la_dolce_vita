import os
import sqlite3
from flask import Flask, g, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import random

APP_NAME = "La dolce vita"
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'la_dolce_vita.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXT = {'png','jpg','jpeg','gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Database helpers ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- Helpers ---

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

# --- Routes ---

###########################
# HOME
###########################
@app.route('/')
def index():
    return render_template('index.html', app_name=APP_NAME)

###########################
# REZEPT-EINTRAG
###########################
@app.route('/rezept-eintrag', methods=['GET','POST'])
def rezept_eintrag():
    db = get_db()

    if request.method == 'POST':

        # Grunddaten
        name = request.form.get('name', '').strip()
        if not name:
            flash("Bitte gib einen Rezeptnamen ein.", "danger")
            return redirect(url_for('rezept_eintrag'))

        base_portions = int(request.form.get('portionen') or 1)
        prep = int(request.form.get('prep_time') or 0)
        cook = int(request.form.get('cook_time') or 0)
        difficulty = request.form.get('difficulty') or "Einfach"

        # Rezept speichern
        cur = db.execute("""
            INSERT INTO recipes (name, base_portions, prep_minutes, cook_minutes, difficulty)
            VALUES (?, ?, ?, ?, ?)
        """, (name, base_portions, prep, cook, difficulty))

        recipe_id = cur.lastrowid

        # 🔥 Zutaten + Alternativen
        i = 0
        while True:
            zutat = request.form.get(f"name_{i}")
            if not zutat:
                break  # keine weitere Zutat vorhanden

            # Menge normalisieren (optional)
            amount_raw = request.form.get(f"amount_{i}", "").strip()
            unit_raw = request.form.get(f"unit_{i}", "").strip()

            try:
                amount = float(amount_raw.replace(",", ".")) if amount_raw else None
            except ValueError:
                amount = None

            unit = unit_raw if unit_raw else None

            # Alternative verarbeiten
            alt_name = request.form.get(f"alt_name_{i}", "").strip() or None
            alt_unit_raw = request.form.get(f"alt_unit_{i}", "").strip()
            alt_amount_raw = request.form.get(f"alt_amount_{i}", "").strip()

            try:
                alt_amount = float(alt_amount_raw.replace(",", ".")) if alt_amount_raw else None
            except ValueError:
                alt_amount = None

            alt_unit = alt_unit_raw if alt_unit_raw else None

            # In DB speichern
            db.execute("""
                INSERT INTO ingredients (
                    recipe_id, amount, unit, name,
                    alternative_name, alternative_amount, alternative_unit
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                recipe_id,
                amount,
                unit,
                zutat.strip(),
                alt_name,
                alt_amount,
                alt_unit
            ))

            i += 1  # nächste Zutat

        # 🔥 Schritte
        steps_text = request.form.get('steps', '').strip()
        if steps_text:
            steps_list = [s.strip() for s in steps_text.split("\n") if s.strip()]
            for idx, step in enumerate(steps_list, start=1):
                db.execute("""
                    INSERT INTO steps (recipe_id, step_number, description)
                    VALUES (?, ?, ?)
                """, (recipe_id, idx, step))

        # 🔥 Tags
        raw_tags = request.form.get("tags", "")
        tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]

        for tag in tag_list:
            # zuerst prüfen, ob Tag existiert
            row = db.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()
            if row:
                tag_id = row["id"]
            else:
                cur = db.execute("INSERT INTO tags (name) VALUES (?)", (tag,))
                tag_id = cur.lastrowid

            db.execute("""
                INSERT INTO recipe_tags (recipe_id, tag_id)
                VALUES (?, ?)
            """, (recipe_id, tag_id))

        # 🔥 Fotos
        files = request.files.getlist("photos")
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)

                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

                # falls derselbe Dateiname existiert → umbenennen
                if os.path.exists(save_path):
                    base, ext = os.path.splitext(filename)
                    filename = f"{base}_{random.randint(1000,9999)}{ext}"
                    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

                file.save(save_path)

                db.execute("""
                    INSERT INTO photos (recipe_id, filename)
                    VALUES (?, ?)
                """, (recipe_id, filename))

        db.commit()

        flash("Rezept erfolgreich gespeichert!", "success")
        return redirect(url_for("rezepte"))

    # GET-Request → Formular anzeigen
    tags = db.execute("SELECT * FROM tags ORDER BY name").fetchall()
    return render_template('rezept_eintrag.html', tags=tags)


###########################
# REZEPTE
###########################
@app.route('/rezepte')
def rezepte():
    db = get_db()

    sort = request.args.get('sort', 'name_asc')
    tag_filter = request.args.get('tag')

    # Sortierung
    order_sql = 'ORDER BY name COLLATE NOCASE ASC'
    if sort == 'name_desc':
        order_sql = 'ORDER BY name COLLATE NOCASE DESC'
    elif sort == 'prep_asc':
        order_sql = 'ORDER BY prep_minutes ASC'
    elif sort == 'prep_desc':
        order_sql = 'ORDER BY prep_minutes DESC'

    # Basis-SQL
    sql = 'SELECT * FROM recipes '
    params = []

    # Tag-Filter
    if tag_filter:
        sql += (
            'JOIN recipe_tags rt ON recipes.id = rt.recipe_id '
            'JOIN tags t ON rt.tag_id = t.id '
            'WHERE t.name = ? '
        )
        params.append(tag_filter)

    sql += ' ' + order_sql

    recipes = db.execute(sql, params).fetchall()

    # Tags für das Filter-Menü
    tags = db.execute('SELECT name FROM tags ORDER BY name').fetchall()

    return render_template(
        'rezepte.html',
        recipes=recipes,
        tags=[t['name'] for t in tags],
        selected_tag=tag_filter,
        sort=sort
    )



###########################
# REZEPT DETAIL
###########################
@app.route('/rezept/<int:recipe_id>', methods=['GET','POST'])
def rezept_detail(recipe_id):
    db = get_db()

    # Rezept abrufen
    rezept = db.execute(
        'SELECT * FROM recipes WHERE id = ?', (recipe_id,)
    ).fetchone()

    if not rezept:
        flash('Rezept nicht gefunden', 'danger')
        return redirect(url_for('rezepte'))

    # Zutaten abrufen
    zutaten = db.execute(
        'SELECT * FROM ingredients WHERE recipe_id = ?', (recipe_id,)
    ).fetchall()

    # Kochschritte abrufen
    schritte = db.execute(
        'SELECT * FROM steps WHERE recipe_id = ? ORDER BY step_number', (recipe_id,)
    ).fetchall()

    # Fotos
    fotos = db.execute(
        'SELECT filename FROM photos WHERE recipe_id = ?', (recipe_id,)
    ).fetchall()

    # Tags
    tags = db.execute(
        'SELECT t.name FROM tags t '
        'JOIN recipe_tags rt ON t.id = rt.tag_id '
        'WHERE rt.recipe_id = ?', (recipe_id,)
    ).fetchall()

    # Portionsberechnung
    portionen = int(request.args.get('p') or rezept['base_portions'])
    multiplier = portionen / rezept['base_portions'] if rezept['base_portions'] else 1

    return render_template(
        'rezept_detail.html',
        rezept=rezept,
        zutaten=zutaten,
        schritte=schritte,
        fotos=fotos,
        tags=[t['name'] for t in tags],
        portionen=portionen,
        multiplier=multiplier
    )


###########################
# WAS KOCHE ICH HEUTE?
###########################
@app.route('/was-koche-ich-heute', methods=['GET','POST'])
def was_koche_ich():
    db = get_db()
    results = []

    # Alle Tags für Filter anzeigen
    tags = db.execute('SELECT name FROM tags ORDER BY name').fetchall()

    if request.method == 'POST':
        ingredient_input = request.form.get('ingredients', '').strip()  # <-- hier
        tag_input = request.form.get('tag', '').strip()                 # <-- hier
        random_choice = request.form.get('random')

        recipe_ids = None

        # Zutatenfilter
        if ingredient_input:
            search_ings = [s.strip().lower() for s in ingredient_input.replace('\n', ',').split(',') if s.strip()]
            placeholders = ','.join('?' for _ in search_ings)
            sql = f"SELECT DISTINCT recipe_id FROM ingredients WHERE LOWER(name) IN ({placeholders})"
            rows = db.execute(sql, search_ings).fetchall()
            recipe_ids = {r['recipe_id'] for r in rows}

        # Tagfilter
        if tag_input:
            rows = db.execute(
                'SELECT recipe_id FROM recipe_tags rt JOIN tags tg ON rt.tag_id = tg.id WHERE tg.name = ?',
                (tag_input,)
            ).fetchall()
            tag_ids_set = {r['recipe_id'] for r in rows}
            recipe_ids = tag_ids_set if recipe_ids is None else recipe_ids.intersection(tag_ids_set)

        # Zufallsauswahl
        if random_choice:
            if recipe_ids:
                pick = random.choice(list(recipe_ids))
                results = db.execute('SELECT * FROM recipes WHERE id = ?', (pick,)).fetchall()
            else:
                results = db.execute('SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1').fetchall()
        else:
            if recipe_ids is not None:
                if recipe_ids:
                    placeholders = ','.join('?' for _ in recipe_ids)
                    results = db.execute(
                        f'SELECT * FROM recipes WHERE id IN ({placeholders})',
                        tuple(recipe_ids)
                    ).fetchall()
                else:
                    results = []

    return render_template(
        'was_koche_ich_heute.html',  # Template korrekt benennen
        results=results,
        tags=[t['name'] for t in tags]
    )


###########################
# RUN
###########################
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
