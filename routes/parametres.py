import os
from flask import Blueprint, render_template, request, redirect, url_for

from config import ADMIN_RESET_CODE
from database import get_db_connection
import pandas as pd
from flask import send_file
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime

parametres_bp = Blueprint("parametres", __name__)


@parametres_bp.route("/parametres")
def parametres():
    return render_template("parametres/index.html")


@parametres_bp.route("/parametres/reset", methods=["GET", "POST"])
def reset_donnees():
    message = None
    erreur = None

    if request.method == "POST":
        code = request.form.get("code", "")

        if code != ADMIN_RESET_CODE:
            erreur = "Code incorrect."
        else:
            conn = get_db_connection()

            conn.execute("DELETE FROM photos")
            conn.execute("DELETE FROM demandes_intervention")
            conn.execute("DELETE FROM rapports_intervention")
            conn.execute("DELETE FROM demandeurs")

            conn.commit()
            conn.close()

            photos_dir = os.path.join(os.getcwd(), "uploads", "photos")

            if os.path.exists(photos_dir):
                for filename in os.listdir(photos_dir):
                    file_path = os.path.join(photos_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

            message = "Toutes les données ont été supprimées."

    return render_template(
        "parametres/reset.html",
        message=message,
        erreur=erreur
    )

@parametres_bp.route("/parametres/secteurs", methods=["GET", "POST"])
def gerer_secteurs():
    message = None
    erreur = None
    conn = get_db_connection()

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()

        if not nom:
            erreur = "Le nom du secteur est obligatoire."
        else:
            try:
                conn.execute("INSERT INTO secteurs (nom) VALUES (?)", (nom,))
                conn.commit()
                message = "Secteur ajouté."
            except:
                erreur = "Ce secteur existe déjà."

    secteurs = conn.execute("SELECT * FROM secteurs ORDER BY nom").fetchall()
    conn.close()

    return render_template(
        "parametres/secteurs.html",
        secteurs=secteurs,
        message=message,
        erreur=erreur
    )

@parametres_bp.route("/parametres/secteurs/<int:secteur_id>/supprimer", methods=["POST"])
def supprimer_secteur(secteur_id):

    conn = get_db_connection()

    # Vérifie qu'aucune demande ou rapport n'utilise ce secteur
    demande = conn.execute(
        "SELECT id FROM demandes_intervention WHERE secteur_id=? LIMIT 1",
        (secteur_id,)
    ).fetchone()

    rapport = conn.execute(
        "SELECT id FROM rapports_intervention WHERE secteur_id=? LIMIT 1",
        (secteur_id,)
    ).fetchone()

    if demande or rapport:
        conn.close()
        return "Impossible de supprimer un secteur utilisé.", 400

    conn.execute(
        "DELETE FROM secteurs WHERE id=?",
        (secteur_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("parametres.gerer_secteurs"))

def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_date(value):
    if pd.isna(value) or value == "":
        return None
    try:
        return pd.to_datetime(value).isoformat(timespec="seconds")
    except:
        return None


def get_or_create_secteur(conn, nom):
    nom = clean(nom)
    if not nom:
        nom = "Non renseigné"

    secteur = conn.execute(
        "SELECT id FROM secteurs WHERE nom = ?",
        (nom,)
    ).fetchone()

    if secteur:
        return secteur["id"]

    cursor = conn.execute(
        "INSERT INTO secteurs (nom) VALUES (?)",
        (nom,)
    )
    return cursor.lastrowid


def get_or_create_demandeur(conn, nom, secteur_id):
    nom = clean(nom)
    if not nom:
        nom = "Non renseigné"

    demandeur = conn.execute(
        "SELECT id FROM demandeurs WHERE nom = ?",
        (nom,)
    ).fetchone()

    if demandeur:
        return demandeur["id"]

    cursor = conn.execute(
        "INSERT INTO demandeurs (nom, secteur_id) VALUES (?, ?)",
        (nom, secteur_id)
    )
    return cursor.lastrowid


@parametres_bp.route("/parametres/import", methods=["GET", "POST"])
def importer_donnees():
    message = None
    erreur = None

    if request.method == "POST":
        fichier = request.files.get("fichier")
        mode_import = request.form.get("mode_import", "ajouter")

        if not fichier or fichier.filename == "":
            erreur = "Aucun fichier sélectionné."
        else:
            try:
                excel = pd.ExcelFile(fichier)
                conn = get_db_connection()

                if mode_import == "remplacer":
                    conn.execute("DELETE FROM photos")
                    conn.execute("DELETE FROM demandes_intervention")
                    conn.execute("DELETE FROM rapports_intervention")
                    conn.execute("DELETE FROM demandeurs")

                    photos_dir = os.path.join(os.getcwd(), "uploads", "photos")
                    if os.path.exists(photos_dir):
                        for filename in os.listdir(photos_dir):
                            file_path = os.path.join(photos_dir, filename)
                            if os.path.isfile(file_path):
                                os.remove(file_path)

                demandes_importees = 0
                rapports_importes = 0

                # Demandes
                if "Demandes" in excel.sheet_names:
                    df_demandes = pd.read_excel(excel, sheet_name="Demandes")
                elif "Travaux" in excel.sheet_names:
                    df_demandes = pd.read_excel(excel, sheet_name="Travaux")
                else:
                    df_demandes = pd.read_excel(excel, sheet_name=0)

                df_demandes.columns = df_demandes.columns.str.strip()

                for _, row in df_demandes.iterrows():
                    secteur_id = get_or_create_secteur(conn, row.get("Secteur", ""))
                    demandeur_id = get_or_create_demandeur(conn, row.get("Demandeur", ""), secteur_id)

                    solded_raw = row.get("Soldé", "")

                    if solded_raw is True:
                        est_solde = True
                    else:
                        solded_value = clean(solded_raw).lower()
                        est_solde = solded_value in [
                            "oui",
                            "yes",
                            "true",
                            "vrai",
                            "1",
                            "x",
                            "soldé",
                            "solde",
                            "soldée",
                            "soldée."
                        ]
                    statut = "Soldé" if est_solde else "En cours"

                    conn.execute("""
                        INSERT INTO demandes_intervention
                        (
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
                        clean(row.get("Nature des travaux", row.get("Objet", row.get("Travaux", "")))),
                        clean(row.get("Description de la demande", row.get("Description", ""))),
                        statut,
                        to_date(row.get("Date", row.get("Horodateur", ""))),
                        to_date(row.get("Soldé le", "")),
                        clean(row.get("Qui", row.get("Soldé par", ""))),
                        clean(row.get("Référence pièce remplacée", "")),
                        clean(row.get("Commentaire", ""))
                    ))

                    demandes_importees += 1

                # Rapports compatible avec plusieurs formats
                if "Rapport dintervention" in excel.sheet_names:
                    df_rapports = pd.read_excel(excel, sheet_name="Rapport dintervention")
                    df_rapports.columns = df_rapports.columns.str.strip()

                    if "Machine" not in df_rapports.columns:
                        df_rapports = pd.read_excel(
                            excel,
                            sheet_name="Rapport dintervention",
                            header=1
                        )
                        df_rapports.columns = df_rapports.columns.str.strip()

                elif "Rapports" in excel.sheet_names:
                    df_rapports = pd.read_excel(excel, sheet_name="Rapports")
                    df_rapports.columns = df_rapports.columns.str.strip()

                else:
                    df_rapports = None

                if df_rapports is not None:
                    for _, row in df_rapports.iterrows():
                        machine = clean(row.get("Machine", ""))
                        probleme = clean(row.get("Problème", ""))
                        travaux = clean(row.get("Travaux", ""))

                        if not machine and not probleme and not travaux:
                            continue

                        secteur_id = get_or_create_secteur(conn, row.get("Secteur", ""))

                        technicien = clean(row.get("Nom", row.get("Technicien", "")))
                        reference = clean(row.get("Réference pièce", row.get("Référence", "")))
                        commentaire = clean(row.get("Commentaires", row.get("Commentaire", "")))

                        conn.execute("""
                            INSERT INTO rapports_intervention
                            (
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
                            to_date(row.get("Date", row.get("Horodateur", "")))
                        ))

                        rapports_importes += 1

                conn.commit()
                conn.close()

                message = (
                    f"✅ Import terminé !<br><br>"
                    f"📋 Demandes importées : <strong>{demandes_importees}</strong><br>"
                    f"📄 Rapports importés : <strong>{rapports_importes}</strong>"
                )

            except Exception as e:
                erreur = f"Erreur pendant l'import : {e}"

    return render_template(
        "parametres/import.html",
        message=message,
        erreur=erreur
    )

@parametres_bp.route("/parametres/export")
def exporter_donnees():
    conn = get_db_connection()

    wb = Workbook()

    # Feuille demandes
    ws = wb.active
    ws.title = "Demandes"

    ws.append([
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
        "Commentaire"
    ])

    demandes = conn.execute("""
        SELECT demandes_intervention.*,
               secteurs.nom AS secteur_nom,
               demandeurs.nom AS demandeur_nom
        FROM demandes_intervention
        LEFT JOIN secteurs ON demandes_intervention.secteur_id = secteurs.id
        LEFT JOIN demandeurs ON demandes_intervention.demandeur_id = demandeurs.id
        ORDER BY demandes_intervention.date_creation DESC
    """).fetchall()

    for d in demandes:
        ws.append([
            d["date_creation"] or "",
            d["secteur_nom"] or "",
            d["demandeur_nom"] or "",
            d["nature_travaux"] or "",
            d["description"] or "",
            "",
            "oui" if d["statut"] == "Soldé" else "",
            d["date_solde"] or "",
            d["solde_par"] or "",
            d["reference_piece"] or "",
            d["commentaire_solde"] or ""
        ])

    # Feuille rapports
    ws2 = wb.create_sheet("Rapport dintervention")

    ws2.append([
        "Date",
        "Secteur",
        "Machine",
        "Problème",
        "Travaux",
        "Nom",
        "Réference pièce",
        "Commentaires"
    ])

    rapports = conn.execute("""
        SELECT rapports_intervention.*,
               secteurs.nom AS secteur_nom
        FROM rapports_intervention
        LEFT JOIN secteurs ON rapports_intervention.secteur_id = secteurs.id
        ORDER BY rapports_intervention.date_rapport DESC
    """).fetchall()

    for r in rapports:
        ws2.append([
            r["date_rapport"] or "",
            r["secteur_nom"] or "",
            r["machine"] or "",
            r["probleme"] or "",
            r["travaux"] or "",
            r["technicien"] or "",
            r["reference"] or "",
            r["commentaire"] or ""
        ])

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"export_maintenance_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )