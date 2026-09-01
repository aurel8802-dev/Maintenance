from datetime import datetime
from io import BytesIO

from openpyxl import Workbook

from database import get_db_connection


EXCEL_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


def recuperer_demandes(conn):
    return conn.execute("""
        SELECT
            demandes_intervention.*,
            secteurs.nom AS secteur_nom,
            demandeurs.nom AS demandeur_nom
        FROM demandes_intervention
        LEFT JOIN secteurs
            ON demandes_intervention.secteur_id = secteurs.id
        LEFT JOIN demandeurs
            ON demandes_intervention.demandeur_id = demandeurs.id
        ORDER BY demandes_intervention.date_creation DESC
    """).fetchall()


def recuperer_rapports(conn):
    return conn.execute("""
        SELECT
            rapports_intervention.*,
            secteurs.nom AS secteur_nom
        FROM rapports_intervention
        LEFT JOIN secteurs
            ON rapports_intervention.secteur_id = secteurs.id
        ORDER BY rapports_intervention.date_rapport DESC
    """).fetchall()


def ajouter_feuille_demandes(classeur, demandes):
    feuille = classeur.active
    feuille.title = "Demandes"

    feuille.append([
        "Horodateur",
        "Secteur",
        "Demandeur",
        "Nature des travaux",
        "Description de la demande",
        "Photo",
        "Soldé",
        "Soldé le",
        "Qui",
        "Référence pièce remplacée",
        "Commentaire",
    ])

    for demande in demandes:
        feuille.append([
            demande["date_creation"] or "",
            demande["secteur_nom"] or "",
            demande["demandeur_nom"] or "",
            demande["nature_travaux"] or "",
            demande["description"] or "",
            "",
            "oui" if demande["statut"] == "Soldé" else "",
            demande["date_solde"] or "",
            demande["solde_par"] or "",
            demande["reference_piece"] or "",
            demande["commentaire_solde"] or "",
        ])


def ajouter_feuille_rapports(classeur, rapports):
    feuille = classeur.create_sheet(
        "Rapport dintervention"
    )

    feuille.append([
        "Date",
        "Secteur",
        "Machine",
        "Problème",
        "Travaux",
        "Nom",
        "Réference pièce",
        "Commentaires",
    ])

    for rapport in rapports:
        feuille.append([
            rapport["date_rapport"] or "",
            rapport["secteur_nom"] or "",
            rapport["machine"] or "",
            rapport["probleme"] or "",
            rapport["travaux"] or "",
            rapport["technicien"] or "",
            rapport["reference"] or "",
            rapport["commentaire"] or "",
        ])


def generer_export_excel():
    conn = get_db_connection()

    try:
        demandes = recuperer_demandes(conn)
        rapports = recuperer_rapports(conn)
    finally:
        conn.close()

    classeur = Workbook()

    ajouter_feuille_demandes(classeur, demandes)
    ajouter_feuille_rapports(classeur, rapports)

    fichier = BytesIO()
    classeur.save(fichier)
    fichier.seek(0)

    nom_fichier = (
        "export_maintenance_"
        f"{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    )

    return fichier, nom_fichier