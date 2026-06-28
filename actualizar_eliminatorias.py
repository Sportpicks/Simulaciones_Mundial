# -*- coding: utf-8 -*-
"""
Created on Sun Jun 28 01:26:24 2026

@author: PC
"""

# -*- coding: utf-8 -*-
"""
actualizar_eliminatorias.py
Reemplaza los cruces simulados con los cruces REALES de 16avos.
Corre en Spyder con F5.
"""
import pandas as pd, os
os.chdir(r'C:\Users\PC\Simulaciones_Mundial')

# Cruces REALES de 16avos — hora Perú
CRUCES_REALES = [
    # Local, Visitante, xG_L, xG_V, Prob1, ProbX, Prob2
    ('Canadá',          'Sudáfrica',          1.4, 1.1, 42.0, 30.0, 28.0),
    ('Brasil',          'Japón',              1.8, 0.9, 52.0, 28.0, 20.0),
    ('Alemania',        'Paraguay',           2.0, 0.8, 58.0, 25.0, 17.0),
    ('Países Bajos',    'Marruecos',          1.7, 1.0, 50.0, 28.0, 22.0),
    ('Costa de Marfil', 'Noruega',            1.3, 1.3, 35.0, 32.0, 33.0),
    ('Francia',         'Suecia',             2.0, 0.9, 55.0, 27.0, 18.0),
    ('México',          'Ecuador',            1.5, 1.2, 42.0, 30.0, 28.0),
    ('Inglaterra',      'RD Congo',           2.1, 0.7, 60.0, 25.0, 15.0),
    ('Bélgica',         'Senegal',            1.8, 1.0, 50.0, 28.0, 22.0),
    ('EE. UU.',         'Bosnia-Herzegovina', 1.5, 1.1, 43.0, 30.0, 27.0),
    ('España',          'Austria',            1.9, 1.0, 52.0, 28.0, 20.0),
    ('Portugal',        'Croacia',            1.8, 1.1, 48.0, 29.0, 23.0),
    ('Suiza',           'Argelia',            1.5, 1.2, 42.0, 30.0, 28.0),
    ('Australia',       'Egipto',             1.4, 1.1, 40.0, 31.0, 29.0),
    ('Argentina',       'Cabo Verde',         2.3, 0.6, 65.0, 22.0, 13.0),
    ('Colombia',        'Ghana',              1.6, 1.0, 46.0, 29.0, 25.0),
]

# Determinar quién avanza (favorito por prob)
def avanza(local, visitante, p1, px, p2):
    if p1 > p2: return local
    elif p2 > p1: return visitante
    else: return f'{local} o {visitante}'

rows = []
for local, visitante, xgl, xgv, p1, px, p2 in CRUCES_REALES:
    rows.append({
        'Fase': 'Dieciseisavos',
        'Fechas': '28 jun - 3 jul',
        'Local': local,
        'Visitante': visitante,
        'Marcador_Predicho': f'{round(xgl)}-{round(xgv)}',
        'Avanza': avanza(local, visitante, p1, px, p2),
        'xG_L': xgl,
        'xG_V': xgv,
        'Prob_1': p1,
        'Prob_X': px,
        'Prob_2': p2,
        'Detalle': 'Tiempo regular',
    })

df = pd.DataFrame(rows)
df.to_csv('Predicciones/predicciones_eliminatorias.csv', index=False)
print(f'✅ {len(df)} cruces reales guardados')
print(df[['Local','Visitante','Prob_1','Prob_X','Prob_2']].to_string())
print('\n▶ Ahora corre: python generar_web_v6.py')