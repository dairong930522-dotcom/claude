-- =====================================================================
--  LEX — modelo de datos (PostgreSQL)
--  SaaS vertical para despachos de extranjería.
--  Principios:
--   - Multi-tenant con aislamiento estricto entre despachos (RLS).
--   - El cliente se escribe UNA vez; sus datos se reutilizan en cualquier EX.
--   - Los esquemas de formulario viven en la BD y se VERSIONAN:
--     actualizar un EX = insertar una fila nueva, NO redeplegar código.
--   - Trazabilidad de cada PDF generado (RGPD / responsabilidad).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ---------- Tenant: el despacho ----------
CREATE TABLE despachos (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre      TEXT NOT NULL,
    cif         TEXT,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Usuarios del despacho ----------
CREATE TYPE rol_usuario AS ENUM ('admin', 'abogado', 'tramitador');

CREATE TABLE usuarios (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    despacho_id   UUID NOT NULL REFERENCES despachos(id) ON DELETE CASCADE,
    email         TEXT NOT NULL UNIQUE,
    hash_clave    TEXT NOT NULL,
    rol           rol_usuario NOT NULL DEFAULT 'tramitador',
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_usuarios_despacho ON usuarios(despacho_id);

-- ---------- Cliente: datos canónicos reutilizables ----------
-- Estas columnas son los campos que se repiten en casi todos los EX.
-- Lo poco frecuente va en datos_extra (jsonb) sin tocar el esquema.
CREATE TABLE clientes (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    despacho_id        UUID NOT NULL REFERENCES despachos(id) ON DELETE CASCADE,
    nombre             TEXT NOT NULL,
    apellido1          TEXT NOT NULL,
    apellido2          TEXT,
    nie                TEXT,
    pasaporte          TEXT,
    nacionalidad       TEXT,
    fecha_nacimiento   DATE,
    lugar_nacimiento   TEXT,
    sexo               TEXT,             -- 'H' / 'M' / etc.
    estado_civil       TEXT,
    nombre_padre       TEXT,
    nombre_madre       TEXT,
    domicilio          TEXT,
    localidad          TEXT,
    provincia          TEXT,
    cp                 TEXT,
    telefono           TEXT,
    email              TEXT,
    datos_extra        JSONB NOT NULL DEFAULT '{}'::jsonb,
    creado_en          TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_clientes_despacho ON clientes(despacho_id);
CREATE INDEX idx_clientes_nie ON clientes(despacho_id, nie);

-- ---------- Esquemas de formulario, VERSIONADOS ----------
-- definicion = el JSON data-driven que usa el motor de mapeo.
-- Conviven versiones: cuando el Ministerio cambia un EX, insertas v2
-- y marcas activa la nueva; los expedientes viejos siguen apuntando a la suya.
CREATE TABLE esquemas_formulario (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    formulario   TEXT NOT NULL,          -- 'EX-15', 'EX-18', ...
    version      TEXT NOT NULL,          -- 'v1', '2025-03', ...
    definicion   JSONB NOT NULL,
    activa       BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (formulario, version)
);

-- ---------- Expedientes ----------
CREATE TYPE estado_expediente AS ENUM
    ('borrador', 'en_revision', 'presentado', 'resuelto', 'archivado');

CREATE TABLE expedientes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    despacho_id      UUID NOT NULL REFERENCES despachos(id) ON DELETE CASCADE,
    cliente_id       UUID NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    formulario       TEXT NOT NULL,
    esquema_id       UUID REFERENCES esquemas_formulario(id),  -- versión usada
    estado           estado_expediente NOT NULL DEFAULT 'borrador',
    -- Snapshot de los datos con los que se rellenó (auditoría e historial):
    datos_formulario JSONB NOT NULL DEFAULT '{}'::jsonb,
    creado_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_expedientes_despacho ON expedientes(despacho_id);
CREATE INDEX idx_expedientes_cliente ON expedientes(cliente_id);

-- ---------- Auditoría de PDFs generados (RGPD / responsabilidad) ----------
CREATE TABLE generaciones (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expediente_id UUID NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    usuario_id    UUID REFERENCES usuarios(id),
    esquema_id    UUID REFERENCES esquemas_formulario(id),
    hash_sha256   TEXT,                  -- huella del PDF producido
    avisos        JSONB NOT NULL DEFAULT '[]'::jsonb,  -- p.ej. campos obligatorios vacíos
    generado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
--  AISLAMIENTO MULTI-TENANT con Row-Level Security.
--  La app fija el despacho activo en cada conexión:
--     SET app.despacho_id = '<uuid del despacho del usuario logueado>';
--  y Postgres impide ver/tocar filas de otro despacho aunque haya un bug
--  en una query. Esto es lo que hace que un abogado te confíe sus clientes.
-- =====================================================================
ALTER TABLE clientes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE expedientes   ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios      ENABLE ROW LEVEL SECURITY;

CREATE POLICY aislar_clientes ON clientes
    USING (despacho_id = current_setting('app.despacho_id')::uuid);

CREATE POLICY aislar_expedientes ON expedientes
    USING (despacho_id = current_setting('app.despacho_id')::uuid);

CREATE POLICY aislar_usuarios ON usuarios
    USING (despacho_id = current_setting('app.despacho_id')::uuid);

-- =====================================================================
--  Login y RLS: la app debe conectarse con un rol NO propietario de las
--  tablas (si fuera el dueño, la RLS no se le aplica). Pero el login es el
--  problema del huevo y la gallina: aún no hay despacho fijado. Para eso,
--  una función SECURITY DEFINER que consulta usuarios saltándose la RLS,
--  SÓLO para autenticar por email.
-- =====================================================================
CREATE OR REPLACE FUNCTION autenticar_usuario(p_email TEXT)
RETURNS TABLE (id UUID, despacho_id UUID, rol rol_usuario, hash_clave TEXT)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT id, despacho_id, rol, hash_clave FROM usuarios WHERE email = p_email;
$$;
