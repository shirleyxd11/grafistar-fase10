from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.db import importar_mayo_desde_excel
from utils.calculos import kpis

if __name__ == "__main__":
    res = importar_mayo_desde_excel(force=True)
    df = res["df"]
    stats = kpis(df)
    print("Base inicial creada desde Excel.")
    print(f"Registros: {stats['total']}")
    print(f"Cumplidos: {stats['cumplidos']}")
    print(f"Retrasados: {stats['retrasados']}")
    print(f"Cumplimiento: {stats['cumplimiento']:.2f}%")
