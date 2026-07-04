# Grafistar · Sistema Digital de Pedidos · Fase 10 · Versión UI Pro

Aplicación web profesional en Python + Streamlit para registrar, programar, priorizar y controlar pedidos de impresión de Grafistar.

## Mejoras de esta versión

- Interfaz más moderna tipo sistema empresarial, no plantilla básica.
- Kanban horizontal con columnas, tarjetas por criticidad, WIP y vista **Activos y alertas**.
- Tablas coloreadas por estado, pago, materiales, diseño, stock, prioridad y resultado.
- Exportación a Excel con colores, filtros, tabla estructurada, leyenda y comparativa.
- Carga de Excel más cuidada: usa el estado operativo real del pedido y evita duplicados.
- Registro de junio a diciembre 2026 desde la web con SQLite como base principal.

## Instalación fácil en Windows

1. Extrae el ZIP.
2. Entra a la carpeta del proyecto.
3. Doble clic en `INICIAR_APP.bat`.
4. Espera que instale las librerías.
5. Se abrirá Streamlit. Si no abre, entra a `http://localhost:8501`.

Si aparece un error con Python, prueba `INICIAR_APP_DIRECTO.bat`. Si Windows aún no lo detecta, reinstala Python y marca **Add python.exe to PATH**.

## Comandos manuales

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Si tu Windows usa el lanzador `py`:

```bash
py -3 -m pip install -r requirements.txt
py -3 -m streamlit run app.py
```

## Qué hace

- Importa mayo 2026 desde el Excel `TO-BE_INDICADOR_1.xlsx` como histórico To-Be.
- Registra pedidos nuevos de junio a diciembre 2026 desde la web.
- Guarda todo en SQLite: `database/pedidos.db`.
- Actualiza automáticamente base maestra, prioridad, programación, Kanban, trazabilidad y dashboard.
- Muestra semáforos, WIP, criticidad y alertas de actuación.
- Exporta reportes a Excel sin usar Excel como medio principal de registro.

## Datos de control validados

La base histórica de mayo queda cargada así:

- Programados: 126
- Cumplidos: 117
- Retrasados: 9
- Cumplimiento To-Be: 92.86%
- As-Is: 56.78%
- Estándar: 91.28%

## Uso sugerido para exposición

1. Mostrar Inicio: problema, PDCA y KPIs.
2. Abrir Carga Inicial: explicar que mayo viene del Excel y no se duplica.
3. Registrar un pedido nuevo: demostrar junio–diciembre desde la web.
4. Mostrar Base Maestra: vista coloreada + edición controlada.
5. Mostrar Prioridad: explicar puntaje y decisión operativa.
6. Mostrar Programación: evitar domingos/feriados y controlar capacidad.
7. Mostrar Kanban: usar vista Activos y alertas para explicar criticidad y WIP.
8. Mostrar Dashboard: comparar As-Is, To-Be y estándar.
9. Mostrar Procedimiento: cierre de Fase 10 Verificar / Actuar.

## Estructura

```text
app.py
requirements.txt
requirements_minimo.txt
INICIAR_APP.bat
INICIAR_APP_DIRECTO.bat
REINICIAR_BASE_MAYO.bat
assets/
  grafistar_logo.png
  styles.css
data/
  excel_inicial/TO-BE_INDICADOR_1.xlsx
  exports/
database/
  pedidos.db
utils/
  calculos.py
  db.py
  excel_loader.py
  exportador.py
  ui.py
scripts/
  init_db.py
```
