from datetime import datetime

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


demandes_bp = Blueprint("demandes", __name__)


# -------------------------------------------------------------------
# Requêtes communes
# -------------------------------------------------------------------

DEMANDE_DETAIL_QUERY = """
    SELECT
        demandes_intervention.*,
        demandeurs.nom AS demandeur_nom,
        secteurs.nom AS secteur_nom
    FROM demandes_intervention
    LEFT JOIN demandeurs
        ON demandes_intervention.demandeur_id = demandeurs.id
    LEFT JOIN secteurs
        ON demandes_intervention.secteur_id = secteurs.id
    WHERE demandes_intervention.id = ?
"""


def get_demande_detail(conn, demande_id):
    """Récupère une demande avec son demandeur et son secteur."""
    return conn.execute(
        DEMANDE_DETAIL_QUERY,
        (demande_id,)
    ).fetchone()


def get_demande_simple(conn, demande_id):
    """Récupère une demande avec le nom de son secteur."""
    return conn.execute("""
        SELECT
            demandes_intervention.*,
            secteurs.nom AS secteur_nom
        FROM demandes_intervention
        LEFT JOIN secteurs
            ON demandes_intervention.secteur_id = secteurs.id
        WHERE demandes_intervention.id = ?
    """, (demande_id,)).fetchone()


def get_all_secteurs(conn):
    """Retourne uniquement les secteurs actifs."""
    return conn.execute("""
        SELECT *
        FROM secteurs
        WHERE actif = ?
        ORDER BY nom
    """, (1,)).fetchall()


# -------------------------------------------------------------------
# Demandeurs
# -------------------------------------------------------------------

def get_or_create_demandeur(conn, nom, secteur_id):
    """
    Retourne l'identifiant d'un demandeur existant ou le crée.

    La recherche ignore les majuscules, minuscules et espaces inutiles.
    """
    nom = nom.strip()

    demandeur = conn.execute("""
        SELECT id
        FROM demandeurs
        WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
        LIMIT 1
    """, (nom,)).fetchone()

    if demandeur:
        return demandeur["id"]

    cursor = conn.execute("""
        INSERT INTO demandeurs (
            nom,
            secteur_id
        )
        VALUES (?, ?)
    """, (
        nom,
        secteur_id
    ))

    return cursor.lastrowid


# -------------------------------------------------------------------
# Création
# -------------------------------------------------------------------

