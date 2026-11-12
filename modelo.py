"""
Rumbo · Simulador de Vida Financiera — Modelo financiero
Evalúa con VPN y TIR tres decisiones conectadas:
  1) Qué crédito tomar        -> costo real (TIR → EA) y VPN de cada opción
  2) Arrendar o comprar        -> VPN y TIR del flujo diferencial (comprar - arrendar)
  3) Cuánto ahorrar al retiro  -> ahorro posible según 1) y 2), valor futuro y VPN
La conexión: lo que pagas en crédito y vivienda reduce tu capacidad de ahorro.
Solo usa Python estándar.
"""


# ----------------------------------------------------------------------
# Funciones financieras base
# ----------------------------------------------------------------------
def ea_a_mensual(ea):
    """Tasa efectiva anual -> efectiva mensual."""
    return (1 + ea) ** (1 / 12) - 1


def mensual_a_ea(im):
    """Tasa efectiva mensual -> efectiva anual."""
    return (1 + im) ** 12 - 1


def cuota_fija(monto, i, n):
    """Cuota fija, sistema francés."""
    if i == 0:
        return monto / n
    return monto * i / (1 - (1 + i) ** -n)


def vpn(tasa, flujos):
    """Valor presente neto. flujos[0] ocurre en t = 0."""
    return sum(f / (1 + tasa) ** t for t, f in enumerate(flujos))


def tir(flujos, bajo=-0.99, alto=1.0, tol=1e-9, max_iter=500):
    """TIR por bisección (tasa por período). None si no hay cambio de signo."""
    f_bajo, f_alto = vpn(bajo, flujos), vpn(alto, flujos)
    if f_bajo * f_alto > 0:
        return None
    for _ in range(max_iter):
        medio = (bajo + alto) / 2
        f_medio = vpn(medio, flujos)
        if abs(f_medio) < tol:
            return medio
        if f_bajo * f_medio < 0:
            alto = medio
        else:
            bajo, f_bajo = medio, f_medio
    return (bajo + alto) / 2


def saldo_credito(monto, i, cuota, k):
    """Saldo pendiente después de k cuotas."""
    if i == 0:
        return monto - cuota * k
    return monto * (1 + i) ** k - cuota * ((1 + i) ** k - 1) / i


# ----------------------------------------------------------------------
# Decisión 1 · Crédito
# ----------------------------------------------------------------------
def evaluar_credito(op, tio_m):
    i = ea_a_mensual(op["tasa_ea"])
    cuota = cuota_fija(op["monto"], i, op["plazo_meses"]) + op["seguro_mensual"]
    neto = op["monto"] - op["comision_inicial"]
    flujos = [neto] + [-cuota] * op["plazo_meses"]
    tir_m = tir(flujos)
    return {
        "nombre": op["nombre"],
        "cuota": cuota,
        "plazo": op["plazo_meses"],
        "total_pagado": cuota * op["plazo_meses"] + op["comision_inicial"],
        "intereses_y_costos": cuota * op["plazo_meses"] + op["comision_inicial"] - op["monto"],
        "costo_real_ea": mensual_a_ea(tir_m) if tir_m is not None else None,
        "tasa_nominal_ea": op["tasa_ea"],
        "vpn": vpn(tio_m, flujos),
    }


# ----------------------------------------------------------------------
# Decisión 2 · Vivienda
# ----------------------------------------------------------------------
def evaluar_vivienda(v, tio_m, horizonte):
    valor = v["valor"]
    inicial = valor * v["pct_inicial"]
    prestamo = valor - inicial
    i_h = ea_a_mensual(v["tasa_hipoteca_ea"])
    n_h = v["plazo_anios"] * 12
    cuota_h = cuota_fija(prestamo, i_h, n_h)
    costos_mes = valor * v["pct_costos"] / 12

    comprar, arrendar = [], []
    arriendo = v["arriendo"]
    for t in range(horizonte + 1):
        if t == 0:
            comprar.append(-inicial - valor * v["pct_escritura"])
            arrendar.append(0.0)
            continue
        if t > 1 and (t - 1) % 12 == 0:
            arriendo *= 1 + v["inc_arriendo"]
        comprar.append(-(cuota_h if t <= n_h else 0) - costos_mes)
        arrendar.append(-arriendo)

    valor_final = valor * (1 + v["valorizacion"]) ** (horizonte / 12)
    saldo = max(saldo_credito(prestamo, i_h, cuota_h, min(horizonte, n_h)), 0)
    patrimonio_final = valor_final - saldo
    comprar_con_venta = comprar[:-1] + [comprar[-1] + patrimonio_final]

    diferencial = [c - a for c, a in zip(comprar_con_venta, arrendar)]
    vpn_dif = vpn(tio_m, diferencial)
    tir_dif = tir(diferencial)

    # Acumulados para la gráfica (sin la venta, para ver el gasto real)
    acum_c, acum_a, sc, sa = [], [], 0.0, 0.0
    for c, a in zip(comprar, arrendar):
        sc += -c
        sa += -a
        acum_c.append(sc)
        acum_a.append(sa)

    return {
        "cuota_hipoteca": cuota_h,
        "cuota_inicial": inicial,
        "costo_mes_comprar": cuota_h + costos_mes,
        "costo_mes_arrendar": v["arriendo"],
        "vpn": vpn_dif,
        "tir_ea": mensual_a_ea(tir_dif) if tir_dif is not None else None,
        "decision": "Comprar" if vpn_dif > 0 else "Arrendar",
        "valor_final": valor_final,
        "patrimonio_final": patrimonio_final,
        "acum_comprar": acum_c,
        "acum_arrendar": acum_a,
    }

