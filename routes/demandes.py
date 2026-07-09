from flask import Blueprint, render_template, request, redirect, url_for, current_app
from database import get_db_connection
import os
from werkzeug.utils import secure_filename
from datetime import datetime

demandes_bp = Blueprint("demandes", __name__)


def get_or_create_demandeur(conn, nom, secteur_id):
    nom = nom.strip()

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


@demandes_bp.route("/demandes/nouvelle", methods=["GET", "POST"])
def nouvelle_demande():
    if request.method == "POST":
        secteur_id = request.form["secteur_id"]
        demandeur_nom = request.form["demandeur"]
        nature_travaux = request.form["nature_travaux"]
        description = request.form["description"]

        conn = get_db_connection()

        demandeur_id = get_or_create_demandeur(conn, demandeur_nom, secteur_id)

        cursor = conn.execute("""
            INSERT INTO demandes_intervention
            (secteur_id, demandeur_id, nature_travaux, description, statut)
            VALUES (?, ?, ?, ?, ?)
        """, (
            secteur_id,
            demandeur_id,
            nature_travaux,
            description,
            "En cours"
        ))

        demande_id = cursor.lastrowid
        photo = request.files.get("photo")

        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            photo.save(photo_path)

            conn.execute("""
                INSERT INTO photos (type_element, element_id, nom_fichier)
                VALUES (?, ?, ?)
            """, ("demande", demande_id, filename))

        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    conn = get_db_connection()
    secteurs = conn.execute("""
        SELECT * FROM secteurs
        ORDER BY nom
    """).fetchall()
    conn.close()

    return render_template("demandes/nouvelle.html", secteurs=secteurs)

@demandes_bp.route("/demandes")
def liste_demandes():
    recherche = request.args.get("recherche", "").strip()
    secteur_id = request.args.get("secteur_id", "").strip()
    statut = request.args.get("statut", "").strip()
    tri = request.args.get("tri", "recent").strip()

    conn = get_db_connection()

    query = """
        SELECT demandes_intervention.*,
               demandeurs.nom AS demandeur_nom,
               secteurs.nom AS secteur_nom
        FROM demandes_intervention
        LEFT JOIN demandeurs ON demandes_intervention.demandeur_id = demandeurs.id
        LEFT JOIN secteurs ON demandes_intervention.secteur_id = secteurs.id
        WHERE 1=1
    """

    params = []

    if recherche:
        query += """
            AND (
                demandes_intervention.nature_travaux LIKE ?
                OR demandes_intervention.description LIKE ?
                OR demandeurs.nom LIKE ?
                OR secteurs.nom LIKE ?
            )
        """
        recherche_sql = f"%{recherche}%"
        params.extend([recherche_sql, recherche_sql, recherche_sql, recherche_sql])

    if secteur_id:
        query += " AND demandes_intervention.secteur_id = ?"
        params.append(secteur_id)

    if statut:
        query += " AND demandes_intervention.statut = ?"
        params.append(statut)

    if tri == "ancien":
        query += " ORDER BY demandes_intervention.date_creation ASC"
    elif tri == "secteur":
        query += " ORDER BY secteurs.nom ASC"
    elif tri == "statut":
        query += " ORDER BY demandes_intervention.statut ASC"
    else:
        query += " ORDER BY demandes_intervention.date_creation DESC"

    demandes = conn.execute(query, params).fetchall()

    secteurs = conn.execute("""
        SELECT * FROM secteurs
        ORDER BY nom
    """).fetchall()

    conn.close()

    return render_template(
        "demandes/liste.html",
        demandes=demandes,
        recherche=recherche,
        secteurs=secteurs,
        secteur_id=secteur_id,
        statut=statut,
        tri=tri
    )

@demandes_bp.route("/demandes/<int:demande_id>")
def detail_demande(demande_id):
    conn = get_db_connection()

    demande = conn.execute("""
        SELECT demandes_intervention.*,
               demandeurs.nom AS demandeur_nom,
               secteurs.nom AS secteur_nom
        FROM demandes_intervention
        LEFT JOIN demandeurs ON demandes_intervention.demandeur_id = demandeurs.id
        LEFT JOIN secteurs ON demandes_intervention.secteur_id = secteurs.id
        WHERE demandes_intervention.id = ?
    """, (demande_id,)).fetchone()

    photos = conn.execute("""
        SELECT * FROM photos
        WHERE type_element = ? AND element_id = ?
        ORDER BY date_ajout DESC
    """, ("demande", demande_id)).fetchall()

    conn.close()

    if demande is None:
        return "Demande introuvable", 404

    return render_template(
    "demandes/detail.html",
    demande=demande,
    photos=photos
)

