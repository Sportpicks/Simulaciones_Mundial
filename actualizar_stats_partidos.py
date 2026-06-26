# -*- coding: utf-8 -*-
"""
actualizar_stats_partidos.py
Descarga stats completas del Mundial 2026 desde AllSports API
y las agrega al CSV de resultados para auditoría automática de props.

Stats por partido:
  - Tiros a puerta (local + visitante + total)
  - Faltas (local + visitante + total)
  - Córners (local + visitante + total)
  - Tarjetas amarillas/rojas

Uso: python actualizar_stats_partidos.py
"""

import os, sys, json, requests, time
import pandas as pd
from datetime import datetime, timezone, timedelta

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

API_KEY  = "410fe96d3a7185456e7146c6b83720aa96f45071f3a5def83a3adf03a4c21b69"
API_URL  = "https://apiv2.allsportsapi.com/football/"

RESULTADOS_CSV = os.path.join(RAIZ, 'Data', 'resultados_mundial.csv')

# ID de la liga Mundial 2026 en AllSports
# Buscaremos los partidos por fecha y equipos
WC_LEAGUE_ID = 1204  # FIFA World Cup 2026

PERU_TZ = timezone(timedelta(hours=-5))

# Normalización de nombres entre CSV y AllSports
NOMBRES_NORM = {
    'ee. uu.': 'usa', 'estados unidos': 'usa',
    'curaçao': 'curacao', 'curazao': 'curacao',
    'república checa': 'czech republic',
    'corea del sur': 'south korea',
    'países bajos': 'netherlands',
    'rd congo': 'dr congo', 'congo dr': 'dr congo',
    'cabo verde': 'cape verde',
    'arabia saudí': 'saudi arabia',
    'bosnia-herzegovina': 'bosnia and herzegovina',
}

def normalizar(nombre):
    n = str(nombre).lower().strip()
    return NOMBRES_NORM.get(n, n)


