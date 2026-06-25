# -*- coding: utf-8 -*-
"""
actualizar_resultados_mundial.py
Descarga resultados reales del Mundial 2026 via football-data.org
y los guarda en Data/resultados_mundial.csv

Plan gratuito: 10 llamadas/minuto, acceso completo al Mundial 2026.

Uso: python actualizar_resultados_mundial.py
Tiempo: ~5 segundos
"""

import os
import requests
import pandas as pd
from datetime import datetime, timezone

# ── Configuración ─────────────────────────────────────────────────────────────
API_TOKEN = "cce6c60e411047abb142e005de2d957a"
URL_BASE  = "https://api.football-data.org/v4"
HEADERS   = {"X-Auth-Token": API_TOKEN}

RAIZ     = os.path.dirname(os.path.abspath(__file__))
CSV_OUT  = os.path.join(RAIZ, "Data", "resultados_mundial.csv")

# Mapeo nombres inglés → español
NOMBRES_EN_ES = {
    "Mexico": "México", "South Africa": "Sudáfrica",
    "South Korea": "Corea del Sur", "Czech Republic": "República Checa",
    "Czechia": "República Checa", "Switzerland": "Suiza",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina", "Canada": "Canadá",
    "Qatar": "Catar", "Scotland": "Escocia", "Brazil": "Brasil",
    "Haiti": "Haití", "Morocco": "Marruecos", "Turkey": "Turquía",
    "United States": "EE. UU.", "Australia": "Australia",
    "Germany": "Alemania", "Ecuador": "Ecuador",
    "Ivory Coast": "Costa de Marfil", "Cote d'Ivoire": "Costa de Marfil",
    "Curacao": "Curazao", "Sweden": "Suecia",
    "Netherlands": "Países Bajos", "Tunisia": "Túnez",
    "Japan": "Japón", "Belgium": "Bélgica", "Egypt": "Egipto",
    "Iran": "Irán", "New Zealand": "Nueva Zelanda", "Spain": "España",
    "Uruguay": "Uruguay", "Cape Verde": "Cabo Verde",
    "Saudi Arabia": "Arabia Saudí", "France": "Francia",
    "Norway": "Noruega", "Senegal": "Senegal", "Iraq": "Irak",
    "Austria": "Austria", "Argentina": "Argentina", "Algeria": "Argelia",
    "Jordan": "Jordania", "Portugal": "Portugal", "Colombia": "Colombia",
    "DR Congo": "RD Congo", "Uzbekistan": "Uzbekistán",
    "Croatia": "Croacia", "England": "Inglaterra",
    "Ghana": "Ghana", "Panama": "Panamá",
}

GRUPOS_ID = {
    "GROUP_A": "A", "GROUP_B": "B", "GROUP_C": "C", "GROUP_D": "D",
    "GROUP_E": "E", "GROUP_F": "F", "GROUP_G": "G", "GROUP_H": "H",
    "GROUP_I": "I", "GROUP_J": "J", "GROUP_K": "K", "GROUP_L": "L",
}

def nombre_es(nombre_en):
    return NOMBRES_EN_ES.get(nombre_en, nombre_en)

def obtener_partidos():
    """Descarga todos los partidos del Mundial 2026."""
    print("📡 Descargando partidos del Mundial 2026...")
    r = requests.get(
        f"{URL_BASE}/competitions/WC/matches",
        headers=HEADERS,
        params={"season": 2026},
        timeout=15
    )
    if r.status_code != 200:
        print(f"❌ Error {r.status_code}: {r.text}")
        return []
    data = r.json()
    total   = data.get("resultSet", {}).get("count", 0)
    jugados = data.get("resultSet", {}).get("played", 0)
    print(f"   ✅ Total partidos: {total} | Jugados: {jugados}")
    return data.get("matches", [])

def obtener_estadisticas(fixture_id):
    """Descarga estadísticas detalladas de un partido."""
    r = requests.get(
        f"{URL_BASE}/matches/{fixture_id}",
        headers=HEADERS,
        timeout=10
    )
    if r.status_code != 200:
        return {}
    return r.json()

