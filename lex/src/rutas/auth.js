const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { getPool } = require('../db');
const { jwtSecret } = require('../config');

const router = express.Router();

// POST /api/auth/login  { email, clave }
router.post('/login', async (req, res, next) => {
  try {
    const { email, clave } = req.body || {};
    if (!email || !clave) return res.status(400).json({ error: 'email y clave requeridos' });

    // Login = excepción a la RLS → función SECURITY DEFINER (ver db/modelo.sql)
    const { rows } = await getPool().query('SELECT * FROM autenticar_usuario($1)', [email]);
    const u = rows[0];
    if (!u || !(await bcrypt.compare(clave, u.hash_clave))) {
      return res.status(401).json({ error: 'Credenciales inválidas' });
    }

    const token = jwt.sign(
      { sub: u.id, despacho_id: u.despacho_id, rol: u.rol },
      jwtSecret,
      { expiresIn: '8h' },
    );
    res.json({ token });
  } catch (e) { next(e); }
});

module.exports = router;
