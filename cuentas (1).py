"""
Rumbo · Cuentas de usuario y registro de simulaciones.

Guarda los datos en Google Sheets (hojas "usuarios" y "simulaciones").
Si la app aún no tiene las credenciales configuradas, usa un almacenamiento
temporal en memoria para que se pueda probar (se borra al reiniciar).

Seguridad:
- El PIN nunca se guarda: se guarda un hash PBKDF2 con sal.
- Solo se guardan datos con autorización explícita (Ley 1581 de 2012).
"""

import hashlib
import hmac
import secrets as _secrets
from datetime import datetime, timedelta, timezone

import streamlit as st

TZ_BOGOTA = timezone(timedelta(hours=-5))

COLS_USUARIOS = ["cedula", "nombre", "pin_hash", "sal", "fecha_registro", "autorizacion_datos"]
COLS_SIMULACIONES = [
    "fecha", "cedula", "nombre",
    "ingreso", "gastos_fijos", "tio_ea",
    "mejor_credito", "costo_real_credito_ea", "cuota_credito",
    "decision_vivienda", "vpn_vivienda", "tir_vivienda_ea",
    "ahorro_mensual_hoy", "endeudamiento",
    "valor_futuro_retiro", "meta_retiro", "cumple_meta",
]


def ahora():
    return datetime.now(TZ_BOGOTA).strftime("%Y-%m-%d %H:%M")


def hash_pin(pin, sal):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), sal.encode(), 120_000).hex()


# ----------------------------------------------------------------------
# Almacenamiento
# ----------------------------------------------------------------------
class AlmacenMemoria:
    """Respaldo temporal mientras no se configura Google Sheets."""
    persistente = False

    def __init__(self):
        self.usuarios, self.simulaciones = [], []

    def buscar_usuario(self, cedula):
        return next((u for u in self.usuarios if str(u["cedula"]) == cedula), None)

    def crear_usuario(self, fila):
        self.usuarios.append(fila)

    def guardar_simulacion(self, fila):
        self.simulaciones.append(fila)

    def simulaciones_de(self, cedula):
        return [s for s in self.simulaciones if str(s["cedula"]) == cedula]


class AlmacenSheets:
    """Google Sheets mediante una cuenta de servicio (st.secrets)."""
    persistente = True

    def __init__(self, credenciales, url_hoja):
        import gspread
        cliente = gspread.service_account_from_dict(dict(credenciales))
        libro = cliente.open_by_url(url_hoja)
        self.h_usuarios = self._hoja(libro, "usuarios", COLS_USUARIOS)
        self.h_simulaciones = self._hoja(libro, "simulaciones", COLS_SIMULACIONES)

    @staticmethod
    def _hoja(libro, nombre, columnas):
        import gspread
        try:
            hoja = libro.worksheet(nombre)
        except gspread.WorksheetNotFound:
            hoja = libro.add_worksheet(title=nombre, rows=1000, cols=len(columnas))
        if hoja.row_values(1) != columnas:
            hoja.update(range_name="A1", values=[columnas])
        return hoja

    def buscar_usuario(self, cedula):
        for u in self.h_usuarios.get_all_records(numericise_ignore=["all"]):
            if str(u["cedula"]) == cedula:
                return u
        return None

    def crear_usuario(self, fila):
        self.h_usuarios.append_row([fila[c] for c in COLS_USUARIOS], value_input_option="RAW")

    def guardar_simulacion(self, fila):
        self.h_simulaciones.append_row([fila[c] for c in COLS_SIMULACIONES], value_input_option="RAW")

    def simulaciones_de(self, cedula):
        return [s for s in self.h_simulaciones.get_all_records(numericise_ignore=["all"])
                if str(s["cedula"]) == cedula]


@st.cache_resource(show_spinner=False)
def _almacen_sheets(credenciales_json, url):
    import json
    return AlmacenSheets(json.loads(credenciales_json), url)


