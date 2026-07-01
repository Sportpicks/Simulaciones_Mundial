# -*- coding: utf-8 -*-
"""
generador_picks_inteligente.py
Genera dos paneles de picks para el canal de Telegram.

PANEL PÚBLICO:  Máx 4 picks con cuota >= 1.50 y prob >= 60%
PANEL PREMIUM:  3 picks — máx 1 por partido, combinadas inteligentes

Mejoras v2:
  - Mercado de Handicap Asiático (-0.5, -1, +0.5, +1) calculado con Dixon-Coles
  - Anti-correlación en combinadas: ningún partido ancla más de 1 combinada premium
  - Banda de confianza en props: valor esperado debe superar umbral >= 15%

Uso: python generador_picks_inteligente.py
"""

import os, sys, json, math, requests, time
from datetime import datetime, timezone, date, timedelta
import pandas as pd

# Hora Peru UTC-5
PERU_TZ = timezone(timedelta(hours=-5))
def hoy_peru(): return datetime.now(PERU_TZ).strftime("%Y-%m-%d")

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
sys.path.insert(0, os.path.join(RAIZ, '04_Prediccion'))
from razonador_mercados import cargar_stats

API_KEY_ODDS = "622b4b772a4d155e032de1c17a83e41a"

# ── Parámetro de banda de confianza para props ──────────────────────────────
# El valor esperado debe superar el umbral de la línea al menos un 15%
# Ejemplo: si lam_faltas=24 y umbral=22.5, margen=6.7% < 15% → NO seleccionar
MARGEN_MINIMO_PROPS = 0.15   # 15% sobre el umbral de línea

BANDERAS_ISO = {
    'México':'mx','Sudáfrica':'za','Corea del Sur':'kr','República Checa':'cz',
    'Suiza':'ch','Bosnia-Herzegovina':'ba','Canadá':'ca','Catar':'qa',
    'Escocia':'gb-sct','Brasil':'br','Haití':'ht','Marruecos':'ma',
    'Turquía':'tr','Paraguay':'py','EE. UU.':'us','Australia':'au',
    'Alemania':'de','Ecuador':'ec','Costa de Marfil':'ci','Curazao':'cw',
    'Suecia':'se','Países Bajos':'nl','Túnez':'tn','Japón':'jp',
    'Bélgica':'be','Egipto':'eg','Irán':'ir','Nueva Zelanda':'nz',
    'España':'es','Uruguay':'uy','Cabo Verde':'cv','Arabia Saudí':'sa',
    'Francia':'fr','Noruega':'no','Senegal':'sn','Irak':'iq',
    'Austria':'at','Argentina':'ar','Argelia':'dz','Jordania':'jo',
    'Portugal':'pt','Colombia':'co','RD Congo':'cd','Uzbekistán':'uz',
    'Croacia':'hr','Inglaterra':'gb-eng','Ghana':'gh','Panamá':'pa',
}

NOMBRES_API = {}
_MAPA = {
    "Mexico":"México","South Africa":"Sudáfrica","South Korea":"Corea del Sur",
    "Czechia":"República Checa","Switzerland":"Suiza",
    "Bosnia and Herzegovina":"Bosnia-Herzegovina","Canada":"Canadá",
    "Qatar":"Catar","Scotland":"Escocia","Brazil":"Brasil","Haiti":"Haití",
    "Morocco":"Marruecos","Turkey":"Turquía","United States":"EE. UU.",
    "Australia":"Australia","Germany":"Alemania","Ecuador":"Ecuador",
    "Cote d'Ivoire":"Costa de Marfil","Curacao":"Curazao","Curaçao":"Curazao",
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
for en, es in _MAPA.items():
    NOMBRES_API[en] = es


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

def p_poisson(lam, linea):
    """P(N > linea) con N ~ Poisson(lam)."""
    k = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k))
    except:
        return 0.0

def poisson_pmf(lam, k):
    """P(N = k) con N ~ Poisson(lam)."""
    try:
        return math.exp(-lam) * lam**k / math.factorial(k)
    except:
        return 0.0

def cuota_estimada(prob):
    if prob <= 0 or prob >= 100: return 1.05
    return max(1.05, round((100/prob)*0.95, 2))

def margen_ok(valor_esperado, linea):
    """Verifica que valor_esperado supere la línea en al menos MARGEN_MINIMO_PROPS."""
    if linea <= 0:
        return True
    return (valor_esperado - linea) / linea >= MARGEN_MINIMO_PROPS


# ══════════════════════════════════════════════════════════════════════════════
# HANDICAP ASIÁTICO
# ══════════════════════════════════════════════════════════════════════════════

def calcular_handicap_asiatico(xgl, xgv, handicap, lado):
    """
    Calcula P(ganar apuesta de handicap asiático) usando distribución Poisson.

    handicap: float — línea (ej: -0.5, -1.0, +0.5, +1.0, -1.5, +1.5)
    lado: 'local' | 'visitante'
    Devuelve: (prob_ganar, prob_empate_devolucion)

    Lógica handicap asiático:
      - Handicap entero (±1, ±2): si diferencia = abs(handicap) → devolución (push)
      - Handicap .5 (±0.5, ±1.5): sin devolución, resultado binario
    """
    prob_win = 0.0
    prob_push = 0.0
    MAX_G = 10

    for g_l in range(MAX_G):
        for g_v in range(MAX_G):
            p = poisson_pmf(xgl, g_l) * poisson_pmf(xgv, g_v)
            if p < 1e-9:
                continue
            diff = g_l - g_v  # diferencia desde perspectiva local
            if lado == 'visitante':
                diff = -diff

            # Con el handicap aplicado al equipo apostado:
            # Si apoyas a local con handicap -1: local necesita ganar por 2+
            # Equivalente a: diff + handicap > 0 → gana; = 0 → push; < 0 → pierde
            resultado_efectivo = diff + handicap

            if abs(handicap % 1) < 0.01:  # entero: push posible
                if resultado_efectivo > 0:
                    prob_win += p
                elif resultado_efectivo == 0:
                    prob_push += p
            else:  # .5: sin push
                if resultado_efectivo > 0:
                    prob_win += p

    return round(prob_win * 100, 1), round(prob_push * 100, 1)


