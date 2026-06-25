# -*- coding: utf-8 -*-
"""
corregir_fechas_peru.py
Corrige las fechas de partidos_mundial.csv para usar hora Perú (UTC-5)
en vez de UTC, así la web muestra correctamente los partidos del día.

Uso: python corregir_fechas_peru.py
"""

import os
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

API_TOKEN = "cce6c60e411047abb142e005de2d957a"
HEADERS   = {"X-Auth-Token": API_TOKEN}
RAIZ      = os.path.dirname(os.path.abspath(__file__))
CSV_OUT   = os.path.join(RAIZ, "Data", "partidos_mundial.csv")

ZONA_PERU = timezone(timedelta(hours=-5))  # UTC-5

NOMBRES = {
    "Mexico":"México","South Africa":"Sudáfrica","South Korea":"Corea del Sur",
    "Czechia":"República Checa","Czech Republic":"República Checa",
    "Switzerland":"Suiza","Bosnia and Herzegovina":"Bosnia-Herzegovina",
    "Canada":"Canadá","Qatar":"Catar","Scotland":"Escocia","Brazil":"Brasil",
    "Haiti":"Haití","Morocco":"Marruecos","Turkey":"Turquía",
    "United States":"EE. UU.","Australia":"Australia","Germany":"Alemania",
    "Ecuador":"Ecuador","Cote d'Ivoire":"Costa de Marfil",
    "Ivory Coast":"Costa de Marfil","Curacao":"Curazao","Curaçao":"Curazao",
    "Sweden":"Suecia","Netherlands":"Países Bajos","Tunisia":"Túnez",
    "Japan":"Japón","Belgium":"Bélgica","Egypt":"Egipto","Iran":"Irán",
    "New Zealand":"Nueva Zelanda","Spain":"España","Uruguay":"Uruguay",
    "Cape Verde":"Cabo Verde","Cape Verde Islands":"Cabo Verde",
    "Saudi Arabia":"Arabia Saudí","France":"Francia","Norway":"Noruega",
    "Senegal":"Senegal","Iraq":"Irak","Austria":"Austria",
    "Argentina":"Argentina","Algeria":"Argelia","Jordan":"Jordania",
    "Portugal":"Portugal","Colombia":"Colombia","DR Congo":"RD Congo",
    "Uzbekistan":"Uzbekistán","Croatia":"Croacia","England":"Inglaterra",
    "Ghana":"Ghana","Panama":"Panamá",
}

GRUPOS = {
    "GROUP_A":"A","GROUP_B":"B","GROUP_C":"C","GROUP_D":"D",
    "GROUP_E":"E","GROUP_F":"F","GROUP_G":"G","GROUP_H":"H",
    "GROUP_I":"I","GROUP_J":"J","GROUP_K":"K","GROUP_L":"L",
}

def nombre_es(n): return NOMBRES.get(n, n)

if __name__ == "__main__":
    print("\n🚀 Reconstruyendo partidos_mundial.csv con hora Perú (UTC-5)")
    print("="*55)

    r = requests.get(
        "https://api.football-data.org/v4/competitions/WC/matches",
        headers=HEADERS, params={"season": 2026}, timeout=15
    )
    data     = r.json()
    partidos = [p for p in data.get("matches",[]) if p.get("stage")=="GROUP_STAGE"]
    print(f"✅ {len(partidos)} partidos de fase de grupos obtenidos")

    filas = []
    for p in partidos:
        local_es = nombre_es(p.get("homeTeam",{}).get("name",""))
        visit_es = nombre_es(p.get("awayTeam",{}).get("name",""))

        score = p.get("score",{})
        ft    = score.get("fullTime",{})
        gl, gv = ft.get("home"), ft.get("away")
        resultado = f"{gl}:{gv}" if gl is not None else "-"

        utc = p.get("utcDate","")
        try:
            # Convertir UTC → hora Perú
            dt_utc  = datetime.fromisoformat(utc.replace("Z","+00:00"))
            dt_peru = dt_utc.astimezone(ZONA_PERU)
            fecha_str = dt_peru.strftime("%Y-%m-%d")  # Fecha en hora Perú
            hora_str  = dt_peru.strftime("%H:%M")
        except:
            fecha_str = ""
            hora_str  = ""

        grupo = GRUPOS.get(p.get("group",""), "")

        filas.append({
            "Fecha"           : fecha_str,
            "Hora_Peru"       : hora_str,
            "Equipo_Local"    : local_es,
            "Equipo_Visitante": visit_es,
            "Resultado"       : resultado,
            "Grupo"           : grupo,
            "Estado"          : p.get("status",""),
        })

    df = pd.DataFrame(filas)
    df.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")

    print(f"✅ partidos_mundial.csv actualizado con hora Perú")
    print(f"\n📅 Partidos por fecha (hora Perú):")
    for fecha, grupo_df in df.groupby("Fecha"):
        print(f"\n  {fecha}:")
        for _, r in grupo_df.iterrows():
            print(f"    {r['Hora_Peru']} — Grupo {r['Grupo']}: {r['Equipo_Local']} vs {r['Equipo_Visitante']}")
