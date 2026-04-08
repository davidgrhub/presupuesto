import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 1. Configuración Inicial
load_dotenv()
st.set_page_config(page_title="Simulador de Presupuesto", layout="wide")

# Inicialización de estados
if 'historial_ajustes' not in st.session_state:
    st.session_state.historial_ajustes = []
if 'version_filtros' not in st.session_state:
    st.session_state.version_filtros = 0


def conectar_db():
    return create_engine(
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")


def get_budget_year_logic(year, month):
    meses_map = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
        'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
    }
    m = meses_map.get(month, 1)
    y = int(float(year))
    return y + 1 if m >= 10 else y


@st.cache_data
def obtener_max_budget_year(_engine):
    df_y = pd.read_sql("SELECT DISTINCT year, month FROM data", _engine)
    df_y['by'] = df_y.apply(lambda x: get_budget_year_logic(x['year'], x['month']), axis=1)
    return int(df_y['by'].max())


@st.cache_data
def cargar_solo_budget_actual(_engine, target_by):
    query = f"""
    SELECT * FROM data 
    WHERE (year = {target_by - 1} AND month IN ('October', 'November', 'December'))
       OR (year = {target_by} AND month NOT IN ('October', 'November', 'December'))
    """
    return pd.read_sql(query, _engine)


@st.cache_data
def consultar_totales_historicos(_engine, target_by):
    query = f"""
    SELECT SUM(income) as total_inc, SUM(pax) as total_px FROM data 
    WHERE (year = {target_by - 1} AND month IN ('October', 'November', 'December'))
       OR (year = {target_by} AND month NOT IN ('October', 'November', 'December'))
    """
    res = pd.read_sql(query, _engine).iloc[0]
    return res['total_inc'], res['total_px']


