"""
Rumbo · Seguimiento de créditos reales e inversiones.

Mis créditos:
  - Tabla de amortización (sistema francés) de un crédito que la persona ya tiene.
  - Abonos extra a capital, con la opción de reducir el plazo o reducir la cuota.
  - Cuánto debe hoy, cuántos intereses lleva pagados y cuánto se ahorra con los abonos.

Mis inversiones:
  - Aportes, retiros y valor actual con sus fechas.
  - TIR real de la inversión con fechas exactas (equivalente a TIR.NO.PER / XIRR).

Todo se guarda en Google Sheets (o en memoria en modo de prueba).
"""

import secrets as _secrets
from datetime import date

from cuentas import AlmacenSheets, ahora
from modelo import cuota_fija, ea_a_mensual

HOJAS = {
    "creditos": ["id", "fecha_registro", "cedula", "entidad", "monto", "tasa_ea",
                 "plazo_meses", "fecha_desembolso", "seguro_mensual"],
    "abonos": ["id", "credito_id", "cedula", "fecha", "valor", "modalidad"],
    "inversiones": ["id", "fecha_registro", "cedula", "nombre", "tipo"],
    "movimientos": ["id", "inversion_id", "cedula", "fecha", "tipo", "valor"],
}
MODALIDADES = ["Reducir plazo", "Reducir cuota"]
TIPOS_MOV = ["Aporte", "Retiro", "Valor actual"]


# ----------------------------------------------------------------------
# Almacenamiento genérico
# ----------------------------------------------------------------------
def _hoja(almacen, nombre):
    if not almacen.persistente:
        if not hasattr(almacen, "tablas"):
            almacen.tablas = {}
        almacen.tablas.setdefault(nombre, [])
        return None
    if not hasattr(almacen, "h_seg"):
        almacen.h_seg = {}
    if nombre not in almacen.h_seg:
        almacen.h_seg[nombre] = AlmacenSheets._hoja(almacen.h_usuarios.spreadsheet, nombre, HOJAS[nombre])
    return almacen.h_seg[nombre]


def agregar(almacen, nombre, fila):
    fila = {"id": _secrets.token_hex(4), **fila}
    hoja = _hoja(almacen, nombre)
    if hoja is None:
        almacen.tablas[nombre].append(fila)
    else:
        hoja.append_row([fila.get(c, "") for c in HOJAS[nombre]], value_input_option="RAW")
    return fila["id"]


def leer(almacen, nombre, cedula):
    hoja = _hoja(almacen, nombre)
    filas = almacen.tablas[nombre] if hoja is None else hoja.get_all_records(numericise_ignore=["all"])
    return [f for f in filas if str(f["cedula"]) == cedula]


