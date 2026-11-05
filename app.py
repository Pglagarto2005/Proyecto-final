
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re
import unicodedata

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================

st.set_page_config(
    page_title="Monitor IoT | Sistema de Riego",
    page_icon="🌱",
    layout="wide"
)

# Estilos visuales
st.markdown("""
<style>
    .main {
        background-color: #f7f9fc;
    }
    h1, h2, h3 {
        color: #174a35;
    }
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e5e9ed;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# CONFIGURACIÓN DE VARIABLES
# ==========================================

VARIABLES = {
    "humedad_suelo": {
        "nombre": "Humedad del suelo",
        "unidad": "%",
        "color": "#2196A6"
    },
    "nivel_agua": {
        "nombre": "Nivel de agua",
        "unidad": "%",
        "color": "#3976D2"
    },
    "humedad_raw": {
        "nombre": "Lectura ADC de humedad",
        "unidad": "ADC",
        "color": "#8E67B2"
    },
    "nivel_raw": {
        "nombre": "Lectura ADC de nivel",
        "unidad": "ADC",
        "color": "#D28B39"
    }
}

ALIAS = {
    "humedad_suelo": [
        "humedad_suelo", "humedad suelo",
        "soil_moisture", "moisture"
    ],
    "nivel_agua": [
        "nivel_agua", "nivel agua",
        "water_level", "nivel"
    ],
    "humedad_raw": ["humedad_raw", "moisture_raw"],
    "nivel_raw": ["nivel_raw", "water_level_raw"]
}


def normalizar(texto):
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return texto.strip("_")


# ==========================================
# PROCESAMIENTO DEL CSV DE GRAFANA
# ==========================================

def procesar_csv(archivo):

    df = pd.read_csv(archivo)
    df.columns = [normalizar(c) for c in df.columns]

    # Detectar formato largo de Grafana:
    # Time | metric | value
    if "value" in df.columns:
        metric_col = next(
            (c for c in ["metric", "field", "series", "name"]
             if c in df.columns),
            None
        )

        if metric_col:
            df[metric_col] = df[metric_col].astype(str).map(normalizar)

            for variable, aliases in ALIAS.items():
                df[metric_col] = df[metric_col].replace(
                    {normalizar(a): variable for a in aliases}
                )

            if df[metric_col].isin(VARIABLES).any():
                time_col = next(
                    (c for c in ["time", "timestamp", "datetime"]
                     if c in df.columns),
                    None
                )

                index_cols = [time_col] if time_col else []
                df = df.pivot_table(
                    index=index_cols,
                    columns=metric_col,
                    values="value",
                    aggfunc="mean"
                ).reset_index()

                df.columns.name = None

    # Renombrar variables reconocidas
    for variable, aliases in ALIAS.items():
        for col in df.columns:
            if col in [normalizar(a) for a in aliases]:
                df = df.rename(columns={col: variable})
                break

    # Detectar fecha y hora
    time_col = next(
        (c for c in ["time", "timestamp", "datetime", "fecha"]
         if c in df.columns),
        None
    )

    if time_col:
        df["fecha"] = pd.to_datetime(
            df[time_col],
            errors="coerce",
            utc=True
        ).dt.tz_convert(None)

    # Convertir datos a formato numérico
    for variable in VARIABLES:
        if variable in df.columns:
            df[variable] = pd.to_numeric(
                df[variable], errors="coerce"
            )

    # Eliminar filas completamente vacías en las variables
    columnas_disponibles = [
        c for c in VARIABLES if c in df.columns
    ]

    if columnas_disponibles:
        df = df.dropna(
            subset=columnas_disponibles,
            how="all"
        )

    if "fecha" in df.columns:
        df = df.dropna(subset=["fecha"])
        df = df.sort_values("fecha")

    return df


# ==========================================
# ENCABEZADO
# ==========================================

st.title("🌱 Monitor IoT | Sistema de Riego")

st.markdown("""
**Panel de análisis del sistema de monitoreo de humedad del suelo
y nivel de agua.**

Carga un archivo CSV exportado desde Grafana para consultar
el comportamiento histórico de los sensores y detectar anomalías.
""")

st.divider()


# ==========================================
# BARRA LATERAL
# ==========================================

st.sidebar.title("⚙️ Configuración")

st.sidebar.subheader("Umbrales del sistema")

humedad_min = st.sidebar.number_input(
    "Humedad mínima (%)",
    min_value=0.0,
    max_value=100.0,
    value=20.0,
    step=1.0
)

humedad_max = st.sidebar.number_input(
    "Humedad máxima (%)",
    min_value=0.0,
    max_value=100.0,
    value=100.0,
    step=1.0
)

nivel_min = st.sidebar.number_input(
    "Nivel mínimo de agua (%)",
    min_value=0.0,
    max_value=100.0,
    value=20.0,
    step=1.0,
    help="Umbral inicial configurable. Ajustarlo al nivel mínimo seguro del tanque."
)

st.sidebar.caption(
    "Los umbrales pueden modificarse según las condiciones "
    "reales de operación."
)

st.sidebar.divider()

st.sidebar.info(
    "Fuente de datos: CSV exportado desde Grafana."
)


# ==========================================
# CARGA DEL ARCHIVO
# ==========================================

archivo = st.file_uploader(
    "📂 Cargar archivo CSV de Grafana",
    type=["csv"]
)

if archivo is None:

    st.info(
        "Carga un archivo CSV para comenzar el análisis."
    )

    st.markdown("""
    ### Variables esperadas

    - `humedad_suelo`
    - `nivel_agua`
    - `humedad_raw`
    - `nivel_raw`

    También se aceptan archivos que tengan las variables
    distribuidas en formato largo (Time, metric, value).
    """)

    st.stop()


# ==========================================
# LECTURA Y VALIDACIÓN
# ==========================================

try:
    df = procesar_csv(archivo)

except Exception as e:
    st.error(f"No fue posible procesar el CSV: {e}")
    st.stop()

if df.empty:
    st.error("El archivo no contiene registros válidos.")
    st.stop()

disponibles = [
    c for c in VARIABLES if c in df.columns
]

if not disponibles:
    st.error(
        "No se encontraron variables reconocidas. "
        "Verifica los nombres de las columnas del CSV."
    )
    st.write("Columnas encontradas:", list(df.columns))
    st.stop()


# ==========================================
# RESUMEN GENERAL
# ==========================================

st.subheader("📊 Resumen de monitoreo")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Registros analizados",
    f"{len(df):,}"
)

if "fecha" in df.columns:
    col2.metric(
        "Última medición",
        df["fecha"].max().strftime("%d/%m/%Y %H:%M")
    )
else:
    col2.metric("Última medición", "No disponible")

col3.metric(
    "Variables detectadas",
    len(disponibles)
)

st.divider()


# ==========================================
# INDICADORES PRINCIPALES
# ==========================================

st.subheader("💧 Estado de los sensores")

col1, col2 = st.columns(2)

if "humedad_suelo" in df.columns:

    valor = df["humedad_suelo"].dropna()

    if not valor.empty:
        actual = valor.iloc[-1]

        if actual < humedad_min:
            estado = "🔴 Humedad crítica"
        elif actual >= humedad_max:
            estado = "🟢 Humedad máxima"
        else:
            estado = "🟡 Humedad normal"

        col1.metric(
            "Humedad del suelo",
            f"{actual:.1f} %",
            estado
        )

if "nivel_agua" in df.columns:

    valor = df["nivel_agua"].dropna()

    if not valor.empty:
        actual = valor.iloc[-1]

        if actual < nivel_min:
            estado = "🔴 Nivel bajo"
        else:
            estado = "🟢 Nivel adecuado"

        col2.metric(
            "Nivel de agua",
            f"{actual:.1f} %",
            estado
        )


# ==========================================
# EVOLUCIÓN TEMPORAL
# ==========================================

st.divider()
st.subheader("📈 Evolución de las variables")

variables_grafica = [
    v for v in ["humedad_suelo", "nivel_agua"]
    if v in disponibles
]

if variables_grafica:

    for variable in variables_grafica:

        datos = df.dropna(subset=[variable]).copy()

        eje_x = (
            "fecha" if "fecha" in datos.columns
            else datos.index
        )

        fig = px.line(
            datos,
            x=eje_x,
            y=variable,
            title=VARIABLES[variable]["nombre"],
            labels={
                variable: VARIABLES[variable]["unidad"],
                "fecha": "Fecha"
            }
        )

        fig.update_traces(
            line=dict(
                color=VARIABLES[variable]["color"],
                width=2
            )
        )

        if variable == "humedad_suelo":
            fig.add_hline(
                y=humedad_min,
                line_dash="dash",
                line_color="red",
                annotation_text="Umbral mínimo"
            )
            fig.add_hline(
                y=humedad_max,
                line_dash="dash",
                line_color="green",
                annotation_text="Humedad máxima"
            )

        if variable == "nivel_agua":
            fig.add_hline(
                y=nivel_min,
                line_dash="dash",
                line_color="red",
                annotation_text="Nivel mínimo"
            )

        fig.update_layout(
            height=350,
            template="plotly_white",
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)


# ==========================================
# ANÁLISIS ESTADÍSTICO
# ==========================================

st.divider()
st.subheader("📋 Análisis estadístico")

estadisticas = []

for variable in disponibles:

    serie = df[variable].dropna()

    if serie.empty:
        continue

    estadisticas.append({
        "Variable": VARIABLES[variable]["nombre"],
        "Unidad": VARIABLES[variable]["unidad"],
        "Promedio": round(serie.mean(), 2),
        "Mínimo": round(serie.min(), 2),
        "Máximo": round(serie.max(), 2),
        "Desviación estándar": round(serie.std(), 2),
        "Registros": len(serie)
    })

st.dataframe(
    pd.DataFrame(estadisticas),
    use_container_width=True,
    hide_index=True
)


# ==========================================
# SISTEMA DE ALERTAS
# ==========================================

st.divider()
st.subheader("🚨 Alertas operativas")

alertas = []

if "humedad_suelo" in disponibles:

    humedad = df["humedad_suelo"].dropna()

    if not humedad.empty:

        criticos = humedad[humedad < humedad_min].count()

        if criticos > 0:
            alertas.append({
                "Tipo": "Humedad baja",
                "Estado": "🔴 Crítico",
                "Detalle": f"{criticos} registros por debajo de {humedad_min}%."
            })

        maximos = humedad[humedad >= humedad_max].count()

        if maximos > 0:
            alertas.append({
                "Tipo": "Humedad máxima",
                "Estado": "🟢 Máximo alcanzado",
                "Detalle": f"{maximos} registros iguales o superiores a {humedad_max}%."
            })

if "nivel_agua" in disponibles:

    nivel = df["nivel_agua"].dropna()

    if not nivel.empty:

        bajos = nivel[nivel < nivel_min].count()

        if bajos > 0:
            alertas.append({
                "Tipo": "Nivel bajo del tanque",
                "Estado": "🔴 Crítico",
                "Detalle": f"{bajos} registros por debajo de {nivel_min}%."
            })

if alertas:

    for alerta in alertas:
        st.warning(
            f"**{alerta['Tipo']} — {alerta['Estado']}**\n\n"
            f"{alerta['Detalle']}"
        )

else:
    st.success(
        "No se detectaron registros fuera de los umbrales configurados."
    )


# ==========================================
# CORRELACIÓN ENTRE SENSORES
# ==========================================

st.divider()
st.subheader("🔗 Correlación entre sensores")

if (
    "humedad_suelo" in disponibles
    and "nivel_agua" in disponibles
):

    correlacion_df = df[
        ["humedad_suelo", "nivel_agua"]
    ].dropna()

    if len(correlacion_df) >= 2:

        correlacion = correlacion_df[
            "humedad_suelo"
        ].corr(
            correlacion_df["nivel_agua"]
        )

        st.metric(
            "Correlación de Pearson",
            f"{correlacion:.3f}"
        )

        if correlacion > 0.5:
            st.info(
                "Existe una asociación lineal positiva entre "
                "el nivel de agua y la humedad del suelo."
            )
        elif correlacion < -0.5:
            st.info(
                "Existe una asociación lineal negativa entre "
                "el nivel de agua y la humedad del suelo."
            )
        else:
            st.info(
                "La relación lineal entre ambas variables "
                "es débil o cercana a cero."
            )

        fig_corr = px.scatter(
            correlacion_df,
            x="nivel_agua",
            y="humedad_suelo",
            trendline="ols",
            labels={
                "nivel_agua": "Nivel de agua (%)",
                "humedad_suelo": "Humedad del suelo (%)"
            },
            title="Relación entre nivel de agua y humedad del suelo"
        )

        fig_corr.update_layout(
            template="plotly_white",
            height=400
        )

        st.plotly_chart(
            fig_corr,
            use_container_width=True
        )

        st.caption(
            "La correlación indica asociación estadística, "
            "no demuestra causalidad."
        )

    else:
        st.info("No hay suficientes registros para calcular correlación.")

else:
    st.info(
        "Se necesitan las dos variables principales "
        "para calcular la correlación."
    )


# ==========================================
# TABLA DE DATOS
# ==========================================

st.divider()
st.subheader("🗂️ Registros del sistema")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)


# ==========================================
# DESCARGA DE DATOS
# ==========================================

csv_procesado = df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="⬇️ Descargar datos procesados",
    data=csv_procesado,
    file_name="datos_sistema_riego.csv",
    mime="text/csv"
)

st.caption(
    "Monitor IoT | Análisis de datos del sistema de riego"
)