try:
    engine = conectar_db()
    target_by = obtener_max_budget_year(engine)
    df_base = cargar_solo_budget_actual(engine, target_by)

    # --- HEADER ---
    st.title(f"🚀 Simulador de Presupuesto Fiscal {target_by}")

    # --- LÍNEA DIVISORIA ENTRE TÍTULO Y REFERENCIA ---
    st.markdown("---")

    # --- BLOQUE DE REFERENCIA HISTÓRICA ---
    st.subheader("📋 Referencia Budget Anterior")
    c_inf_select, c_spacer, c_inf_m1, c_inf_m2 = st.columns([2, 1, 1.5, 1.5])

    with c_inf_select:
        budget_ref = st.selectbox("🔎 Seleccionar Año:", range(target_by - 1, target_by - 5, -1), index=0)

    h_inc, h_pax = consultar_totales_historicos(engine, budget_ref)

    with c_inf_m1:
        st.metric(f"Income Total ({budget_ref})", f"{h_inc:,.2f}")
    with c_inf_m2:
        st.metric(f"Pax Total ({budget_ref})", f"{h_pax:,.2f}")

    st.markdown("---")

    # --- BARRA LATERAL (MULTISELECCIÓN Y DESCRIPCIÓN) ---
    v = st.session_state.version_filtros
    st.sidebar.header(f"🛠️ Configurar Budget {target_by}")

    # Campo de descripción personalizada
    desc_ajuste = st.sidebar.text_input("📝 Descripción del ajuste:", placeholder="Ej: Incremento Temporada Alta",
                                        key=f"desc_{v}")

    f_agency = st.sidebar.multiselect("Agencia", sorted(df_base['agency'].unique().tolist()), key=f"ag_{v}")
    f_service = st.sidebar.multiselect("Servicio", sorted(df_base['service'].unique().tolist()), key=f"ser_{v}")
    f_delegation = st.sidebar.multiselect("Delegación", sorted(df_base['delegation'].unique().tolist()), key=f"del_{v}")
    f_year = st.sidebar.multiselect("Año", sorted(df_base['year'].unique().tolist()), key=f"ye_{v}")
    f_month = st.sidebar.multiselect("Mes", sorted(df_base['month'].unique().tolist()), key=f"mo_{v}")

    st.sidebar.markdown("---")
    t_inc_inc = st.sidebar.selectbox("Tipo Income", ["Porcentaje", "Numérico"], key=f"ti_{v}")
    v_inc_inc = st.sidebar.number_input("Valor Income", value=0.0, step=0.1, key=f"vi_{v}")
    t_inc_pax = st.sidebar.selectbox("Tipo Pax", ["Porcentaje", "Numérico"], key=f"tp_{v}")
    v_inc_pax = st.sidebar.number_input("Valor Pax", value=0.0, step=0.1, key=f"vp_{v}")


    # --- PROCESAMIENTO ---
    # Lógica para aplicar filtros de multiselección
    def filtrar_dataframe(df, filtros):
        df_temp = df.copy()
        for col, values in filtros.items():
            if values:  # Si la lista no está vacía, aplicamos el filtro
                df_temp = df_temp[df_temp[col].isin(values)]
        return df_temp


    filtros_actuales = {
        "agency": f_agency,
        "service": f_service,
        "delegation": f_delegation,
        "year": f_year,
        "month": f_month
    }

    # Cálculo acumulado del historial
    df_acumulado = df_base.copy()
    for ajuste in st.session_state.historial_ajustes:
        df_target = filtrar_dataframe(df_acumulado, ajuste['filtros'])
        idx_h = df_target.index

        for c_n in ['income', 'pax']:
            tipo = ajuste[f'tipo_{c_n}']
            valor = ajuste[f'val_{c_n}']
            if tipo == "Porcentaje":
                df_acumulado.loc[idx_h, c_n] *= (1 + valor / 100)
            else:
                df_acumulado.loc[idx_h, c_n] += valor

    # Cálculo de la proyección actual
    df_proyectado = df_acumulado.copy()
    df_target_actual = filtrar_dataframe(df_proyectado, filtros_actuales)
    idx_actual = df_target_actual.index

    if t_inc_inc == "Porcentaje":
        df_proyectado.loc[idx_actual, 'income'] *= (1 + v_inc_inc / 100)
    else:
        df_proyectado.loc[idx_actual, 'income'] += v_inc_inc

    if t_inc_pax == "Porcentaje":
        df_proyectado.loc[idx_actual, 'pax'] *= (1 + v_inc_pax / 100)
    else:
        df_proyectado.loc[idx_actual, 'pax'] += v_inc_pax

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
        # Usamos la descripción o un nombre genérico si está vacío
        nombre_final = desc_ajuste if desc_ajuste.strip() != "" else f"Ajuste #{len(st.session_state.historial_ajustes) + 1}"

        st.session_state.historial_ajustes.append({
            "nombre": nombre_final,
            "filtros": filtros_actuales,
            "tipo_income": t_inc_inc, "val_income": v_inc_inc,
            "tipo_pax": t_inc_pax, "val_pax": v_inc_pax
        })
        st.session_state.version_filtros += 1
        st.rerun()

    # --- HISTORIAL REESTRUCTURADO ---
    st.markdown("---")

    # Usamos columnas para alinear Título y Botones a la misma altura
    col_hist_t, col_hist_b1, col_hist_b2 = st.columns([3, 1, 1], vertical_alignment="bottom")

    with col_hist_t:
        st.subheader("📜 Historial de Ajustes")

    with col_hist_b1:
        if st.button("🗑️ Borrar Métricas", use_container_width=True):
            st.session_state.historial_ajustes = []
            st.session_state.version_filtros += 1
            st.rerun()

    with col_hist_b2:
        # Lógica de Exportación (movida aquí)
        df_export = df_base.copy()
        for aj in st.session_state.historial_ajustes:
            df_target_exp = filtrar_dataframe(df_export, aj['filtros'])
            idx_e = df_target_exp.index
            for col_n in ['income', 'pax']:
                if aj[f'tipo_{col_n}'] == "Porcentaje":
                    df_export.loc[idx_e, col_n] *= (1 + aj[f'val_{col_n}'] / 100)
                else:
                    df_export.loc[idx_e, col_n] += aj[f'val_{col_n}']

        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(f"📥 Exportar Budget {target_by}", csv, f"budget_{target_by}.csv", "text/csv",
                           use_container_width=True)

    # Renderizado del historial
    if not st.session_state.historial_ajustes:
        st.info("No hay ajustes en el historial.")
    else:
        for i, aj in enumerate(st.session_state.historial_ajustes):
            # El título del expander ahora usa el nombre personalizado
            with st.expander(
                    f"📌 {aj['nombre']} | Inc: {aj['val_income']} ({aj['tipo_income']}) | Pax: {aj['val_pax']} ({aj['tipo_pax']})"):
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    # Formatear los filtros para mostrar qué se seleccionó
                    detalles = []
                    for k, v in aj['filtros'].items():
                        if v: detalles.append(f"**{k.capitalize()}**: {', '.join(map(str, v))}")

                    st.write(" | ".join(detalles) if detalles else "Aplicado a: Toda la tabla")

                with col_del:
                    if st.button("Eliminar", key=f"del_{i}", use_container_width=True):
                        st.session_state.historial_ajustes.pop(i)
                        st.rerun()

except Exception as e:
    st.error(f"Error: {e}")