import pandas as pd
from pathlib import Path
import re
from collections import defaultdict

NOMBRE = "DataSet-Obras-Publicas 12-05-2026"
BASE = Path("data")
XLSX_PURO = BASE / f"{NOMBRE}.xlsx"
PARQUET_COMPRIMIDO = BASE / f"{NOMBRE}.parquet"
PARQUET_PROCESADO_COLAB = BASE / f"data_procesada.parquet"
PARQUET_SQL = BASE / f"data_sql.parquet"

def imprimir_color(texto):
    print(f"\033[32m{texto}\033[0m")

# Fase 0: Comprimir data para facil lectura
if PARQUET_COMPRIMIDO.exists():
    imprimir_color("Cargando parquet...")
    df = pd.read_parquet(PARQUET_COMPRIMIDO)
else:
    print("Parquet no encontrado")
    print("Leyendo Excel...")
    df = pd.read_excel(
        XLSX_PURO,
        header=3
    )
    imprimir_color("Guardando parquet...")
    df.to_parquet(
        PARQUET_COMPRIMIDO,
        index=False
    )

# Fase 1: Normalizar columnas
def normalizar_columnas(cols):    
    def normalizar_columna(col):
        col = col.strip().lower()
        reemplazos = {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ñ": "n"
        }
        for a, b in reemplazos.items():
            col = col.replace(a, b)
        col = re.sub(r"[¿?%°]", "", col)
        col = re.sub(r"[^a-z0-9]+", "_", col)
        col = re.sub(r"_+", "_", col)
        return col.strip("_")

    contador = defaultdict(int)
    nuevas_columnas = []
    for c in cols:
        base = normalizar_columna(c)
        contador[base] += 1
        if contador[base] == 1:
            nuevas_columnas.append(base)
        else:
            nuevas_columnas.append(f"{base}_{contador[base]}")

    return nuevas_columnas
df.columns = normalizar_columnas(df.columns)

# Fase 2: Ver Nulls
total_filas = len(df)
nulos_por_columna = (
    df.isnull()
      .sum()
      .sort_values(ascending=False)
)
for columna, cantidad in nulos_por_columna.items():
    porcentaje = (
        cantidad / total_filas
    ) * 100
    texto = (
        f"{columna} -> "
        f"{cantidad}/{total_filas} "
        f"nulos ({porcentaje:.2f}%)"
    )
    # Analizar valores mas comunes
    serie = (
        df[columna]
        .dropna()
        .astype(str)
        .str.strip()
        .str.lower()
    )

    if len(serie) > 0:
        valor_mas_comun = (
            serie.value_counts()
                 .idxmax()
        )
        porcentaje_mas_comun = (
            serie.value_counts(normalize=True)
                 .max()
        ) * 100
        texto += (
            f', mas comun "{str(valor_mas_comun)[:20]}" '
            f'en ({porcentaje_mas_comun:.2f}%)'
        )
    print(texto)

# Fase 3: Guarda columnas importantes
COLS_SQL = [
    # Identificadores
    "codigo_infobras",
    "codigo_unico_de_inversion",
    "codigo_snip",
    "codigo_entidad",

    # Descripción de la obra
    "nombre_de_obra",
    "nombre_proyecto",
    "naturaleza_de_la_obra",
    "tipo_de_obra_clasificador_nivel_1",
    "tipo_de_obra_clasificador_nivel_2",
    "tipo_de_obra_clasificador_nivel_3",
    "modalidad_de_ejecucion_de_la_obra",
    "estado_de_ejecucion",
    "estado_del_proyecto",

    # Entidad
    "entidad_publica",
    "nivel_de_gobierno",
    "sector_de_la_entidad",

    # Ubicación
    "departamento",
    "provincia",
    "distrito",
    "direccion_o_informacion_de_referencia",

    # Montos
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

    # Fechas clave
    "fecha_de_inicio_de_obra",
    "fecha_finalizacion_programada_de_obra",
    "fecha_finalizacion_reprogramada_de_obra",
    "fecha_de_finalizacion_real",
    "fecha_de_aprobacion_del_expediente",
    "fecha_de_aprobacion_de_liquidacion_de_obra",

    # Avance
    "avance_fisico_real_acumulado",
    "avance_fisico_programado_acumulado",
    "porcentaje_de_ejecucion_financiera",
    "plazo_de_ejecucion_en_dias",
    "nuevo_plazo_de_ejecucion_en_dias",
    "n_dias_de_modificaciones_de_plazo",

    # Contratista
    "nombre_o_razon_social_de_la_empresa_o_consorcio",
    "ruc",

    # Flags / contadores útiles
    "existe_paralizacion",
    "tiene_recepcion_total",
    "tiene_liquidacion_de_obra",
    "n_de_adicionales_de_obra",
    "n_de_deductivos_de_obra",
    "n_de_modificaciones",
    "n_de_controversias",
    "n_informes_de_control",
    "n_comentarios_ciudadanos",
    "corresponde_a_un_saldo_de_obra",
    "marca_reconstruccion_con_cambios_si_no",
    "es_una_obra_de_caracter_reservado",
]

