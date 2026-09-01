from calendar import monthrange
from datetime import datetime, time, timedelta

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for
)

from database import get_db_connection


agenda_bp = Blueprint(
    "agenda",
    __name__,
    url_prefix="/agenda"
)


COULEURS_AUTORISEES = {
    "#2563eb",
    "#16a34a",
    "#eab308",
    "#f97316",
    "#dc2626",
    "#9333ea",
}

COULEUR_PAR_DEFAUT = "#2563eb"


REPETITIONS_AUTORISEES = {
    "aucune",
    "quotidienne",
    "hebdomadaire",
    "mensuelle",
    "annuelle",
}


# ---------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------

def convertir_date_iso(value):
    if not value:
        return ""

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def convertir_heure_iso(value):
    if not value:
        return ""

    if isinstance(value, time):
        return value.strftime("%H:%M")

    return str(value)[:5]


def valider_date(value):
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()

    except (TypeError, ValueError):
        return None


def valider_heure(value):
    if not value:
        return ""

    try:
        datetime.strptime(
            value,
            "%H:%M"
        )

        return value

    except (TypeError, ValueError):
        return None


def normaliser_couleur(value):
    if value in COULEURS_AUTORISEES:
        return value

    return COULEUR_PAR_DEFAUT


def normaliser_repetition(value):
    if value in REPETITIONS_AUTORISEES:
        return value

    return "aucune"


def convertir_secteur_id(value):
    """
    Retourne l'identifiant du secteur ou None lorsque
    l'utilisateur choisit « Aucun secteur ».
    """
    if value is None:
        return None

    texte = str(value).strip()

    if texte in {"", "0", "none", "null"}:
        return None

    try:
        return int(texte)
    except (TypeError, ValueError):
        return None


def ajouter_mois(date_source, nombre_mois=1):
    """
    Ajoute un ou plusieurs mois en conservant autant que possible
    le numéro du jour.

    Exemple :
    31 janvier + 1 mois -> 28 ou 29 février.
    """
    index_mois = (
        date_source.year * 12
        + date_source.month - 1
        + nombre_mois
    )

    nouvelle_annee = index_mois // 12
    nouveau_mois = index_mois % 12 + 1

    dernier_jour = monthrange(
        nouvelle_annee,
        nouveau_mois
    )[1]

    nouveau_jour = min(
        date_source.day,
        dernier_jour
    )

    return date_source.replace(
        year=nouvelle_annee,
        month=nouveau_mois,
        day=nouveau_jour
    )


def calculer_date_suivante(
    date_source,
    repetition
):
    if repetition == "quotidienne":
        return date_source + timedelta(days=1)

    if repetition == "hebdomadaire":
        return date_source + timedelta(weeks=1)

    if repetition == "mensuelle":
        return ajouter_mois(
            date_source,
            1
        )

    if repetition == "annuelle":
        try:
            return date_source.replace(
                year=date_source.year + 1
            )

        except ValueError:
            # Cas particulier du 29 février.
            return date_source.replace(
                year=date_source.year + 1,
                month=2,
                day=28
            )

    return None


# ---------------------------------------------------------
# Construction des événements du calendrier
# ---------------------------------------------------------

