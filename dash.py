# --- IMPORTS ---
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from collections import Counter  # <-- ESTA LÍNEA ES LA CLAVE
import chardet
import requests
import io

# --- CONFIGURACION DE PÁGINA ---
st.set_page_config(layout="wide")

@st.cache_data
def cargar_csv_desde_drive(file_id):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return pd.read_csv(io.StringIO(response.content.decode('utf-8')), dtype=str)
    else:
        st.error("❌ No se pudo descargar el archivo desde Google Drive.")
        return pd.DataFrame()

# --- CARGA DE DATOS DESDE GOOGLE DRIVE ---
file_id = "1XPdSPiSjf_FSZapgfRZxUNoZWlVmzs5Y"  # ID del archivo que me diste
df = cargar_csv_desde_drive(file_id)


# --- VERIFICACIÓN DE COLUMNAS CLAVE ---
columnas_necesarias = ['Technology', 'Departamento', 'Cell Activate State']
faltantes = [col for col in columnas_necesarias if col not in df.columns]
if faltantes:
    st.error(f"❌ Las siguientes columnas no se encuentran en el archivo: {', '.join(faltantes)}")
    st.stop()
st.title("📡 Huawei Base Station Visualization - Peru")

if df.empty:
    st.warning("⚠️ No se pudo cargar el archivo.")
    st.stop()

# --- LIMPIEZA ---
df.fillna({
    'Tiene instalado Massive MIMO': 'No', 'Technology': 'Desconocido', 'Departamento': 'Sin dato',
    'Tipo general': 'Sin clasificar', '5G Ready': 'Desconocido',
    'MIMO type': '', 'Banda Comercial': '',
    'Cell Activate State': 'INACTIVO', 'Distrito': 'Sin dato'
}, inplace=True)

# --- FILTROS MULTISELECCIÓN ---
st.subheader("🔍 Display filters")

col1, col2 = st.columns(2)  # Solo dos columnas ahora

with col1:
    tecnologias = st.multiselect(
        "Select technologies:",
        options=sorted(df['Technology'].unique()),
        default=sorted(df['Technology'].unique())
    )

with col2:
    departamentos = st.multiselect(
        "Select departments:",
        options=sorted(df['Departamento'].unique()) + ['All'],
        default='All'
    )

# Aplicar filtros (sin Cell Activate State)
if 'All' in departamentos:
    df_filtrado = df[df['Technology'].isin(tecnologias)]
else:
    df_filtrado = df[(df['Technology'].isin(tecnologias)) & (df['Departamento'].isin(departamentos))]

# Agrupar por site_id para conteo real
site_id_unicos = df_filtrado['site_id'].nunique()
st.markdown(f'<p style="font-size:18px">🔢 Total Base Stations: {site_id_unicos}</p>', unsafe_allow_html=True)
cantidad_celdas = df_filtrado.shape[0]
st.markdown(f'<p style="font-size:18px">🧩 Total Cells: {cantidad_celdas}</p>', unsafe_allow_html=True)

desactivadas = df_filtrado[df_filtrado['Cell Activate State'].str.strip().str.upper() == 'DEACTIVE']
estaciones_desactivadas = desactivadas['site_id'].nunique()
st.markdown(f'<p style="font-size:18px;">🚫 Base Stations Disabled: {estaciones_desactivadas}</p>', unsafe_allow_html=True)

# --- ESTACIONES ACTIVAS ---
df_filtrado['Activo'] = df_filtrado['Cell Activate State'].apply(lambda x: 'Activo' if 'ACTIVO' in x.upper() else 'Inactivo')

# --- GRAFICO BARRAS: ESTACIONES POR DEPARTAMENTO ---
st.subheader("📊 Base Stations by Department")
conteo_dep = df_filtrado.groupby(['Departamento', 'site_id']).size().reset_index(name='Quantity')
conteo_dep = conteo_dep.groupby('Departamento')['site_id'].count().reset_index(name='Quantity')
conteo_dep = conteo_dep[~conteo_dep['Departamento'].isin(['ND', 'Otros'])]  # excluir ND y Otros
conteo_dep = conteo_dep.sort_values(by='Quantity', ascending=False)

# 🔄 Renombrar columna solo para el gráfico
conteo_dep.rename(columns={'Departamento': 'Department'}, inplace=True)

