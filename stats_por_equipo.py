# -*- coding: utf-8 -*-
"""
stats_por_equipo.py
Calcula estadísticas individuales por equipo usando partidos.csv
y genera Data/stats_equipos.json para usarlo en la web.

Estadísticas calculadas por equipo:
- Tiros a puerta promedio (últimos 5 y total)
- Córners promedio (últimos 5 y total)
- Faltas promedio (últimos 5 y total)
- Remates totales promedio
- Posesión promedio

Uso: python stats_por_equipo.py
"""

import os
import json
import pandas as pd
import numpy as np

RAIZ     = os.path.dirname(os.path.abspath(__file__))
CSV_PART = os.path.join(RAIZ, 'Data', 'partidos.csv')
JSON_OUT = os.path.join(RAIZ, 'Data', 'stats_equipos.json')

def calcular_stats_equipo(df, equipo):
    """Calcula estadísticas de un equipo como local y visitante."""

    # Como local
    local = df[df['Equipo_Local'] == equipo].copy()
    # Como visitante
    visit = df[df['Equipo_Visitante'] == equipo].copy()

    # Unificar columnas
    cols_local = {
        'Remates_a_puerta_Local'    : 'tiros_favor',
        'Remates_a_puerta_Visitante': 'tiros_contra',
        'Remates_totales_Local'     : 'remates_favor',
        'Córneres_Local'            : 'corners_favor',
        'Córneres_Visitante'        : 'corners_contra',
        'Faltas_Local'              : 'faltas_cometidas',
        'Faltas_Visitante'          : 'faltas_recibidas',
    }
    cols_visit = {
        'Remates_a_puerta_Visitante': 'tiros_favor',
        'Remates_a_puerta_Local'    : 'tiros_contra',
        'Remates_totales_Visitante' : 'remates_favor',
        'Córneres_Visitante'        : 'corners_favor',
        'Córneres_Local'            : 'corners_contra',
        'Faltas_Visitante'          : 'faltas_cometidas',
        'Faltas_Local'              : 'faltas_recibidas',
    }

    # Filtrar columnas que existen
    cols_l = {k:v for k,v in cols_local.items() if k in local.columns}
    cols_v = {k:v for k,v in cols_visit.items() if k in visit.columns}

    df_l = local.rename(columns=cols_l)[list(cols_l.values())] if cols_l else pd.DataFrame()
    df_v = visit.rename(columns=cols_v)[list(cols_v.values())] if cols_v else pd.DataFrame()

    todos = pd.concat([df_l, df_v], ignore_index=True)
    todos = todos.apply(pd.to_numeric, errors='coerce')

    if len(todos) == 0:
        return None

    ultimos5 = todos.tail(5)
    historico = todos

    stats = {'partidos': len(todos)}
    for col in todos.columns:
        if col in todos.columns:
            stats[f'{col}_5']   = round(float(ultimos5[col].mean()),  1) if len(ultimos5) > 0 else 0
            stats[f'{col}_tot'] = round(float(historico[col].mean()), 1) if len(historico) > 0 else 0

    return stats

if __name__ == '__main__':
    print("\n🚀 Calculando estadísticas por equipo...")
    print("="*50)

    if not os.path.exists(CSV_PART):
        print(f"❌ No se encontró {CSV_PART}")
        exit(1)

    df = pd.read_csv(CSV_PART)
    print(f"✅ Partidos cargados: {len(df)}")

    # Obtener todos los equipos únicos
    equipos = sorted(set(
        df['Equipo_Local'].dropna().tolist() +
        df['Equipo_Visitante'].dropna().tolist()
    ))
    print(f"✅ Equipos encontrados: {len(equipos)}")

    # Calcular stats por equipo
    resultado = {}
    sin_datos = []

    for eq in equipos:
        stats = calcular_stats_equipo(df, eq)
        if stats:
            resultado[eq] = stats
        else:
            sin_datos.append(eq)

    # Guardar JSON
    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Estadísticas calculadas: {len(resultado)} equipos")
    if sin_datos:
        print(f"⚠️  Sin datos: {sin_datos}")
    print(f"✅ Guardado en: Data/stats_equipos.json")

    # Mostrar ejemplo con Argentina
    if 'Argentina' in resultado:
        s = resultado['Argentina']
        print(f"\n📊 Ejemplo — Argentina ({s['partidos']} partidos):")
        print(f"   Tiros a puerta (últ.5): {s.get('tiros_favor_5',0)} | Histórico: {s.get('tiros_favor_tot',0)}")
        print(f"   Córners (últ.5):        {s.get('corners_favor_5',0)} | Histórico: {s.get('corners_favor_tot',0)}")
        print(f"   Faltas cometidas (últ.5): {s.get('faltas_cometidas_5',0)} | Histórico: {s.get('faltas_cometidas_tot',0)}")
        print(f"   Tiros recibidos (últ.5): {s.get('tiros_contra_5',0)} | Histórico: {s.get('tiros_contra_tot',0)}")
