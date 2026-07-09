import sqlite3

DB_NAME = "maintenance.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS secteurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS demandeurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            secteur_id INTEGER,
            telephone TEXT,
            email TEXT,
            FOREIGN KEY (secteur_id) REFERENCES secteurs(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS demandes_intervention (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secteur_id INTEGER,
            demandeur_id INTEGER,
            nature_travaux TEXT NOT NULL,
            description TEXT NOT NULL,
            statut TEXT NOT NULL DEFAULT 'En cours',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_cloture TIMESTAMP,
            FOREIGN KEY (secteur_id) REFERENCES secteurs(id),
            FOREIGN KEY (demandeur_id) REFERENCES demandeurs(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rapports_intervention (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secteur_id INTEGER,
            machine TEXT,
            probleme TEXT NOT NULL,
            travaux TEXT NOT NULL,
            technicien TEXT NOT NULL,
            commentaire TEXT,
            reference TEXT,
            date_rapport TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (secteur_id) REFERENCES secteurs(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_element TEXT NOT NULL,
            element_id INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    secteurs_par_defaut = [
        "Axame",
        "Pourfendeuse",
        "Extérieur",
        "Pont n°2",
        "Hall 1",
        "Hall 2",
        "V2",
        "V3",
        "V2-V3",
        "V6"
    ]

    for secteur in secteurs_par_defaut:
        conn.execute(
            "INSERT OR IGNORE INTO secteurs (nom) VALUES (?)",
            (secteur,)
        )
    conn.commit()
    conn.close()