import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 1. Configuración Inicial
load_dotenv()
st.set_page_config(page_title="Simulador de Presupuesto", layout="wide")

# Inicializamos el historial
if 'historial_ajustes' not in st.session_state:
    st.session_state.historial_ajustes = []


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
            st.rerun()
    with col_b2:
        # Lógica de exportación final (Aplica todo el historial guardado)
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
    st.sidebar.header("🛠️ Configurar Nueva Metrica")

    # Usamos st.sidebar.selectbox sin llave fija para poder resetearlos si fuera necesario,
    # pero para el "reset" efectivo, Streamlit funciona mejor con el formulario o rerun.
    f_agency = st.sidebar.selectbox("Agencia", ["Todos"] + sorted(df_base['agency'].unique().tolist()), index=0)
    f_service = st.sidebar.selectbox("Servicio", ["Todos"] + sorted(df_base['service'].unique().tolist()), index=0)
    f_delegation = st.sidebar.selectbox("Delegación", ["Todos"] + sorted(df_base['delegation'].unique().tolist()),
                                        index=0)
    f_year = st.sidebar.selectbox("Año", ["Todos"] + sorted(df_base['year'].unique().tolist()), index=0)
    f_month = st.sidebar.selectbox("Mes", ["Todos"] + sorted(df_base['month'].unique().tolist()), index=0)

    st.sidebar.markdown("---")
    t_inc_inc = st.sidebar.selectbox("Tipo Income", ["Porcentaje", "Numérico"])
    v_inc_inc = st.sidebar.number_input("Valor Income", value=0.0, step=0.1)
    t_inc_pax = st.sidebar.selectbox("Tipo Pax", ["Porcentaje", "Numérico"])
    v_inc_pax = st.sidebar.number_input("Valor Pax", value=0.0, step=0.1)

    # --- PROCESAMIENTO EN TIEMPO REAL ---

    # 1. Calculamos el Estado Acumulado (Lo que ya está en el historial)
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

    # 2. Calculamos la Proyección (Acumulado + Lo que el usuario tiene en el Sidebar ahorita)
    df_proyectado = df_acumulado.copy()
    idx_actual = df_proyectado.index
    filtros_actuales = {"agency": f_agency, "service": f_service, "delegation": f_delegation, "year": f_year,
                        "month": f_month}
    for col, val in filtros_actuales.items():
        if val != "Todos": idx_actual = df_proyectado[df_proyectado[col] == val].index.intersection(idx_actual)

    # Aplicar incremento temporal para la vista previa
    if t_inc_inc == "Porcentaje":
        df_proyectado.loc[idx_actual, 'income'] *= (1 + v_inc_inc / 100)
    else:
        df_proyectado.loc[idx_actual, 'income'] += v_inc_inc

    if t_inc_pax == "Porcentaje":
        df_proyectado.loc[idx_actual, 'pax'] *= (1 + v_inc_pax / 100)
    else:
        df_proyectado.loc[idx_actual, 'pax'] += v_inc_pax

    # --- VISTA DE MÉTRICAS ---

    # A. MÉTRICAS TOTALES (Cómo afecta a toda la empresa)
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

    # B. MÉTRICAS DE SELECCIÓN ACTUAL (Lo que el usuario está filtrando ahora)
    st.subheader(f"🔍 Proyección de Selección Actual")
    s1, s2, s3, s4 = st.columns(4)
    # Valores Base de la selección
    base_inc_s = df_base.loc[idx_actual, 'income'].sum()
    base_pax_s = df_base.loc[idx_actual, 'pax'].sum()
    # Valores Proyectados de la selección
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
        st.rerun()  # Esto limpia los inputs porque al recargar vuelven a sus valores por defecto

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