@demandes_bp.route(
    "/demandes/nouvelle",
    methods=["GET", "POST"]
)
def nouvelle_demande():
    if request.method == "GET":
        with connexion_db() as conn:
            secteurs = get_all_secteurs(conn)

        return render_template(
            "demandes/nouvelle.html",
            secteurs=secteurs
        )

    secteur_id = request.form.get("secteur_id", "").strip()
    demandeur_nom = request.form.get("demandeur", "").strip()
    nature_travaux = request.form.get(
        "nature_travaux",
        ""
    ).strip()
    description = request.form.get(
        "description",
        ""
    ).strip()

    if not all([
        secteur_id,
        demandeur_nom,
        nature_travaux,
        description
    ]):
        with connexion_db() as conn:
            secteurs = get_all_secteurs(conn)

        return (
            render_template(
                "demandes/nouvelle.html",
                secteurs=secteurs,
                erreur=(
                    "Tous les champs obligatoires "
                    "doivent être remplis."
                )
            ),
            400
        )

    with transaction_db() as conn:
        demandeur_id = get_or_create_demandeur(
            conn,
            demandeur_nom,
            secteur_id
        )

        cursor = conn.execute("""
            INSERT INTO demandes_intervention (
                secteur_id,
                demandeur_id,
                nature_travaux,
                description,
                statut
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            secteur_id,
            demandeur_id,
            nature_travaux,
            description,
            "En cours"
        ))

        demande_id = cursor.lastrowid

        photos = request.files.getlist("photos")

        for photo in photos:
            enregistrer_photo(
                conn,
                "demande",
                demande_id,
                photo
            )

    return redirect(
        url_for(
            "demandes.detail_demande",
            demande_id=demande_id
        )
    )


# -------------------------------------------------------------------
# Liste, recherche, filtres et tri
# -------------------------------------------------------------------

@demandes_bp.route("/demandes")
def liste_demandes():
    recherche = request.args.get("recherche", "").strip()
    secteur_id = request.args.get("secteur_id", "").strip()
    statut = request.args.get("statut", "").strip()
    tri = request.args.get("tri", "recent").strip()

    query = """
        SELECT
            demandes_intervention.*,
            demandeurs.nom AS demandeur_nom,
            secteurs.nom AS secteur_nom
        FROM demandes_intervention
        LEFT JOIN demandeurs
            ON demandes_intervention.demandeur_id = demandeurs.id
        LEFT JOIN secteurs
            ON demandes_intervention.secteur_id = secteurs.id
        WHERE 1 = 1
    """

    params = []

    if recherche:
        query += """
            AND (
                LOWER(
                    demandes_intervention.nature_travaux
                ) LIKE LOWER(?)
                OR LOWER(
                    demandes_intervention.description
                ) LIKE LOWER(?)
                OR LOWER(
                    COALESCE(demandeurs.nom, '')
                ) LIKE LOWER(?)
                OR LOWER(
                    COALESCE(secteurs.nom, '')
                ) LIKE LOWER(?)
            )
        """

        recherche_sql = f"%{recherche}%"
        params.extend([recherche_sql] * 4)

    if secteur_id:
        query += """
            AND demandes_intervention.secteur_id = ?
        """
        params.append(secteur_id)

    if statut:
        query += """
            AND demandes_intervention.statut = ?
        """
        params.append(statut)

    order_by_options = {
        "ancien": "demandes_intervention.date_creation ASC",
        "secteur": "secteurs.nom ASC",
        "statut": "demandes_intervention.statut ASC",
        "recent": "demandes_intervention.date_creation DESC",
    }

    order_by = order_by_options.get(
        tri,
        order_by_options["recent"]
    )

    query += f" ORDER BY {order_by}"

    with connexion_db() as conn:
        demandes = conn.execute(
            query,
            params
        ).fetchall()

        secteurs = get_all_secteurs(conn)

    return render_template(
        "demandes/liste.html",
        demandes=demandes,
        recherche=recherche,
        secteurs=secteurs,
        secteur_id=secteur_id,
        statut=statut,
        tri=tri
    )


# -------------------------------------------------------------------
# Détail
# -------------------------------------------------------------------

@demandes_bp.route("/demandes/<int:demande_id>")
def detail_demande(demande_id):
    with connexion_db() as conn:
        demande = get_demande_detail(
            conn,
            demande_id
        )

        if demande is None:
            abort(404)

        photos = recuperer_photos(
            conn,
            "demande",
            demande_id
        )

    return render_template(
        "demandes/detail.html",
        demande=demande,
        photos=photos
    )


# -------------------------------------------------------------------
# Modification
# -------------------------------------------------------------------

@demandes_bp.route(
    "/demandes/<int:demande_id>/modifier",
    methods=["GET", "POST"]
)
def modifier_demande(demande_id):
    if request.method == "GET":
        with connexion_db() as conn:
            demande = get_demande_simple(
                conn,
                demande_id
            )

            if demande is None:
                abort(404)

            secteurs = get_all_secteurs(conn)

            demandeur = conn.execute("""
                SELECT nom
                FROM demandeurs
                WHERE id = ?
            """, (
                demande["demandeur_id"],
            )).fetchone()

            photos = recuperer_photos(
                conn,
                "demande",
                demande_id
            )

            return render_template(
                "demandes/modifier.html",
                demande=demande,
                demandeur=demandeur,
                secteurs=secteurs,
                photos=photos
            )

    secteur_id = request.form.get("secteur_id", "").strip()
    demandeur_nom = request.form.get("demandeur", "").strip()
    nature_travaux = request.form.get(
        "nature_travaux",
        ""
    ).strip()
    description = request.form.get(
        "description",
        ""
    ).strip()

    with connexion_db() as conn:
        demande = get_demande_simple(
            conn,
            demande_id
        )

        if demande is None:
            abort(404)

        secteurs = get_all_secteurs(conn)

    if not all([
        secteur_id,
        demandeur_nom,
        nature_travaux,
        description
    ]):
        demandeur = {
            "nom": demandeur_nom
        }

        return (
            render_template(
                "demandes/modifier.html",
                demande=demande,
                demandeur=demandeur,
                secteurs=secteurs,
                erreur=(
                    "Tous les champs obligatoires "
                    "doivent être remplis."
                )
            ),
            400
        )

    with transaction_db() as conn:
        demandeur_id = get_or_create_demandeur(
            conn,
            demandeur_nom,
            secteur_id
        )

        conn.execute("""
            UPDATE demandes_intervention
            SET
                secteur_id = ?,
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

        photos = request.files.getlist("photos")

        for photo in photos:
            enregistrer_photo(
                conn,
                "demande",
                demande_id,
                photo
            )

    return redirect(
        url_for(
            "demandes.detail_demande",
            demande_id=demande_id
        )
    )



@demandes_bp.route(
    "/demandes/<int:demande_id>/photos/<int:photo_id>/supprimer",
    methods=["POST"]
)
def supprimer_photo_demande(demande_id, photo_id):
    with transaction_db() as conn:
        demande = get_demande_simple(
            conn,
            demande_id
        )

        if demande is None:
            abort(404)

        photo = conn.execute("""
            SELECT id
            FROM photos
            WHERE id = ?
              AND type_element = 'demande'
              AND element_id = ?
        """, (
            photo_id,
            demande_id
        )).fetchone()

        if photo is None:
            abort(404)

        supprimer_photo(
            conn,
            photo_id
        )

    return redirect(
        url_for(
            "demandes.modifier_demande",
            demande_id=demande_id
        )
    )

# -------------------------------------------------------------------
# Suppression
# -------------------------------------------------------------------

@demandes_bp.route(
    "/demandes/<int:demande_id>/supprimer",
    methods=["GET", "POST"]
)
def supprimer_demande(demande_id):
    if request.method == "GET":
        with connexion_db() as conn:
            demande = get_demande_detail(
                conn,
                demande_id
            )

            if demande is None:
                abort(404)

        return render_template(
            "demandes/supprimer.html",
            demande=demande
        )

    with transaction_db() as conn:
        demande = get_demande_detail(
            conn,
            demande_id
        )

        if demande is None:
            abort(404)

        supprimer_photos(
            conn,
            "demande",
            demande_id
        )

        conn.execute("""
            DELETE FROM demandes_intervention
            WHERE id = ?
        """, (
            demande_id,
        ))

    return redirect(
        url_for("demandes.liste_demandes")
    )


# -------------------------------------------------------------------
# Clôture
# -------------------------------------------------------------------

@demandes_bp.route(
    "/demandes/<int:demande_id>/solder",
    methods=["GET", "POST"]
)
def solder_demande(demande_id):
    if request.method == "GET":
        with connexion_db() as conn:
            demande = get_demande_detail(
                conn,
                demande_id
            )

            if demande is None:
                abort(404)

        if demande["statut"] == "Soldé":
            return redirect(
                url_for(
                    "demandes.detail_demande",
                    demande_id=demande_id
                )
            )

        return render_template(
            "demandes/solder.html",
            demande=demande
        )

    solde_par = request.form.get(
        "solde_par",
        ""
    ).strip()

    reference_piece = request.form.get(
        "reference_piece",
        ""
    ).strip()

    commentaire_solde = request.form.get(
        "commentaire_solde",
        ""
    ).strip()

    with connexion_db() as conn:
        demande = get_demande_detail(
            conn,
            demande_id
        )

        if demande is None:
            abort(404)

    if demande["statut"] == "Soldé":
        return redirect(
            url_for(
                "demandes.detail_demande",
                demande_id=demande_id
            )
        )

    if not solde_par:
        return (
            render_template(
                "demandes/solder.html",
                demande=demande,
                erreur=(
                    "Le nom de la personne ayant soldé "
                    "la demande est obligatoire."
                )
            ),
            400
        )

    with transaction_db() as conn:
        conn.execute("""
            UPDATE demandes_intervention
            SET
                statut = ?,
                date_solde = ?,
                solde_par = ?,
                reference_piece = ?,
                commentaire_solde = ?
            WHERE id = ?
        """, (
            "Soldé",
            datetime.now(),
            solde_par,
            reference_piece,
            commentaire_solde,
            demande_id
        ))

    return redirect(
        url_for(
            "demandes.detail_demande",
            demande_id=demande_id
        )
    )