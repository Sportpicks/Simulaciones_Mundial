# -*- coding: utf-8 -*-
"""
analisis_mercado.py
Módulo de análisis automático pre-picks:
1. Cuotas reales de la API (h2h + totals)
2. Búsqueda web de lesiones/bajas
3. Comparación prob modelo vs prob implícita mercado
4. Selección inteligente de líneas de props
5. Genera reporte JSON para el generador
"""
import os, sys, json, math, requests
from datetime import datetime, timezone, timedelta

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

PERU_TZ = timezone(timedelta(hours=-5))
def hoy_peru(): return datetime.now(PERU_TZ).strftime("%Y-%m-%d")

API_KEY_ODDS = "622b4b772a4d155e032de1c17a83e41a"
API_FOOTBALL = "2ef79c28645eb3c1041bd8768da83e65"

# Mapa nombres español → inglés para la API
NOMBRES_ES_EN = {
    'Argentina': 'Argentina', 'Egipto': 'Egypt',
    'Suiza': 'Switzerland', 'Colombia': 'Colombia',
    'Francia': 'France', 'Paraguay': 'Paraguay',
    'Brasil': 'Brazil', 'Noruega': 'Norway',
    'México': 'Mexico', 'Inglaterra': 'England',
    'Portugal': 'Portugal', 'España': 'Spain',
    'EE. UU.': 'United States', 'Bélgica': 'Belgium',
    'Canadá': 'Canada', 'Marruecos': 'Morocco',
    'Alemania': 'Germany', 'Países Bajos': 'Netherlands',
}

NOMBRES_EN_ES = {v: k for k, v in NOMBRES_ES_EN.items()}

def p_poisson(lam, linea):
    """Probabilidad Poisson de superar una línea"""
    k_min = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(k_min))
    except:
        return 0.0

def obtener_cuotas_reales():
    """Obtiene cuotas h2h + totals de la API"""
    cuotas = {}
    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/",
            params={
                "apiKey": API_KEY_ODDS,
                "regions": "eu",
                "markets": "h2h,totals",
                "oddsFormat": "decimal"
            },
            timeout=15
        )
        if r.status_code == 200:
            for partido in r.json():
                local_en = partido.get("home_team", "")
                visit_en = partido.get("away_team", "")
                local_es = NOMBRES_EN_ES.get(local_en, local_en)
                visit_es = NOMBRES_EN_ES.get(visit_en, visit_en)

                c1s, cxs, c2s = [], [], []
                totals = {}

                for bk in partido.get("bookmakers", []):
                    for mkt in bk.get("markets", []):
                        if mkt["key"] == "h2h":
                            outs = {o["name"]: o["price"] for o in mkt["outcomes"]}
                            if local_en in outs: c1s.append(outs[local_en])
                            if "Draw" in outs:   cxs.append(outs["Draw"])
                            if visit_en in outs: c2s.append(outs[visit_en])
                        elif mkt["key"] == "totals":
                            for o in mkt["outcomes"]:
                                linea = o.get("point", "")
                                nombre = o.get("name", "").lower()
                                key = f"{nombre}_{linea}"
                                if key not in totals:
                                    totals[key] = []
                                totals[key].append(o["price"])

                cuotas[(local_es, visit_es)] = {
                    'c1': round(sum(c1s)/len(c1s), 2) if c1s else 0,
                    'cx': round(sum(cxs)/len(cxs), 2) if cxs else 0,
                    'c2': round(sum(c2s)/len(c2s), 2) if c2s else 0,
                    'totals': {k: round(sum(v)/len(v), 2) for k, v in totals.items()},
                }
    except Exception as e:
        print(f"  ⚠️ Error API cuotas: {e}")
    return cuotas

def calcular_valor(prob_modelo, cuota_real, nombre=""):
    """Calcula EV y determina si hay valor real"""
    prob_impl = 1 / cuota_real if cuota_real > 0 else 1
    ev = round((prob_modelo/100) - prob_impl, 3)
    margen = round((prob_modelo/100 / prob_impl - 1) * 100, 1)
    tiene_valor = ev > 0.03 and margen > 5
    return {
        'ev': ev,
        'margen_pct': margen,
        'prob_modelo': prob_modelo,
        'prob_mercado': round(prob_impl * 100, 1),
        'cuota': cuota_real,
        'tiene_valor': tiene_valor,
        'nivel': 'ALTO' if margen > 15 else 'MEDIO' if margen > 5 else 'BAJO'
    }

