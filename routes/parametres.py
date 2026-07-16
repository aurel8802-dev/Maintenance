from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from config import ADMIN_RESET_CODE
from database import get_db_connection
from services.database_service import (
    connexion_db,
    transaction_db,
)

from services.export_excel import (
    EXCEL_MIME_TYPE,
    generer_export_excel,
)
from services.import_excel import importer_fichier_excel
from services.secteur_service import (
    nettoyer_secteurs_base,
    normaliser_nom_secteur,
)

parametres_bp = Blueprint("parametres", __name__)

def dossier_photos():
    """Retourne le dossier des photos configuré dans Flask."""
    return Path(current_app.config["UPLOAD_FOLDER"])


def supprimer_fichiers_photos():
    """Supprime tous les fichiers du dossier des photos."""
    repertoire = dossier_photos()

    if not repertoire.exists():
        return

    for fichier in repertoire.iterdir():
        if fichier.is_file():
            fichier.unlink()

# -------------------------------------------------------------------
# Page principale
# -------------------------------------------------------------------

@parametres_bp.route("/parametres")
def parametres():
    return render_template("parametres/index.html")


# -------------------------------------------------------------------
# Réinitialisation
# -------------------------------------------------------------------

@parametres_bp.route(
    "/parametres/reset",
    methods=["GET", "POST"]
)
def reset_donnees():
    message = None
    erreur = None

    if request.method == "POST":
        code = request.form.get("code", "")

        if code != ADMIN_RESET_CODE:
            erreur = "Code incorrect."

        else:
            conn = get_db_connection()

            try:
                conn.execute("DELETE FROM photos")
                conn.execute("DELETE FROM demandes_intervention")
                conn.execute("DELETE FROM rapports_intervention")
                conn.execute("DELETE FROM demandeurs")

                conn.commit()
                supprimer_fichiers_photos()

                message = "Toutes les données ont été supprimées."

            except Exception as error:
                conn.rollback()
                erreur = (
                    "Une erreur est survenue pendant la "
                    f"réinitialisation : {error}"
                )

            finally:
                conn.close()

    return render_template(
        "parametres/reset.html",
        message=message,
        erreur=erreur
    )


# -------------------------------------------------------------------
# Gestion des secteurs
# -------------------------------------------------------------------

@parametres_bp.route(
    "/parametres/secteurs",
    methods=["GET", "POST"]
)

def gerer_secteurs():
    message = None
    erreur = None

    nettoyage = request.args.get("nettoyage")

    if nettoyage == "ok":
        fusionnes = request.args.get("fusionnes", "0")
        supprimes = request.args.get("supprimes", "0")

        message = (
            f"Nettoyage terminé : {fusionnes} doublon(s) "
            f"fusionné(s) et {supprimes} secteur(s) supprimé(s)."
        )

    elif nettoyage == "erreur":
        erreur = (
            "Erreur pendant le nettoyage : "
            + request.args.get("detail", "erreur inconnue")
        )

    conn = get_db_connection()

    try:
        if request.method == "POST":
            nom = normaliser_nom_secteur(
                request.form.get("nom", "")
            )

            if not nom:
                erreur = "Le nom du secteur est obligatoire."

            else:
                secteur_existant = conn.execute("""
                    SELECT id, actif
                    FROM secteurs
                    WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
                    LIMIT 1
                """, (nom,)).fetchone()

                if secteur_existant:
                    if secteur_existant["actif"]:
                        erreur = "Ce secteur existe déjà."

                    else:
                        conn.execute("""
                            UPDATE secteurs
                            SET actif = TRUE
                            WHERE id = ?
                        """, (
                            secteur_existant["id"],
                        ))

                        conn.commit()
                        message = "Secteur réactivé."

                else:
                    conn.execute("""
                        INSERT INTO secteurs (
                            nom,
                            actif
                        )
                        VALUES (?, TRUE)
                    """, (
                        nom,
                    ))

                    conn.commit()
                    message = "Secteur ajouté."

        secteurs = conn.execute("""
            SELECT *
            FROM secteurs
            WHERE actif = TRUE
            ORDER BY nom
        """).fetchall()

    except Exception as error:
        conn.rollback()
        erreur = f"Erreur pendant la gestion des secteurs : {error}"
        secteurs = []

    finally:
        conn.close()

    return render_template(
        "parametres/secteurs.html",
        secteurs=secteurs,
        message=message,
        erreur=erreur
    )



@parametres_bp.route(
    "/parametres/machines/<int:machine_id>/supprimer",
    methods=["POST"]
)
def supprimer_machine(machine_id):
    with transaction_db() as conn:
        machine = conn.execute("""
            SELECT id
            FROM machines
            WHERE id = ?
        """, (machine_id,)).fetchone()

        if machine is None:
            return "Machine introuvable.", 404

        conn.execute("""
            UPDATE machines
            SET actif = FALSE
            WHERE id = ?
        """, (machine_id,))

    return redirect(
        url_for("parametres.gerer_machines")
    )


@parametres_bp.route(
    "/parametres/secteurs/nettoyer",
    methods=["POST"]
)
def nettoyer_secteurs():
    conn = get_db_connection()

    try:
        fusionnes, supprimes = nettoyer_secteurs_base(conn)

        conn.commit()

        return redirect(
            url_for(
                "parametres.gerer_secteurs",
                nettoyage="ok",
                fusionnes=fusionnes,
                supprimes=supprimes
            )
        )

    except Exception as error:
        conn.rollback()

        return redirect(
            url_for(
                "parametres.gerer_secteurs",
                nettoyage="erreur",
                detail=str(error)
            )
        )

    finally:
        conn.close()


