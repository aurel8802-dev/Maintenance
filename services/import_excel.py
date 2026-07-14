import os

import pandas as pd

from database import get_db_connection


SOLDE_VALUES = {
    "oui",
    "yes",
    "true",
    "vrai",
    "1",
    "x",
    "soldé",
    "solde",
    "soldée",
    "soldée.",
}


SECTEUR_CORRESPONDANCES = {
    "axame": "Axame",
    "batiments": "Bâtiments",
    "bâtiments": "Bâtiments",
    "extérieur": "Extérieur",
    "exterieur": "Extérieur",
    "hall 1": "Hall 1",
    "hall1": "Hall 1",
    "hall 2": "Hall 2",
    "hall2": "Hall 2",
    "mag auto": "Mag Auto",
    "maintenance": "Maintenance",
    "pont n°2": "Pont n°2",
    "pont n 2": "Pont n°2",
    "pont n2": "Pont n°2",
    "poste ht": "Poste HT",
    "pourfendeuse": "Pourfendeuse",
    "refendeuse": "Pourfendeuse",
    "réseau eau": "Réseau Eau",
    "reseau eau": "Réseau Eau",
    "réseau d'eau": "Réseau Eau",
    "reseau d'eau": "Réseau Eau",
    "tuberie": "Tuberie",
    "v2": "V2",
    "v 2": "V2",
    "v3": "V3",
    "v 3": "V3",
    "v2-v3": "V2-V3",
    "v2 - v3": "V2-V3",
    "v2 / v3": "V2-V3",
    "v6": "V6",
    "v 6": "V6",
}


def clean(value):
    """Transforme une valeur Excel vide en chaîne vide."""
    if pd.isna(value):
        return ""

    return str(value).strip()


def to_date(value):
    """Convertit une date Excel en date ISO compatible avec les deux bases."""
    if pd.isna(value) or value == "":
        return None

    try:
        return pd.to_datetime(value).isoformat(timespec="seconds")
    except (ValueError, TypeError):
        return None


def normaliser_secteur(nom):
    """Uniformise l’écriture d’un secteur."""
    nom = clean(nom)

    if not nom:
        return None

    return SECTEUR_CORRESPONDANCES.get(
        nom.lower(),
        nom
    )


def get_or_create_secteur(conn, nom):
    """Retourne l’identifiant du secteur ou le crée s’il n’existe pas."""
    nom_normalise = normaliser_secteur(nom)

    if not nom_normalise:
        return None

    secteur = conn.execute("""
        SELECT id
        FROM secteurs
        WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
        LIMIT 1
    """, (nom_normalise,)).fetchone()

    if secteur:
        return secteur["id"]

    cursor = conn.execute("""
        INSERT INTO secteurs (nom)
        VALUES (?)
    """, (nom_normalise,))

    return cursor.lastrowid


def get_or_create_demandeur(conn, nom, secteur_id):
    """Retourne l’identifiant du demandeur ou le crée."""
    nom = clean(nom)

    if not nom:
        nom = "Non renseigné"

    demandeur = conn.execute("""
        SELECT id
        FROM demandeurs
        WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
        LIMIT 1
    """, (nom,)).fetchone()

    if demandeur:
        return demandeur["id"]

    cursor = conn.execute("""
        INSERT INTO demandeurs (nom, secteur_id)
        VALUES (?, ?)
    """, (
        nom,
        secteur_id
    ))

    return cursor.lastrowid


def est_demande_soldee(value):
    """Détermine si une valeur Excel correspond à une demande soldée."""
    if value is True:
        return True

    return clean(value).lower() in SOLDE_VALUES


def charger_feuille_demandes(excel):
    """Trouve automatiquement la feuille contenant les demandes."""
    if "Demandes" in excel.sheet_names:
        dataframe = pd.read_excel(
            excel,
            sheet_name="Demandes"
        )
    elif "Travaux" in excel.sheet_names:
        dataframe = pd.read_excel(
            excel,
            sheet_name="Travaux"
        )
    else:
        dataframe = pd.read_excel(
            excel,
            sheet_name=0
        )

    dataframe.columns = dataframe.columns.astype(str).str.strip()

    return dataframe


def charger_feuille_rapports(excel):
    """Trouve la feuille de rapports et détecte un en-tête décalé."""
    if "Rapport dintervention" in excel.sheet_names:
        dataframe = pd.read_excel(
            excel,
            sheet_name="Rapport dintervention"
        )

        dataframe.columns = dataframe.columns.astype(str).str.strip()

        if "Machine" not in dataframe.columns:
            dataframe = pd.read_excel(
                excel,
                sheet_name="Rapport dintervention",
                header=1
            )

            dataframe.columns = dataframe.columns.astype(str).str.strip()

        return dataframe

    if "Rapports" in excel.sheet_names:
        dataframe = pd.read_excel(
            excel,
            sheet_name="Rapports"
        )

        dataframe.columns = dataframe.columns.astype(str).str.strip()

        return dataframe

    return None


