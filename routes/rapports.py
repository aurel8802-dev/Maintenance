import os
from flask import Blueprint, render_template, request, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from database import get_db_connection

rapports_bp = Blueprint("rapports", __name__)


@rapports_bp.route("/rapports/nouveau", methods=["GET", "POST"])
def nouveau_rapport():
    conn = get_db_connection()

    secteurs = conn.execute("""
        SELECT * FROM secteurs
        ORDER BY nom
    """).fetchall()

    if request.method == "POST":
        secteur_id = request.form["secteur_id"]
        machine = request.form["machine"]
        probleme = request.form["probleme"]
        travaux = request.form["travaux"]
        technicien = request.form["technicien"]
        commentaire = request.form["commentaire"]
        reference = request.form["reference"]

        cursor = conn.execute("""
            INSERT INTO rapports_intervention
            (secteur_id, machine, probleme, travaux, technicien, commentaire, reference)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            secteur_id,
            machine,
            probleme,
            travaux,
            technicien,
            commentaire,
            reference
        ))

        rapport_id = cursor.lastrowid

        photo = request.files.get("photo")

        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            photo.save(photo_path)

            conn.execute("""
                INSERT INTO photos (type_element, element_id, nom_fichier)
                VALUES (?, ?, ?)
            """, ("rapport", rapport_id, filename))

        conn.commit()
        conn.close()

        return redirect(url_for("rapports.liste_rapports"))

    conn.close()
    return render_template("rapports/nouveau.html", secteurs=secteurs)


@rapports_bp.route("/rapports")
def liste_rapports():
    recherche = request.args.get("recherche", "").strip()
    secteur_id = request.args.get("secteur_id", "").strip()
    tri = request.args.get("tri", "recent").strip()

    conn = get_db_connection()

    query = """
        SELECT rapports_intervention.*,
               secteurs.nom AS secteur_nom
        FROM rapports_intervention
        LEFT JOIN secteurs ON rapports_intervention.secteur_id = secteurs.id
        WHERE 1=1
    """

    params = []

    if recherche:
        query += """
            AND (
                rapports_intervention.machine LIKE ?
                OR rapports_intervention.probleme LIKE ?
                OR rapports_intervention.travaux LIKE ?
                OR rapports_intervention.technicien LIKE ?
                OR rapports_intervention.commentaire LIKE ?
                OR rapports_intervention.reference LIKE ?
                OR secteurs.nom LIKE ?
            )
        """
        recherche_sql = f"%{recherche}%"
        params.extend([recherche_sql] * 7)

    if secteur_id:
        query += " AND rapports_intervention.secteur_id = ?"
        params.append(secteur_id)

    if tri == "ancien":
        query += " ORDER BY rapports_intervention.date_rapport ASC"
    elif tri == "secteur":
        query += " ORDER BY secteurs.nom ASC"
    elif tri == "technicien":
        query += " ORDER BY rapports_intervention.technicien ASC"
    else:
        query += " ORDER BY rapports_intervention.date_rapport DESC"

    rapports = conn.execute(query, params).fetchall()

    secteurs = conn.execute("""
        SELECT * FROM secteurs
        ORDER BY nom
    """).fetchall()

    conn.close()

    return render_template(
        "rapports/liste.html",
        rapports=rapports,
        secteurs=secteurs,
        recherche=recherche,
        secteur_id=secteur_id,
        tri=tri
    )

@rapports_bp.route("/rapports/<int:rapport_id>")
def detail_rapport(rapport_id):

    conn = get_db_connection()

    rapport = conn.execute("""
        SELECT rapports_intervention.*,
               secteurs.nom AS secteur_nom
        FROM rapports_intervention
        LEFT JOIN secteurs
        ON rapports_intervention.secteur_id = secteurs.id
        WHERE rapports_intervention.id = ?
    """, (rapport_id,)).fetchone()

    if rapport is None:
        conn.close()
        return "Rapport introuvable", 404

    photos = conn.execute("""
        SELECT *
        FROM photos
        WHERE type_element='rapport'
        AND element_id=?
    """, (rapport_id,)).fetchall()

    conn.close()

    return render_template(
        "rapports/detail.html",
        rapport=rapport,
        photos=photos
    )

@rapports_bp.route("/rapports/<int:rapport_id>/modifier", methods=["GET", "POST"])
def modifier_rapport(rapport_id):
    conn = get_db_connection()

    rapport = conn.execute("""
        SELECT * FROM rapports_intervention
        WHERE id = ?
    """, (rapport_id,)).fetchone()

    if rapport is None:
        conn.close()
        return "Rapport introuvable", 404

    secteurs = conn.execute("""
        SELECT * FROM secteurs
        ORDER BY nom
    """).fetchall()

    if request.method == "POST":
        secteur_id = request.form["secteur_id"]
        machine = request.form["machine"]
        probleme = request.form["probleme"]
        travaux = request.form["travaux"]
        technicien = request.form["technicien"]
        commentaire = request.form["commentaire"]
        reference = request.form["reference"]

        conn.execute("""
            UPDATE rapports_intervention
            SET secteur_id = ?,
                machine = ?,
                probleme = ?,
                travaux = ?,
                technicien = ?,
                commentaire = ?,
                reference = ?
            WHERE id = ?
        """, (
            secteur_id,
            machine,
            probleme,
            travaux,
            technicien,
            commentaire,
            reference,
            rapport_id
        ))

        photo = request.files.get("photo")

        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            photo.save(photo_path)

            conn.execute("""
                INSERT INTO photos (type_element, element_id, nom_fichier)
                VALUES (?, ?, ?)
            """, ("rapport", rapport_id, filename))

        conn.commit()
        conn.close()

        return redirect(url_for("rapports.detail_rapport", rapport_id=rapport_id))

    conn.close()

    return render_template(
        "rapports/modifier.html",
        rapport=rapport,
        secteurs=secteurs
    )

@rapports_bp.route("/rapports/<int:rapport_id>/supprimer", methods=["POST"])
def supprimer_rapport(rapport_id):
    conn = get_db_connection()

    # Récupération de la photo associée
    photo = conn.execute("""
        SELECT nom_fichier
        FROM photos
        WHERE type_element = 'rapport'
        AND element_id = ?
    """, (rapport_id,)).fetchone()

    # Suppression du fichier photo
    if photo:
        chemin = os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            photo["nom_fichier"]
        )

        if os.path.exists(chemin):
            os.remove(chemin)

    # Suppression de la référence photo
    conn.execute("""
        DELETE FROM photos
        WHERE type_element = 'rapport'
        AND element_id = ?
    """, (rapport_id,))

    # Suppression du rapport
    conn.execute("""
        DELETE FROM rapports_intervention
        WHERE id = ?
    """, (rapport_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("rapports.liste_rapports"))