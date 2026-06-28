const express = require('express');
const path = require('path');
const { puerto } = require('./config');
const { auth } = require('./middleware/auth');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

// Salud (sin auth, para monitorización / arranque)
app.get('/salud', (req, res) => res.json({ ok: true, servicio: 'lex' }));

// Login (sin auth)
app.use('/api/auth', require('./rutas/auth'));

// A partir de aquí, todo exige token válido
app.use('/api', auth);
app.use('/api/clientes', require('./rutas/clientes'));
app.use('/api/expedientes', require('./rutas/expedientes'));

// Manejador de errores central
app.use((err, req, res, next) => {
  console.error(err);
  res.status(err.status || 500).json({ error: err.message || 'Error interno' });
});

app.listen(puerto, () => console.log(`LEX escuchando en http://localhost:${puerto}`));

module.exports = app;
