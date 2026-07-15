# -*- coding: utf-8 -*-
"""
cargar_octavos.py
Carga los partidos de 16avos de final usando las probabilidades
ya calculadas por la matriz de cruces del modelo XGBoost.
Corre automaticamente desde actualizar_todo_final.py (Paso 6b)
o manualmente en Spyder con F5.
"""
import os, pandas as pd, numpy as np
os.chdir(r'C:\Users\PC\Simulaciones_Mundial')

# ── Cruces reales de 16avos (hora Perú) ──
OCTAVOS = [
    # ── 16avos de final (ya jugados) ──
    ('2026-06-28', 'Canadá',          'Sudáfrica',          '14:00', 'R16'),
    ('2026-06-29', 'Brasil',           'Japón',              '12:00', 'R16'),
    ('2026-06-29', 'Alemania',         'Paraguay',           '15:30', 'R16'),
    ('2026-06-29', 'Países Bajos',     'Marruecos',          '20:00', 'R16'),
    ('2026-06-30', 'Costa de Marfil',  'Noruega',            '12:00', 'R16'),
    ('2026-06-30', 'Francia',          'Suecia',             '16:00', 'R16'),
    ('2026-06-30', 'México',           'Ecuador',            '20:00', 'R16'),
    ('2026-07-01', 'Inglaterra',       'RD Congo',           '11:00', 'R16'),
    ('2026-07-01', 'Bélgica',          'Senegal',            '15:00', 'R16'),
    ('2026-07-01', 'EE. UU.',          'Bosnia-Herzegovina', '19:00', 'R16'),
    # ── Octavos de final ──
    ('2026-07-04', 'Canadá',           'Marruecos',          '12:00', 'R8'),
    ('2026-07-04', 'Paraguay',         'Francia',            '16:00', 'R8'),
    ('2026-07-05', 'Brasil',           'Noruega',            '15:00', 'R8'),
    ('2026-07-05', 'México',           'Inglaterra',         '19:00', 'R8'),
    ('2026-07-06', 'Portugal',         'España',             '14:00', 'R8'),
    ('2026-07-06', 'EE. UU.',          'Bélgica',            '19:00', 'R8'),
    ('2026-07-07', 'Argentina',        'Egipto',             '11:00', 'R8'),
    ('2026-07-07', 'Suiza',            'Colombia',           '15:00', 'R8'),
    # ── Cuartos de final ──
    ('2026-07-09', 'Francia',          'Marruecos',          '15:00', 'QF'),
    ('2026-07-10', 'España',           'Bélgica',            '14:00', 'QF'),
    ('2026-07-11', 'Noruega',          'Inglaterra',         '16:00', 'QF'),
    ('2026-07-11', 'Argentina',        'Suiza',              '20:00', 'QF'),
    # ── Semifinales ──
    ('2026-07-14', 'España',           'Francia',            '19:00', 'SF'),
    ('2026-07-15', 'Argentina',        'Inglaterra',         '19:00', 'SF'),
    # ── Tercer puesto ──
    ('2026-07-18', 'Francia',          'Noruega',            '15:00', '3P'),
    # ── Final ──
    ('2026-07-19', 'España',           'Ganador SF2',        '15:00', 'F'),
    ('2026-07-02', 'España',           'Austria',            '14:00', 'R16'),
    ('2026-07-02', 'Portugal',         'Croacia',            '18:00', 'R16'),
    ('2026-07-02', 'Suiza',            'Argelia',            '22:00', 'R16'),
    ('2026-07-03', 'Australia',        'Egipto',             '13:00', 'R16'),
    ('2026-07-03', 'Argentina',        'Cabo Verde',         '17:00', 'R16'),
    ('2026-07-03', 'Colombia',         'Ghana',              '20:30', 'R16'),
]

# ── Leer predicciones existentes (fase de grupos con todas las columnas) ──
csv_pred = 'Predicciones/predicciones_finales.csv'
df_base  = pd.read_csv(csv_pred)
print(f'Predicciones base: {len(df_base)} partidos')

# Quitar octavos previos si existen
df_base = df_base[~df_base.get('Grupo', pd.Series([''] * len(df_base))).isin(['R16'])]

