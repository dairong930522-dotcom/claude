"""Persistencia en SQLite: leads, mensajes, costes, ingresos y lista de exclusión."""

import sqlite3
from datetime import date, datetime

ESQUEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    contacto TEXT,
    web TEXT,
    notas TEXT,
    fuente TEXT,
    estado TEXT NOT NULL DEFAULT 'nuevo',
    variante TEXT,
    contactos INTEGER NOT NULL DEFAULT 0,
    ultimo_contacto TEXT,
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER,
    direccion TEXT NOT NULL,
    asunto TEXT,
    cuerpo TEXT,
    fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exclusiones (
    email TEXT PRIMARY KEY,
    motivo TEXT,
    fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS costes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    concepto TEXT NOT NULL,
    usd REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ingresos (
    id TEXT PRIMARY KEY,
    fecha TEXT NOT NULL,
    lead_id INTEGER,
    importe REAL NOT NULL,
    moneda TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS variantes (
    nombre TEXT PRIMARY KEY,
    envios INTEGER NOT NULL DEFAULT 0,
    exitos INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS estado (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
CREATE TABLE IF NOT EXISTS escalados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    lead_id INTEGER,
    motivo TEXT,
    atendido INTEGER NOT NULL DEFAULT 0
);
"""


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hoy() -> str:
    return date.today().isoformat()


class DB:
    def __init__(self, ruta: str):
        self.con = sqlite3.connect(ruta)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        self.con.commit()

    def q(self, sql: str, *params):
        return self.con.execute(sql, params).fetchall()

    def uno(self, sql: str, *params):
        return self.con.execute(sql, params).fetchone()

    def ex(self, sql: str, *params) -> int:
        cur = self.con.execute(sql, params)
        self.con.commit()
        return cur.lastrowid

    # --- leads -----------------------------------------------------------
    def anadir_lead(self, empresa, email, contacto="", web="", notas="", fuente="") -> bool:
        email = email.strip().lower()
        if self.excluido(email):
            return False
        try:
            self.ex(
                "INSERT INTO leads (empresa, email, contacto, web, notas, fuente, creado)"
                " VALUES (?,?,?,?,?,?,?)",
                empresa.strip(), email, contacto, web, notas, fuente, ahora(),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def lead_por_email(self, email):
        return self.uno("SELECT * FROM leads WHERE email = ?", email.strip().lower())

    def estado_lead(self, lead_id, estado):
        self.ex("UPDATE leads SET estado = ? WHERE id = ?", estado, lead_id)

    # --- exclusiones (bajas / no contactar) ------------------------------
    def excluir(self, email, motivo):
        email = email.strip().lower()
        self.ex("INSERT OR REPLACE INTO exclusiones VALUES (?,?,?)", email, motivo, ahora())
        self.ex("UPDATE leads SET estado = 'excluido' WHERE email = ?", email)

    def excluido(self, email) -> bool:
        return self.uno("SELECT 1 FROM exclusiones WHERE email = ?", email.strip().lower()) is not None

    # --- dinero ----------------------------------------------------------
    def registrar_coste(self, concepto, usd):
        self.ex("INSERT INTO costes (fecha, concepto, usd) VALUES (?,?,?)", ahora(), concepto, usd)

    def coste_dia(self, dia=None) -> float:
        dia = dia or hoy()
        r = self.uno("SELECT COALESCE(SUM(usd),0) s FROM costes WHERE fecha LIKE ?", dia + "%")
        return r["s"]

    def coste_total(self) -> float:
        return self.uno("SELECT COALESCE(SUM(usd),0) s FROM costes")["s"]

    def registrar_ingreso(self, id_pago, importe, moneda, lead_id=None) -> bool:
        try:
            self.ex("INSERT INTO ingresos VALUES (?,?,?,?,?)", id_pago, ahora(), lead_id, importe, moneda)
            return True
        except sqlite3.IntegrityError:
            return False

    def ingreso_total(self) -> float:
        return self.uno("SELECT COALESCE(SUM(importe),0) s FROM ingresos")["s"]

    def ingreso_dia(self, dia=None) -> float:
        dia = dia or hoy()
        r = self.uno("SELECT COALESCE(SUM(importe),0) s FROM ingresos WHERE fecha LIKE ?", dia + "%")
        return r["s"]

    # --- estado clave/valor ----------------------------------------------
    def get(self, clave, defecto=None):
        r = self.uno("SELECT valor FROM estado WHERE clave = ?", clave)
        return r["valor"] if r else defecto

    def set(self, clave, valor):
        self.ex("INSERT OR REPLACE INTO estado VALUES (?,?)", clave, str(valor))

    def escalar(self, lead_id, motivo):
        self.ex("INSERT INTO escalados (fecha, lead_id, motivo) VALUES (?,?,?)", ahora(), lead_id, motivo)
