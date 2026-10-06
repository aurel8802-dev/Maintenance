from datetime import date

from flask import Blueprint, redirect, render_template, request, url_for

from database import get_db_connection

commandes_bp = Blueprint("commandes", __name__, url_prefix="/commandes")
ETATS = ["À demander", "Prix demandé", "Commandé", "Livré", "Refusé"]


@commandes_bp.route("/")
def liste():
    recherche = request.args.get("recherche", "").strip()
    etat = request.args.get("etat", "").strip()
    chantier_id = request.args.get("chantier_id", "").strip()

    conn = get_db_connection()
    sql = """
        SELECT c.*, ch.nom AS chantier_nom
        FROM commandes c
        LEFT JOIN chantiers ch ON ch.id = c.chantier_id
        WHERE 1=1
    """
    params = []

    if recherche:
        sql += """
            AND (
                LOWER(c.piece) LIKE LOWER(?)
                OR LOWER(COALESCE(c.reference, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(c.commentaire, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(ch.nom, '')) LIKE LOWER(?)
            )
        """
        q = f"%{recherche}%"
        params += [q, q, q, q]

    if etat:
        sql += " AND c.etat = ?"
        params.append(etat)

    if chantier_id:
        sql += " AND c.chantier_id = ?"
        params.append(chantier_id)

    sql += " ORDER BY c.date_commande DESC, c.id DESC"

    commandes = conn.execute(sql, params).fetchall()
    chantiers = conn.execute("""
        SELECT id, nom FROM chantiers
        WHERE actif = TRUE
        ORDER BY nom
    """).fetchall()
    conn.close()

    return render_template(
        "commandes/index.html",
        commandes=commandes,
        chantiers=chantiers,
        etats=ETATS,
        recherche=recherche,
        etat=etat,
        chantier_id=chantier_id,
    )


@commandes_bp.route("/nouvelle", methods=["GET", "POST"])
def nouvelle():
    conn = get_db_connection()

    if request.method == "POST":
        cursor = conn.execute("""
            INSERT INTO commandes
            (date_commande, piece, quantite, reference, etat, delai, chantier_id, commentaire)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form.get("date_commande") or date.today().isoformat(),
            request.form["piece"].strip(),
            request.form.get("quantite", "1").strip(),
            request.form.get("reference", "").strip(),
            request.form.get("etat", "À demander"),
            request.form.get("delai") or None,
            request.form.get("chantier_id") or None,
            request.form.get("commentaire", "").strip(),
        ))
        commande_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return redirect(url_for("commandes.detail", id=commande_id))

    chantiers = conn.execute("""
        SELECT id, nom FROM chantiers
        WHERE actif = TRUE
        ORDER BY nom
    """).fetchall()
    conn.close()
    return render_template(
        "commandes/form.html",
        commande=None,
        chantiers=chantiers,
        etats=ETATS,
        titre="Nouvelle commande",
    )


@commandes_bp.route("/<int:id>")
def detail(id):
    conn = get_db_connection()
    commande = conn.execute("""
        SELECT c.*, ch.nom AS chantier_nom
        FROM commandes c
        LEFT JOIN chantiers ch ON ch.id = c.chantier_id
        WHERE c.id = ?
    """, (id,)).fetchone()
    conn.close()

    if not commande:
        return redirect(url_for("commandes.liste"))

    return render_template("commandes/detail.html", commande=commande)


@commandes_bp.route("/<int:id>/modifier", methods=["GET", "POST"])
def modifier(id):
    conn = get_db_connection()
    commande = conn.execute("SELECT * FROM commandes WHERE id = ?", (id,)).fetchone()

    if not commande:
        conn.close()
        return redirect(url_for("commandes.liste"))

    if request.method == "POST":
        conn.execute("""
            UPDATE commandes
            SET date_commande = ?, piece = ?, quantite = ?, reference = ?,
                etat = ?, delai = ?, chantier_id = ?, commentaire = ?
            WHERE id = ?
        """, (
            request.form["date_commande"],
            request.form["piece"].strip(),
            request.form.get("quantite", "1").strip(),
            request.form.get("reference", "").strip(),
            request.form.get("etat", "À demander"),
            request.form.get("delai") or None,
            request.form.get("chantier_id") or None,
            request.form.get("commentaire", "").strip(),
            id,
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("commandes.detail", id=id))

    chantiers = conn.execute("""
        SELECT id, nom FROM chantiers
        WHERE actif = TRUE
        ORDER BY nom
    """).fetchall()
    conn.close()
    return render_template(
        "commandes/form.html",
        commande=commande,
        chantiers=chantiers,
        etats=ETATS,
        titre="Modifier la commande",
    )


@commandes_bp.route("/<int:id>/supprimer", methods=["POST"])
def supprimer(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM commandes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("commandes.liste"))
