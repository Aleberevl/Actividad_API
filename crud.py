# pip install mysql-connector-python
import mysql.connector
from datetime import datetime, timedelta
import random

# ----------------------------------------------------
# 1. Configuración de Conexión
# ----------------------------------------------------
# Nota: Asegúrate de que tu contenedor Docker esté corriendo con:
# host="127.0.0.1", user="root", password="contrasena", database="dofdb", port=3306
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "contrasena",
    "database": "dofdb",
    "port": 3306
}

conn = None
cursor = None
try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
except mysql.connector.Error as err:
    print(f"Error al conectar con MySQL: {err}")
    print("Asegúrate de que el contenedor 'mysql-container' esté corriendo y el puerto 3306 esté accesible.")
    exit()

# ----------------------------------------------------
# 2. Función Auxiliar para Inserción
# ----------------------------------------------------

def insert_record(table_name, columns, values):
    """Función genérica para insertar un registro y obtener el ID."""
    cols_str = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(values))
    sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
    
    try:
        cursor.execute(sql, values)
        conn.commit()
        last_id = cursor.lastrowid
        print(f"  ✅ Registro creado en '{table_name}' con ID: {last_id}")
        return last_id
    except mysql.connector.Error as err:
        print(f"  ❌ Error al insertar en '{table_name}': {err}")
        conn.rollback()
        return None

# ----------------------------------------------------
# 3. Creación de Datos de Prueba (Fixture)
# ----------------------------------------------------

print("--- INSERCIÓN DE DATOS DE PRUEBA EN ORDEN DE DEPENDENCIA ---")

# Variables para almacenar los IDs de FK
IDs = {}

# 1. users
IDs['user_id'] = insert_record(
    "users",
    ["email", "password_hash", "full_name", "status", "role"],
    ["usuario@dof.gob.mx", "hash_seguro_123", "Alejandro B.", "active", "admin"]
)

# 2. ingestion_jobs (Independiente)
IDs['job_id'] = insert_record(
    "ingestion_jobs",
    ["run_at", "source", "status"],
    [datetime.now(), "crawler", "completed"]
)

# 3. publications (Núcleo)
IDs['publication_id'] = insert_record(
    "publications",
    ["dof_date", "issue_number", "type", "source_url", "sha256", "status"],
    [
        datetime(2025, 11, 6).date(), 
        "478(4)", 
        "DOF", 
        "http://www.dof.gob.mx/478_4.pdf", 
        "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6", 
        "summarized"
    ]
)

# 4. tasks (Depende de publications)
IDs['task_id'] = insert_record(
    "tasks",
    ["publication_id", "task_type", "status", "started_at", "finished_at"],
    [IDs['publication_id'], "summarize", "done", datetime.now() - timedelta(minutes=5), datetime.now()]
)

# 5. files (Depende de publications)
IDs['file_id'] = insert_record(
    "files",
    ["publication_id", "storage_uri", "mime", "bytes", "sha256", "has_ocr", "pages_count"],
    [IDs['publication_id'], "s3://dof-files/2025/11/06/file.pdf", "application/pdf", 123456, "f6e5d4c3b2a109877890123456789012", True, 25]
)

# 6. pages (Depende de files)
page_text = "Texto de la página 1. Contiene la nueva Ley de Fomento a la Inversión."
IDs['page_id'] = insert_record(
    "pages",
    ["file_id", "page_no", "text", "tsv", "image_uri", "checksum"],
    [IDs['file_id'], 1, page_text, page_text, "s3://dof-images/p1.jpg", "chk-12345"]
)

# 7. sections (Depende de publications)
IDs['section_id'] = insert_record(
    "sections",
    ["publication_id", "name", "seq", "page_start", "page_end"],
    [IDs['publication_id'], "SECRETARIA DE HACIENDA Y CREDITO PUBLICO", 1, 1, 15]
)

# 8. items (Depende de sections)
raw_item_text = "DECRETO por el que se modifica la Ley de Inversión. Texto completo del artículo 1..."
IDs['item_id'] = insert_record(
    "items",
    ["section_id", "item_type", "title", "issuing_entity", "reference_code", "page_from", "page_to", "raw_text", "tsv"],
    [
        IDs['section_id'], 
        "Decreto", 
        "Decreto de Modificación a la Ley de Inversión", 
        "Poder Ejecutivo Federal", 
        "DOF-DECRETO-001", 
        3, 
        8, 
        raw_item_text, 
        raw_item_text
    ]
)

# 9. entities
IDs['entity_id'] = insert_record(
    "entities",
    ["name", "type", "norm_name"],
    ["Ley de Fomento a la Inversión", "Ley", "ley_de_fomento_a_la_inversion"]
)

# 10. item_entities (N-a-N)
insert_record(
    "item_entities",
    ["item_id", "entity_id", "evidence_span"],
    [IDs['item_id'], IDs['entity_id'], "Sección 1, Párrafo 5"]
)

# 11. summaries (Depende de items y users)
IDs['summary_id'] = insert_record(
    "summaries",
    ["object_type", "object_id", "model", "model_version", "lang", "summary_text", "confidence", "created_by"],
    [
        "item", 
        IDs['item_id'], 
        "Gemini-2.5-Pro", 
        "v2.5", 
        "es", 
        "Resumen del decreto: principal cambio en incentivos fiscales para PYMES.", 
        0.995, 
        IDs['user_id']
    ]
)

# 12. exports (Depende de users)
IDs['export_id'] = insert_record(
    "exports",
    ["user_id", "format", "status", "storage_uri", "created_at"],
    [IDs['user_id'], "PDF", "completed", "s3://dof-exports/export-001.pdf", datetime.now()]
)

# 13. retention_queue (Ejemplo para borrar el summary en 24h)
delete_time = datetime.now() + timedelta(hours=24)
insert_record(
    "retention_queue",
    ["object_type", "object_id", "delete_after", "reason"],
    ["summary", IDs['summary_id'], delete_time, "ttl_24h"]
)


print("\n--- RESUMEN DE IDs CREADOS ---")
for key, value in IDs.items():
    print(f"{key}: {value}")

# ----------------------------------------------------
# 4. Cierre de Conexión
# ----------------------------------------------------
print("\nConexión cerrada.")
cursor.close()
conn.close()
