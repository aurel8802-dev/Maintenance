import os
import re
from functools import wraps
from io import BytesIO

import pandas as pd
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from database import get_db_connection


courbes_edf_bp = Blueprint(
    "courbes_edf",
    __name__,
    url_prefix="/courbes-edf",
)

MOIS = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}


def lire_fichier_xml(fichier):
    """Lit un XML ENEDIS/EDF et renvoie un DataFrame."""
    contenu = fichier.read().decode("utf-8", errors="ignore")

    pattern = (
        r'<Donnees_Point_Mesure '
        r'Horodatage="([^"]+)" '
        r'Valeur_Point="([^"]+)" '
        r'Statut_Point="([^"]*)"'
    )

    donnees = []

    for match in re.finditer(pattern, contenu):
        try:
            valeur = float(match.group(2).replace(",", "."))
        except ValueError:
            continue

        donnees.append({
            "Date/Heure": match.group(1),
            "Consommation_kW": valeur,
            "Statut": match.group(3),
        })

    df = pd.DataFrame(donnees)

    if not df.empty:
        df["Date/Heure"] = pd.to_datetime(
            df["Date/Heure"],
            errors="coerce",
        )
        df = df.dropna(subset=["Date/Heure"])
        df = df.sort_values("Date/Heure")

    return df


def creer_excel_avec_graphique(df, titre="Courbe de consommation"):
    fichier_excel = BytesIO()

    df_export = df.copy()
    df_export["Date/Heure"] = pd.to_datetime(df_export["Date/Heure"])
    df_export["Consommation_kW"] = pd.to_numeric(
        df_export["Consommation_kW"]
    )
    df_export = df_export[["Date/Heure", "Consommation_kW"]]
    df_export.insert(0, "Index", range(1, len(df_export) + 1))

    with pd.ExcelWriter(fichier_excel, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, sheet_name="Données", index=False)

        workbook = writer.book
        ws_data = writer.sheets["Données"]
        ws_graph = workbook.add_worksheet("Graphique")

        format_date = workbook.add_format({"num_format": "dd/mm/yyyy hh:mm"})
        format_kw = workbook.add_format({"num_format": "0.00"})
        format_header = workbook.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1,
        })

        ws_data.set_column("A:A", 10)
        ws_data.set_column("B:B", 20, format_date)
        ws_data.set_column("C:C", 18, format_kw)

        for col_num, value in enumerate(df_export.columns):
            ws_data.write(0, col_num, value, format_header)

        ligne_fin = len(df_export)
        chart = workbook.add_chart({"type": "line"})
        chart.add_series({
            "name": "Consommation kW",
            "categories": ["Données", 1, 0, ligne_fin, 0],
            "values": ["Données", 1, 2, ligne_fin, 2],
            "line": {"color": "#1F4E79", "width": 1},
        })
        chart.set_title({"name": titre})
        chart.set_x_axis({
            "name": "Relevés sur le mois",
            "major_gridlines": {"visible": False},
        })
        chart.set_y_axis({
            "name": "Consommation (kW)",
            "min": 0,
            "major_gridlines": {"visible": True},
        })
        chart.set_legend({"none": True})
        chart.set_size({"width": 1400, "height": 750})
        ws_graph.insert_chart("B2", chart)

    fichier_excel.seek(0)
    return fichier_excel


def code_edf_attendu():
    # Le code demandé est 1976. Il peut être changé sur Render avec EDF_ACCESS_CODE.
    return os.getenv("EDF_ACCESS_CODE", "1976")