fig_dep = px.bar(
    conteo_dep,
    x='Quantity', y='Department', orientation='h',
    color='Quantity', text='Quantity', title='Base Stations by Department',
    color_continuous_scale='Blues'
)
fig_dep.update_layout(
    yaxis=dict(tickmode='array', tickvals=conteo_dep['Department'], ticktext=conteo_dep['Department']),
    margin=dict(l=150, r=20, t=40, b=40)
)
st.plotly_chart(fig_dep, use_container_width=True)
st.caption(f"Total departments viewed: {len(conteo_dep)}")
st.caption("Legend - Stations by Technology Type:")
df_tec_legend = df_filtrado[['site_id', 'Technology']].drop_duplicates()
conteo_tec = df_tec_legend['Technology'].value_counts()

cols_tec = st.columns(2)
for i, (tec, cant) in enumerate(conteo_tec.items()):
    cols_tec[i % 2].markdown(f"- **{tec}**: {cant}")

# --- GRAFICO PIE MASSIVE MIMO ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📶 Massive MIMO installed")

    # ✅ Crear columna temporal para mostrar Yes/No sin alterar los datos
    df_mimo_plot = df_filtrado.copy()
    df_mimo_plot['MIMO Display'] = df_mimo_plot['Tiene instalado Massive MIMO'].apply(lambda x: 'Yes' if str(x).strip().upper() == 'SI' else 'No')

    # Conteo por tecnología solo para los que tienen 'Yes'
    tech_si = df_mimo_plot[df_mimo_plot['MIMO Display'] == 'Yes']
    tech_counts = tech_si['Technology'].value_counts().to_dict()

    # Generar lista personalizada por cada valor del gráfico
    customdata_mimo = []
    for val in df_mimo_plot['MIMO Display']:
        if val == 'Yes':
            detalle = "<br>".join([f"{tec}: {cnt}" for tec, cnt in tech_counts.items()])
        else:
            detalle = ""
        customdata_mimo.append([detalle])

    # Crear gráfico con columna modificada
    fig_mimo = px.pie(
        df_mimo_plot,
        names='MIMO Display',
        title='Massive MIMO Distribution',
        color_discrete_sequence=px.colors.qualitative.Set2
    )

    fig_mimo.update_traces(
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{customdata[0]}',
        customdata=customdata_mimo
    )

    st.plotly_chart(fig_mimo, use_container_width=True)

# --- GRAFICO PIE 5G READY (solo si se filtra 4G) ---
with col2:
    if '4G' in tecnologias:
        st.subheader("📶 5G Ready")

        # Crear columna temporal con Yes/No para visualización
        df_5g_plot = df_filtrado.copy()
        df_5g_plot['5G Display'] = df_5g_plot['5G Ready'].apply(lambda x: 'Yes' if str(x).strip().upper() == 'SI' else 'No')

        # Conteo por tecnología con 'Yes'
        tech_5g_si = df_5g_plot[df_5g_plot['5G Display'] == 'Yes']
        tech_5g_counts = tech_5g_si['Technology'].value_counts().to_dict()

        customdata_5g = []
        for val in df_5g_plot['5G Display']:
            if val == 'Yes':
                detalle = "<br>".join([f"{tec}: {cnt}" for tec, cnt in tech_5g_counts.items()])
            else:
                detalle = ""
            customdata_5g.append([detalle])

        fig_5g = px.pie(
            df_5g_plot,
            names='5G Display',
            title='5G Ready Distribution',
            color_discrete_sequence=px.colors.qualitative.Set1
        )

        fig_5g.update_traces(
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{customdata[0]}',
            customdata=customdata_5g
        )

        st.plotly_chart(fig_5g, use_container_width=True)

# --- GRAFICO PIE BEAMFORMING ---
st.subheader("📡 Distribution by support to Beamforming")

# Crear columna temporal con Yes/No para visualización
df_beam_plot = df_filtrado.copy()
df_beam_plot['Beam Display'] = df_beam_plot['Soporta Beamforming'].apply(lambda x: 'Yes' if str(x).strip().upper() == 'SI' else 'No')

# Conteo por tecnología con 'Yes'
tech_beam_si = df_beam_plot[df_beam_plot['Beam Display'] == 'Yes']
tech_beam_counts = tech_beam_si['Technology'].value_counts().to_dict()

customdata_beam = []
for val in df_beam_plot['Beam Display']:
    if val == 'Yes':
        detalle = "<br>".join([f"{tec}: {cnt}" for tec, cnt in tech_beam_counts.items()])
    else:
        detalle = ""
    customdata_beam.append([detalle])

fig_beam = px.pie(
    df_beam_plot,
    names='Beam Display',
    title='Beamforming Support',
    color_discrete_sequence=px.colors.qualitative.Set3
)

fig_beam.update_traces(
    textinfo='percent+label',
    hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{customdata[0]}',
    customdata=customdata_beam
)