# ----------------------------------------------------------------------
# Conexión · flujo de ahorro mes a mes
# ----------------------------------------------------------------------
def serie_ahorro(perfil, credito, vivienda, res_v, meses):
    """Ahorro disponible cada mes = ingreso - gastos - cuota crédito - costo vivienda.
    El crédito solo resta mientras dura; la hipoteca solo mientras dura;
    el arriendo sube cada año. Ingreso y gastos crecen con el incremento salarial."""
    ingreso, gastos = perfil["ingreso"], perfil["gastos"]
    arriendo = vivienda["arriendo"]
    costos_mes = vivienda["valor"] * vivienda["pct_costos"] / 12
    n_h = vivienda["plazo_anios"] * 12
    compra = res_v["decision"] == "Comprar"
    serie = []
    for t in range(1, meses + 1):
        if t > 1 and (t - 1) % 12 == 0:
            ingreso *= 1 + perfil["inc_ingreso"]
            gastos *= 1 + perfil["inc_ingreso"]
            arriendo *= 1 + vivienda["inc_arriendo"]
        c = credito["cuota"] if credito and t <= credito["plazo"] else 0
        if compra:
            viv = (res_v["cuota_hipoteca"] if t <= n_h else 0) + costos_mes
        else:
            viv = arriendo
        serie.append(ingreso - gastos - c - viv)
    return serie


# ----------------------------------------------------------------------
# Decisión 3 · Retiro
# ----------------------------------------------------------------------
def evaluar_retiro(r, ahorros, tio_m):
    i = ea_a_mensual(r["rentabilidad_ea"])
    saldo, serie = 0.0, [0.0]
    for a in ahorros:
        saldo = saldo * (1 + i) + max(a, 0)
        serie.append(saldo)
    n = len(ahorros)
    necesario = r["meta"] * i / ((1 + i) ** n - 1) if i else r["meta"] / n
    flujos = [0.0] + [-max(a, 0) for a in ahorros]
    flujos[-1] += saldo
    return {
        "valor_futuro": saldo,
        "meta": r["meta"],
        "cumple": saldo >= r["meta"],
        "aporte_necesario": necesario,
        "avance": saldo / r["meta"] if r["meta"] else 0,
        "vpn": vpn(tio_m, flujos),
        "serie": serie,
    }


def _p(x):
    return f"{x * 100:.1f}%".replace(".", ",")


# ----------------------------------------------------------------------
# Motor conectado
# ----------------------------------------------------------------------
def simular(perfil, creditos, vivienda, retiro):
    tio_m = ea_a_mensual(perfil["tio_ea"])
    horizonte = perfil["horizonte_anios"] * 12
    meses_retiro = retiro["anios"] * 12

    res_c = [evaluar_credito(c, tio_m) for c in creditos if c["monto"] > 0 and c["plazo_meses"] > 0]
    mejor = min(res_c, key=lambda x: x["costo_real_ea"]) if res_c else None
    menor_cuota = min(res_c, key=lambda x: x["cuota"]) if res_c else None

    res_v = evaluar_vivienda(vivienda, tio_m, horizonte)
    compra = res_v["decision"] == "Comprar"

    ahorros = serie_ahorro(perfil, mejor, vivienda, res_v, meses_retiro)
    res_r = evaluar_retiro(retiro, ahorros, tio_m)

    # Escenario alterno: ¿y si eliges el crédito por la cuota más baja?
    costo_cuota_baja = 0.0
    if mejor and menor_cuota and mejor["nombre"] != menor_cuota["nombre"]:
        alt = serie_ahorro(perfil, menor_cuota, vivienda, res_v, meses_retiro)
        costo_cuota_baja = res_r["valor_futuro"] - evaluar_retiro(retiro, alt, tio_m)["valor_futuro"]

    cuota_credito = mejor["cuota"] if mejor else 0
    gasto_vivienda = res_v["costo_mes_comprar"] if compra else res_v["costo_mes_arrendar"]
    ahorro_hoy = ahorros[0] if ahorros else 0
    deudas = cuota_credito + (res_v["cuota_hipoteca"] if compra else 0)
    endeudamiento = deudas / perfil["ingreso"] if perfil["ingreso"] else 0

    alertas = []
    if costo_cuota_baja > 0:
        alertas.append(("warn", f"La cuota más baja ({menor_cuota['nombre']}) no es el crédito más barato: "
                                f"cuesta {_p(menor_cuota['costo_real_ea'])} EA frente a "
                                f"{_p(mejor['costo_real_ea'])} EA de {mejor['nombre']}."))
    if endeudamiento > 0.40:
        alertas.append(("bad", f"Endeudamiento del {endeudamiento:.0%}: más del 40% de tu ingreso "
                               "se va en deudas. Riesgo alto de sobreendeudamiento."))
    elif endeudamiento > 0.30:
        alertas.append(("warn", f"Endeudamiento del {endeudamiento:.0%}: supera el 30% recomendado."))
    if ahorro_hoy <= 0:
        alertas.append(("bad", "Hoy no te queda capacidad de ahorro: crédito y vivienda consumen todo tu ingreso."))
    if not res_r["cumple"]:
        alertas.append(("warn", "Con este plan no llegas a tu meta de retiro."))
    if not alertas:
        alertas.append(("ok", "Tus tres decisiones son coherentes entre sí. Vas por buen rumbo."))

    return {
        "creditos": res_c, "mejor": mejor, "menor_cuota": menor_cuota,
        "vivienda": res_v, "retiro": res_r, "ahorros": ahorros,
        "ingreso": perfil["ingreso"], "gastos": perfil["gastos"],
        "cuota_credito": cuota_credito, "gasto_vivienda": gasto_vivienda,
        "ahorro_hoy": ahorro_hoy, "endeudamiento": endeudamiento,
        "costo_cuota_baja": costo_cuota_baja, "alertas": alertas,
    }