@demandes_bp.route("/demandes/<int:demande_id>/modifier", methods=["GET", "POST"])
def modifier_demande(demande_id):
    conn = get_db_connection()

    demande = conn.execute("""
        SELECT * FROM demandes_intervention
        WHERE id = ?
    """, (demande_id,)).fetchone()

    if demande is None:
        conn.close()
        return "Demande introuvable", 404

    secteurs = conn.execute("""
        SELECT * FROM secteurs
        ORDER BY nom
    """).fetchall()

    if request.method == "POST":
        secteur_id = request.form["secteur_id"]
        demandeur_nom = request.form["demandeur"]
        nature_travaux = request.form["nature_travaux"]
        description = request.form["description"]

        demandeur_id = get_or_create_demandeur(conn, demandeur_nom, secteur_id)

        conn.execute("""
            UPDATE demandes_intervention
            SET secteur_id = ?,
                demandeur_id = ?,
                nature_travaux = ?,
                description = ?
            WHERE id = ?
        """, (
            secteur_id,
            demandeur_id,
            nature_travaux,
            description,
            demande_id
        ))

        photo = request.files.get("photo")

        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            photo.save(photo_path)

            conn.execute("""
        INSERT INTO photos (type_element, element_id, nom_fichier)
        VALUES (?, ?, ?)
    """, ("demande", demande_id, filename))

        conn.commit()
        conn.close()

        return redirect(url_for("demandes.detail_demande", demande_id=demande_id))

    demandeur = conn.execute("""
        SELECT nom FROM demandeurs
        WHERE id = ?
    """, (demande["demandeur_id"],)).fetchone()

    conn.close()

    return render_template(
        "demandes/modifier.html",
        demande=demande,
        demandeur=demandeur,
        secteurs=secteurs
    )

@demandes_bp.route("/demandes/<int:demande_id>/supprimer", methods=["GET", "POST"])
def supprimer_demande(demande_id):
    conn = get_db_connection()

    demande = conn.execute("""
        SELECT demandes_intervention.*,
               demandeurs.nom AS demandeur_nom,
               secteurs.nom AS secteur_nom
        FROM demandes_intervention
        LEFT JOIN demandeurs ON demandes_intervention.demandeur_id = demandeurs.id
        LEFT JOIN secteurs ON demandes_intervention.secteur_id = secteurs.id
        WHERE demandes_intervention.id = ?
    """, (demande_id,)).fetchone()

    if demande is None:
        conn.close()
        return "Demande introuvable", 404

    if request.method == "POST":
        conn.execute("""
            DELETE FROM demandes_intervention
            WHERE id = ?
        """, (demande_id,))

        conn.commit()
        conn.close()

        return redirect(url_for("demandes.liste_demandes"))

    conn.close()

    return render_template("demandes/supprimer.html", demande=demande)

@demandes_bp.route("/demandes/<int:demande_id>/solder", methods=["GET", "POST"])
def solder_demande(demande_id):
    conn = get_db_connection()

    demande = conn.execute("""
        SELECT demandes_intervention.*,
               demandeurs.nom AS demandeur_nom,
               secteurs.nom AS secteur_nom
        FROM demandes_intervention
        LEFT JOIN demandeurs ON demandes_intervention.demandeur_id = demandeurs.id
        LEFT JOIN secteurs ON demandes_intervention.secteur_id = secteurs.id
        WHERE demandes_intervention.id = ?
    """, (demande_id,)).fetchone()

    if demande is None:
        conn.close()
        return "Demande introuvable", 404

    if request.method == "POST":
        solde_par = request.form["solde_par"]
        reference_piece = request.form["reference_piece"]
        commentaire_solde = request.form["commentaire_solde"]

        conn.execute("""
            UPDATE demandes_intervention
            SET statut = ?,
                date_solde = ?,
                solde_par = ?,
                reference_piece = ?,
                commentaire_solde = ?
            WHERE id = ?
        """, (
            "Soldé",
            datetime.now().isoformat(timespec="seconds"),
            solde_par,
            reference_piece,
            commentaire_solde,
            demande_id
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("demandes.detail_demande", demande_id=demande_id))

    conn.close()

    return render_template("demandes/solder.html", demande=demande)