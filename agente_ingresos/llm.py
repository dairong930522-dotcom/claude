"""Envoltorio de Claude con control de coste: cada llamada se contabiliza y se
bloquea si supera el presupuesto diario."""

import json
import re

import anthropic

# USD por millón de tokens (entrada, salida)
PRECIOS = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
USD_POR_BUSQUEDA = 0.01  # búsqueda web: 10 USD / 1000
MODELOS_CON_FALLBACK = {"claude-opus-5", "claude-fable-5-1"}


class PresupuestoAgotado(Exception):
    pass


class LLM:
    def __init__(self, db, modelo: str, presupuesto_diario_usd: float):
        self.db = db
        self.modelo = modelo
        self.presupuesto = presupuesto_diario_usd
        self.cliente = anthropic.Anthropic()

    def _comprobar_presupuesto(self):
        if self.db.coste_dia() >= self.presupuesto:
            raise PresupuestoAgotado(
                f"Presupuesto diario de IA agotado ({self.presupuesto:.2f} USD)"
            )

    def _contabilizar(self, respuesta, concepto):
        entrada, salida = PRECIOS.get(self.modelo, (5.0, 25.0))
        u = respuesta.usage
        tokens_in = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        tokens_in += 0.1 * (getattr(u, "cache_read_input_tokens", 0) or 0)
        usd = tokens_in * entrada / 1e6 + (u.output_tokens or 0) * salida / 1e6
        stu = getattr(u, "server_tool_use", None)
        if stu is not None:
            usd += (getattr(stu, "web_search_requests", 0) or 0) * USD_POR_BUSQUEDA
        self.db.registrar_coste(f"ia:{concepto}", usd)

    def _crear(self, concepto, **kwargs):
        self._comprobar_presupuesto()
        if self.modelo in MODELOS_CON_FALLBACK:
            # Si el modelo rechaza una petición, la API la reintenta con otro modelo.
            r = self.cliente.beta.messages.create(
                model=self.modelo,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                **kwargs,
            )
        else:
            r = self.cliente.messages.create(model=self.modelo, **kwargs)
        self._contabilizar(r, concepto)
        if r.stop_reason == "refusal":
            raise RuntimeError(f"El modelo rechazó la petición ({concepto})")
        return r

    @staticmethod
    def _texto(respuesta) -> str:
        return "".join(b.text for b in respuesta.content if b.type == "text")

    def json(self, concepto: str, system: str, prompt: str, esquema: dict, max_tokens=8000) -> dict:
        r = self._crear(
            concepto,
            max_tokens=max_tokens,
            system=system,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": esquema}},
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(self._texto(r))

    def investigar(self, concepto: str, system: str, prompt: str, max_busquedas=5, max_tokens=16000):
        """Pide a Claude que investigue en la web y devuelva una lista JSON."""
        mensajes = [{"role": "user", "content": prompt}]
        herramientas = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_busquedas}]
        for _ in range(4):  # continúa si la API pausa el turno
            r = self._crear(concepto, max_tokens=max_tokens, system=system,
                            tools=herramientas, messages=mensajes)
            if r.stop_reason != "pause_turn":
                break
            mensajes.append({"role": "assistant", "content": r.content})
        texto = self._texto(r)
        m = re.search(r"\[.*\]", texto, re.S)
        return json.loads(m.group(0)) if m else []