def construire_evenements_agenda(conn):
    taches = conn.execute("""
        SELECT
            agenda.id,
            agenda.titre,
            agenda.description,
            agenda.date_tache,
            agenda.date_fin,
            agenda.heure_tache,
            agenda.couleur,
            agenda.repetition,
            agenda.occurrence_suivante_creee,
            agenda.solde,
            agenda.demande_par,
            agenda.solde_par,
            agenda.date_solde,
            agenda.secteur_id,
            secteurs.nom AS secteur_nom
        FROM agenda
        LEFT JOIN secteurs
            ON agenda.secteur_id = secteurs.id
        ORDER BY
            agenda.date_tache ASC,
            agenda.heure_tache ASC,
            agenda.id ASC
    """).fetchall()

    evenements = []

    for tache in taches:
        soldee = bool(
            tache["solde"]
        )

        date_debut = convertir_date_iso(
            tache["date_tache"]
        )

        date_fin = convertir_date_iso(
            tache["date_fin"]
        )

        heure_tache = convertir_heure_iso(
            tache["heure_tache"]
        )

        couleur = normaliser_couleur(
            tache["couleur"]
        )

        repetition = normaliser_repetition(
            tache["repetition"]
        )

        all_day = not bool(
            heure_tache
        )

        if all_day:
            debut = date_debut
        else:
            debut = (
                f"{date_debut}"
                f"T{heure_tache}:00"
            )

        evenement = {
            "id": str(tache["id"]),
            "title": tache["titre"],
            "start": debut,
            "allDay": all_day,
            "backgroundColor": couleur,
            "borderColor": couleur,

            "classNames": (
                ["tache-soldee"]
                if soldee
                else ["tache-non-soldee"]
            ),

            "extendedProps": {
                "description": (
                    tache["description"] or ""
                ),

                "solde": soldee,

                "secteur_id": (
                    tache["secteur_id"] or ""
                ),

                "secteur_nom": (
                    tache["secteur_nom"] or ""
                ),

                "demande_par": (
                    tache["demande_par"] or ""
                ),

                "solde_par": (
                    tache["solde_par"] or ""
                ),

                "date_solde": convertir_date_iso(
                    tache["date_solde"]
                ),

                "date_debut": date_debut,
                "date_fin": date_fin,
                "heure_tache": heure_tache,
                "couleur": couleur,
                "repetition": repetition,

                "occurrence_suivante_creee": bool(
                    tache[
                        "occurrence_suivante_creee"
                    ]
                ),
            },
        }

        if date_fin:
            fin_obj = valider_date(
                date_fin
            )

            if fin_obj:
                # FullCalendar utilise une date de fin exclusive.
                evenement["end"] = (
                    fin_obj
                    + timedelta(days=1)
                ).isoformat()

        evenements.append(
            evenement
        )

    return evenements


# ---------------------------------------------------------
# Page principale de l'agenda
# ---------------------------------------------------------

@agenda_bp.route("/")
def afficher_agenda():
    conn = get_db_connection()

    try:
        secteurs = conn.execute("""
            SELECT
                id,
                nom
            FROM secteurs
            WHERE actif = TRUE
            ORDER BY nom
        """).fetchall()

        evenements_agenda = construire_evenements_agenda(
            conn
        )

    finally:
        conn.close()

    return render_template(
        "agenda/index.html",
        secteurs=secteurs,
        evenements_agenda=evenements_agenda
    )


# ---------------------------------------------------------
# Route JSON conservée pour les tests
# ---------------------------------------------------------

@agenda_bp.route("/taches")
def recuperer_taches():
    conn = get_db_connection()

    try:
        evenements = construire_evenements_agenda(
            conn
        )

        return jsonify(
            evenements
        )

    finally:
        conn.close()


# ---------------------------------------------------------
# Ajouter une tâche
# ---------------------------------------------------------

