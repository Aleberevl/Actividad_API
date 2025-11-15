# tools/reindex_pages.py
import os, glob
import mysql.connector
from PyPDF2 import PdfReader

DB_CONFIG = dict(host="127.0.0.1", user="root", password="contrasena", database="dofdb", port=3306)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(PROJECT_ROOT, "DOF_PDF")

def main(only_missing=True):
    cn = mysql.connector.connect(**DB_CONFIG)
    cur = cn.cursor()

    # Trae storage_uri y pages_count actuales
    cur.execute("SELECT storage_uri, pages_count FROM files")
    current = {row[0]: row[1] for row in cur.fetchall()}

    updates = []
    for pdf in glob.glob(os.path.join(BASE, "*.pdf")):
        name = os.path.basename(pdf)
        # si only_missing, actualiza solo nulos/0; si no, recalcula siempre
        if only_missing and current.get(name, 0):
            continue
        try:
            pages = len(PdfReader(pdf).pages)
        except Exception:
            pages = 0
        updates.append((pages, name))

    if updates:
        cur.executemany("UPDATE files SET pages_count=%s WHERE storage_uri=%s", updates)
        cn.commit()
        print("Actualizados:", dict(updates))
    else:
        print("No hay cambios.")

    cur.close(); cn.close()

if __name__ == "__main__":
    main(only_missing=True)
