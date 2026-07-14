import os
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


def enregistrer_photo(conn, type_element, element_id, photo):
    """
    Enregistre une photo et crée sa référence en base.
    """

    if not photo or not photo.filename:
        return None

    original_filename = secure_filename(photo.filename)

    if not original_filename:
        return None

    extension = os.path.splitext(original_filename)[1].lower()

    filename = f"{uuid4().hex}{extension}"

    photo_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        filename
    )

    photo.save(photo_path)

    try:
        conn.execute("""
            INSERT INTO photos
            (
                type_element,
                element_id,
                nom_fichier
            )
            VALUES (?, ?, ?)
        """, (
            type_element,
            element_id,
            filename
        ))

    except Exception:

        if os.path.exists(photo_path):
            os.remove(photo_path)

        raise

    return filename


def recuperer_photos(conn, type_element, element_id):
    """
    Retourne toutes les photos d'un élément.
    """

    return conn.execute("""
        SELECT *
        FROM photos
        WHERE type_element = ?
        AND element_id = ?
        ORDER BY date_ajout DESC
    """, (
        type_element,
        element_id
    )).fetchall()


def supprimer_photos(conn, type_element, element_id):
    """
    Supprime les photos de la base
    et les fichiers du disque.
    """

    photos = recuperer_photos(
        conn,
        type_element,
        element_id
    )

    for photo in photos:

        filename = photo["nom_fichier"]

        if not filename:
            continue

        path = os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            filename
        )

        if os.path.isfile(path):
            os.remove(path)

    conn.execute("""
        DELETE FROM photos
        WHERE type_element = ?
        AND element_id = ?
    """, (
        type_element,
        element_id
    ))