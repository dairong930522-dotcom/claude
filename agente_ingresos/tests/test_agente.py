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
        self.llamadas, self.modelos = [], []
        self.angulos_nuevos = ["ángulo nuevo"]

    def json(self, concepto, system, prompt, esquema, max_tokens=8000, modelo=None):
        self.llamadas.append(concepto)
        self.modelos.append(modelo)
        concepto = concepto.split(":")[-1]
        if self.db is not None:
            if self.db.coste_dia() >= CFG["limites"]["presupuesto_ia_diario_usd"]:
                raise PresupuestoAgotado("agotado")
            self.db.registrar_coste("ia:" + concepto, self.coste)
        if concepto == "respuesta":
            return {"intencion": self.intencion, "respuesta": "Aquí tiene el enlace."}
        if concepto == "revision":
            return {"angulos_nuevos": self.angulos_nuevos, "recomendaciones": ["subir precio"]}
        if concepto == "contenido":
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
        self.assertEqual(self.ag["comercial"].contactar(), 2)
        borradores = os.listdir(os.path.join(self.dir, "salida", "borradores"))
        self.assertEqual(len(borradores), 2)
        with open(os.path.join(self.dir, "salida", "borradores", borradores[0]), "rb") as f:
            contenido = f.read()
        self.assertIn(b"List-Unsubscribe", contenido)
        self.assertIn(b"BAJA", contenido)

    def test_limite_diario_de_emails(self):
        self.ag.ctx.cfg = dict(CFG, limites=dict(CFG["limites"], emails_por_dia=1))
        self.assertEqual(self.ag["comercial"].contactar(), 1)
        self.assertEqual(self.ag["comercial"].contactar(), 0)

    def test_baja_excluye_para_siempre(self):
        self.ag["comercial"].contactar()
        lead = self.ag.db.lead_por_email("a@a.com")
        self.llm.intencion = "no_interesado"
        self.ag["recepcionista"].procesar(lead, "Re: Hola", "No gracias")
        self.assertTrue(self.ag.db.excluido("a@a.com"))
        self.assertFalse(self.ag.db.anadir_lead("A", "a@a.com"))

    def test_interesado_recibe_enlace_y_cuenta_exito(self):
        self.ag["comercial"].contactar()
        lead = self.ag.db.lead_por_email("a@a.com")
        self.ag["recepcionista"].procesar(lead, "Re: Hola", "Me interesa")
        self.assertEqual(self.ag.db.lead_por_email("a@a.com")["estado"], "negociando")
        v = self.ag.db.uno("SELECT exitos FROM variantes WHERE nombre = ?", lead["variante"])
        self.assertEqual(v["exitos"], 1)

    def test_requiere_humano_se_escala(self):
        self.ag["comercial"].contactar()
        self.llm.intencion = "requiere_humano"
        self.ag["recepcionista"].procesar(self.ag.db.lead_por_email("b@b.com"), "Re: Hola", "¿Descuento por 50?")
        self.assertIn("Necesitan tu atención", self.ag.informe())

    def test_freno_de_perdidas_pausa_el_agente(self):
        self.ag.db.registrar_coste("prueba", CFG["limites"]["perdida_maxima_usd"] + 1)
        res = self.ag.ciclo()
        self.assertIn("Freno de pérdidas", res["pausa"])
        self.assertNotIn("comercial:redaccion", self.llm.llamadas)
        # los ingresos no la reactivan solos: debe reanudarla una persona
        self.ag.db.registrar_ingreso("pago1", 500, "eur")
        self.assertIsNotNone(self.ag.riesgo.motivo_pausa())
        self.ag.riesgo.reanudar()
        self.assertIsNone(self.ag.riesgo.motivo_pausa())

    def test_presupuesto_global_detiene_el_ciclo(self):
        self.llm.coste = CFG["limites"]["presupuesto_ia_diario_usd"]
        res = self.ag.ciclo()
        self.assertIn("presupuesto", res)
        self.assertNotIn("analista", res)  # el ciclo se corta al agotar el global

    def test_pausa_manual(self):
        open(self.ag.riesgo.fichero_pausa, "w").close()
        self.assertIn("manual", self.ag.ciclo()["pausa"])

    def test_marketing_una_vez_al_dia(self):
        self.assertEqual(self.ag["marketing"].ejecutar()["piezas"], 1)
        self.assertEqual(self.ag["marketing"].ejecutar()["piezas"], 0)


class TestSubagentes(Base):
    def test_hay_seis_subagentes_en_orden(self):
        self.assertEqual(list(self.ag.subagentes),
                         ["cobrador", "recepcionista", "prospector", "comercial", "marketing", "analista"])

    def test_presupuesto_de_un_subagente_no_frena_a_los_demas(self):
        comercial = self.ag["comercial"]
        self.ag.db.registrar_coste("ia:comercial:redaccion", comercial.presupuesto())
        res = self.ag.ciclo()
        self.assertIn("comercial", res["comercial"])  # mensaje de presupuesto agotado
        self.assertEqual(res["marketing"], {"piezas": 1})  # marketing trabajó igualmente
        self.assertNotIn("comercial:redaccion", self.llm.llamadas)

    def test_cada_subagente_usa_su_modelo(self):
        self.ag["marketing"].ejecutar()
        self.assertEqual(self.llm.modelos[-1], "claude-sonnet-5")

    def test_subagente_que_falla_se_desactiva_y_avisa(self):
        def rompe():
            raise RuntimeError("SMTP caído")
        self.ag["comercial"].ejecutar = rompe
        for _ in range(3):
            self.ag.db.set("marketing_dia", "")  # que el resto tenga trabajo
            res = self.ag.ciclo()
            self.assertEqual(res["marketing"], {"piezas": 1})
        self.assertEqual(self.ag.ciclo()["comercial"], "inactivo")
        self.assertIn("desactivado tras 3 fallos", self.ag.informe())
        self.ag.reactivar()
        self.assertNotEqual(self.ag.ciclo()["comercial"], "inactivo")

    def test_analista_retira_el_peor_angulo_y_propone_otro(self):
        sel = self.ag.ctx.selector
        for nombre, exitos in zip([a["nombre"] for a in sel.activos()], [10, 8, 1, 6]):
            for _ in range(25):
                sel.envio(nombre)
            for _ in range(exitos):
                sel.exito(nombre)
        peor = [a["nombre"] for a in sel.activos()][2]
        res = self.ag["analista"].ejecutar()
        self.assertEqual(res["retirados"], [peor])
        self.assertEqual(res["nuevos"], ["ángulo nuevo"])
        activos = [a["nombre"] for a in sel.activos()]
        self.assertNotIn(peor, activos)
        self.assertIn("ángulo nuevo", activos)
        self.assertEqual(self.ag["analista"].ejecutar(), {"revisado": False})  # una vez al día

    def test_analista_no_juzga_con_pocos_datos(self):
        res = self.ag["analista"].ejecutar()
        self.assertEqual(res["retirados"], [])
        self.assertNotIn("analista:revision", self.llm.llamadas)


class TestSelector(Base):
    def test_prefiere_el_angulo_que_convierte(self):
        self.ag.db.ex("UPDATE variantes SET activo = 0")
        s = Selector(self.ag.db, ["a", "b"], rng=random.Random(0))
        for _ in range(50):
            s.envio("a"); s.envio("b")
        for _ in range(20):
            s.exito("b")
        elegidos = [s.elegir() for _ in range(200)]
        self.assertGreater(elegidos.count("b"), 190)


if __name__ == "__main__":
    unittest.main()
