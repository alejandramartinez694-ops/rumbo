"""
Rumbo · Simulador de Vida Financiera
App en Streamlit que evalúa con VPN y TIR tres decisiones conectadas:
crédito, vivienda (arrendar o comprar) y ahorro para el retiro.

Ejecutar:  streamlit run app.py
"""

import os

import streamlit as st
import plotly.graph_objects as go

from datetime import date

import ahorros as ah
import seguimiento as seg
import modelo
from cuentas import obtener_almacen, ingresar, registrar, fila_simulacion
from cuentas import ahora as cuentas_ahora
from modelo import simular, ea_a_mensual

# Rango de búsqueda de la TIR que no se desborda con horizontes largos
if modelo.tir.__defaults__[0] < -0.5:
    modelo.tir.__defaults__ = (-0.5,) + modelo.tir.__defaults__[1:]

# ----------------------------------------------------------------------
# Paleta Rumbo
# ----------------------------------------------------------------------
NAVY = "#12263A"
NAVY_DEEP = "#0A1724"
AMBER = "#E9A23B"
AMBER_SOFT = "#FBEBD2"
CREAM = "#F4F2EE"
SLATE = "#3E4F60"
MUTED = "#6B7A89"
LINE = "#E2DDD3"
NAVY_SOFT = "#B9C3CD"
GREEN = "#2E8B6B"
GREEN_SOFT = "#DCEFE7"
RED = "#C0492F"
RED_SOFT = "#F7DED7"

st.set_page_config(
    page_title="Rumbo · Simulador de vida financiera",
    page_icon=next((p for p in ("assets/icono.png", "icono.png") if os.path.exists(p)), "📈"),
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------------------------------------------------------
# Formatos (estilo Colombia: punto de miles, coma decimal)
# ----------------------------------------------------------------------
def num(x, dec=0):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def cop(x):
    return ("-" if x < 0 else "") + "$" + num(abs(x))


def dinero(contenedor, etiqueta, *args, **kwargs):
    """Campo de dinero: muestra debajo el valor con puntos de miles."""
    valor = contenedor.number_input(etiqueta, *args, **kwargs)
    contenedor.caption(f"= {cop(valor)}")
    return valor


def millones(x):
    return ("-" if x < 0 else "") + "$" + num(abs(x) / 1e6, 1) + " M"


def pct(x, dec=1):
    return "—" if x is None else num(x * 100, dec) + "%"


def html(s):
    """Renderiza HTML sin que Markdown lo convierta en bloque de código."""
    st.markdown(" ".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Estilos
# ----------------------------------------------------------------------
LOGO_SVG = f"""
<svg width="{{s}}" height="{{s}}" viewBox="0 0 64 64" aria-hidden="true">
<path d="M8 36 L27 18 L38 28 L54 12" fill="none" stroke="{{c}}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M44 12 L54 12 L54 22" fill="none" stroke="{{c}}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="12" cy="52" r="5" fill="{AMBER}"/>
<path d="M24 52 L52 52" stroke="{{c}}" stroke-width="6" stroke-linecap="round"/>
</svg>"""


def logo(size, color):
    return LOGO_SVG.replace("{s}", str(size)).replace("{c}", color)


html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&display=swap');
html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp li, .stApp td, .stApp th {{
font-family: 'Sora', sans-serif !important;
}}
[data-testid="stIconMaterial"], .material-symbols-rounded {{
font-family: 'Material Symbols Rounded' !important;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1240px; }}

/* Barra lateral */
section[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {LINE}; }}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}
.side-brand {{ display:flex; align-items:center; gap:10px; margin: 4px 0 18px; }}
.side-brand span {{ font-size: 24px; font-weight: 700; letter-spacing: -0.8px; color: {NAVY}; }}
.side-title {{ font-size: 11px; font-weight: 600; letter-spacing: 1.6px; text-transform: uppercase;
color: {MUTED}; margin: 22px 0 8px; }}
[data-testid="stExpander"] {{ border-radius: 12px; border-color: {LINE}; }}