# -------------------------------------------------------------------
# Import Excel
# -------------------------------------------------------------------

@parametres_bp.route(
    "/parametres/import",
    methods=["GET", "POST"]
)
def importer_donnees():
    message = None
    erreur = None

    if request.method == "POST":
        fichier = request.files.get("fichier")
        mode_import = request.form.get(
            "mode_import",
            "ajouter"
        )

        if not fichier or not fichier.filename:
            erreur = "Aucun fichier sélectionné."

        else:
            try:
                resultat = importer_fichier_excel(
                    fichier=fichier,
                    mode_import=mode_import,
                    photos_dir=current_app.config["UPLOAD_FOLDER"]
                )

                # Nettoyage automatique après l'import.
                conn = get_db_connection()

                try:
                    nettoyer_secteurs_base(conn)
                    conn.commit()

                except Exception:
                    conn.rollback()
                    raise

                finally:
                    conn.close()

                message = (
                    "✅ Import terminé !<br><br>"
                    f"📋 Demandes importées : "
                    f"<strong>{resultat['demandes']}</strong><br>"
                    f"📄 Rapports importés : "
                    f"<strong>{resultat['rapports']}</strong>"
                )

            except Exception as error:
                erreur = f"Erreur pendant l'import : {error}"

    return render_template(
        "parametres/import.html",
        message=message,
        erreur=erreur
    )

@parametres_bp.route("/parametres/export")
def exporter_donnees():
    fichier, nom_fichier = generer_export_excel()

    return send_file(
        fichier,
        as_attachment=True,
        download_name=nom_fichier,
        mimetype=EXCEL_MIME_TYPE
    )

@parametres_bp.route(
    "/parametres/techniciens",
    methods=["GET", "POST"]
)
def gerer_techniciens():
    message = None
    erreur = None

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()

        if not nom:
            erreur = "Le nom du technicien est obligatoire."
        else:
            try:
                with transaction_db() as conn:
                    technicien_existant = conn.execute("""
                        SELECT id
                        FROM techniciens
                        WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
                        LIMIT 1
                    """, (nom,)).fetchone()

                    if technicien_existant:
                        erreur = "Ce technicien existe déjà."
                    else:
                        conn.execute("""
                            INSERT INTO techniciens (nom)
                            VALUES (?)
                        """, (nom,))

                        message = "Technicien ajouté."

            except Exception as error:
                erreur = f"Erreur : {error}"

    with connexion_db() as conn:
        techniciens = conn.execute("""
            SELECT *
            FROM techniciens
            ORDER BY nom
        """).fetchall()

    return render_template(
        "parametres/techniciens.html",
        techniciens=techniciens,
        message=message,
        erreur=erreur
    )


@parametres_bp.route(
    "/parametres/techniciens/<int:technicien_id>/supprimer",
    methods=["POST"]
)
def supprimer_technicien(technicien_id):
    with transaction_db() as conn:
        conn.execute("""
            DELETE FROM techniciens
            WHERE id = ?
        """, (technicien_id,))

    return redirect(
        url_for("parametres.gerer_techniciens")
    )

@parametres_bp.route(
    "/parametres/machines",
    methods=["GET", "POST"]
)
def gerer_machines():
    message = None
    erreur = None
    secteur_selectionne = ""

    if request.method == "POST":
        secteur_selectionne = request.form.get(
            "secteur_id",
            ""
        ).strip()

        nom = request.form.get(
            "nom",
            ""
        ).strip()

        if not secteur_selectionne or not nom:
            erreur = (
                "Le secteur et le nom de la machine "
                "sont obligatoires."
            )

        else:
            try:
                with transaction_db() as conn:
                    machine_existante = conn.execute("""
                        SELECT id, actif
                        FROM machines
                        WHERE secteur_id = ?
                          AND LOWER(TRIM(nom)) = LOWER(TRIM(?))
                        LIMIT 1
                    """, (
                        secteur_selectionne,
                        nom
                    )).fetchone()

                    if machine_existante:
                        if machine_existante["actif"]:
                            erreur = (
                                "Cette machine existe déjà "
                                "dans ce secteur."
                            )

                        else:
                            conn.execute("""
                                UPDATE machines
                                SET actif = TRUE
                                WHERE id = ?
                            """, (
                                machine_existante["id"],
                            ))

                            message = "Machine réactivée."

                    else:
                        conn.execute("""
                            INSERT INTO machines (
                                nom,
                                secteur_id,
                                actif
                            )
                            VALUES (?, ?, TRUE)
                        """, (
                            nom,
                            secteur_selectionne
                        ))

                        message = "Machine ajoutée."

            except Exception as error:
                erreur = f"Erreur : {error}"

    with connexion_db() as conn:
        secteurs = conn.execute("""
            SELECT *
            FROM secteurs
            WHERE actif = TRUE
            ORDER BY nom
        """).fetchall()

        machines = conn.execute("""
            SELECT
                machines.*,
                secteurs.nom AS secteur_nom
            FROM machines
            JOIN secteurs
                ON machines.secteur_id = secteurs.id
            WHERE machines.actif = TRUE
            ORDER BY secteurs.nom, machines.nom
        """).fetchall()

    return render_template(
        "parametres/machines.html",
        secteurs=secteurs,
        machines=machines,
        secteur_selectionne=secteur_selectionne,
        message=message,
        erreur=erreur
    )
