from datetime import date
from flask import Blueprint, redirect, render_template, request, url_for
from database import get_db_connection

tar_bp = Blueprint("tar", __name__, url_prefix="/tar")

@tar_bp.route("/", methods=["GET", "POST"])
def liste():
    conn = get_db_connection()
    if request.method == "POST":
        cursor = conn.execute("""
            INSERT INTO releves_tar (date_releve, index_compteur, traitements)
            VALUES (?, ?, ?)
        """, (
            request.form.get("date_releve") or date.today().isoformat(),
            request.form["index_compteur"].strip(),
            request.form.get("traitements", "").strip(),
        ))
        releve_id = cursor.lastrowid
        conn.commit(); conn.close()
        return redirect(url_for("tar.liste"))

    releves = conn.execute("SELECT * FROM releves_tar ORDER BY date_releve DESC, id DESC").fetchall()
    conn.close()
    return render_template("tar/index.html", releves=releves, today=date.today().isoformat())

@tar_bp.route("/<int:id>")
def detail(id):
    conn=get_db_connection(); releve=conn.execute("SELECT * FROM releves_tar WHERE id = ?",(id,)).fetchone(); conn.close()
    if not releve: return redirect(url_for("tar.liste"))
    return render_template("tar/detail.html", releve=releve)

@tar_bp.route("/<int:id>/modifier", methods=["GET","POST"])
def modifier(id):
    conn=get_db_connection(); releve=conn.execute("SELECT * FROM releves_tar WHERE id = ?",(id,)).fetchone()
    if not releve:
        conn.close(); return redirect(url_for("tar.liste"))
    if request.method=="POST":
        conn.execute("UPDATE releves_tar SET date_releve = ?, index_compteur = ?, traitements = ? WHERE id = ?",(
            request.form["date_releve"], request.form["index_compteur"].strip(), request.form.get("traitements","").strip(), id))
        conn.commit(); conn.close(); return redirect(url_for("tar.detail",id=id))
    conn.close(); return render_template("tar/form.html",releve=releve)

@tar_bp.route("/<int:id>/supprimer", methods=["POST"])
def supprimer(id):
    conn=get_db_connection(); conn.execute("DELETE FROM releves_tar WHERE id = ?",(id,)); conn.commit(); conn.close()
    return redirect(url_for("tar.liste"))