COLS_EMBED = [
    "codigo_infobras",           # FK
    "nombre_de_obra",
    "nombre_proyecto",
    "naturaleza_de_la_obra",
    "tipo_de_obra_clasificador_nivel_1",
    "tipo_de_obra_clasificador_nivel_2",
    "tipo_de_obra_clasificador_nivel_3",
    "entidad_publica",
    "sector_de_la_entidad",
    "nivel_de_gobierno",
    "departamento",
    "provincia",
    "distrito",
    "modalidad_de_ejecucion_de_la_obra",
    "estado_de_ejecucion",
    "direccion_o_informacion_de_referencia",
    "comentarios",
]

def filtrar_cols(df, cols):
    disponibles = [c for c in cols if c in df.columns]
    faltantes = set(cols) - set(disponibles)
    if faltantes:
        print(f"columnas no encontradas: {faltantes}")
    return df[disponibles].copy()

def limpiar_strings(df):
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    return df

def construir_texto_embedding(row):
    """
    Concatena los campos textuales en una sola cadena coherente
    que el modelo all-MiniLM-L6-v2 va a encodear.
    """
    partes = []

    if pd.notna(row.get("nombre_de_obra")):
        partes.append(f"Obra: {row['nombre_de_obra']}")

    if pd.notna(row.get("nombre_proyecto")):
        partes.append(f"Proyecto: {row['nombre_proyecto']}")

    niveles = [
        row.get("tipo_de_obra_clasificador_nivel_1"),
        row.get("tipo_de_obra_clasificador_nivel_2"),
        row.get("tipo_de_obra_clasificador_nivel_3"),
    ]
    niveles = [n for n in niveles if pd.notna(n)]
    if niveles:
        partes.append("Tipo: " + " > ".join(niveles))

    if pd.notna(row.get("naturaleza_de_la_obra")):
        partes.append(f"Naturaleza: {row['naturaleza_de_la_obra']}")

    ubic = [
        row.get("departamento"),
        row.get("provincia"),
        row.get("distrito"),
    ]
    ubic = [u for u in ubic if pd.notna(u)]
    if ubic:
        partes.append("Ubicación: " + ", ".join(ubic))

    if pd.notna(row.get("direccion_o_informacion_de_referencia")):
        partes.append(f"Referencia: {row['direccion_o_informacion_de_referencia']}")

    if pd.notna(row.get("entidad_publica")):
        partes.append(f"Entidad: {row['entidad_publica']}")

    if pd.notna(row.get("sector_de_la_entidad")):
        partes.append(f"Sector: {row['sector_de_la_entidad']}")

    if pd.notna(row.get("modalidad_de_ejecucion_de_la_obra")):
        partes.append(f"Modalidad: {row['modalidad_de_ejecucion_de_la_obra']}")

    if pd.notna(row.get("estado_de_ejecucion")):
        partes.append(f"Estado: {row['estado_de_ejecucion']}")

    if pd.notna(row.get("comentarios")) and str(row["comentarios"]).strip():
        partes.append(f"Comentarios: {row['comentarios']}")

    return ". ".join(partes)

# Fase 4: Guardar resultados
imprimir_color("\nPreparando parquet para PostgreSQL...")
df_sql = filtrar_cols(df, COLS_SQL)
df_sql = limpiar_strings(df_sql)
df_sql.to_parquet(PARQUET_SQL, index=False)
imprimir_color(f"Guardado: {PARQUET_SQL}  |  shape: {df_sql.shape}")


imprimir_color("\nPreparando parquet para embeddings en Colab...")
df_embed = filtrar_cols(df, COLS_EMBED)
df_embed = limpiar_strings(df_embed)
df_embed["texto_embedding"] = df_embed.apply(
    construir_texto_embedding, axis=1
)
# Solo nos interesa el ID + el texto ya armado para Colab
df_embed_final = df_embed[["codigo_infobras", "texto_embedding"]].copy()
df_embed_final.to_parquet(PARQUET_PROCESADO_COLAB, index=False)
imprimir_color(f"Guardado: {PARQUET_PROCESADO_COLAB}  |  shape: {df_embed_final.shape}")
