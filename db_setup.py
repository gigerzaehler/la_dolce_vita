import sqlite3

DB = "la_dolce_vita.db"

def create_tables():
    conn = sqlite3.connect(DB)
    c = conn.cursor()


    # recipes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        base_portions INTEGER NOT NULL DEFAULT 1,
        prep_minutes INTEGER DEFAULT 0,
        cook_minutes INTEGER DEFAULT 0,
        difficulty TEXT CHECK(difficulty IN ('Einfach','Mittel','Schwer')) DEFAULT 'Einfach'
        )
    ''')


    # ingredients (one row per ingredient per recipe)
    c.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipe_id INTEGER NOT NULL,
        amount REAL,
        unit TEXT,
        name TEXT NOT NULL,
        alternative_name TEXT,
        alternative_amount REAL,
        alternative_unit TEXT,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    ''')


    # steps
    c.execute('''
        CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipe_id INTEGER NOT NULL,
        step_number INTEGER NOT NULL,
        description TEXT NOT NULL,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    ''')


    # tags
    c.execute('''
        CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
        )
    ''')


    # many-to-many recipe_tags
    c.execute('''
        CREATE TABLE IF NOT EXISTS recipe_tags (
        recipe_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY(recipe_id, tag_id),
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
        FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    ''')


    # photos
    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipe_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    ''')


    conn.commit()
    conn.close()


if __name__ == '__main__':
    create_tables()
    print(f"Database created/updated la_dolce_vita.db")
