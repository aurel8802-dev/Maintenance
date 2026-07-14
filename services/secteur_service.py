SECTEURS_CORRESPONDANCES = {
    "axame": "Axame",
    "batiments": "Bâtiments",
    "bâtiments": "Bâtiments",
    "extérieur": "Extérieur",
    "exterieur": "Extérieur",
    "hall 1": "Hall 1",
    "hall1": "Hall 1",
    "hall 2": "Hall 2",
    "hall2": "Hall 2",
    "mag auto": "Mag Auto",
    "maintenance": "Maintenance",
    "pont n°2": "Pont n°2",
    "pont n 2": "Pont n°2",
    "pont n2": "Pont n°2",
    "poste ht": "Poste HT",
    "pourfendeuse": "Pourfendeuse",
    "refendeuse": "Pourfendeuse",
    "réseau eau": "Réseau Eau",
    "reseau eau": "Réseau Eau",
    "réseau d'eau": "Réseau Eau",
    "reseau d'eau": "Réseau Eau",
    "tuberie": "Tuberie",
    "v2": "V2",
    "v 2": "V2",
    "v3": "V3",
    "v 3": "V3",
    "v2-v3": "V2-V3",
    "v2 - v3": "V2-V3",
    "v2 / v3": "V2-V3",
    "v6": "V6",
    "v 6": "V6",
    "non renseigné": None,
    "non renseigne": None,
}


def normaliser_nom_secteur(nom):
    if nom is None:
        return None

    nom_nettoye = str(nom).strip()

    if not nom_nettoye:
        return None

    return SECTEURS_CORRESPONDANCES.get(
        nom_nettoye.lower(),
        nom_nettoye
    )


def fusionner_donnees_secteur(
    conn,
    secteur_source_id,
    secteur_destination_id
):
    conn.execute("""
        UPDATE demandes_intervention
        SET secteur_id = ?
        WHERE secteur_id = ?
    """, (
        secteur_destination_id,
        secteur_source_id
    ))

    conn.execute("""
        UPDATE rapports_intervention
        SET secteur_id = ?
        WHERE secteur_id = ?
    """, (
        secteur_destination_id,
        secteur_source_id
    ))

    conn.execute("""
        UPDATE demandeurs
        SET secteur_id = ?
        WHERE secteur_id = ?
    """, (
        secteur_destination_id,
        secteur_source_id
    ))


def detacher_donnees_secteur(conn, secteur_id):
    conn.execute("""
        UPDATE demandes_intervention
        SET secteur_id = NULL
        WHERE secteur_id = ?
    """, (secteur_id,))

    conn.execute("""
        UPDATE rapports_intervention
        SET secteur_id = NULL
        WHERE secteur_id = ?
    """, (secteur_id,))

    conn.execute("""
        UPDATE demandeurs
        SET secteur_id = NULL
        WHERE secteur_id = ?
    """, (secteur_id,))


def nettoyer_secteurs_base(conn):
    secteurs = conn.execute("""
        SELECT id, nom
        FROM secteurs
        ORDER BY id
    """).fetchall()

    nombre_fusionnes = 0
    nombre_supprimes = 0

    for secteur in secteurs:
        secteur_id = secteur["id"]
        ancien_nom = secteur["nom"]
        nom_normalise = normaliser_nom_secteur(ancien_nom)

        if nom_normalise is None:
            detacher_donnees_secteur(conn, secteur_id)

            conn.execute("""
                DELETE FROM secteurs
                WHERE id = ?
            """, (secteur_id,))

            nombre_supprimes += 1
            continue

        secteur_officiel = conn.execute("""
            SELECT id, nom
            FROM secteurs
            WHERE LOWER(TRIM(nom)) = LOWER(TRIM(?))
            ORDER BY
                CASE WHEN nom = ? THEN 0 ELSE 1 END,
                id
            LIMIT 1
        """, (
            nom_normalise,
            nom_normalise
        )).fetchone()

        if secteur_officiel:
            secteur_officiel_id = secteur_officiel["id"]
        else:
            cursor = conn.execute("""
                INSERT INTO secteurs (nom)
                VALUES (?)
            """, (nom_normalise,))

            secteur_officiel_id = cursor.lastrowid

        if secteur_id != secteur_officiel_id:
            fusionner_donnees_secteur(
                conn,
                secteur_id,
                secteur_officiel_id
            )

            conn.execute("""
                DELETE FROM secteurs
                WHERE id = ?
            """, (secteur_id,))

            nombre_fusionnes += 1

        elif ancien_nom != nom_normalise:
            conn.execute("""
                UPDATE secteurs
                SET nom = ?
                WHERE id = ?
            """, (
                nom_normalise,
                secteur_id
            ))

    return nombre_fusionnes, nombre_supprimes