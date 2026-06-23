# -*- coding: utf-8 -*-
"""
mejoras_avanzadas.py
Implementa las 3 mejoras principales al modelo:

MEJORA 1 — Decaimiento temporal + Forma reciente
MEJORA 2 — EV Tracking + Closing Line Value  
MEJORA 3 — Factor de ausencia por jugadores clave

Uso: python mejoras_avanzadas.py
Genera:
  - Data/pesos_temporales.csv     (pesos por partido)
  - Data/forma_equipos.json       (forma reciente de cada equipo)
  - Predicciones/ev_tracking.csv  (EV de cada predicción)
  - Predicciones/predicciones_mejoradas_v2.csv
"""

import os
import json
import math
import requests
import numpy as np
import pandas as pd
from datetime import datetime, date, timezone

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

# ═══════════════════════════════════════════════════════════════════
# MEJORA 1 — DECAIMIENTO TEMPORAL + FORMA RECIENTE
# ═══════════════════════════════════════════════════════════════════

LAMBDA_DECAY = 0.003   # Factor de decaimiento exponencial
N_FORMA      = 5       # Últimos N partidos para forma reciente
HOY          = date.today()

def calcular_peso_temporal(fecha_str):
    """
    Calcula el peso de un partido según su antigüedad.
    Peso = e^(-λ × días_desde_partido)
    
    Ejemplos:
    - Hoy        → 1.000 (100%)
    - 1 mes      → 0.914 (91%)
    - 6 meses    → 0.578 (58%)
    - 1 año      → 0.334 (33%)
    - 2 años     → 0.112 (11%)
    """
    try:
        if isinstance(fecha_str, str):
            fecha = datetime.strptime(fecha_str[:10], '%Y-%m-%d').date()
        else:
            fecha = fecha_str
        dias = (HOY - fecha).days
        return round(math.exp(-LAMBDA_DECAY * dias), 4)
    except:
        return 0.1

def calcular_forma_equipo(df_hist, equipo, n=N_FORMA):
    """
    Calcula la forma reciente de un equipo (últimos N partidos).
    Retorna:
    - puntos_forma: promedio de puntos en últimos N partidos
    - racha: número de partidos sin perder (+ = racha positiva, - = racha negativa)
    - goles_favor_forma: promedio goles a favor en últimos N
    - goles_contra_forma: promedio goles en contra en últimos N
    - tendencia: 'subida', 'bajada', 'estable'
    """
    # Partidos como local
    local = df_hist[df_hist['Equipo_Local'] == equipo][
        ['Fecha', 'Goles_Local', 'Goles_Visitante']
    ].rename(columns={'Goles_Local': 'GF', 'Goles_Visitante': 'GC'})
    local['pts'] = local.apply(
        lambda r: 3 if r['GF'] > r['GC'] else (1 if r['GF'] == r['GC'] else 0), axis=1
    )

    # Partidos como visitante
    visit = df_hist[df_hist['Equipo_Visitante'] == equipo][
        ['Fecha', 'Goles_Visitante', 'Goles_Local']
    ].rename(columns={'Goles_Visitante': 'GF', 'Goles_Local': 'GC'})
    visit['pts'] = visit.apply(
        lambda r: 3 if r['GF'] > r['GC'] else (1 if r['GF'] == r['GC'] else 0), axis=1
    )

    todos = pd.concat([local, visit]).sort_values('Fecha')
    todos['Fecha'] = pd.to_datetime(todos['Fecha'], errors='coerce')
    todos = todos.dropna(subset=['Fecha'])

    if len(todos) == 0:
        return {'puntos_forma': 1.5, 'racha': 0, 'gf_forma': 1.2,
                'gc_forma': 1.2, 'tendencia': 'estable', 'partidos': 0}

    ultimos = todos.tail(n)
    todos_pts = todos['pts'].tolist()

    # Racha actual
    racha = 0
    for pts in reversed(todos_pts):
        if pts >= 1:  # No perdió
            racha += 1
        else:
            break

    # Tendencia: comparar forma reciente vs forma anterior
    if len(todos) >= n * 2:
        pts_reciente  = todos.tail(n)['pts'].mean()
        pts_anterior  = todos.tail(n * 2).head(n)['pts'].mean()
        if pts_reciente > pts_anterior + 0.3:
            tendencia = 'subida'
        elif pts_reciente < pts_anterior - 0.3:
            tendencia = 'bajada'
        else:
            tendencia = 'estable'
    else:
        tendencia = 'estable'

    return {
        'puntos_forma'  : round(float(ultimos['pts'].mean()), 2),
        'racha'         : int(racha),
        'gf_forma'      : round(float(ultimos['GF'].mean()), 2),
        'gc_forma'      : round(float(ultimos['GC'].mean()), 2),
        'tendencia'     : tendencia,
        'partidos'      : int(len(todos)),
    }

