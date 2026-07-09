import os
from datetime import datetime
from flask import Flask, render_template, send_from_directory

from database import init_db, get_db_connection
from routes.demandes import demandes_bp

from routes.rapports import rapports_bp
from routes.parametres import parametres_bp

app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads", "photos")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

app.register_blueprint(parametres_bp)

@app.template_filter("date_fr")
def date_fr(value):
    if value:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y")
    return ""


@app.route("/uploads/photos/<filename>")
def uploaded_photo(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


app.register_blueprint(demandes_bp)
app.register_blueprint(rapports_bp)

@app.route("/")
def index():
    conn = get_db_connection()

    total = conn.execute("SELECT COUNT(*) FROM demandes_intervention").fetchone()[0]
    en_cours = conn.execute("SELECT COUNT(*) FROM demandes_intervention WHERE statut = 'En cours'").fetchone()[0]
    soldees = conn.execute("SELECT COUNT(*) FROM demandes_intervention WHERE statut = 'Soldé'").fetchone()[0]

    demandes = conn.execute("""
        SELECT demandes_intervention.*, 
               demandeurs.nom AS demandeur_nom,
               secteurs.nom AS secteur_nom
        FROM demandes_intervention
        LEFT JOIN demandeurs ON demandes_intervention.demandeur_id = demandeurs.id
        LEFT JOIN secteurs ON demandes_intervention.secteur_id = secteurs.id
        ORDER BY date_creation DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "accueil/index.html",
        total=total,
        en_cours=en_cours,
        soldees=soldees,
        demandes=demandes
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)