def borrar(almacen, nombre, cedula, campo, valor):
    """Borra las filas de la persona cuyo `campo` sea `valor`."""
    hoja = _hoja(almacen, nombre)
    if hoja is None:
        almacen.tablas[nombre] = [f for f in almacen.tablas[nombre]
                                  if not (str(f["cedula"]) == cedula and str(f[campo]) == str(valor))]
        return
    filas = hoja.get_all_records(numericise_ignore=["all"])
    indices = [i for i, f in enumerate(filas, start=2)
               if str(f["cedula"]) == cedula and str(f[campo]) == str(valor)]
    for i in reversed(indices):
        hoja.delete_rows(i)


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def fecha(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return date.today()


# ----------------------------------------------------------------------
# Créditos: amortización con abonos
# ----------------------------------------------------------------------
def meses_entre(inicio, fin):
    """Cuotas completas que han vencido entre dos fechas."""
    m = (fin.year - inicio.year) * 12 + (fin.month - inicio.month)
    if fin.day < inicio.day:
        m -= 1
    return max(m, 0)


def amortizar(monto, tasa_ea, plazo, abonos=()):
    """Tabla mes a mes. `abonos` = [(mes, valor, modalidad)], aplicados después de la cuota de ese mes."""
    i = ea_a_mensual(tasa_ea)
    cuota = cuota_fija(monto, i, plazo)
    por_mes = {}
    for k, v, mod in abonos:
        por_mes.setdefault(int(k), []).append((v, mod))

    saldo, filas, k = monto, [], 0

    def aplicar_abonos(k, saldo, cuota):
        abono_total = 0.0
        for v, mod in por_mes.get(k, []):
            v = min(v, saldo)
            saldo -= v
            abono_total += v
            restantes = plazo - k
            if mod == "Reducir cuota" and saldo > 0.5 and restantes > 0:
                cuota = cuota_fija(saldo, i, restantes)
        return saldo, cuota, abono_total

    saldo, cuota, ab0 = aplicar_abonos(0, saldo, cuota)
    while saldo > 0.5 and k < plazo * 2:
        k += 1
        interes = saldo * i
        pago = min(cuota, saldo + interes)
        capital = pago - interes
        saldo -= capital
        saldo, cuota, abono = aplicar_abonos(k, saldo, cuota)
        filas.append({"mes": k, "cuota": pago, "interes": interes, "capital": capital,
                      "abono": abono + (ab0 if k == 1 else 0), "saldo": max(saldo, 0)})
    return filas


def analizar_credito(c, abonos_reg, hoy=None):
    hoy = hoy or date.today()
    monto, tasa, plazo = num(c["monto"]), num(c["tasa_ea"]), int(num(c["plazo_meses"]))
    inicio = fecha(c["fecha_desembolso"])
    seguro = num(c.get("seguro_mensual", 0))
    ab = [(meses_entre(inicio, fecha(a["fecha"])), num(a["valor"]), a["modalidad"]) for a in abonos_reg]

    base = amortizar(monto, tasa, plazo)
    real = amortizar(monto, tasa, plazo, ab)
    k_hoy = min(meses_entre(inicio, hoy), len(real))

    pagado = real[:k_hoy]
    saldo_hoy = real[k_hoy - 1]["saldo"] if k_hoy else monto - sum(v for k, v, _ in ab if k == 0)
    int_base = sum(f["interes"] for f in base)
    int_real = sum(f["interes"] for f in real)
    cuota_actual = real[k_hoy]["cuota"] if k_hoy < len(real) else 0
    return {
        "inicio": inicio, "monto": monto, "tasa": tasa, "plazo": plazo, "seguro": seguro,
        "base": base, "real": real, "cuotas_pagadas": k_hoy,
        "saldo_hoy": max(saldo_hoy, 0), "intereses_pagados": sum(f["interes"] for f in pagado),
        "capital_pagado": sum(f["capital"] + f["abono"] for f in pagado),
        "abonos_total": sum(v for _, v, _ in ab),
        "intereses_base": int_base, "intereses_real": int_real,
        "ahorro_intereses": int_base - int_real,
        "meses_restantes": max(len(real) - k_hoy, 0),
        "meses_ahorrados": len(base) - len(real),
        "cuota_actual": cuota_actual + (seguro if cuota_actual else 0),
        "cuota_original": base[0]["cuota"] + seguro if base else 0,
    }


def simular_abono(c, abonos_reg, valor, modalidad, fecha_abono):
    """Cuánto se ahorra con un abono nuevo (sin guardarlo)."""
    actual = analizar_credito(c, abonos_reg)
    nuevo = analizar_credito(c, list(abonos_reg) + [
        {"fecha": fecha_abono.isoformat(), "valor": valor, "modalidad": modalidad}])
    return {
        "ahorro_intereses": actual["intereses_real"] - nuevo["intereses_real"],
        "meses_menos": len(actual["real"]) - len(nuevo["real"]),
        "cuota_nueva": nuevo["cuota_actual"],
    }


# ----------------------------------------------------------------------
# Inversiones: TIR con fechas exactas (XIRR)
# ----------------------------------------------------------------------
def _vpn_fechas(tasa, flujos):
    t0 = flujos[0][0]
    return sum(v / (1 + tasa) ** ((d - t0).days / 365) for d, v in flujos)


def tir_fechas(flujos, bajo=-0.95, alto=10.0):
    """TIR anual con fechas exactas. `flujos` = [(fecha, valor)] ordenados por fecha."""
    if len(flujos) < 2 or (flujos[-1][0] - flujos[0][0]).days < 1:
        return None
    f_bajo, f_alto = _vpn_fechas(bajo, flujos), _vpn_fechas(alto, flujos)
    if f_bajo * f_alto > 0:
        return None
    for _ in range(300):
        medio = (bajo + alto) / 2
        f_medio = _vpn_fechas(medio, flujos)
        if abs(f_medio) < 1e-6:
            break
        if f_bajo * f_medio < 0:
            alto = medio
        else:
            bajo, f_bajo = medio, f_medio
    return (bajo + alto) / 2


def analizar_inversion(movs):
    movs = sorted(movs, key=lambda m: fecha(m["fecha"]))
    aportes = sum(num(m["valor"]) for m in movs if m["tipo"] == "Aporte")
    retiros = sum(num(m["valor"]) for m in movs if m["tipo"] == "Retiro")
    valores = [m for m in movs if m["tipo"] == "Valor actual"]
    ultimo = valores[-1] if valores else None
    valor_actual = num(ultimo["valor"]) if ultimo else 0.0

    flujos = [(fecha(m["fecha"]), -num(m["valor"]) if m["tipo"] == "Aporte" else num(m["valor"]))
              for m in movs if m["tipo"] in ("Aporte", "Retiro")]
    if ultimo:
        flujos.append((fecha(ultimo["fecha"]), valor_actual))
    flujos.sort(key=lambda x: x[0])
    ganancia = retiros + valor_actual - aportes
    return {
        "aportes": aportes, "retiros": retiros, "valor_actual": valor_actual,
        "fecha_valor": fecha(ultimo["fecha"]) if ultimo else None,
        "ganancia": ganancia, "tir": tir_fechas(flujos) if ultimo else None,
        "movs": movs,
    }
