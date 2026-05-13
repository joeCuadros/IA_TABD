import os
import pandas as pd
import psycopg2
import numpy as np
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()

# Config desde .env
CONN = dict(
    host     = os.getenv("POSTGRES_HOST", "localhost"),
    port     = int(os.getenv("POSTGRES_PORT", 5432)),
    dbname   = os.getenv("POSTGRES_DB"),
    user     = os.getenv("POSTGRES_USER"),
    password = os.getenv("POSTGRES_PASSWORD"),
)

# Rutas de los parquets 
RUTA_SQL       = "data/data_sql.parquet"
RUTA_EMBEDDINGS = "data/embeddings_output.parquet"

# Cargar parquets 
print("Cargando data_sql.parquet...")
df_sql = pd.read_parquet(RUTA_SQL)
df_sql["codigo_infobras"] = df_sql["codigo_infobras"].astype(str).str.strip()

# Limpiar columnas numericas 
COLS_NUMERIC = [
    "monto_viable_aprobado",
    "monto_viable_actualizado",
    "monto_aprobado_en_soles",
    "monto_de_aprobacion_de_expediente_tecnico",
    "monto_del_contrato_en_soles",
    "monto_de_ejecucion_financiera_de_la_obra",
    "monto_de_adicionales_de_obra_en_soles",
    "monto_de_deductivos_de_obra_en_soles",
    "costo_de_la_obra_en_soles",
    "monto_total_devengado_del_proyecto",
    "avance_fisico_real_acumulado",
    "avance_fisico_programado_acumulado",
    "porcentaje_de_ejecucion_financiera",
    "plazo_de_ejecucion_en_dias",
    "nuevo_plazo_de_ejecucion_en_dias",
    "n_dias_de_modificaciones_de_plazo",
    "n_de_adicionales_de_obra",
    "n_de_deductivos_de_obra",
    "n_de_modificaciones",
    "n_de_controversias",
    "n_informes_de_control",
    "n_comentarios_ciudadanos",
]

for col in COLS_NUMERIC:
    if col in df_sql.columns:
        df_sql[col] = (
            df_sql[col]
            .astype(str)
            .str.strip()
            .str.replace(r"(\d)\s+(\d)", r"\1.\2", regex=True) 
            .str.replace(",", ".", regex=False)                
            .replace({"nan": None, "": None, "None": None})
        )
        df_sql[col] = pd.to_numeric(df_sql[col], errors="coerce")
print(f"Filas SQL      : {len(df_sql):,}")


print("Cargando embeddings_output.parquet...")
df_emb = pd.read_parquet(RUTA_EMBEDDINGS)
df_emb["codigo_infobras"] = df_emb["codigo_infobras"].astype(str).str.strip()
print(f"Filas Embeddings: {len(df_emb):,}")

# Conectar 
print("\nConectando a PostgreSQL...")
conn = psycopg2.connect(**CONN)
register_vector(conn)
cur = conn.cursor()
print("Conectado.")

#  Helper: insert en batches
def insert_batches(cur, conn, query, rows, batch_size=2000, label=""):
    total = len(rows)
    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        cur.executemany(query, batch)
        conn.commit()
        print(f"  {label}: {min(i + batch_size, total):,}/{total:,}", end="\r")
    print()

# Insertar obras_sql
print("\nInsertando obras_sql...")

cols = df_sql.columns.tolist()
placeholders = ", ".join(["%s"] * len(cols))
col_names    = ", ".join(cols)
update_set   = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "codigo_infobras")

query_sql = f"""
    INSERT INTO obras_sql ({col_names})
    VALUES ({placeholders})
    ON CONFLICT (codigo_infobras) DO UPDATE SET {update_set};
"""

# Convertir NaN a None para que psycopg2 los meta como NULL
def row_to_tuple(row):
    return tuple(None if pd.isna(v) else v for v in row)

rows_sql = [row_to_tuple(row) for row in df_sql.itertuples(index=False)]
insert_batches(cur, conn, query_sql, rows_sql, label="obras_sql")
print(f"  obras_sql listo: {len(rows_sql):,} filas")

# Insertar obras_embeddings 
print("\nInsertando obras_embeddings...")

query_emb = """
    INSERT INTO obras_embeddings (codigo_infobras, embedding)
    VALUES (%s, %s)
    ON CONFLICT (codigo_infobras) DO UPDATE
        SET embedding = EXCLUDED.embedding;
"""

rows_emb = [
    (row.codigo_infobras, np.array(row.embedding, dtype=np.float32))
    for row in df_emb.itertuples(index=False)
]
insert_batches(cur, conn, query_emb, rows_emb, label="embeddings")
print(f"  obras_embeddings listo: {len(rows_emb):,} filas")

#  Crear índice HNSW ahora que la tabla esta llena 
print("\nCreando índice HNSW...")
cur.execute("""
    CREATE INDEX IF NOT EXISTS obras_embeddings_hnsw
    ON obras_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
""")
conn.commit()
print("  Índice creado.")

# Verificar
cur.execute("SELECT COUNT(*) FROM obras_sql;")
print(f"\nobras_sql      : {cur.fetchone()[0]:,} filas")

cur.execute("SELECT COUNT(*) FROM obras_embeddings;")
print(f"obras_embeddings: {cur.fetchone()[0]:,} filas")

cur.close()
conn.close()
print("\nListo.")