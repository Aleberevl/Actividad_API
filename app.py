# app.py
# Ejecuta con: python app.py
# Requiere:
#   pip install mysql-connector-python flask flask-cors requests

import io
import os
import zipfile
import requests
import mysql.connector
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ----------------------------------------------------------------------
# Configuración de la Conexión a la Base de Datos
# ----------------------------------------------------------------------
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "contrasena",   # ajusta si usaste otra
    "database": "dofdb",
    "port": 3306,
}

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        return None

# ----------------------------------------------------------------------
# Utilidades para resolver/obtener el PDF desde storage_uri o download_uri
# ----------------------------------------------------------------------
def _fetch_pdf_bytes(storage_uri: str, download_uri: str | None = None) -> bytes:
    """
    Intenta obtener el PDF en este orden:
    1) Si download_uri es http(s), la usa directamente.
    2) Si storage_uri es http(s), la usa.
    3) Si storage_uri es una ruta local, la abre localmente.
    4) Si storage_uri es s3:// y no hay download_uri http(s), devolvemos NotImplemented.
    """
    url = download_uri or storage_uri

    # Caso http(s)
    if isinstance(url, str) and url.lower().startswith(("http://", "https://")):
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        return r.content

    # Caso ruta local absoluta o relativa
    if os.path.exists(storage_uri):
        with open(storage_uri, "rb") as f:
            return f.read()

    # Caso s3://... sin URL pública configurada
    if isinstance(storage_uri, str) and storage_uri.lower().startswith("s3://"):
        raise NotImplementedError(
            "storage_uri con esquema s3:// requiere 'download_uri' http(s) o presignado."
        )

    # Si nada funcionó
    raise FileNotFoundError("No fue posible resolver/obtener el PDF desde storage_uri/download_uri.")

def _safe_filename(base: str) -> str:
    # Limpia nombre para descarga
    return "".join(c for c in base if c.isalnum() or c in ("-", "_", ".", " ")).strip() or "document"

# ----------------------------------------------------------------------
# 1) GET /dof/files  -> lista de archivos + datos básicos de publicación
# ----------------------------------------------------------------------
@app.route("/dof/files", methods=["GET"])
def get_files():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT
            f.id,
            f.publication_id,
            f.storage_uri,
            f.mime,
            f.bytes,
            f.sha256,
            f.has_ocr,
            f.pages_count,
            p.dof_date   AS publication_date,
            p.type       AS publication_type,
            p.source_url AS source_url
        FROM files f
        JOIN publications p ON f.publication_id = p.id
        ORDER BY p.dof_date DESC, f.id DESC
        LIMIT 5
    """
    # ^ Si quieres TODA la lista, quita el LIMIT 5. Así tal cual devuelve “las últimas 5 publicaciones”.

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        for r in rows:
            r["has_ocr"] = bool(r["has_ocr"])
        return jsonify(rows), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar archivos DOF: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# 2) GET /dof/files/{file_id} -> detalle de archivo + páginas + resumen
# ----------------------------------------------------------------------
@app.route("/dof/files/<int:file_id>", methods=["GET"])
def get_file_detail(file_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        # Datos del archivo
        cursor.execute(
            """
            SELECT
                id,
                publication_id,
                storage_uri,
                mime,
                has_ocr
            FROM files
            WHERE id = %s
            """,
            (file_id,),
        )
        file_row = cursor.fetchone()

        if not file_row:
            return jsonify({"message": "Archivo DOF no encontrado"}), 404

        # Páginas del archivo
        cursor.execute(
            """
            SELECT
                page_no,
                text,
                image_uri
            FROM pages
            WHERE file_id = %s
            ORDER BY page_no
            """,
            (file_id,),
        )
        pages = cursor.fetchall()

        # Resumen opcional desde summaries
        cursor.execute(
            """
            SELECT summary_text
            FROM summaries
            WHERE object_type = 'publication'
              AND object_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (file_row["publication_id"],),
        )
        summary_row = cursor.fetchone()
        summary_text = summary_row["summary_text"] if summary_row else None

        result = {
            "id": file_row["id"],
            "publication_id": file_row["publication_id"],
            "storage_uri": file_row["storage_uri"],
            "mime": file_row["mime"],
            "has_ocr": bool(file_row["has_ocr"]),
            "pages": pages,
            "summary": summary_text,
        }

        return jsonify(result), 200

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar archivo DOF: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# 3) GET /dof/files/{file_id}/download -> Descargar PDF o ZIP (PDF + summary.txt)
#    Query param opcional: bundle=zip  (por defecto entrega el PDF directo)
# ----------------------------------------------------------------------
@app.route("/dof/files/<int:file_id>/download", methods=["GET"])
def download_file(file_id):
    bundle = request.args.get("bundle", "pdf").lower().strip()  # 'pdf' | 'zip'

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor(dictionary=True)

    try:
        # Traemos info del file + publicación, usando public_url (no download_uri)
        cursor.execute(
            """
            SELECT
                f.id,
                f.publication_id,
                f.storage_uri,
                f.public_url,              -- <--- aquí usamos public_url
                f.mime,
                p.dof_date,
                p.type AS publication_type
            FROM files f
            JOIN publications p ON f.publication_id = p.id
            WHERE f.id = %s
            """,
            (file_id,),
        )
        frow = cursor.fetchone()
        if not frow:
            return jsonify({"message": "Archivo DOF no encontrado"}), 404

        # Intentamos obtener el PDF; si hay public_url http(s), se usa primero
        try:
            pdf_bytes = _fetch_pdf_bytes(frow["storage_uri"], frow.get("public_url"))
        except NotImplementedError as nie:
            return jsonify({"message": str(nie)}), 501
        except Exception as e:
            return jsonify({"message": f"No se pudo obtener el PDF: {e}"}), 502

        # Nombre base para el archivo
        base_name = f"DOF_{frow['dof_date']}_{frow['publication_type']}_file{frow['id']}"
        base_name = _safe_filename(base_name)

        if bundle == "zip":
            # Conseguimos resumen si existe
            cursor.execute(
                """
                SELECT summary_text
                FROM summaries
                WHERE object_type = 'publication'
                  AND object_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (frow["publication_id"],),
            )
            srow = cursor.fetchone()
            summary_text = srow["summary_text"] if srow else "Sin resumen disponible."

            # Empaquetamos ZIP en memoria: document.pdf + summary.txt
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("document.pdf", pdf_bytes)
                zf.writestr("summary.txt", summary_text)
            zip_buffer.seek(0)

            return send_file(
                zip_buffer,
                mimetype="application/zip",
                as_attachment=True,
                download_name=f"{base_name}.zip",
            )

        # Por defecto: PDF directo
        pdf_buffer = io.BytesIO(pdf_bytes)
        pdf_buffer.seek(0)
        mimetype = frow["mime"] or "application/pdf"
        return send_file(
            pdf_buffer,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{base_name}.pdf",
        )

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al preparar descarga: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# Inicialización
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Servidor Flask iniciado. Accede a http://127.0.0.1:8000")
    app.run(port=8000, debug=True)