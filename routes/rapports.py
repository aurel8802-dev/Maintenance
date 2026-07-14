from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from services.database_service import (
    connexion_db,
    transaction_db,
)
from services.photo_service import (
    enregistrer_photo,
    recuperer_photos,
    supprimer_photos,
)


rapports_bp = Blueprint("rapports", __name__)


# -------------------------------------------------------------------
# Requêtes communes
# -------------------------------------------------------------------

RAPPORT_DETAIL_QUERY = """
    SELECT
        rapports_intervention.*,
        secteurs.nom AS secteur_nom
    FROM rapports_intervention
    LEFT JOIN secteurs
        ON rapports_intervention.secteur_id = secteurs.id
    WHERE rapports_intervention.id = ?
"""


def get_all_secteurs(conn):
    """Retourne les secteurs classés par ordre alphabétique."""
    return conn.execute("""
        SELECT *
        FROM secteurs
        ORDER BY nom
    """).fetchall()


def get_rapport(conn, rapport_id):
    """Récupère un rapport sans le nom du secteur."""
    return conn.execute("""
        SELECT *
        FROM rapports_intervention
        WHERE id = ?
    """, (rapport_id,)).fetchone()


def get_rapport_detail(conn, rapport_id):
    """Récupère un rapport avec le nom de son secteur."""
    return conn.execute(
        RAPPORT_DETAIL_QUERY,
        (rapport_id,)
    ).fetchone()


# -------------------------------------------------------------------
# Création d'un rapport
# -------------------------------------------------------------------

