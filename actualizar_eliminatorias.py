# -*- coding: utf-8 -*-
"""
actualizar_eliminatorias.py
Reemplaza los cruces SIMULADOS con los cruces REALES de 16avos.
Corre en Spyder con F5.
"""
import pandas as pd, os
os.chdir(r'C:\Users\PC\Simulaciones_Mundial')

# Leer predicciones_finales.csv que ya tiene los octavos con probabilidades reales
csv_pred = 'Predicciones/predicciones_finales.csv'
df = pd.read_csv(csv_pred)

# Filtrar solo los octavos
octavos = df[df['Grupo'] == 'R16'].copy()
print(f'Octavos en predicciones_finales: {len(octavos)}')

if len(octavos) == 0:
    print('ERROR: No hay octavos en predicciones_finales.csv')
    print('Corre primero cargar_octavos.py')
else:
    # Construir predicciones_eliminatorias.csv con los cruces reales
    rows = []
    for _, row in octavos.iterrows():
        local     = row['Local']
        visitante = row['Visitante']
        p1  = float(row.get('Prob_1_Final', row.get('Prob_1', 40)))
        px  = float(row.get('Prob_X_Final', row.get('Prob_X', 25)))
        p2  = float(row.get('Prob_2_Final', row.get('Prob_2', 35)))
        xgl = float(row.get('xG_L', 1.2))
        xgv = float(row.get('xG_V', 1.0))
        avanza = local if p1 > p2 else (visitante if p2 > p1 else f'{local} o {visitante}')
        marcador = f"{round(xgl)}-{round(xgv)}"

        rows.append({
            'Fase':              'Dieciseisavos',
            'Fechas':            '28 jun - 3 jul',
            'Local':             local,
            'Visitante':         visitante,
            'Marcador_Predicho': marcador,
            'Avanza':            avanza,
            'xG_L':              xgl,
            'xG_V':              xgv,
            'Prob_1':            p1,
            'Prob_X':            px,
            'Prob_2':            p2,
            'Detalle':           'Tiempo regular',
        })
        print(f'  {local} vs {visitante} | {p1}%-{px}%-{p2}% → {avanza}')

    df_elim = pd.DataFrame(rows)
    df_elim.to_csv('Predicciones/predicciones_eliminatorias.csv', index=False)
    print(f'\n✅ {len(rows)} cruces reales guardados en predicciones_eliminatorias.csv')
    print('\n▶ Ahora corre: python generar_web_v6.py')
