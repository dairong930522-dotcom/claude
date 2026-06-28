// =====================================================================
//  Motor de mapeo data-driven.
//  Dado un esquema (JSON) + los datos del cliente + el PDF plantilla,
//  produce el PDF relleno. NO hay nada cableado por formulario aquí:
//  añadir un EX nuevo es añadir un esquema, no tocar este archivo.
//
//  Dos modos por campo (un EX real mezcla ambos):
//   - overlay : dibuja el texto en coordenadas (para PDFs planos / XFA
//               traicioneros del Ministerio). Robusto y predecible.
//   - acroform: el PDF tiene campos rellenables; se mapea por nombre
//               de campo (campo.campo_pdf).
// =====================================================================
const { PDFDocument, StandardFonts, rgb } = require('pdf-lib');
const crypto = require('crypto');

function esVerdadero(v) {
  return v === true || v === 'true' || v === 1 || v === '1' || v === 'Sí' || v === 'si';
}

async function rellenarFormulario({ esquema, datos, plantillaBytes }) {
  const pdf = await PDFDocument.load(plantillaBytes);
  const fuente = await pdf.embedFont(StandardFonts.Helvetica);
  const paginas = pdf.getPages();
  const avisos = [];
  let form = null; // se carga sólo si algún campo es acroform

  for (const campo of esquema.campos) {
    const valor = datos[campo.clave];

    // Control de campos vacíos
    const vacio = valor === undefined || valor === null || valor === '';
    if (vacio) {
      if (campo.obligatorio) avisos.push(`Campo obligatorio vacío: ${campo.clave}`);
      continue;
    }

    const modo = campo.modo || 'overlay';

    if (modo === 'overlay') {
      const pagina = paginas[campo.pagina ?? 0];
      if (!pagina) { avisos.push(`Página inexistente para ${campo.clave}`); continue; }

      if (campo.tipo === 'checkbox') {
        if (esVerdadero(valor)) {
          pagina.drawText('X', { x: campo.x, y: campo.y, size: campo.size ?? 11, font: fuente, color: rgb(0, 0, 0) });
        }
      } else {
        pagina.drawText(String(valor), { x: campo.x, y: campo.y, size: campo.size ?? 10, font: fuente, color: rgb(0, 0, 0) });
      }

    } else if (modo === 'acroform') {
      if (!form) form = pdf.getForm();
      try {
        if (campo.tipo === 'checkbox') {
          const cb = form.getCheckBox(campo.campo_pdf);
          esVerdadero(valor) ? cb.check() : cb.uncheck();
        } else {
          form.getTextField(campo.campo_pdf).setText(String(valor));
        }
      } catch (e) {
        avisos.push(`Campo PDF no encontrado: ${campo.campo_pdf} (${campo.clave})`);
      }
    }
  }

  // Si se usó acroform, fijamos la apariencia para que se vea sin abrir Acrobat
  if (form) { try { form.updateFieldAppearances(fuente); } catch (_) {} }

  const bytes = await pdf.save();
  const hash = crypto.createHash('sha256').update(bytes).digest('hex');
  return { bytes, avisos, hash };
}

module.exports = { rellenarFormulario };
