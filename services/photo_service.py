import os

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from flask import current_app


load_dotenv()


cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)


def cloudinary_configured():
    """Vérifie que les identifiants Cloudinary sont disponibles."""
    return all([
        os.getenv("CLOUDINARY_CLOUD_NAME"),
        os.getenv("CLOUDINARY_API_KEY"),
        os.getenv("CLOUDINARY_API_SECRET"),
    ])


def enregistrer_photo(conn, type_element, element_id, photo):
    print("✅ Fonction enregistrer_photo appelée", flush=True)

    print(
        "Photo reçue :",
        photo.filename if photo else "Aucune photo",
        flush=True
    )

    print(
        "Cloudinary configuré :",
        cloudinary_configured(),
        flush=True
    )

    if not photo or not photo.filename:
        print("❌ Aucune photo transmise par le formulaire", flush=True)
        return None

    if cloudinary_configured():
        print("☁️ Envoi de la photo vers Cloudinary", flush=True)

        resultat = cloudinary.uploader.upload(
            photo,
            folder=f"gm_interventions/{type_element}s",
            resource_type="image",
        )

        url_photo = resultat.get("secure_url")
        public_id = resultat.get("public_id")
        nom_fichier = (
            resultat.get("original_filename")
            or photo.filename
        )

        print("✅ Photo envoyée :", url_photo, flush=True)

        try:
            conn.execute("""
                INSERT INTO photos (
                    type_element,
                    element_id,
                    nom_fichier,
                    url_photo,
                    public_id
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                type_element,
                element_id,
                nom_fichier,
                url_photo,
                public_id
            ))

        except Exception:
            if public_id:
                cloudinary.uploader.destroy(
                    public_id,
                    resource_type="image"
                )
            raise

        return url_photo

    print("⚠️ Cloudinary absent : stockage local utilisé", flush=True)

    return enregistrer_photo_locale(
        conn,
        type_element,
        element_id,
        photo
    )


def enregistrer_photo_locale(
    conn,
    type_element,
    element_id,
    photo
):
    """Solution de secours locale lorsque Cloudinary n'est pas configuré."""
    from uuid import uuid4
    from werkzeug.utils import secure_filename

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
            INSERT INTO photos (
                type_element,
                element_id,
                nom_fichier,
                url_photo,
                public_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            type_element,
            element_id,
            filename,
            None,
            None
        ))

    except Exception:
        if os.path.isfile(photo_path):
            os.remove(photo_path)
        raise

    return filename


def recuperer_photos(conn, type_element, element_id):
    """Retourne toutes les photos associées à une demande ou un rapport."""
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
    Supprime toutes les photos associées.

    Les photos Cloudinary sont supprimées du cloud.
    Les anciennes photos locales sont supprimées du disque.
    """
    photos = recuperer_photos(
        conn,
        type_element,
        element_id
    )

    for photo in photos:
        public_id = photo["public_id"]
        nom_fichier = photo["nom_fichier"]

        if public_id and cloudinary_configured():
            cloudinary.uploader.destroy(
                public_id,
                resource_type="image",
                invalidate=True
            )

        elif nom_fichier:
            photo_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"],
                nom_fichier
            )

            if os.path.isfile(photo_path):
                os.remove(photo_path)

    conn.execute("""
        DELETE FROM photos
        WHERE type_element = ?
          AND element_id = ?
    """, (
        type_element,
        element_id
    ))

def supprimer_photo(conn, photo_id):
    """
    Supprime une seule photo de Cloudinary ou du stockage local,
    puis retire sa ligne de la base de données.
    """
    photo = conn.execute("""
        SELECT *
        FROM photos
        WHERE id = ?
    """, (photo_id,)).fetchone()

    if photo is None:
        return False

    public_id = photo["public_id"]
    nom_fichier = photo["nom_fichier"]

    if public_id and cloudinary_configured():
        cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
            invalidate=True
        )

    elif nom_fichier:
        photo_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            nom_fichier
        )

        if os.path.isfile(photo_path):
            os.remove(photo_path)

    conn.execute("""
        DELETE FROM photos
        WHERE id = ?
    """, (photo_id,))

    return True