import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PARQUET_PATH    = os.path.join(BASE_DIR, "data", "pnp_ifsp_20192024.parquet")
PARQUET_EF_PATH = os.path.join(BASE_DIR, "data", "pnp_eficiencia_ifsp_20192024.parquet")
MODELO_PATH     = os.path.join(BASE_DIR, "data", "Planilha_Modelo.xlsx")
