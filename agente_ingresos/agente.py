"""Director: coordina a los subagentes especializados.

En cada ciclo el director comprueba los frenos de riesgo y lanza a cada
subagente por orden (cobrador -> recepcionista -> prospector -> comercial ->
marketing -> analista). Los fallos de uno no paran a los demás; si un
subagente falla varias veces seguidas, el director lo desactiva y te avisa."""

import json
import logging
import os

from .correo import Correo
from .db import DB, hoy
from .llm import LLM, PresupuestoAgotado
from .pagos import Pagos
from .riesgo import Riesgo, Selector
from .subagentes import ORDEN
from .subagentes.base import Contexto, PresupuestoSubagenteAgotado
from .subagentes.comercial import enviados_hoy

log = logging.getLogger("agente")


class Agente:
    def __init__(self, cfg: dict, carpeta: str, llm=None):
        self.cfg = cfg
        self.carpeta = carpeta
        self.salida = os.path.join(carpeta, "salida")
        os.makedirs(self.salida, exist_ok=True)
        self.db = DB(os.path.join(carpeta, "agente.db"))
        lim = cfg["limites"]
        self.llm = llm or LLM(self.db, cfg.get("modelo", "claude-opus-5"), lim["presupuesto_ia_diario_usd"])
        self.riesgo = Riesgo(self.db, cfg, carpeta)
        self.ctx = Contexto(
            cfg, self.db, self.llm,
            Correo(cfg, self.salida, cfg.get("modo_prueba", True)),
            Pagos(self.db, cfg),
            Selector(self.db, cfg["angulos_venta"]),
            self.riesgo, self.salida,
        )
        self.subagentes = {cls.nombre: cls(self.ctx) for cls in ORDEN}
        self.max_fallos = cfg.get("director", {}).get("max_fallos_seguidos", 3)

    def __getitem__(self, nombre):
        return self.subagentes[nombre]

    def importar_csv(self, ruta) -> int:
        return self["prospector"].importar_csv(ruta)

    # ----------------------------------------------------- salud de subagentes
    def _desactivado(self, nombre) -> bool:
        return self.db.get(f"sub:{nombre}:desactivado") == "1"

    def _fallo(self, sub, error):
        fallos = int(self.db.get(f"sub:{sub.nombre}:fallos", 0)) + 1
        self.db.set(f"sub:{sub.nombre}:fallos", fallos)
        if fallos >= self.max_fallos:
            self.db.set(f"sub:{sub.nombre}:desactivado", "1")
            self.db.escalar(None, f"Subagente '{sub.nombre}' desactivado tras {fallos} fallos seguidos: {error}")
            log.error("Subagente %s desactivado", sub.nombre)

    def reactivar(self, nombre=None):
        for n in [nombre] if nombre else self.subagentes:
            self.db.set(f"sub:{n}:desactivado", "0")
            self.db.set(f"sub:{n}:fallos", 0)

    # ------------------------------------------------------------------ ciclo
    def ciclo(self) -> dict:
        res = {}
        pausa = self.riesgo.motivo_pausa()
        if pausa:
            log.warning("Agente en pausa: %s", pausa)
            res["pausa"] = pausa
        else:
            for nombre, sub in self.subagentes.items():
                if not sub.activo or self._desactivado(nombre):
                    res[nombre] = "inactivo"
                    continue
                try:
                    res[nombre] = sub.ejecutar()
                    self.db.set(f"sub:{nombre}:fallos", 0)
                except PresupuestoSubagenteAgotado as e:
                    res[nombre] = str(e)  # solo se para este subagente
                except PresupuestoAgotado as e:
                    log.warning("%s", e)
                    res["presupuesto"] = str(e)
                    break
                except Exception as e:  # un subagente que falla no detiene a los demás
                    log.exception("Fallo en %s", nombre)
                    res[nombre] = f"error: {e}"
                    self._fallo(sub, e)
                self.db.set(f"sub:{nombre}:ultimo", json.dumps(res[nombre], ensure_ascii=False, default=str))
            pausa = self.riesgo.motivo_pausa()
        texto = self.informe(pausa)
        if self.db.get("informe_dia") != hoy() and os.environ.get("EMAIL_DUENO"):
            try:
                self.ctx.correo.enviar(os.environ["EMAIL_DUENO"], f"Informe diario {hoy()}", texto)
                self.db.set("informe_dia", hoy())
            except Exception:
                log.exception("No se pudo enviar el informe")
        log.info("Ciclo: %s", json.dumps(res, ensure_ascii=False, default=str))
        return res

    # ---------------------------------------------------------------- informe
    def informe(self, pausa=None) -> str:
        est = {r["estado"]: r["c"] for r in self.db.q("SELECT estado, COUNT(*) c FROM leads GROUP BY estado")}
        var = self.db.q("SELECT * FROM variantes WHERE activo = 1 ORDER BY exitos DESC")
        esc = self.db.q("SELECT * FROM escalados WHERE atendido = 0")
        subs = []
        for n, s in self.subagentes.items():
            if not s.activo:
                estado = "apagado en config"
            elif self._desactivado(n):
                estado = "DESACTIVADO por fallos"
            else:
                estado = "ok"
            gasto = f", IA hoy {s.gasto_hoy():.2f}/{s.presupuesto():.2f} USD" if s.pct else ""
            subs.append(f"- {n} ({s.descripcion}): {estado}{gasto} — último: {self.db.get(f'sub:{n}:ultimo', '-')}")
        lineas = [
            f"# Informe del agente — {hoy()}",
            f"Modo: {'PRUEBA (no se envía nada)' if self.cfg.get('modo_prueba', True) else 'REAL'}",
            f"Estado: {'PAUSADO — ' + pausa if pausa else 'activo'}", "",
            f"Ingresos hoy: {self.db.ingreso_dia():.2f} | total: {self.db.ingreso_total():.2f}",
            f"Gasto IA hoy: {self.db.coste_dia():.2f} USD | gasto total: {self.db.coste_total():.2f} USD",
            f"Balance (ingresos - gastos): {self.riesgo.balance():.2f}", "",
            "Subagentes:", *subs, "",
            f"Emails enviados hoy: {enviados_hoy(self.db)}",
            "Leads por estado: " + ", ".join(f"{k}={v}" for k, v in sorted(est.items())), "",
            "Ángulos de venta activos (respuestas positivas / envíos):",
            *[f"- {v['nombre']}: {v['exitos']}/{v['envios']}" for v in var],
        ]
        if esc:
            lineas += ["", "Necesitan tu atención:",
                       *[f"- {'lead ' + str(e['lead_id']) if e['lead_id'] else 'sistema'}: {e['motivo']}" for e in esc]]
        texto = "\n".join(lineas)
        with open(os.path.join(self.salida, "informe.md"), "w", encoding="utf-8") as f:
            f.write(texto)
        return texto
