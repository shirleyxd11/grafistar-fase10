from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    from streamlit_option_menu import option_menu
except Exception:  # fallback if optional package is not installed
    option_menu = None

from utils.db import (
    ensure_db_ready, importar_mayo_desde_excel, read_pedidos, read_historial, insert_pedido,
    update_pedido, mover_kanban, upsert_df_edits, delete_pedido, connect, EXCEL_INICIAL
)
from utils.excel_loader import cargar_pedidos_mayo, resumen_calidad
from utils.calculos import (
    ASIS, TOBE_MAYO, ESTANDAR, KANBAN_ESTADOS, MESES_2026, WIP_LIMITES,
    kpis, semaforo_cumplimiento, puntaje_prioridad, codigo_siguiente, nombre_mes, semana_mes,
    normalizar_estado_kanban, criticidad
)
from utils.exportador import exportar_excel
from utils.ui import load_css, sidebar_brand, hero, section_title, kpi_card, render_quality_panel, kanban_board, kanban_summary, styled_pedidos_table, action_cards

st.set_page_config(
    page_title="Grafistar | Sistema Digital Fase 10",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_db_ready()

MENU = ["Inicio", "Carga Inicial", "Registro OP", "Base Maestra", "Prioridad", "Programación", "Kanban", "Trazabilidad", "Dashboard", "Procedimiento"]
ICONOS = ["house", "cloud-upload", "plus-square", "table", "bar-chart", "calendar2-week", "kanban", "clock-history", "speedometer2", "book"]


def read_filtered_base():
    df = read_pedidos()
    if df.empty:
        return df
    # Limpieza de fechas para gráficos
    for col in ["fecha_recepcion", "fecha_prometida", "fecha_programada", "fecha_entrega_real"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def safe_options(series):
    vals = series.dropna().astype(str).unique().tolist() if series is not None else []
    return ["Todos"] + sorted([v for v in vals if v and v.lower() != "nan"])


def apply_filters(df: pd.DataFrame, key_prefix="flt") -> pd.DataFrame:
    if df.empty:
        return df
    with st.expander("Filtros rápidos", expanded=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            mes = st.selectbox("Mes", safe_options(df["mes"]), key=f"{key_prefix}_mes")
        with c2:
            semana = st.selectbox("Semana", safe_options(df["semana"]), key=f"{key_prefix}_sem")
        with c3:
            estado = st.selectbox("Estado Kanban", safe_options(df["estado_kanban"]), key=f"{key_prefix}_estado")
        with c4:
            prioridad = st.selectbox("Prioridad", safe_options(df["prioridad"]), key=f"{key_prefix}_prio")
        with c5:
            texto = st.text_input("Buscar OP / cliente", key=f"{key_prefix}_txt")
    out = df.copy()
    if mes != "Todos": out = out[out["mes"].astype(str) == mes]
    if semana != "Todos": out = out[out["semana"].astype(str) == semana]
    if estado != "Todos": out = out[out["estado_kanban"].astype(str) == estado]
    if prioridad != "Todos": out = out[out["prioridad"].astype(str) == prioridad]
    if texto:
        t = texto.lower().strip()
        out = out[out["codigo_op"].astype(str).str.lower().str.contains(t, na=False) | out["cliente"].astype(str).str.lower().str.contains(t, na=False)]
    return out


def page_inicio():
    hero()
    df = read_filtered_base()
    section_title("Panel ejecutivo", "Resumen automático del histórico de mayo y registros creados desde la web.")
    render_quality_panel(df)
    c1, c2 = st.columns([1.4, .9])
    with c1:
        section_title("Flujo operativo digital", "La app reemplaza la programación verbal por registro, trazabilidad y control visual.")
        action_cards()
    with c2:
        section_title("Auditoría rápida de datos", "Control de concordancia para sustentar que la base inicial no se alteró.")
        stats = kpis(df[df["mes"].astype(str).str.contains("Mayo", na=False)] if "mes" in df.columns else df)
        sem, nombre, accion = semaforo_cumplimiento(stats["cumplimiento"])
        st.markdown(f"""
        <div class='info-panel'>
          <h3>Base histórica Mayo 2026</h3>
          <p><b>Registros:</b> {stats['total']} pedidos</p>
          <p><b>Cumplidos:</b> {stats['cumplidos']} · <b>Retrasados:</b> {stats['retrasados']}</p>
          <p><b>Cumplimiento:</b> {stats['cumplimiento']:.2f}% · <b>Semáforo:</b> {nombre}</p>
          <p><b>Acción:</b> {accion}</p>
          <p>Desde junio hasta diciembre de 2026, los pedidos se registran directamente desde esta app y quedan guardados en SQLite.</p>
        </div>
        """, unsafe_allow_html=True)
    section_title("Vista Kanban resumida", "Muestra primero las OP activas o con alerta para no saturar el tablero con pedidos ya cerrados.")
    kanban_preview = df.copy()
    if not kanban_preview.empty:
        kanban_preview = kanban_preview[(~kanban_preview["estado_kanban"].astype(str).str.upper().eq("ENTREGADO")) | (~kanban_preview["resultado"].astype(str).str.lower().eq("a tiempo"))]
    kanban_board(kanban_preview if not kanban_preview.empty else df, max_cards=3, density="Compacto")


def page_carga_inicial():
    section_title("Carga inicial desde Excel", "Mayo 2026 se importa como base histórica To-Be. Los siguientes meses se registran desde la web.")
    st.info(f"Archivo base incluido: {EXCEL_INICIAL.name}")
    c1, c2, c3, c4 = st.columns(4)
    try:
        df_excel = cargar_pedidos_mayo(EXCEL_INICIAL)
        resumen = resumen_calidad(df_excel)
    except Exception as e:
        st.error(f"No se pudo leer el Excel inicial: {e}")
        return
    with c1: kpi_card("Registros detectados", resumen["registros"], "Desde Excel", "blue")
    with c2: kpi_card("Duplicados OP", resumen["duplicados"], "Debe ser 0", "green" if resumen["duplicados"] == 0 else "red")
    with c3: kpi_card("Cumplidos", resumen["cumplidos"], "Mayo", "green")
    with c4: kpi_card("Cumplimiento", f"{resumen['cumplimiento']:.2f}%", "Esperado 92.86%", "green")
    st.markdown("### Comparación de control")
    control = pd.DataFrame([
        {"Indicador": "Pedidos programados mayo", "Esperado": 126, "Leído desde Excel": resumen["registros"], "Estado": "OK" if resumen["registros"] == 126 else "Revisar"},
        {"Indicador": "Pedidos cumplidos mayo", "Esperado": 117, "Leído desde Excel": resumen["cumplidos"], "Estado": "OK" if resumen["cumplidos"] == 117 else "Revisar"},
        {"Indicador": "Pedidos retrasados mayo", "Esperado": 9, "Leído desde Excel": resumen["retrasados"], "Estado": "OK" if resumen["retrasados"] == 9 else "Revisar"},
        {"Indicador": "Cumplimiento To-Be", "Esperado": "92.86%", "Leído desde Excel": f"{resumen['cumplimiento']:.2f}%", "Estado": "OK" if abs(resumen["cumplimiento"] - 92.86) < .02 else "Revisar"},
    ])
    st.dataframe(control, use_container_width=True, hide_index=True)
    st.markdown("### Acciones de carga")
    c1, c2 = st.columns([.3, .7])
    with c1:
        if st.button("Recargar mayo desde Excel", type="primary"):
            try:
                importar_mayo_desde_excel(force=True)
                st.success("Base histórica reiniciada y cargada nuevamente desde Excel sin duplicados.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al recargar: {e}")
    with c2:
        st.warning("Usa esta opción solo si quieres restaurar la base al histórico de mayo. Los pedidos nuevos registrados desde la web se eliminarán al reiniciar.")
    with st.expander("Vista previa de los primeros 20 pedidos leídos del Excel", expanded=False):
        st.dataframe(df_excel.head(20), use_container_width=True, hide_index=True)


def page_registro_op():
    section_title("Registro de Orden de Pedido Digital", "Formulario web para crear pedidos de junio a diciembre 2026 sin volver a llenar Excel.")
    df = read_filtered_base()
    with st.form("registro_op_form", clear_on_submit=False):
        st.markdown("#### Datos del cliente y recepción")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            fecha_recepcion = st.date_input("Fecha recepción", value=date(2026, 6, 1), min_value=date(2026, 6, 1), max_value=date(2026, 12, 31))
        with c2:
            hora_recepcion = st.time_input("Hora recepción", value=time(9, 0))
        with c3:
            codigo_auto = codigo_siguiente(df, fecha_recepcion)
            codigo_op = st.text_input("Código OP", value=codigo_auto, help="Se genera automáticamente; puedes ajustarlo si la empresa ya lo definió.")
        with c4:
            responsable = st.text_input("Responsable", value="Jefe Jesús Rojas / Jefe de producción")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            cliente = st.text_input("Cliente *")
        with c2:
            telefono = st.text_input("Teléfono")
        with c3:
            tipo_cliente = st.selectbox("Tipo de cliente", ["Normal", "Frecuente", "Sensible / urgente", "Nuevo"])
        with c4:
            asesoria = st.selectbox("Asesoría a cliente nuevo", ["No aplica", "Sí", "No"])

        st.markdown("#### Pedido, pago y cálculo comercial")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            tipo_pedido = st.selectbox("Tipo pedido", ["Tira", "Tira/retira", "Matizado", "Tira + matizado"])
        with c2:
            producto = st.text_input("Producto / trabajo", value="Impresión offset CMYK")
        with c3:
            cantidad = st.number_input("Cantidad unidades", min_value=1, value=1000, step=100)
        miles = int(math.ceil(cantidad / 1000))
        default_price = 60 if tipo_pedido == "Tira" else 120 if tipo_pedido == "Tira/retira" else 90
        with c4:
            precio_mil = st.number_input("Precio x 1,000", min_value=0.0, value=float(default_price), step=10.0)
        with c5:
            importe = miles * precio_mil
            st.metric("Importe estimado", f"S/ {importe:,.2f}")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            estado_pago = st.selectbox("Estado de pago", ["Pagado", "Adelanto", "Pendiente"])
        with c2:
            monto_total = st.number_input("Monto total", min_value=0.0, value=float(importe), step=10.0)
        with c3:
            anticipo = st.number_input("Anticipo", min_value=0.0, value=float(importe if estado_pago == "Pagado" else importe * .5 if estado_pago == "Adelanto" else 0), step=10.0)
        with c4:
            saldo = max(monto_total - anticipo, 0)
            st.metric("Saldo", f"S/ {saldo:,.2f}")

        st.markdown("#### Validación técnica y programación")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            fecha_prometida = st.date_input("Fecha prometida", value=fecha_recepcion + timedelta(days=2), min_value=fecha_recepcion, max_value=date(2026, 12, 31))
        with c2:
            hora_prometida = st.time_input("Hora prometida", value=time(18, 0))
        with c3:
            fecha_programada = st.date_input("Fecha programada", value=fecha_recepcion, min_value=fecha_recepcion, max_value=date(2026, 12, 31))
        with c4:
            hora_programada = st.time_input("Hora programada", value=time(9, 30))
        with c5:
            estado_kanban = st.selectbox("Estado Kanban inicial", ["RECIBIDO", "VALIDACIÓN", "BLOQUEADO", "LISTO", "PROGRAMADO"])
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            materiales = st.selectbox("Materiales", ["Sí", "Parcial", "No"])
        with c2:
            diseno_validado = st.selectbox("Diseño validado", ["Sí", "Observado", "No"])
        with c3:
            stock_critico = st.selectbox("Stock crítico", ["No", "Sí", "Reposición DDMRP"])
        with c4:
            oc_activada = st.selectbox("OC activada", ["No", "Sí"])
        with c5:
            complejidad = st.selectbox("Complejidad", ["Baja", "Media", "Alta"])
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            traslado_min = st.number_input("Traslado min", min_value=0, value=20, step=1)
        with c2:
            diagnostico_min = st.number_input("Diagnóstico min", min_value=0, value=25, step=1)
        with c3:
            parada_h = st.number_input("Parada/ajuste h", min_value=0.0, value=0.0, step=0.25)
        with c4:
            merma = st.selectbox("Merma prevista", ["Dentro del estándar", "Ligera desviación", "Fuera del estándar"])
        observacion = st.text_area("Observación técnica / cierre", height=95)
        puntaje, prioridad, accion = puntaje_prioridad(fecha_prometida, materiales if stock_critico == "No" else stock_critico, estado_pago, diseno_validado, complejidad, merma, tipo_cliente, hoy=fecha_recepcion)
        st.markdown(f"<div class='action-strip verde'>Resultado automático: <b>{puntaje} puntos</b> · Prioridad <b>{prioridad}</b> · Acción: <b>{accion}</b></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Guardar OP en SQLite", type="primary")
        if submitted:
            try:
                if not cliente.strip():
                    st.error("Debes registrar el cliente.")
                    return
                if codigo_op in df["codigo_op"].astype(str).tolist():
                    st.error("Ese código OP ya existe. Usa otro código o deja el sugerido automático.")
                    return
                if fecha_programada.weekday() == 6:
                    st.error("No se puede programar en domingo.")
                    return
                data = {
                    "codigo_op": codigo_op.strip(), "fecha_recepcion": fecha_recepcion.isoformat(), "hora_recepcion": hora_recepcion.strftime("%H:%M"),
                    "mes": nombre_mes(fecha_recepcion), "semana": semana_mes(fecha_recepcion), "cliente": cliente.strip(), "telefono": telefono,
                    "tipo_cliente": tipo_cliente, "asesoria_cliente_nuevo": asesoria, "estado_pago": estado_pago, "monto_total": monto_total,
                    "anticipo": anticipo, "saldo": saldo, "tipo_pedido": tipo_pedido, "producto": producto, "cantidad_unidades": cantidad,
                    "miles_facturables": miles, "precio_mil": precio_mil, "importe_estimado": importe, "colores": "CMYK",
                    "fecha_prometida": fecha_prometida.isoformat(), "hora_prometida": hora_prometida.strftime("%H:%M"),
                    "fecha_programada": fecha_programada.isoformat(), "hora_programada": hora_programada.strftime("%H:%M"),
                    "materiales": materiales, "diseno_recibido": "Sí", "diseno_validado": diseno_validado, "stock_critico": stock_critico,
                    "oc_activada": oc_activada, "restriccion": "Sin restricción" if prioridad not in ["Bloqueado pago", "Bloqueado diseño", "Bloqueado materiales"] else prioridad,
                    "traslado_min": traslado_min, "diagnostico_min": diagnostico_min, "parada_ajuste_h": parada_h, "puntaje": puntaje,
                    "prioridad": prioridad, "estado_op": estado_kanban, "estado_kanban": estado_kanban, "cumple_programa": "Pendiente", "resultado": "En seguimiento",
                    "accion_requerida": accion, "responsable": responsable, "alerta_wip": "Controlado", "observacion": observacion, "clave": f"{estado_kanban}|WEB"
                }
                insert_pedido(data)
                st.success(f"OP {codigo_op} registrada correctamente. El dashboard y Kanban ya fueron actualizados.")
                st.rerun()
            except Exception as e:
                st.error(str(e))


def page_base_maestra():
    section_title("Base maestra de pedidos", "Consulta visual, edición controlada, filtros y exportación de reportes desde SQLite.")
    df = read_filtered_base()
    filt = apply_filters(df, "base")
    render_quality_panel(filt)
    visible_cols = [
        "codigo_op", "fecha_recepcion", "hora_recepcion", "mes", "semana", "cliente", "telefono", "tipo_pedido",
        "cantidad_unidades", "miles_facturables", "precio_mil", "importe_estimado", "fecha_prometida", "fecha_programada",
        "fecha_entrega_real", "estado_pago", "materiales", "diseno_validado", "stock_critico", "oc_activada",
        "puntaje", "prioridad", "estado_kanban", "cumple_programa", "resultado", "accion_requerida", "responsable", "alerta_wip", "observacion"
    ]
    editable = ["fecha_programada", "fecha_entrega_real", "estado_pago", "materiales", "diseno_validado", "stock_critico", "oc_activada", "estado_kanban", "cumple_programa", "resultado", "accion_requerida", "responsable", "observacion"]

    tab1, tab2, tab3 = st.tabs(["🎨 Vista ejecutiva coloreada", "✍️ Edición controlada", "📤 Reportes y eliminación"])
    with tab1:
        st.markdown("""
        <div class='info-panel'>
          <b>Lectura rápida:</b> las celdas se colorean por criticidad. Rojo = bloqueo/retraso, morado = DDMRP/stock, naranja = prioridad alta, amarillo = atención preventiva y verde = controlado.
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        styled_pedidos_table(filt, visible_cols, height=620)
    with tab2:
        st.markdown("### Tabla editable")
        st.caption("Solo se habilitan campos de seguimiento para evitar alterar datos históricos cargados desde Excel.")
        edited = st.data_editor(
            filt[[c for c in visible_cols if c in filt.columns]].copy(),
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="editor_base",
            disabled=[c for c in visible_cols if c not in editable],
            column_config={
                "puntaje": st.column_config.ProgressColumn("Puntaje", min_value=0, max_value=100, format="%d pts"),
                "importe_estimado": st.column_config.NumberColumn("Importe estimado", format="S/ %.2f"),
            }
        )
        if st.button("Guardar cambios", type="primary"):
            try:
                upsert_df_edits(edited, editable)
                st.success("Cambios guardados en SQLite. La vista, Kanban y dashboard quedan actualizados.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo guardar: {e}")
    with tab3:
        c1, c2 = st.columns([.35, .65])
        with c1:
            if st.button("Exportar reporte Excel", type="primary"):
                path = exportar_excel("reporte_grafistar")
                st.success(f"Reporte generado: {path.name}")
                st.download_button("Descargar reporte", data=path.read_bytes(), file_name=path.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            st.markdown("""
            <div class='info-panel'>
              El Excel exportado incluye colores por estado/prioridad, filtros, tablas y hojas de resumen. El registro principal sigue siendo la app y SQLite.
            </div>
            """, unsafe_allow_html=True)
        with st.expander("Eliminar OP con confirmación", expanded=False):
            codes = df["codigo_op"].astype(str).tolist() if not df.empty else []
            if codes:
                code = st.selectbox("Código OP a eliminar", codes)
                confirm = st.checkbox("Confirmo eliminación definitiva de esta OP")
                if st.button("Eliminar OP") and confirm:
                    delete_pedido(code)
                    st.success("OP eliminada.")
                    st.rerun()
            else:
                st.info("No hay OP para eliminar.")

def page_prioridad():
    section_title("Matriz de prioridad automática", "El sistema calcula puntaje y decisión operativa para evitar programación verbal.")
    df = read_filtered_base()
    filt = apply_filters(df, "prio")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("### Criterios de puntaje")
        criterios = pd.DataFrame([
            ["Fecha y hora de entrega", "0 a 30", "Crítico / vence hoy = 30"],
            ["Materiales listos", "0 a 20", "Completo = 20; parcial = 10"],
            ["Pago o adelanto", "0 a 15", "Pagado = 15; adelanto = 10"],
            ["Diseño aprobado", "0 a 15", "Validado = 15; observado = 5"],
            ["Complejidad operativa", "3 a 10", "Baja = 10; media = 6; alta = 3"],
            ["Merma prevista", "0 a 5", "Dentro del estándar = 5"],
            ["Cliente / compromiso", "1 a 5", "Urgente = 5; frecuente = 3"],
        ], columns=["Criterio", "Puntaje", "Regla"])
        st.dataframe(criterios, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("### Distribución por prioridad")
        count = filt["prioridad"].value_counts().reset_index()
        count.columns = ["Prioridad", "Pedidos"]
        fig = px.pie(count, names="Prioridad", values="Pedidos", hole=.45, color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(height=370, margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("### Ranking operativo coloreado")
    rank_cols = ["codigo_op", "cliente", "fecha_prometida", "fecha_programada", "estado_pago", "materiales", "diseno_validado", "stock_critico", "puntaje", "prioridad", "estado_kanban", "accion_requerida", "responsable"]
    tabla_rank = filt[[c for c in rank_cols if c in filt.columns]].sort_values(["puntaje"], ascending=False)
    styled_pedidos_table(tabla_rank, rank_cols, height=560)


def page_programacion():
    section_title("Programación diaria y cronograma", "Control de fechas programadas, capacidad y restricciones de domingos/feriados.")
    df = read_filtered_base()
    feriados = pd.read_sql_query("SELECT fecha, descripcion FROM feriados", connect())
    feriados_set = set(feriados["fecha"].astype(str).tolist())
    c1, c2, c3 = st.columns([.25, .25, .5])
    with c1:
        fecha = st.date_input("Fecha a revisar/programar", value=date(2026, 6, 1), min_value=date(2026, 5, 1), max_value=date(2026, 12, 31))
    with c2:
        capacidad = st.number_input("Capacidad diaria referencial", min_value=1, max_value=30, value=8, step=1)
    with c3:
        condicion = "Domingo no laborable" if fecha.weekday() == 6 else "Feriado" if fecha.isoformat() in feriados_set else "Laborable"
        kind = "red" if condicion != "Laborable" else "green"
        st.markdown(f"<div style='padding-top:29px'><span class='status-badge {kind}'>{condicion}</span></div>", unsafe_allow_html=True)
    if condicion != "Laborable":
        st.error("No se deben programar pedidos en esta fecha.")
    diario = df[df["fecha_programada"].dt.date == fecha] if not df.empty and "fecha_programada" in df.columns else pd.DataFrame()
    stats = kpis(diario)
    cols = st.columns(5)
    with cols[0]: kpi_card("Programados", stats["programados"], f"Capacidad {capacidad}", "blue")
    with cols[1]: kpi_card("Cumplidos", stats["cumplidos"], "A tiempo", "green")
    with cols[2]: kpi_card("Retrasados", stats["retrasados"], "Reprogramar", "red" if stats["retrasados"] else "green")
    with cols[3]: kpi_card("Carga", f"{len(diario)}/{capacidad}", "Pedidos/día", "red" if len(diario) > capacidad else "green")
    with cols[4]: kpi_card("Cumplimiento", f"{stats['cumplimiento']:.2f}%", "Día seleccionado", semaforo_cumplimiento(stats["cumplimiento"])[0])
    st.markdown("### Pedidos programados para el día")
    cols_view = ["codigo_op", "cliente", "prioridad", "puntaje", "fecha_prometida", "fecha_programada", "estado_pago", "materiales", "estado_kanban", "resultado", "responsable", "observacion"]
    diario_view = diario[[c for c in cols_view if c in diario.columns]].sort_values(["puntaje"], ascending=False) if not diario.empty else pd.DataFrame(columns=cols_view)
    styled_pedidos_table(diario_view, cols_view, height=360)
    with st.expander("Asignar pedido a una fecha programada", expanded=True):
        candidates = df[~df["estado_kanban"].astype(str).str.upper().isin(["ENTREGADO"])] if not df.empty else df
        if candidates.empty:
            st.info("No hay pedidos pendientes para programar.")
        else:
            c1, c2, c3 = st.columns([.35, .25, .4])
            with c1:
                code = st.selectbox("Código OP", candidates["codigo_op"].astype(str).tolist())
            with c2:
                nueva_fecha = st.date_input("Nueva fecha programada", value=fecha, min_value=date(2026, 5, 1), max_value=date(2026, 12, 31), key="nueva_fecha_prog")
            with c3:
                motivo = st.text_input("Motivo", value="Programación según prioridad y capacidad")
            if st.button("Guardar programación", type="primary"):
                if nueva_fecha.weekday() == 6 or nueva_fecha.isoformat() in feriados_set:
                    st.error("No se puede programar en domingo o feriado.")
                else:
                    update_pedido(code, {"fecha_programada": nueva_fecha.isoformat(), "estado_kanban": "PROGRAMADO", "accion_requerida": "Ejecutar según secuencia programada"})
                    try:
                        mover_kanban(code, "PROGRAMADO", "Jefe Jesús Rojas / Jefe de producción", motivo, "Pedido asignado al cronograma")
                    except Exception:
                        pass
                    st.success("Pedido programado y Kanban actualizado.")
                    st.rerun()
    st.markdown("### Cumplimiento semanal")
    if not df.empty:
        week = df.groupby(["semana"]).apply(lambda x: pd.Series(kpis(x))).reset_index()
        fig = px.bar(week, x="semana", y="cumplimiento", text="cumplimiento", range_y=[0, 110])
        fig.add_hline(y=ESTANDAR, line_dash="dash", annotation_text="Estándar 91.28%")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=380, margin=dict(t=30, b=20, l=10, r=10), yaxis_title="Cumplimiento %", xaxis_title="Semana")
        st.plotly_chart(fig, use_container_width=True)


def page_kanban():
    section_title("Kanban digital / Canva operativo", "Tablero visual con tarjetas por criticidad, límites WIP y avance de cada OP.")
    df = read_filtered_base()
    filt = apply_filters(df, "kanban")
    if filt.empty:
        st.info("No hay pedidos con los filtros actuales.")
        return

    c1, c2, c3 = st.columns([.28, .22, .5])
    with c1:
        vista = st.radio("Vista del tablero", ["Activos y alertas", "Todos", "Solo críticos"], horizontal=True)
    with c2:
        densidad = st.radio("Densidad", ["Detalle", "Compacto"], horizontal=True)
    with c3:
        max_cards = st.slider("Tarjetas visibles por columna", min_value=3, max_value=24, value=10, step=1)

    board_df = filt.copy()
    if vista == "Activos y alertas":
        mask = (
            ~board_df["estado_kanban"].astype(str).str.upper().eq("ENTREGADO") |
            ~board_df["resultado"].astype(str).str.lower().eq("a tiempo") |
            board_df["prioridad"].astype(str).str.lower().str.contains("bloqueado|ddmrp|observado", regex=True, na=False)
        )
        board_df = board_df[mask]
    elif vista == "Solo críticos":
        mask = (
            board_df["criticidad_key"].astype(str).isin(["critico", "ddmrp"]) |
            board_df["prioridad"].astype(str).str.lower().str.contains("bloqueado|ddmrp|observado", regex=True, na=False) |
            board_df["resultado"].astype(str).str.lower().str.contains("retras", regex=True, na=False)
        )
        board_df = board_df[mask]

    st.markdown("""
    <div class='info-panel'>
      <b>Cómo interpretar:</b> 🔴 crítico/bloqueado · 🟣 stock/DDMRP/OC · 🟠 alta prioridad · 🟡 media · 🔵 baja · 🟢 controlado. Cada columna muestra su WIP para detectar acumulación.
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    kanban_summary(board_df)

    tab1, tab2, tab3, tab4 = st.tabs(["🧩 Canva digital", "↔️ Mover tarjeta", "📋 Tabla del tablero", "📌 Reglas WIP"])
    with tab1:
        kanban_board(board_df, max_cards=max_cards, density=densidad)
    with tab2:
        st.markdown("### Movimiento controlado de tarjetas")
        st.caption("Cada movimiento queda registrado en el historial de trazabilidad.")
        if filt.empty:
            st.info("No hay pedidos en el filtro actual.")
        else:
            c1, c2, c3 = st.columns([.28, .22, .5])
            with c1:
                code = st.selectbox("Código OP", filt["codigo_op"].astype(str).tolist(), key="move_code")
            with c2:
                nuevo = st.selectbox("Nuevo estado", KANBAN_ESTADOS, key="move_estado")
            with c3:
                responsable = st.text_input("Responsable", value="Jefe Jesús Rojas / Jefe de producción", key="move_resp")
            motivo = st.text_input("Motivo del movimiento", value="Actualización de seguimiento Kanban", key="move_motivo")
            obs = st.text_area("Observación", key="move_obs")
            if st.button("Guardar movimiento Kanban", type="primary"):
                try:
                    mover_kanban(code, nuevo, responsable, motivo, obs)
                    st.success("Movimiento guardado y trazabilidad actualizada.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with tab3:
        cols = ["codigo_op", "cliente", "fecha_programada", "fecha_prometida", "prioridad", "puntaje", "estado_kanban", "estado_pago", "materiales", "diseno_validado", "stock_critico", "oc_activada", "resultado", "accion_requerida", "responsable", "observacion"]
        styled_pedidos_table(board_df, cols, height=620)
    with tab4:
        reglas = pd.DataFrame([
            ["RECIBIDO → VALIDACIÓN", "OP registrada con datos mínimos completos"],
            ["VALIDACIÓN → LISTO/BLOQUEADO", "Se revisa pago, diseño, materiales y fecha"],
            ["BLOQUEADO → LISTO", "Se levanta la restricción principal"],
            ["LISTO → PROGRAMADO", "Existe prioridad y capacidad disponible"],
            ["PROGRAMADO → PRODUCCIÓN", "Materiales en mesa y máquina disponible"],
            ["PRODUCCIÓN → CALIDAD", "Termina impresión y se registra control"],
            ["CALIDAD → ENTREGADO", "Pedido conforme"],
            ["CALIDAD → OBSERVADO", "Defecto, diferencia de color o reproceso"],
        ], columns=["Movimiento", "Regla operativa"])
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("### Reglas de movimiento")
            st.dataframe(reglas, use_container_width=True, hide_index=True)
        with c2:
            st.markdown("### Límites WIP")
            wip = pd.DataFrame([{"Estado": k, "Límite": "Sin límite" if v is None else v} for k, v in WIP_LIMITES.items()])
            st.dataframe(wip, use_container_width=True, hide_index=True)

def page_trazabilidad():
    section_title("Historial de trazabilidad", "Cada movimiento de estado queda registrado con responsable, fecha, hora y motivo.")
    df = read_filtered_base()
    if df.empty:
        st.info("No hay pedidos.")
        return
    c1, c2 = st.columns([.35, .65])
    with c1:
        code = st.selectbox("Seleccionar OP", df["codigo_op"].astype(str).tolist())
    pedido = df[df["codigo_op"].astype(str) == code].iloc[0]
    with c2:
        st.markdown(f"""
        <div class='info-panel'>
          <h3>{pedido['codigo_op']} · {pedido['cliente']}</h3>
          <p><b>Estado actual:</b> {pedido['estado_kanban']} · <b>Prioridad:</b> {pedido['prioridad']} · <b>Puntaje:</b> {pedido['puntaje']}</p>
          <p><b>Programado:</b> {pedido['fecha_programada']} · <b>Prometido:</b> {pedido['fecha_prometida']} · <b>Resultado:</b> {pedido['resultado']}</p>
          <p><b>Acción requerida:</b> {pedido['accion_requerida']}</p>
        </div>
        """, unsafe_allow_html=True)
    hist = read_historial(code)
    st.markdown("### Línea de tiempo")
    if hist.empty:
        st.info("Aún no hay movimientos registrados para esta OP.")
    else:
        items = []
        for _, h in hist.sort_values("id", ascending=False).iterrows():
            items.append(f"""
            <div class='timeline-item'>
              <b>{h['estado_anterior']} → {h['estado_nuevo']}</b>
              <p>{h['fecha_movimiento']} {h['hora_movimiento']} · Responsable: {h['responsable']}</p>
              <p><b>Motivo:</b> {h['motivo']}</p>
              <p>{h['observacion'] if pd.notna(h['observacion']) else ''}</p>
            </div>
            """)
        st.markdown(f"<div class='timeline'>{''.join(items)}</div>", unsafe_allow_html=True)
    with st.expander("Historial completo en tabla", expanded=False):
        st.dataframe(hist, use_container_width=True, hide_index=True)


def page_dashboard():
    section_title("Dashboard Fase 10: Verificar / Actuar", "Indicadores ejecutivos para comparar As-Is, To-Be mayo, estándar y resultado actual.")
    df = read_filtered_base()
    filt = apply_filters(df, "dash")
    render_quality_panel(filt)
    if filt.empty:
        st.info("No hay datos con el filtro actual.")
        return
    stats = kpis(filt)
    sem, sem_nom, accion = semaforo_cumplimiento(stats["cumplimiento"])
    c1, c2 = st.columns([1.15, .85])
    with c1:
        comp = pd.DataFrame({
            "Escenario": ["As-Is", "To-Be Mayo", "Estándar", "Resultado filtrado"],
            "Cumplimiento": [ASIS, TOBE_MAYO, ESTANDAR, stats["cumplimiento"]]
        })
        fig = px.bar(comp, x="Escenario", y="Cumplimiento", text="Cumplimiento", color="Escenario", color_discrete_sequence=["#64748b", "#08a8ff", "#18c37e", "#ef233c"])
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig.update_layout(title="Comparación de cumplimiento", height=420, yaxis_range=[0, 110], showlegend=False, margin=dict(t=60, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=stats["cumplimiento"],
            number={"suffix": "%"},
            delta={"reference": ESTANDAR, "suffix": " pp vs estándar"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#08a8ff"},
                "steps": [
                    {"range": [0, 75], "color": "#ffe2e5"},
                    {"range": [75, ESTANDAR], "color": "#fff0bd"},
                    {"range": [ESTANDAR, 100], "color": "#d7f9e9"},
                ],
                "threshold": {"line": {"color": "#ef233c", "width": 4}, "thickness": 0.8, "value": ESTANDAR}
            },
            title={"text": f"Semáforo {sem_nom}"}
        ))
        fig.update_layout(height=420, margin=dict(t=60, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(f"<div class='action-strip {sem}'><b>Actuar:</b> {accion}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        by_estado = filt["estado_kanban"].value_counts().reset_index()
        by_estado.columns = ["Estado", "Pedidos"]
        fig = px.bar(by_estado, x="Estado", y="Pedidos", text="Pedidos", color="Estado", color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_layout(title="Pedidos por estado Kanban", height=390, showlegend=False, margin=dict(t=50, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        by_prio = filt["prioridad"].value_counts().reset_index()
        by_prio.columns = ["Prioridad", "Pedidos"]
        fig = px.treemap(by_prio, path=["Prioridad"], values="Pedidos", color="Pedidos", color_continuous_scale="Blues")
        fig.update_layout(title="Carga por prioridad", height=390, margin=dict(t=50, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        if "mes" in df.columns:
            monthly = df.groupby("mes").apply(lambda x: pd.Series(kpis(x))).reset_index()
            # ordenar por fecha mínima
            min_dates = df.groupby("mes")["fecha_recepcion"].min().reset_index(name="_orden")
            monthly = monthly.merge(min_dates, on="mes", how="left").sort_values("_orden")
            fig = px.line(monthly, x="mes", y="cumplimiento", markers=True, text="cumplimiento")
            fig.add_hline(y=ESTANDAR, line_dash="dash", annotation_text="Estándar 91.28%")
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="top center")
            fig.update_layout(title="Cumplimiento mensual 2026", height=390, yaxis_range=[0, 110], margin=dict(t=50, b=20, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        tipo = filt["tipo_pedido"].value_counts().reset_index()
        tipo.columns = ["Tipo pedido", "Pedidos"]
        fig = px.pie(tipo, names="Tipo pedido", values="Pedidos", hole=.5, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(title="Pedidos por tipo de impresión", height=390, margin=dict(t=50, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        top_clientes = filt["cliente"].value_counts().head(10).reset_index()
        top_clientes.columns = ["Cliente", "Pedidos"]
        fig = px.bar(top_clientes, y="Cliente", x="Pedidos", orientation="h", text="Pedidos")
        fig.update_layout(title="Top clientes por pedidos", height=410, margin=dict(t=50, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        dinero = filt.copy()
        dinero["importe_estimado"] = pd.to_numeric(dinero["importe_estimado"], errors="coerce").fillna(0)
        imp = dinero.groupby("mes")["importe_estimado"].sum().reset_index().sort_values("mes")
        fig = px.bar(imp, x="mes", y="importe_estimado", text="importe_estimado")
        fig.update_traces(texttemplate="S/ %{text:,.0f}", textposition="outside")
        fig.update_layout(title="Importe estimado mensual", height=410, margin=dict(t=50, b=20, l=10, r=10), yaxis_title="S/")
        st.plotly_chart(fig, use_container_width=True)


def page_procedimiento():
    section_title("Procedimiento estándar de registro y control", "Manual operativo integrado para sustentar la Fase 10.")
    st.markdown("""
    <div class='info-panel'>
      <h3>Objetivo del procedimiento</h3>
      <p>Convertir la recepción y programación de pedidos de Grafistar en un flujo digital trazable: OP digital → validación → prioridad → programación → Kanban → dashboard → acción correctiva.</p>
    </div>
    """, unsafe_allow_html=True)
    action_cards()
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("### Procedimiento de uso")
        pasos = [
            "Registrar la OP digital desde la página web.",
            "Validar cliente, pago, diseño, materiales y fecha prometida.",
            "Calcular prioridad automáticamente con puntaje de 0 a 100.",
            "Liberar o bloquear el pedido según restricciones.",
            "Activar OC DDMRP/SRM si existe stock crítico.",
            "Programar según prioridad, capacidad y días laborables.",
            "Mover la tarjeta en el Kanban y guardar trazabilidad.",
            "Registrar producción, calidad, merma y entrega real.",
            "Verificar cumplimiento mensual y actuar según semáforo.",
        ]
        for i, p in enumerate(pasos, 1):
            st.markdown(f"<div class='timeline-item'><b>{i}. {p}</b></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("### Guion breve para exposición")
        st.markdown("""
        <div class='info-panel'>
          <p>“En la Fase 10 implementamos una aplicación web para verificar y actuar sobre la mejora del cumplimiento de servicio. Antes, la programación dependía de registros manuales y decisiones verbales. Ahora, cada pedido entra por una OP digital, se valida, recibe un puntaje de prioridad, se programa y se controla mediante un Kanban visual.</p>
          <p>El sistema usa SQLite como base principal, por eso desde junio a diciembre ya no se llena Excel. Excel queda solo como histórico inicial de mayo y como reporte exportable. El dashboard compara el resultado contra el As-Is de 56.78%, el To-Be de mayo de 92.86% y el estándar de 91.28%.</p>
          <p>Cuando el semáforo está verde se mantiene el procedimiento; si está amarillo se revisan WIP y bloqueos; y si está rojo se activa un plan de acción inmediato. Así demostramos trazabilidad, control y toma de decisiones.”</p>
        </div>
        """, unsafe_allow_html=True)


def main():
    with st.sidebar:
        theme = st.radio("Modo visual", ["Claro", "Oscuro"], horizontal=True, key="theme_mode")
    load_css(theme)
    sidebar_brand()
    with st.sidebar:
        if option_menu:
            page = option_menu(
                menu_title=None,
                options=MENU,
                icons=ICONOS,
                default_index=0,
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent"},
                    "icon": {"color": "#08a8ff", "font-size": "16px"},
                    "nav-link": {"font-size": "14px", "font-weight": "700", "text-align": "left", "margin": "4px 0", "border-radius": "14px", "padding": "10px 12px"},
                    "nav-link-selected": {"background": "linear-gradient(135deg,#08a8ff,#ef233c)", "color": "white"},
                },
            )
        else:
            page = st.radio("Navegación", MENU, label_visibility="collapsed")
        st.markdown("---")
        st.markdown("**Mayo 2026:** histórico importado desde Excel")
        st.markdown("**Junio–diciembre:** registro web + SQLite")
        st.caption("Tip: usa `INICIAR_APP.bat` para abrir la app sin escribir comandos.")

    if page == "Inicio": page_inicio()
    elif page == "Carga Inicial": page_carga_inicial()
    elif page == "Registro OP": page_registro_op()
    elif page == "Base Maestra": page_base_maestra()
    elif page == "Prioridad": page_prioridad()
    elif page == "Programación": page_programacion()
    elif page == "Kanban": page_kanban()
    elif page == "Trazabilidad": page_trazabilidad()
    elif page == "Dashboard": page_dashboard()
    elif page == "Procedimiento": page_procedimiento()


if __name__ == "__main__":
    main()
