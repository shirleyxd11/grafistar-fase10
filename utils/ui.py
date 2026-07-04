from __future__ import annotations
from pathlib import Path
import base64
import html
import pandas as pd
import streamlit as st
from .calculos import KANBAN_ESTADOS, WIP_LIMITES, kpis, semaforo_cumplimiento, ASIS, TOBE_MAYO, ESTANDAR

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "grafistar_logo.png"
CSS = ROOT / "assets" / "styles.css"

STATE_META = {
    "RECIBIDO": {"icon":"📥", "short":"Entrada", "desc":"OP registrada", "class":"state-recibido"},
    "VALIDACIÓN": {"icon":"🔎", "short":"Validación", "desc":"Pago/diseño/materiales", "class":"state-validacion"},
    "BLOQUEADO": {"icon":"⛔", "short":"Bloqueado", "desc":"Restricción pendiente", "class":"state-bloqueado"},
    "LISTO": {"icon":"✅", "short":"Listo", "desc":"Liberado para programar", "class":"state-listo"},
    "PROGRAMADO": {"icon":"🗓️", "short":"Programado", "desc":"Secuencia definida", "class":"state-programado"},
    "PRODUCCIÓN": {"icon":"⚙️", "short":"Producción", "desc":"En máquina", "class":"state-produccion"},
    "CALIDAD": {"icon":"🧪", "short":"Calidad", "desc":"Conformidad/merma", "class":"state-calidad"},
    "ENTREGADO": {"icon":"🏁", "short":"Entregado", "desc":"Cerrado", "class":"state-entregado"},
    "OBSERVADO": {"icon":"⚠️", "short":"Observado", "desc":"Reproceso/corrección", "class":"state-observado"},
}

PRIORITY_ORDER = {
    "Bloqueado materiales": 0,
    "Bloqueado pago": 1,
    "Bloqueado diseño": 2,
    "Alta-DDMRP": 3,
    "Alta": 4,
    "Media": 5,
    "Baja": 6,
    "Observado": 7,
}


def img_to_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def load_css(theme: str = "Claro"):
    css = CSS.read_text(encoding="utf-8") if CSS.exists() else ""
    mode = "dark" if theme == "Oscuro" else "light"
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    st.markdown(f"<div class='theme-hook {mode}'></div>", unsafe_allow_html=True)