def factor_forma(forma_local, forma_visit):
    """
    Calcula un factor de ajuste basado en la forma reciente.
    Rango: 0.85 a 1.15 (±15% máximo de ajuste)
    
    Si local está en tendencia positiva → sube su probabilidad
    Si visitante está en tendencia positiva → baja probabilidad del local
    """
    # Factor base: diferencia de puntos de forma (0-3 escala)
    diff_pts = forma_local['puntos_forma'] - forma_visit['puntos_forma']
    
    # Factor tendencia
    tend_local = {'subida': 0.05, 'estable': 0, 'bajada': -0.05}
    tend_visit = {'subida': -0.03, 'estable': 0, 'bajada': 0.03}
    
    # Factor racha
    racha_factor = (forma_local['racha'] - forma_visit['racha']) * 0.01
    
    # Factor total (normalizado)
    factor_total = (diff_pts * 0.03 + 
                    tend_local[forma_local['tendencia']] + 
                    tend_visit[forma_visit['tendencia']] + 
                    racha_factor)
    
    # Limitar a ±15%
    return round(max(-0.15, min(0.15, factor_total)), 4)


# ═══════════════════════════════════════════════════════════════════
# MEJORA 2 — EV TRACKING + CLOSING LINE VALUE
# ═══════════════════════════════════════════════════════════════════

API_KEY_ODDS = "622b4b772a4d155e032de1c17a83e41a"

def calcular_ev(prob_modelo, cuota_casa):
    """
    Expected Value = (Probabilidad real × Cuota) - 1
    
    EV > 0 → apuesta con valor positivo
    EV > 0.05 → valor significativo (>5%)
    EV > 0.10 → valor alto (>10%)
    """
    if cuota_casa <= 1 or prob_modelo <= 0:
        return 0
    return round((prob_modelo / 100) * cuota_casa - 1, 4)

def clasificar_ev(ev):
    """Clasifica el EV en categorías."""
    if ev >= 0.15:  return '🔥 ALTO VALUE',   'alto'
    if ev >= 0.07:  return '✅ VALUE',          'medio'
    if ev >= 0.02:  return '⚠️ VALUE LEVE',    'leve'
    if ev >= 0:     return '⚖️ NEUTRO',         'neutro'
    return '❌ SIN VALUE', 'negativo'

def obtener_cuotas_actuales():
    """Obtiene cuotas actuales de The Odds API."""
    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/",
            params={
                "apiKey"     : API_KEY_ODDS,
                "regions"    : "eu",
                "markets"    : "h2h",
                "oddsFormat" : "decimal",
                "bookmakers" : "pinnacle"  # Pinnacle = referencia profesional
            },
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []

