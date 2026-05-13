from __future__ import annotations
 
import os
from contextlib import asynccontextmanager
from typing import Optional
 
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pgvector.psycopg2 import register_vector
from pydantic import BaseModel, Field
from fastembed import TextEmbedding
 
load_dotenv()
 
# Modelo 
MODEL_NAME     = "sentence-transformers/all-MiniLM-L6-v2"
MODEL = None
 
CONN_PARAMS = dict(
    host     = os.getenv("POSTGRES_HOST", "localhost"),
    port     = int(os.getenv("POSTGRES_PORT", 5432)),
    dbname   = os.getenv("POSTGRES_DB"),
    user     = os.getenv("POSTGRES_USER"),
    password = os.getenv("POSTGRES_PASSWORD"),
)
 
 
def get_conn():
    conn = psycopg2.connect(**CONN_PARAMS)
    register_vector(conn)
    return conn
 
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    global MODEL
    print(f"Cargando modelo {MODEL_NAME} con FastEmbed...")
    MODEL = TextEmbedding(MODEL_NAME)
    print("Modelo listo.")
    yield
    print("Shutdown.")
 
 
app = FastAPI(
    title="Obras Públicas API",
    version="1.0.0",
    lifespan=lifespan,
)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajustar en producción
    allow_methods=["*"],
    allow_headers=["*"],
)
 
 
#  SCHEMAS
class BusquedaRequest(BaseModel):
    texto: str = Field(..., min_length=3, description="Texto libre a buscar")
    top:   int = Field(10, ge=1, le=25, description="Resultados a retornar (máx 25)")
 
    # Filtros opcionales
    departamento:                      Optional[str] = None
    provincia:                         Optional[str] = None
    distrito:                          Optional[str] = None
    nivel_de_gobierno:                 Optional[str] = None
    sector_de_la_entidad:              Optional[str] = None
    naturaleza_de_la_obra:             Optional[str] = None
    tipo_de_obra_clasificador_nivel_1: Optional[str] = None
    tipo_de_obra_clasificador_nivel_2: Optional[str] = None
    modalidad_de_ejecucion_de_la_obra: Optional[str] = None
    estado_de_ejecucion:               Optional[str] = None
    monto_min: Optional[float] = Field(None, description="Monto mínimo del contrato en soles")
    monto_max: Optional[float] = Field(None, description="Monto máximo del contrato en soles")
 
 
class ObraResult(BaseModel):
    codigo_infobras:                    str
    nombre_de_obra:                     Optional[str]
    naturaleza_de_la_obra:              Optional[str]
    tipo_de_obra_clasificador_nivel_1:  Optional[str]
    tipo_de_obra_clasificador_nivel_2:  Optional[str]
    tipo_de_obra_clasificador_nivel_3:  Optional[str]
    modalidad_de_ejecucion_de_la_obra:  Optional[str]
    estado_de_ejecucion:                Optional[str]
    entidad_publica:                    Optional[str]
    nivel_de_gobierno:                  Optional[str]
    sector_de_la_entidad:               Optional[str]
    departamento:                       Optional[str]
    provincia:                          Optional[str]
    distrito:                           Optional[str]
    monto_del_contrato_en_soles:        Optional[float]
    avance_fisico_real_acumulado:       Optional[float]
    fecha_de_inicio_de_obra:            Optional[str]
    fecha_de_finalizacion_real:         Optional[str]
    similitud:                          float
 
 
#  HELPERS
def build_where(filters: dict) -> tuple[str, list]:
    clauses = []
    params  = []
 
    text_fields = [
        "departamento", "provincia", "distrito",
        "nivel_de_gobierno", "sector_de_la_entidad",
        "naturaleza_de_la_obra",
        "tipo_de_obra_clasificador_nivel_1",
        "tipo_de_obra_clasificador_nivel_2",
        "modalidad_de_ejecucion_de_la_obra",
        "estado_de_ejecucion",
    ]
    for field in text_fields:
        val = filters.get(field)
        if val:
            clauses.append(f"o.{field} ILIKE %s")
            params.append(f"%{val}%")
 
    if filters.get("monto_min") is not None:
        clauses.append("o.monto_del_contrato_en_soles >= %s")
        params.append(filters["monto_min"])
 
    if filters.get("monto_max") is not None:
        clauses.append("o.monto_del_contrato_en_soles <= %s")
        params.append(filters["monto_max"])
 
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params
 
 
def _distinct(col: str, parent_col: str = None, parent_val: str = None) -> list[str]:
    if parent_col and parent_val:
        query = f"""
            SELECT DISTINCT {col}
            FROM obras_sql
            WHERE {parent_col} ILIKE %s
              AND {col} IS NOT NULL
            ORDER BY {col};
        """
        params = [parent_val]
    else:
        query = f"""
            SELECT DISTINCT {col}
            FROM obras_sql
            WHERE {col} IS NOT NULL
            ORDER BY {col};
        """
        params = []
 
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(query, params)
    rows = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows
 