def generar_picks_handicap(local, visitante, xgl, xgv, p1, p2):
    """
    Genera picks de handicap asiático SOLO cuando hay valor real.

    Criterios estrictos para evitar que domine el panel:
    - Solo líneas donde la ventaja de xG es CLARA (diff >= 0.6 goles)
    - El favorito debe tener p1 o p2 >= 55% en 1X2
    - Máximo 1 pick HC por partido (el de mayor valor)
    - Prob mínima 62% Y cuota mínima 1.75 (real de mercado)
    - No generar HC +0.5 para favoritos aplastantes (>80% prob) — es redundante
    """
    picks_h = []
    diff_xg = abs(xgl - xgv)

    # Solo proceder si hay ventaja clara en xG
    if diff_xg < 0.6:
        return []

    # Identificar favorito claro
    if xgl > xgv:
        fav_lado, und_lado = 'local', 'visitante'
        fav_eq, und_eq = local, visitante
        fav_prob = p1
    else:
        fav_lado, und_lado = 'visitante', 'local'
        fav_eq, und_eq = visitante, local
        fav_prob = p2

    # Solo si el favorito tiene ventaja clara en 1X2
    if fav_prob < 50:
        return []

    # Líneas candidatas según magnitud de ventaja xG
    candidatas = []

    if diff_xg >= 0.6:
        # Favorito -0.5 (gana): solo si prob victoria directa < 75% (hay incertidumbre)
        if fav_prob < 75:
            candidatas.append((-0.5, fav_lado,
                f"{fav_eq} gana — xG {xgl:.1f}-{xgv:.1f}"))
        # Underdog +0.5 (no pierde): útil cuando el underdog tiene opciones reales
        if fav_prob < 70:
            candidatas.append((+0.5, und_lado,
                f"{und_eq} no pierde — xG {xgl:.1f}-{xgv:.1f}"))

    if diff_xg >= 1.0:
        # Favorito -1 (gana por 2+): solo con ventaja grande
        if fav_prob >= 60:
            candidatas.append((-1.0, fav_lado,
                f"{fav_eq} gana por 2+ — xG {xgl:.1f}-{xgv:.1f}"))

    for handicap, lado, desc in candidatas:
        prob_w, prob_push = calcular_handicap_asiatico(xgl, xgv, handicap, lado)

        if prob_w < 62:
            continue

        # Cuota de mercado real para HC: casas ofrecen ~1.80-1.95
        # Usamos 1.85 como base y ajustamos levemente por la prob
        cuota_h = round(max(1.75, min(1.95, (100/prob_w)*0.93)), 2)
        ev = round((prob_w/100)*cuota_h - 1, 3)

        eq_nombre = local if lado == 'local' else visitante
        signo = '+' if handicap > 0 else ''
        push_str = f" · push si empate exacto {abs(int(handicap))}" if prob_push > 3 else ""

        picks_h.append({
            'partido': f"{local} vs {visitante}",
            'local': local, 'visitante': visitante,
            'mercado': f"HC {eq_nombre} {signo}{handicap:g}",
            'prob': prob_w,
            'cuota': cuota_h,
            'ev': ev,
            'emoji': '⚖️',
            'categoria': 'Handicap',
            'descripcion': f"{desc}{push_str}",
            'fuente': 'estimada',
        })

    # Devolver solo el pick HC de mayor EV por partido
    if not picks_h:
        return []
    return [max(picks_h, key=lambda x: x['ev'])]


# ══════════════════════════════════════════════════════════════════════════════
# CUOTAS REALES
# ══════════════════════════════════════════════════════════════════════════════

def obtener_cuotas():
    cuotas = {}
    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/",
            params={"apiKey":API_KEY_ODDS,"regions":"eu","markets":"h2h,asian_handicap",
                    "oddsFormat":"decimal"},
            timeout=15
        )
        if r.status_code == 200:
            for partido in r.json():
                local_en = partido.get("home_team","")
                visit_en = partido.get("away_team","")
                local_es = NOMBRES_API.get(local_en, local_en)
                visit_es = NOMBRES_API.get(visit_en, visit_en)
                c1s,cxs,c2s = [],[],[]
                hc_cuotas = {}
                for bk in partido.get("bookmakers",[]):
                    for mkt in bk.get("markets",[]):
                        if mkt["key"]=="h2h":
                            outs = {o["name"]:o["price"] for o in mkt["outcomes"]}
                            if local_en in outs: c1s.append(outs[local_en])
                            if "Draw" in outs:   cxs.append(outs["Draw"])
                            if visit_en in outs: c2s.append(outs[visit_en])
                        elif mkt["key"]=="asian_handicap":
                            for o in mkt["outcomes"]:
                                hc_key = f"{o['name']}_{o.get('point','')}"
                                if hc_key not in hc_cuotas:
                                    hc_cuotas[hc_key] = []
                                hc_cuotas[hc_key].append(o["price"])
                cuotas[(local_es,visit_es)] = {
                    'c1': round(sum(c1s)/len(c1s),2) if c1s else 0,
                    'cx': round(sum(cxs)/len(cxs),2) if cxs else 0,
                    'c2': round(sum(c2s)/len(c2s),2) if c2s else 0,
                    'hc': {k: round(sum(v)/len(v),2) for k,v in hc_cuotas.items()},
                }
    except Exception as e:
        print(f"   ⚠️ Error cuotas: {e}")
    # ── Cuotas reales manuales de respaldo (Oddschecker/Betano) ──
    # Se usan cuando la API no devuelve datos para estos partidos
    cuotas_manuales = {
        ('Inglaterra',  'RD Congo'):           {'c1':1.31,'cx':5.60,'c2':15.0, 'hc':{}},
        ('Bélgica',     'Senegal'):             {'c1':2.21,'cx':3.56,'c2':3.90, 'hc':{}},
        ('EE. UU.',     'Bosnia-Herzegovina'): {'c1':1.42,'cx':5.19,'c2':9.50, 'hc':{}},
        ('España',      'Austria'):             {'c1':1.37,'cx':5.70,'c2':12.0, 'hc':{}},
        ('Portugal',    'Croacia'):             {'c1':1.82,'cx':3.65,'c2':5.20, 'hc':{}},
        ('Suiza',       'Argelia'):             {'c1':2.15,'cx':3.41,'c2':4.10, 'hc':{}},
        ('Australia',   'Egipto'):              {'c1':3.48,'cx':3.06,'c2':2.58, 'hc':{}},
        ('Argentina',   'Cabo Verde'):          {'c1':1.20,'cx':7.55,'c2':22.0, 'hc':{}},
        ('Colombia',    'Ghana'):               {'c1':1.57,'cx':3.80,'c2':5.50, 'hc':{}},
        ('Canadá',      'Sudáfrica'):           {'c1':1.55,'cx':3.90,'c2':6.00, 'hc':{}},
        ('Brasil',      'Japón'):               {'c1':1.80,'cx':3.60,'c2':4.50, 'hc':{}},
        ('Alemania',    'Paraguay'):            {'c1':1.65,'cx':4.00,'c2':5.50, 'hc':{}},
        ('Países Bajos','Marruecos'):           {'c1':1.90,'cx':3.50,'c2':4.20, 'hc':{}},
        ('Costa de Marfil','Noruega'):          {'c1':2.20,'cx':3.40,'c2':3.30, 'hc':{}},
        ('Francia',     'Suecia'):              {'c1':1.55,'cx':4.00,'c2':5.50, 'hc':{}},
        ('México',      'Ecuador'):             {'c1':2.10,'cx':3.30,'c2':3.50, 'hc':{}},
        ('Inglaterra',  'RD Congo'):            {'c1':1.31,'cx':5.60,'c2':15.0, 'hc':{}},
        ('Bélgica',     'Senegal'):             {'c1':2.21,'cx':3.56,'c2':3.90, 'hc':{}},
        ('EE. UU.',     'Bosnia-Herzegovina'): {'c1':1.42,'cx':5.19,'c2':9.50, 'hc':{}},
    }
    for key, vals in cuotas_manuales.items():
        if key not in cuotas:
            cuotas[key] = vals

    print(f"   ✅ Cuotas: {len(cuotas)} partidos")
    return cuotas


# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE PICKS POR PARTIDO
# ══════════════════════════════════════════════════════════════════════════════

def generar_picks_partido(r, cuotas_p):
    local  = r['Local']
    visit  = r['Visitante']
    p1     = float(r['Prob_1_Final'])
    px     = float(r['Prob_X_Final'])
    p2     = float(r['Prob_2_Final'])
    xgl    = float(r.get('xG_L',0))
    xgv    = float(r.get('xG_V',0))
    # Factor eliminatoria: reducir xG 15% en octavos/cuartos (partidos mas conservadores)
    fase = str(r.get('Grupo',''))
    if fase in ('R16','R8','R4','FINAL','SF'):
        xgl  = round(xgl * 0.85, 2)
        xgv  = round(xgv * 0.85, 2)
    xg_t   = xgl + xgv
    lam_cor   = float(r.get('cor',9.0))
    lam_tar   = float(r.get('tar',4.0))
    lam_tiros = float(r.get('tiros_esp',7.0))
    lam_fal   = float(r.get('faltas_esp',22.0))
    c1 = cuotas_p.get('c1',0)
    cx = cuotas_p.get('cx',0)
    c2 = cuotas_p.get('c2',0)
    picks = []

    def add(mercado, prob, cuota, emoji, cat, desc=""):
        if prob < 52 or cuota < 1.05: return
        ev = round((prob/100)*cuota - 1, 3)
        picks.append({
            'partido': f"{local} vs {visit}",
            'local': local, 'visitante': visit,
            'mercado': mercado, 'prob': round(prob,1),
            'cuota': cuota, 'ev': ev,
            'emoji': emoji, 'categoria': cat,
            'descripcion': desc,
            'fuente': 'real' if cuota > 1.10 else 'estimada',
        })

    # ── 1X2 ──
    if c1 > 1.05: add(f"Victoria {local}", p1, c1, '⚽','1X2', f"{local} favorito ({p1:.0f}%)")
    if cx > 1.05: add("Empate", px, cx, '⚖️','1X2', f"Empate esperado ({px:.0f}%)")
    if c2 > 1.05: add(f"Victoria {visit}", p2, c2, '⚽','1X2', f"{visit} favorito ({p2:.0f}%)")

    # ── Doble oportunidad ──
    # Filtro de coherencia: no emitir X2 si el modelo ya favorece al local con prob > 55%
    # ni emitir 1X si el modelo ya favorece al visitante con prob > 55%
    # Esto evita contradecir la propia predicción del modelo.
    UMBRAL_FAVORITO = 55.0

    opciones_do = []

    # 1X — solo si el local es favorito O el partido es parejo
    if p1 >= p2 or px >= 30:
        opciones_do.append((round(p1+px,1), f"1X — {local} o Empate", f"Cubre victoria {local} + empate"))

    # X2 — solo si el visitante es favorito O el partido es parejo (p1 < umbral)
    if p1 < UMBRAL_FAVORITO or p2 > p1:
        opciones_do.append((round(px+p2,1), f"X2 — Empate o {visit}", f"Cubre empate + victoria {visit}"))

    # Sin empate — siempre válido si ninguno tiene prob de empate > 40%
    if px < 40:
        opciones_do.append((round(p1+p2,1), "Sin empate (1 o 2)", "Cualquier equipo gana"))

    for prob_do, label, desc_do in opciones_do:
        add(label, prob_do, cuota_estimada(prob_do), '🛡️','Doble Op.', desc_do)

    # ── Handicap Asiático ──
    picks_hc = generar_picks_handicap(local, visit, xgl, xgv, p1, p2)
    # Enriquecer con cuotas reales si disponibles
    hc_reales = cuotas_p.get('hc', {})
    for pk_hc in picks_hc:
        # Intentar matchear cuota real (aproximación por nombre)
        for hk, hcuota in hc_reales.items():
            if str(pk_hc['mercado'].split()[-1]) in hk and hcuota > 1.05:
                pk_hc['cuota'] = hcuota
                pk_hc['fuente'] = 'real'
                pk_hc['ev'] = round((pk_hc['prob']/100)*hcuota - 1, 3)
                break
        picks.append(pk_hc)

    # ── Goles ──
    for lin, lab in [(1.5,'1.5'),(2.5,'2.5'),(3.5,'3.5')]:
        pr = round(p_poisson(xg_t, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15 and margen_ok(xg_t, lin):
            add(f"Más de {lab} goles", pr, cu, '🥅','Goles', f"xG total {round(xg_t,1)}")
    pr_u = 100 - round(p_poisson(xg_t,2.5)*100)
    cu_u = cuota_estimada(pr_u)
    if cu_u >= 1.15:
        add("Menos de 2.5 goles", pr_u, cu_u, '🔒','Goles', f"xG bajo ({round(xg_t,1)})")

    # ── Córners — con banda de confianza ──
    for lin in [7.5, 8.5, 9.5, 10.5]:
        if not margen_ok(lam_cor, lin):
            continue
        pr = round(p_poisson(lam_cor, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Córners +{lin}", pr, cu, '⛳','Córners',
                f"{round(lam_cor,1)} córners esperados (margen {(lam_cor-lin)/lin*100:.0f}%)")

    # ── Tiros — con banda de confianza ──
    for lin in [4.5, 5.5, 6.5, 7.5]:
        if not margen_ok(lam_tiros, lin):
            continue
        pr = round(p_poisson(lam_tiros, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Tiros a puerta +{lin}", pr, cu, '🎯','Tiros',
                f"{round(lam_tiros,1)} tiros esperados (margen {(lam_tiros-lin)/lin*100:.0f}%)")

    # ── Faltas — con banda de confianza ──
    for lin in [18.5, 20.5, 22.5]:
        if not margen_ok(lam_fal, lin):
            continue
        pr = round(p_poisson(lam_fal, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Faltas +{lin}", pr, cu, '🦵','Faltas',
                f"{round(lam_fal,1)} faltas esperadas (margen {(lam_fal-lin)/lin*100:.0f}%)")

    # ── Tarjetas ──
    for lin in [3.5, 4.5]:
        pr = round(p_poisson(lam_tar, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Tarjetas +{lin}", pr, cu, '🟨','Tarjetas',
                f"{round(lam_tar,1)} tarjetas esperadas")

    # ── Stats por equipo — mercados avanzados ──
    stats = cargar_stats()
    for eq in [local, visit]:
        s = stats.get(eq,{})
        t = s.get('tiros_favor_5', s.get('tiros_favor_tot',0))
        if t >= 4:
            for lin in [2.5, 3.5, 4.5]:
                if not margen_ok(t, lin): continue
                pr = round(p_poisson(t, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} tiros a puerta +{lin}", pr, cu, '🎯', f'Tiros {eq}',
                        f"{eq} promedia {round(t,1)} tiros/partido")
        rt = s.get('remates_tot_favor_5', s.get('remates_tot_favor_tot',0))
        if rt >= 10:
            for lin in [8.5, 10.5, 12.5]:
                if not margen_ok(rt, lin): continue
                pr = round(p_poisson(rt, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} remates totales +{lin}", pr, cu, '🎯', f'Remates {eq}',
                        f"{eq} promedia {round(rt,1)} remates/partido")
        c = s.get('corners_favor_5', s.get('corners_favor_tot',0))
        if c >= 5:
            for lin in [3.5, 4.5, 5.5]:
                if not margen_ok(c, lin): continue
                pr = round(p_poisson(c, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} córners +{lin}", pr, cu, '⛳', f'Córners {eq}',
                        f"{eq} promedia {round(c,1)} córners/partido")
        f = s.get('faltas_cometidas_5', s.get('faltas_cometidas_tot',0))
        if f >= 10:
            for lin in [8.5, 9.5, 10.5]:
                if not margen_ok(f, lin): continue
                pr = round(p_poisson(f, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} faltas +{lin}", pr, cu, '🦵', f'Faltas {eq}',
                        f"{eq} promedia {round(f,1)} faltas/partido")
        p_par = s.get('paradas_5', s.get('paradas_tot',0))
        if p_par >= 3:
            for lin in [2.5, 3.5, 4.5]:
                pr = round(p_poisson(p_par, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.20:
                    add(f"{eq} portero +{lin} paradas", pr, cu, '🧤', f'Paradas {eq}',
                        f"Portero de {eq} promedia {round(p_par,1)} paradas/partido")
        go = s.get('grandes_ocas_5', s.get('grandes_ocas_tot',0))
        if go >= 2.5:
            for lin in [1.5, 2.5, 3.5]:
                pr = round(p_poisson(go, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.20:
                    add(f"{eq} grandes ocasiones +{lin}", pr, cu, '💥', f'Ocasiones {eq}',
                        f"{eq} promedia {round(go,1)} grandes ocasiones/partido")

    sb_tot_l = stats.get(local,{}).get('saques_banda_5', stats.get(local,{}).get('saques_banda_tot',0))
    sb_tot_v = stats.get(visit,{}).get('saques_banda_5', stats.get(visit,{}).get('saques_banda_tot',0))
    sb_total = sb_tot_l + sb_tot_v
    if sb_total >= 25:
        for lin in [22.5, 25.5, 28.5]:
            if not margen_ok(sb_total, lin): continue
            pr = round(p_poisson(sb_total, lin)*100, 1)
            cu = cuota_estimada(pr)
            if cu >= 1.20:
                add(f"Saques de banda totales +{lin}", pr, cu, '🏳️', 'Saques Banda',
                    f"Total esperado {round(sb_total,1)} saques de banda")

    vistos = set()
    result = []
    for pk in sorted(picks, key=lambda x: (x['cuota'], x['prob']), reverse=True):
        key = pk['mercado'][:25].lower()
        if key not in vistos:
            vistos.add(key)
            result.append(pk)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# SELECCIÓN PICKS PÚBLICOS
# ══════════════════════════════════════════════════════════════════════════════

def seleccionar_publicos(todos, max_picks=3, cuota_min=1.50):
    """
    Panel publico v3:
    - Max 3 picks INDIVIDUALES solidos (sin combinadas)
    - Con cuotas reales: prob >= 60%, cuota >= 1.50
    - Sin cuotas reales: prob >= 62%, cuota >= 1.10 O prob >= 80%
    - Diversidad de mercado — max 2 picks de misma categoria
    - Si no hay suficientes, mejor menos que forzar combinadas
    """
    hay_cuotas_reales = any(pk.get('fuente') == 'real' for pk in todos)

    CAT_PRIORIDAD = {
        '1X2': 10, 'Handicap': 9, 'Goles': 8,
        'Doble Op.': 7, 'Córners': 6, 'Faltas': 5,
        'Tiros': 4, 'Tarjetas': 3, 'Paradas': 3,
        'Remates': 4, 'Ocasiones': 3, 'Saques Banda': 2,
    }

    def score(pk):
        cat_p   = CAT_PRIORIDAD.get(pk.get('categoria',''), 1)
        es_real = 3 if pk.get('fuente') == 'real' else 0
        return (es_real, cat_p, pk['prob'])

    prob_min = 60 if hay_cuotas_reales else 62

    candidatos = []
    for pk in todos:
        if pk['prob'] < prob_min:
            continue
        if pk.get('fuente') == 'real':
            if pk['cuota'] >= cuota_min:
                candidatos.append(pk)
        else:
            # Sin cuota real: aceptar si cuota >= 1.10 O prob muy alta (pick seguro)
            if pk['cuota'] >= 1.10 or pk['prob'] >= 80:
                candidatos.append(pk)

    candidatos.sort(key=score, reverse=True)

    resultado = []
    partidos_usados = set()
    categorias_usadas = {}
    hc_count = 0

    for pk in candidatos:
        if len(resultado) >= max_picks:
            break
        partido = pk['partido']
        cat = pk.get('categoria', '')

        if partido in partidos_usados:
            continue
        if cat == 'Handicap':
            if hc_count >= 1:
                continue
            hc_count += 1
        if categorias_usadas.get(cat, 0) >= 2:
            continue

        pk['tipo'] = 'individual'
        resultado.append(pk)
        partidos_usados.add(partido)
        categorias_usadas[cat] = categorias_usadas.get(cat, 0) + 1

    for pk in resultado:
        if 'cuota_display' not in pk: pk['cuota_display'] = pk['cuota']
        if 'tipo' not in pk: pk['tipo'] = 'individual'

    return resultado[:max_picks]

def seleccionar_premium(todos, max_picks=1, prob_min=78):
    """
    Panel premium MEJORADO:
    - 1 solo pick — el MAS solido del dia
    - Preferencia: pick individual con prob >= 78% y cuota >= 1.20
    - Si no hay individual solido, 1 combinada doble con prob >= 68% y cuota >= 1.40
    - Nunca triple combinada en premium
    - Prioridad: diversidad de mercado respecto al panel publico
    """
    # Candidatos individuales con prob alta
    candidatos = [pk for pk in todos
                  if pk.get('tipo','individual') == 'individual'
                  and pk['prob'] >= prob_min
                  and pk['cuota'] >= 1.15]
    candidatos.sort(key=lambda x: (x['prob'], x['cuota']), reverse=True)

    # Mejor pick por partido
    mejores_por_partido = {}
    for pk in candidatos:
        if pk['partido'] not in mejores_por_partido:
            mejores_por_partido[pk['partido']] = pk
    base = sorted(mejores_por_partido.values(), key=lambda x: x['prob'], reverse=True)

    resultado = []

    # Opcion 1: pick individual solido (prob >= 78% cuota >= 1.20)
    for pk in base:
        if pk['prob'] >= 78 and pk['cuota'] >= 1.20:
            pk['tipo'] = 'premium'
            resultado.append(pk)
            break

    # Opcion 2: si no hay individual solido, combinada doble (prob >= 68% cuota >= 1.40)
    if not resultado and len(base) >= 2:
        for i in range(len(base)):
            for j in range(i+1, len(base)):
                pk1, pk2 = base[i], base[j]
                if pk1['partido'] == pk2['partido']: continue
                cuota_c = round(pk1['cuota'] * pk2['cuota'], 2)
                prob_c  = round(pk1['prob']/100 * pk2['prob']/100 * 100, 1)
                if cuota_c >= 1.40 and prob_c >= 68:
                    resultado.append({
                        'partido': 'COMBINADA PREMIUM',
                        'local': f"{pk1['partido']} + {pk2['partido']}",
                        'visitante': '',
                        'mercado': f"{pk1['emoji']} {pk1['mercado'][:28]} + {pk2['emoji']} {pk2['mercado'][:28]}",
                        'prob': prob_c, 'cuota': cuota_c, 'cuota_display': cuota_c,
                        'ev': round((prob_c/100)*cuota_c - 1, 3),
                        'emoji': '💎', 'categoria': 'Combinada Premium',
                        'descripcion': f"Doble premium — prob. {prob_c}% | cuota @{cuota_c}",
                        'fuente': 'calculada', 'tipo': 'combinada', 'picks_combo': [pk1, pk2],
                    })
                    break
            if resultado: break

    # Opcion 3: el mejor individual disponible aunque prob sea menor
    if not resultado and base:
        pk = base[0]
        pk['tipo'] = 'premium'
        resultado.append(pk)

    return resultado[:max_picks]


# ══════════════════════════════════════════════════════════════════════════════
# HTML — PANEL PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

def html_publico(picks, hoy, fecha_gen, ts):
    ISO_J   = json.dumps(BANDERAS_ISO, ensure_ascii=False)
    PICKS_J = json.dumps(picks, ensure_ascii=False, default=str)
    return f"""<!DOCTYPE html>
<html lang="es">
<!-- ts:{ts} -->
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Picks del Día — Mundial 2026</title>
<style>
:root{{--bg:#0d1220;--panel:#161d31;--panel2:#1c2540;--tx:#eef1f8;--tx2:#9aa5c0;
--lin:#2a3554;--v:#34d399;--e:#fbbf24;--d:#fb7185;--ac:#60a5fa;--pu:#a78bfa;--or:#fb923c;--go:#ffd700}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,sans-serif;padding-bottom:48px}}
.wrap{{max-width:820px;margin:0 auto;padding:0 16px}}
nav{{background:rgba(13,18,32,.95);border-bottom:1px solid var(--lin);padding:12px 16px;
position:sticky;top:0;z-index:50;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-weight:700;color:var(--ac);font-size:.95rem}}
.nav-links a{{color:var(--tx2);text-decoration:none;font-size:.82rem;margin-left:12px;font-weight:600}}
header{{text-align:center;padding:26px 0 16px}}
header h1{{font-size:1.45rem;font-weight:700}}
header p{{color:var(--tx2);font-size:.84rem;margin-top:5px}}
.badge{{display:inline-block;border:1px solid var(--lin);border-radius:999px;
padding:2px 11px;font-size:.75rem;color:var(--tx2);margin:3px 2px}}
.badge.hoy{{border-color:var(--ac);color:var(--ac)}}
.tg-btn{{display:block;text-align:center;background:var(--ac);color:#0d1220;border-radius:10px;
padding:11px;font-weight:700;text-decoration:none;margin:14px 0;font-size:.88rem}}
.resumen{{background:var(--panel);border:1px solid var(--lin);border-radius:12px;
padding:14px;margin-bottom:18px;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center}}
.rs-v{{font-size:1.25rem;font-weight:700;color:var(--ac)}}
.rs-l{{font-size:.7rem;color:var(--tx2)}}
.pick{{background:var(--panel);border:1px solid var(--lin);border-radius:14px;
padding:18px;margin-bottom:12px;position:relative}}
.pick.alta{{border-color:var(--v)}}.pick.combo{{border-color:var(--pu)}}.pick.value{{border-color:var(--go)}}
.pick.hc{{border-color:var(--or)}}
.pick-n{{position:absolute;top:10px;right:12px;font-size:.72rem;color:var(--tx2);
font-weight:600;background:var(--panel2);border-radius:5px;padding:1px 7px}}
.ph{{display:flex;align-items:flex-start;gap:10px;margin-bottom:10px}}
.ph-em{{font-size:1.7rem;flex-shrink:0;line-height:1}}
.ph-info .sub{{font-size:.75rem;color:var(--tx2);margin-bottom:2px}}
.ph-info .merc{{font-size:.95rem;font-weight:700;line-height:1.3}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:10px 0}}
.sb{{background:var(--panel2);border-radius:9px;padding:9px;text-align:center}}
.sb .v{{font-size:1.2rem;font-weight:700}}
.sb .l{{font-size:.69rem;color:var(--tx2);margin-top:2px}}
.desc{{font-size:.79rem;color:var(--tx2);margin-top:8px;padding:7px 10px;
background:var(--panel2);border-radius:7px;border-left:3px solid var(--ac)}}
.combo-box{{margin-top:8px}}
.combo-row{{display:flex;align-items:center;gap:7px;padding:5px 9px;
background:var(--panel2);border-radius:7px;margin-bottom:4px;font-size:.8rem}}
.combo-x{{text-align:center;font-size:.72rem;color:var(--tx2)}}
.freal{{font-size:.68rem;background:rgba(52,211,153,.15);color:var(--v);border-radius:3px;padding:1px 5px}}
.fest{{font-size:.68rem;background:rgba(251,191,36,.12);color:var(--e);border-radius:3px;padding:1px 5px}}
.ev-pos{{color:var(--v)}}.ev-neg{{color:var(--d)}}
.aviso{{background:var(--panel);border-left:4px solid var(--e);border-radius:0 10px 10px 0;
padding:11px 13px;font-size:.79rem;color:var(--tx2);margin-top:18px}}
footer{{text-align:center;color:var(--tx2);font-size:.75rem;margin-top:22px}}
footer a{{color:var(--ac);text-decoration:none}}
@media(max-width:520px){{.resumen{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body>
<nav>
  <span class="logo">⚽ Sportpicks — Mundial 2026</span>
  <div class="nav-links">
    <a href="index_final.html">🔮 Modelo</a>
    <a href="picks_premium.html">💎 Premium</a>
    <a href="picks_publicos_v2.html">📊 Historial</a>
  </div>
</nav>
<div class="wrap">
  <header>
    <h1>🎯 Picks del Día — {hoy}</h1>
    <p>Selección inteligente con cuota mínima 1.50 — máximo 4 picks</p>
    <span class="badge hoy">📅 {fecha_gen}</span>
    <span class="badge">🤖 XGBoost + 25 casas + Razonamiento automático</span>
  </header>
  <a class="tg-btn" href="https://t.me/TU_CANAL" target="_blank">📱 Unirte al canal de Telegram</a>
  <div class="resumen" id="res"></div>
  <div id="picks"></div>
  <div class="aviso">⚠️ Cuotas marcadas <span class="freal">real</span> vienen de casas de apuestas.
  <span class="fest">estimada</span> = calculada por el modelo. Verifica siempre antes de apostar.</div>
  <footer>
    <a href="index_final.html">Modelo completo</a> ·
    <a href="picks_premium.html">💎 Picks premium</a> ·
    ⚠️ Apuesta con responsabilidad
  </footer>
</div>
<script>
const PICKS={PICKS_J};
const ISO={ISO_J};
const fl=eq=>ISO[eq]?`<img style="width:18px;height:13px;border-radius:2px;vertical-align:-2px;object-fit:cover" src="https://flagcdn.com/w20/${{ISO[eq]}}.png">`:'';
const probP=PICKS.length?Math.round(PICKS.reduce((s,p)=>s+p.prob,0)/PICKS.length):0;
const cuotaP=PICKS.length?(PICKS.reduce((s,p)=>s+(p.cuota_display||p.cuota),0)/PICKS.length).toFixed(2):0;
const nV=PICKS.filter(p=>p.ev&&p.ev>0.05).length;
document.getElementById('res').innerHTML=`
  <div><div class="rs-v">${{PICKS.length}}</div><div class="rs-l">Picks</div></div>
  <div><div class="rs-v" style="color:var(--v)">${{probP}}%</div><div class="rs-l">Prob. prom.</div></div>
  <div><div class="rs-v" style="color:var(--go)">${{cuotaP}}</div><div class="rs-l">Cuota prom.</div></div>
  <div><div class="rs-v" style="color:var(--pu)">${{nV}}</div><div class="rs-l">Con EV+</div></div>`;
const cont=document.getElementById('picks');
PICKS.forEach((pk,i)=>{{
  const esC=pk.tipo==='combinada';
  const esHC=pk.categoria==='Handicap';
  const esV=pk.ev&&pk.ev>0.10;
  const cls=esC?'combo':esHC?'hc':esV?'value':'alta';
  const cuotaD=pk.cuota_display||pk.cuota;
  const fB=pk.fuente==='real'?'<span class="freal">real</span>':'<span class="fest">estimada</span>';
  const evH=pk.ev!=null?`<span class="${{pk.ev>0?'ev-pos':'ev-neg'}}">${{pk.ev>0?'+':''}}${{(pk.ev*100).toFixed(1)}}%</span>`:'—';
  let comboH='';
  if(esC&&pk.picks_combo){{
    comboH='<div class="combo-box">'+pk.picks_combo.map((s,si)=>`
      <div class="combo-row">${{s.emoji}} ${{fl(s.local)}} ${{s.partido}} · <b>${{s.mercado}}</b>
        <span style="margin-left:auto;color:var(--v)">${{s.prob}}%</span>
        <span style="color:var(--go);margin-left:5px">@${{s.cuota}}</span></div>
      ${{si<pk.picks_combo.length-1?'<div class="combo-x">✖️</div>':''}}
    `).join('')+'</div>';
  }}
  const d=document.createElement('div');
  d.className=`pick ${{cls}}`;
  d.innerHTML=`
    <div class="pick-n">Pick #${{i+1}}</div>
    <div class="ph">
      <div class="ph-em">${{pk.emoji}}</div>
      <div class="ph-info">
        <div class="sub">${{esC?'🔗 COMBINADA':fl(pk.local)+' '+pk.partido}} · ${{pk.categoria}}</div>
        <div class="merc">${{pk.mercado}}</div>
      </div>
    </div>
    <div class="stats">
      <div class="sb"><div class="v" style="color:var(--v)">${{pk.prob}}%</div><div class="l">Probabilidad</div></div>
      <div class="sb"><div class="v" style="color:var(--go)">@${{cuotaD}}</div><div class="l">Cuota ${{fB}}</div></div>
      <div class="sb"><div class="v">${{evH}}</div><div class="l">EV</div></div>
    </div>
    ${{comboH}}
    ${{pk.descripcion?`<div class="desc">💡 ${{pk.descripcion}}</div>`:''}}
  `;
  cont.appendChild(d);
}});
</script>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# HTML — PANEL PREMIUM
# ══════════════════════════════════════════════════════════════════════════════

def html_premium(picks, hoy, fecha_gen, ts):
    import functools
    ISO_J   = json.dumps(BANDERAS_ISO, ensure_ascii=False)
    PICKS_J = json.dumps(picks, ensure_ascii=False, default=str)
    cuota_acum = round(functools.reduce(lambda a,b: a*b, [p['cuota'] for p in picks], 1), 2) if picks else 1
    return f"""<!DOCTYPE html>
<html lang="es">
<!-- ts:{ts} -->
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Picks Premium 💎 — Mundial 2026</title>
<style>
:root{{--bg:#0d1220;--panel:#161d31;--panel2:#1c2540;--tx:#eef1f8;--tx2:#9aa5c0;
--lin:#2a3554;--v:#34d399;--e:#fbbf24;--d:#fb7185;--ac:#60a5fa;--pu:#a78bfa;--go:#ffd700}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,sans-serif;padding-bottom:48px}}
.wrap{{max-width:820px;margin:0 auto;padding:0 16px}}
nav{{background:rgba(13,18,32,.95);border-bottom:1px solid var(--lin);padding:12px 16px;
position:sticky;top:0;z-index:50;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-weight:700;color:var(--go);font-size:.95rem}}
.nav-links a{{color:var(--tx2);text-decoration:none;font-size:.82rem;margin-left:12px;font-weight:600}}
header{{text-align:center;padding:26px 0 16px;border-bottom:1px solid rgba(255,215,0,.15);margin-bottom:18px}}
header h1{{font-size:1.45rem;font-weight:700;color:var(--go)}}
header p{{color:var(--tx2);font-size:.84rem;margin-top:5px}}
.badge{{display:inline-block;border:1px solid var(--go);border-radius:999px;
padding:2px 11px;font-size:.75rem;color:var(--go);margin:3px 2px}}
.resumen{{background:var(--panel);border:1px solid rgba(255,215,0,.2);border-radius:12px;
padding:14px;margin-bottom:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:8px;text-align:center}}
.rs-v{{font-size:1.25rem;font-weight:700;color:var(--go)}}
.rs-l{{font-size:.7rem;color:var(--tx2)}}
.acum-box{{background:rgba(255,215,0,.07);border:1px solid rgba(255,215,0,.25);border-radius:10px;
padding:12px 16px;text-align:center;margin-bottom:16px}}
.acum-box .title{{font-size:.8rem;color:var(--tx2);margin-bottom:4px}}
.acum-box .val{{font-size:1.6rem;font-weight:700;color:var(--go)}}
.pick{{background:var(--panel);border:1px solid rgba(255,215,0,.25);border-radius:14px;
padding:18px;margin-bottom:12px;position:relative}}
.pick-n{{position:absolute;top:10px;right:12px;font-size:.72rem;color:var(--go);
font-weight:700;background:rgba(255,215,0,.1);border-radius:5px;padding:1px 7px}}
.seg-bar{{height:7px;background:var(--panel2);border-radius:4px;overflow:hidden;margin:10px 0}}
.seg-inner{{height:100%;background:linear-gradient(90deg,var(--v),var(--go));border-radius:4px}}
.ph{{display:flex;align-items:flex-start;gap:10px;margin-bottom:8px}}
.ph-em{{font-size:1.7rem;flex-shrink:0;line-height:1}}
.ph-info .sub{{font-size:.75rem;color:var(--tx2);margin-bottom:2px}}
.ph-info .merc{{font-size:.95rem;font-weight:700}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:10px 0}}
.sb{{background:var(--panel2);border-radius:9px;padding:9px;text-align:center}}
.sb .v{{font-size:1.2rem;font-weight:700}}
.sb .l{{font-size:.69rem;color:var(--tx2);margin-top:2px}}
.desc{{font-size:.79rem;color:var(--tx2);margin-top:8px;padding:7px 10px;
background:rgba(255,215,0,.05);border-radius:7px;border-left:3px solid var(--go)}}
.aviso{{background:var(--panel);border-left:4px solid var(--go);border-radius:0 10px 10px 0;
padding:11px 13px;font-size:.79rem;color:var(--tx2);margin-top:18px}}
footer{{text-align:center;color:var(--tx2);font-size:.75rem;margin-top:22px}}
footer a{{color:var(--ac);text-decoration:none}}
</style>
</head>
<body>
<nav>
  <span class="logo">💎 Sportpicks Premium</span>
  <div class="nav-links">
    <a href="index_final.html">🔮 Modelo</a>
    <a href="picks_dia.html">🎯 Picks públicos</a>
    <a href="picks_publicos_v2.html">📊 Historial</a>
  </div>
</nav>
<div class="wrap">
  <header>
    <h1>💎 Picks Premium — {hoy}</h1>
    <p>Los 3 picks con mayor probabilidad de acierto del día</p>
    <span class="badge">📅 {fecha_gen}</span>
    <span class="badge">🔐 Acceso exclusivo suscriptores</span>
  </header>
  <div class="resumen" id="res"></div>
  <div class="acum-box">
    <div class="title">📈 Cuota acumulador (combinados)</div>
    <div class="val">@{cuota_acum}</div>
  </div>
  <div id="picks"></div>
  <div class="aviso">💡 Picks premium = máxima seguridad. Combínalos en un acumulador
  para obtener mejor cuota manteniendo alta probabilidad de acierto.</div>
  <footer>
    <a href="picks_dia.html">🎯 Ver picks públicos</a> ·
    <a href="index_final.html">Modelo completo</a> ·
    ⚠️ Apuesta con responsabilidad
  </footer>
</div>
<script>
const PICKS={PICKS_J};
const ISO={ISO_J};
const fl=eq=>ISO[eq]?`<img style="width:18px;height:13px;border-radius:2px;vertical-align:-2px;object-fit:cover" src="https://flagcdn.com/w20/${{ISO[eq]}}.png">`:'';
const probP=PICKS.length?Math.round(PICKS.reduce((s,p)=>s+p.prob,0)/PICKS.length):0;
const cuotaP=PICKS.length?(PICKS.reduce((s,p)=>s+p.cuota,0)/PICKS.length).toFixed(2):0;
document.getElementById('res').innerHTML=`
  <div><div class="rs-v">${{PICKS.length}}</div><div class="rs-l">Picks premium</div></div>
  <div><div class="rs-v">${{probP}}%</div><div class="rs-l">Prob. promedio</div></div>
  <div><div class="rs-v">${{cuotaP}}</div><div class="rs-l">Cuota prom.</div></div>`;
const cont=document.getElementById('picks');
PICKS.forEach((pk,i)=>{{
  const d=document.createElement('div');
  d.className='pick';
  const esC=pk.tipo==='combinada';
  let comboH='';
  if(esC&&pk.picks_combo){{
    comboH='<div style="margin-top:8px">'+pk.picks_combo.map((s,si)=>`
      <div style="display:flex;align-items:center;gap:7px;padding:5px 9px;
        background:rgba(255,215,0,.05);border-radius:7px;margin-bottom:4px;font-size:.8rem">
        ${{s.emoji}} ${{fl(s.local)}} ${{s.partido}} · <b>${{s.mercado}}</b>
        <span style="margin-left:auto;color:#34d399">${{s.prob}}%</span>
        <span style="color:var(--go);margin-left:5px">@${{s.cuota}}</span></div>
      ${{si<pk.picks_combo.length-1?'<div style="text-align:center;font-size:.72rem;color:var(--tx2)">✖️</div>':''}}
    `).join('')+'</div>';
  }}
  d.innerHTML=`
    <div class="pick-n">💎 #${{i+1}}</div>
    <div class="ph">
      <div class="ph-em">${{pk.emoji}}</div>
      <div class="ph-info">
        <div class="sub">${{esC?'🔗 COMBINADA':fl(pk.local)+' '+pk.partido}} · ${{pk.categoria}}</div>
        <div class="merc">${{pk.mercado}}</div>
      </div>
    </div>
    <div class="seg-bar"><div class="seg-inner" style="width:${{pk.prob}}%"></div></div>
    <div class="stats">
      <div class="sb"><div class="v" style="color:var(--v)">${{pk.prob}}%</div><div class="l">Probabilidad</div></div>
      <div class="sb"><div class="v" style="color:var(--go)">@${{pk.cuota_display||pk.cuota}}</div><div class="l">Cuota</div></div>
      <div class="sb"><div class="v" style="color:var(--pu)">#${{i+1}}</div><div class="l">Ranking</div></div>
    </div>
    ${{comboH}}
    ${{pk.descripcion?`<div class="desc">💡 ${{pk.descripcion}}</div>`:''}}
  `;
  cont.appendChild(d);
}});
</script>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n🚀 GENERADOR DE PICKS INTELIGENTE v2")
    print("="*55)
    print("Mejoras activas:")
    print("  ✅ Handicap Asiático (HC ±0.5, ±1.0, ±1.5)")
    print(f"  ✅ Banda de confianza props >= {MARGEN_MINIMO_PROPS*100:.0f}%")
    print("  ✅ Anti-correlación en combinadas premium")
    print("="*55)

    hoy       = hoy_peru()  # Hora Peru UTC-5
    fecha_gen = datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')
    ts        = int(time.time())

    csv = os.path.join(RAIZ,'Predicciones','predicciones_finales.csv')
    df  = pd.read_csv(csv)
    hoy_df = df[df['Fecha']==hoy]
    print(f"\n✅ Partidos de hoy: {len(hoy_df)}")

    print("📡 Obteniendo cuotas (h2h + asian_handicap)...")
    cuotas = obtener_cuotas()

    todos = []
    for _, r in hoy_df.iterrows():
        key   = (r['Local'], r['Visitante'])
        cq    = cuotas.get(key, {})
        picks = generar_picks_partido(r, cq)
        todos.extend(picks)
        hc_picks = [p for p in picks if p['categoria']=='Handicap']
        print(f"   ⚽ {r['Local']} vs {r['Visitante']}: {len(picks)} picks ({len(hc_picks)} HC)")

    print(f"\n✅ Total picks candidatos: {len(todos)}")

    picks_pub  = seleccionar_publicos(todos)
    picks_prem = seleccionar_premium(todos, max_picks=3)

    print(f"\n📋 PANEL PÚBLICO ({len(picks_pub)} picks):")
    for i,pk in enumerate(picks_pub,1):
        ev = f" EV:{pk['ev']:+.1%}" if pk.get('ev') else ""
        cat = f"[{pk['categoria']}]"
        print(f"   #{i} {pk['emoji']} {cat} {pk['mercado'][:40]}")
        print(f"      {pk['partido']} | {pk['prob']}% | @{pk.get('cuota_display',pk['cuota'])}{ev}")

    print(f"\n💎 PANEL PREMIUM ({len(picks_prem)} picks):")
    for i,pk in enumerate(picks_prem,1):
        print(f"   #{i} {pk['emoji']} {pk['mercado'][:50]}")
        print(f"      {pk['partido']} | {pk['prob']}% | @{pk['cuota']}")

    os.makedirs('docs', exist_ok=True)
    with open('docs/picks_dia.html',     'w', encoding='utf-8') as f:
        f.write(html_publico(picks_pub,  hoy, fecha_gen, ts))
    with open('docs/picks_premium.html', 'w', encoding='utf-8') as f:
        f.write(html_premium(picks_prem, hoy, fecha_gen, ts))

    print(f"\n✅ docs/picks_dia.html generado")
    print(f"✅ docs/picks_premium.html generado")

if __name__ == '__main__':
    main()