def sidebar_brand():
    logo_b64 = img_to_b64(LOGO)
    logo_html = f"<img src='data:image/png;base64,{logo_b64}' class='brand-logo'/>" if logo_b64 else ""
    st.sidebar.markdown(f"""
        <div class='sidebar-brand'>
            {logo_html}
            <div class='brand-kicker'>Command Center</div>
            <div class='brand-title'>Grafistar</div>
            <div class='brand-subtitle'>Gestión digital de pedidos · Impresión de calidad</div>
            <div class='brand-pill'>Fase 10 · Verificar / Actuar</div>
        </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")


def hero():
    logo_b64 = img_to_b64(LOGO)
    logo = f"<img src='data:image/png;base64,{logo_b64}' class='hero-logo'/>" if logo_b64 else ""
    st.markdown(f"""
    <section class='hero-panel'>
        <div class='hero-copy'>
            <div class='eyebrow'>Grafistar · sistema digital operativo</div>
            <h1>Control de pedidos con trazabilidad, Kanban y decisiones en tiempo real</h1>
            <p>Plataforma web para registrar OP, priorizar con puntaje, programar pedidos, controlar semáforos y verificar el cumplimiento contra As-Is, To-Be y estándar.</p>
            <div class='hero-badges'>
                <span>OP digital</span><span>Kanban visual</span><span>Semáforos</span><span>SQLite</span><span>Dashboard ejecutivo</span>
            </div>
        </div>
        <div class='hero-visual'>{logo}<div class='hero-orbit cmyk-c'></div><div class='hero-orbit cmyk-m'></div><div class='hero-orbit cmyk-y'></div></div>
    </section>
    """, unsafe_allow_html=True)


def kpi_card(title, value, delta=None, status="neutral", footer=None):
    safe_title = html.escape(str(title))
    safe_value = html.escape(str(value))
    delta_html = f"<span class='kpi-delta'>{html.escape(str(delta))}</span>" if delta else ""
    footer_html = f"<div class='kpi-footer'>{html.escape(str(footer))}</div>" if footer else ""
    st.markdown(f"""
    <div class='kpi-card {status}'>
        <div class='kpi-title'>{safe_title}</div>
        <div class='kpi-value'>{safe_value}</div>
        {delta_html}
        {footer_html}
    </div>
    """, unsafe_allow_html=True)


def section_title(title, subtitle=""):
    st.markdown(f"""
    <div class='section-title'>
        <div class='section-accent'></div>
        <div><h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>
    </div>
    """, unsafe_allow_html=True)


def status_badge(text, kind="neutral"):
    st.markdown(f"<span class='status-badge {kind}'>{html.escape(str(text))}</span>", unsafe_allow_html=True)


def render_quality_panel(df: pd.DataFrame):
    stats = kpis(df)
    sem_key, sem_nombre, accion = semaforo_cumplimiento(stats["cumplimiento"])
    cols = st.columns(6)
    with cols[0]: kpi_card("Pedidos", stats["total"], "Base filtrada", "blue")
    with cols[1]: kpi_card("Cumplidos", stats["cumplidos"], "A tiempo", "green")
    with cols[2]: kpi_card("Retrasados", stats["retrasados"], "Reprogramar", "red" if stats["retrasados"] else "green")
    with cols[3]: kpi_card("Cumplimiento", f"{stats['cumplimiento']:.2f}%", f"Estándar {ESTANDAR:.2f}%", sem_key)
    with cols[4]: kpi_card("As-Is", f"{ASIS:.2f}%", "Abril", "neutral")
    with cols[5]: kpi_card("To-Be mayo", f"{TOBE_MAYO:.2f}%", "+36.08 p.p.", "purple")
    st.markdown(f"<div class='action-strip {sem_key}'><b>Semáforo {sem_nombre}:</b> {html.escape(accion)}</div>", unsafe_allow_html=True)


def _safe(v, default=""):
    if pd.isna(v) if isinstance(v, float) else False:
        return default
    if v is None:
        return default
    return str(v)


def _date_short(v):
    try:
        dt = pd.to_datetime(v)
        if pd.isna(dt): return "-"
        return dt.strftime("%d/%m")
    except Exception:
        return "-" if not v else str(v)


def _days_to_due(v):
    try:
        dt = pd.to_datetime(v).normalize()
        today = pd.Timestamp("2026-05-31") if dt.year == 2026 and dt.month == 5 else pd.Timestamp.today().normalize()
        d = (dt - today).days
        if d < 0: return f"{abs(d)} días vencido", "late"
        if d == 0: return "vence hoy", "today"
        if d <= 2: return f"{d} días", "soon"
        return f"{d} días", "ok"
    except Exception:
        return "sin fecha", "muted"


def _score_bar(value):
    try:
        v = max(0, min(100, float(value)))
    except Exception:
        v = 0
    return f"<div class='score-bar'><span style='width:{v}%;'></span></div>"


def kanban_summary(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("No hay pedidos para resumir.")
        return
    cols = st.columns(9)
    for i, state in enumerate(KANBAN_ESTADOS):
        meta = STATE_META[state]
        d = df[df["estado_kanban"].astype(str).str.upper() == state]
        count = len(d)
        limit = WIP_LIMITES.get(state)
        kind = "green" if limit is None or count < limit else "yellow" if count == limit else "red"
        with cols[i]:
            st.markdown(f"""
            <div class='mini-state {meta['class']} {kind}'>
              <span>{meta['icon']}</span>
              <b>{count}</b>
              <small>{meta['short']}</small>
            </div>
            """, unsafe_allow_html=True)


def kanban_board(df: pd.DataFrame, max_cards: int = 12, density: str = "Detalle"):
    if df is None or df.empty:
        st.info("No hay pedidos para mostrar en el tablero.")
        return
    data = df.copy()
    if "puntaje" in data.columns:
        data["_prio_order"] = data["prioridad"].map(PRIORITY_ORDER).fillna(9)
        data["_puntaje_sort"] = pd.to_numeric(data["puntaje"], errors="coerce").fillna(0)
        data = data.sort_values(["_prio_order", "_puntaje_sort"], ascending=[True, False])
    html_cols = []
    compact = density == "Compacto"
    for state in KANBAN_ESTADOS:
        meta = STATE_META[state]
        d = data[data["estado_kanban"].astype(str).str.upper() == state].copy()
        limit = WIP_LIMITES.get(state)
        count = len(d)
        if limit is None:
            wip_kind, wip_text = "ok", "Sin límite operativo"
        elif count > limit:
            wip_kind, wip_text = "danger", f"WIP excedido {count}/{limit}"
        elif count == limit:
            wip_kind, wip_text = "warn", f"En límite {count}/{limit}"
        else:
            wip_kind, wip_text = "ok", f"WIP {count}/{limit}"
        cards_html = []
        for _, row in d.head(max_cards).iterrows():
            ck = _safe(row.get("criticidad_key"), "controlado")
            code = html.escape(_safe(row.get("codigo_op")))
            cliente = html.escape(_safe(row.get("cliente")))
            prioridad = html.escape(_safe(row.get("prioridad")))
            puntaje_raw = row.get("puntaje", 0)
            try: puntaje = str(int(float(puntaje_raw)))
            except Exception: puntaje = "-"
            pago = html.escape(_safe(row.get("estado_pago")))
            mat = html.escape(_safe(row.get("materiales")))
            diseno = html.escape(_safe(row.get("diseno_validado")))
            prog = html.escape(_date_short(row.get("fecha_programada")))
            prom = html.escape(_date_short(row.get("fecha_prometida")))
            due_text, due_kind = _days_to_due(row.get("fecha_prometida"))
            accion = html.escape(_safe(row.get("accion_requerida"))[:115])
            obs = html.escape(_safe(row.get("observacion"))[:95])
            icon = html.escape(_safe(row.get("criticidad_icono"), "🟢"))
            resultado = html.escape(_safe(row.get("resultado")))
            result_chip = "ok" if "A tiempo" in resultado else "bad" if resultado else "muted"
            body = "" if compact else f"""
                <div class='card-checks'>
                  <span class='dot-label'><i class='dot pago'></i>{pago}</span>
                  <span class='dot-label'><i class='dot mat'></i>Mat. {mat}</span>
                  <span class='dot-label'><i class='dot dis'></i>Diseño {diseno}</span>
                </div>
                <div class='card-action'>{accion}</div>
                <div class='card-observation'>{obs}</div>
            """
            cards_html.append(f"""
              <article class='kanban-card {ck}'>
                <div class='card-ribbon'></div>
                <div class='card-top'><span class='code'>{code}</span><span class='crit'>{icon}</span></div>
                <h4>{cliente}</h4>
                <div class='card-meta'><span>Prog. {prog}</span><span>Prom. {prom}</span><span class='due {due_kind}'>{html.escape(due_text)}</span></div>
                <div class='chips'><span class='prio-chip {ck}'>{prioridad}</span><span>{puntaje} pts</span><span class='{result_chip}'>{resultado}</span></div>
                {_score_bar(puntaje_raw)}
                {body}
              </article>
            """)
        if not cards_html:
            cards_html.append("<div class='empty-lane'>Sin tarjetas en este estado</div>")
        if len(d) > max_cards:
            cards_html.append(f"<div class='more-card'>+ {len(d)-max_cards} pedidos más · usa filtros para revisar</div>")
        html_cols.append(f"""
          <div class='kanban-column neo {meta['class']}'>
            <div class='column-head {wip_kind}'>
              <div><span class='state-icon'>{meta['icon']}</span><b>{state}</b><small>{meta['desc']}</small></div>
              <strong>{count}</strong>
            </div>
            <div class='wip-badge {wip_kind}'>{wip_text}</div>
            <div class='column-body'>{''.join(cards_html)}</div>
          </div>
        """)
    board = f"<div class='kanban-board-shell'><div class='kanban-wrap'>{''.join(html_cols)}</div></div>"
    st.markdown(board, unsafe_allow_html=True)


def action_cards():
    st.markdown("""
    <div class='action-grid'>
      <div class='action-card'><b>1. Registrar</b><span>La OP entra desde la web y queda en SQLite.</span></div>
      <div class='action-card'><b>2. Validar</b><span>Pago, diseño, materiales y fecha prometida.</span></div>
      <div class='action-card'><b>3. Priorizar</b><span>Puntaje de 0 a 100 y criticidad visual.</span></div>
      <div class='action-card'><b>4. Programar</b><span>Control de capacidad, domingo y feriados.</span></div>
      <div class='action-card'><b>5. Mover Kanban</b><span>Cada cambio queda en trazabilidad.</span></div>
      <div class='action-card'><b>6. Actuar</b><span>Semáforos indican cuándo corregir.</span></div>
    </div>
    """, unsafe_allow_html=True)


def _style_row(row):
    styles = []
    for col, val in row.items():
        txt = str(val).lower()
        style = ""
        if col in {"prioridad", "estado_kanban", "resultado", "estado_pago", "materiales", "diseno_validado", "stock_critico", "oc_activada", "alerta_wip"}:
            if "bloque" in txt or "retras" in txt or "observ" in txt or "pendiente" in txt or txt == "no":
                style = "background-color:#ffe4e8;color:#981b2c;font-weight:700;"
            elif "ddmrp" in txt or "repos" in txt or "crit" in txt or "oc" in txt:
                style = "background-color:#f0e7ff;color:#5b21b6;font-weight:700;"
            elif "alta" in txt:
                style = "background-color:#fff1db;color:#9a4b00;font-weight:700;"
            elif "media" in txt or "adelanto" in txt:
                style = "background-color:#fff8d9;color:#815400;font-weight:700;"
            elif "baja" in txt:
                style = "background-color:#e7f4ff;color:#075985;font-weight:700;"
            elif "sí" in txt or "si" == txt or "a tiempo" in txt or "entregado" in txt or "pagado" in txt or "controlado" in txt:
                style = "background-color:#e6f8ef;color:#087450;font-weight:700;"
        styles.append(style)
    return styles


def styled_pedidos_table(df: pd.DataFrame, cols: list[str] | None = None, height: int = 560):
    if df is None or df.empty:
        st.info("No hay datos para mostrar.")
        return
    data = df.copy()
    if cols:
        data = data[[c for c in cols if c in data.columns]].copy()
    for c in ["fecha_recepcion", "fecha_prometida", "fecha_programada", "fecha_entrega_real"]:
        if c in data.columns:
            data[c] = pd.to_datetime(data[c], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    numeric_formats = {}
    if "importe_estimado" in data.columns: numeric_formats["importe_estimado"] = "S/ {:,.2f}"
    if "puntaje" in data.columns: numeric_formats["puntaje"] = "{:.0f}"
    styler = data.style.apply(_style_row, axis=1).format(numeric_formats, na_rep="")
    st.dataframe(styler, use_container_width=True, height=height, hide_index=True)
