# -*- coding: utf-8 -*-
"""
obtener_stats_api.py
Obtiene stats reales del Mundial 2026 via API-Football
y las agrega a Data/partidos.csv

Corre en terminal:
    python obtener_stats_api.py

Requiere: pip install requests pandas
"""
import os, json, time
import requests
import pandas as pd

os.chdir(r'C:\Users\PC\Simulaciones_Mundial')

API_KEY = '2ef79c28645eb3c1041bd8768da83e65'
BASE_URL = 'https://v3.football.api-sports.io'
HEADERS = {'x-apisports-key': API_KEY}

# ── Paso 1: Encontrar el ID del Mundial 2026 ──
print("🔍 Buscando ID del Mundial 2026...")
r = requests.get(f'{BASE_URL}/leagues', headers=HEADERS,
                 params={'name': 'FIFA World Cup', 'season': '2026'})
print(f"   Requests restantes: {r.headers.get('x-ratelimit-remaining', '?')}")

leagues = r.json().get('response', [])
league_id = None
for lg in leagues:
    print(f"   Encontrado: {lg['league']['id']} - {lg['league']['name']}")
    if 'World Cup' in lg['league']['name']:
        league_id = lg['league']['id']
        break

if not league_id:
    # Intentar con ID conocido del Mundial
    league_id = 1  # ID FIFA World Cup en API-Football
    print(f"   Usando ID por defecto: {league_id}")

print(f"✅ League ID: {league_id}")
time.sleep(1)

# ── Paso 2: Obtener todos los fixtures del Mundial 2026 ──
print("\n📡 Obteniendo partidos del Mundial 2026...")
r2 = requests.get(f'{BASE_URL}/fixtures', headers=HEADERS,
                  params={'league': league_id, 'season': '2026'})
print(f"   Requests restantes: {r2.headers.get('x-ratelimit-remaining', '?')}")

fixtures = r2.json().get('response', [])
print(f"   Total partidos encontrados: {len(fixtures)}")

# Filtrar solo partidos terminados de eliminatorias (desde junio 28)
fixtures_terminados = [
    f for f in fixtures
    if f['fixture']['status']['short'] in ('FT', 'AET', 'PEN')
    and f['fixture']['date'][:10] >= '2026-06-28'
]
print(f"   Partidos eliminatorias terminados: {len(fixtures_terminados)}")

if len(fixtures_terminados) == 0:
    print("\n⚠️  No se encontraron partidos. Guardando respuesta completa para debug...")
    with open('Data/api_fixtures_debug.json', 'w', encoding='utf-8') as f:
        json.dump(r2.json(), f, ensure_ascii=False, indent=2)
    print("   Ver Data/api_fixtures_debug.json para diagnosticar")
    exit()

time.sleep(1)

# ── Paso 3: Obtener stats de cada partido ──
print("\n📊 Obteniendo stats de cada partido...")
filas = []
errores = []

for i, fixture in enumerate(fixtures_terminados):
    fid = fixture['fixture']['id']
    fecha = fixture['fixture']['date'][:10]
    local = fixture['teams']['home']['name']
    visit = fixture['teams']['away']['name']
    goles_l = fixture['goals']['home']
    goles_v = fixture['goals']['away']
    resultado = f"{goles_l}-{goles_v}"

    print(f"   [{i+1}/{len(fixtures_terminados)}] {fecha} {local} {resultado} {visit}")

    # Obtener stats del partido
    r3 = requests.get(f'{BASE_URL}/fixtures/statistics',
                      headers=HEADERS, params={'fixture': fid})
    remaining = r3.headers.get('x-ratelimit-remaining', '?')

    stats_data = r3.json().get('response', [])

    fila = {
        'Fecha': fecha,
        'Equipo_Local': local,
        'Equipo_Visitante': visit,
        'Resultado': resultado,
        'Fixture_ID': fid,
    }

    for team_stats in stats_data:
        team_name = team_stats['team']['name']
        suffix = '_Local' if team_name == local else '_Visitante'

        for stat in team_stats.get('statistics', []):
            tipo = stat['type']
            valor = stat['value']
            if valor is None:
                valor = 0
            try:
                valor = float(str(valor).replace('%',''))
            except:
                valor = 0

            # Mapear nombres de stats
            mapa_stats = {
                'Shots on Goal': f'Remates_a_puerta{suffix}',
                'Total Shots': f'Remates_totales{suffix}',
                'Corner Kicks': f'Córneres{suffix}',
                'Fouls': f'Faltas{suffix}',
                'Yellow Cards': f'Tarjetas_amarillas{suffix}',
                'Red Cards': f'Tarjetas_rojas{suffix}',
                'Ball Possession': f'Posesión{suffix}',
                'Goalkeeper Saves': f'Paradas{suffix}',
                'expected_goals': f'Goles_esperados_(xG){suffix}',
                'Passes': f'Pases{suffix}',
            }

            if tipo in mapa_stats:
                fila[mapa_stats[tipo]] = valor

    filas.append(fila)
    print(f"      C:{fila.get('Córneres_Local',0):.0f}-{fila.get('Córneres_Visitante',0):.0f} "
          f"T:{fila.get('Remates_a_puerta_Local',0):.0f}-{fila.get('Remates_a_puerta_Visitante',0):.0f} "
          f"F:{fila.get('Faltas_Local',0):.0f}-{fila.get('Faltas_Visitante',0):.0f} "
          f"[{remaining} req restantes]")

    time.sleep(0.5)  # respetar rate limit

# ── Paso 4: Actualizar partidos.csv ──
print(f"\n✅ Stats obtenidas: {len(filas)} partidos")

df_nuevo = pd.DataFrame(filas)

# Cargar CSV existente
df_exist = pd.read_csv('Data/partidos.csv')
print(f"   Partidos existentes: {len(df_exist)}")

# Quitar partidos que ya tenemos del API (para no duplicar)
fechas_nuevas = set(df_nuevo['Fecha'].unique())
df_sin_dupl = df_exist[~df_exist['Fecha'].isin(fechas_nuevas) |
                        ~df_exist['Equipo_Local'].isin(df_nuevo['Equipo_Local'].unique())]

# Combinar
df_final = pd.concat([df_sin_dupl, df_nuevo], ignore_index=True)
df_final.to_csv('Data/partidos.csv', index=False)
print(f"   Partidos después: {len(df_final)}")

# Guardar también el JSON de stats para referencia
with open('Data/stats_api_mundial2026.json', 'w', encoding='utf-8') as f:
    json.dump(filas, f, ensure_ascii=False, indent=2)

print("\n✅ Data/partidos.csv actualizado con stats reales")
print("✅ Data/stats_api_mundial2026.json guardado")
print("\n▶ Ahora corre: python stats_por_equipo_v2.py")
