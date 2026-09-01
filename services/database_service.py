from contextlib import contextmanager

from database import get_db_connection


@contextmanager
def connexion_db():
    """
    Ouvre une connexion pour les opérations de lecture.

    La connexion est toujours fermée, même si une erreur survient.
    """
    conn = get_db_connection()

    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction_db():
    """
    Ouvre une connexion pour les opérations qui modifient la base.

    - valide automatiquement avec commit si tout fonctionne ;
    - annule avec rollback en cas d'erreur ;
    - ferme toujours la connexion.
    """
    conn = get_db_connection()

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()