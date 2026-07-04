from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd
from .db import read_pedidos, read_historial, ROOT
from .calculos import kpis, ASIS, TOBE_MAYO, ESTANDAR


def _excel_col(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _set_format_by_text(ws, first_row, last_row, col_idx, rules):
    col = _excel_col(col_idx)
    rng = f"{col}{first_row}:{col}{last_row}"
    for text, fmt in rules:
        ws.conditional_format(rng, {"type": "text", "criteria": "containing", "value": text, "format": fmt})


def exportar_excel(nombre: str = "reporte_grafistar") -> Path:
    export_dir = ROOT / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"{nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    pedidos = read_pedidos()
    hist = read_historial()
    resumen = pd.DataFrame([kpis(pedidos)])
    comparativa = pd.DataFrame([
        {"Escenario": "As-Is", "Cumplimiento %": ASIS},
        {"Escenario": "To-Be Mayo", "Cumplimiento %": TOBE_MAYO},
        {"Escenario": "Estándar", "Cumplimiento %": ESTANDAR},
        {"Escenario": "Resultado actual", "Cumplimiento %": float(resumen.loc[0, "cumplimiento"]) if not resumen.empty else 0},
    ])

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        pedidos.to_excel(writer, sheet_name="Base Maestra", index=False, startrow=1)
        hist.to_excel(writer, sheet_name="Historial Kanban", index=False, startrow=1)
        resumen.to_excel(writer, sheet_name="Dashboard KPI", index=False, startrow=1)
        comparativa.to_excel(writer, sheet_name="Comparativa", index=False, startrow=1)
        workbook = writer.book

        fmt_title = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#08172D", "font_size": 16, "align": "center", "valign": "vcenter"})
        fmt_header = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#0B1F3A", "border": 1, "align": "center", "valign": "vcenter"})
        fmt_money = workbook.add_format({"num_format": "S/ #,##0.00"})
        fmt_pct = workbook.add_format({"num_format": "0.00%"})
        fmt_green = workbook.add_format({"bg_color": "#DFF7EA", "font_color": "#087450", "bold": True})
        fmt_red = workbook.add_format({"bg_color": "#FFE4E8", "font_color": "#9D1324", "bold": True})
        fmt_yellow = workbook.add_format({"bg_color": "#FFF8DC", "font_color": "#8A5B00", "bold": True})
        fmt_orange = workbook.add_format({"bg_color": "#FFF1DB", "font_color": "#9A4B00", "bold": True})
        fmt_purple = workbook.add_format({"bg_color": "#F0E7FF", "font_color": "#5B21B6", "bold": True})
        fmt_blue = workbook.add_format({"bg_color": "#E7F4FF", "font_color": "#075985", "bold": True})
        fmt_gray = workbook.add_format({"bg_color": "#F2F4F7", "font_color": "#344054", "bold": True})

        for sheet_name, df in [("Base Maestra", pedidos), ("Historial Kanban", hist), ("Dashboard KPI", resumen), ("Comparativa", comparativa)]:
            ws = writer.sheets[sheet_name]
            max_col = max(0, len(df.columns) - 1)
            last_col = _excel_col(max_col)
            ws.merge_range(f"A1:{last_col}1", f"GRAFISTAR · {sheet_name}", fmt_title)
            ws.set_row(0, 25)
            ws.set_row(1, 24, fmt_header)
            ws.freeze_panes(2, 0)
            if sheet_name != "Base Maestra":
                ws.autofilter(1, 0, max(2, len(df) + 1), max_col)
            for idx, col in enumerate(df.columns):
                width = min(max(len(str(col)) + 4, 13), 34)
                if col in {"observacion", "accion_requerida", "motivo"}:
                    width = 38
                if col in {"codigo_op", "cliente", "responsable"}:
                    width = 22
                ws.set_column(idx, idx, width)
            if sheet_name == "Base Maestra" and not df.empty:
                last_row = len(df) + 2
                # Add formal Excel table
                ws.add_table(1, 0, len(df) + 1, len(df.columns) - 1, {
                    "name": "Tabla_Base_Grafistar",
                    "style": "Table Style Medium 2",
                    "columns": [{"header": c} for c in df.columns],
                })
                cols = {c: i for i, c in enumerate(df.columns)}
                if "importe_estimado" in cols:
                    ws.set_column(cols["importe_estimado"], cols["importe_estimado"], 16, fmt_money)
                if "puntaje" in cols:
                    c = _excel_col(cols["puntaje"])
                    ws.conditional_format(f"{c}3:{c}{last_row}", {"type": "data_bar", "bar_color": "#08A8FF"})
                for col_name in ["prioridad", "estado_kanban", "resultado", "estado_pago", "materiales", "diseno_validado", "stock_critico", "oc_activada", "alerta_wip"]:
                    if col_name in cols:
                        _set_format_by_text(ws, 3, last_row, cols[col_name], [
                            ("Bloque", fmt_red), ("Retras", fmt_red), ("Observ", fmt_red), ("Pendiente", fmt_red),
                            ("DDMRP", fmt_purple), ("Repos", fmt_purple), ("crítico", fmt_purple), ("Crit", fmt_purple),
                            ("Alta", fmt_orange), ("Media", fmt_yellow), ("Baja", fmt_blue),
                            ("Entregado", fmt_green), ("A tiempo", fmt_green), ("Pagado", fmt_green), ("Sí", fmt_green), ("Controlado", fmt_green),
                        ])
            if sheet_name == "Comparativa" and not df.empty:
                ws.set_column(0, 0, 24)
                ws.set_column(1, 1, 18)
                chart = workbook.add_chart({"type": "column"})
                chart.add_series({
                    "name": "Cumplimiento %",
                    "categories": "=Comparativa!$A$3:$A$6",
                    "values": "=Comparativa!$B$3:$B$6",
                    "fill": {"color": "#08A8FF"},
                    "data_labels": {"value": True, "num_format": "0.00"},
                })
                chart.set_title({"name": "As-Is vs To-Be vs Estándar"})
                chart.set_y_axis({"name": "% cumplimiento", "min": 0, "max": 100})
                chart.set_legend({"none": True})
                ws.insert_chart("D3", chart, {"x_scale": 1.35, "y_scale": 1.2})
        # Small color legend on Dashboard KPI
        ws = writer.sheets["Dashboard KPI"]
        legend = [
            ("Crítico / bloqueo / retraso", fmt_red), ("DDMRP / stock / OC", fmt_purple),
            ("Alta prioridad", fmt_orange), ("Media preventiva", fmt_yellow),
            ("Baja / consulta", fmt_blue), ("Controlado / a tiempo", fmt_green),
        ]
        row = 6
        ws.write(row, 0, "Leyenda de colores", fmt_header)
        for i, (txt, fmt) in enumerate(legend, start=row + 1):
            ws.write(i, 0, txt, fmt)
    return path
