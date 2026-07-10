import os
import sqlite3

import psycopg2
from psycopg2.extras import DictCursor


DATABASE_URL = os.environ.get("DATABASE_URL")
DB_NAME = "maintenance.db"


class PostgresCursorAdapter:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class PostgresConnectionAdapter:
    """
    Permet de continuer à utiliser la syntaxe actuelle :
        conn.execute(...)
        WHERE id = ?
        cursor.lastrowid
    avec PostgreSQL.
    """

    def __init__(self, database_url):
        self.connection = psycopg2.connect(database_url)

    def execute(self, query, params=()):
        # Conversion des ? SQLite en %s PostgreSQL
        postgres_query = query.replace("?", "%s")
        cursor = self.connection.cursor(cursor_factory=DictCursor)

        lastrowid = None
        normalized_query = postgres_query.strip().upper()

        # Les INSERT de l'application utilisent parfois cursor.lastrowid.
        # On ajoute donc RETURNING id lorsque c'est possible.
        if (
            normalized_query.startswith("INSERT INTO")
            and "RETURNING" not in normalized_query
            and "ON CONFLICT" not in normalized_query
        ):
            postgres_query = postgres_query.rstrip().rstrip(";") + " RETURNING id"

            cursor.execute(postgres_query, params)
            inserted_row = cursor.fetchone()

            if inserted_row:
                lastrowid = inserted_row["id"]
        else:
            cursor.execute(postgres_query, params)

        return PostgresCursorAdapter(cursor, lastrowid)

    def cursor(self):
        return self.connection.cursor(cursor_factory=DictCursor)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def get_db_connection():
    if DATABASE_URL:
        print("Connexion à Neon PostgreSQL", flush=True)
        return PostgresConnectionAdapter(DATABASE_URL)

    print("Connexion à SQLite", flush=True)

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def is_postgres():
    return bool(DATABASE_URL)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS secteurs (
                id SERIAL PRIMARY KEY,
                nom TEXT NOT NULL UNIQUE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS demandeurs (
                id SERIAL PRIMARY KEY,
                nom TEXT NOT NULL,
                secteur_id INTEGER REFERENCES secteurs(id),
                telephone TEXT,
                email TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS demandes_intervention (
                id SERIAL PRIMARY KEY,
                secteur_id INTEGER REFERENCES secteurs(id),
                demandeur_id INTEGER REFERENCES demandeurs(id),
                nature_travaux TEXT NOT NULL,
                description TEXT NOT NULL,
                statut TEXT NOT NULL DEFAULT 'En cours',
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_cloture TIMESTAMP,
                date_solde TIMESTAMP,
                solde_par TEXT,
                reference_piece TEXT,
                commentaire_solde TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rapports_intervention (
                id SERIAL PRIMARY KEY,
                secteur_id INTEGER REFERENCES secteurs(id),
                machine TEXT,
                probleme TEXT NOT NULL,
                travaux TEXT NOT NULL,
                technicien TEXT NOT NULL,
                commentaire TEXT,
                reference TEXT,
                date_rapport TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id SERIAL PRIMARY KEY,
                type_element TEXT NOT NULL,
                element_id INTEGER NOT NULL,
                nom_fichier TEXT NOT NULL,
                date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS secteurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS demandeurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                secteur_id INTEGER,
                telephone TEXT,
                email TEXT,
                FOREIGN KEY (secteur_id) REFERENCES secteurs(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS demandes_intervention (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                secteur_id INTEGER,
                demandeur_id INTEGER,
                nature_travaux TEXT NOT NULL,
                description TEXT NOT NULL,
                statut TEXT NOT NULL DEFAULT 'En cours',
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_cloture TIMESTAMP,
                date_solde TIMESTAMP,
                solde_par TEXT,
                reference_piece TEXT,
                commentaire_solde TEXT,
                FOREIGN KEY (secteur_id) REFERENCES secteurs(id),
                FOREIGN KEY (demandeur_id) REFERENCES demandeurs(id)
            )
        """)

        cursor.execute("""
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

        cursor.execute("""
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
        "Mag Auto",
        "Poste HT",
        "Réseau Eau",
        "Tuberie",
        "Batiments",
        "Pont n°2",
        "Hall 1",
        "Hall 2",
        "V2",
        "V3",
        "V2-V3",
        "V6"
    ]

    for secteur in secteurs_par_defaut:
        if is_postgres():
            cursor.execute("""
                INSERT INTO secteurs (nom)
                VALUES (%s)
                ON CONFLICT (nom) DO NOTHING
            """, (secteur,))
        else:
            cursor.execute(
                "INSERT OR IGNORE INTO secteurs (nom) VALUES (?)",
                (secteur,)
            )

    conn.commit()
    conn.close()