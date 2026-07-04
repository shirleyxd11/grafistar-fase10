from __future__ import annotations

from datetime import date, datetime
import math
import pandas as pd

ASIS = 56.78
TOBE_MAYO = 92.86
ESTANDAR = 91.28
MESES_2026 = {
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre",
    10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}
KANBAN_ESTADOS = [
    "RECIBIDO", "VALIDACIÓN", "BLOQUEADO", "LISTO", "PROGRAMADO",
    "PRODUCCIÓN", "CALIDAD", "ENTREGADO", "OBSERVADO"
]
WIP_LIMITES = {
    "RECIBIDO": None,
    "VALIDACIÓN": 3,
    "BLOQUEADO": None,
    "LISTO": None,
    "PROGRAMADO": None,
    "PRODUCCIÓN": 2,
    "CALIDAD": 2,
    "ENTREGADO": None,
    "OBSERVADO": None,
}


def normalizar_si_no(valor: object) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "No"
    txt = str(valor).strip().lower()
    if txt in {"si", "sí", "s", "true", "1", "pagado", "completo", "validado", "aprobado"}:
        return "Sí"
    if "repos" in txt or "ddmrp" in txt or "crit" in txt:
        return str(valor).strip()
    return "No" if txt in {"no", "false", "0", "pendiente", "incompleto"} else str(valor).strip()


def normalizar_estado_kanban(valor: object) -> str:
    if valor is None:
        return "RECIBIDO"
    txt = str(valor).strip().upper()
    txt = txt.replace("VALIDACION", "VALIDACIÓN").replace("PRODUCCION", "PRODUCCIÓN")
    if "BLOQUE" in txt or "DDMRP" in txt:
        return "BLOQUEADO"
    if "OBSERV" in txt:
        return "OBSERVADO"
    if "ENTREG" in txt or "CERR" in txt:
        return "ENTREGADO"
    if "VALID" in txt:
        return "VALIDACIÓN"
    if "LIST" in txt:
        return "LISTO"
    if "PROGRAM" in txt:
        return "PROGRAMADO"
    if "PRODUC" in txt or "IMPRES" in txt:
        return "PRODUCCIÓN"
    if "CALIDAD" in txt or "PRUEBA" in txt:
        return "CALIDAD"
    if "RECIB" in txt:
        return "RECIBIDO"
    return txt if txt in KANBAN_ESTADOS else "RECIBIDO"


def nombre_mes(fecha: object) -> str:
    try:
        dt = pd.to_datetime(fecha)
        if pd.isna(dt):
            return "Sin mes"
        return f"{MESES_2026.get(dt.month, dt.strftime('%B').capitalize())} {dt.year}"
    except Exception:
        return "Sin mes"


def semana_mes(fecha: object) -> str:
    try:
        dt = pd.to_datetime(fecha)
        if pd.isna(dt):
            return "Sin semana"
        wk = (dt.day - 1) // 7 + 1
        return f"Semana {wk}"
    except Exception:
        return "Sin semana"


def codigo_siguiente(df: pd.DataFrame, fecha_recepcion: date) -> str:
    mes = int(fecha_recepcion.month)
    prefijo = f"OP-2026-{mes:03d}-"
    if df is None or df.empty or "codigo_op" not in df.columns:
        return prefijo + "001"
    existentes = df["codigo_op"].dropna().astype(str)
    nums = []
    for code in existentes:
        if code.startswith(prefijo):
            try:
                nums.append(int(code.split("-")[-1]))
            except ValueError:
                pass
    return f"{prefijo}{(max(nums) + 1 if nums else 1):03d}"