NOMBRES_API = {
    "Mexico":"México", "South Africa":"Sudáfrica", "South Korea":"Corea del Sur",
    "Czechia":"República Checa", "Switzerland":"Suiza",
    "Bosnia and Herzegovina":"Bosnia-Herzegovina", "Canada":"Canadá",
    "Qatar":"Catar", "Scotland":"Escocia", "Brazil":"Brasil",
    "Haiti":"Haití", "Morocco":"Marruecos", "Turkey":"Turquía",
    "United States":"EE. UU.", "Australia":"Australia", "Germany":"Alemania",
    "Ecuador":"Ecuador", "Cote d'Ivoire":"Costa de Marfil", "Curacao":"Curazao",
    "Curaçao":"Curazao", "Sweden":"Suecia", "Netherlands":"Países Bajos",
    "Tunisia":"Túnez", "Japan":"Japón", "Belgium":"Bélgica", "Egypt":"Egipto",
    "Iran":"Irán", "New Zealand":"Nueva Zelanda", "Spain":"España",
    "Uruguay":"Uruguay", "Cape Verde":"Cabo Verde",
    "Cape Verde Islands":"Cabo Verde", "Saudi Arabia":"Arabia Saudí",
    "France":"Francia", "Norway":"Noruega", "Senegal":"Senegal", "Iraq":"Irak",
    "Austria":"Austria", "Argentina":"Argentina", "Algeria":"Argelia",
    "Jordan":"Jordania", "Portugal":"Portugal", "Colombia":"Colombia",
    "DR Congo":"RD Congo", "Uzbekistan":"Uzbekistán", "Croatia":"Croacia",
    "England":"Inglaterra", "Ghana":"Ghana", "Panama":"Panamá",
}

def calcular_ev_todos_partidos(df_pred, cuotas_raw):
    """
    Calcula el EV para cada predicción del modelo
    comparando con las cuotas de Pinnacle.
    """
    # Construir mapa de cuotas Pinnacle
    cuotas_pinnacle = {}
    for partido in cuotas_raw:
        local_en  = partido.get("home_team", "")
        visit_en  = partido.get("away_team", "")
        local_es  = NOMBRES_API.get(local_en, local_en)
        visit_es  = NOMBRES_API.get(visit_en, visit_en)
        
        for bk in partido.get("bookmakers", []):
            if bk.get("key") != "pinnacle":
                continue
            for market in bk.get("markets", []):
                if market["key"] != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                cuotas_pinnacle[(local_es, visit_es)] = {
                    'c1': outcomes.get(local_en, 0),
                    'cx': outcomes.get("Draw", 0),
                    'c2': outcomes.get(visit_en, 0),
                }

    filas = []
    for _, r in df_pred.iterrows():
        local = r['Local']
        visit = r['Visitante']
        p1    = float(r['Prob_1_Final'])
        px    = float(r['Prob_X_Final'])
        p2    = float(r['Prob_2_Final'])

        clave = (local, visit)
        cuotas = cuotas_pinnacle.get(clave, {})
        c1 = cuotas.get('c1', 0)
        cx = cuotas.get('cx', 0)
        c2 = cuotas.get('c2', 0)

        # EV para cada resultado
        ev1 = calcular_ev(p1, c1) if c1 > 0 else None
        evx = calcular_ev(px, cx) if cx > 0 else None
        ev2 = calcular_ev(p2, c2) if c2 > 0 else None

        # Mejor EV del partido
        evs = {k: v for k, v in {'1': ev1, 'X': evx, '2': ev2}.items() if v is not None}
        if evs:
            mejor_resultado = max(evs, key=lambda k: evs[k])
            mejor_ev        = evs[mejor_resultado]
            etiqueta, cat   = clasificar_ev(mejor_ev)
        else:
            mejor_resultado = '—'
            mejor_ev        = None
            etiqueta        = '—'
            cat             = 'sin_datos'

        # CLV: diferencia entre prob. modelo y prob. implícita Pinnacle
        prob_imp_p1 = round(100 / c1, 1) if c1 > 0 else None
        clv_1 = round(p1 - prob_imp_p1, 1) if prob_imp_p1 else None

        filas.append({
            'Fecha'         : r.get('Fecha', ''),
            'Local'         : local,
            'Visitante'     : visit,
            'Prob_1'        : p1, 'Prob_X': px, 'Prob_2': p2,
            'Cuota_Pinnacle_1': c1, 'Cuota_Pinnacle_X': cx, 'Cuota_Pinnacle_2': c2,
            'EV_1'          : ev1, 'EV_X': evx, 'EV_2': ev2,
            'Mejor_resultado': mejor_resultado,
            'Mejor_EV'      : mejor_ev,
            'EV_Etiqueta'   : etiqueta,
            'EV_Categoria'  : cat,
            'CLV_1'         : clv_1,
            'Tiene_Pinnacle': bool(cuotas),
        })

    return pd.DataFrame(filas)