/* Hero */
.hero {{ background: {NAVY}; border-radius: 22px; padding: 30px 34px; display:flex;
align-items:center; justify-content:space-between; gap: 24px; flex-wrap: wrap; margin-bottom: 22px; }}
.hero-left {{ display:flex; align-items:center; gap: 18px; }}
.hero-word {{ font-size: 46px; font-weight: 700; letter-spacing: -1.8px; color: {CREAM}; line-height: 1; }}
.hero-sub {{ font-size: 11.5px; letter-spacing: 2.4px; text-transform: uppercase; color: #AEB9C4; margin-top: 6px; }}
.hero-right {{ max-width: 430px; color: #D5DCE3; font-size: 14px; line-height: 1.55; }}
.hero-right b {{ color: {AMBER}; font-weight: 600; }}

/* Tarjetas KPI */
.kpi {{ background:#FFFFFF; border:1px solid {LINE}; border-radius: 18px; padding: 18px 20px; height: 100%; }}
.kpi-label {{ display:flex; align-items:center; gap:8px; font-size: 11px; font-weight: 600;
letter-spacing: 1.3px; text-transform: uppercase; color: {MUTED}; }}
.dot {{ width: 8px; height: 8px; border-radius: 50%; display:inline-block; }}
.kpi-value {{ font-size: 26px; font-weight: 700; color: {NAVY}; letter-spacing: -0.8px; margin: 10px 0 4px; }}
.kpi-sub {{ font-size: 13px; color: {SLATE}; }}

/* Pestañas */
div[role="tablist"] {{ gap: 6px; background:#FFFFFF; padding: 6px; border-radius: 14px;
border: 1px solid {LINE}; margin-top: 10px; }}
[role="tab"] {{ height: 40px; border-radius: 10px !important; padding: 0 18px !important; color: {SLATE};
background: transparent; }}
[role="tab"]:hover {{ background: {CREAM}; }}
[role="tab"][aria-selected="true"] {{ background: {NAVY} !important; }}
[role="tab"][aria-selected="true"] p {{ color: {CREAM} !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* Tarjetas de contenido */
div[data-testid="stVerticalBlockBorderWrapper"] {{ background: #FFFFFF; border-radius: 18px; border-color: {LINE} !important; }}
.h-sec {{ font-size: 19px; font-weight: 700; color: {NAVY}; letter-spacing: -0.4px; margin: 6px 0 2px; }}
.p-sec {{ font-size: 14px; color: {SLATE}; margin-bottom: 10px; line-height: 1.55; }}

/* Alertas */
.alerta {{ display:flex; gap: 12px; align-items:flex-start; padding: 13px 15px; border-radius: 14px;
font-size: 13.5px; line-height: 1.5; margin-bottom: 10px; color: {NAVY}; }}
.alerta .dot {{ margin-top: 6px; flex: 0 0 8px; }}
.alerta.ok {{ background: {GREEN_SOFT}; }} .alerta.ok .dot {{ background: {GREEN}; }}
.alerta.warn {{ background: {AMBER_SOFT}; }} .alerta.warn .dot {{ background: {AMBER}; }}
.alerta.bad {{ background: {RED_SOFT}; }} .alerta.bad .dot {{ background: {RED}; }}

/* Cadena de decisiones */
.cadena {{ display:flex; align-items:stretch; gap: 8px; margin: 6px 0 4px; }}
.eslabon {{ flex:1; background: {CREAM}; border-radius: 14px; padding: 12px 14px; }}
.eslabon small {{ display:block; font-size: 10.5px; letter-spacing: 1.2px; text-transform: uppercase; color: {MUTED}; }}
.eslabon b {{ display:block; font-size: 15px; color: {NAVY}; margin-top: 4px; }}
.flecha {{ align-self:center; color: {AMBER}; font-weight: 700; }}

/* Dato destacado */
.destacado {{ background: {NAVY}; color: {CREAM}; border-radius: 16px; padding: 18px 20px; margin-top: 12px; }}
.destacado small {{ font-size: 11px; letter-spacing: 1.3px; text-transform: uppercase; color: #AEB9C4; }}
.destacado b {{ display:block; font-size: 28px; color: {AMBER}; letter-spacing: -0.8px; margin: 6px 0; }}
.destacado span {{ font-size: 13px; color: #D5DCE3; line-height: 1.5; }}

/* Veredicto */
.veredicto {{ display:inline-flex; align-items:center; gap: 10px; padding: 8px 16px; border-radius: 999px;
font-weight: 600; font-size: 14px; }}
.veredicto.si {{ background: {GREEN_SOFT}; color: #1D5E47; }}
.veredicto.no {{ background: {AMBER_SOFT}; color: #7A4E0E; }}

/* Barra de progreso */
.progreso {{ background: {CREAM}; border-radius: 999px; height: 12px; overflow: hidden; margin: 8px 0 4px; }}
.progreso div {{ height: 100%; border-radius: 999px; }}

.pie {{ text-align:center; font-size: 12px; color: {MUTED}; margin-top: 36px; }}

/* Usuario */
.usuario {{ background: {CREAM}; border-radius: 14px; padding: 12px 14px; margin-bottom: 8px; }}
.usuario small {{ display:block; font-size: 10.5px; letter-spacing: 1.2px; text-transform: uppercase; color: {MUTED}; }}
.usuario b {{ display:block; font-size: 16px; color: {NAVY}; margin-top: 2px; }}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"] {{
background: {NAVY}; border-color: {NAVY}; color: {CREAM}; border-radius: 12px; font-weight: 600; }}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primaryFormSubmit"]:hover {{
background: {NAVY_DEEP}; border-color: {NAVY_DEEP}; color: {AMBER}; }}
</style>
""")


# ----------------------------------------------------------------------
# Gráficas
# ----------------------------------------------------------------------
def estilo(fig, alto=340, titulo=None):
    fig.update_layout(
        title=dict(text=titulo, x=0, xanchor="left", font=dict(size=15, color=NAVY)) if titulo else None,
        height=alto,
        margin=dict(l=6, r=6, t=52 if titulo else 16, b=6),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Sora, sans-serif", color=SLATE, size=12),
        separators=",.",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=1, xanchor="right", font=dict(size=12)),
        hoverlabel=dict(bgcolor=NAVY, font=dict(color=CREAM, family="Sora")),
    )
    fig.update_xaxes(showgrid=False, linecolor=LINE, ticks="", tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=LINE, zeroline=False, tickfont=dict(color=MUTED), tickprefix="$", ticksuffix=" M",
                     tickformat=",.1~f")
    return fig


CONFIG_GRAFICA = {"displayModeBar": False}


# ----------------------------------------------------------------------
# Cuentas · ingreso y registro
# ----------------------------------------------------------------------
almacen, error_almacen = obtener_almacen()

TEXTO_AUTORIZACION = (
    "Autorizo a Rumbo, proyecto académico de Ingeniería Económica, a recolectar y tratar mi nombre, "
    "número de cédula y los datos de mis simulaciones con fines exclusivamente académicos, conforme a la "
    "Ley 1581 de 2012. Sé que puedo pedir la consulta, corrección o eliminación de mis datos en cualquier momento."
)


def pantalla_ingreso():
    html('<style>section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],'
         '[data-testid="stExpandSidebarButton"] { display: none; }</style>')
    _, centro, _ = st.columns([1, 1.6, 1])
    with centro:
        html(f"""
        <div class="hero" style="flex-direction:column;align-items:flex-start;margin-top:4vh">
        <div class="hero-left">{logo(54, CREAM)}
        <div><div class="hero-word">rumbo</div><div class="hero-sub">Simulador de vida financiera</div></div>
        </div>
        <div class="hero-right" style="max-width:none">Crea tu cuenta para guardar tus simulaciones y ver
        cómo cambian tus decisiones con el tiempo.</div>
        </div>
        """)
        if error_almacen:
            st.error(error_almacen)
        elif not almacen.persistente:
            st.info("Modo de prueba: los datos se guardan solo mientras la app esté encendida. "
                    "Conecta Google Sheets para guardarlos de forma permanente.")

        intentos = st.session_state.get("intentos", 0)
        with st.container(border=True):
            t_in, t_reg = st.tabs(["Ingresar", "Crear cuenta"])
            with t_in:
                with st.form("ingresar", border=False):
                    ced = st.text_input("Número de cédula", placeholder="Solo números")
                    pin = st.text_input("PIN de 4 dígitos", type="password", max_chars=4)
                    ok = st.form_submit_button("Ingresar", type="primary", width="stretch")
                if ok:
                    if intentos >= 5:
                        st.error("Demasiados intentos fallidos. Recarga la página e inténtalo más tarde.")
                    else:
                        usuario, err = ingresar(almacen, ced, pin)
                        if err:
                            st.session_state["intentos"] = intentos + 1
                            st.error(err)
                        else:
                            st.session_state["usuario"] = usuario
                            st.session_state["intentos"] = 0
                            st.rerun()
            with t_reg:
                with st.form("registro", border=False):
                    nom = st.text_input("Nombre completo")
                    ced_r = st.text_input("Número de cédula ", placeholder="Solo números")
                    a, b = st.columns(2)
                    pin_r = a.text_input("Crea un PIN (4 dígitos)", type="password", max_chars=4)
                    pin_r2 = b.text_input("Repite el PIN", type="password", max_chars=4)
                    autoriza = st.checkbox(TEXTO_AUTORIZACION)
                    ok_r = st.form_submit_button("Crear cuenta", type="primary", width="stretch")
                if ok_r:
                    usuario, err = registrar(almacen, nom, ced_r, pin_r, pin_r2, autoriza)
                    if err:
                        st.error(err)
                    else:
                        st.session_state["usuario"] = usuario
                        st.rerun()
        html('<div class="pie">Herramienta educativa · No constituye asesoría financiera.</div>')


if "usuario" not in st.session_state:
    pantalla_ingreso()
    st.stop()

usuario = st.session_state["usuario"]


# ----------------------------------------------------------------------
# Barra lateral · entradas
# ----------------------------------------------------------------------
sb = st.sidebar
with sb:
    html(f'<div class="side-brand">{logo(30, NAVY)}<span>rumbo</span></div>')
    primer_nombre = usuario["nombre"].split()[0].capitalize()
    html(f'<div class="usuario"><div><small>Sesión iniciada</small><b>Hola, {primer_nombre}</b></div></div>')
    if st.button("Cerrar sesión", width="stretch"):
        st.session_state.pop("usuario", None)
        st.rerun()
    st.caption("Ingresa tus datos. Todo se recalcula al instante.")

    html('<div class="side-title">Tu perfil</div>')
    ingreso = dinero(st, "Ingreso mensual (COP)", 0, value=3_500_000, step=100_000)
    gastos = dinero(st, "Gastos fijos mensuales (COP)", 0, value=1_200_000, step=50_000,
                             help="Comida, transporte, servicios, etc. Sin vivienda ni créditos.")
    c1, c2 = st.columns(2)
    tio = c1.number_input("TIO (% EA)", 0.0, 60.0, 10.0, 0.5,
                          help="Tasa de oportunidad: lo que ganarías invirtiendo tu dinero en otra parte.")
    inc_ingreso = c2.number_input("Aumento anual (%)", 0.0, 20.0, 4.0, 0.5,
                                  help="Cuánto crecen tu ingreso y tus gastos cada año.")
    horizonte = st.slider("Horizonte de evaluación (años)", 5, 30, 10)

    html('<div class="side-title">Crédito · compara opciones</div>')
    defaults = [
        ("Banco A", 10_000_000, 24.0, 36, 15_000, 0),
        ("Banco B", 10_000_000, 27.0, 60, 20_000, 300_000),
        ("Cooperativa", 10_000_000, 21.0, 48, 10_000, 0),
    ]
    creditos = []
    for i, (n, m, t, p, s, com) in enumerate(defaults):
        with st.expander(f"Opción {i + 1} · {n}", expanded=(i == 0)):
            nombre = st.text_input("Entidad", n, key=f"n{i}")
            monto = dinero(st, "Monto (COP)", 0, value=m, step=500_000, key=f"m{i}")
            a, b = st.columns(2)
            tasa = a.number_input("Tasa (% EA)", 0.0, 60.0, t, 0.5, key=f"t{i}")
            plazo = b.number_input("Plazo (meses)", 1, 120, p, 6, key=f"p{i}")
            a, b = st.columns(2)
            seguro = dinero(a, "Seguro / mes", 0, value=s, step=5_000, key=f"s{i}")
            comision = dinero(b, "Comisión inicial", 0, value=com, step=50_000, key=f"c{i}")
            creditos.append({"nombre": nombre, "monto": monto, "tasa_ea": tasa / 100,
                             "plazo_meses": int(plazo), "seguro_mensual": seguro,
                             "comision_inicial": comision})

    html('<div class="side-title">Vivienda</div>')
    valor = dinero(st, "Valor de la vivienda (COP)", 0, value=180_000_000, step=5_000_000)
    arriendo = dinero(st, "Arriendo equivalente / mes (COP)", 0, value=1_100_000, step=50_000)
    pct_inicial = st.slider("Cuota inicial (%)", 10, 50, 30)
    a, b = st.columns(2)
    tasa_h = a.number_input("Tasa hipoteca (% EA)", 0.0, 30.0, 13.0, 0.25)
    plazo_h = b.number_input("Plazo (años)", 5, 30, 20, 1)
    with st.expander("Supuestos de vivienda"):
        a, b = st.columns(2)
        inc_arriendo = a.number_input("Alza arriendo (%/año)", 0.0, 20.0, 6.0, 0.5)
        valorizacion = b.number_input("Valorización (%/año)", -5.0, 20.0, 5.0, 0.5)
        a, b = st.columns(2)
        escritura = a.number_input("Gastos escritura (%)", 0.0, 10.0, 2.0, 0.5)
        costos = b.number_input("Predial y mant. (%/año)", 0.0, 5.0, 1.0, 0.25)

    html('<div class="side-title">Retiro</div>')
    a, b = st.columns(2)
    rentab = a.number_input("Rentabilidad (% EA)", 0.0, 30.0, 8.0, 0.5)
    anios_ret = b.number_input("Años al retiro", 5, 50, 35, 1)
    meta = dinero(st, "Meta para el retiro (COP)", 0, value=3_000_000_000, step=100_000_000)
    usar_ahorros = st.toggle("Sumar mis ahorros actuales al retiro", value=True,
                             help="Lo que ya tienes registrado en «Mis ahorros» sigue creciendo hasta tu retiro.")


perfil = {"ingreso": ingreso, "gastos": gastos, "tio_ea": tio / 100,
          "horizonte_anios": horizonte, "inc_ingreso": inc_ingreso / 100}
vivienda = {"valor": valor, "pct_inicial": pct_inicial / 100, "tasa_hipoteca_ea": tasa_h / 100,
            "plazo_anios": int(plazo_h), "pct_escritura": escritura / 100, "pct_costos": costos / 100,
            "arriendo": arriendo, "inc_arriendo": inc_arriendo / 100, "valorizacion": valorizacion / 100}
retiro = {"rentabilidad_ea": rentab / 100, "anios": int(anios_ret), "meta": meta}

if ingreso <= 0:
    st.warning("Ingresa un ingreso mensual mayor a cero para empezar.")
    st.stop()

r = simular(perfil, creditos, vivienda, retiro)
mejor, viv, ret = r["mejor"], r["vivienda"], r["retiro"]

# Mis ahorros: se cargan una vez y, si la persona quiere, son el punto de partida del retiro
try:
    mis_ahorros = ah.listar(almacen, usuario["cedula"])
except Exception as e:
    mis_ahorros = []
    st.toast(f"No se pudieron leer tus ahorros ({type(e).__name__}).")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


total_ahorrado = sum(_f(a["monto"]) for a in mis_ahorros)
aporte_ahorros_retiro = 0.0
if usar_ahorros and total_ahorrado > 0:
    i_ret = ea_a_mensual(retiro["rentabilidad_ea"])
    ret["serie"] = [s + total_ahorrado * (1 + i_ret) ** t for t, s in enumerate(ret["serie"])]
    aporte_ahorros_retiro = total_ahorrado * (1 + i_ret) ** (len(ret["serie"]) - 1)
    ret["valor_futuro"] += aporte_ahorros_retiro
    ret["cumple"] = ret["valor_futuro"] >= ret["meta"]
    ret["avance"] = ret["valor_futuro"] / ret["meta"] if ret["meta"] else 0
    if ret["cumple"]:
        r["alertas"] = [a for a in r["alertas"] if "meta de retiro" not in a[1]] or \
            [("ok", "Tus tres decisiones son coherentes entre sí. Vas por buen rumbo.")]


# ----------------------------------------------------------------------
# Encabezado
# ----------------------------------------------------------------------
html(f"""
<div class="hero">
<div class="hero-left">{logo(62, CREAM)}
<div><div class="hero-word">rumbo</div><div class="hero-sub">Simulador de vida financiera</div></div>
</div>
<div class="hero-right">Evalúa con <b>VPN</b> y <b>TIR</b> qué crédito tomar, si arrendar o comprar
y cuánto ahorrar para tu retiro, y mira cómo <b>cada decisión mueve a las demás</b>.</div>
</div>
""")


# ----------------------------------------------------------------------
# KPIs
# ----------------------------------------------------------------------
def kpi(col, label, valor_txt, sub, color):
    with col:
        html(f'<div class="kpi"><div class="kpi-label"><span class="dot" style="background:{color}"></span>'
             f'{label}</div><div class="kpi-value">{valor_txt}</div><div class="kpi-sub">{sub}</div></div>')


endeu = r["endeudamiento"]
color_endeu = GREEN if endeu <= 0.30 else (AMBER if endeu <= 0.40 else RED)
k1, k2, k3, k4 = st.columns(4)
if mejor:
    kpi(k1, "Mejor crédito", mejor["nombre"], f"Costo real {pct(mejor['costo_real_ea'])} EA", AMBER)
else:
    kpi(k1, "Mejor crédito", "Sin crédito", "No ingresaste opciones", MUTED)
kpi(k2, "Vivienda", viv["decision"], f"VPN {millones(viv['vpn'])} frente a la otra opción", NAVY)
kpi(k3, "Ahorro disponible hoy", cop(r["ahorro_hoy"]), "por mes, después de crédito y vivienda",
    GREEN if r["ahorro_hoy"] > 0 else RED)
kpi(k4, "Endeudamiento", pct(endeu, 0), "de tu ingreso va a cuotas", color_endeu)

# Guardar simulación
g1, g2 = st.columns([3, 1], vertical_alignment="center")
with g1:
    if error_almacen:
        st.caption(f"⚠ {error_almacen}")
    elif not almacen.persistente:
        st.caption("Modo de prueba: las simulaciones guardadas se borran al reiniciar la app.")
with g2:
    if st.button("Guardar esta simulación", type="primary", width="stretch"):
        try:
            almacen.guardar_simulacion(fila_simulacion(usuario, perfil, r))
            st.toast("Simulación guardada en tu historial.")
        except Exception as e:
            st.error(f"No se pudo guardar ({type(e).__name__}). Inténtalo de nuevo.")


# ----------------------------------------------------------------------
# Pestañas
# ----------------------------------------------------------------------
t_imp, t_cred, t_viv, t_ret, t_aho, t_mcred, t_inv, t_hist, t_como = st.tabs(
    ["Impacto conectado", "Crédito", "Vivienda", "Retiro", "Mis ahorros", "Mis créditos",
     "Mis inversiones", "Mis simulaciones", "Cómo funciona"])

# ---------------- Impacto conectado ----------------
with t_imp:
    izq, der = st.columns([1.35, 1], gap="large")
    with izq:
        with st.container(border=True):
            etiquetas = ["Ingreso", "Gastos fijos", "Cuota crédito", "Vivienda", "Ahorro"]
            valores = [r["ingreso"], -r["gastos"], -r["cuota_credito"], -r["gasto_vivienda"], 0]
            fig = go.Figure(go.Waterfall(
                x=etiquetas, y=valores,
                measure=["relative", "relative", "relative", "relative", "total"],
                text=[millones(abs(v)) if v else millones(r["ahorro_hoy"]) for v in valores],
                textposition="outside", textfont=dict(color=NAVY, size=12),
                connector=dict(line=dict(color=LINE, width=1.5)),
                increasing=dict(marker=dict(color=NAVY)),
                decreasing=dict(marker=dict(color=AMBER)),
                totals=dict(marker=dict(color=GREEN if r["ahorro_hoy"] > 0 else RED)),
                hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
            ))
            estilo(fig, 360, "¿A dónde se va tu ingreso este mes?")
            fig.update_yaxes(showticklabels=False)
            st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

        with st.container(border=True):
            anios = len(r["ahorros"]) // 12
            prom = [sum(r["ahorros"][a * 12:(a + 1) * 12]) / 12 for a in range(anios)]
            fig = go.Figure(go.Bar(
                x=list(range(1, anios + 1)), y=[v / 1e6 for v in prom],
                marker=dict(color=[GREEN if v > 0 else RED for v in prom], cornerradius=4),
                hovertemplate="Año %{x}: $%{y:,.2f} M / mes<extra></extra>",
            ))
            if mejor:
                fig.add_vline(x=mejor["plazo"] / 12 + 0.5, line=dict(color=AMBER, dash="dot", width=2))
                fig.add_annotation(x=mejor["plazo"] / 12 + 0.5, y=max(prom) / 1e6 if prom else 0, text="Terminas el crédito",
                                   showarrow=False, xanchor="left", font=dict(color=SLATE, size=11), xshift=6)
            if viv["decision"] == "Comprar" and vivienda["plazo_anios"] < anios:
                fig.add_vline(x=vivienda["plazo_anios"] + 0.5, line=dict(color=NAVY, dash="dot", width=2))
                fig.add_annotation(x=vivienda["plazo_anios"] + 0.5, y=max(prom) / 1e6 * 0.85 if prom else 0,
                                   text="Terminas la hipoteca", showarrow=False, xanchor="left",
                                   font=dict(color=SLATE, size=11), xshift=6)
            estilo(fig, 300, "Tu ahorro mensual año a año")
            fig.update_xaxes(title=dict(text="Año", font=dict(color=MUTED, size=11)))
            st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

    with der:
        with st.container(border=True):
            html('<div class="h-sec">La cadena de tus decisiones</div>')
            html('<div class="p-sec">Lo que pagas en crédito y vivienda es lo que dejas de ahorrar para tu retiro.</div>')
            html(f"""
            <div class="cadena">
            <div class="eslabon"><small>Crédito</small><b>{cop(r['cuota_credito'])}</b></div>
            <div class="flecha">→</div>
            <div class="eslabon"><small>Vivienda</small><b>{cop(r['gasto_vivienda'])}</b></div>
            <div class="flecha">→</div>
            <div class="eslabon"><small>Retiro</small><b>{millones(ret['valor_futuro'])}</b></div>
            </div>
            """)
            if r["costo_cuota_baja"] > 0:
                html(f"""
                <div class="destacado"><small>El costo de elegir por la cuota</small>
                <b>{millones(r['costo_cuota_baja'])}</b>
                <span>es lo que tendrías de menos en tu retiro si eliges {r['menor_cuota']['nombre']}
                (la cuota más baja) en vez de {mejor['nombre']} (el crédito más barato).</span></div>
                """)

        with st.container(border=True):
            html('<div class="h-sec">Alertas</div>')
            for tono, texto in r["alertas"]:
                html(f'<div class="alerta {tono}"><span class="dot"></span><div>{texto}</div></div>')

# ---------------- Crédito ----------------
with t_cred:
    if not r["creditos"]:
        st.info("Ingresa al menos una opción de crédito en la barra lateral.")
    else:
        html('<div class="h-sec">¿Qué crédito tomar?</div>')
        html('<div class="p-sec">La cuota más baja casi nunca es la más barata. Comparamos el <b>costo real</b>: '
             'la TIR del crédito incluyendo seguros y comisiones, convertida a tasa efectiva anual.</div>')
        nombres = [c["nombre"] for c in r["creditos"]]
        colores = [AMBER if c["nombre"] == mejor["nombre"] else NAVY_SOFT for c in r["creditos"]]
        a, b = st.columns(2, gap="large")
        with a:
            with st.container(border=True):
                fig = go.Figure(go.Bar(x=nombres, y=[c["cuota"] for c in r["creditos"]],
                                       marker=dict(color=colores, cornerradius=6),
                                       text=[cop(c["cuota"]) for c in r["creditos"]], textposition="outside",
                                       hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
                estilo(fig, 320, "Cuota mensual")
                fig.update_yaxes(showticklabels=False, showgrid=False)
                st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)
        with b:
            with st.container(border=True):
                fig = go.Figure(go.Bar(x=nombres, y=[c["costo_real_ea"] * 100 for c in r["creditos"]],
                                       marker=dict(color=colores, cornerradius=6),
                                       text=[pct(c["costo_real_ea"]) for c in r["creditos"]], textposition="outside",
                                       hovertemplate="%{x}: %{y:.2f}% EA<extra></extra>"))
                estilo(fig, 320, "Costo real (% EA)")
                fig.update_yaxes(showticklabels=False, showgrid=False)
                st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

        with st.container(border=True):
            st.dataframe(
                [{"Entidad": c["nombre"],
                  "Tasa ofrecida (EA)": pct(c["tasa_nominal_ea"]),
                  "Costo real (EA)": pct(c["costo_real_ea"]),
                  "Cuota mensual": cop(c["cuota"]),
                  "Plazo": f"{c['plazo']} meses",
                  "Total pagado": cop(c["total_pagado"]),
                  "Intereses y costos": cop(c["intereses_y_costos"]),
                  "VPN (a tu TIO)": cop(c["vpn"])} for c in r["creditos"]],
                width="stretch", hide_index=True)
            st.caption("VPN del crédito desde tu punto de vista: recibes el dinero hoy y pagas cuotas. "
                       "Entre más negativo, más valor pierdes frente a tu tasa de oportunidad.")

# ---------------- Vivienda ----------------
with t_viv:
    html('<div class="h-sec">¿Arrendar o comprar?</div>')
    clase = "si" if viv["decision"] == "Comprar" else "no"
    tir_txt = pct(viv["tir_ea"])
    html(f'<div class="veredicto {clase}">Recomendación: {viv["decision"]} · VPN {millones(viv["vpn"])} · '
         f'TIR {tir_txt} vs TIO {pct(tio / 100)}</div>')
    html('<div class="p-sec" style="margin-top:10px">Evaluamos el flujo diferencial (comprar − arrendar): la cuota '
         'inicial y los gastos son la inversión; lo que pagas de más o de menos cada mes, el flujo; y al final del '
         'horizonte recuperas el patrimonio (valor de la vivienda menos lo que debes). Si el VPN es positivo, '
         'comprar crea valor.</div>')
    a, b, c = st.columns(3)
    kpi(a, "Cuota inicial + escritura", cop(viv["cuota_inicial"] + valor * escritura / 100), "inversión en el mes 0", NAVY)
    kpi(b, "Comprar / mes", cop(viv["costo_mes_comprar"]), f"vs arrendar {cop(viv['costo_mes_arrendar'])}", AMBER)
    kpi(c, f"Patrimonio en {horizonte} años", millones(viv["patrimonio_final"]), "valor de la vivienda menos la deuda", GREEN)

    with st.container(border=True):
        idx = list(range(0, len(viv["acum_comprar"]), 12))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[i // 12 for i in idx], y=[viv["acum_arrendar"][i] / 1e6 for i in idx],
                                 name="Arrendar", mode="lines", line=dict(color=NAVY_SOFT, width=3),
                                 hovertemplate="Año %{x}: $%{y:,.1f} M<extra>Arrendar</extra>"))
        fig.add_trace(go.Scatter(x=[i // 12 for i in idx], y=[viv["acum_comprar"][i] / 1e6 for i in idx],
                                 name="Comprar", mode="lines", line=dict(color=NAVY, width=3),
                                 hovertemplate="Año %{x}: $%{y:,.1f} M<extra>Comprar</extra>"))
        fig.add_trace(go.Scatter(x=[horizonte], y=[viv["patrimonio_final"] / 1e6], name="Patrimonio al final",
                                 mode="markers", marker=dict(color=AMBER, size=14),
                                 hovertemplate="Patrimonio: $%{y:,.1f} M<extra></extra>"))
        estilo(fig, 380, "Dinero que sale de tu bolsillo (acumulado)")
        fig.update_xaxes(title=dict(text="Año", font=dict(color=MUTED, size=11)))
        st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)
        st.caption("Comprar suele costar más cada mes, pero al final te queda un activo (punto ámbar). "
                   "Arrendar no deja patrimonio.")

# ---------------- Retiro ----------------
with t_ret:
    html('<div class="h-sec">¿Cuánto ahorrar para el retiro?</div>')
    html('<div class="p-sec">Tu ahorro no es un número fijo: es lo que te queda cada mes después del crédito y la '
         'vivienda. Cuando terminas de pagarlos, tu capacidad de ahorro crece.</div>')
    a, b, c = st.columns(3)
    kpi(a, "Tendrías al retirarte", millones(ret["valor_futuro"]), f"en {int(anios_ret)} años", NAVY)
    kpi(b, "Tu meta", millones(ret["meta"]), "Cumples la meta" if ret["cumple"] else "Aún no la alcanzas",
        GREEN if ret["cumple"] else AMBER)
    kpi(c, "Aporte fijo necesario", cop(ret["aporte_necesario"]), "por mes para llegar exacto a la meta", AMBER)

    avance = min(ret["avance"], 1)
    html(f'<div class="p-sec" style="margin-top:16px;margin-bottom:0">Avance hacia la meta: <b>{pct(ret["avance"], 0)}</b></div>'
         f'<div class="progreso"><div style="width:{avance * 100:.1f}%;background:{GREEN if ret["cumple"] else AMBER}"></div></div>')

    with st.container(border=True):
        serie = ret["serie"][::12]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(len(serie))), y=[v / 1e6 for v in serie], name="Ahorro acumulado", mode="lines",
                                 line=dict(color=NAVY, width=3), fill="tozeroy",
                                 fillcolor="rgba(18,38,58,0.08)",
                                 hovertemplate="Año %{x}: $%{y:,.1f} M<extra></extra>"))
        fig.add_hline(y=ret["meta"] / 1e6, line=dict(color=AMBER, dash="dash", width=2),
                      annotation_text="Meta", annotation_position="top left",
                      annotation_font=dict(color=SLATE, size=11))
        estilo(fig, 380, "Así crece tu ahorro para el retiro")
        fig.update_xaxes(title=dict(text="Año", font=dict(color=MUTED, size=11)))
        st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

# ---------------- Mis ahorros ----------------
with t_aho:
    html('<div class="h-sec">¿Cuánto te rinden tus ahorros?</div>')
    html('<div class="p-sec">Registra dónde tienes tu dinero hoy. Rumbo calcula lo que de verdad te queda '
         'después de la retención en la fuente y si le estás ganando a la inflación. Lo que registres queda '
         'guardado en tu cuenta y, si activas la opción en la barra lateral, se suma a tu plan de retiro.</div>')

    izq, der = st.columns([1, 1.15], gap="large")
    with izq:
        with st.container(border=True):
            html('<div class="h-sec" style="font-size:16px">Agregar un ahorro</div>')
            tipo = st.selectbox("Tipo de producto", list(ah.TIPOS.keys()), key="aho_tipo")
            entidad = st.text_input("Entidad", placeholder="Ej.: Bancolombia, Nu, Comfama…", key="aho_ent")
            monto_a = dinero(st, "Monto ahorrado (COP)", 0, value=5_000_000, step=500_000, key="aho_monto")
            a, b = st.columns(2)
            tasa_a = a.number_input("Tasa (% EA)", 0.0, 50.0, 10.0 if tipo == "CDT" else 6.0, 0.25,
                                    key=f"aho_tasa_{tipo}")
            meses_a = b.number_input("Plazo (meses)", 1, 120, 12, 1, key="aho_meses",
                                     help="Para cuentas de ahorro o fondos sin plazo, usa el tiempo que lo piensas dejar.")
            a, b = st.columns(2)
            ret_a = a.number_input("Retención (%)", 0.0, 30.0, ah.TIPOS[tipo], 0.5, key=f"aho_ret_{tipo}",
                                   help="Valor de referencia. Verifica la tarifa vigente con tu entidad.")
            infl = b.number_input("Inflación esperada (%)", 0.0, 30.0, 5.0, 0.25, key="aho_infl",
                                  help="Supuesto para calcular la rentabilidad real. Ajústalo al dato que prefieras.")

            calc = ah.calcular(monto_a, tasa_a / 100, meses_a, ret_a / 100, infl / 100)
            gana = calc["tasa_real"] >= 0
            html(f"""
            <div class="cadena" style="margin-top:10px">
            <div class="eslabon"><small>Te queda</small><b>{cop(calc['valor_final'])}</b></div>
            <div class="eslabon"><small>Rendimiento neto</small><b>{cop(calc['rend_neto'])}</b></div>
            </div>
            <div class="cadena">
            <div class="eslabon"><small>Retención</small><b>{cop(calc['retencion'])}</b></div>
            <div class="eslabon"><small>Tasa neta</small><b>{pct(calc['tasa_neta_ea'])} EA</b></div>
            </div>
            <div class="alerta {'ok' if gana else 'bad'}" style="margin-top:6px"><span class="dot"></span>
            <div>Rentabilidad real: <b>{pct(calc['tasa_real'])}</b>.
            {'Le ganas a la inflación: tu dinero crece de verdad.' if gana else
             'No le ganas a la inflación: aunque el saldo suba, tu dinero compra menos.'}</div></div>
            """)
            if st.button("Guardar en mis ahorros", type="primary", width="stretch", disabled=monto_a <= 0):
                try:
                    ah.guardar(almacen, usuario, {"tipo": tipo, "entidad": entidad, "monto": monto_a,
                                                  "tasa_ea": tasa_a / 100, "meses": meses_a,
                                                  "retencion": ret_a / 100}, calc)
                    st.toast("Ahorro guardado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo guardar ({type(e).__name__}). Inténtalo de nuevo.")

    with der:
        if not mis_ahorros:
            st.info("Todavía no has registrado ahorros. Agrega el primero con el formulario.")
        else:
            rend_total = sum(_f(x["rendimiento_neto"]) for x in mis_ahorros)
            tasa_prom = (sum(_f(x["tasa_neta_ea"]) * _f(x["monto"]) for x in mis_ahorros) / total_ahorrado
                         if total_ahorrado else 0)
            a, b = st.columns(2)
            kpi(a, "Total ahorrado", cop(total_ahorrado), f"en {len(mis_ahorros)} producto(s)", NAVY)
            kpi(b, "Tasa neta promedio", f"{pct(tasa_prom)} EA", f"rendimiento neto {cop(rend_total)}", AMBER)

            with st.container(border=True):
                nombres_a = [f"{x['tipo'].split(' (')[0]} · {x['entidad']}" for x in mis_ahorros]
                tasas_a = [_f(x["tasa_neta_ea"]) * 100 for x in mis_ahorros]
                fig = go.Figure(go.Bar(
                    x=tasas_a, y=nombres_a, orientation="h",
                    marker=dict(color=[GREEN if t >= infl else AMBER for t in tasas_a], cornerradius=6),
                    text=[f"{num(t, 1)}%" for t in tasas_a], textposition="outside",
                    hovertemplate="%{y}: %{x:.2f}% EA neta<extra></extra>"))
                fig.add_vline(x=infl, line=dict(color=RED, dash="dash", width=2))
                fig.add_annotation(x=infl, y=1, yref="paper", text="Inflación", showarrow=False,
                                   yanchor="bottom", font=dict(color=SLATE, size=11))
                estilo(fig, 120 + 46 * len(mis_ahorros), "¿Cuál rinde más? (tasa neta EA)")
                fig.update_xaxes(showticklabels=False, showgrid=False,
                                 range=[0, max(tasas_a + [infl]) * 1.3])
                fig.update_yaxes(tickprefix="", ticksuffix="", tickformat="", autorange="reversed")
                st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

            with st.container(border=True):
                st.dataframe([{
                    "Producto": x["tipo"], "Entidad": x["entidad"], "Monto": cop(_f(x["monto"])),
                    "Tasa": f"{pct(_f(x['tasa_ea']))} EA", "Plazo": f"{x['plazo_meses']} meses",
                    "Te queda": cop(_f(x["valor_final"])), "Registrado": x["fecha"],
                } for x in mis_ahorros], width="stretch", hide_index=True)
                opciones = {f"{x['tipo']} · {x['entidad']} · {cop(_f(x['monto']))}": x["id"] for x in mis_ahorros}
                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                quitar = c1.selectbox("Eliminar un registro", list(opciones.keys()), key="aho_quitar")
                if c2.button("Eliminar", width="stretch"):
                    try:
                        ah.eliminar(almacen, usuario["cedula"], str(opciones[quitar]))
                        st.toast("Registro eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo eliminar ({type(e).__name__}).")
            if usar_ahorros:
                st.caption(f"Tus {cop(total_ahorrado)} se suman a tu retiro: con la rentabilidad del plan "
                           f"llegarían a {millones(aporte_ahorros_retiro)}.")

# ---------------- Mis créditos ----------------
with t_mcred:
    html('<div class="h-sec">Mis créditos</div>')
    html('<div class="p-sec">Registra un crédito que ya tengas y lleva el control: cuánto debes hoy, cuántos '
         'intereses has pagado y cuánto te ahorras con cada <b>abono a capital</b>. Las cuotas normales se '
         'asumen pagadas al día; aquí registras los abonos extra.</div>')
    try:
        mis_creditos = seg.leer(almacen, "creditos", usuario["cedula"])
        mis_abonos = seg.leer(almacen, "abonos", usuario["cedula"])
    except Exception as e:
        mis_creditos, mis_abonos = [], []
        st.error(f"No se pudieron leer tus créditos ({type(e).__name__}).")

    with st.expander("Registrar un crédito", expanded=not mis_creditos):
        with st.form("nuevo_credito", border=False):
            a, b = st.columns(2)
            cr_ent = a.text_input("Entidad", placeholder="Ej.: Banco de Bogotá")
            cr_monto = dinero(b, "Monto desembolsado (COP)", 0, value=10_000_000, step=500_000)
            a, b, c3 = st.columns(3)
            cr_tasa = a.number_input("Tasa (% EA)", 0.0, 60.0, 24.0, 0.25)
            cr_plazo = b.number_input("Plazo (meses)", 1, 360, 36, 1)
            cr_seg = dinero(c3, "Seguro / mes (COP)", 0, value=0, step=5_000)
            cr_fecha = st.date_input("Fecha del desembolso", value=date.today(), max_value=date.today(),
                                     format="DD/MM/YYYY")
            if st.form_submit_button("Guardar crédito", type="primary"):
                if cr_monto <= 0:
                    st.error("El monto debe ser mayor que cero.")
                else:
                    seg.agregar(almacen, "creditos", {
                        "fecha_registro": cuentas_ahora(), "cedula": usuario["cedula"],
                        "entidad": cr_ent.strip() or "Mi crédito", "monto": round(cr_monto),
                        "tasa_ea": round(cr_tasa / 100, 6), "plazo_meses": int(cr_plazo),
                        "fecha_desembolso": cr_fecha.isoformat(), "seguro_mensual": round(cr_seg)})
                    st.toast("Crédito guardado.")
                    st.rerun()

    if mis_creditos:
        etiquetas = {f"{x['entidad']} · {cop(seg.num(x['monto']))} · {x['fecha_desembolso']}": x for x in mis_creditos}
        elegido = etiquetas[st.selectbox("Crédito", list(etiquetas.keys()), key="sel_credito")]
        abonos_cred = [x for x in mis_abonos if str(x["credito_id"]) == str(elegido["id"])]
        an = seg.analizar_credito(elegido, abonos_cred)

        a, b, c3, d = st.columns(4)
        kpi(a, "Debes hoy", cop(an["saldo_hoy"]), f"de {cop(an['monto'])} prestados", RED if an["saldo_hoy"] else GREEN)
        kpi(b, "Cuota actual", cop(an["cuota_actual"]), f"{an['meses_restantes']} cuotas por pagar", NAVY)
        kpi(c3, "Intereses pagados", cop(an["intereses_pagados"]), f"en {an['cuotas_pagadas']} cuotas", AMBER)
        if an["abonos_total"] > 0:
            kpi(d, "Ahorro por abonos", cop(an["ahorro_intereses"]),
                f"{an['meses_ahorrados']} meses menos" if an["meses_ahorrados"] else "en intereses", GREEN)
        else:
            kpi(d, "Intereses totales", cop(an["intereses_base"]), "si no haces abonos", MUTED)

        izq, der = st.columns([1.35, 1], gap="large")
        with izq:
            with st.container(border=True):
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=[0] + [f["mes"] for f in an["base"]],
                                         y=[an["monto"] / 1e6] + [f["saldo"] / 1e6 for f in an["base"]],
                                         name="Sin abonos", mode="lines", line=dict(color=NAVY_SOFT, width=3),
                                         hovertemplate="Mes %{x}: $%{y:,.2f} M<extra>Sin abonos</extra>"))
                if an["abonos_total"] > 0:
                    fig.add_trace(go.Scatter(x=[0] + [f["mes"] for f in an["real"]],
                                             y=[an["monto"] / 1e6] + [f["saldo"] / 1e6 for f in an["real"]],
                                             name="Con tus abonos", mode="lines", line=dict(color=NAVY, width=3),
                                             hovertemplate="Mes %{x}: $%{y:,.2f} M<extra>Con abonos</extra>"))
                fig.add_vline(x=an["cuotas_pagadas"], line=dict(color=AMBER, dash="dot", width=2))
                fig.add_annotation(x=an["cuotas_pagadas"], y=1, yref="paper", text="Hoy", showarrow=False,
                                   xanchor="left", xshift=6, font=dict(color=SLATE, size=11))
                estilo(fig, 340, "Así baja tu deuda")
                fig.update_xaxes(title=dict(text="Mes", font=dict(color=MUTED, size=11)))
                st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

        with der:
            with st.container(border=True):
                html('<div class="h-sec" style="font-size:16px">¿Y si haces un abono?</div>')
                a, b = st.columns(2)
                ab_valor = dinero(a, "Valor del abono", 0, value=1_000_000, step=100_000, key="ab_valor")
                ab_fecha = b.date_input("Fecha", value=date.today(), min_value=an["inicio"],
                                        format="DD/MM/YYYY", key="ab_fecha")
                ab_mod = st.radio("Quiero…", seg.MODALIDADES, horizontal=True, key="ab_mod")
                if ab_valor > 0 and an["saldo_hoy"] > 0:
                    sim = seg.simular_abono(elegido, abonos_cred, ab_valor, ab_mod, ab_fecha)
                    detalle = (f"terminas <b>{sim['meses_menos']} meses antes</b>" if ab_mod == "Reducir plazo"
                               else f"tu cuota baja a <b>{cop(sim['cuota_nueva'])}</b>")
                    html(f'<div class="alerta ok"><span class="dot"></span><div>Te ahorras '
                         f'<b>{cop(sim["ahorro_intereses"])}</b> en intereses y {detalle}.</div></div>')
                    tasa_cr, tio_ea = an["tasa"], tio / 100
                    if tasa_cr > tio_ea:
                        html(f'<div class="alerta ok"><span class="dot"></span><div>Abonar te "rinde" '
                             f'{pct(tasa_cr)} EA sin riesgo (lo que dejas de pagar), más que tu TIO de '
                             f'{pct(tio_ea)}. <b>Conviene abonar.</b></div></div>')
                    else:
                        html(f'<div class="alerta warn"><span class="dot"></span><div>Tu crédito cuesta '
                             f'{pct(tasa_cr)} EA, menos que tu TIO de {pct(tio_ea)}. Puede convenir más '
                             f'<b>invertir</b> ese dinero que abonarlo.</div></div>')
                if st.button("Guardar abono", type="primary", width="stretch",
                             disabled=ab_valor <= 0 or an["saldo_hoy"] <= 0):
                    seg.agregar(almacen, "abonos", {"credito_id": elegido["id"], "cedula": usuario["cedula"],
                                                    "fecha": ab_fecha.isoformat(), "valor": round(ab_valor),
                                                    "modalidad": ab_mod})
                    st.toast("Abono guardado.")
                    st.rerun()

        if abonos_cred:
            with st.container(border=True):
                html('<div class="h-sec" style="font-size:16px">Tus abonos</div>')
                st.dataframe([{"Fecha": x["fecha"], "Valor": cop(seg.num(x["valor"])), "Elegiste": x["modalidad"]}
                              for x in sorted(abonos_cred, key=lambda x: x["fecha"])],
                             width="stretch", hide_index=True)
                ops = {f"{x['fecha']} · {cop(seg.num(x['valor']))}": x["id"] for x in abonos_cred}
                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                q = c1.selectbox("Eliminar un abono", list(ops.keys()), key="del_abono")
                if c2.button("Eliminar abono", width="stretch"):
                    seg.borrar(almacen, "abonos", usuario["cedula"], "id", ops[q])
                    st.rerun()

        with st.expander("Ver tabla de amortización"):
            st.dataframe([{"Mes": f["mes"], "Estado": "Pagada" if f["mes"] <= an["cuotas_pagadas"] else "Pendiente",
                           "Cuota": cop(f["cuota"] + (an["seguro"] if f["cuota"] else 0)),
                           "Interés": cop(f["interes"]), "Capital": cop(f["capital"]),
                           "Abono": cop(f["abono"]) if f["abono"] else "", "Saldo": cop(f["saldo"])}
                          for f in an["real"]], width="stretch", hide_index=True, height=360)

        with st.expander("Eliminar este crédito"):
            confirma = st.checkbox("Sí, quiero borrar este crédito y todos sus abonos", key="conf_del_cred")
            if st.button("Eliminar crédito", disabled=not confirma):
                seg.borrar(almacen, "abonos", usuario["cedula"], "credito_id", elegido["id"])
                seg.borrar(almacen, "creditos", usuario["cedula"], "id", elegido["id"])
                st.toast("Crédito eliminado.")
                st.rerun()

# ---------------- Mis inversiones ----------------
with t_inv:
    html('<div class="h-sec">Mis inversiones</div>')
    html('<div class="p-sec">Registra cada vez que metes o sacas dinero de una inversión y, de vez en cuando, '
         'cuánto vale hoy. Rumbo calcula su <b>TIR real con las fechas exactas</b> y te dice si le está ganando '
         'a tu tasa de oportunidad.</div>')
    try:
        mis_inv = seg.leer(almacen, "inversiones", usuario["cedula"])
        mis_movs = seg.leer(almacen, "movimientos", usuario["cedula"])
    except Exception as e:
        mis_inv, mis_movs = [], []
        st.error(f"No se pudieron leer tus inversiones ({type(e).__name__}).")

    with st.expander("Registrar una inversión", expanded=not mis_inv):
        with st.form("nueva_inv", border=False):
            a, b = st.columns(2)
            in_nom = a.text_input("Nombre", placeholder="Ej.: Acciones Ecopetrol, Fondo Comfama…")
            in_tipo = b.selectbox("Tipo", ["Acciones", "Fondo de inversión", "CDT", "Finca raíz",
                                           "Negocio propio", "Criptomonedas", "Otro"])
            if st.form_submit_button("Guardar inversión", type="primary"):
                seg.agregar(almacen, "inversiones", {"fecha_registro": cuentas_ahora(), "cedula": usuario["cedula"],
                                                     "nombre": in_nom.strip() or "Mi inversión", "tipo": in_tipo})
                st.toast("Inversión guardada. Ahora registra tu primer aporte.")
                st.rerun()

    if mis_inv:
        etq = {f"{x['nombre']} · {x['tipo']}": x for x in mis_inv}
        inv = etq[st.selectbox("Inversión", list(etq.keys()), key="sel_inv")]
        movs = [m for m in mis_movs if str(m["inversion_id"]) == str(inv["id"])]
        ai = seg.analizar_inversion(movs)

        izq, der = st.columns([1, 1.35], gap="large")
        with izq:
            with st.container(border=True):
                html('<div class="h-sec" style="font-size:16px">Registrar un movimiento</div>')
                mv_tipo = st.radio("Tipo", seg.TIPOS_MOV, horizontal=True, key="mv_tipo",
                                   help="«Valor actual» es cuánto vale hoy tu inversión: míralo en la app de tu banco o broker.")
                a, b = st.columns(2)
                mv_valor = dinero(a, "Valor (COP)", 0, value=1_000_000, step=100_000, key="mv_valor")
                mv_fecha = b.date_input("Fecha", value=date.today(), max_value=date.today(),
                                        format="DD/MM/YYYY", key="mv_fecha")
                if st.button("Guardar movimiento", type="primary", width="stretch", disabled=mv_valor <= 0):
                    seg.agregar(almacen, "movimientos", {"inversion_id": inv["id"], "cedula": usuario["cedula"],
                                                         "fecha": mv_fecha.isoformat(), "tipo": mv_tipo,
                                                         "valor": round(mv_valor)})
                    st.toast("Movimiento guardado.")
                    st.rerun()

        with der:
            a, b = st.columns(2)
            kpi(a, "Has aportado", cop(ai["aportes"]), f"y retirado {cop(ai['retiros'])}", NAVY)
            if ai["fecha_valor"]:
                kpi(b, "Vale hoy", cop(ai["valor_actual"]), f"ganancia {cop(ai['ganancia'])}",
                    GREEN if ai["ganancia"] >= 0 else RED)
            else:
                kpi(b, "Vale hoy", "—", "registra el «Valor actual»", MUTED)
            if ai["tir"] is not None:
                tio_ea = tio / 100
                gana_tio = ai["tir"] >= tio_ea
                html(f'<div class="alerta {"ok" if gana_tio else "warn"}" style="margin-top:12px"><span class="dot"></span>'
                     f'<div>TIR de tu inversión: <b>{pct(ai["tir"])} EA</b> frente a tu TIO de {pct(tio_ea)}. '
                     f'{"Le está ganando a tu tasa de oportunidad." if gana_tio else "Está rindiendo menos que tu tasa de oportunidad."}'
                     f'</div></div>')
            elif movs:
                st.info("Para calcular la TIR registra un «Valor actual» (cuánto vale hoy) con fecha posterior a tu primer aporte.")

        if movs:
            with st.container(border=True):
                mov_ord = ai["movs"]
                neto, xs, ys = 0.0, [], []
                for m in mov_ord:
                    if m["tipo"] == "Aporte":
                        neto += seg.num(m["valor"])
                    elif m["tipo"] == "Retiro":
                        neto -= seg.num(m["valor"])
                    else:
                        continue
                    xs.append(m["fecha"]); ys.append(neto / 1e6)
                fig = go.Figure(go.Scatter(x=xs, y=ys, name="Dinero neto que has puesto", mode="lines+markers",
                                           line=dict(color=NAVY_SOFT, width=3, shape="hv"),
                                           hovertemplate="%{x}: $%{y:,.2f} M<extra></extra>"))
                vals = [m for m in mov_ord if m["tipo"] == "Valor actual"]
                if vals:
                    fig.add_trace(go.Scatter(x=[m["fecha"] for m in vals], y=[seg.num(m["valor"]) / 1e6 for m in vals],
                                             name="Lo que vale", mode="markers+lines",
                                             marker=dict(color=AMBER, size=12), line=dict(color=AMBER, dash="dot"),
                                             hovertemplate="%{x}: $%{y:,.2f} M<extra>Valor</extra>"))
                estilo(fig, 320, "Lo que has puesto vs. lo que vale")
                st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

                st.dataframe([{"Fecha": m["fecha"], "Tipo": m["tipo"], "Valor": cop(seg.num(m["valor"]))}
                              for m in reversed(mov_ord)], width="stretch", hide_index=True)
                ops = {f"{m['fecha']} · {m['tipo']} · {cop(seg.num(m['valor']))}": m["id"] for m in mov_ord}
                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                q = c1.selectbox("Eliminar un movimiento", list(ops.keys()), key="del_mov")
                if c2.button("Eliminar movimiento", width="stretch"):
                    seg.borrar(almacen, "movimientos", usuario["cedula"], "id", ops[q])
                    st.rerun()

        with st.expander("Eliminar esta inversión"):
            confirma_i = st.checkbox("Sí, quiero borrar esta inversión y todos sus movimientos", key="conf_del_inv")
            if st.button("Eliminar inversión", disabled=not confirma_i):
                seg.borrar(almacen, "movimientos", usuario["cedula"], "inversion_id", inv["id"])
                seg.borrar(almacen, "inversiones", usuario["cedula"], "id", inv["id"])
                st.toast("Inversión eliminada.")
                st.rerun()

# ---------------- Mis simulaciones ----------------
with t_hist:
    html(f'<div class="h-sec">Historial de {usuario["nombre"]}</div>')
    html('<div class="p-sec">Cada vez que tocas <b>Guardar esta simulación</b> queda un registro aquí. '
         'Así puedes comparar cómo cambian tus decisiones con el tiempo.</div>')
    try:
        historial = almacen.simulaciones_de(usuario["cedula"])
    except Exception as e:
        historial = []
        st.error(f"No se pudo leer tu historial ({type(e).__name__}).")

    if not historial:
        st.info("Aún no tienes simulaciones guardadas. Ajusta tus datos y toca «Guardar esta simulación».")
    else:
        def _n(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        a, b, c = st.columns(3)
        ultima = historial[-1]
        kpi(a, "Simulaciones guardadas", str(len(historial)), f"la última el {ultima['fecha']}", NAVY)
        kpi(b, "Último ahorro mensual", cop(_n(ultima["ahorro_mensual_hoy"]) or 0), "disponible después de cuotas", GREEN)
        kpi(c, "Último endeudamiento", pct(_n(ultima["endeudamiento"]), 0), "de tu ingreso en cuotas", AMBER)

        if len(historial) > 1:
            with st.container(border=True):
                fig = go.Figure(go.Scatter(
                    x=[h["fecha"] for h in historial],
                    y=[(_n(h["valor_futuro_retiro"]) or 0) / 1e6 for h in historial],
                    mode="lines+markers", line=dict(color=NAVY, width=3), marker=dict(color=AMBER, size=10),
                    hovertemplate="%{x}<br>$%{y:,.1f} M<extra></extra>"))
                estilo(fig, 300, "Tu retiro proyectado en cada simulación")
                fig.update_xaxes(type="category")
                st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA)

        with st.container(border=True):
            tabla = [{
                "Fecha": h["fecha"],
                "Ingreso": cop(_n(h["ingreso"]) or 0),
                "Mejor crédito": h["mejor_credito"],
                "Vivienda": h["decision_vivienda"],
                "Ahorro / mes": cop(_n(h["ahorro_mensual_hoy"]) or 0),
                "Endeudamiento": pct(_n(h["endeudamiento"]), 0),
                "Retiro proyectado": millones(_n(h["valor_futuro_retiro"]) or 0),
                "¿Cumple meta?": h["cumple_meta"],
            } for h in reversed(historial)]
            st.dataframe(tabla, width="stretch", hide_index=True)
            csv = "\n".join([";".join(tabla[0].keys())] + [";".join(map(str, f.values())) for f in tabla])
            st.download_button("Descargar mi historial (CSV)", csv.encode("utf-8-sig"),
                               file_name="rumbo_historial.csv", mime="text/csv")

# ---------------- Cómo funciona ----------------
with t_como:
    a, b = st.columns(2, gap="large")
    with a:
        with st.container(border=True):
            html('<div class="h-sec">Fórmulas</div>')
            st.markdown("**Conversión de tasas**")
            st.latex(r"i_{m} = (1 + i_{EA})^{1/12} - 1")
            st.markdown("**Cuota fija (sistema francés)**")
            st.latex(r"A = P \cdot \frac{i}{1-(1+i)^{-n}}")
            st.markdown("**Valor presente neto**")
            st.latex(r"VPN = \sum_{t=0}^{n} \frac{F_t}{(1+TIO)^{t}}")
            st.markdown("**Tasa interna de retorno**")
            st.latex(r"\sum_{t=0}^{n} \frac{F_t}{(1+TIR)^{t}} = 0")
            st.markdown("**La conexión**")
            st.latex(r"Ahorro_t = Ingreso_t - Gastos_t - Cuota^{cr\acute{e}dito}_t - Costo^{vivienda}_t")
    with b:
        with st.container(border=True):
            html('<div class="h-sec">Cómo decide Rumbo</div>')
            st.markdown(
                "- **Crédito:** calcula la TIR de cada opción (lo que recibes vs. lo que pagas, con seguros y "
                "comisiones) y elige la de **menor costo real**, no la de menor cuota.\n"
                "- **Vivienda:** evalúa el flujo diferencial comprar − arrendar a tu TIO. "
                "Si **VPN > 0** (o **TIR > TIO**), conviene comprar.\n"
                "- **Retiro:** acumula mes a mes lo que te queda después de crédito y vivienda, "
                "con la rentabilidad que indicas.\n"
                "- **Alertas:** endeudamiento sobre 30% y 40% del ingreso, ahorro negativo y meta no alcanzada.\n"
                "- **Mis créditos:** tabla de amortización (sistema francés) con abonos a capital; compara "
                "los intereses con y sin abonos, reduciendo el plazo o la cuota.\n"
                "- **Mis inversiones:** TIR con fechas exactas (equivalente a TIR.NO.PER en Excel) a partir "
                "de aportes, retiros y valor actual, comparada con tu TIO."
            )
            html('<div class="h-sec" style="margin-top:14px">Supuestos</div>')
            st.markdown(
                "- Valores nominales en pesos colombianos.\n"
                "- Cuota fija mensual; tasas en efectivo anual.\n"
                "- Ingreso, gastos y arriendo suben una vez al año.\n"
                "- Al final del horizonte de vivienda se valora el inmueble y se descuenta el saldo de la hipoteca."
            )

html('<div class="pie">Rumbo · Proyecto académico de Ingeniería Económica · Herramienta educativa, '
     'no constituye asesoría financiera.</div>')
