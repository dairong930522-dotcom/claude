"""Ciclo autónomo: cobros -> respuestas -> prospección -> contacto -> seguimiento
-> marketing -> informe. Cada paso respeta los límites de riesgo."""

import csv
import json
import logging
import os
import re
from datetime import datetime, timedelta

from .correo import Correo
from .db import DB, ahora, hoy
from .llm import LLM, PresupuestoAgotado
from .pagos import Pagos
from .riesgo import Riesgo, Selector

log = logging.getLogger("agente")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)

REGLAS = """Reglas obligatorias:
- Escribe en el idioma del cliente (por defecto, español), tono cercano y profesional.
- No inventes datos, clientes, testimonios, cifras ni garantías. Si no sabes algo, no lo afirmes.
- No prometas resultados garantizados ni uses urgencia falsa.
- Mensajes cortos (máx. 120 palabras), una sola llamada a la acción.
- No incluyas firma ni pie: se añaden automáticamente."""


class Agente:
    def __init__(self, cfg: dict, carpeta: str, llm=None):
        self.cfg = cfg
        self.carpeta = carpeta
        self.salida = os.path.join(carpeta, "salida")
        os.makedirs(self.salida, exist_ok=True)
        self.db = DB(os.path.join(carpeta, "agente.db"))
        lim = cfg["limites"]
        self.llm = llm or LLM(self.db, cfg.get("modelo", "claude-opus-5"), lim["presupuesto_ia_diario_usd"])
        self.correo = Correo(cfg, self.salida, cfg.get("modo_prueba", True))
        self.pagos = Pagos(self.db, cfg)
        self.riesgo = Riesgo(self.db, cfg, carpeta)
        self.selector = Selector(self.db, cfg["angulos_venta"])

    # ------------------------------------------------------------------ util
    def _negocio(self) -> str:
        n = self.cfg["negocio"]
        return (
            f"Negocio: {n['nombre']}\nOferta: {n['oferta']}\n"
            f"Precio: {n['precio']} {n.get('moneda', 'eur').upper()}\n"
            f"Cliente ideal: {n['cliente_ideal']}\nPropuesta de valor: {n['propuesta_valor']}\n"
            f"Web: {n.get('web', '')}"
        )

    def _enviados_hoy(self) -> int:
        return self.db.uno(
            "SELECT COUNT(*) c FROM mensajes WHERE direccion = 'salida' AND fecha LIKE ?", hoy() + "%"
        )["c"]

    def _registrar_envio(self, lead, asunto, cuerpo, estado, angulo=None):
        self.db.ex("INSERT INTO mensajes (lead_id, direccion, asunto, cuerpo, fecha) VALUES (?,?,?,?,?)",
                   lead["id"], "salida", asunto, cuerpo, ahora())
        self.db.ex("UPDATE leads SET estado = ?, contactos = contactos + 1, ultimo_contacto = ?"
                   + (", variante = ?" if angulo else "") + " WHERE id = ?",
                   *([estado, ahora(), angulo, lead["id"]] if angulo else [estado, ahora(), lead["id"]]))

    # ------------------------------------------------------------ prospección
    def importar_csv(self, ruta) -> int:
        n = 0
        with open(ruta, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                email = (fila.get("email") or "").strip()
                if EMAIL_RE.match(email) and self.db.anadir_lead(
                    fila.get("empresa", ""), email, fila.get("contacto", ""),
                    fila.get("web", ""), fila.get("notas", ""), "csv"):
                    n += 1
        return n

    def prospectar(self) -> int:
        p = self.cfg["prospeccion"]
        pendientes = self.db.uno("SELECT COUNT(*) c FROM leads WHERE estado = 'nuevo'")["c"]
        if not p.get("busqueda_web") or pendientes >= self.cfg["limites"]["emails_por_dia"]:
            return 0
        ya = [r["email"] for r in self.db.q("SELECT email FROM leads ORDER BY id DESC LIMIT 200")]
        encontrados = self.llm.investigar(
            "prospeccion",
            "Eres un investigador de mercado B2B. Solo recopilas datos de contacto "
            "profesionales publicados por las propias empresas (su web o ficha oficial).",
            f"{self._negocio()}\nZona: {p.get('zona', '')}\n\n"
            f"Busca {p['leads_por_ciclo']} empresas reales que encajen con el cliente ideal y que "
            "publiquen un email de contacto corporativo (no personal). Evita estos emails: "
            f"{', '.join(ya[:50]) or 'ninguno'}.\n"
            "Devuelve SOLO un array JSON de objetos con las claves: empresa, email, web, "
            "fuente (URL donde aparece el email), motivo (por qué encaja, una frase).",
            max_busquedas=p.get("max_busquedas", 5),
        )
        n = 0
        for e in encontrados:
            email = str(e.get("email", "")).strip()
            if EMAIL_RE.match(email) and e.get("fuente") and self.db.anadir_lead(
                e.get("empresa", ""), email, "", e.get("web", ""), e.get("motivo", ""), e["fuente"]):
                n += 1
        return n

    # ---------------------------------------------------------------- ventas
    def _escribir(self, lead, angulo, historial=""):
        return self.llm.json(
            "redaccion",
            "Eres un comercial experto en venta consultiva por email.\n" + REGLAS,
            f"{self._negocio()}\n\nDestinatario: {lead['empresa']} ({lead['web'] or 's/web'})\n"
            f"Por qué encaja: {lead['notas'] or 'desconocido'}\nÁngulo a usar: {angulo}\n"
            + (f"\nMensajes previos sin respuesta:\n{historial}\nEscribe un seguimiento breve y distinto."
               if historial else "\nEscribe el primer email. No incluyas enlace de pago todavía."),
            {"type": "object", "additionalProperties": False, "required": ["asunto", "cuerpo"],
             "properties": {"asunto": {"type": "string"}, "cuerpo": {"type": "string"}}},
        )

    def contactar(self) -> int:
        cupo = self.cfg["limites"]["emails_por_dia"] - self._enviados_hoy()
        n = 0
        for lead in self.db.q("SELECT * FROM leads WHERE estado = 'nuevo' ORDER BY id LIMIT ?", max(cupo, 0)):
            if self.db.excluido(lead["email"]):
                continue
            angulo = self.selector.elegir()
            m = self._escribir(lead, angulo)
            estado = self.correo.enviar(lead["email"], m["asunto"], m["cuerpo"])
            self._registrar_envio(lead, m["asunto"], m["cuerpo"], "contactado", angulo)
            self.selector.envio(angulo)
            log.info("Contacto %s a %s (%s)", estado, lead["email"], angulo)
            n += 1
        return n

    def seguir(self) -> int:
        lim = self.cfg["limites"]
        cupo = lim["emails_por_dia"] - self._enviados_hoy()
        limite = (datetime.now() - timedelta(days=lim["dias_entre_seguimientos"])).isoformat()
        n = 0
        for lead in self.db.q(
            "SELECT * FROM leads WHERE estado = 'contactado' AND contactos <= ? AND ultimo_contacto < ?"
            " ORDER BY ultimo_contacto LIMIT ?", lim["seguimientos_max"], limite, max(cupo, 0)):
            previos = self.db.q("SELECT asunto, cuerpo FROM mensajes WHERE lead_id = ? ORDER BY id", lead["id"])
            historial = "\n---\n".join(f"{p['asunto']}\n{p['cuerpo']}" for p in previos)
            m = self._escribir(lead, lead["variante"] or self.selector.elegir(), historial)
            self.correo.enviar(lead["email"], m["asunto"], m["cuerpo"])
            self._registrar_envio(lead, m["asunto"], m["cuerpo"], "contactado")
            n += 1
        # quien no responde tras el último seguimiento se cierra
        self.db.ex("UPDATE leads SET estado = 'sin_respuesta' WHERE estado = 'contactado' AND contactos > ?"
                   " AND ultimo_contacto < ?", lim["seguimientos_max"], limite)
        return n

    def atender_respuestas(self) -> int:
        n = 0
        for remitente, asunto, cuerpo, msg_id in self.correo.leer_no_leidos():
            lead = self.db.lead_por_email(remitente)
            if not lead:
                continue
            self.db.ex("INSERT INTO mensajes (lead_id, direccion, asunto, cuerpo, fecha) VALUES (?,?,?,?,?)",
                       lead["id"], "entrada", asunto, cuerpo, ahora())
            if re.search(r"\bbaja\b|unsubscribe", f"{asunto} {cuerpo[:300]}", re.I):
                self.db.excluir(remitente, "baja solicitada")
                continue
            self.procesar_respuesta(lead, asunto, cuerpo, msg_id)
            n += 1
        return n

    def procesar_respuesta(self, lead, asunto, cuerpo, msg_id=None):
        enlace = self.pagos.enlace(lead["id"])
        r = self.llm.json(
            "respuesta",
            "Eres el comercial que atiende las respuestas de clientes potenciales.\n" + REGLAS
            + "\n- Si la pregunta requiere información que no tienes (contratos, descuentos, "
              "casos a medida), clasifícala como 'requiere_humano' y no respondas nada concreto.",
            f"{self._negocio()}\nEnlace de pago: {enlace}\n\nEl cliente {lead['empresa']} respondió:\n"
            f"Asunto: {asunto}\n{cuerpo[:4000]}\n\n"
            "Clasifica la intención y redacta la respuesta. Si está interesado, incluye el enlace de pago.",
            {"type": "object", "additionalProperties": False, "required": ["intencion", "respuesta"],
             "properties": {
                 "intencion": {"type": "string", "enum": [
                     "interesado", "pregunta", "no_interesado", "baja", "requiere_humano"]},
                 "respuesta": {"type": "string"}}},
        )
        intencion = r["intencion"]
        if intencion in ("baja", "no_interesado"):
            self.db.excluir(lead["email"], intencion)
            return intencion
        if intencion == "requiere_humano":
            self.db.estado_lead(lead["id"], "requiere_humano")
            self.db.escalar(lead["id"], f"{asunto}: {cuerpo[:300]}")
            return intencion
        if lead["estado"] == "contactado":
            self.selector.exito(lead["variante"])
        self.correo.enviar(lead["email"], "Re: " + asunto.removeprefix("Re: "), r["respuesta"], msg_id)
        self._registrar_envio(lead, "Re: " + asunto, r["respuesta"], "negociando")
        return intencion

    # ------------------------------------------------------------- marketing
    def marketing(self) -> int:
        if self.db.get("marketing_dia") == hoy():
            return 0
        mk = self.cfg["marketing"]
        r = self.llm.json(
            "marketing",
            "Eres un especialista en marketing de contenidos.\n" + REGLAS.replace(
                "Mensajes cortos (máx. 120 palabras), una sola llamada a la acción.",
                "Cada pieza adaptada a su canal, útil por sí misma y con una llamada a la acción."),
            f"{self._negocio()}\n\nCrea {mk['piezas_por_dia']} piezas de contenido para hoy en los canales "
            f"{', '.join(mk['canales'])}. Temas distintos, que eduquen al cliente ideal.",
            {"type": "object", "additionalProperties": False, "required": ["piezas"],
             "properties": {"piezas": {"type": "array", "items": {
                 "type": "object", "additionalProperties": False, "required": ["canal", "titulo", "texto"],
                 "properties": {"canal": {"type": "string"}, "titulo": {"type": "string"},
                                "texto": {"type": "string"}}}}}},
        )
        carpeta = os.path.join(self.salida, "contenido")
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, f"{hoy()}.md"), "w", encoding="utf-8") as f:
            for p in r["piezas"]:
                f.write(f"## [{p['canal']}] {p['titulo']}\n\n{p['texto']}\n\n")
        self.db.set("marketing_dia", hoy())
        return len(r["piezas"])

    # --------------------------------------------------------------- informe
    def informe(self, pausa=None) -> str:
        est = {r["estado"]: r["c"] for r in self.db.q("SELECT estado, COUNT(*) c FROM leads GROUP BY estado")}
        var = self.db.q("SELECT * FROM variantes ORDER BY exitos DESC")
        esc = self.db.q("SELECT * FROM escalados WHERE atendido = 0")
        lineas = [
            f"# Informe del agente — {hoy()}",
            f"Modo: {'PRUEBA (no se envía nada)' if self.cfg.get('modo_prueba', True) else 'REAL'}",
            f"Estado: {'PAUSADO — ' + pausa if pausa else 'activo'}", "",
            f"Ingresos hoy: {self.db.ingreso_dia():.2f} | total: {self.db.ingreso_total():.2f}",
            f"Gasto IA hoy: {self.db.coste_dia():.2f} USD | gasto total: {self.db.coste_total():.2f} USD",
            f"Balance (ingresos - gastos): {self.riesgo.balance():.2f}", "",
            f"Emails enviados hoy: {self._enviados_hoy()}",
            "Leads por estado: " + ", ".join(f"{k}={v}" for k, v in sorted(est.items())), "",
            "Ángulos de venta (respuestas positivas / envíos):",
            *[f"- {v['nombre']}: {v['exitos']}/{v['envios']}" for v in var],
        ]
        if esc:
            lineas += ["", "Necesitan tu atención:", *[f"- lead {e['lead_id']}: {e['motivo']}" for e in esc]]
        texto = "\n".join(lineas)
        with open(os.path.join(self.salida, "informe.md"), "w", encoding="utf-8") as f:
            f.write(texto)
        return texto

    # ----------------------------------------------------------------- ciclo
    def ciclo(self) -> dict:
        res = {}
        pausa = self.riesgo.motivo_pausa()
        if pausa:
            log.warning("Agente en pausa: %s", pausa)
            res["pausa"] = pausa
        else:
            res["cobrado"] = self.pagos.sincronizar()
            for paso in (self.atender_respuestas, self.prospectar, self.contactar, self.seguir, self.marketing):
                try:
                    res[paso.__name__] = paso()
                except PresupuestoAgotado as e:
                    log.warning("%s", e)
                    res["presupuesto"] = str(e)
                    break
                except Exception as e:  # un paso fallido no detiene a los demás
                    log.exception("Fallo en %s", paso.__name__)
                    res[paso.__name__] = f"error: {e}"
            pausa = self.riesgo.motivo_pausa()
        texto = self.informe(pausa)
        if self.db.get("informe_dia") != hoy() and os.environ.get("EMAIL_DUENO"):
            try:
                self.correo.enviar(os.environ["EMAIL_DUENO"], f"Informe diario {hoy()}", texto)
                self.db.set("informe_dia", hoy())
            except Exception:
                log.exception("No se pudo enviar el informe")
        log.info("Ciclo: %s", json.dumps(res, ensure_ascii=False))
        return res
