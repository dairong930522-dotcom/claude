const express = require('express');
const { z } = require('zod');
const { conTenant } = require('../db');
const { generarExpediente } = require('../servicios/generar');

const router = express.Router();

const ExpedienteSchema = z.object({
  cliente_id: z.string().uuid(),
  formulario: z.string().min(1),
  datos_formulario: z.record(z.unknown()).optional().default({}),
});

// POST /api/expedientes  ->  crea un expediente borrador
router.post('/', async (req, res, next) => {
  try {
    const datos = ExpedienteSchema.parse(req.body);
    const fila = await conTenant(req.despachoId, async (cli) => {
      const { rows } = await cli.query(
        `INSERT INTO expedientes (despacho_id, cliente_id, formulario, datos_formulario)
         VALUES (current_setting('app.despacho_id')::uuid, $1, $2, $3)
         RETURNING id, formulario, estado, creado_en`,
        [datos.cliente_id, datos.formulario, JSON.stringify(datos.datos_formulario)],
      );
      return rows[0];
    });
    res.status(201).json(fila);
  } catch (e) {
    if (e.name === 'ZodError') return res.status(400).json({ error: e.issues });
    next(e);
  }
});

// GET /api/expedientes/:id
router.get('/:id', async (req, res, next) => {
  try {
    const fila = await conTenant(req.despachoId, async (cli) => {
      const { rows } = await cli.query(
        `SELECT e.*, c.nombre, c.apellido1 FROM expedientes e
         JOIN clientes c ON c.id = e.cliente_id
         WHERE e.id = $1`,
        [req.params.id],
      );
      return rows[0];
    });
    if (!fila) return res.status(404).json({ error: 'Expediente no encontrado' });
    res.json(fila);
  } catch (e) { next(e); }
});

// POST /api/expedientes/:id/generar  ->  devuelve el PDF relleno
router.post('/:id/generar', async (req, res, next) => {
  try {
    const { bytes, avisos } = await generarExpediente({
      despachoId: req.despachoId,
      usuarioId: req.usuarioId,
      expedienteId: req.params.id,
    });
    res.setHeader('X-Lex-Avisos', JSON.stringify(avisos));
    res.setHeader('Content-Type', 'application/pdf');
    res.send(Buffer.from(bytes));
  } catch (e) { next(e); }
});

module.exports = router;
