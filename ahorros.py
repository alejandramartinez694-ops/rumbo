"""
Rumbo · Mis ahorros
Registra dónde tiene la persona su dinero (cuenta de ahorros, CDT, fondos...)
y calcula cuánto le rinde de verdad: rendimiento bruto, retención en la fuente,
rendimiento neto, tasa neta efectiva anual y rentabilidad real (frente a la inflación).
Los registros se guardan en la hoja "ahorros" de Google Sheets.
"""

import secrets as _secrets

from cuentas import ahora

# Retención de referencia por tipo de producto (editable en la app; verificar con la entidad)
TIPOS = {
    "Cuenta de ahorros": 7.0,
    "CDT": 4.0,
    "Fondo de inversión colectiva (FIC)": 0.0,
    "Fondo de pensiones voluntarias": 0.0,
    "Otro": 0.0,
}

COLS_AHORROS = [
    "id", "fecha", "cedula", "nombre", "tipo", "entidad", "monto", "tasa_ea",
    "plazo_meses", "retencion", "rendimiento_neto", "valor_final", "tasa_neta_ea",
]


# ----------------------------------------------------------------------
# Cálculo
# ----------------------------------------------------------------------
def calcular(monto, tasa_ea, meses, retencion, inflacion):
    """Rendimiento de un ahorro con interés compuesto a tasa efectiva anual."""
    anios = meses / 12
    valor_bruto = monto * (1 + tasa_ea) ** anios
    rend_bruto = valor_bruto - monto
    ret = max(rend_bruto, 0) * retencion
    rend_neto = rend_bruto - ret
    valor_final = monto + rend_neto
    tasa_neta = (valor_final / monto) ** (1 / anios) - 1 if monto > 0 and anios > 0 else 0
    tasa_real = (1 + tasa_neta) / (1 + inflacion) - 1
    return {
        "rend_bruto": rend_bruto, "retencion": ret, "rend_neto": rend_neto,
        "valor_final": valor_final, "tasa_neta_ea": tasa_neta, "tasa_real": tasa_real,
        "rend_mensual_prom": rend_neto / meses if meses else 0,
    }


# ----------------------------------------------------------------------
# Almacenamiento (Google Sheets o memoria, igual que cuentas.py)
# ----------------------------------------------------------------------
def _hoja(almacen):
    if not almacen.persistente:
        if not hasattr(almacen, "ahorros"):
            almacen.ahorros = []
        return None
    if not hasattr(almacen, "h_ahorros"):
        from cuentas import AlmacenSheets
        libro = almacen.h_usuarios.spreadsheet
        almacen.h_ahorros = AlmacenSheets._hoja(libro, "ahorros", COLS_AHORROS)
    return almacen.h_ahorros


def guardar(almacen, usuario, datos, calc):
    fila = {
        "id": _secrets.token_hex(4), "fecha": ahora(),
        "cedula": usuario["cedula"], "nombre": usuario["nombre"],
        "tipo": datos["tipo"], "entidad": datos["entidad"] or "-",
        "monto": round(datos["monto"]), "tasa_ea": round(datos["tasa_ea"], 4),
        "plazo_meses": int(datos["meses"]), "retencion": round(datos["retencion"], 4),
        "rendimiento_neto": round(calc["rend_neto"]), "valor_final": round(calc["valor_final"]),
        "tasa_neta_ea": round(calc["tasa_neta_ea"], 4),
    }
    hoja = _hoja(almacen)
    if hoja is None:
        almacen.ahorros.append(fila)
    else:
        hoja.append_row([fila[c] for c in COLS_AHORROS], value_input_option="RAW")


def listar(almacen, cedula):
    hoja = _hoja(almacen)
    filas = almacen.ahorros if hoja is None else hoja.get_all_records(numericise_ignore=["all"])
    return [f for f in filas if str(f["cedula"]) == cedula]


def eliminar(almacen, cedula, id_ahorro):
    hoja = _hoja(almacen)
    if hoja is None:
        almacen.ahorros = [f for f in almacen.ahorros
                           if not (str(f["cedula"]) == cedula and str(f["id"]) == id_ahorro)]
        return
    for i, f in enumerate(hoja.get_all_records(numericise_ignore=["all"]), start=2):
        if str(f["cedula"]) == cedula and str(f["id"]) == id_ahorro:
            hoja.delete_rows(i)
            return