def analizar_partido(local, visit, stats_l, stats_v, pred, cuotas_p):
    """Análisis completo de un partido"""
    resultado = {
        'partido': f"{local} vs {visit}",
        'picks_recomendados': [],
        'advertencias': [],
    }

    xgl = float(pred.get('xG_L', 1.2)) * 0.85  # factor eliminatoria
    xgv = float(pred.get('xG_V', 1.0)) * 0.85
    xg_t = xgl + xgv

    p1 = float(pred.get('Prob_1_Final', 33))
    px = float(pred.get('Prob_X_Final', 33))
    p2 = float(pred.get('Prob_2_Final', 33))

    c1 = cuotas_p.get('c1', 0)
    cx = cuotas_p.get('cx', 0)
    c2 = cuotas_p.get('c2', 0)
    totals = cuotas_p.get('totals', {})

    print(f"\n  📊 {local} vs {visit}")
    print(f"     xG: {xgl:.2f} - {xgv:.2f} | Total: {xg_t:.2f}")
    print(f"     Probs: {p1:.0f}%-{px:.0f}%-{p2:.0f}%")

    # ── Analizar Over/Under goles ──
    for linea_str, linea in [('1.5', 1.5), ('2.5', 2.5), ('3.5', 3.5)]:
        prob_over = round(p_poisson(xg_t, linea) * 100, 1)
        prob_under = round(100 - prob_over, 1)

        # Buscar cuota real
        cuota_over = totals.get(f'over_{linea_str}', 0)
        cuota_under = totals.get(f'under_{linea_str}', 0)

        if cuota_over >= 1.40:
            val = calcular_valor(prob_over, cuota_over, f"Over {linea_str}")
            if val['tiene_valor'] and prob_over >= 55:
                resultado['picks_recomendados'].append({
                    'mercado': f'Más de {linea_str} goles',
                    'emoji': '🥅',
                    'categoria': 'Goles',
                    **val
                })
                print(f"     ✅ Over {linea_str}: {prob_over}% vs mercado {val['prob_mercado']}% @{cuota_over} → EV{val['ev']:+.2f} [{val['nivel']}]")

        if cuota_under >= 1.40:
            val = calcular_valor(prob_under, cuota_under, f"Under {linea_str}")
            if val['tiene_valor'] and prob_under >= 55:
                resultado['picks_recomendados'].append({
                    'mercado': f'Menos de {linea_str} goles',
                    'emoji': '🔒',
                    'categoria': 'Goles',
                    **val
                })
                print(f"     ✅ Under {linea_str}: {prob_under}% vs mercado {val['prob_mercado']}% @{cuota_under} → EV{val['ev']:+.2f} [{val['nivel']}]")

    # ── Analizar props con stats del modelo ──
    # Córners
    cl = stats_l.get('corners_favor_5', stats_l.get('corners_favor_tot', 5))
    cv = stats_v.get('corners_favor_5', stats_v.get('corners_favor_tot', 5))
    ct = cl + cv
    # Usar línea más conservadora (9.5 en vez de 10.5)
    for linea in [8.5, 9.5]:
        prob_c = round(p_poisson(ct, linea) * 100, 1)
        if prob_c >= 70:
            resultado['picks_recomendados'].append({
                'mercado': f'Córners totales +{linea}',
                'emoji': '⛳',
                'categoria': 'Córners',
                'prob_modelo': prob_c,
                'prob_mercado': None,
                'cuota': 1.65,  # estimada conservadora
                'ev': round((prob_c/100) - (1/1.65), 3),
                'margen_pct': round((prob_c/100 / (1/1.65) - 1) * 100, 1),
                'tiene_valor': prob_c >= 75,
                'nivel': 'ALTO' if prob_c >= 85 else 'MEDIO'
            })
            print(f"     ⛳ Córners +{linea}: {prob_c}% (cuota est. @1.65)")

    # Faltas — usar línea más conservadora
    fl = stats_l.get('faltas_cometidas_5', stats_l.get('faltas_cometidas_tot', 12))
    fv = stats_v.get('faltas_cometidas_5', stats_v.get('faltas_cometidas_tot', 12))
    ft = fl + fv
    for linea in [18.5, 20.5]:
        prob_f = round(p_poisson(ft, linea) * 100, 1)
        if prob_f >= 70:
            resultado['picks_recomendados'].append({
                'mercado': f'Faltas totales +{linea}',
                'emoji': '🦵',
                'categoria': 'Faltas',
                'prob_modelo': prob_f,
                'prob_mercado': None,
                'cuota': 1.60,
                'ev': round((prob_f/100) - (1/1.60), 3),
                'margen_pct': round((prob_f/100 / (1/1.60) - 1) * 100, 1),
                'tiene_valor': prob_f >= 75,
                'nivel': 'ALTO' if prob_f >= 85 else 'MEDIO'
            })
            print(f"     🦵 Faltas +{linea}: {prob_f}% (cuota est. @1.60)")

    # Ordenar por margen de valor
    resultado['picks_recomendados'].sort(
        key=lambda x: (x['nivel'] == 'ALTO', x.get('margen_pct', 0)),
        reverse=True
    )

    return resultado

