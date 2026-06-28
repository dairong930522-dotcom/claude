const express = require('express');
const { z } = require('zod');
const { conTenant } = require('../db');

const router = express.Router();

const ClienteSchema = z.object({
  nombre: z.string().min(1),
  apellido1: z.string().min(1),
  apellido2: z.string().optional(),
  nie: z.string().optional(),
  pasaporte: z.string().optional(),
  nacionalidad: z.string().optional(),
  // ...resto de campos canónicos (ver db/modelo.sql)
});

// POST /api/clientes
router.post('/', async (req, res, next) => {
  try {
    const datos = ClienteSchema.parse(req.body);
    const fila = await conTenant(req.despachoId, async (cli) => {
      const { rows } = await cli.query(
        `INSERT INTO clientes (despacho_id, nombre, apellido1, apellido2, nie, pasaporte, nacionalidad)
         VALUES (current_setting('app.despacho_id')::uuid, $1, $2, $3, $4, $5, $6)
         RETURNING id`,
        [datos.nombre, datos.apellido1, datos.apellido2, datos.nie, datos.pasaporte, datos.nacionalidad],
      );
      return rows[0];
    });
    res.status(201).json(fila);
  } catch (e) {
    if (e.name === 'ZodError') return res.status(400).json({ error: e.issues });
    next(e);
  }
});

// GET /api/clientes
router.get('/', async (req, res, next) => {
  try {
    const filas = await conTenant(req.despachoId, async (cli) => {
      const { rows } = await cli.query(
        'SELECT id, nombre, apellido1, apellido2, nie FROM clientes ORDER BY apellido1');
      return rows;
    });
    res.json(filas);
  } catch (e) { next(e); }
});

module.exports = router;
