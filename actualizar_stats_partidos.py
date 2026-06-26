# -*- coding: utf-8 -*-
"""
actualizar_stats_partidos.py
Descarga stats completas de partidos del Mundial 2026 desde API-Football
y las agrega al CSV de resultados para auditoría de props.

Stats descargadas por partido:
  - Tiros a puerta (local + visitante)
  - Tiros totales
  - Faltas cometidas (local + visitante)
  - Córners (local + visitante)
  - Tarjetas amarillas/rojas

Uso: python actualizar_stats_partidos.py
"""

import os, sys, json, requests, time
import pandas as pd
from datetime import datetime, timezone, timedelta

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

API_KEY   = "2ef79c28645eb3c1041bd8768da83e65"
API_URL   = "https://v3.football.api-sports.io"
WC_ID     = 1  # FIFA World Cup 2026
WC_SEASON = 2026

RESULTADOS_CSV = os.path.join(RAIZ, 'Data', 'resultados_mundial.csv')

PERU_TZ = timezone(timedelta(hours=-5))

HEADERS = {
    "x-apisports-key": API_KEY,
    "x-apisports-host": "v3.football.api-sports.io"
}


def api_get(endpoint, params=None):
    """Llamada a la API con manejo de errores y rate limiting."""
    try:
        r = requests.get(f"{API_URL}/{endpoint}", headers=HEADERS,
                         params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        print(f"   ⚠️ API error {r.status_code}: {r.text[:100]}")
        return None
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return None


def buscar_fixture_id(local, visitante, fecha, fixtures_df=None):
    """Busca el fixture_id del partido en la API."""
    # Normalizar nombres para buscar
    params = {
        "league": WC_ID,
        "season": WC_SEASON,
        "date": fecha,
    }
    data = api_get("fixtures", params)
    if not data or not data.get('response'):
        return None

    for fix in data['response']:
        home = fix['teams']['home']['name'].lower()
        away = fix['teams']['away']['name'].lower()
        loc_lower = local.lower()
        vis_lower = visitante.lower()
        # Match flexible
        if (loc_lower[:4] in home or home[:4] in loc_lower) and \
           (vis_lower[:4] in away or away[:4] in vis_lower):
            return fix['fixture']['id']
    return None


def obtener_stats_fixture(fixture_id):
    """Descarga las estadísticas de un partido por su fixture_id."""
    data = api_get("fixtures/statistics", {"fixture": fixture_id})
    if not data or not data.get('response'):
        return None

    stats = {}
    for team_data in data['response']:
        lado = 'local' if team_data.get('team', {}).get('id') else 'visitante'
        # Determinar si es local o visitante por posición en lista
        idx = data['response'].index(team_data)
        prefijo = 'L' if idx == 0 else 'V'

        for stat in team_data.get('statistics', []):
            tipo = stat['type']
            valor = stat['value']
            if valor is None:
                valor = 0
            try:
                valor = float(valor)
            except:
                valor = 0

            if tipo == 'Shots on Goal':
                stats[f'Tiros_Puerta_{prefijo}'] = int(valor)
            elif tipo == 'Total Shots':
                stats[f'Tiros_Total_{prefijo}'] = int(valor)
            elif tipo == 'Fouls':
                stats[f'Faltas_{prefijo}'] = int(valor)
            elif tipo == 'Corner Kicks':
                stats[f'Corners_{prefijo}'] = int(valor)
            elif tipo == 'Yellow Cards':
                stats[f'Amarillas_{prefijo}'] = int(valor)
            elif tipo == 'Red Cards':
                stats[f'Rojas_{prefijo}'] = int(valor)
            elif tipo == 'Ball Possession':
                try:
                    stats[f'Posesion_{prefijo}'] = float(str(valor).replace('%',''))
                except:
                    pass

    # Calcular totales
    if 'Tiros_Puerta_L' in stats and 'Tiros_Puerta_V' in stats:
        stats['Tiros_Puerta_Total'] = stats['Tiros_Puerta_L'] + stats['Tiros_Puerta_V']
    if 'Tiros_Total_L' in stats and 'Tiros_Total_V' in stats:
        stats['Tiros_Total_Total'] = stats['Tiros_Total_L'] + stats['Tiros_Total_V']
    if 'Faltas_L' in stats and 'Faltas_V' in stats:
        stats['Faltas_Total'] = stats['Faltas_L'] + stats['Faltas_V']
    if 'Corners_L' in stats and 'Corners_V' in stats:
        stats['Corners_Total'] = stats['Corners_L'] + stats['Corners_V']
    if 'Amarillas_L' in stats and 'Amarillas_V' in stats:
        stats['Tarjetas_Total'] = stats['Amarillas_L'] + stats['Amarillas_V'] + \
                                   stats.get('Rojas_L', 0) + stats.get('Rojas_V', 0)

    return stats


def actualizar_stats_csv():
    """Proceso principal: actualiza el CSV con stats de partidos finalizados."""
    print("\n📊 ACTUALIZADOR DE STATS — MUNDIAL 2026")
    print("=" * 50)
    print(f"   API-Football: {API_URL}")

    if not os.path.exists(RESULTADOS_CSV):
        print("   ❌ No se encontró resultados_mundial.csv")
        return

    df = pd.read_csv(RESULTADOS_CSV)

    # Agregar columnas de stats si no existen
    cols_stats = [
        'Fixture_ID',
        'Tiros_Puerta_L', 'Tiros_Puerta_V', 'Tiros_Puerta_Total',
        'Tiros_Total_L', 'Tiros_Total_V', 'Tiros_Total_Total',
        'Faltas_L', 'Faltas_V', 'Faltas_Total',
        'Corners_L', 'Corners_V', 'Corners_Total',
        'Amarillas_L', 'Amarillas_V', 'Tarjetas_Total',
    ]
    for col in cols_stats:
        if col not in df.columns:
            df[col] = None

    # Filtrar partidos finalizados sin stats
    terminados = df[df['Estado'] == 'FINISHED'].copy()
    sin_stats  = terminados[terminados['Tiros_Puerta_Total'].isna() |
                             (terminados['Tiros_Puerta_Total'] == 0)]

    print(f"   Partidos finalizados: {len(terminados)}")
    print(f"   Sin stats: {len(sin_stats)}")

    if sin_stats.empty:
        print("   ✅ Todos los partidos ya tienen stats")
        return df

    # Verificar requests disponibles
    status = api_get("status")
    if status and status.get('response'):
        requests_hoy = status['response'].get('requests', {})
        used = requests_hoy.get('current', 0)
        limit = requests_hoy.get('limit_day', 100)
        print(f"   API requests: {used}/{limit} usadas hoy")
        disponibles = limit - used
        if disponibles < 5:
            print("   ⚠️ Pocas requests disponibles — procesando solo las más recientes")
            sin_stats = sin_stats.tail(min(disponibles//2, 5))

    actualizados = 0
    errores = 0

    for idx, row in sin_stats.iterrows():
        local    = row['Local']
        visitante = row['Visitante']
        fecha    = row['Fecha']

        print(f"   📡 {local} vs {visitante} ({fecha})...")

        # Buscar fixture_id si no lo tenemos
        fixture_id = row.get('Fixture_ID')
        if pd.isna(fixture_id) or fixture_id == 0:
            # Intentar desde el ID_Partido que ya tenemos
            fixture_id = row.get('ID_Partido')

        if pd.isna(fixture_id) or not fixture_id:
            fixture_id = buscar_fixture_id(local, visitante, fecha)
            time.sleep(0.5)

        if not fixture_id:
            print(f"      ⚠️ No se encontró fixture_id")
            errores += 1
            continue

        # Obtener stats
        stats = obtener_stats_fixture(int(fixture_id))
        time.sleep(0.3)  # Rate limiting

        if not stats:
            print(f"      ⚠️ Sin stats disponibles")
            errores += 1
            continue

        # Actualizar fila
        df.at[idx, 'Fixture_ID'] = int(fixture_id)
        for col, val in stats.items():
            if col in df.columns:
                df.at[idx, col] = val

        tiros = stats.get('Tiros_Puerta_Total', '?')
        faltas = stats.get('Faltas_Total', '?')
        corners = stats.get('Corners_Total', '?')
        print(f"      ✅ Tiros puerta: {tiros} | Faltas: {faltas} | Córners: {corners}")
        actualizados += 1

    # Guardar CSV actualizado
    df.to_csv(RESULTADOS_CSV, index=False)
    print(f"\n✅ CSV actualizado: {actualizados} partidos con stats, {errores} errores")
    print(f"   Guardado en: {RESULTADOS_CSV}")
    return df


if __name__ == '__main__':
    actualizar_stats_csv()
