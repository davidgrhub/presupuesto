import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 1. Configuración Inicial
load_dotenv()
st.set_page_config(page_title="Simulador de Presupuesto", layout="wide")

# Inicializamos el historial y un contador de versión para resetear filtros
if 'historial_ajustes' not in st.session_state:
    st.session_state.historial_ajustes = []
if 'version_filtros' not in st.session_state:
    st.session_state.version_filtros = 0

def conectar_db():
    engine = create_engine(
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    return engine

try:
    engine = conectar_db()
    df_base = pd.read_sql("SELECT * FROM data", engine)

    # --- HEADER ---
    col_t, col_b1, col_b2 = st.columns([3, 1, 1])
    with col_t:
        st.title("🚀 Simulador de Presupuesto")
    with col_b1:
        if st.button("🗑️ Borrar Métricas", use_container_width=True):
            st.session_state.historial_ajustes = []
            st.session_state.version_filtros += 1 # Reset filtros al borrar
            st.rerun()
    with col_b2:
        df_export = df_base.copy()
        for aj in st.session_state.historial_ajustes:
            idx_e = df_export.index
            for c, v in aj['filtros'].items():
                if v != "Todos": idx_e = df_export[df_export[c] == v].index.intersection(idx_e)
            for col_n in ['income', 'pax']:
                if aj[f'tipo_{col_n}'] == "Porcentaje":
                    df_export.loc[idx_e, col_n] *= (1 + aj[f'val_{col_n}'] / 100)
                else:
                    df_export.loc[idx_e, col_n] += aj[f'val_{col_n}']
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar CSV", csv, "presupuesto_final.csv", "text/csv", use_container_width=True)

    # --- BARRA LATERAL (ENTRADA DE DATOS) ---
    # Usamos la versión en la KEY para forzar el reset
    v = st.session_state.version_filtros
    st.sidebar.header("🛠️ Configurar Nueva Metrica")

    f_agency = st.sidebar.selectbox("Agencia", ["Todos"] + sorted(df_base['agency'].unique().tolist()), key=f"agency_{v}")
    f_service = st.sidebar.selectbox("Servicio", ["Todos"] + sorted(df_base['service'].unique().tolist()), key=f"service_{v}")
    f_delegation = st.sidebar.selectbox("Delegación", ["Todos"] + sorted(df_base['delegation'].unique().tolist()), key=f"deleg_{v}")
    f_year = st.sidebar.selectbox("Año", ["Todos"] + sorted(df_base['year'].unique().tolist()), key=f"year_{v}")
    f_month = st.sidebar.selectbox("Mes", ["Todos"] + sorted(df_base['month'].unique().tolist()), key=f"month_{v}")

    st.sidebar.markdown("---")
    t_inc_inc = st.sidebar.selectbox("Tipo Income", ["Porcentaje", "Numérico"], key=f"t_inc_{v}")
    v_inc_inc = st.sidebar.number_input("Valor Income", value=0.0, step=0.1, key=f"v_inc_{v}")
    t_inc_pax = st.sidebar.selectbox("Tipo Pax", ["Porcentaje", "Numérico"], key=f"t_pax_{v}")
    v_inc_pax = st.sidebar.number_input("Valor Pax", value=0.0, step=0.1, key=f"v_pax_{v}")

    # --- PROCESAMIENTO ---
    df_acumulado = df_base.copy()
    for ajuste in st.session_state.historial_ajustes:
        idx_h = df_acumulado.index
        for col, val in ajuste['filtros'].items():
            if val != "Todos": idx_h = df_acumulado[df_acumulado[col] == val].index.intersection(idx_h)
        for c_n in ['income', 'pax']:
            if ajuste[f'tipo_{c_n}'] == "Porcentaje":
                df_acumulado.loc[idx_h, c_n] *= (1 + ajuste[f'val_{c_n}'] / 100)
            else:
                df_acumulado.loc[idx_h, c_n] += ajuste[f'val_{c_n}']

    df_proyectado = df_acumulado.copy()
    idx_actual = df_proyectado.index
    filtros_actuales = {"agency": f_agency, "service": f_service, "delegation": f_delegation, "year": f_year, "month": f_month}
    for col, val in filtros_actuales.items():
        if val != "Todos": idx_actual = df_proyectado[df_proyectado[col] == val].index.intersection(idx_actual)

    if t_inc_inc == "Porcentaje": df_proyectado.loc[idx_actual, 'income'] *= (1 + v_inc_inc / 100)
    else: df_proyectado.loc[idx_actual, 'income'] += v_inc_inc

    if t_inc_pax == "Porcentaje": df_proyectado.loc[idx_actual, 'pax'] *= (1 + v_inc_pax / 100)
    else: df_proyectado.loc[idx_actual, 'pax'] += v_inc_pax

    # --- VISTA DE MÉTRICAS ---
    st.subheader("📊 Impacto en Presupuesto Total")
    t1, t2, t3, t4 = st.columns(4)
    base_inc_t = df_base['income'].sum()
    base_pax_t = df_base['pax'].sum()
    proj_inc_t = df_proyectado['income'].sum()
    proj_pax_t = df_proyectado['pax'].sum()
    t1.metric("Income Base (Total)", f"{base_inc_t:,.2f}")
    t2.metric("Pax Base (Total)", f"{base_pax_t:,.2f}")
    t3.metric("Total Proyectado", f"{proj_inc_t:,.2f}", delta=f"{proj_inc_t - base_inc_t:,.2f}")
    t4.metric("Total Proyectado", f"{proj_pax_t:,.2f}", delta=f"{proj_pax_t - base_pax_t:,.2f}")

    st.subheader(f"🔍 Proyección de Selección Actual")
    s1, s2, s3, s4 = st.columns(4)
    base_inc_s = df_base.loc[idx_actual, 'income'].sum()
    base_pax_s = df_base.loc[idx_actual, 'pax'].sum()
    proj_inc_s = df_proyectado.loc[idx_actual, 'income'].sum()
    proj_pax_s = df_proyectado.loc[idx_actual, 'pax'].sum()
    s1.metric("Income Base (Filtro)", f"{base_inc_s:,.2f}")
    s2.metric("Pax Base (Filtro)", f"{base_pax_s:,.2f}")
    s3.metric("Income Proyectado", f"{proj_inc_s:,.2f}", delta=f"{proj_inc_s - base_inc_s:,.2f}")
    s4.metric("Pax Proyectado", f"{proj_pax_s:,.2f}", delta=f"{proj_pax_s - base_pax_s:,.2f}")

    # --- BOTÓN PARA GUARDAR ---
    st.sidebar.markdown("---")
    if st.sidebar.button("➕ AGREGAR MÉTRICA", use_container_width=True):
        nuevo = {
            "filtros": filtros_actuales,
            "tipo_income": t_inc_inc, "val_income": v_inc_inc,
            "tipo_pax": t_inc_pax, "val_pax": v_inc_pax
        }
        st.session_state.historial_ajustes.append(nuevo)
        st.session_state.version_filtros += 1  # AQUÍ ocurre la magia: cambiamos la clave de los filtros
        st.rerun()

    # --- HISTORIAL ---
    st.markdown("---")
    st.subheader("📜 Historial de Ajustes")
    for i, aj in enumerate(st.session_state.historial_ajustes):
        with st.expander(f"Ajuste #{i + 1}: {aj['tipo_income']} {aj['val_income']} | {aj['tipo_pax']} {aj['val_pax']}"):
            txt = ", ".join([f"{k}: {v}" for k, v in aj['filtros'].items() if v != "Todos"])
            st.write(f"**Filtros:** {txt if txt else 'Toda la tabla'}")
            if st.button("Eliminar", key=f"del_{i}"):
                st.session_state.historial_ajustes.pop(i)
                st.rerun()

except Exception as e:
    st.error(f"Error: {e}")