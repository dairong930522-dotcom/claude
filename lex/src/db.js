const { Pool } = require('pg');
const { databaseUrl } = require('./config');

let pool = null;

function getPool() {
  if (!databaseUrl) throw new Error('DATABASE_URL no configurada (.env)');
  if (!pool) pool = new Pool({ connectionString: databaseUrl });
  return pool;
}

// Ejecuta `fn(client)` con el despacho activo fijado, para que la RLS de
// Postgres filtre por tenant. SET LOCAL vive sólo dentro de la transacción,
// así que cada petición queda aislada.
//
// IMPORTANTE: la app debe conectar con un rol que NO sea dueño de las tablas;
// si fuera el propietario, la RLS no se le aplicaría.
async function conTenant(despachoId, fn) {
  const client = await getPool().connect();
  try {
    await client.query('BEGIN');
    await client.query("SELECT set_config('app.despacho_id', $1, true)", [despachoId]);
    const resultado = await fn(client);
    await client.query('COMMIT');
    return resultado;
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

module.exports = { getPool, conTenant };
