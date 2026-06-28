// Demo de extremo a extremo:
//  1) crea una PLANTILLA con la pinta de un EX (etiquetas + casilla)
//  2) la rellena con el MOTOR usando un esquema data-driven + un cliente
//  3) guarda el PDF relleno y muestra avisos + huella sha256
//
//  En producción la plantilla NO se crea: es el PDF oficial del Ministerio,
//  y el esquema se obtiene midiendo sus coordenadas una sola vez.
const fs = require('fs');
const path = require('path');
const { PDFDocument, StandardFonts, rgb } = require('pdf-lib');
const { rellenarFormulario } = require('./src/motor');
const { CLIENTE_DEMO } = require('./src/datos-canonicos');

const DIR = __dirname;
const esquema = JSON.parse(fs.readFileSync(path.join(DIR, 'esquemas/EX-modelo.v1.json'), 'utf8'));

// -------- 1) Plantilla de demostración (sustituye al PDF oficial) --------
async function crearPlantilla() {
  const pdf = await PDFDocument.create();
  const pagina = pdf.addPage([595, 842]); // A4 en puntos
  const fuente = await pdf.embedFont(StandardFonts.HelveticaBold);
  const normal = await pdf.embedFont(StandardFonts.Helvetica);

  const tit = (t, x, y, s = 12, f = fuente) => pagina.drawText(t, { x, y, size: s, font: f, color: rgb(0.1, 0.1, 0.1) });
  const et  = (t, x, y) => pagina.drawText(t, { x, y, size: 10, font: normal, color: rgb(0.25, 0.25, 0.25) });

  tit('EX-MODELO — Solicitud (demostración)', 60, 780, 14);
  tit('DATOS DE LA PERSONA', 60, 715, 11);

  et('Primer apellido:', 60, 690);   et('Segundo apellido:', 60, 668);
  et('Nombre:', 60, 646);
  et('NIE:', 60, 624);               et('Pasaporte:', 330, 624);
  et('Nacionalidad:', 60, 602);      et('F. nacimiento:', 330, 602);
  et('Lugar nacimiento:', 60, 580);  et('Sexo:', 330, 580);
  et('Estado civil:', 60, 558);

  tit('DOMICILIO EN ESPAÑA', 60, 536, 11);
  et('Domicilio:', 60, 514);
  et('Localidad:', 60, 492);         et('Provincia:', 330, 492);
  et('C.P.:', 60, 470);              et('Teléfono:', 330, 470);
  et('Email:', 60, 448);

  et('¿Reside actualmente en España?', 100, 404);
  pagina.drawRectangle({ x: 318, y: 401, width: 14, height: 14, borderColor: rgb(0.3, 0.3, 0.3), borderWidth: 1 });

  // líneas de subrayado bajo cada hueco (estética de formulario)
  return await pdf.save();
}

(async () => {
  const plantillaBytes = await crearPlantilla();
  fs.writeFileSync(path.join(DIR, 'salida/plantilla-EX-modelo.pdf'), plantillaBytes);

  // -------- 2) Rellenar con el motor --------
  const { bytes, avisos, hash } = await rellenarFormulario({
    esquema,
    datos: CLIENTE_DEMO,
    plantillaBytes,
  });

  // -------- 3) Guardar y reportar --------
  fs.writeFileSync(path.join(DIR, 'salida/EX-modelo-relleno.pdf'), bytes);

  console.log('Formulario:', esquema.formulario, esquema.version);
  console.log('Campos en el esquema:', esquema.campos.length);
  console.log('Avisos:', avisos.length ? avisos : 'ninguno');
  console.log('Huella SHA-256 (para la tabla generaciones):', hash.slice(0, 16) + '…');
  console.log('PDF generado: salida/EX-modelo-relleno.pdf');
})();
