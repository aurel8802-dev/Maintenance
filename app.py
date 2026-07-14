import os
from datetime import datetime

from flask import Flask, render_template, send_from_directory

from database import init_db
from services.database_service import connexion_db
from routes.demandes import demandes_bp
from routes.parametres import parametres_bp
from routes.rapports import rapports_bp


app = Flask(__name__)


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "uploads",
    "photos"
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# -------------------------------------------------------------------
# Blueprints
# -------------------------------------------------------------------

app.register_blueprint(demandes_bp)
app.register_blueprint(rapports_bp)
app.register_blueprint(parametres_bp)


# -------------------------------------------------------------------
# Filtres Jinja
# -------------------------------------------------------------------

@app.template_filter("date_fr")
def date_fr(value):
    """Affiche une date au format français JJ/MM/AAAA."""
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")

    try:
        date_value = datetime.fromisoformat(str(value))
        return date_value.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(value)


# -------------------------------------------------------------------
# Photos
# -------------------------------------------------------------------

@app.route("/uploads/photos/<path:filename>")
def uploaded_photo(filename):
    """Affiche une photo enregistrée dans le dossier uploads/photos."""
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# -------------------------------------------------------------------
# Tableau de bord
# -------------------------------------------------------------------

@app.route("/")
def index():
    with connexion_db() as conn:
        total = conn.execute("""
            SELECT COUNT(*)
            FROM demandes_intervention
        """).fetchone()[0]

        en_cours = conn.execute("""
            SELECT COUNT(*)
            FROM demandes_intervention
            WHERE statut = 'En cours'
        """).fetchone()[0]

        soldees = conn.execute("""
            SELECT COUNT(*)
            FROM demandes_intervention
            WHERE statut = 'Soldé'
        """).fetchone()[0]

        demandes = conn.execute("""
            SELECT
                demandes_intervention.*,
                demandeurs.nom AS demandeur_nom,
                secteurs.nom AS secteur_nom
            FROM demandes_intervention
            LEFT JOIN demandeurs
                ON demandes_intervention.demandeur_id = demandeurs.id
            LEFT JOIN secteurs
                ON demandes_intervention.secteur_id = secteurs.id
            ORDER BY demandes_intervention.date_creation DESC
            LIMIT 5
        """).fetchall()

    return render_template(
        "accueil/index.html",
        total=total,
        en_cours=en_cours,
        soldees=soldees,
        demandes=demandes
    )

# -------------------------------------------------------------------
# Initialisation de la base
# -------------------------------------------------------------------

# Cet appel est placé hors du bloc principal afin qu'il soit également
# exécuté lorsque l'application est lancée avec Gunicorn sur Render.
init_db()


# -------------------------------------------------------------------
# Lancement local
# -------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)