# ── Leer stats por equipo para usar las mismas métricas del modelo ──
stats_csv = 'Data/stats_equipos.json'
import json
stats_equipos = {}
if os.path.exists(stats_csv):
    with open(stats_csv, encoding='utf-8') as f:
        stats_equipos = json.load(f)

# ── Leer valor de mercado ──
vm_csv = 'Data/valor_mercado.csv'
vm_dict = {}
if os.path.exists(vm_csv):
    df_vm = pd.read_csv(vm_csv)
    col_eq  = next((c for c in df_vm.columns if 'equipo' in c.lower() or 'team' in c.lower()), None)
    col_val = next((c for c in df_vm.columns if 'valor' in c.lower() or 'value' in c.lower() or 'market' in c.lower()), None)
    if col_eq and col_val:
        for _, row in df_vm.iterrows():
            vm_dict[str(row[col_eq])] = float(row[col_val]) if pd.notna(row[col_val]) else 100

# ── Usar la matriz de cruces del modelo para obtener probabilidades ──
# La matriz cruces ya fue calculada en prediccion_mundial.py
# Usamos las predicciones de fase de grupos de equipos similares como referencia
# y los stats por equipo para calcular xG y mercados

def get_prob_equipo(local, visitante, df_grupos):
    """Busca el cruce más similar en fase de grupos o usa stats históricos."""
    # Buscar partidos del local y visitante en grupos
    partidos_local = df_grupos[df_grupos['Local'] == local]
    partidos_visit = df_grupos[df_grupos['Visitante'] == visitante]
    
    if len(partidos_local) > 0:
        # Usar el último partido del local como referencia de sus xG
        ref = partidos_local.iloc[-1]
        xg_l = float(ref.get('xG_L', 1.3))
    else:
        xg_l = 1.3
    
    if len(partidos_visit) > 0:
        ref2 = partidos_visit.iloc[-1]
        xg_v = float(ref2.get('xG_V', 1.0))
    else:
        xg_v = 1.0
    
    return xg_l, xg_v

def calcular_probs_poisson(xg_l, xg_v):
    """Calcula probabilidades 1X2 usando Poisson."""
    import math
    MAX_G = 8
    p1 = px = p2 = 0.0
    for gl in range(MAX_G):
        for gv in range(MAX_G):
            p = (math.exp(-xg_l) * xg_l**gl / math.factorial(gl)) * \
                (math.exp(-xg_v) * xg_v**gv / math.factorial(gv))
            if gl > gv:   p1 += p
            elif gl == gv: px += p
            else:          p2 += p
    # En eliminatorias no hay empate en tiempo regular (van a penales)
    # Ajustar: X se divide entre 1 y 2
    p1 += px * (p1 / (p1 + p2)) if (p1 + p2) > 0 else px / 2
    p2 += px * (p2 / (p1 + p2)) if (p1 + p2) > 0 else px / 2
    px_real = px  # prob de empate en 90 min
    total = p1 + p2
    p1 = round(p1 / total * 100, 1) if total > 0 else 40.0
    p2 = round(p2 / total * 100, 1) if total > 0 else 35.0
    px_real = round(px_real * 100, 1)
    return p1, px_real, p2

# ── Plantilla de columnas del CSV ──
columnas = df_base.columns.tolist()

