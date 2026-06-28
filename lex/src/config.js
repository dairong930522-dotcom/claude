require('dotenv').config();

module.exports = {
  puerto: process.env.PORT || 3000,
  jwtSecret: process.env.JWT_SECRET || 'cambia-esto-en-produccion',
  databaseUrl: process.env.DATABASE_URL || '',
};