# ═══════════════════════════════════════════════════════════════════
# MEJORA 3 — FACTOR DE AUSENCIA POR JUGADORES CLAVE
# ═══════════════════════════════════════════════════════════════════

# Valor relativo de jugadores clave (% del valor total del equipo que representan)
# Basado en Transfermarkt — cuánto pesa ese jugador en su selección
JUGADORES_CLAVE = {
    'Francia'      : [('Kylian Mbappé',      0.22), ('Antoine Griezmann', 0.12)],
    'Argentina'    : [('Lionel Messi',        0.18), ('Lautaro Martínez',  0.14)],
    'Inglaterra'   : [('Jude Bellingham',     0.20), ('Harry Kane',        0.16)],
    'Brasil'       : [('Vinicius Jr.',        0.22), ('Rodrygo',           0.12)],
    'Portugal'     : [('Cristiano Ronaldo',   0.14), ('Bruno Fernandes',   0.16)],
    'Alemania'     : [('Jamal Musiala',       0.20), ('Florian Wirtz',     0.18)],
    'España'       : [('Pedri',               0.16), ('Lamine Yamal',      0.15)],
    'Noruega'      : [('Erling Haaland',      0.35), ('Martin Ødegaard',   0.20)],
    'Países Bajos' : [('Virgil van Dijk',     0.16), ('Cody Gakpo',        0.15)],
    'Bélgica'      : [('Kevin De Bruyne',     0.22), ('Romelu Lukaku',     0.14)],
    'Colombia'     : [('James Rodríguez',     0.18), ('Luis Díaz',         0.20)],
    'México'       : [('Hirving Lozano',      0.20), ('Raúl Jiménez',      0.15)],
    'Uruguay'      : [('Darwin Núñez',        0.25), ('Federico Valverde', 0.20)],
    'Japón'        : [('Takefusa Kubo',       0.22), ('Ao Tanaka',         0.12)],
    'Senegal'      : [('Sadio Mané',          0.30), ('Édouard Mendy',     0.15)],
    'Marruecos'    : [('Hakim Ziyech',        0.20), ('Achraf Hakimi',     0.22)],
}

def calcular_factor_ausencia(equipo, jugadores_ausentes):
    """
    Calcula el factor de penalización por ausencias.
    
    Si falta un jugador que representa el 20% del valor del equipo:
    → Reducción del 20% × 0.4 = 8% en probabilidad
    
    El factor 0.4 refleja que el impacto no es lineal
    (el sistema no colapsa sin un jugador).
    """
    if not jugadores_ausentes or equipo not in JUGADORES_CLAVE:
        return 1.0

    jugadores_equipo = {j[0].lower(): j[1] for j in JUGADORES_CLAVE.get(equipo, [])}
    
    impacto_total = 0
    for ausente in jugadores_ausentes:
        peso = jugadores_equipo.get(ausente.lower(), 0)
        impacto_total += peso

    # Factor de penalización (máx 30%)
    penalizacion = min(impacto_total * 0.4, 0.30)
    return round(1.0 - penalizacion, 4)

def ajustar_probabilidades_ausencias(p1, px, p2, factor_local, factor_visit):
    """
    Ajusta las probabilidades según las ausencias de cada equipo.
    Si el local tiene bajas → sube prob. de empate y visitante.
    """
    # Ajustar probabilidad local
    p1_adj = p1 * factor_local
    p2_adj = p2 * factor_visit
    
    # El empate absorbe la diferencia
    px_adj = 100 - p1_adj - p2_adj
    px_adj = max(5, px_adj)  # Mínimo 5% de empate
    
    # Renormalizar
    total = p1_adj + px_adj + p2_adj
    return (
        round(p1_adj / total * 100, 1),
        round(px_adj / total * 100, 1),
        round(p2_adj / total * 100, 1)
    )