@rapports_bp.route(
    "/rapports/nouveau",
    methods=["GET", "POST"]
)
def nouveau_rapport():
    if request.method == "GET":
        with connexion_db() as conn:
            secteurs = get_all_secteurs(conn)

        return render_template(
            "rapports/nouveau.html",
            secteurs=secteurs
        )

    secteur_id = request.form.get("secteur_id", "").strip()
    machine = request.form.get("machine", "").strip()
    probleme = request.form.get("probleme", "").strip()
    travaux = request.form.get("travaux", "").strip()
    technicien = request.form.get("technicien", "").strip()
    commentaire = request.form.get("commentaire", "").strip()
    reference = request.form.get("reference", "").strip()

    if not all([
        secteur_id,
        machine,
        probleme,
        travaux,
        technicien
    ]):
        with connexion_db() as conn:
            secteurs = get_all_secteurs(conn)

        return (
            render_template(
                "rapports/nouveau.html",
                secteurs=secteurs,
                erreur=(
                    "Le secteur, la machine, le problème, "
                    "les travaux et le technicien sont obligatoires."
                )
            ),
            400
        )

    with transaction_db() as conn:
        cursor = conn.execute("""
            INSERT INTO rapports_intervention (
                secteur_id,
                machine,
                probleme,
                travaux,
                technicien,
                commentaire,
                reference
            )
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

        enregistrer_photo(
            conn,
            "rapport",
            rapport_id,
            request.files.get("photo")
        )

    return redirect(
        url_for(
            "rapports.detail_rapport",
            rapport_id=rapport_id
        )
    )


# -------------------------------------------------------------------
# Liste, recherche, filtres et tri
# -------------------------------------------------------------------

@rapports_bp.route("/rapports")
def liste_rapports():
    recherche = request.args.get("recherche", "").strip()
    secteur_id = request.args.get("secteur_id", "").strip()
    tri = request.args.get("tri", "recent").strip()

    query = """
        SELECT
            rapports_intervention.*,
            secteurs.nom AS secteur_nom
        FROM rapports_intervention
        LEFT JOIN secteurs
            ON rapports_intervention.secteur_id = secteurs.id
        WHERE 1 = 1
    """

    params = []

    if recherche:
        query += """
            AND (
                LOWER(rapports_intervention.machine) LIKE LOWER(?)
                OR LOWER(rapports_intervention.probleme) LIKE LOWER(?)
                OR LOWER(rapports_intervention.travaux) LIKE LOWER(?)
                OR LOWER(rapports_intervention.technicien) LIKE LOWER(?)
                OR LOWER(COALESCE(rapports_intervention.commentaire, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(rapports_intervention.reference, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(secteurs.nom, '')) LIKE LOWER(?)
            )
        """

        recherche_sql = f"%{recherche}%"
        params.extend([recherche_sql] * 7)

    if secteur_id:
        query += """
            AND rapports_intervention.secteur_id = ?
        """
        params.append(secteur_id)

    order_by_options = {
        "ancien": "rapports_intervention.date_rapport ASC",
        "secteur": "secteurs.nom ASC",
        "technicien": "rapports_intervention.technicien ASC",
        "recent": "rapports_intervention.date_rapport DESC",
    }

    order_by = order_by_options.get(
        tri,
        order_by_options["recent"]
    )

    query += f" ORDER BY {order_by}"

    with connexion_db() as conn:
        rapports = conn.execute(
            query,
            params
        ).fetchall()

        secteurs = get_all_secteurs(conn)

    return render_template(
        "rapports/liste.html",
        rapports=rapports,
        secteurs=secteurs,
        recherche=recherche,
        secteur_id=secteur_id,
        tri=tri
    )


# -------------------------------------------------------------------
# Détail d'un rapport
# -------------------------------------------------------------------

@rapports_bp.route("/rapports/<int:rapport_id>")
def detail_rapport(rapport_id):
    with connexion_db() as conn:
        rapport = get_rapport_detail(
            conn,
            rapport_id
        )

        if rapport is None:
            abort(404)

        photos = recuperer_photos(
            conn,
            "rapport",
            rapport_id
        )

    return render_template(
        "rapports/detail.html",
        rapport=rapport,
        photos=photos
    )


# -------------------------------------------------------------------
# Modification d'un rapport
# -------------------------------------------------------------------

@rapports_bp.route(
    "/rapports/<int:rapport_id>/modifier",
    methods=["GET", "POST"]
)
def modifier_rapport(rapport_id):
    if request.method == "GET":
        with connexion_db() as conn:
            rapport = get_rapport(
                conn,
                rapport_id
            )

            if rapport is None:
                abort(404)

            secteurs = get_all_secteurs(conn)

        return render_template(
            "rapports/modifier.html",
            rapport=rapport,
            secteurs=secteurs
        )

    secteur_id = request.form.get("secteur_id", "").strip()
    machine = request.form.get("machine", "").strip()
    probleme = request.form.get("probleme", "").strip()
    travaux = request.form.get("travaux", "").strip()
    technicien = request.form.get("technicien", "").strip()
    commentaire = request.form.get("commentaire", "").strip()
    reference = request.form.get("reference", "").strip()

    with connexion_db() as conn:
        rapport = get_rapport(
            conn,
            rapport_id
        )

        if rapport is None:
            abort(404)

        secteurs = get_all_secteurs(conn)

    if not all([
        secteur_id,
        machine,
        probleme,
        travaux,
        technicien
    ]):
        return (
            render_template(
                "rapports/modifier.html",
                rapport=rapport,
                secteurs=secteurs,
                erreur=(
                    "Le secteur, la machine, le problème, "
                    "les travaux et le technicien sont obligatoires."
                )
            ),
            400
        )

    with transaction_db() as conn:
        conn.execute("""
            UPDATE rapports_intervention
            SET
                secteur_id = ?,
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

        enregistrer_photo(
            conn,
            "rapport",
            rapport_id,
            request.files.get("photo")
        )

    return redirect(
        url_for(
            "rapports.detail_rapport",
            rapport_id=rapport_id
        )
    )


# -------------------------------------------------------------------
# Suppression d'un rapport
# -------------------------------------------------------------------

@rapports_bp.route(
    "/rapports/<int:rapport_id>/supprimer",
    methods=["POST"]
)
def supprimer_rapport(rapport_id):
    with transaction_db() as conn:
        rapport = get_rapport(
            conn,
            rapport_id
        )

        if rapport is None:
            abort(404)

        supprimer_photos(
            conn,
            "rapport",
            rapport_id
        )

        conn.execute("""
            DELETE FROM rapports_intervention
            WHERE id = ?
        """, (rapport_id,))

    return redirect(
        url_for("rapports.liste_rapports")
    )