import os
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import DictCursor


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "maintenance.db"
DATABASE_URL = os.getenv("DATABASE_URL")


class PostgresCursorAdapter:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class PostgresConnectionAdapter:
    def __init__(self, database_url):
        self.connection = psycopg2.connect(database_url)

    def execute(self, query, params=()):
        postgres_query = query.replace("?", "%s")
        cursor = self.connection.cursor(cursor_factory=DictCursor)

        lastrowid = None
        normalized_query = postgres_query.strip().upper()

        is_insert = normalized_query.startswith("INSERT INTO")
        has_returning = "RETURNING" in normalized_query
        has_conflict_clause = "ON CONFLICT" in normalized_query

        if is_insert and not has_returning and not has_conflict_clause:
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


def is_postgres():
    return bool(DATABASE_URL)


def get_db_connection():
    if is_postgres():
        return PostgresConnectionAdapter(DATABASE_URL)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_postgres_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS secteurs (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL UNIQUE,
            actif BOOLEAN NOT NULL DEFAULT TRUE
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
            nom_fichier TEXT,
            url_photo TEXT,
            public_id TEXT,
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techniciens (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS machines (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL,
            secteur_id INTEGER NOT NULL REFERENCES secteurs(id),
            actif BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE (nom, secteur_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courbes_edf (
            id SERIAL PRIMARY KEY,
            annee INTEGER NOT NULL,
            mois INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            donnees_xml BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (annee, mois)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chantiers (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL UNIQUE,
            actif BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commandes (
            id SERIAL PRIMARY KEY,
            date_commande DATE NOT NULL DEFAULT CURRENT_DATE,
            piece TEXT NOT NULL,
            quantite TEXT NOT NULL DEFAULT '1',
            reference TEXT,
            etat TEXT NOT NULL DEFAULT 'À demander',
            delai DATE,
            secteur_id INTEGER REFERENCES secteurs(id),
            chantier_id INTEGER REFERENCES chantiers(id),
            commentaire TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id SERIAL PRIMARY KEY,
            titre TEXT NOT NULL,
            description TEXT,
            date_tache DATE NOT NULL,
            date_fin DATE,
            heure_tache TIME,
            couleur TEXT NOT NULL DEFAULT '#2563eb',
            repetition TEXT NOT NULL DEFAULT 'aucune',
            occurrence_suivante_creee BOOLEAN NOT NULL DEFAULT FALSE,
            secteur_id INTEGER REFERENCES secteurs(id),
            demande_par TEXT,
            solde BOOLEAN NOT NULL DEFAULT FALSE,
            solde_par TEXT,
            date_solde TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def create_sqlite_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS secteurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            actif INTEGER NOT NULL DEFAULT 1
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
            nom_fichier TEXT,
            url_photo TEXT,
            public_id TEXT,
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS techniciens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            secteur_id INTEGER NOT NULL,
            actif INTEGER NOT NULL DEFAULT 1,
            UNIQUE (nom, secteur_id),
            FOREIGN KEY (secteur_id) REFERENCES secteurs(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courbes_edf (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            annee INTEGER NOT NULL,
            mois INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            donnees_xml BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (annee, mois)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chantiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            actif INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_commande DATE NOT NULL DEFAULT CURRENT_DATE,
            piece TEXT NOT NULL,
            quantite TEXT NOT NULL DEFAULT '1',
            reference TEXT,
            etat TEXT NOT NULL DEFAULT 'À demander',
            delai DATE,
            secteur_id INTEGER,
            chantier_id INTEGER,
            commentaire TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (secteur_id) REFERENCES secteurs(id),
            FOREIGN KEY (chantier_id) REFERENCES chantiers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            description TEXT,
            date_tache DATE NOT NULL,
            date_fin DATE,
            heure_tache TEXT,
            couleur TEXT NOT NULL DEFAULT '#2563eb',
            repetition TEXT NOT NULL DEFAULT 'aucune',
            occurrence_suivante_creee INTEGER NOT NULL DEFAULT 0,
            secteur_id INTEGER,
            demande_par TEXT,
            solde INTEGER NOT NULL DEFAULT 0,
            solde_par TEXT,
            date_solde TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (secteur_id) REFERENCES secteurs(id)
        )
    """)


def migrate_secteurs_table(conn):
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            ALTER TABLE secteurs
            ADD COLUMN IF NOT EXISTS actif BOOLEAN NOT NULL DEFAULT TRUE
        """)
    else:
        columns = cursor.execute("PRAGMA table_info(secteurs)").fetchall()
        column_names = [column[1] for column in columns]

        if "actif" not in column_names:
            cursor.execute("""
                ALTER TABLE secteurs
                ADD COLUMN actif INTEGER NOT NULL DEFAULT 1
            """)


def migrate_photos_table(conn):
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("ALTER TABLE photos ADD COLUMN IF NOT EXISTS url_photo TEXT")
        cursor.execute("ALTER TABLE photos ADD COLUMN IF NOT EXISTS public_id TEXT")
        cursor.execute("ALTER TABLE photos ALTER COLUMN nom_fichier DROP NOT NULL")
    else:
        columns = cursor.execute("PRAGMA table_info(photos)").fetchall()
        column_names = [column[1] for column in columns]

        if "url_photo" not in column_names:
            cursor.execute("ALTER TABLE photos ADD COLUMN url_photo TEXT")

        if "public_id" not in column_names:
            cursor.execute("ALTER TABLE photos ADD COLUMN public_id TEXT")


def migrate_agenda_table(conn):
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            ALTER TABLE agenda
            ADD COLUMN IF NOT EXISTS secteur_id INTEGER REFERENCES secteurs(id)
        """)
        cursor.execute("ALTER TABLE agenda ADD COLUMN IF NOT EXISTS demande_par TEXT")
        cursor.execute("ALTER TABLE agenda ADD COLUMN IF NOT EXISTS solde_par TEXT")
        cursor.execute("ALTER TABLE agenda ADD COLUMN IF NOT EXISTS date_solde TIMESTAMP")
        cursor.execute("ALTER TABLE agenda ADD COLUMN IF NOT EXISTS date_fin DATE")
        cursor.execute("ALTER TABLE agenda ADD COLUMN IF NOT EXISTS heure_tache TIME")
        cursor.execute("""
            ALTER TABLE agenda
            ADD COLUMN IF NOT EXISTS couleur TEXT NOT NULL DEFAULT '#2563eb'
        """)
        cursor.execute("""
            ALTER TABLE agenda
            ADD COLUMN IF NOT EXISTS repetition TEXT NOT NULL DEFAULT 'aucune'
        """)
        cursor.execute("""
            ALTER TABLE agenda
            ADD COLUMN IF NOT EXISTS occurrence_suivante_creee BOOLEAN
            NOT NULL DEFAULT FALSE
        """)
        cursor.execute("""
            UPDATE agenda
            SET couleur = '#2563eb'
            WHERE couleur IS NULL OR couleur = ''
        """)
        cursor.execute("""
            UPDATE agenda
            SET repetition = 'aucune'
            WHERE repetition IS NULL OR repetition = ''
        """)
    else:
        columns = cursor.execute("PRAGMA table_info(agenda)").fetchall()
        column_names = [column[1] for column in columns]

        migrations = {
            "secteur_id": "ALTER TABLE agenda ADD COLUMN secteur_id INTEGER REFERENCES secteurs(id)",
            "demande_par": "ALTER TABLE agenda ADD COLUMN demande_par TEXT",
            "solde_par": "ALTER TABLE agenda ADD COLUMN solde_par TEXT",
            "date_solde": "ALTER TABLE agenda ADD COLUMN date_solde TIMESTAMP",
            "date_fin": "ALTER TABLE agenda ADD COLUMN date_fin DATE",
            "heure_tache": "ALTER TABLE agenda ADD COLUMN heure_tache TEXT",
            "couleur": "ALTER TABLE agenda ADD COLUMN couleur TEXT NOT NULL DEFAULT '#2563eb'",
            "repetition": "ALTER TABLE agenda ADD COLUMN repetition TEXT NOT NULL DEFAULT 'aucune'",
            "occurrence_suivante_creee": "ALTER TABLE agenda ADD COLUMN occurrence_suivante_creee INTEGER NOT NULL DEFAULT 0"
        }

        for column_name, sql in migrations.items():
            if column_name not in column_names:
                cursor.execute(sql)

        cursor.execute("""
            UPDATE agenda
            SET couleur = '#2563eb'
            WHERE couleur IS NULL OR couleur = ''
        """)
        cursor.execute("""
            UPDATE agenda
            SET repetition = 'aucune'
            WHERE repetition IS NULL OR repetition = ''
        """)


def migrate_commandes_chantiers_table(conn):
    """Ajoute chantier_id aux anciennes bases sans supprimer les commandes existantes."""
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute("""
            ALTER TABLE commandes
            ADD COLUMN IF NOT EXISTS chantier_id INTEGER REFERENCES chantiers(id)
        """)
    else:
        columns = cursor.execute("PRAGMA table_info(commandes)").fetchall()
        column_names = [row[1] for row in columns]
        if "chantier_id" not in column_names:
            cursor.execute("ALTER TABLE commandes ADD COLUMN chantier_id INTEGER REFERENCES chantiers(id)")


def init_db():
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        if is_postgres():
            create_postgres_tables(cursor)
        else:
            create_sqlite_tables(cursor)

        migrate_photos_table(conn)
        migrate_secteurs_table(conn)
        migrate_agenda_table(conn)
        migrate_commandes_chantiers_table(conn)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()