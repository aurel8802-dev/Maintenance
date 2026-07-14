import os
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import DictCursor


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "maintenance.db"

DATABASE_URL = os.getenv("DATABASE_URL")


# -------------------------------------------------------------------
# Adaptateurs PostgreSQL
# -------------------------------------------------------------------

class PostgresCursorAdapter:
    """
    Adapte un curseur PostgreSQL au fonctionnement attendu
    par le reste de l'application.
    """

    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class PostgresConnectionAdapter:
    """
    Permet de conserver la syntaxe utilisée avec SQLite :

        conn.execute(...)
        WHERE id = ?
        cursor.lastrowid

    tout en utilisant PostgreSQL sur Render.
    """

    def __init__(self, database_url):
        self.connection = psycopg2.connect(database_url)

    def execute(self, query, params=()):
        postgres_query = query.replace("?", "%s")
        cursor = self.connection.cursor(cursor_factory=DictCursor)

        lastrowid = None
        normalized_query = postgres_query.strip().upper()

        # Les INSERT de l'application récupèrent parfois cursor.lastrowid.
        # PostgreSQL utilise RETURNING id pour obtenir l'identifiant créé.
        is_insert = normalized_query.startswith("INSERT INTO")
        has_returning = "RETURNING" in normalized_query
        has_conflict_clause = "ON CONFLICT" in normalized_query

        if is_insert and not has_returning and not has_conflict_clause:
            postgres_query = (
                postgres_query.rstrip().rstrip(";")
                + " RETURNING id"
            )

            cursor.execute(postgres_query, params)
            inserted_row = cursor.fetchone()

            if inserted_row:
                lastrowid = inserted_row["id"]
        else:
            cursor.execute(postgres_query, params)

        return PostgresCursorAdapter(
            cursor=cursor,
            lastrowid=lastrowid
        )

    def cursor(self):
        return self.connection.cursor(cursor_factory=DictCursor)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


# -------------------------------------------------------------------
# Connexion
# -------------------------------------------------------------------

def is_postgres():
    """Indique si l'application utilise PostgreSQL."""
    return bool(DATABASE_URL)


def get_db_connection():
    """
    Retourne une connexion PostgreSQL sur Render
    ou SQLite en développement local.
    """
    if is_postgres():
        return PostgresConnectionAdapter(DATABASE_URL)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Active réellement les contraintes FOREIGN KEY sous SQLite.
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# -------------------------------------------------------------------
# Création des tables PostgreSQL
# -------------------------------------------------------------------

def create_postgres_tables(cursor):
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


# -------------------------------------------------------------------
# Création des tables SQLite
# -------------------------------------------------------------------

def create_sqlite_tables(cursor):
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


# -------------------------------------------------------------------
# Secteurs par défaut
# -------------------------------------------------------------------

DEFAULT_SECTORS = [
    "Axame",
    "Pourfendeuse",
    "Extérieur",
    "Mag Auto",
    "Poste HT",
    "Réseau Eau",
    "Tuberie",
    "Bâtiments",
    "Pont n°2",
    "Hall 1",
    "Hall 2",
    "V2",
    "V3",
    "V2-V3",
    "V6"
]


def insert_default_sectors(cursor):
    for sector_name in DEFAULT_SECTORS:
        if is_postgres():
            cursor.execute("""
                INSERT INTO secteurs (nom)
                VALUES (%s)
                ON CONFLICT (nom) DO NOTHING
            """, (sector_name,))
        else:
            cursor.execute(
                "INSERT OR IGNORE INTO secteurs (nom) VALUES (?)",
                (sector_name,)
            )


# -------------------------------------------------------------------
# Initialisation
# -------------------------------------------------------------------

def init_db():
    """Crée les tables et ajoute les secteurs par défaut."""
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        if is_postgres():
            create_postgres_tables(cursor)
        else:
            create_sqlite_tables(cursor)

        insert_default_sectors(cursor)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()