@agenda_bp.route(
    "/ajouter",
    methods=["POST"]
)
def ajouter_tache():
    titre = request.form.get(
        "titre",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    date_tache_texte = request.form.get(
        "date_tache",
        ""
    ).strip()

    date_fin_texte = request.form.get(
        "date_fin",
        ""
    ).strip()

    heure_tache = request.form.get(
        "heure_tache",
        ""
    ).strip()

    couleur = normaliser_couleur(
        request.form.get(
            "couleur",
            ""
        ).strip()
    )

    repetition = normaliser_repetition(
        request.form.get(
            "repetition",
            ""
        ).strip()
    )

    secteur_id = request.form.get(
        "secteur_id",
        ""
    ).strip()

    secteur_id_valide = convertir_secteur_id(
        secteur_id
    )

    demande_par = request.form.get(
        "demande_par",
        ""
    ).strip()

    date_tache = valider_date(
        date_tache_texte
    )

    date_fin = (
        valider_date(
            date_fin_texte
        )
        if date_fin_texte
        else None
    )

    heure_validee = valider_heure(
        heure_tache
    )

    if (
        not titre
        or not date_tache
        or not demande_par
        or heure_validee is None
    ):
        return redirect(
            url_for(
                "agenda.afficher_agenda"
            )
        )

    if (
        date_fin
        and date_fin < date_tache
    ):
        return redirect(
            url_for(
                "agenda.afficher_agenda"
            )
        )

    conn = get_db_connection()

    try:
        conn.execute("""
            INSERT INTO agenda (
                titre,
                description,
                date_tache,
                date_fin,
                heure_tache,
                couleur,
                repetition,
                occurrence_suivante_creee,
                secteur_id,
                demande_par,
                solde,
                solde_par,
                date_solde
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                FALSE,
                ?, ?,
                FALSE,
                NULL,
                NULL
            )
        """, (
            titre,
            description or None,
            date_tache.isoformat(),

            (
                date_fin.isoformat()
                if date_fin
                else None
            ),

            heure_validee or None,
            couleur,
            repetition,
            secteur_id_valide,
            demande_par,
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return redirect(
        url_for(
            "agenda.afficher_agenda"
        )
    )


# ---------------------------------------------------------
# Modifier une tâche
# ---------------------------------------------------------

@agenda_bp.route(
    "/<int:tache_id>/modifier",
    methods=["POST"]
)
def modifier_tache(tache_id):
    titre = request.form.get(
        "titre",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    date_tache_texte = request.form.get(
        "date_tache",
        ""
    ).strip()

    date_fin_texte = request.form.get(
        "date_fin",
        ""
    ).strip()

    heure_tache = request.form.get(
        "heure_tache",
        ""
    ).strip()

    couleur = normaliser_couleur(
        request.form.get(
            "couleur",
            ""
        ).strip()
    )

    repetition = normaliser_repetition(
        request.form.get(
            "repetition",
            ""
        ).strip()
    )

    secteur_id = request.form.get(
        "secteur_id",
        ""
    ).strip()

    secteur_id_valide = convertir_secteur_id(
        secteur_id
    )

    demande_par = request.form.get(
        "demande_par",
        ""
    ).strip()

    date_tache = valider_date(
        date_tache_texte
    )

    date_fin = (
        valider_date(
            date_fin_texte
        )
        if date_fin_texte
        else None
    )

    heure_validee = valider_heure(
        heure_tache
    )

    if (
        not titre
        or not date_tache
        or not demande_par
        or heure_validee is None
    ):
        return redirect(
            url_for(
                "agenda.afficher_agenda"
            )
        )

    if (
        date_fin
        and date_fin < date_tache
    ):
        return redirect(
            url_for(
                "agenda.afficher_agenda"
            )
        )

    conn = get_db_connection()

    try:
        tache = conn.execute("""
            SELECT
                id
            FROM agenda
            WHERE id = ?
        """, (
            tache_id,
        )).fetchone()

        if tache is None:
            return (
                "Tâche introuvable.",
                404
            )

        conn.execute("""
            UPDATE agenda
            SET
                titre = ?,
                description = ?,
                date_tache = ?,
                date_fin = ?,
                heure_tache = ?,
                couleur = ?,
                repetition = ?,
                secteur_id = ?,
                demande_par = ?
            WHERE id = ?
        """, (
            titre,
            description or None,
            date_tache.isoformat(),

            (
                date_fin.isoformat()
                if date_fin
                else None
            ),

            heure_validee or None,
            couleur,
            repetition,
            secteur_id_valide,
            demande_par,
            tache_id,
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return redirect(
        url_for(
            "agenda.afficher_agenda"
        )
    )


# ---------------------------------------------------------
# Solder ou rouvrir une tâche
# ---------------------------------------------------------

@agenda_bp.route(
    "/<int:tache_id>/changer-statut",
    methods=["POST"]
)
def changer_statut_tache(tache_id):
    solde_par = request.form.get(
        "solde_par",
        ""
    ).strip()

    conn = get_db_connection()

    try:
        tache = conn.execute("""
            SELECT
                id,
                titre,
                description,
                date_tache,
                date_fin,
                heure_tache,
                couleur,
                repetition,
                occurrence_suivante_creee,
                secteur_id,
                demande_par,
                solde
            FROM agenda
            WHERE id = ?
        """, (
            tache_id,
        )).fetchone()

        if tache is None:
            return (
                "Tâche introuvable.",
                404
            )

        actuellement_soldee = bool(
            tache["solde"]
        )

        # La tâche est déjà soldée :
        # on la repasse en non soldée.
        if actuellement_soldee:
            conn.execute("""
                UPDATE agenda
                SET
                    solde = FALSE,
                    solde_par = NULL,
                    date_solde = NULL
                WHERE id = ?
            """, (
                tache_id,
            ))

        # La tâche n'est pas encore soldée.
        else:
            if not solde_par:
                return redirect(
                    url_for(
                        "agenda.afficher_agenda"
                    )
                )

            repetition = normaliser_repetition(
                tache["repetition"]
            )

            occurrence_deja_creee = bool(
                tache[
                    "occurrence_suivante_creee"
                ]
            )

            conn.execute("""
                UPDATE agenda
                SET
                    solde = TRUE,
                    solde_par = ?,
                    date_solde = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                solde_par,
                tache_id
            ))

            # Création de la prochaine occurrence.
            if (
                repetition != "aucune"
                and not occurrence_deja_creee
            ):
                date_debut = valider_date(
                    convertir_date_iso(
                        tache["date_tache"]
                    )
                )

                date_fin = None

                if tache["date_fin"]:
                    date_fin = valider_date(
                        convertir_date_iso(
                            tache["date_fin"]
                        )
                    )

                prochaine_date = (
                    calculer_date_suivante(
                        date_debut,
                        repetition
                    )
                )

                prochaine_date_fin = None

                if date_fin:
                    duree = (
                        date_fin - date_debut
                    )

                    prochaine_date_fin = (
                        prochaine_date + duree
                    )

                conn.execute("""
                    INSERT INTO agenda (
                        titre,
                        description,
                        date_tache,
                        date_fin,
                        heure_tache,
                        couleur,
                        repetition,
                        occurrence_suivante_creee,
                        secteur_id,
                        demande_par,
                        solde,
                        solde_par,
                        date_solde
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        FALSE,
                        ?, ?,
                        FALSE,
                        NULL,
                        NULL
                    )
                """, (
                    tache["titre"],
                    tache["description"],
                    prochaine_date.isoformat(),

                    (
                        prochaine_date_fin.isoformat()
                        if prochaine_date_fin
                        else None
                    ),

                    (
                        convertir_heure_iso(
                            tache["heure_tache"]
                        )
                        or None
                    ),

                    normaliser_couleur(
                        tache["couleur"]
                    ),

                    repetition,
                    tache["secteur_id"],
                    tache["demande_par"],
                ))

                conn.execute("""
                    UPDATE agenda
                    SET
                        occurrence_suivante_creee = TRUE
                    WHERE id = ?
                """, (
                    tache_id,
                ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return redirect(
        url_for(
            "agenda.afficher_agenda"
        )
    )


# ---------------------------------------------------------
# Supprimer une tâche
# ---------------------------------------------------------

@agenda_bp.route(
    "/<int:tache_id>/supprimer",
    methods=["POST"]
)
def supprimer_tache(tache_id):
    conn = get_db_connection()

    try:
        tache = conn.execute("""
            SELECT
                id
            FROM agenda
            WHERE id = ?
        """, (
            tache_id,
        )).fetchone()

        if tache is None:
            return (
                "Tâche introuvable.",
                404
            )

        conn.execute("""
            DELETE FROM agenda
            WHERE id = ?
        """, (
            tache_id,
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return redirect(
        url_for(
            "agenda.afficher_agenda"
        )
    )