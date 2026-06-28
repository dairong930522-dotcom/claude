const jwt = require('jsonwebtoken');
const { jwtSecret } = require('../config');

// Valida el Bearer token y deja en req el despacho y usuario activos.
function auth(req, res, next) {
  const cabecera = req.headers.authorization || '';
  const token = cabecera.startsWith('Bearer ') ? cabecera.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'Falta token' });

  try {
    const payload = jwt.verify(token, jwtSecret);
    req.despachoId = payload.despacho_id;
    req.usuarioId = payload.sub;
    req.rol = payload.rol;
    next();
  } catch {
    return res.status(401).json({ error: 'Token inválido o caducado' });
  }
}

module.exports = { auth };
