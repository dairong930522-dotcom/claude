const fs = require('fs');
const path = require('path');
const { conTenant } = require('../db');
const { rellenarFormulario } = require('../motor');

const DIR_PLANTILLAS = path.join(__dirname, '..', '..', 'plantillas');

// Campos canónicos del cliente que pueden mapear los esquemas.
const CAMPOS_CLIENTE = [
  'nombre', 'apellido1', 'apellido2', 'nie', 'pasaporte', 'nacionalidad',
  'fecha_nacimiento', 'lugar_nacimiento', 'sexo', 'estado_civil',
  'nombre_padre', 'nombre_madre', 'domicilio', 'localidad', 'provincia',
  'cp', 'telefono', 'email',
];

// Mezcla: datos canónicos del cliente + datos_extra + lo específico del expediente.
function construirDatos(fila) {
  const datos = {};
  for (const k of CAMPOS_CLIENTE) if (fila[k] != null) datos[k] = fila[k];
  Object.assign(datos, fila.datos_extra || {}, fila.datos_formulario || {});
  return datos;
}

function rutaPlantilla(formulario) {
  return path.join(DIR_PLANTILLAS, `${formulario}.pdf`); // PDF oficial por formulario
}

// Genera el PDF de un expediente. Todo dentro del tenant (RLS activa).
async function generarExpediente({ despachoId, usuarioId, expedienteId }) {
  return conTenant(despachoId, async (cli) => {
    const { rows } = await cli.query(
      `SELECT e.id, e.formulario, e.esquema_id, e.datos_formulario,
              c.*
         FROM expedientes e
         JOIN clientes c ON c.id = e.cliente_id
        WHERE e.id = $1`,
      [expedienteId],
    );
    const fila = rows[0];
    if (!fila) throw Object.assign(new Error('Expediente no encontrado'), { status: 404 });

    // Esquema: el fijado en el expediente, o el activo del formulario.
    const esq = fila.esquema_id
      ? await cli.query('SELECT id, definicion FROM esquemas_formulario WHERE id = $1', [fila.esquema_id])
      : await cli.query(
          `SELECT id, definicion FROM esquemas_formulario
            WHERE formulario = $1 AND activa = true
            ORDER BY creado_en DESC LIMIT 1`, [fila.formulario]);
    const esquema = esq.rows[0];
    if (!esquema) throw Object.assign(new Error(`Sin esquema activo para ${fila.formulario}`), { status: 422 });

    const datos = construirDatos(fila);
    const plantillaBytes = fs.readFileSync(rutaPlantilla(esquema.definicion.formulario));

    const { bytes, avisos, hash } = await rellenarFormulario({
      esquema: esquema.definicion, datos, plantillaBytes,
    });

    // Auditoría (RGPD / responsabilidad)
    await cli.query(
      `INSERT INTO generaciones (expediente_id, usuario_id, esquema_id, hash_sha256, avisos)
       VALUES ($1, $2, $3, $4, $5)`,
      [expedienteId, usuarioId, esquema.id, hash, JSON.stringify(avisos)],
    );

    return { bytes, avisos, hash };
  });
}

module.exports = { generarExpediente };