def vider_donnees_existantes(conn, photos_dir):
    """Vide les données avant un import en mode remplacement."""
    conn.execute("DELETE FROM photos")
    conn.execute("DELETE FROM demandes_intervention")
    conn.execute("DELETE FROM rapports_intervention")
    conn.execute("DELETE FROM demandeurs")

    if os.path.isdir(photos_dir):
        for filename in os.listdir(photos_dir):
            file_path = os.path.join(
                photos_dir,
                filename
            )

            if os.path.isfile(file_path):
                os.remove(file_path)


def importer_demandes(conn, dataframe):
    """Importe toutes les demandes présentes dans le tableau."""
    compteur = 0

    for _, row in dataframe.iterrows():
        nature_travaux = clean(
            row.get(
                "Nature des travaux",
                row.get(
                    "Objet",
                    row.get("Travaux", "")
                )
            )
        )

        description = clean(
            row.get(
                "Description de la demande",
                row.get("Description", "")
            )
        )

        # Ignore les lignes totalement vides.
        if not nature_travaux and not description:
            continue

        secteur_id = get_or_create_secteur(
            conn,
            row.get("Secteur", "")
        )

        demandeur_id = get_or_create_demandeur(
            conn,
            row.get("Demandeur", ""),
            secteur_id
        )

        statut = (
            "Soldé"
            if est_demande_soldee(row.get("Soldé", ""))
            else "En cours"
        )

        conn.execute("""
            INSERT INTO demandes_intervention (
                secteur_id,
                demandeur_id,
                nature_travaux,
                description,
                statut,
                date_creation,
                date_solde,
                solde_par,
                reference_piece,
                commentaire_solde
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            secteur_id,
            demandeur_id,
            nature_travaux,
            description,
            statut,
            to_date(
                row.get(
                    "Date",
                    row.get("Horodateur", "")
                )
            ),
            to_date(row.get("Soldé le", "")),
            clean(
                row.get(
                    "Qui",
                    row.get("Soldé par", "")
                )
            ),
            clean(
                row.get(
                    "Référence pièce remplacée",
                    ""
                )
            ),
            clean(row.get("Commentaire", ""))
        ))

        compteur += 1

    return compteur


def importer_rapports(conn, dataframe):
    """Importe les rapports présents dans le tableau."""
    if dataframe is None:
        return 0

    compteur = 0

    for _, row in dataframe.iterrows():
        machine = clean(row.get("Machine", ""))
        probleme = clean(row.get("Problème", ""))
        travaux = clean(row.get("Travaux", ""))

        # Ignore les lignes vides.
        if not machine and not probleme and not travaux:
            continue

        secteur_id = get_or_create_secteur(
            conn,
            row.get("Secteur", "")
        )

        technicien = clean(
            row.get(
                "Nom",
                row.get("Technicien", "")
            )
        )

        reference = clean(
            row.get(
                "Réference pièce",
                row.get("Référence", "")
            )
        )

        commentaire = clean(
            row.get(
                "Commentaires",
                row.get("Commentaire", "")
            )
        )

        conn.execute("""
            INSERT INTO rapports_intervention (
                secteur_id,
                machine,
                probleme,
                travaux,
                technicien,
                commentaire,
                reference,
                date_rapport
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            secteur_id,
            machine,
            probleme,
            travaux,
            technicien,
            commentaire,
            reference,
            to_date(
                row.get(
                    "Date",
                    row.get("Horodateur", "")
                )
            )
        ))

        compteur += 1

    return compteur


def importer_fichier_excel(
    fichier,
    mode_import,
    photos_dir
):
    """
    Importe un fichier Excel complet.

    Retourne :
        {
            "demandes": nombre,
            "rapports": nombre
        }
    """
    excel = pd.ExcelFile(fichier)
    conn = get_db_connection()

    try:
        if mode_import == "remplacer":
            vider_donnees_existantes(
                conn,
                photos_dir
            )

        df_demandes = charger_feuille_demandes(excel)
        df_rapports = charger_feuille_rapports(excel)

        demandes_importees = importer_demandes(
            conn,
            df_demandes
        )

        rapports_importes = importer_rapports(
            conn,
            df_rapports
        )

        conn.commit()

        return {
            "demandes": demandes_importees,
            "rapports": rapports_importes,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()