// Diccionario canónico: las claves que se reutilizan entre formularios EX.
// Cualquier esquema de formulario mapea SUS posiciones a estas claves.
// Si añades un campo raro, va en datos_extra del cliente (jsonb) y lo
// referencias igual por su clave. La idea: el dato se nombra una sola vez.
const CAMPOS_CANONICOS = [
  'nombre', 'apellido1', 'apellido2',
  'nie', 'pasaporte', 'nacionalidad',
  'fecha_nacimiento', 'lugar_nacimiento', 'sexo', 'estado_civil',
  'nombre_padre', 'nombre_madre',
  'domicilio', 'localidad', 'provincia', 'cp',
  'telefono', 'email',
];

// Cliente de ejemplo (ficticio) para la demostración.
const CLIENTE_DEMO = {
  nombre: 'María',
  apellido1: 'González',
  apellido2: 'Pérez',
  nie: 'Y1234567Z',
  pasaporte: 'C01234567',
  nacionalidad: 'Cubana',
  fecha_nacimiento: '14/03/1990',
  lugar_nacimiento: 'La Habana',
  sexo: 'M',
  estado_civil: 'Casada',
  domicilio: 'C/ Ejemplo 12, 3º A',
  localidad: 'Santa Cruz de Tenerife',
  provincia: 'Santa Cruz de Tenerife',
  cp: '38001',
  telefono: '600123456',
  email: 'maria@ejemplo.es',
  // dato de control para un checkbox del formulario:
  reside_espana: true,
};

module.exports = { CAMPOS_CANONICOS, CLIENTE_DEMO };