#  ENDPOINT 1: Busqueda semántica
@app.post("/buscar", response_model=list[ObraResult], tags=["Busqueda"])
def buscar_obras(req: BusquedaRequest):
    """Busqueda semantica por texto libre + filtros de metadatos."""
    embeddings_generador = MODEL.embed([req.texto])
    vector = list(embeddings_generador)[0].tolist()
 
    filters = req.model_dump(exclude={"texto", "top"})
    where, where_params = build_where(filters)
 
    params = [vector] + where_params + [req.top]
 
    query = f"""
        SELECT
            o.codigo_infobras,
            o.nombre_de_obra,
            o.naturaleza_de_la_obra,
            o.tipo_de_obra_clasificador_nivel_1,
            o.tipo_de_obra_clasificador_nivel_2,
            o.tipo_de_obra_clasificador_nivel_3,
            o.modalidad_de_ejecucion_de_la_obra,
            o.estado_de_ejecucion,
            o.entidad_publica,
            o.nivel_de_gobierno,
            o.sector_de_la_entidad,
            o.departamento,
            o.provincia,
            o.distrito,
            o.monto_del_contrato_en_soles,
            o.avance_fisico_real_acumulado,
            o.fecha_de_inicio_de_obra,
            o.fecha_de_finalizacion_real,
            1 - (e.embedding <=> %s::vector) AS similitud
        FROM obras_sql o
        JOIN obras_embeddings e USING (codigo_infobras)
        {where}
        ORDER BY similitud DESC
        LIMIT %s;
    """

    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
    cols = [
        "codigo_infobras", "nombre_de_obra", "naturaleza_de_la_obra",
        "tipo_de_obra_clasificador_nivel_1", "tipo_de_obra_clasificador_nivel_2",
        "tipo_de_obra_clasificador_nivel_3", "modalidad_de_ejecucion_de_la_obra",
        "estado_de_ejecucion", "entidad_publica", "nivel_de_gobierno",
        "sector_de_la_entidad", "departamento", "provincia", "distrito",
        "monto_del_contrato_en_soles", "avance_fisico_real_acumulado",
        "fecha_de_inicio_de_obra", "fecha_de_finalizacion_real", "similitud",
    ]
    return [ObraResult(**dict(zip(cols, row))) for row in rows]
 
 
#  ENDPOINT 2: Detalle de obra
 
@app.get("/obras/{codigo_infobras}", tags=["Obras"])
def detalle_obra(codigo_infobras: str):
    """Retorna todos los campos de una obra por su código."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "SELECT * FROM obras_sql WHERE codigo_infobras = %s;",
            (codigo_infobras,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Obra no encontrada")
        cols = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
    return dict(zip(cols, row))
 
 
#  ENDPOINTS 3: Selects para el frontend
 
@app.get("/selects/departamentos", tags=["Selects"])
def get_departamentos():
    return _distinct("departamento")
 
@app.get("/selects/provincias", tags=["Selects"])
def get_provincias(departamento: Optional[str] = Query(None)):
    return _distinct("provincia", "departamento", departamento)
 
@app.get("/selects/distritos", tags=["Selects"])
def get_distritos(provincia: Optional[str] = Query(None)):
    return _distinct("distrito", "provincia", provincia)
 
@app.get("/selects/niveles-gobierno", tags=["Selects"])
def get_niveles_gobierno():
    return _distinct("nivel_de_gobierno")
 
@app.get("/selects/sectores", tags=["Selects"])
def get_sectores():
    return _distinct("sector_de_la_entidad")
 
@app.get("/selects/naturalezas", tags=["Selects"])
def get_naturalezas():
    return _distinct("naturaleza_de_la_obra")
 
@app.get("/selects/tipos-nivel-1", tags=["Selects"])
def get_tipos_nivel1():
    return _distinct("tipo_de_obra_clasificador_nivel_1")
 
@app.get("/selects/tipos-nivel-2", tags=["Selects"])
def get_tipos_nivel2(nivel1: Optional[str] = Query(None)):
    return _distinct("tipo_de_obra_clasificador_nivel_2", "tipo_de_obra_clasificador_nivel_1", nivel1)
 
@app.get("/selects/modalidades", tags=["Selects"])
def get_modalidades():
    return _distinct("modalidad_de_ejecucion_de_la_obra")
 
@app.get("/selects/estados", tags=["Selects"])
def get_estados():
    return _distinct("estado_de_ejecucion")
 
 
# Health check 
@app.get("/health", tags=["Sistema"])
def health():
    try:
        conn = get_conn()
        conn.close()
        return {"status": "ok", "db": "conectado", "modelo": MODEL_NAME}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    
# FRONTEND HTML
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
def home(request: Request):
    try:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"request": request} 
        )
    except Exception as e:
        error_msg = f"<h1>¡Ups! Falló el Home</h1><p>El error exacto es: <b>{repr(e)}</b></p>"
        return HTMLResponse(content=error_msg, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)