def api_get(params):
    """Llamada a AllSports API."""
    try:
        params['APIkey'] = API_KEY
        r = requests.get(API_URL, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        print(f"   ⚠️ HTTP {r.status_code}")
        return None
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return None


def buscar_evento_id(local, visitante, fecha):
    """Busca el evento_id en AllSports por fecha."""
    # AllSports v2: met=Fixtures
    data = api_get({'met': 'Fixtures', 'from': fecha, 'to': fecha,
                    'leagueId': WC_LEAGUE_ID})
    if not data or not data.get('result'):
        data = api_get({'met': 'Fixtures', 'from': fecha, 'to': fecha})
        if not data or not data.get('result'):
            return None

    loc_n = normalizar(local)
    vis_n = normalizar(visitante)

    for ev in data['result']:
        home = normalizar(ev.get('event_home_team', ''))
        away = normalizar(ev.get('event_away_team', ''))
        if (loc_n[:4] in home or home[:4] in loc_n) and \
           (vis_n[:4] in away or away[:4] in vis_n):
            return ev.get('event_key')

    return None


def obtener_stats_evento(evento_id):
    """Descarga las estadísticas de un partido."""
    # AllSports v2: met=Statistics
    data = api_get({'met': 'Statistics', 'matchId': evento_id})
    if not data:
        return None

    # AllSports devuelve lista de stats
    result = data.get('result') or data.get('statistics') or []
    if not result:
        return None

    stats = {}

    for stat in result:
        tipo = str(stat.get('type', stat.get('stat', ''))).lower()
        home_val = stat.get('home', stat.get('home_value', 0)) or 0
        away_val = stat.get('away', stat.get('away_value', 0)) or 0
        try:
            hv = int(str(home_val).replace('%','').strip() or 0)
            av = int(str(away_val).replace('%','').strip() or 0)
        except:
            hv, av = 0, 0

        if 'shot' in tipo and 'target' in tipo:
            stats['Tiros_Puerta_L'] = hv
            stats['Tiros_Puerta_V'] = av
            stats['Tiros_Puerta_Total'] = hv + av
        elif 'shot' in tipo or 'total shot' in tipo:
            if 'Tiros_Total_L' not in stats:
                stats['Tiros_Total_L'] = hv
                stats['Tiros_Total_V'] = av
                stats['Tiros_Total_Total'] = hv + av
        elif 'foul' in tipo:
            stats['Faltas_L'] = hv
            stats['Faltas_V'] = av
            stats['Faltas_Total'] = hv + av
        elif 'corner' in tipo:
            stats['Corners_L'] = hv
            stats['Corners_V'] = av
            stats['Corners_Total'] = hv + av
        elif 'yellow' in tipo:
            stats['Amarillas_L'] = hv
            stats['Amarillas_V'] = av
        elif 'red' in tipo:
            stats['Rojas_L'] = hv
            stats['Rojas_V'] = av

    if 'Amarillas_L' in stats:
        stats['Tarjetas_Total'] = (stats.get('Amarillas_L',0) +
                                    stats.get('Amarillas_V',0) +
                                    stats.get('Rojas_L',0) +
                                    stats.get('Rojas_V',0))
    return stats if stats else None


def actualizar_stats_csv():
    print("\n📊 ACTUALIZADOR DE STATS — MUNDIAL 2026 (AllSports API)")
    print("=" * 55)

    if not os.path.exists(RESULTADOS_CSV):
        print("   ❌ No se encontró resultados_mundial.csv")
        return

    df = pd.read_csv(RESULTADOS_CSV)

    # Agregar columnas si no existen
    cols = ['Evento_ID', 'Tiros_Puerta_L', 'Tiros_Puerta_V', 'Tiros_Puerta_Total',
            'Tiros_Total_L', 'Tiros_Total_V', 'Tiros_Total_Total',
            'Faltas_L', 'Faltas_V', 'Faltas_Total',
            'Corners_L', 'Corners_V', 'Corners_Total',
            'Amarillas_L', 'Amarillas_V', 'Tarjetas_Total']
    for col in cols:
        if col not in df.columns:
            df[col] = None

    # Partidos finalizados sin stats
    terminados = df[df['Estado'] == 'FINISHED'].copy()
    sin_stats = terminados[
        terminados['Tiros_Puerta_Total'].isna() |
        (terminados['Tiros_Puerta_Total'] == 0)
    ]

    print(f"   Finalizados: {len(terminados)} | Sin stats: {len(sin_stats)}")

    if sin_stats.empty:
        print("   ✅ Todos los partidos ya tienen stats")
        df.to_csv(RESULTADOS_CSV, index=False)
        return

    # Procesar los más recientes primero (máx 15 por ejecución)
    sin_stats = sin_stats.sort_values('Fecha', ascending=False).head(15)
    print(f"   Procesando {len(sin_stats)} partidos más recientes...")

    actualizados = 0
    errores = 0

    for idx, row in sin_stats.iterrows():
        local     = row['Local']
        visitante = row['Visitante']
        fecha     = row['Fecha']

        print(f"\n   📡 {local} vs {visitante} ({fecha})")

        # Buscar evento_id
        evento_id = row.get('Evento_ID')
        if pd.isna(evento_id) or not evento_id:
            evento_id = buscar_evento_id(local, visitante, fecha)
            time.sleep(1.5)

        if not evento_id:
            print(f"      ⚠️ No encontrado en AllSports")
            errores += 1
            continue

        df.at[idx, 'Evento_ID'] = evento_id

        # Obtener stats
        stats = obtener_stats_evento(evento_id)
        time.sleep(1.5)

        if not stats:
            print(f"      ⚠️ Sin estadísticas disponibles (evento_id: {evento_id})")
            errores += 1
            continue

        for col, val in stats.items():
            if col in df.columns:
                df.at[idx, col] = val

        print(f"      ✅ Tiros puerta: {stats.get('Tiros_Puerta_Total','?')} | "
              f"Faltas: {stats.get('Faltas_Total','?')} | "
              f"Corners: {stats.get('Corners_Total','?')}")
        actualizados += 1

    df.to_csv(RESULTADOS_CSV, index=False)
    print(f"\n✅ CSV actualizado: {actualizados} con stats, {errores} sin datos")
    print(f"   Guardado: {RESULTADOS_CSV}")

    if actualizados > 0:
        print("\n   ▶ Ahora corre: python registrar_picks_historial.py --audit")


if __name__ == '__main__':
    actualizar_stats_csv()
