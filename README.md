# BACKEND DOF – API Flask + MySQL (dofdb)

Este proyecto expone una **API REST en Flask** conectada a MySQL (`dofdb`) para tres casos de uso:

1) **Recuperar archivos DOF (últimas 5 publicaciones)**  
   - **GET** `/dof/files`  
   - Lista de archivos con metadatos de su publicación.

2) **Visualizar archivo completo**  
   - **GET** `/dof/files/{file_id}`  
   - Metadatos del archivo + sus páginas (`pages`) + resumen más reciente si existe (`summaries`).

3) **Descargar PDF o ZIP (PDF + resumen)**  
   - **GET** `/dof/files/{file_id}/download`  
   - Parámetro opcional: `bundle=zip` para recibir un `.zip` con `document.pdf` y `summary.txt`.  
   - La descarga resuelve primero `files.public_url` (si es `http(s)`), luego intenta `files.storage_uri` (ruta local). Si `storage_uri` es `s3://` debes proporcionar una URL pública/presignada en `public_url`.

La API sigue la especificación funcional definida en `api-dof-files.yaml` y está pensada para integrarse con pipelines de ingestión/OCR y NLP.

---

## 1) Requisitos

- Python 3.x  
- Docker (para MySQL en contenedor)  
- Librerías de Python:
  ```bash
  pip install mysql-connector-python flask flask-cors requests
  ```

---

## 2) Levantar MySQL en Codespaces (o local con Docker)

1. **Crear/arrancar contenedor MySQL (puerto 3306):**
   ```bash
   docker run --name mysql-container -e MYSQL_ROOT_PASSWORD=contrasena -p 3306:3306 -d mysql:latest
   ```

2. **Crear la base `dofdb` y cargar la estructura (archivo seguro):**
   - Guarda el dump **SAFE** como `dofdb_estructura.sql` (el que incluye `public_url` en `files` y evita SETs problemáticos).
   - Ejecuta:
   ```bash
   # Crea la base si no existe
   docker exec -i mysql-container mysql -u root -pcontrasena -e "CREATE DATABASE IF NOT EXISTS dofdb;"
   # Carga la estructura (CREATE TABLE ...)
   docker exec -i mysql-container mysql -u root -pcontrasena dofdb < dofdb_estructura.sql
   ```

3. **(Opcional) Entrar a MySQL interactivo:**
   ```bash
   docker exec -it mysql-container mysql -u root -pcontrasena
   ```

> **DB_CONFIG** en `app.py` debe tener la misma contraseña/host/puerto:
```python
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "contrasena",
    "database": "dofdb",
    "port": 3306,
}
```

---

## 3) Insertar datos de ejemplo (mínimos para probar los 3 endpoints)

**Importante:** Para probar `/download`, usa **una URL pública** en `public_url` o un **PDF local existente** en `storage_uri`.

### Opción A — Usar una URL pública (rápido)
```sql
USE dofdb;

INSERT INTO publications (id, dof_date, issue_number, type, source_url, status)
VALUES (1,'2025-11-06','10','DOF','https://dof.gob.mx/nota_detalle.php?codigo=1234567','parsed')
ON DUPLICATE KEY UPDATE dof_date=VALUES(dof_date);

INSERT INTO files (id, publication_id, storage_uri, public_url, mime, bytes, sha256, has_ocr, pages_count)
VALUES (
  1, 1,
  's3://dof-storage/2025-11-06/001.pdf',
  'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
  'application/pdf', 2048000, 'a2b8e8c9d1f34b8d7e42e6c8f77f74a1b2aaaaaa', 1, 2
)
ON DUPLICATE KEY UPDATE publication_id=VALUES(publication_id);

INSERT INTO pages (file_id, page_no, text, image_uri) VALUES
(1,1,'Texto extraído de la primera página...','https://s3.amazonaws.com/dof-storage/2025-11-06/page1.png'),
(1,2,'Texto extraído de la segunda página...','https://s3.amazonaws.com/dof-storage/2025-11-06/page2.png')
ON DUPLICATE KEY UPDATE text=VALUES(text);

INSERT INTO summaries (object_type, object_id, model, summary_text, confidence)
VALUES ('publication',1,'gpt-5','Resumen del decreto: principales incentivos fiscales para PYMES.',0.95);
```

### Opción B — Usar un PDF local
1. Copia un PDF al workspace (ej. `./data/ejemplo.pdf`).  
2. Actualiza la fila:
```sql
UPDATE files
SET public_url = NULL,
    storage_uri = '/workspaces/DOFDB_ac/data/ejemplo.pdf'
WHERE id = 1;
```

---

## 4) Ejecutar la API (Flask)

En tu Codespace/terminal del repo:

```bash
pip install mysql-connector-python flask flask-cors requests
python app.py
```

- En Codespaces se abrirá la **Port 8000**. Pulsa **Open in Browser** cuando aparezca la notificación.  
- Localmente, ve a: <http://127.0.0.1:8000>

---

## 5) Probar los 3 endpoints (con `curl`)

> Si usas navegador, basta con abrir las URLs. Con `curl`, además puedes guardar archivos.

### 5.1) Últimas 5 publicaciones (lista)
```bash
curl -s http://127.0.0.1:8000/dof/files | python -m json.tool
```

### 5.2) Detalle de un archivo (metadatos + páginas + summary)
```bash
curl -s http://127.0.0.1:8000/dof/files/1 | python -m json.tool
```

### 5.3) Descargar PDF (por defecto) o ZIP (PDF + summary.txt)

- **PDF directo:**
```bash
curl -L -o dof_1.pdf "http://127.0.0.1:8000/dof/files/1/download"
```

- **ZIP con PDF + resumen:**
```bash
curl -L -o dof_1_bundle.zip "http://127.0.0.1:8000/dof/files/1/download?bundle=zip"
```

> Si obtienes un ZIP vacío o error, revisa que `public_url` sea una URL `http(s)` válida **o** que `storage_uri` apunte a un PDF **existente** y legible desde el servidor.

---

## 6) Notas finales y buenas prácticas

- `public_url` simplifica la descarga (ideal con pre-signed URLs). Si sólo usas `s3://...`, el backend necesita una URL pública o presignada.  
- Para producción, agrega autenticación, logging y maneja límites/paginación en `/dof/files`.  
- Índices útiles ya incluidos: `idx_publications_dof_date`, `idx_files_pub_date`, `uq_pages_file_page`.

---

