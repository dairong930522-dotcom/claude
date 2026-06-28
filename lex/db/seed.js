#!/usr/bin/env node
// Siembra: despacho de prueba, usuario admin (bcrypt), esquema EX-MODELO.
// Ejecutar como lex_owner (tiene acceso completo para seed inicial).
// Usage: DATABASE_URL=postgres://lex_owner:lex_owner_pass@localhost:5432/lex node db/seed.js

require('dotenv').config();
const { Pool } = require('pg');
const bcrypt = require('bcryptjs');
const fs = require('fs');
const path = require('path');

const url = process.env.SEED_DATABASE_URL || process.env.DATABASE_URL.replace('lex_app', 'lex_owner').replace('lex_app_pass', 'lex_owner_pass');
const pool = new Pool({ connectionString: url });

async function main() {
  const cli = await pool.connect();
  try {
    await cli.query('BEGIN');

    // Despacho de prueba
    const { rows: [despacho] } = await cli.query(
      `INSERT INTO despachos (nombre, cif) VALUES ($1, $2)
       ON CONFLICT DO NOTHING
       RETURNING id`,
      ['Despacho Demo', 'B12345678'],
    );

    let despachoId = despacho?.id;
    if (!despachoId) {
      const r = await cli.query(`SELECT id FROM despachos WHERE nombre = 'Despacho Demo'`);
      despachoId = r.rows[0].id;
      console.log('Despacho ya existía, reutilizando id:', despachoId);
    } else {
      console.log('Despacho creado:', despachoId);
    }

    // Usuario admin
    const hash = await bcrypt.hash('admin1234', 10);
    const { rows: [usuario] } = await cli.query(
      `INSERT INTO usuarios (despacho_id, email, hash_clave, rol)
       VALUES ($1, $2, $3, 'admin')
       ON CONFLICT (email) DO UPDATE SET hash_clave = EXCLUDED.hash_clave
       RETURNING id`,
      [despachoId, 'admin@demo.lex', hash],
    );
    console.log('Usuario admin:', usuario.id, '/ email: admin@demo.lex / clave: admin1234');

    // Esquema EX-MODELO v1
    const definicion = JSON.parse(
      fs.readFileSync(path.join(__dirname, '..', 'esquemas', 'EX-modelo.v1.json'), 'utf8'),
    );
    const { rows: [esquema] } = await cli.query(
      `INSERT INTO esquemas_formulario (formulario, version, definicion, activa)
       VALUES ($1, $2, $3, true)
       ON CONFLICT (formulario, version) DO UPDATE SET definicion = EXCLUDED.definicion
       RETURNING id`,
      ['EX-MODELO', 'v1', JSON.stringify(definicion)],
    );
    console.log('Esquema EX-MODELO v1:', esquema.id);

    await cli.query('COMMIT');
    console.log('\nSeed completado.');
    console.log(`  Despacho ID : ${despachoId}`);
  } catch (e) {
    await cli.query('ROLLBACK');
    throw e;
  } finally {
    cli.release();
    await pool.end();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
