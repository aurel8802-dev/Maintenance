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
    supprimer_photo,
    supprimer_photos,
)

from datetime import date, datetime

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
    """Retourne uniquement les secteurs actifs."""
    return conn.execute("""
        SELECT *
        FROM secteurs
        WHERE actif = ?
        ORDER BY nom
    """, (1,)).fetchall()


def get_rapport(conn, rapport_id):
    """Récupère un rapport avec le nom de son secteur."""
    return conn.execute("""
        SELECT
            rapports_intervention.*,
            secteurs.nom AS secteur_nom
        FROM rapports_intervention
        LEFT JOIN secteurs
            ON rapports_intervention.secteur_id = secteurs.id
        WHERE rapports_intervention.id = ?
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
            techniciens = get_all_techniciens(conn)
            machines = get_all_machines(conn)

        return render_template(
            "rapports/nouveau.html",
            secteurs=secteurs,
            techniciens=techniciens,
            date_du_jour=date.today().isoformat(),
            machines=machines
        )

    date_rapport_raw = request.form.get(
        "date_rapport",
        ""
    ).strip()

    secteur_id = request.form.get(
        "secteur_id",
        ""
    ).strip()

    machine = request.form.get(
        "machine",
        ""
    ).strip()

    probleme = request.form.get(
        "probleme",
        ""
    ).strip()

    travaux = request.form.get(
        "travaux",
        ""
    ).strip()

    technicien = request.form.get(
        "technicien",
        ""
    ).strip()

    commentaire = request.form.get(
        "commentaire",
        ""
    ).strip()

    reference = request.form.get(
        "reference",
        ""
    ).strip()

    if not all([
        date_rapport_raw,
        secteur_id,
        machine,
        probleme,
        travaux,
        technicien
    ]):
        with connexion_db() as conn:
            secteurs = get_all_secteurs(conn)
            techniciens = get_all_techniciens(conn)

        return (
            render_template(
                "rapports/nouveau.html",
                secteurs=secteurs,
                techniciens=techniciens,
                date_du_jour=(
                    date_rapport_raw
                    or date.today().isoformat()
                ),
                erreur=(
                    "La date, le secteur, la machine, "
                    "le problème, les travaux et le "
                    "technicien sont obligatoires."
                )
            ),
            400
        )

    try:
        date_rapport = datetime.strptime(
            date_rapport_raw,
            "%Y-%m-%d"
        )

    except ValueError:
        with connexion_db() as conn:
            secteurs = get_all_secteurs(conn)
            techniciens = get_all_techniciens(conn)

        return (
            render_template(
                "rapports/nouveau.html",
                secteurs=secteurs,
                techniciens=techniciens,
                date_du_jour=date.today().isoformat(),
                erreur="La date du rapport est invalide."
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
            date_rapport
        ))

        rapport_id = cursor.lastrowid

        photos_ajoutees = request.files.getlist("photos")

        for photo in photos_ajoutees:
            enregistrer_photo(
                conn,
                "rapport",
                rapport_id,
                photo
            )

    return redirect(
        url_for(
            "rapports.detail_rapport",
            rapport_id=rapport_id
        )
    )

def get_all_techniciens(conn):
    """Retourne les techniciens enregistrés dans les paramètres."""
    rows = conn.execute("""
        SELECT nom
        FROM techniciens
        ORDER BY nom
    """).fetchall()

    return [
        row["nom"]
        for row in rows
    ]
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
            rapport = get_rapport(conn, rapport_id)

            if rapport is None:
                abort(404)

            secteurs = get_all_secteurs(conn)
            techniciens = get_all_techniciens(conn)
            machines = get_all_machines(conn)

            photos = recuperer_photos(
                conn,
                "rapport",
                rapport_id
            )

        date_rapport_value = ""

        if rapport["date_rapport"]:
            try:
                date_rapport_value = rapport[
                    "date_rapport"
                ].strftime("%Y-%m-%d")

            except AttributeError:
                date_rapport_value = str(
                    rapport["date_rapport"]
                )[:10]

        return render_template(
            "rapports/modifier.html",
            rapport=rapport,
            secteurs=secteurs,
            techniciens=techniciens,
            date_rapport_value=date_rapport_value,
            photos=photos,
            machines=machines
        )

    date_rapport_raw = request.form.get(
        "date_rapport",
        ""
    ).strip()

    secteur_id = request.form.get(
        "secteur_id",
        ""
    ).strip()

    machine = request.form.get(
        "machine",
        ""
    ).strip()

    probleme = request.form.get(
        "probleme",
        ""
    ).strip()

    travaux = request.form.get(
        "travaux",
        ""
    ).strip()

    technicien = request.form.get(
        "technicien",
        ""
    ).strip()

    commentaire = request.form.get(
        "commentaire",
        ""
    ).strip()

    reference = request.form.get(
        "reference",
        ""
    ).strip()

    with connexion_db() as conn:
        rapport = get_rapport(
            conn,
            rapport_id
        )

        if rapport is None:
            abort(404)

        secteurs = get_all_secteurs(conn)
        techniciens = get_all_techniciens(conn)

        photos = recuperer_photos(
            conn,
            "rapport",
            rapport_id
        )

    if not all([
        date_rapport_raw,
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
                techniciens=techniciens,
                date_rapport_value=date_rapport_raw,
                photos=photos,
                erreur=(
                    "La date, le secteur, la machine, "
                    "le problème, les travaux et le "
                    "technicien sont obligatoires."
                )
            ),
            400
        )

    try:
        date_rapport = datetime.strptime(
            date_rapport_raw,
            "%Y-%m-%d"
        )

    except ValueError:
        return (
            render_template(
                "rapports/modifier.html",
                rapport=rapport,
                secteurs=secteurs,
                techniciens=techniciens,
                date_rapport_value=date_rapport_raw,
                photos=photos,
                erreur="La date du rapport est invalide."
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
                reference = ?,
                date_rapport = ?
            WHERE id = ?
        """, (
            secteur_id,
            machine,
            probleme,
            travaux,
            technicien,
            commentaire,
            reference,
            date_rapport,
            rapport_id
        ))

        photos_ajoutees = request.files.getlist("photos")

        for photo in photos_ajoutees:
            enregistrer_photo(
                conn,
                "rapport",
                rapport_id,
                photo
            )

    return redirect(
        url_for(
            "rapports.detail_rapport",
            rapport_id=rapport_id
        )
    )

@rapports_bp.route(
    "/rapports/<int:rapport_id>/photos/<int:photo_id>/supprimer",
    methods=["POST"]
)
def supprimer_photo_rapport(rapport_id, photo_id):
    with transaction_db() as conn:
        rapport = get_rapport(
            conn,
            rapport_id
        )

        if rapport is None:
            abort(404)

        photo = conn.execute("""
            SELECT id
            FROM photos
            WHERE id = ?
              AND type_element = 'rapport'
              AND element_id = ?
        """, (
            photo_id,
            rapport_id
        )).fetchone()

        if photo is None:
            abort(404)

        supprimer_photo(
            conn,
            photo_id
        )

    return redirect(
        url_for(
            "rapports.modifier_rapport",
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

def get_all_machines(conn):
    """Retourne uniquement les machines actives."""
    return conn.execute("""
        SELECT
            machines.id,
            machines.nom,
            machines.secteur_id
        FROM machines
        WHERE machines.actif = ?
        ORDER BY machines.nom
    """, (1,)).fetchall()