st.plotly_chart(fig_beam, use_container_width=True)

# --- GRAFICO CIRCULAR FREQUENCY BAND ---
col3, col4 = st.columns(2)
with col3:
    st.markdown('<p style="font-size:20px;">📡 Frequency Band Distribution</p>', unsafe_allow_html=True)

    # Definir bandas de interés
    bandas_posibles = ['1', '2', '4', '7', '28', '30', '40', '42', 'n7', 'n40', 'n78']
    conteo_bandas = Counter()
    tecnologia_por_banda = {}

    # Recorremos filas y asignamos bandas a tecnologías
    for _, row in df_filtrado[['Frequency Band', 'Technology']].dropna().iterrows():
        bandas = [x.strip() for x in str(row['Frequency Band']).split(',') if x.strip() in bandas_posibles]
        for banda in bandas:
            conteo_bandas[banda] += 1
            tecnologia_por_banda.setdefault(banda, []).append(row['Technology'])

    # Armar DataFrame de bandas
    df_band_pie = pd.DataFrame.from_dict(conteo_bandas, orient='index', columns=['Cantidad']).reset_index()
    df_band_pie.columns = ['Frequency Band', 'Cantidad']

    # Armar customdata para hover con desglose por tecnología
    customdata_band = []
    for banda in df_band_pie['Frequency Band']:
        tecnologias = tecnologia_por_banda.get(banda, [])
        tec_count = pd.Series(tecnologias).value_counts()
        texto = "<br>".join([f"{tec}: {cnt}" for tec, cnt in tec_count.items()])
        customdata_band.append([texto])

    # Crear gráfico circular
    fig_band_pie = px.pie(
        df_band_pie,
        names='Frequency Band',
        values='Cantidad',
        title='Commercial Belt Distribution',
        color_discrete_sequence=px.colors.sequential.Plasma
    )

    fig_band_pie.update_traces(
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Cantidad: %{value}<br>%{customdata[0]}',
        customdata=customdata_band
    )

    # Mostrar gráfico en el dashboard
    st.plotly_chart(fig_band_pie, use_container_width=True)

# --- GRAFICO CIRCULAR TXRX ---
with col4:
    st.markdown('<p style="font-size:20px;">📶 TXRX Distribution - Types of MIMO</p>', unsafe_allow_html=True)

    # Definir valores TXRX válidos (tipos de MIMO)
    valores_txrx = ['1T1R', '2T2R', '2T4R', '4T4R', '8T8R', '32T32R', '64T64R']
    conteo_txrx = Counter()
    tecnologia_por_txrx = {}

    # Recorremos filas filtradas para contar ocurrencias por tipo de MIMO
    for _, row in df_filtrado[['TXRX', 'Technology']].dropna().iterrows():
        tipos = [x.strip() for x in str(row['TXRX']).split(',') if x.strip() in valores_txrx]
        for t in tipos:
            conteo_txrx[t] += 1
            tecnologia_por_txrx.setdefault(t, []).append(row['Technology'])

    # Crear DataFrame para el gráfico
    df_txrx_pie = pd.DataFrame.from_dict(conteo_txrx, orient='index', columns=['Cantidad']).reset_index()
    df_txrx_pie.columns = ['TXRX', 'Cantidad']

    # Crear hover personalizado con desglose por tecnología
    customdata_txrx = []
    for tipo in df_txrx_pie['TXRX']:
        tecnologias = tecnologia_por_txrx.get(tipo, [])
        tec_count = pd.Series(tecnologias).value_counts()
        texto = "<br>".join([f"{tec}: {cnt}" for tec, cnt in tec_count.items()])
        customdata_txrx.append([texto])

    # Crear gráfico circular
    fig_txrx_pie = px.pie(
        df_txrx_pie,
        names='TXRX',
        values='Cantidad',
        title='TXRX Type Distribution (MIMO)',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )

    fig_txrx_pie.update_traces(
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Cantidad: %{value}<br>%{customdata[0]}',
        customdata=customdata_txrx
    )

    # Mostrar el gráfico
    st.plotly_chart(fig_txrx_pie, use_container_width=True)

# --- TABLA FINAL ---
st.subheader("📋 Station Details by cells")
st.dataframe(df_filtrado[['site_id', 'Departamento', 'Provincia' , 'Distrito' ,'Technology', 'Tiene instalado Massive MIMO', '5G Ready', 'Frequency Band', 'Cell Activate State']], use_container_width=True)

st.info("Interactive visualization of base stations filtered by department and technology.")
