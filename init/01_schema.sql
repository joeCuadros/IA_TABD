-- Extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

--  Tabla principal
CREATE TABLE IF NOT EXISTS obras_sql (
    -- Identificadores
    codigo_infobras                             TEXT PRIMARY KEY,
    codigo_unico_de_inversion                   TEXT,
    codigo_snip                                 TEXT,
    codigo_entidad                              TEXT,

    -- Descripción
    nombre_de_obra                              TEXT,
    nombre_proyecto                             TEXT,
    naturaleza_de_la_obra                       TEXT,
    tipo_de_obra_clasificador_nivel_1           TEXT,
    tipo_de_obra_clasificador_nivel_2           TEXT,
    tipo_de_obra_clasificador_nivel_3           TEXT,
    modalidad_de_ejecucion_de_la_obra           TEXT,
    estado_de_ejecucion                         TEXT,
    estado_del_proyecto                         TEXT,

    -- Entidad
    entidad_publica                             TEXT,
    nivel_de_gobierno                           TEXT,
    sector_de_la_entidad                        TEXT,

    -- Ubicación
    departamento                                TEXT,
    provincia                                   TEXT,
    distrito                                    TEXT,
    direccion_o_informacion_de_referencia       TEXT,

    -- Montos
    monto_viable_aprobado                       NUMERIC,
    monto_viable_actualizado                    NUMERIC,
    monto_aprobado_en_soles                     NUMERIC,
    monto_de_aprobacion_de_expediente_tecnico   NUMERIC,
    monto_del_contrato_en_soles                 NUMERIC,
    monto_de_ejecucion_financiera_de_la_obra    NUMERIC,
    monto_de_adicionales_de_obra_en_soles       NUMERIC,
    monto_de_deductivos_de_obra_en_soles        NUMERIC,
    costo_de_la_obra_en_soles                   NUMERIC,
    monto_total_devengado_del_proyecto          NUMERIC,

    -- Fechas
    fecha_de_inicio_de_obra                     TEXT,
    fecha_finalizacion_programada_de_obra       TEXT,
    fecha_finalizacion_reprogramada_de_obra     TEXT,
    fecha_de_finalizacion_real                  TEXT,
    fecha_de_aprobacion_del_expediente          TEXT,
    fecha_de_aprobacion_de_liquidacion_de_obra  TEXT,

    -- Avance
    avance_fisico_real_acumulado                NUMERIC,
    avance_fisico_programado_acumulado          NUMERIC,
    porcentaje_de_ejecucion_financiera          NUMERIC,
    plazo_de_ejecucion_en_dias                  NUMERIC,
    nuevo_plazo_de_ejecucion_en_dias            NUMERIC,
    n_dias_de_modificaciones_de_plazo           NUMERIC,

    -- Contratista
    nombre_o_razon_social_de_la_empresa_o_consorcio TEXT,
    ruc                                         TEXT,

    -- Flags / contadores
    existe_paralizacion                         TEXT,
    tiene_recepcion_total                       TEXT,
    tiene_liquidacion_de_obra                   TEXT,
    n_de_adicionales_de_obra                    NUMERIC,
    n_de_deductivos_de_obra                     NUMERIC,
    n_de_modificaciones                         NUMERIC,
    n_de_controversias                          NUMERIC,
    n_informes_de_control                       NUMERIC,
    n_comentarios_ciudadanos                    NUMERIC,
    corresponde_a_un_saldo_de_obra              TEXT,
    marca_reconstruccion_con_cambios_si_no      TEXT,
    es_una_obra_de_caracter_reservado           TEXT
);

-- Tabla embeddings (viene de embeddings_output.parquet) 
CREATE TABLE IF NOT EXISTS obras_embeddings (
    codigo_infobras TEXT PRIMARY KEY
        REFERENCES obras_sql(codigo_infobras) ON DELETE CASCADE,
    embedding       vector(384)
);