# ═══════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

def main():
    print("\n🚀 MEJORAS AVANZADAS AL MODELO")
    print("="*55)

    # ── Cargar datos ──
    df_hist = pd.read_csv(os.path.join(RAIZ, 'Data', 'datos_historicos.csv'))
    df_pred = pd.read_csv(os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv'))
    
    print(f"✅ Histórico: {len(df_hist)} partidos")
    print(f"✅ Predicciones: {len(df_pred)} partidos")

    # ══════════════════════════════════════════
    # MEJORA 1: Decaimiento temporal + Forma
    # ══════════════════════════════════════════
    print("\n📉 MEJORA 1 — Decaimiento temporal + Forma reciente")
    print("-"*50)

    # Calcular pesos temporales para histórico
    df_hist['peso_temporal'] = df_hist['Fecha'].apply(calcular_peso_temporal)
    df_hist.to_csv(os.path.join(RAIZ, 'Data', 'datos_historicos_ponderados.csv'),
                   index=False, encoding='utf-8-sig')
    
    prom_peso = df_hist['peso_temporal'].mean()
    print(f"✅ Peso promedio del histórico: {prom_peso:.3f}")
    print(f"   → Partidos de 2021: peso ~{calcular_peso_temporal('2021-06-01'):.3f}")
    print(f"   → Partidos de 2023: peso ~{calcular_peso_temporal('2023-06-01'):.3f}")
    print(f"   → Partidos de 2025: peso ~{calcular_peso_temporal('2025-06-01'):.3f}")
    print(f"   → Partidos de hoy:  peso ~1.000")

    # Calcular forma de equipos del Mundial
    print("\n📊 Calculando forma reciente de selecciones...")
    equipos_mundial = list(set(
        df_pred['Local'].tolist() + df_pred['Visitante'].tolist()
    ))
    
    forma_equipos = {}
    for eq in equipos_mundial:
        forma = calcular_forma_equipo(df_hist, eq)
        forma_equipos[eq] = forma
    
    with open(os.path.join(RAIZ, 'Data', 'forma_equipos.json'), 'w', encoding='utf-8') as f:
        json.dump(forma_equipos, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Forma calculada para {len(forma_equipos)} equipos")

    # Mostrar ejemplos
    print("\n   Forma reciente de equipos de hoy:")
    hoy_str = date.today().strftime('%Y-%m-%d')
    hoy_pred = df_pred[df_pred['Fecha'] == hoy_str]
    for _, r in hoy_pred.iterrows():
        fl = forma_equipos.get(r['Local'], {})
        fv = forma_equipos.get(r['Visitante'], {})
        factor = factor_forma(fl, fv) if fl and fv else 0
        tend_l = fl.get('tendencia', '?')
        tend_v = fv.get('tendencia', '?')
        print(f"   ⚽ {r['Local']} ({tend_l}) vs {r['Visitante']} ({tend_v})")
        print(f"      Factor ajuste forma: {factor:+.4f} ({'favorece local' if factor > 0 else 'favorece visitante' if factor < 0 else 'neutro'})")

    # Aplicar ajuste de forma a predicciones
    filas_ajustadas = []
    for _, r in df_pred.iterrows():
        fl = forma_equipos.get(r['Local'],    {})
        fv = forma_equipos.get(r['Visitante'], {})
        
        p1 = float(r['Prob_1_Final'])
        px = float(r['Prob_X_Final'])
        p2 = float(r['Prob_2_Final'])
        
        if fl and fv:
            factor = factor_forma(fl, fv)
            # Ajustar probabilidades con factor de forma
            p1_adj = p1 * (1 + factor)
            p2_adj = p2 * (1 - factor * 0.5)
            px_adj = 100 - p1_adj - p2_adj
            px_adj = max(5, px_adj)
            total  = p1_adj + px_adj + p2_adj
            p1_f   = round(p1_adj / total * 100, 1)
            px_f   = round(px_adj / total * 100, 1)
            p2_f   = round(p2_adj / total * 100, 1)
        else:
            p1_f, px_f, p2_f = p1, px, p2
            factor = 0

        fila = r.to_dict()
        fila['Prob_1_Forma'] = p1_f
        fila['Prob_X_Forma'] = px_f
        fila['Prob_2_Forma'] = p2_f
        fila['Factor_Forma'] = factor
        fila['Tendencia_Local']    = fl.get('tendencia', 'sin_datos')
        fila['Tendencia_Visitante'] = fv.get('tendencia', 'sin_datos')
        fila['Racha_Local']    = fl.get('racha', 0)
        fila['Racha_Visitante'] = fv.get('racha', 0)
        filas_ajustadas.append(fila)

    df_ajustado = pd.DataFrame(filas_ajustadas)
    # Actualizar columnas finales
    df_ajustado['Prob_1_Final'] = df_ajustado['Prob_1_Forma']
    df_ajustado['Prob_X_Final'] = df_ajustado['Prob_X_Forma']
    df_ajustado['Prob_2_Final'] = df_ajustado['Prob_2_Forma']

    # ══════════════════════════════════════════
    # MEJORA 2: EV Tracking + CLV
    # ══════════════════════════════════════════
    print("\n💰 MEJORA 2 — EV Tracking + Closing Line Value (Pinnacle)")
    print("-"*50)

    cuotas_raw = obtener_cuotas_actuales()
    print(f"✅ Cuotas Pinnacle obtenidas: {len(cuotas_raw)} partidos")

    df_ev = calcular_ev_todos_partidos(df_ajustado, cuotas_raw)
    df_ev.to_csv(
        os.path.join(RAIZ, 'Predicciones', 'ev_tracking.csv'),
        index=False, encoding='utf-8-sig'
    )

    # Mostrar partidos con value
    value_hoy = df_ev[
        (df_ev['Fecha'] == hoy_str) &
        (df_ev['EV_Categoria'].isin(['alto', 'medio', 'leve']))
    ]
    if len(value_hoy) > 0:
        print(f"\n   🎯 Partidos con VALUE hoy ({hoy_str}):")
        for _, r in value_hoy.iterrows():
            print(f"   {r['EV_Etiqueta']} {r['Local']} vs {r['Visitante']}")
            print(f"      Mejor resultado: {r['Mejor_resultado']} | EV: {r['Mejor_EV']:+.3f}")
            if r['CLV_1']:
                print(f"      CLV (1): {r['CLV_1']:+.1f}% vs Pinnacle")
    else:
        print("   → Sin partidos con value detectado hoy (cuotas Pinnacle no disponibles o sin edge)")

    # ══════════════════════════════════════════
    # MEJORA 3: Factor de ausencias
    # ══════════════════════════════════════════
    print("\n🏥 MEJORA 3 — Factor de ausencias por jugadores clave")
    print("-"*50)
    print("   (Sistema configurado — actívalo indicando ausencias manualmente)")
    print("\n   Ejemplo de uso:")
    print("   Si Haaland no juega en Noruega:")
    factor = calcular_factor_ausencia('Noruega', ['Erling Haaland'])
    print(f"   → Factor Noruega sin Haaland: {factor} ({round((1-factor)*100)}% de penalización)")
    
    factor2 = calcular_factor_ausencia('Francia', ['Kylian Mbappé'])
    print(f"   → Factor Francia sin Mbappé: {factor2} ({round((1-factor2)*100)}% de penalización)")

    # ══════════════════════════════════════════
    # Guardar predicciones mejoradas
    # ══════════════════════════════════════════
    salida = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
    df_ajustado.to_csv(salida, index=False, encoding='utf-8-sig')

    print(f"\n{'='*55}")
    print(f"✅ TODAS LAS MEJORAS APLICADAS")
    print(f"   📄 predicciones_finales.csv actualizado")
    print(f"   📄 ev_tracking.csv generado")
    print(f"   📄 forma_equipos.json generado")
    print(f"   📄 datos_historicos_ponderados.csv generado")
    print(f"   Fecha: {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')}")


if __name__ == '__main__':
    main()
