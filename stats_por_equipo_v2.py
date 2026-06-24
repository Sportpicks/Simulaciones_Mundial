# -*- coding: utf-8 -*-
"""
stats_por_equipo_v2.py
Versión ampliada — calcula estadísticas por equipo incluyendo
mercados avanzados: paradas, grandes ocasiones, remates totales,
saques de banda, centros, toques en área, xGOT, goles cabeza.

Uso: python stats_por_equipo_v2.py
"""

import os, json
import pandas as pd

RAIZ     = os.path.dirname(os.path.abspath(__file__))
CSV_PART = os.path.join(RAIZ, 'Data', 'partidos.csv')
JSON_OUT = os.path.join(RAIZ, 'Data', 'stats_equipos.json')

def stats_equipo(df, equipo):
    local = df[df['Equipo_Local'] == equipo].copy()
    visit = df[df['Equipo_Visitante'] == equipo].copy()

    def col_l(c): return c + '_Local'
    def col_v(c): return c + '_Visitante'

    MAPA = {
        # (nombre_stat, col_local_como_local, col_local_como_visitante)
        'tiros_favor'      : ('Remates_a_puerta_Local',        'Remates_a_puerta_Visitante'),
        'tiros_contra'     : ('Remates_a_puerta_Visitante',    'Remates_a_puerta_Local'),
        'remates_tot_favor': ('Remates_totales_Local',         'Remates_totales_Visitante'),
        'remates_fuera'    : ('Remates_fuera_Local',           'Remates_fuera_Visitante'),
        'remates_area'     : ('Remates_dentro_del_área_Local', 'Remates_dentro_del_área_Visitante'),
        'corners_favor'    : ('Córneres_Local',                'Córneres_Visitante'),
        'corners_contra'   : ('Córneres_Visitante',            'Córneres_Local'),
        'faltas_cometidas' : ('Faltas_Local',                  'Faltas_Visitante'),
        'faltas_recibidas' : ('Faltas_Visitante',              'Faltas_Local'),
        'paradas'          : ('Paradas_Local',                 'Paradas_Visitante'),
        'paradas_rival'    : ('Paradas_Visitante',             'Paradas_Local'),
        'grandes_ocas'     : ('Grandes_ocasiones_Local',       'Grandes_ocasiones_Visitante'),
        'saques_banda'     : ('Saques_de_banda_Local',         'Saques_de_banda_Visitante'),
        'centros'          : ('Centros_Local',                 'Centros_Visitante'),
        'toques_area'      : ('Toques_en_el_área_rival_Local', 'Toques_en_el_área_rival_Visitante'),
        'xg_favor'         : ('Goles_esperados_(xG)_Local',    'Goles_esperados_(xG)_Visitante'),
        'xg_contra'        : ('Goles_esperados_(xG)_Visitante','Goles_esperados_(xG)_Local'),
        'xgot_favor'       : ('xG_a_puerta_(xGOT)_Local',     'xG_a_puerta_(xGOT)_Visitante'),
        'goles_cabeza'     : ('Goles_de_cabeza_Local',         'Goles_de_cabeza_Visitante'),
        'al_palo'          : ('Al_palo_Local',                 'Al_palo_Visitante'),
        'fueras_juego'     : ('Fueras_de_juego_Local',         'Fueras_de_juego_Visitante'),
        'entradas'         : ('Entradas_Local',                'Entradas_Visitante'),
    }

    frames = []
    for stat, (col_cuando_local, col_cuando_visit) in MAPA.items():
        vals = []
        if col_cuando_local in local.columns:
            vals.extend(local[col_cuando_local].dropna().tolist())
        if col_cuando_visit in visit.columns:
            vals.extend(visit[col_cuando_visit].dropna().tolist())
        if vals:
            s = pd.to_numeric(pd.Series(vals), errors='coerce').dropna()
            if len(s) > 0:
                frames.append({'stat': stat, 'vals': s})

    if not frames:
        return None

    n_total = len(local) + len(visit)
    result  = {'partidos': n_total}

    for item in frames:
        s    = item['vals']
        stat = item['stat']
        n5   = min(5, len(s))
        result[f'{stat}_5']   = round(float(s.tail(n5).mean()), 2) if n5 > 0 else 0
        result[f'{stat}_tot'] = round(float(s.mean()), 2) if len(s) > 0 else 0

    # Goles (desde resultado)
    goles = []
    if 'Resultado' in local.columns:
        for res in local['Resultado'].dropna():
            try:
                g = int(str(res).split('-')[0].strip())
                goles.append(g)
            except: pass
    if 'Resultado' in visit.columns:
        for res in visit['Resultado'].dropna():
            try:
                g = int(str(res).split('-')[1].strip())
                goles.append(g)
            except: pass
    if goles:
        s = pd.Series(goles)
        result['goles_5']   = round(float(s.tail(5).mean()), 2)
        result['goles_tot'] = round(float(s.mean()), 2)

    return result

def main():
    print("\n🚀 STATS POR EQUIPO v2 — Mercados ampliados")
    print("="*55)

    df = pd.read_csv(CSV_PART)
    print(f"✅ Partidos: {len(df)}")

    equipos = sorted(set(
        df['Equipo_Local'].dropna().tolist() +
        df['Equipo_Visitante'].dropna().tolist()
    ))

    resultado  = {}
    sin_datos  = []

    for eq in equipos:
        s = stats_equipo(df, eq)
        if s:
            resultado[eq] = s
        else:
            sin_datos.append(eq)

    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"✅ Stats calculadas: {len(resultado)} equipos")
    if sin_datos:
        print(f"⚠️  Sin datos: {sin_datos}")

    # Ejemplo Portugal
    if 'Portugal' in resultado:
        s = resultado['Portugal']
        print(f"\n📊 Portugal ({s['partidos']} partidos):")
        metricas = [
            ('tiros_favor',       'Tiros a puerta'),
            ('remates_tot_favor', 'Remates totales'),
            ('corners_favor',     'Córners'),
            ('paradas',           'Paradas propias'),
            ('grandes_ocas',      'Grandes ocasiones'),
            ('saques_banda',      'Saques de banda'),
            ('centros',           'Centros'),
            ('toques_area',       'Toques área rival'),
            ('xg_favor',          'xG favor'),
            ('xgot_favor',        'xGOT favor'),
            ('goles_5',           'Goles (últ.5)'),
            ('al_palo',           'Al palo'),
        ]
        for key, nombre in metricas:
            v5  = s.get(f'{key}_5',  s.get(key, '—'))
            tot = s.get(f'{key}_tot', '—')
            if v5 != '—':
                print(f"   {nombre:<25} últ.5: {v5:>5} | hist: {tot:>5}")

if __name__ == '__main__':
    main()