def acces_edf_requis(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("courbes_edf_autorise"):
            return redirect(url_for("courbes_edf.acces"))
        return view(*args, **kwargs)

    return wrapper


def convertir_xml_bytes(valeur):
    if valeur is None:
        return b""
    if isinstance(valeur, memoryview):
        return valeur.tobytes()
    if isinstance(valeur, bytes):
        return valeur
    return bytes(valeur)


def recuperer_courbe(courbe_id):
    conn = get_db_connection()
    try:
        return conn.execute(
            """
            SELECT id, annee, mois, nom_fichier, donnees_xml, created_at
            FROM courbes_edf
            WHERE id = ?
            """,
            (courbe_id,),
        ).fetchone()
    finally:
        conn.close()


@courbes_edf_bp.route("/acces", methods=["GET", "POST"])
def acces():
    erreur = None

    # Chaque clic depuis Paramètres repasse par cet écran.
    if request.method == "GET":
        session.pop("courbes_edf_autorise", None)

    if request.method == "POST":
        code = request.form.get("code", "").strip()

        if code == code_edf_attendu():
            session["courbes_edf_autorise"] = True
            return redirect(url_for("courbes_edf.index"))

        erreur = "Code incorrect."

    return render_template(
        "courbes_edf/acces.html",
        erreur=erreur,
    )


@courbes_edf_bp.route("/")
@acces_edf_requis
def index():
    recherche = request.args.get("recherche", "").strip().lower()
    courbe_id = request.args.get("courbe_id", "").strip()

    conn = get_db_connection()
    try:
        courbes = conn.execute(
            """
            SELECT id, annee, mois, nom_fichier, created_at
            FROM courbes_edf
            ORDER BY annee DESC, mois DESC
            """
        ).fetchall()
    finally:
        conn.close()

    historique = []
    for courbe in courbes:
        mois_nom = MOIS.get(int(courbe["mois"]), str(courbe["mois"]))
        libelle = f"{mois_nom} {courbe['annee']}"
        if recherche and recherche not in libelle.lower():
            continue
        historique.append({
            "id": courbe["id"],
            "annee": courbe["annee"],
            "mois": courbe["mois"],
            "mois_nom": mois_nom,
            "libelle": libelle,
            "nom_fichier": courbe["nom_fichier"],
        })

    courbe_selectionnee = None
    stats = None
    graphique = None

    if courbe_id.isdigit():
        courbe_selectionnee = recuperer_courbe(int(courbe_id))

    if courbe_selectionnee:
        contenu = convertir_xml_bytes(courbe_selectionnee["donnees_xml"])
        df = lire_fichier_xml(BytesIO(contenu))

        if not df.empty:
            valeurs = df["Consommation_kW"]
            stats = {
                "mesures": int(len(df)),
                "maximum": float(valeurs.max()),
                "moyenne": float(valeurs.mean()),
                "minimum": float(valeurs.min()),
                "debut": df["Date/Heure"].min().strftime("%d/%m/%Y %H:%M"),
                "fin": df["Date/Heure"].max().strftime("%d/%m/%Y %H:%M"),
            }

            # Pour garder le navigateur fluide sur les très gros fichiers,
            # on réduit l'affichage à environ 1500 points maximum.
            pas = max(1, len(df) // 1500)
            df_graph = df.iloc[::pas]

            graphique = {
                "labels": [
                    dt.strftime("%d/%m %H:%M")
                    for dt in df_graph["Date/Heure"]
                ],
                "valeurs": [
                    round(float(v), 3)
                    for v in df_graph["Consommation_kW"]
                ],
            }

    return render_template(
        "courbes_edf/index.html",
        historique=historique,
        courbe=courbe_selectionnee,
        stats=stats,
        graphique=graphique,
        recherche=request.args.get("recherche", ""),
        mois=MOIS,
    )


@courbes_edf_bp.route("/importer", methods=["POST"])
@acces_edf_requis
def importer():
    fichier = request.files.get("fichier")
    remplacer = request.form.get("remplacer") == "1"

    if not fichier or not fichier.filename:
        return redirect(url_for("courbes_edf.index", erreur="Aucun fichier sélectionné."))

    contenu = fichier.read()
    df = lire_fichier_xml(BytesIO(contenu))

    if df.empty:
        return redirect(url_for("courbes_edf.index", erreur="Aucune donnée ENEDIS trouvée dans ce fichier."))

    date_debut = df["Date/Heure"].min()
    annee = int(date_debut.year)
    mois = int(date_debut.month)

    conn = get_db_connection()
    try:
        existante = conn.execute(
            "SELECT id FROM courbes_edf WHERE annee = ? AND mois = ?",
            (annee, mois),
        ).fetchone()

        if existante and not remplacer:
            conn.close()
            return redirect(url_for(
                "courbes_edf.index",
                erreur=(
                    f"La courbe {MOIS[mois]} {annee} existe déjà. "
                    "Cochez « Remplacer si elle existe déjà » pour la remplacer."
                ),
            ))

        if existante:
            conn.execute(
                """
                UPDATE courbes_edf
                SET nom_fichier = ?, donnees_xml = ?, created_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (fichier.filename, contenu, existante["id"]),
            )
            courbe_id = existante["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO courbes_edf (
                    annee, mois, nom_fichier, donnees_xml
                )
                VALUES (?, ?, ?, ?)
                """,
                (annee, mois, fichier.filename, contenu),
            )
            courbe_id = cursor.lastrowid

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return redirect(url_for(
        "courbes_edf.index",
        courbe_id=courbe_id,
        message=f"Courbe {MOIS[mois]} {annee} enregistrée.",
    ))


@courbes_edf_bp.route("/<int:courbe_id>/exporter")
@acces_edf_requis
def exporter(courbe_id):
    courbe = recuperer_courbe(courbe_id)
    if not courbe:
        return redirect(url_for("courbes_edf.index"))

    contenu = convertir_xml_bytes(courbe["donnees_xml"])
    df = lire_fichier_xml(BytesIO(contenu))
    if df.empty:
        return redirect(url_for("courbes_edf.index", courbe_id=courbe_id))

    mois_nom = MOIS.get(int(courbe["mois"]), str(courbe["mois"]))
    titre = f"Courbe {mois_nom} {courbe['annee']}"
    fichier_excel = creer_excel_avec_graphique(df, titre=titre)

    return send_file(
        fichier_excel,
        as_attachment=True,
        download_name=f"courbe_{courbe['annee']}_{int(courbe['mois']):02d}.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


@courbes_edf_bp.route("/<int:courbe_id>/supprimer", methods=["POST"])
@acces_edf_requis
def supprimer(courbe_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM courbes_edf WHERE id = ?", (courbe_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return redirect(url_for("courbes_edf.index", message="Courbe supprimée."))


@courbes_edf_bp.route("/quitter")
def quitter():
    session.pop("courbes_edf_autorise", None)
    return redirect(url_for("parametres.parametres"))