def procesar_partidos(partidos):
    """Procesa la lista de partidos y extrae la información relevante."""
    filas = []
    jugados = [p for p in partidos if p.get("status") == "FINISHED"]
    pendientes = [p for p in partidos if p.get("status") != "FINISHED"]

    print(f"\n📊 Procesando {len(jugados)} partidos jugados...")
    print(f"   Pendientes: {len(pendientes)}")

    for p in partidos:
        local_en = p.get("homeTeam", {}).get("name", "")
        visit_en = p.get("awayTeam", {}).get("name", "")
        local_es = nombre_es(local_en)
        visit_es = nombre_es(visit_en)

        score    = p.get("score", {})
        ft       = score.get("fullTime", {})
        ht       = score.get("halfTime", {})
        goles_l  = ft.get("home")
        goles_v  = ft.get("away")
        ganador  = score.get("winner", "")

        # Resultado 1X2
        if ganador == "HOME_TEAM":
            resultado = "1"
        elif ganador == "AWAY_TEAM":
            resultado = "2"
        elif ganador == "DRAW":
            resultado = "X"
        else:
            resultado = ""

        # Marcador
        if goles_l is not None and goles_v is not None:
            marcador = f"{goles_l}-{goles_v}"
        else:
            marcador = ""

        # Fecha local
        utc_date = p.get("utcDate", "")
        try:
            fecha = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
            fecha_str = fecha.strftime("%Y-%m-%d")
        except:
            fecha_str = ""

        grupo = GRUPOS_ID.get(p.get("group", ""), "")
        stage = p.get("stage", "")
        status = p.get("status", "")

        filas.append({
            "ID_Partido"      : p.get("id"),
            "Fecha"           : fecha_str,
            "Grupo"           : grupo,
            "Fase"            : stage,
            "Estado"          : status,
            "Local"           : local_es,
            "Visitante"       : visit_es,
            "Goles_Local"     : goles_l,
            "Goles_Visitante" : goles_v,
            "Marcador"        : marcador,
            "Resultado_1X2"   : resultado,
            "HT_Local"        : ht.get("home"),
            "HT_Visitante"    : ht.get("away"),
        })

    return pd.DataFrame(filas)

def imprimir_resumen(df):
    """Muestra resumen de resultados jugados."""
    jugados = df[df["Estado"] == "FINISHED"]
    print(f"\n{'='*70}")
    print(f"  RESULTADOS MUNDIALES 2026 — {len(jugados)} partidos jugados")
    print(f"{'='*70}")
    print(f"{'Fecha':<12} {'Grupo':<6} {'Local':<22} {'Marc':^5} {'Visitante':<22}")
    print("-"*70)
    for _, r in jugados.sort_values("Fecha").iterrows():
        print(f"{r['Fecha']:<12} {r['Grupo']:<6} {r['Local']:<22} "
              f"{r['Marcador']:^5} {r['Visitante']:<22}")

    print(f"\n  Próximos partidos:")
    print("-"*70)
    proximos = df[df["Estado"] != "FINISHED"].head(5)
    for _, r in proximos.iterrows():
        print(f"  {r['Fecha']:<12} {r['Grupo']:<6} {r['Local']} vs {r['Visitante']}")

if __name__ == "__main__":
    print("\n🚀 ACTUALIZADOR DE RESULTADOS — MUNDIAL 2026")
    print("="*50)

    # Descargar partidos
    partidos = obtener_partidos()
    if not partidos:
        print("❌ No se pudieron obtener partidos")
        exit(1)

    # Procesar
    df = procesar_partidos(partidos)

    # Guardar
    os.makedirs(os.path.join(RAIZ, "Data"), exist_ok=True)
    df.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
    print(f"\n✅ Guardado en: Data/resultados_mundial.csv")
    print(f"   Total partidos: {len(df)}")
    print(f"   Jugados: {len(df[df['Estado']=='FINISHED'])}")
    print(f"   Pendientes: {len(df[df['Estado']!='FINISHED'])}")

    # Mostrar resumen
    imprimir_resumen(df)

    print(f"\n   Generado: {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')}")
