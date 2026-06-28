// Tests para el servicio generar y el aislamiento RLS.
// Requiere BD real: DATABASE_URL y SEED_DATABASE_URL en .env
// Ejecutar: node --test test/generar.test.js

const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { Pool } = require('pg');

require('dotenv').config();

const ownerUrl = (process.env.DATABASE_URL || '')
  .replace('lex_app:lex_app_pass', 'postgres:postgres');

const pool = new Pool({ connectionString: ownerUrl });
const { conTenant } = require('../src/db');
const { generarExpediente } = require('../src/servicios/generar');

let despachoA, despachoB, clienteId, expedienteId, esquemaId;

before(async () => {
  const cli = await pool.connect();
  try {
    // Despacho A
    const { rows: [d] } = await cli.query(
      `INSERT INTO despachos (nombre) VALUES ('Test A') RETURNING id`);
    despachoA = d.id;

    // Despacho B
    const { rows: [d2] } = await cli.query(
      `INSERT INTO despachos (nombre) VALUES ('Test B') RETURNING id`);
    despachoB = d2.id;

    // Esquema activo para EX-MODELO
    const { rows: [esq] } = await cli.query(
      `SELECT id FROM esquemas_formulario WHERE formulario = 'EX-MODELO' AND activa = true LIMIT 1`);
    assert.ok(esq, 'Debe haber un esquema EX-MODELO sembrado (ejecuta db/seed.js primero)');
    esquemaId = esq.id;

    // Cliente en despacho A — SET app.despacho_id para insertar con RLS OFF (somos postgres)
    await cli.query(`SET LOCAL app.despacho_id = '${despachoA}'`);
    // Insertar directo como propietario (sin RLS)
    const { rows: [c] } = await cli.query(
      `INSERT INTO clientes (despacho_id, nombre, apellido1, nie) VALUES ($1,'Ana','López','X9999999Z') RETURNING id`,
      [despachoA]);
    clienteId = c.id;

    // Expediente
    const { rows: [e] } = await cli.query(
      `INSERT INTO expedientes (despacho_id, cliente_id, formulario, esquema_id, datos_formulario)
       VALUES ($1, $2, 'EX-MODELO', $3, '{}') RETURNING id`,
      [despachoA, clienteId, esquemaId]);
    expedienteId = e.id;
  } finally {
    cli.release();
  }
});

after(async () => {
  // Limpieza — borrar los datos de test
  const cli = await pool.connect();
  try {
    await cli.query(`DELETE FROM despachos WHERE nombre IN ('Test A', 'Test B')`);
  } finally {
    cli.release();
    await pool.end();
  }
});

test('generarExpediente devuelve bytes de PDF y hash', async () => {
  const result = await generarExpediente({
    despachoId: despachoA,
    usuarioId: null,
    expedienteId,
  });
  assert.ok(result.bytes instanceof Uint8Array, 'bytes debe ser Uint8Array');
  assert.ok(result.bytes.length > 0, 'PDF no puede estar vacío');
  assert.match(result.hash, /^[0-9a-f]{64}$/, 'hash debe ser SHA-256 hex');
  assert.ok(Array.isArray(result.avisos), 'avisos debe ser array');
});

test('generarExpediente incluye aviso si NIE vacío', async () => {
  // Expediente con cliente sin NIE
  const cli = await pool.connect();
  let expSinNie;
  try {
    const { rows: [cSinNie] } = await cli.query(
      `INSERT INTO clientes (despacho_id, nombre, apellido1) VALUES ($1,'Sin','NIE') RETURNING id`,
      [despachoA]);
    const { rows: [e] } = await cli.query(
      `INSERT INTO expedientes (despacho_id, cliente_id, formulario, esquema_id, datos_formulario)
       VALUES ($1, $2, 'EX-MODELO', $3, '{}') RETURNING id`,
      [despachoA, cSinNie.id, esquemaId]);
    expSinNie = e.id;
  } finally {
    cli.release();
  }

  const { avisos } = await generarExpediente({
    despachoId: despachoA,
    usuarioId: null,
    expedienteId: expSinNie,
  });
  const tieneAvisoNIE = avisos.some(a => a.includes('nie'));
  assert.ok(tieneAvisoNIE, `Debe avisar que 'nie' obligatorio está vacío. Avisos: ${JSON.stringify(avisos)}`);
});

test('RLS: despacho B no puede generar expediente de despacho A', async () => {
  await assert.rejects(
    () => generarExpediente({ despachoId: despachoB, usuarioId: null, expedienteId }),
    (err) => {
      assert.equal(err.status, 404);
      return true;
    },
    'Debe rechazar con 404 (RLS oculta el expediente)',
  );
});

test('RLS: despacho B no puede leer clientes de despacho A', async () => {
  const filas = await conTenant(despachoB, async (cli) => {
    const { rows } = await cli.query(`SELECT id FROM clientes WHERE id = $1`, [clienteId]);
    return rows;
  });
  assert.equal(filas.length, 0, 'RLS debe ocultar el cliente al despacho B');
});
