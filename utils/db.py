from __future__ import annotations

from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime
from .excel_loader import cargar_pedidos_mayo
from .calculos import normalizar_estado_kanban, criticidad, nombre_mes, semana_mes

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "pedidos.db"
EXCEL_INICIAL = ROOT / "data" / "excel_inicial" / "TO-BE_INDICADOR_1.xlsx"

PEDIDOS_COLUMNS = [
    "codigo_op", "fecha_recepcion", "hora_recepcion", "mes", "semana", "cliente", "telefono",
    "tipo_cliente", "asesoria_cliente_nuevo", "estado_pago", "monto_total", "anticipo", "saldo",
    "tipo_pedido", "producto", "cantidad_unidades", "miles_facturables", "precio_mil", "importe_estimado",
    "colores", "fecha_prometida", "hora_prometida", "fecha_programada", "hora_programada",
    "fecha_entrega_real", "hora_entrega_real", "materiales", "pliegos_entregados", "merma_estandar",
    "merma_adicional", "pliegos_requeridos", "diseno_recibido", "diseno_validado", "stock_critico",
    "oc_activada", "restriccion", "traslado_min", "diagnostico_min", "parada_ajuste_h", "puntaje",
    "prioridad", "estado_op", "estado_kanban", "cumple_programa", "resultado", "accion_requerida",
    "responsable", "alerta_wip", "observacion", "clave", "fuente", "criticidad_key", "criticidad", "criticidad_icono",
    "fecha_creacion", "fecha_actualizacion"
]

CREATE_PEDIDOS = """
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_op TEXT UNIQUE NOT NULL,
    fecha_recepcion TEXT,
    hora_recepcion TEXT,
    mes TEXT,
    semana TEXT,
    cliente TEXT NOT NULL,
    telefono TEXT,
    tipo_cliente TEXT DEFAULT 'Normal',
    asesoria_cliente_nuevo TEXT,
    estado_pago TEXT,
    monto_total REAL,
    anticipo REAL,
    saldo REAL,
    tipo_pedido TEXT,
    producto TEXT,
    cantidad_unidades REAL,
    miles_facturables REAL,
    precio_mil REAL,
    importe_estimado REAL,
    colores TEXT DEFAULT 'CMYK',
    fecha_prometida TEXT,
    hora_prometida TEXT,
    fecha_programada TEXT,
    hora_programada TEXT,
    fecha_entrega_real TEXT,
    hora_entrega_real TEXT,
    materiales TEXT,
    pliegos_entregados REAL,
    merma_estandar REAL,
    merma_adicional REAL,
    pliegos_requeridos REAL,
    diseno_recibido TEXT,
    diseno_validado TEXT,
    stock_critico TEXT,
    oc_activada TEXT,
    restriccion TEXT,
    traslado_min REAL,
    diagnostico_min REAL,
    parada_ajuste_h REAL,
    puntaje REAL,
    prioridad TEXT,
    estado_op TEXT,
    estado_kanban TEXT,
    cumple_programa TEXT,
    resultado TEXT,
    accion_requerida TEXT,
    responsable TEXT,
    alerta_wip TEXT,
    observacion TEXT,
    clave TEXT,
    fuente TEXT,
    criticidad_key TEXT,
    criticidad TEXT,
    criticidad_icono TEXT,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT
)
"""

CREATE_HISTORIAL = """
CREATE TABLE IF NOT EXISTS historial_kanban (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_op TEXT NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT,
    fecha_movimiento TEXT,
    hora_movimiento TEXT,
    responsable TEXT,
    motivo TEXT,
    observacion TEXT
)
"""

CREATE_FERIADOS = """
CREATE TABLE IF NOT EXISTS feriados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT UNIQUE NOT NULL,
    descripcion TEXT
)
"""

CREATE_CONFIG = """
CREATE TABLE IF NOT EXISTS configuracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parametro TEXT UNIQUE NOT NULL,
    valor TEXT
)
"""