def buscar_noticias_lesiones(local, visit):
    """Busca lesiones y bajas via web search"""
    try:
        import urllib.request, urllib.parse
        query = urllib.parse.quote(f"{local} {visit} lesiones bajas alineacion Mundial 2026 hoy")
        url = f"https://www.google.com/search?q={query}&num=3"
        # Solo intentamos — si falla no es crítico
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        return "Búsqueda de noticias no disponible — verificar manualmente"
    except:
        return "No disponible"

def main():
    import pandas as pd

    print("\n" + "="*60)
    print("  ANÁLISIS DE MERCADO — Pre-generador de picks")
    print("="*60)

    hoy = hoy_peru()
    print(f"  📅 Fecha: {hoy}")

    # Cargar predicciones
    try:
        df = pd.read_csv('Predicciones/predicciones_finales.csv')
        partidos_hoy = df[df['Fecha'] == hoy]
        if partidos_hoy.empty:
            print(f"  ⚠️ No hay partidos para hoy ({hoy})")
            return {}
    except Exception as e:
        print(f"  ❌ Error cargando predicciones: {e}")
        return {}

    # Cargar stats
    try:
        stats = json.load(open('Data/stats_equipos.json', encoding='utf-8'))
    except:
        stats = {}

    print(f"\n  ✅ Partidos encontrados: {len(partidos_hoy)}")

    # Obtener cuotas reales
    print("\n  📡 Obteniendo cuotas de la API...")
    cuotas = obtener_cuotas_reales()
    print(f"  ✅ Cuotas obtenidas: {len(cuotas)} partidos")

    # Analizar cada partido
    reporte = {
        'fecha': hoy,
        'partidos': [],
        'picks_top': [],
        'resumen': ''
    }

    todos_picks = []

    for _, pred in partidos_hoy.iterrows():
        local = pred['Local']
        visit = pred['Visitante']

        stats_l = stats.get(local, {})
        stats_v = stats.get(visit, {})

        # Buscar cuotas — intentar ambos órdenes
        cuotas_p = cuotas.get((local, visit), cuotas.get((visit, local), {}))

        analisis = analizar_partido(local, visit, stats_l, stats_v, pred, cuotas_p)
        reporte['partidos'].append(analisis)

        for pick in analisis['picks_recomendados']:
            pick['partido'] = f"{local} vs {visit}"
            todos_picks.append(pick)

    # Ordenar picks globales por valor
    todos_picks.sort(
        key=lambda x: (x['nivel'] == 'ALTO', x.get('margen_pct', 0)),
        reverse=True
    )

    reporte['picks_top'] = todos_picks[:6]

    # Resumen
    n_alto = sum(1 for p in todos_picks if p['nivel'] == 'ALTO')
    n_medio = sum(1 for p in todos_picks if p['nivel'] == 'MEDIO')
    reporte['resumen'] = f"{n_alto} picks ALTO valor, {n_medio} MEDIO valor"

    print(f"\n{'='*60}")
    print(f"  📋 PICKS CON VALOR REAL (ordenados):")
    for i, pk in enumerate(todos_picks[:6], 1):
        print(f"  {i}. [{pk['nivel']:5}] {pk['partido']} — {pk['mercado']}")
        print(f"       Modelo: {pk['prob_modelo']}% | Mercado: {pk.get('prob_mercado','?')}% | @{pk['cuota']} | EV{pk['ev']:+.2f}")

    # Guardar reporte
    with open('Data/analisis_mercado.json', 'w', encoding='utf-8') as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"\n  ✅ Reporte guardado en Data/analisis_mercado.json")
    print("="*60)

    return reporte

if __name__ == '__main__':
    main()