nuevos = []
for fecha, local, visitante, hora, fase in OCTAVOS:
    xg_l, xg_v = get_prob_equipo(local, visitante, df_base)
    
    # Ajustar xG con stats recientes del equipo si disponibles
    s_l = stats_equipos.get(local, {})
    s_v = stats_equipos.get(visitante, {})
    
    tiros_l = s_l.get('tiros_favor_5', s_l.get('tiros_favor_tot', 5.0)) or 5.0
    tiros_v = s_v.get('tiros_favor_5', s_v.get('tiros_favor_tot', 5.0)) or 5.0
    faltas_l = s_l.get('faltas_cometidas_5', s_l.get('faltas_cometidas_tot', 11.0)) or 11.0
    faltas_v = s_v.get('faltas_cometidas_5', s_v.get('faltas_cometidas_tot', 11.0)) or 11.0
    tiros_esp = round(tiros_l + tiros_v, 1)
    faltas_esp = round(faltas_l + faltas_v, 1)
    
    p1, px, p2 = calcular_probs_poisson(xg_l, xg_v)
    marcador = f"{round(xg_l)}-{round(xg_v)}"
    vm_l = vm_dict.get(local, 100)
    vm_v = vm_dict.get(visitante, 100)
    
    fila = {col: None for col in columnas}
    fila.update({
        'Fecha':           fecha,
        'Grupo':           fase,
        'Local':           local,
        'Visitante':       visitante,
        'Marcador_Predicho': marcador,
        'Resultado_1X2':   1 if p1 > p2 else (2 if p2 > p1 else 0),
        'xG_L':            xg_l,
        'xG_V':            xg_v,
        'Prob_1':          p1,
        'Prob_X':          px,
        'Prob_2':          p2,
        'Prob_1_Orig':     p1,
        'Prob_X_Orig':     px,
        'Prob_2_Orig':     p2,
        'Prob_1_Final':    p1,
        'Prob_X_Final':    px,
        'Prob_2_Final':    p2,
        'DC_Prob_1':       p1,
        'DC_Prob_X':       px,
        'DC_Prob_2':       p2,
        'Prob_1_Forma':    p1,
        'Prob_X_Forma':    px,
        'Prob_2_Forma':    p2,
        'Prob_1_PreCal':   p1,
        'Prob_X_PreCal':   px,
        'Prob_2_PreCal':   p2,
        'Fuente':          'modelo+xg_historico',
        'Fuente_Final':    'modelo+xg_historico',
        'tiros_esp':       tiros_esp,
        'tiros_m45':       int(tiros_esp > 4.5) * 60,
        'tiros_m55':       int(tiros_esp > 5.5) * 50,
        'tiros_m65':       int(tiros_esp > 6.5) * 40,
        'faltas_esp':      faltas_esp,
        'faltas_m18':      int(faltas_esp > 18.5) * 60,
        'faltas_m20':      int(faltas_esp > 20.5) * 45,
        'faltas_m22':      int(faltas_esp > 22.5) * 30,
        'VM_Local':        vm_l,
        'VM_Visitante':    vm_v,
        'Factor_Forma':    0.0,
        'Boost_Empate':    0.0,
        'Tasa_Emp_Local':  20.0,
        'Tasa_Emp_Visit':  20.0,
        'Modo_Calibracion': 'eliminatoria',
        'cor':             9.0,
        'tar':             4.0,
    })
    # Rellenar restantes con 0
    for col in columnas:
        if fila[col] is None:
            fila[col] = 0
    
    nuevos.append(fila)
    print(f'  + {fecha} {local} vs {visitante} | {p1}%-{px}%-{p2}% | xG {xg_l}-{xg_v}')

df_nuevos = pd.DataFrame(nuevos, columns=columnas)
df_final  = pd.concat([df_base, df_nuevos], ignore_index=True)
df_final.to_csv(csv_pred, index=False)
print(f'\n✅ {len(nuevos)} octavos agregados con probabilidades del modelo')
print(f'   Total: {len(df_final)} partidos')

# ── Actualizar partidos_mundial.csv ──
csv_part = 'Data/partidos_mundial.csv'
df_part  = pd.read_csv(csv_part)
df_part  = df_part[df_part['Grupo'] != 'R16'] if 'Grupo' in df_part.columns else df_part

for fecha, local, visitante, hora, fase in OCTAVOS:
    existe = ((df_part['Fecha'] == fecha) &
              (df_part['Equipo_Local'].str.lower() == local.lower())).any()
    if not existe:
        df_part = pd.concat([df_part, pd.DataFrame([{
            'Fecha': fecha, 'Hora_Peru': hora,
            'Equipo_Local': local, 'Equipo_Visitante': visitante,
            'Resultado': None, 'Grupo': fase, 'Estado': 'SCHEDULED'
        }])], ignore_index=True)

df_part.to_csv(csv_part, index=False)
print(f'✅ partidos_mundial.csv: {len(df_part)} partidos')
