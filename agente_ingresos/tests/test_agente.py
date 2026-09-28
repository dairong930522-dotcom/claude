import json
import os
import random
import tempfile
import unittest

from agente_ingresos.agente import Agente
from agente_ingresos.llm import PresupuestoAgotado
from agente_ingresos.riesgo import Selector

CFG = json.load(open(os.path.join(os.path.dirname(__file__), "..", "config.ejemplo.json"), encoding="utf-8"))
CFG["prospeccion"]["busqueda_web"] = False


class LLMFalso:
    def __init__(self, intencion="interesado", db=None, coste=0.0):
        self.intencion, self.db, self.coste = intencion, db, coste
        self.llamadas = []

    def json(self, concepto, system, prompt, esquema, max_tokens=8000):
        self.llamadas.append(concepto)
        if self.db is not None:
            if self.db.coste_dia() >= CFG["limites"]["presupuesto_ia_diario_usd"]:
                raise PresupuestoAgotado("agotado")
            self.db.registrar_coste("ia:" + concepto, self.coste)
        if concepto == "respuesta":
            return {"intencion": self.intencion, "respuesta": "Aquí tiene el enlace."}
        if concepto == "marketing":
            return {"piezas": [{"canal": "Blog", "titulo": "T", "texto": "X"}]}
        return {"asunto": "Hola", "cuerpo": "Cuerpo"}

    def investigar(self, *a, **k):
        return []


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.llm = LLMFalso()
        self.ag = Agente(CFG, self.dir, llm=self.llm)
        self.llm.db = self.ag.db
        csv_path = os.path.join(self.dir, "l.csv")
        with open(csv_path, "w") as f:
            f.write("empresa,email,web\nA,a@a.com,a.com\nB,b@b.com,b.com\nB2,B@B.com,b.com\nMal,no-email,x\n")
        self.importados = self.ag.importar_csv(csv_path)


class TestAgente(Base):
    def test_importar_deduplica_y_valida(self):
        self.assertEqual(self.importados, 2)

    def test_modo_prueba_no_envia_y_guarda_borradores(self):
        self.assertEqual(self.ag.contactar(), 2)
        borradores = os.listdir(os.path.join(self.dir, "salida", "borradores"))
        self.assertEqual(len(borradores), 2)
        contenido = open(os.path.join(self.dir, "salida", "borradores", borradores[0]), "rb").read()
        self.assertIn(b"List-Unsubscribe", contenido)
        self.assertIn(b"BAJA", contenido)

    def test_limite_diario_de_emails(self):
        self.ag.cfg = dict(CFG, limites=dict(CFG["limites"], emails_por_dia=1))
        self.assertEqual(self.ag.contactar(), 1)
        self.assertEqual(self.ag.contactar(), 0)

    def test_baja_excluye_para_siempre(self):
        self.ag.contactar()
        lead = self.ag.db.lead_por_email("a@a.com")
        self.llm.intencion = "no_interesado"
        self.ag.procesar_respuesta(lead, "Re: Hola", "No gracias")
        self.assertTrue(self.ag.db.excluido("a@a.com"))
        self.assertFalse(self.ag.db.anadir_lead("A", "a@a.com"))

    def test_interesado_recibe_enlace_y_cuenta_exito(self):
        self.ag.contactar()
        lead = self.ag.db.lead_por_email("a@a.com")
        self.ag.procesar_respuesta(lead, "Re: Hola", "Me interesa")
        self.assertEqual(self.ag.db.lead_por_email("a@a.com")["estado"], "negociando")
        v = self.ag.db.uno("SELECT exitos FROM variantes WHERE nombre = ?", lead["variante"])
        self.assertEqual(v["exitos"], 1)

    def test_requiere_humano_se_escala(self):
        self.ag.contactar()
        self.llm.intencion = "requiere_humano"
        self.ag.procesar_respuesta(self.ag.db.lead_por_email("b@b.com"), "Re: Hola", "¿Descuento por 50?")
        self.assertIn("Necesitan tu atención", self.ag.informe())

    def test_freno_de_perdidas_pausa_el_agente(self):
        self.ag.db.registrar_coste("prueba", CFG["limites"]["perdida_maxima_usd"] + 1)
        res = self.ag.ciclo()
        self.assertIn("Freno de pérdidas", res["pausa"])
        self.assertNotIn("redaccion", self.llm.llamadas)
        # los ingresos no la reactivan solos: debe reanudarla una persona
        self.ag.db.registrar_ingreso("pago1", 500, "eur")
        self.assertIsNotNone(self.ag.riesgo.motivo_pausa())
        self.ag.riesgo.reanudar()
        self.assertIsNone(self.ag.riesgo.motivo_pausa())

    def test_presupuesto_diario_detiene_el_ciclo(self):
        self.llm.coste = CFG["limites"]["presupuesto_ia_diario_usd"]
        res = self.ag.ciclo()
        self.assertIn("presupuesto", res)
        self.assertEqual(self.llm.llamadas.count("redaccion"), 2)  # la 2ª se rechaza

    def test_pausa_manual(self):
        open(self.ag.riesgo.fichero_pausa, "w").close()
        self.assertIn("manual", self.ag.ciclo()["pausa"])

    def test_marketing_una_vez_al_dia(self):
        self.assertEqual(self.ag.marketing(), 1)
        self.assertEqual(self.ag.marketing(), 0)


class TestSelector(Base):
    def test_prefiere_el_angulo_que_convierte(self):
        s = Selector(self.ag.db, ["a", "b"], rng=random.Random(0))
        for _ in range(50):
            s.envio("a"); s.envio("b")
        for _ in range(20):
            s.exito("b")
        elegidos = [s.elegir() for _ in range(200)]
        self.assertGreater(elegidos.count("b"), 190)


if __name__ == "__main__":
    unittest.main()