def puntaje_prioridad(fecha_prometida=None, materiales="No", estado_pago="Pendiente", diseno="No", complejidad="Media", merma="Dentro", tipo_cliente="Normal", hoy=None) -> tuple[int, str, str]:
    hoy = pd.to_datetime(hoy or date.today()).normalize()
    puntos = 0
    # Fecha y hora de entrega: max 30
    try:
        fp = pd.to_datetime(fecha_prometida).normalize()
        dias = (fp - hoy).days
        if dias <= 0:
            puntos += 30
        elif dias <= 2:
            puntos += 20
        elif dias <= 7:
            puntos += 10
    except Exception:
        dias = None
    # Materiales: max 20
    mat = str(materiales).lower()
    if "sí" in mat or "si" == mat.strip() or "completo" in mat:
        puntos += 20
    elif "parcial" in mat or "crit" in mat or "ddmrp" in mat or "repos" in mat:
        puntos += 10
    # Pago: max 15
    pago = str(estado_pago).lower()
    if "pagado" in pago:
        puntos += 15
    elif "adelanto" in pago or "anticipo" in pago:
        puntos += 10
    # Diseño: max 15
    dis = str(diseno).lower()
    if "sí" in dis or "si" == dis.strip() or "valid" in dis or "aprob" in dis:
        puntos += 15
    elif "observ" in dis:
        puntos += 5
    # Complejidad: max 10
    comp = str(complejidad).lower()
    if "baja" in comp:
        puntos += 10
    elif "media" in comp:
        puntos += 6
    elif "alta" in comp:
        puntos += 3
    # Merma: max 5
    me = str(merma).lower()
    if "dentro" in me or "estandar" in me or "estándar" in me:
        puntos += 5
    elif "ligera" in me:
        puntos += 2
    # Cliente: max 5
    cli = str(tipo_cliente).lower()
    if "sensible" in cli or "urgente" in cli or "vip" in cli:
        puntos += 5
    elif "frecuente" in cli:
        puntos += 3
    else:
        puntos += 1

    # estados especiales antes del rango simple
    if not ("sí" in mat or mat.strip() in {"si", "completo"}) and not ("oc" in mat or "ddmrp" in mat or "repos" in mat):
        prioridad = "Bloqueado materiales"
        accion = "Bloquear hasta liberar materiales o activar OC"
    elif "pendiente" in pago:
        prioridad = "Bloqueado pago"
        accion = "Revisar pago antes de programar"
    elif not ("sí" in dis or dis.strip() == "si" or "valid" in dis or "aprob" in dis) and "observ" not in dis:
        prioridad = "Bloqueado diseño"
        accion = "Validar diseño antes de programar"
    elif "ddmrp" in mat or "repos" in mat or "crit" in mat:
        prioridad = "Alta-DDMRP"
        accion = "Activar/seguir OC DDMRP-SRM y liberar materiales"
    elif puntos >= 80:
        prioridad = "Alta"
        accion = "Programar primero"
    elif puntos >= 60:
        prioridad = "Media"
        accion = "Programar según capacidad"
    elif puntos >= 40:
        prioridad = "Baja"
        accion = "Programar si queda capacidad"
    else:
        prioridad = "Observado"
        accion = "Completar datos críticos antes de liberar"
    return int(min(puntos, 100)), prioridad, accion


def criticidad(row: dict | pd.Series) -> tuple[str, str, str]:
    data = row.to_dict() if hasattr(row, "to_dict") else row
    estado = normalizar_estado_kanban(data.get("estado_kanban"))
    prioridad = str(data.get("prioridad", "")).lower()
    resultado = str(data.get("resultado", "")).lower()
    stock = str(data.get("stock_critico", "")).lower()
    oc = str(data.get("oc_activada", "")).lower()
    cumple = str(data.get("cumple_programa", "")).lower()
    if estado in {"BLOQUEADO", "OBSERVADO"} or "retras" in resultado or cumple in {"no", "0", "false"}:
        return "critico", "Crítico", "🔴"
    if "ddmrp" in prioridad or "repos" in stock or "crit" in stock or "sí" in oc or oc == "si":
        return "ddmrp", "Stock/DDMRP", "🟣"
    if "alta" in prioridad:
        return "alta", "Alta", "🟠"
    if "media" in prioridad:
        return "media", "Media", "🟡"
    if "baja" in prioridad:
        return "baja", "Baja", "🔵"
    return "controlado", "Controlado", "🟢"


def semaforo_cumplimiento(valor_pct: float) -> tuple[str, str, str]:
    try:
        v = float(valor_pct)
    except Exception:
        v = 0.0
    if v >= ESTANDAR:
        return "verde", "Verde", "Mantener procedimiento estándar y auditar trazabilidad."
    if v >= 75:
        return "amarillo", "Amarillo", "Revisar programación, WIP y pedidos bloqueados."
    return "rojo", "Rojo", "Activar plan de acción inmediato."


def kpis(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"total": 0, "programados": 0, "cumplidos": 0, "retrasados": 0, "cumplimiento": 0.0, "incumplimiento": 0.0}
    data = df.copy()
    programados = len(data[data["fecha_programada"].notna()]) if "fecha_programada" in data.columns else len(data)
    cumplidos = int((data.get("cumple_programa", pd.Series(dtype=str)).astype(str).str.lower().isin(["sí", "si", "1", "true"]).sum()))
    retrasados = max(programados - cumplidos, 0)
    cumplimiento = (cumplidos / programados * 100) if programados else 0.0
    return {
        "total": len(data),
        "programados": int(programados),
        "cumplidos": int(cumplidos),
        "retrasados": int(retrasados),
        "cumplimiento": cumplimiento,
        "incumplimiento": 100 - cumplimiento if programados else 0.0,
        "bloqueados": int((data.get("estado_kanban", pd.Series(dtype=str)).astype(str).str.upper().eq("BLOQUEADO").sum())),
        "observados": int((data.get("estado_kanban", pd.Series(dtype=str)).astype(str).str.upper().eq("OBSERVADO").sum())),
        "stock_critico": int((data.get("stock_critico", pd.Series(dtype=str)).astype(str).str.lower().str.contains("ddmrp|repos|crit", regex=True) | data.get("oc_activada", pd.Series(dtype=str)).astype(str).str.lower().str.contains("sí|si", regex=True)).sum()),
        "oc_activada": int(data.get("oc_activada", pd.Series(dtype=str)).astype(str).str.lower().str.contains("sí|si", regex=True).sum()),
        "importe": float(pd.to_numeric(data.get("importe_estimado", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
    }
