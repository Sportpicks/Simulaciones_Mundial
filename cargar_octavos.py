# -*- coding: utf-8 -*-
"""
cargar_octavos.py
Carga los partidos de 16avos de final en el CSV de predicciones.
Corre en Spyder con F5.
"""
import os, pandas as pd
from datetime import datetime, timezone, timedelta

os.chdir(r'C:\Users\PC\Simulaciones_Mundial')

PERU_TZ = timezone(timedelta(hours=-5))

# Partidos de 16avos — hora Perú
OCTAVOS = [
    # Fecha Peru, Local, Visitante, Hora Peru
    ('2026-06-28', 'Canadá',        'Sudáfrica',          '14:00'),
    ('2026-06-29', 'Brasil',         'Japón',              '12:00'),
    ('2026-06-29', 'Alemania',       'Paraguay',           '15:30'),
    ('2026-06-29', 'Países Bajos',   'Marruecos',          '20:00'),
    ('2026-06-30', 'Costa de Marfil','Noruega',            '12:00'),
    ('2026-06-30', 'Francia',        'Suecia',             '16:00'),
    ('2026-06-30', 'México',         'Ecuador',            '20:00'),
    ('2026-07-01', 'Inglaterra',     'RD Congo',           '11:00'),
    ('2026-07-01', 'Bélgica',        'Senegal',            '15:00'),
    ('2026-07-01', 'EE. UU.',        'Bosnia-Herzegovina', '19:00'),
    ('2026-07-02', 'España',         'Austria',            '14:00'),
    ('2026-07-02', 'Portugal',       'Croacia',            '18:00'),
    ('2026-07-02', 'Suiza',          'Argelia',            '22:00'),
    ('2026-07-03', 'Australia',      'Egipto',             '13:00'),
    ('2026-07-03', 'Argentina',      'Cabo Verde',         '17:00'),
    ('2026-07-03', 'Colombia',       'Ghana',              '20:30'),
]

# Leer predicciones existentes
csv_pred = 'Predicciones/predicciones_finales.csv'
df = pd.read_csv(csv_pred)
print(f'Predicciones existentes: {len(df)} partidos')

# Quitar partidos de octavos si ya existen
df = df[~df['Fase'].isin(['ROUND_OF_16'])] if 'Fase' in df.columns else df

# Crear filas para octavos
nuevos = []
for fecha, local, visitante, hora in OCTAVOS:
    # Verificar si ya existe
    existe = ((df['Fecha'] == fecha) & 
              (df['Local'].str.lower() == local.lower())).any() if 'Local' in df.columns else False
    if existe:
        print(f'  Ya existe: {local} vs {visitante}')
        continue
    
    fila = {col: None for col in df.columns}
    fila['Fecha']     = fecha
    fila['Local']     = local
    fila['Visitante'] = visitante
    fila['Fase']      = 'ROUND_OF_16'
    fila['Hora_Peru'] = hora
    # Probabilidades base (50/50 con ligero ajuste por ranking FIFA si disponible)
    fila['Prob_1_Final'] = 40.0
    fila['Prob_X_Final'] = 25.0
    fila['Prob_2_Final'] = 35.0
    fila['xG_L'] = 1.2
    fila['xG_V'] = 1.0
    fila['tiros_esp'] = 7.0
    fila['faltas_esp'] = 22.0
    fila['cor'] = 9.0
    fila['tar'] = 4.0
    nuevos.append(fila)
    print(f'  + {fecha} {local} vs {visitante}')

if nuevos:
    df_nuevos = pd.DataFrame(nuevos)
    df = pd.concat([df, df_nuevos], ignore_index=True)
    df.to_csv(csv_pred, index=False)
    print(f'\n✅ {len(nuevos)} partidos de octavos agregados')
    print(f'   Total predicciones: {len(df)}')
else:
    print('\n✅ Todos los partidos ya estaban cargados')

# También actualizar partidos_mundial.csv
csv_part = 'Data/partidos_mundial.csv'
df_part = pd.read_csv(csv_part)
print(f'\nPartidos existentes: {len(df_part)}')

for fecha, local, visitante, hora in OCTAVOS:
    existe = ((df_part['Fecha'] == fecha) & 
              (df_part['Equipo_Local'].str.lower() == local.lower())).any()
    if not existe:
        nueva_fila = {
            'Fecha': fecha,
            'Hora_Peru': hora,
            'Equipo_Local': local,
            'Equipo_Visitante': visitante,
            'Resultado': None,
            'Grupo': 'R16',
            'Estado': 'SCHEDULED'
        }
        df_part = pd.concat([df_part, pd.DataFrame([nueva_fila])], ignore_index=True)

df_part.to_csv(csv_part, index=False)
print(f'✅ partidos_mundial.csv actualizado: {len(df_part)} partidos')
print('\n▶ Ahora corre: python generador_picks_inteligente.py')
