-- Ejecutar como superusuario (lex_owner) después de aplicar modelo.sql.
-- Crea el rol de aplicación sin privilegios de propietario (para que RLS aplique).

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lex_app') THEN
    CREATE ROLE lex_app LOGIN PASSWORD 'lex_app_pass';
  END IF;
END $$;

GRANT CONNECT ON DATABASE lex TO lex_app;
GRANT USAGE ON SCHEMA public TO lex_app;

-- SELECT en esquemas_formulario y generaciones es global (no tienen RLS de tenant)
GRANT SELECT ON esquemas_formulario TO lex_app;
GRANT ALL ON generaciones TO lex_app;

-- Tablas con RLS: el rol sólo ve las filas que la policy permite
GRANT SELECT, INSERT, UPDATE ON clientes TO lex_app;
GRANT SELECT, INSERT, UPDATE ON expedientes TO lex_app;
GRANT SELECT ON usuarios TO lex_app;

-- Función SECURITY DEFINER (login sin RLS)
GRANT EXECUTE ON FUNCTION autenticar_usuario(TEXT) TO lex_app;