@st.cache_resource(show_spinner=False)
def _almacen_memoria():
    return AlmacenMemoria()


def obtener_almacen():
    """Devuelve (almacen, error). Si no hay credenciales, usa memoria."""
    import json
    try:
        url = st.secrets.get("sheet_url")
        # Opción fácil: el JSON de la cuenta de servicio pegado tal cual en gcp_json
        cred_json = st.secrets.get("gcp_json")
        if not cred_json and st.secrets.get("gcp_service_account"):
            cred_json = json.dumps(dict(st.secrets["gcp_service_account"]))
    except Exception:
        cred_json, url = None, None
    if not cred_json or not url:
        return _almacen_memoria(), None
    try:
        return _almacen_sheets(cred_json.strip(), url.strip()), None
    except Exception as e:
        return _almacen_memoria(), f"No se pudo conectar con Google Sheets ({type(e).__name__}). Revisa la configuración."


# ----------------------------------------------------------------------
# Validaciones y acciones
# ----------------------------------------------------------------------
def validar_cedula(c):
    c = c.strip().replace(".", "").replace(" ", "")
    return c if c.isdigit() and 5 <= len(c) <= 12 else None


def registrar(almacen, nombre, cedula, pin, pin2, autoriza):
    nombre = " ".join(nombre.split())
    ced = validar_cedula(cedula)
    if len(nombre) < 3:
        return None, "Escribe tu nombre completo."
    if not ced:
        return None, "La cédula debe tener solo números (entre 5 y 12 dígitos)."
    if not (pin.isdigit() and len(pin) == 4):
        return None, "El PIN debe tener exactamente 4 números."
    if pin != pin2:
        return None, "Los dos PIN no coinciden."
    if not autoriza:
        return None, "Para crear tu cuenta debes autorizar el tratamiento de tus datos."
    if almacen.buscar_usuario(ced):
        return None, "Ya existe una cuenta con esa cédula. Usa la opción Ingresar."
    sal = _secrets.token_hex(16)
    almacen.crear_usuario({
        "cedula": ced, "nombre": nombre, "pin_hash": hash_pin(pin, sal), "sal": sal,
        "fecha_registro": ahora(), "autorizacion_datos": "SI",
    })
    return {"cedula": ced, "nombre": nombre}, None


def ingresar(almacen, cedula, pin):
    ced = validar_cedula(cedula)
    if not ced or not pin:
        return None, "Escribe tu cédula y tu PIN."
    u = almacen.buscar_usuario(ced)
    if not u or not hmac.compare_digest(hash_pin(pin, str(u["sal"])), str(u["pin_hash"])):
        return None, "Cédula o PIN incorrectos."
    return {"cedula": ced, "nombre": u["nombre"]}, None


def fila_simulacion(usuario, perfil, r):
    mejor, viv, ret = r["mejor"], r["vivienda"], r["retiro"]
    return {
        "fecha": ahora(), "cedula": usuario["cedula"], "nombre": usuario["nombre"],
        "ingreso": round(perfil["ingreso"]), "gastos_fijos": round(perfil["gastos"]),
        "tio_ea": round(perfil["tio_ea"], 4),
        "mejor_credito": mejor["nombre"] if mejor else "Sin crédito",
        "costo_real_credito_ea": round(mejor["costo_real_ea"], 4) if mejor else "",
        "cuota_credito": round(r["cuota_credito"]),
        "decision_vivienda": viv["decision"], "vpn_vivienda": round(viv["vpn"]),
        "tir_vivienda_ea": round(viv["tir_ea"], 4) if viv["tir_ea"] is not None else "",
        "ahorro_mensual_hoy": round(r["ahorro_hoy"]), "endeudamiento": round(r["endeudamiento"], 4),
        "valor_futuro_retiro": round(ret["valor_futuro"]), "meta_retiro": round(ret["meta"]),
        "cumple_meta": "SI" if ret["cumple"] else "NO",
    }
