# -*- coding: utf-8 -*-
"""
actualizar_fechas_peru.py
Actualiza las fechas del CSV de predicciones usando hora Peru (UTC-5)
para que la web muestre correctamente los partidos del dia en Peru.

Uso: python actualizar_fechas_peru.py
"""
import pandas as pd
import os

RAIZ = os.path.dirname(os.path.abspath(__file__))

# Cargar fechas en hora Peru (ya corregidas por corregir_fechas_peru.py)
df_mun = pd.read_csv(os.path.join(RAIZ, 'Data', 'partidos_mundial.csv'))

# Crear mapa: (local, visitante) -> fecha hora Peru
mapa = {}
for _, r in df_mun.iterrows():
    mapa[(r['Equipo_Local'], r['Equipo_Visitante'])] = r['Fecha']

# Actualizar predicciones_finales.csv
csv_pred = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
df_pred = pd.read_csv(csv_pred)

actualizados = 0
for i, r in df_pred.iterrows():
    clave = (r['Local'], r['Visitante'])
    if clave in mapa:
        df_pred.at[i, 'Fecha'] = mapa[clave]
        actualizados += 1

df_pred.to_csv(csv_pred, index=False, encoding='utf-8-sig')
print(f'✅ Fechas actualizadas: {actualizados} partidos')

# Mostrar partidos del dia de hoy
from datetime import date
hoy = date.today().strftime('%Y-%m-%d')
hoy_df = df_pred[df_pred['Fecha'] == hoy][['Fecha','Local','Visitante']]
print(f'\n📅 Partidos de hoy ({hoy}) en hora Peru:')
if len(hoy_df) > 0:
    for _, r in hoy_df.iterrows():
        print(f'   {r["Local"]} vs {r["Visitante"]}')
else:
    print('   Ninguno encontrado')