def _sqlite_value(v):
    try:
        import pandas as pd
        if pd.isna(v):
            return None
    except Exception:
        pass
    if hasattr(v, "strftime"):
        try:
            return v.strftime("%Y-%m-%d")
        except Exception:
            return str(v)
    return v

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute(CREATE_PEDIDOS)
    cur.execute(CREATE_HISTORIAL)
    cur.execute(CREATE_FERIADOS)
    cur.execute(CREATE_CONFIG)
    cur.execute("INSERT OR IGNORE INTO feriados(fecha, descripcion) VALUES (?, ?)", ("2026-05-01", "Día del Trabajo"))
    default_config = {
        "estandar": "91.28",
        "asis": "56.78",
        "tobe_mayo": "92.86",
        "capacidad_diaria": "8",
        "responsable_principal": "Jefe Jesús Rojas / Jefe de producción",
        "empresa": "Grafistar",
    }
    for k, v in default_config.items():
        cur.execute("INSERT OR IGNORE INTO configuracion(parametro, valor) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


def pedidos_count() -> int:
    init_schema()
    conn = connect()
    n = conn.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0]
    conn.close()
    return int(n)


def importar_mayo_desde_excel(force: bool = False) -> dict:
    init_schema()
    conn = connect()
    cur = conn.cursor()
    if force:
        cur.execute("DELETE FROM historial_kanban")
        cur.execute("DELETE FROM pedidos")
        conn.commit()
    actual = cur.execute("SELECT COUNT(*) FROM pedidos WHERE fuente='Excel To-Be Mayo 2026'").fetchone()[0]
    if actual and not force:
        df = read_pedidos()
        conn.close()
        return {"ok": True, "mensaje": "Mayo ya estaba cargado. No se duplicaron registros.", "registros": actual, "df": df}
    df = cargar_pedidos_mayo(EXCEL_INICIAL)
    # completar columnas faltantes
    for col in PEDIDOS_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[PEDIDOS_COLUMNS]
    df.to_sql("pedidos", conn, if_exists="append", index=False)
    now = datetime.now()
    movimientos = []
    for _, row in df.iterrows():
        movimientos.append({
            "codigo_op": row["codigo_op"],
            "estado_anterior": "CREADO",
            "estado_nuevo": row.get("estado_kanban") or "RECIBIDO",
            "fecha_movimiento": now.strftime("%Y-%m-%d"),
            "hora_movimiento": now.strftime("%H:%M:%S"),
            "responsable": row.get("responsable") or "Jefe Jesús Rojas / Jefe de producción",
            "motivo": "Carga inicial histórica desde Excel To-Be mayo 2026",
            "observacion": row.get("observacion") or "Base histórica importada",
        })
    pd.DataFrame(movimientos).to_sql("historial_kanban", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    return {"ok": True, "mensaje": "Carga histórica de mayo completada.", "registros": len(df), "df": df}


def ensure_db_ready():
    init_schema()
    if pedidos_count() == 0 and EXCEL_INICIAL.exists():
        importar_mayo_desde_excel(force=False)


def read_pedidos() -> pd.DataFrame:
    init_schema()
    conn = connect()
    df = pd.read_sql_query("SELECT * FROM pedidos ORDER BY fecha_recepcion, codigo_op", conn)
    conn.close()
    return df


def read_historial(codigo_op: str | None = None) -> pd.DataFrame:
    init_schema()
    conn = connect()
    if codigo_op:
        df = pd.read_sql_query("SELECT * FROM historial_kanban WHERE codigo_op=? ORDER BY id DESC", conn, params=(codigo_op,))
    else:
        df = pd.read_sql_query("SELECT * FROM historial_kanban ORDER BY id DESC", conn)
    conn.close()
    return df


def insert_pedido(data: dict):
    init_schema()
    if not data.get("cliente"):
        raise ValueError("No se puede registrar una OP sin cliente.")
    data = dict(data)
    data["estado_kanban"] = normalizar_estado_kanban(data.get("estado_kanban", "RECIBIDO"))
    data["mes"] = data.get("mes") or nombre_mes(data.get("fecha_recepcion"))
    data["semana"] = data.get("semana") or semana_mes(data.get("fecha_recepcion"))
    data["fuente"] = data.get("fuente") or "Registro web SQLite"
    data["fecha_creacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["fecha_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["criticidad_key"], data["criticidad"], data["criticidad_icono"] = criticidad(data)
    for col in PEDIDOS_COLUMNS:
        data.setdefault(col, None)
    conn = connect()
    cols = PEDIDOS_COLUMNS
    placeholders = ",".join(["?"] * len(cols))
    conn.execute(f"INSERT INTO pedidos({','.join(cols)}) VALUES ({placeholders})", [data.get(c) for c in cols])
    conn.execute(
        "INSERT INTO historial_kanban(codigo_op, estado_anterior, estado_nuevo, fecha_movimiento, hora_movimiento, responsable, motivo, observacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (data["codigo_op"], "CREADO", data["estado_kanban"], datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), data.get("responsable"), "Registro de nueva OP desde la web", data.get("observacion"))
    )
    conn.commit()
    conn.close()


def update_pedido(codigo_op: str, updates: dict):
    if not updates:
        return
    updates = dict(updates)
    if "estado_kanban" in updates:
        updates["estado_kanban"] = normalizar_estado_kanban(updates["estado_kanban"])
    # recalcular criticidad con datos actuales + updates
    df = read_pedidos()
    current = df[df["codigo_op"] == codigo_op].head(1)
    if not current.empty:
        merged = current.iloc[0].to_dict()
        merged.update(updates)
        updates["criticidad_key"], updates["criticidad"], updates["criticidad_icono"] = criticidad(merged)
    updates["fecha_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = {k: _sqlite_value(v) for k, v in updates.items()}
    conn = connect()
    pairs = ", ".join([f"{k}=?" for k in updates.keys()])
    params = list(updates.values()) + [codigo_op]
    conn.execute(f"UPDATE pedidos SET {pairs} WHERE codigo_op=?", params)
    conn.commit()
    conn.close()


def mover_kanban(codigo_op: str, nuevo_estado: str, responsable: str, motivo: str, observacion: str = ""):
    nuevo_estado = normalizar_estado_kanban(nuevo_estado)
    df = read_pedidos()
    row = df[df["codigo_op"] == codigo_op]
    if row.empty:
        raise ValueError("Código OP no encontrado.")
    estado_anterior = row.iloc[0].get("estado_kanban") or "RECIBIDO"
    # validaciones básicas operativas
    if nuevo_estado == "PRODUCCIÓN":
        mat = str(row.iloc[0].get("materiales", "")).lower()
        dis = str(row.iloc[0].get("diseno_validado", "")).lower()
        if not ("sí" in mat or mat == "si"):
            raise ValueError("No puede pasar a PRODUCCIÓN si no tiene materiales completos.")
        if not ("sí" in dis or dis == "si"):
            raise ValueError("No puede pasar a PRODUCCIÓN si el diseño no está validado.")
    if nuevo_estado == "ENTREGADO" and not row.iloc[0].get("fecha_entrega_real"):
        raise ValueError("No puede marcarse como ENTREGADO sin fecha de entrega real.")
    conn = connect()
    conn.execute("UPDATE pedidos SET estado_kanban=?, fecha_actualizacion=? WHERE codigo_op=?", (nuevo_estado, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), codigo_op))
    conn.execute(
        "INSERT INTO historial_kanban(codigo_op, estado_anterior, estado_nuevo, fecha_movimiento, hora_movimiento, responsable, motivo, observacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (codigo_op, estado_anterior, nuevo_estado, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), responsable, motivo, observacion)
    )
    conn.commit()
    conn.close()


def upsert_df_edits(df: pd.DataFrame, editable_cols: list[str]):
    original = read_pedidos().set_index("codigo_op")
    conn = connect()
    for _, row in df.iterrows():
        code = row.get("codigo_op")
        if not code or code not in original.index:
            continue
        updates = {}
        for col in editable_cols:
            if col in df.columns:
                old = original.loc[code, col] if col in original.columns else None
                new = row[col]
                if str(old) != str(new):
                    updates[col] = new
        if updates:
            updates["fecha_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if "estado_kanban" in updates:
                updates["estado_kanban"] = normalizar_estado_kanban(updates["estado_kanban"])
            pairs = ", ".join([f"{k}=?" for k in updates])
            updates = {k: _sqlite_value(v) for k, v in updates.items()}
            conn.execute(f"UPDATE pedidos SET {pairs} WHERE codigo_op=?", list(updates.values()) + [code])
    conn.commit()
    conn.close()


def delete_pedido(codigo_op: str):
    conn = connect()
    conn.execute("DELETE FROM historial_kanban WHERE codigo_op=?", (codigo_op,))
    conn.execute("DELETE FROM pedidos WHERE codigo_op=?", (codigo_op,))
    conn.commit()
    conn.close()
