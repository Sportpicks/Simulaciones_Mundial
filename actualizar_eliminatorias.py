# -*- coding: utf-8 -*-
"""
actualizar_eliminatorias.py
Actualiza predicciones_eliminatorias.csv con todas las fases del torneo.
Corre en Spyder con F5 o automaticamente desde el pipeline.
"""
import pandas as pd, os
os.chdir(r'C:\Users\PC\Simulaciones_Mundial')

# ── 16avos de final (ya jugados) ──
DIECISEISAVOS = [
    # Local, Visitante, xG_L, xG_V, Prob1, ProbX, Prob2, Avanza_real
    ('Canadá',          'Sudáfrica',          1.39, 1.78, 39.8, 23.1, 60.2, 'Canadá'),
    ('Brasil',           'Japón',              2.64, 1.31, 68.6, 18.2, 31.4, 'Brasil'),
    ('Alemania',         'Paraguay',           1.63, 0.98, 70.8, 24.7, 29.2, 'Paraguay'),
    ('Países Bajos',     'Marruecos',          1.99, 1.78, 56.0, 21.3, 44.0, 'Marruecos'),
    ('Costa de Marfil',  'Noruega',            1.50, 1.81, 42.2, 22.7, 57.8, 'Noruega'),
    ('Francia',          'Suecia',             2.65, 1.21, 81.9, 16.6, 18.1, 'Francia'),
    ('México',           'Ecuador',            1.37, 0.95, 65.4, 27.4, 34.6, 'México'),
    ('Inglaterra',       'RD Congo',           2.29, 0.93, 83.5, 18.3, 16.5, 'Inglaterra'),
    ('Bélgica',          'Senegal',            1.82, 1.76, 52.3, 22.0, 47.7, 'Bélgica'),
    ('EE. UU.',          'Bosnia-Herzegovina', 1.33, 1.19, 55.7, 26.8, 44.3, 'EE. UU.'),
    ('España',           'Austria',            2.40, 1.37, 74.8, 18.9, 25.2, 'España'),
    ('Portugal',         'Croacia',            2.35, 2.04, 57.6, 19.5, 42.4, 'Portugal'),
    ('Suiza',            'Argelia',            1.69, 2.00, 42.7, 21.4, 57.3, 'Suiza'),
    ('Australia',        'Egipto',             1.12, 1.54, 37.7, 25.4, 62.3, 'Egipto'),
    ('Argentina',        'Cabo Verde',         1.67, 0.90, 74.2, 24.3, 25.8, 'Argentina'),
    ('Colombia',         'Ghana',              1.15, 0.79, 65.3, 30.7, 34.7, 'Colombia'),
]

# ── Octavos de final (en curso) ──
OCTAVOS = [
    # Local, Visitante, xG_L, xG_V, Prob1, ProbX, Prob2
    ('Canadá',    'Marruecos',  1.39, 1.78, 39.8, 23.1, 37.1),
    ('Paraguay',  'Francia',    1.03, 2.24, 20.2, 19.1, 79.8),
    ('Brasil',    'Noruega',    2.64, 1.81, 68.6, 18.2, 31.4),
    ('México',    'Inglaterra', 1.37, 2.27, 28.3, 19.8, 71.7),
    ('Portugal',  'España',     2.35, 1.78, 63.9, 19.7, 36.1),
    ('EE. UU.',   'Bélgica',    1.33, 2.98, 17.0, 14.9, 83.0),
    ('Argentina', 'Egipto',     1.67, 1.54, 54.4, 23.3, 45.6),
    ('Suiza',     'Colombia',   1.69, 1.93, 44.4, 21.7, 55.6),
]

def avanza_modelo(local, visitante, p1, px, p2):
    if p1 > p2: return local
    elif p2 > p1: return visitante
    return f'{local} o {visitante}'

rows = []

# Agregar 16avos
for local, visit, xgl, xgv, p1, px, p2, avanza_real in DIECISEISAVOS:
    marcador = f'{round(xgl)}-{round(xgv)}'
    rows.append({
        'Fase': 'Dieciseisavos', 'Fechas': '28 jun - 3 jul',
        'Local': local, 'Visitante': visit,
        'Marcador_Predicho': marcador, 'Avanza': avanza_real,
        'xG_L': xgl, 'xG_V': xgv,
        'Prob_1': p1, 'Prob_X': px, 'Prob_2': p2,
        'Detalle': 'Resultado real',
    })

# Agregar octavos
for local, visit, xgl, xgv, p1, px, p2 in OCTAVOS:
    marcador = f'{round(xgl)}-{round(xgv)}'
    avanza = avanza_modelo(local, visit, p1, px, p2)
    rows.append({
        'Fase': 'Octavos de final', 'Fechas': '4 jul - 7 jul',
        'Local': local, 'Visitante': visit,
        'Marcador_Predicho': marcador, 'Avanza': avanza,
        'xG_L': xgl, 'xG_V': xgv,
        'Prob_1': p1, 'Prob_X': px, 'Prob_2': p2,
        'Detalle': 'Predicción modelo',
    })

df = pd.DataFrame(rows)
df.to_csv('Predicciones/predicciones_eliminatorias.csv', index=False)
print(f'✅ {len(df)} cruces guardados')
print(f'   - 16avos: {len(DIECISEISAVOS)}')
print(f'   - Octavos: {len(OCTAVOS)}')
print('\n▶ Ahora corre: python generar_web_v6.py')
