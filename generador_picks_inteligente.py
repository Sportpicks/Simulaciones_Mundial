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

API_KEY_ODDS   = "622b4b772a4d155e032de1c17a83e41a"
API_KEY_FDORG  = "cce6c60e411047abb142e005de2d957a"   # football-data.org
API_KEY_APIF   = "2ef79c28645eb3c1041bd8768da83e65"   # API-Football

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
# HISTORIAL H2H — Head to Head entre equipos
# ══════════════════════════════════════════════════════════════════════════════

# Cache para no repetir llamadas
_H2H_CACHE = {}

# Mapa de nombres español → ID football-data.org
FDORG_IDS = {
    'Portugal': 765, 'Croacia': 799, 'España': 760, 'Austria': 775,
    'Suiza': 788, 'Argelia': 1780, 'Francia': 773, 'Suecia': 784,
    'Brasil': 764, 'Japón': 827, 'Alemania': 759, 'Paraguay': 833,
    'Países Bajos': 779, 'Marruecos': 1819, 'Costa de Marfil': 1825,
    'Noruega': 779, 'México': 764, 'Ecuador': 839, 'Inglaterra': 770,
    'RD Congo': 1879, 'Bélgica': 805, 'Senegal': 1825, 'EE. UU.': 762,
    'Bosnia-Herzegovina': 1658, 'Argentina': 762, 'Cabo Verde': 1891,
    'Colombia': 826, 'Ghana': 1832, 'Australia': 825, 'Egipto': 1818,
    'Canadá': 769, 'Sudáfrica': 1835,
}

def obtener_h2h(local, visitante, n=10):
    """
    Obtiene historial H2H entre dos equipos.
    Devuelve dict con:
      - btts_pct: % partidos donde ambos anotaron
      - over25_pct: % partidos con más de 2.5 goles
      - avg_goles: promedio de goles por partido
      - n_partidos: partidos analizados
    """
    key = tuple(sorted([local, visitante]))
    if key in _H2H_CACHE:
        return _H2H_CACHE[key]

    resultado = {'btts_pct': None, 'over25_pct': None, 'avg_goles': None, 'n_partidos': 0}

    try:
        id_l = FDORG_IDS.get(local)
        id_v = FDORG_IDS.get(visitante)
        if not id_l or not id_v:
            return resultado

        r = requests.get(
            f"https://api.football-data.org/v4/teams/{id_l}/matches",
            headers={"X-Auth-Token": API_KEY_FDORG},
            params={"status": "FINISHED", "limit": 30},
            timeout=10
        )
        if r.status_code != 200:
            return resultado

        partidos = r.json().get('matches', [])
        h2h = []
        for p in partidos:
            ht = p.get('homeTeam',{}).get('id')
            at = p.get('awayTeam',{}).get('id')
            if id_v in (ht, at):
                score = p.get('score',{}).get('fullTime',{})
                gl = score.get('home') or 0
                gv = score.get('away') or 0
                h2h.append({'gl': gl, 'gv': gv})

        if len(h2h) >= 3:
            n_real = min(len(h2h), n)
            h2h = h2h[:n_real]
            btts = sum(1 for p in h2h if p['gl'] > 0 and p['gv'] > 0)
            over = sum(1 for p in h2h if p['gl'] + p['gv'] > 2.5)
            total_g = sum(p['gl'] + p['gv'] for p in h2h)
            resultado = {
                'btts_pct':   round(btts/n_real*100, 1),
                'over25_pct': round(over/n_real*100, 1),
                'avg_goles':  round(total_g/n_real, 2),
                'n_partidos': n_real,
            }
    except Exception as e:
        pass

    _H2H_CACHE[key] = resultado
    return resultado


def ajustar_prob_con_h2h(prob_base, h2h, mercado):
    """
    Ajusta la probabilidad del modelo con el historial H2H.
    Solo ajusta si hay >= 5 partidos de H2H.
    Ajuste máximo: ±12 puntos porcentuales.
    """
    if not h2h or h2h['n_partidos'] < 5:
        return prob_base

    if mercado == 'btts':
        hist = h2h['btts_pct']
    elif mercado == 'over25':
        hist = h2h['over25_pct']
    else:
        return prob_base

    if hist is None:
        return prob_base

    # Peso del historial: 30% historial, 70% modelo
    ajustada = round(prob_base * 0.70 + hist * 0.30, 1)
    # Limitar el ajuste a ±12 puntos
    ajustada = max(prob_base - 12, min(prob_base + 12, ajustada))
    return ajustada


# ══════════════════════════════════════════════════════════════════════════════
# CUOTAS REALES
# ══════════════════════════════════════════════════════════════════════════════

def obtener_cuotas():
    cuotas = {}
    try:
        # Llamada 1: h2h + asian_handicap
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/",
            params={"apiKey":API_KEY_ODDS,"regions":"eu",
                    "markets":"h2h,asian_handicap,totals,btts",
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
                totals = {}   # over/under goles: {'over_1.5': [cuotas], 'under_2.5': [...]}
                btts_si = []  # ambos anotan SI
                btts_no = []  # ambos anotan NO
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
                        elif mkt["key"]=="totals":
                            for o in mkt["outcomes"]:
                                linea = o.get("point","")
                                nombre = o.get("name","").lower()
                                key = f"{nombre}_{linea}"
                                if key not in totals:
                                    totals[key] = []
                                totals[key].append(o["price"])
                        elif mkt["key"]=="btts":
                            for o in mkt["outcomes"]:
                                nombre = o.get("name","").lower()
                                if nombre in ("yes","sí","si","ambos anotan"):
                                    btts_si.append(o["price"])
                                elif nombre in ("no","no anotan"):
                                    btts_no.append(o["price"])

                cuotas[(local_es,visit_es)] = {
                    'c1': round(sum(c1s)/len(c1s),2) if c1s else 0,
                    'cx': round(sum(cxs)/len(cxs),2) if cxs else 0,
                    'c2': round(sum(c2s)/len(c2s),2) if c2s else 0,
                    'hc': {k: round(sum(v)/len(v),2) for k,v in hc_cuotas.items()},
                    'totals': {k: round(sum(v)/len(v),2) for k,v in totals.items()},
                    'btts_si': round(sum(btts_si)/len(btts_si),2) if btts_si else 0,
                    'btts_no': round(sum(btts_no)/len(btts_no),2) if btts_no else 0,
                }
    except Exception as e:
        print(f"   ⚠️ Error cuotas: {e}")
    # ── Cuotas reales manuales de respaldo (Oddschecker/Betano) ──
    # Se usan cuando la API no devuelve datos para estos partidos
    cuotas_manuales = {
        # Cuotas 1X2 + totals + btts reales de Betano/Oddschecker
        ('Inglaterra',  'RD Congo'):           {'c1':1.31,'cx':5.60,'c2':15.0,'hc':{},
            'totals':{'over_1.5':1.22,'over_2.5':2.10,'under_2.5':1.72,'under_3.5':1.22,'over_3.5':3.50},'btts_si':3.20,'btts_no':1.30},
        ('Bélgica',     'Senegal'):             {'c1':2.21,'cx':3.56,'c2':3.90,'hc':{},
            'totals':{'over_1.5':1.40,'over_2.5':2.00,'under_2.5':1.80,'over_3.5':3.80,
                      'over_8.5_corners':1.67,'over_9.5_corners':2.10,'over_2.5_cards':1.55},'btts_si':1.76,'btts_no':2.06},
        ('EE. UU.',     'Bosnia-Herzegovina'): {'c1':1.42,'cx':5.19,'c2':9.50,'hc':{},
            'totals':{'over_1.5':1.35,'over_2.5':1.95,'under_2.5':1.85,'over_3.5':3.60},'btts_si':2.80,'btts_no':1.40},
        ('España',      'Austria'):             {'c1':1.37,'cx':5.70,'c2':12.0,'hc':{},
            'totals':{'over_1.5':1.25,'over_2.5':1.90,'under_2.5':1.90,'over_3.5':3.40},'btts_si':3.00,'btts_no':1.33},
        ('Portugal',    'Croacia'):             {'c1':1.82,'cx':3.65,'c2':5.20,'hc':{},
            'totals':{'over_1.5':1.35,'over_2.5':1.85,'under_2.5':1.95,'over_3.5':3.50},
            'btts_si':1.90,'btts_no':1.85},
        # Octavos de final — cuotas reales API + Betano
        ('Portugal',    'España'):              {'c1':4.10,'cx':3.70,'c2':1.93,'hc':{},
            'totals':{'over_1.5':1.55,'over_2.5':1.75,'under_2.5':2.00,'over_3.5':3.80,
                      'over_10.5_corners':1.70,'over_9.5_corners':1.55,'over_2.5_cards':1.90},
            'btts_si':1.85,'btts_no':1.90},  # BTTS real Betano — H2H 100% en 6 partidos
        ('Suiza',       'Argelia'):             {'c1':2.15,'cx':3.41,'c2':4.10,'hc':{},
            'totals':{'over_1.5':1.40,'over_2.5':2.10,'under_2.5':1.72,'over_3.5':4.00},
            'btts_si':1.90,'btts_no':1.88},  # BTTS real — Suiza encajó en 3/3, Argelia marcó en 2/3
        ('Australia',   'Egipto'):              {'c1':3.40,'cx':2.88,'c2':2.50,'hc':{},
            'totals':{'over_1.5':1.61,'over_2.5':2.19,'under_2.5':1.65,'over_3.5':4.20},
            'btts_si':2.40,'btts_no':1.55},
        ('Argentina',   'Cabo Verde'):          {'c1':1.20,'cx':7.55,'c2':22.0,'hc':{},
            'totals':{'over_1.5':1.18,'over_2.5':1.65,'under_2.5':2.20,'over_3.5':2.80},
            'btts_si':5.50,'btts_no':1.12},  # Cabo Verde no anota facil vs Argentina
        ('Colombia',    'Ghana'):               {'c1':1.57,'cx':3.80,'c2':5.50,'hc':{},
            'totals':{'over_1.5':1.38,'over_2.5':2.00,'under_2.5':1.80,'over_3.5':3.70},
            'btts_si':2.30,'btts_no':1.60},
        ('Canadá',      'Sudáfrica'):           {'c1':1.55,'cx':3.90,'c2':6.00,'hc':{},
            'totals':{'over_1.5':1.40,'over_2.5':2.10,'under_2.5':1.72,'over_3.5':4.00},'btts_si':3.00,'btts_no':1.33},
        ('Brasil',      'Japón'):               {'c1':1.80,'cx':3.60,'c2':4.50,'hc':{},
            'totals':{'over_1.5':1.30,'over_2.5':1.90,'under_2.5':1.90,'over_3.5':3.50},'btts_si':2.50,'btts_no':1.50},
        ('Alemania',    'Paraguay'):            {'c1':1.65,'cx':4.00,'c2':5.50,'hc':{},
            'totals':{'over_1.5':1.28,'over_2.5':1.85,'under_2.5':1.95,'over_3.5':3.40},'btts_si':2.80,'btts_no':1.40},
        ('Países Bajos','Marruecos'):           {'c1':1.90,'cx':3.50,'c2':4.20,'hc':{},
            'totals':{'over_1.5':1.35,'over_2.5':2.00,'under_2.5':1.80,'over_3.5':3.80},'btts_si':2.60,'btts_no':1.45},
        ('Costa de Marfil','Noruega'):          {'c1':2.20,'cx':3.40,'c2':3.30,'hc':{},
            'totals':{'over_1.5':1.38,'over_2.5':1.95,'under_2.5':1.85,'over_3.5':3.60},'btts_si':2.40,'btts_no':1.52},
        ('Francia',     'Suecia'):              {'c1':1.55,'cx':4.00,'c2':5.50,'hc':{},
            'totals':{'over_1.5':1.25,'over_2.5':1.80,'under_2.5':2.00,'over_3.5':3.30},'btts_si':3.10,'btts_no':1.30},
        ('México',      'Ecuador'):             {'c1':2.10,'cx':3.30,'c2':3.50,'hc':{},
            'totals':{'over_1.5':1.40,'over_2.5':2.05,'under_2.5':1.75,'over_3.5':3.90},'btts_si':2.50,'btts_no':1.50},
        # ── Octavos de final ──
        ('Canadá',      'Marruecos'):           {'c1':2.55,'cx':2.90,'c2':2.70,'hc':{},
            'totals':{'over_1.5':1.60,'over_2.5':2.25,'under_2.5':1.65,'over_3.5':4.50},
            'btts_si':2.20,'btts_no':1.65},
        ('Paraguay',    'Francia'):             {'c1':8.50,'cx':4.80,'c2':1.35,
            'hc':{'Francia_-1.5':2.10,'Francia_-2.5':3.80},
            'totals':{'over_1.5':1.38,'over_2.5':1.85,'under_2.5':1.90,'over_3.5':3.60,
                      'over_2.5_cards':2.10,'over_3.5_cards':3.20},
            'btts_si':2.80,'btts_no':1.42},
        ('Brasil',      'Noruega'):             {'c1':1.65,'cx':4.10,'c2':5.50,'hc':{},
            'totals':{'over_1.5':1.32,'over_2.5':1.80,'under_2.5':1.95,'over_3.5':3.40},
            'btts_si':2.60,'btts_no':1.45},
        ('México',      'Inglaterra'):          {'c1':4.20,'cx':3.80,'c2':1.85,'hc':{},
            'totals':{'over_1.5':1.42,'over_2.5':2.00,'under_2.5':1.80,'over_3.5':3.70},
            'btts_si':2.50,'btts_no':1.50},
        ('Portugal',    'España'):              {'c1':2.10,'cx':3.30,'c2':3.50,'hc':{},
            'totals':{'over_1.5':1.35,'over_2.5':1.90,'under_2.5':1.88,'over_3.5':3.50},
            'btts_si':1.90,'btts_no':1.85},
        ('EE. UU.',     'Bélgica'):             {'c1':2.55,'cx':3.40,'c2':2.78,'hc':{},
            'totals':{'over_1.5':1.40,'over_2.5':1.64,'under_2.5':2.10,'over_3.5':3.20,
                      'over_22.5_faltas':1.65,'over_20.5_faltas':1.40},
            'btts_si':2.20,'btts_no':1.62},
        ('Argentina',   'Egipto'):              {'c1':1.85,'cx':3.60,'c2':4.20,'hc':{},
            'totals':{'over_1.5':1.38,'over_2.5':2.00,'under_2.5':1.80,'over_3.5':3.70},
            'btts_si':2.60,'btts_no':1.42},
        ('Suiza',       'Colombia'):            {'c1':2.80,'cx':3.20,'c2':2.55,'hc':{},
            'totals':{'over_1.5':1.45,'over_2.5':2.10,'under_2.5':1.70,'over_3.5':4.00},
            'btts_si':2.20,'btts_no':1.62},
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
    totals_r  = cuotas_p.get('totals', {})   # over/under reales
    btts_si_r = cuotas_p.get('btts_si', 0)   # ambos anotan SI real
    btts_no_r = cuotas_p.get('btts_no', 0)   # ambos anotan NO real
    picks = []

    # ── Obtener historial H2H para ajustar probabilidades ──
    h2h = obtener_h2h(local, visit)
    if h2h['n_partidos'] >= 5:
        pass  # disponible para ajustes abajo

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
        # Ajustar Over 2.5 con H2H
        if lin == 2.5:
            pr = ajustar_prob_con_h2h(pr, h2h, 'over25')
            h2h_g = f" · H2H {h2h['over25_pct']}% +2.5 en {h2h['n_partidos']}p" if h2h['n_partidos'] >= 5 else ""
        else:
            h2h_g = ""
        cu = cuota_estimada(pr)
        if cu >= 1.15 and margen_ok(xg_t, lin):
            add(f"Más de {lab} goles", pr, cu, '🥅','Goles', f"xG total {round(xg_t,1)}{h2h_g}")
    pr_u = 100 - round(p_poisson(xg_t,2.5)*100)
    cu_u = cuota_estimada(pr_u)
    if cu_u >= 1.15:
        add("Menos de 2.5 goles", pr_u, cu_u, '🔒','Goles', f"xG bajo ({round(xg_t,1)})")

    # ── Mercados con cuotas REALES (goles, corners, tarjetas) ──
    for key_r, cuota_r in totals_r.items():
        if cuota_r < 1.30: continue
        partes = key_r.split('_')
        if len(partes) < 2: continue
        tipo = partes[0]  # 'over' o 'under'

        # ── Corners reales ──
        if 'corner' in key_r:
            try: linea_r = float(partes[1])
            except: continue
            pr_impl  = round((1/cuota_r)*100*0.95, 1)
            pr_model = round(p_poisson(lam_cor, linea_r)*100, 1)
            pr_r = max(pr_impl, pr_model)
            if tipo == 'over' and pr_r >= 48:
                add(f"Córners totales +{linea_r}", pr_r, cuota_r, '⛳', 'Córners',
                    f"{round(lam_cor,1)} córners esperados — cuota real @{cuota_r}")
            continue

        # ── Tarjetas reales ──
        if 'card' in key_r:
            try: linea_r = float(partes[1])
            except: continue
            pr_impl  = round((1/cuota_r)*100*0.95, 1)
            pr_model = round(p_poisson(lam_tar, linea_r)*100, 1)
            pr_r = max(pr_impl, pr_model)
            if tipo == 'over' and pr_r >= 48:
                add(f"Tarjetas +{linea_r}", pr_r, cuota_r, '🟨', 'Tarjetas',
                    f"{round(lam_tar,1)} tarjetas esperadas — cuota real @{cuota_r}")
            continue

        # ── Goles over/under reales ──
        try: linea_r = float(partes[1])
        except: continue
        pr_impl  = round((1/cuota_r)*100*0.95, 1)
        pr_model = round(p_poisson(xg_t, linea_r)*100, 1)
        if tipo == 'under':
            pr_model = round(100 - p_poisson(xg_t, linea_r)*100, 1)
        pr_r = max(pr_impl, pr_model)
        if pr_r >= 50:
            emoji_r = '🥅' if tipo == 'over' else '🔒'
            label_r = f"Más de {linea_r} goles" if tipo == 'over' else f"Menos de {linea_r} goles"
            add(label_r, pr_r, cuota_r, emoji_r, 'Goles',
                f"xG total {round(xg_t,1)} — cuota real @{cuota_r}")

    # ── Ambos anotan (BTTS) con cuotas reales + ajuste H2H ──
    if btts_si_r >= 1.40:
        pr_btts = round((1 - math.exp(-xgl)) * (1 - math.exp(-xgv)) * 100, 1)
        pr_btts = ajustar_prob_con_h2h(pr_btts, h2h, 'btts')
        # Si cuota real < 2.0, la casa ya la ve probable — usar prob implicita si es mayor
        pr_impl_btts = round((1/btts_si_r)*100*0.95, 1) if btts_si_r > 0 else 0
        pr_btts = max(pr_btts, pr_impl_btts)
        h2h_info = f" · H2H {h2h['btts_pct']}% en {h2h['n_partidos']} partidos" if h2h['n_partidos'] >= 5 else ""
        if pr_btts >= 42:
            add("Ambos anotan - Sí", pr_btts, btts_si_r, '⚽', 'Goles',
                f"xG local {xgl} · xG visitante {xgv}{h2h_info}")
    if btts_no_r >= 1.40:
        pr_btts_no = round(100 - (1 - math.exp(-xgl)) * (1 - math.exp(-xgv)) * 100, 1)
        if pr_btts_no >= 45:
            add("Ambos anotan - No", pr_btts_no, btts_no_r, '🔒', 'Goles',
                f"xG local {xgl} · xG visitante {xgv}")

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

def seleccionar_publicos(todos, publicos_excluidos=None, partidos_premium=None, max_picks=3):
    """
    Panel publico v4:
    - Max 3 picks individuales
    - Cuota real >= 1.60 (no demasiado obvios)
    - Cuota max 2.50 (no demasiado arriesgados)
    - Prob >= 58%
    - Diversidad de mercado y partido
    - No incluir picks ya seleccionados en premium
    - No incluir picks del mismo partido que el premium (evita contradicciones)
    """
    if publicos_excluidos is None:
        publicos_excluidos = set()
    if partidos_premium is None:
        partidos_premium = set()

    hay_cuotas_reales = any(pk.get('fuente') == 'real' for pk in todos)

    CAT_PRIORIDAD = {
        'Goles': 10, 'Doble Op.': 9, '1X2': 8, 'Handicap': 7,
        'Córners': 6, 'Faltas': 5, 'Tiros': 4,
        'Tarjetas': 3, 'Paradas': 3, 'Remates': 4,
    }

    def score(pk):
        cat_p   = CAT_PRIORIDAD.get(pk.get('categoria',''), 1)
        es_real = 3 if pk.get('fuente') == 'real' else 0
        boost   = 5 if pk.get('h2h_boost') else 0
        return (es_real + boost, cat_p, pk['prob'])

    prob_min = 58

    candidatos = []
    for pk in todos:
        mercado_key = pk.get('mercado','')
        # Solo excluir el mercado exacto del premium, no todo el partido
        if mercado_key in publicos_excluidos:
            continue
        # Para picks de valor alto (cuota >= 2.0), bajar umbral de prob a 57%
        prob_min_pk = 57 if pk.get('cuota', 0) >= 2.0 else prob_min
        if pk['prob'] < prob_min_pk:
            continue
        if pk.get('fuente') == 'real':
            if 1.60 <= pk['cuota'] <= 2.50:
                candidatos.append(pk)
        else:
            if (1.60 <= pk['cuota'] <= 2.50) or (pk['prob'] >= 78 and pk['cuota'] >= 1.50):
                candidatos.append(pk)

    candidatos.sort(key=score, reverse=True)

    resultado = []
    partidos_count = {}
    categorias_usadas = {}
    hc_count = 0
    n_partidos = len(set(pk['partido'] for pk in todos))
    max_por_partido = 2 if n_partidos <= 3 else 1

    for pk in candidatos:
        if len(resultado) >= max_picks:
            break
        partido = pk['partido']
        cat = pk.get('categoria', '')

        if partidos_count.get(partido, 0) >= max_por_partido:
            continue
        if cat == 'Handicap':
            if hc_count >= 1:
                continue
            hc_count += 1
        if categorias_usadas.get(cat, 0) >= 2:
            continue
        if partidos_count.get(partido, 0) >= 1:
            cats_partido = [p.get('categoria') for p in resultado if p['partido'] == partido]
            if cat in cats_partido:
                continue

        pk['tipo'] = 'individual'
        resultado.append(pk)
        partidos_count[partido] = partidos_count.get(partido, 0) + 1
        categorias_usadas[cat] = categorias_usadas.get(cat, 0) + 1

    for pk in resultado:
        if 'cuota_display' not in pk: pk['cuota_display'] = pk['cuota']
        if 'tipo' not in pk: pk['tipo'] = 'individual'

    return resultado[:max_picks]


def seleccionar_premium(todos, max_picks=1):
    """
    Panel premium v4:
    - 1 pick — el MAS confiable del dia
    - Cuota entre 1.50 y 1.90 (alta confianza = casa tambien lo ve probable)
    - Prob >= 65%
    - Prioridad: BTTS > Under 2.5 > 1X2 favorito > otros
    - Nunca duplicar picks publicos
    - H2H boost automatico
    """
    # Candidatos premium: prob alta, cuota en rango de confianza
    candidatos = []
    for pk in todos:
        if pk['prob'] < 65:
            continue
        if pk['cuota'] < 1.50 or pk['cuota'] > 2.20:
            continue
        candidatos.append(pk)

    # Boost H2H automatico
    for pk in candidatos:
        desc = pk.get('descripcion','')
        if 'H2H' in desc:
            try:
                pct = float(desc.split('H2H')[1].strip().split('%')[0])
                if pct >= 60:
                    pk['prob'] = min(pk['prob'] + 8, 99)
                    pk['h2h_boost'] = True
            except: pass

    # Orden de prioridad por mercado
    PRIO_MERCADO = {
        'ambos anotan - sí': 10,
        'ambos anotan': 10,
        'menos de 2.5': 9,
        'menos de 1.5': 8,
        '1x': 7,
        'x2': 7,
        'victoria': 6,
        'más de 1.5': 5,
        'más de 2.5': 4,
    }

    def score_prem(pk):
        m = pk.get('mercado','').lower()
        prio = max((v for k,v in PRIO_MERCADO.items() if k in m), default=1)
        boost = 5 if pk.get('h2h_boost') else 0
        return (prio + boost, pk['prob'], pk['cuota'])

    candidatos.sort(key=score_prem, reverse=True)

    resultado = []
    vistos = set()
    for pk in candidatos:
        if pk['partido'] not in vistos:
            pk['tipo'] = 'premium'
            resultado.append(pk)
            vistos.add(pk['partido'])
            break

    # Si no hay candidato en rango 1.50-2.20, ampliar a 1.40-2.50
    if not resultado:
        for pk in sorted(todos, key=lambda x: x['prob'], reverse=True):
            if pk['prob'] >= 62 and 1.40 <= pk['cuota'] <= 2.50:
                pk['tipo'] = 'premium'
                resultado.append(pk)
                break

    return resultado[:max_picks]


def html_publico(picks, hoy, fecha_gen, ts, picks_prem=None):
    ISO_J   = json.dumps(BANDERAS_ISO, ensure_ascii=False)
    PICKS_J = json.dumps(picks, ensure_ascii=False, default=str)
    # Pick premium para mostrar bloqueado
    prem = picks_prem[0] if picks_prem else None
    prem_mercado = prem.get('mercado','Pick Premium') if prem else 'Pick Premium del día'
    prem_partido = prem.get('partido','') if prem else ''
    prem_prob    = prem.get('prob', 0) if prem else 0
    prem_cuota   = prem.get('cuota_display', prem.get('cuota',0)) if prem else 0
    prem_emoji   = prem.get('emoji','💎') if prem else '💎'

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
.seccion-titulo{{display:flex;align-items:center;gap:8px;margin:20px 0 10px;
font-size:.82rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--tx2)}}
.seccion-titulo::after{{content:'';flex:1;height:1px;background:var(--lin)}}
.badge-gratis{{background:#1a3320;color:var(--v);border:1px solid var(--v);border-radius:6px;
padding:2px 10px;font-size:.72rem;font-weight:700}}
.badge-prem{{background:#2a1a3d;color:var(--pu);border:1px solid var(--pu);border-radius:6px;
padding:2px 10px;font-size:.72rem;font-weight:700}}
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
background:var(--panel2);border-radius:7px;border-left:3px solid var(--go)}}
.aviso{{background:var(--panel);border-left:4px solid var(--go);border-radius:0 10px 10px 0;
padding:11px 13px;font-size:.79rem;color:var(--tx2);margin-top:18px}}
.freal{{font-size:.65rem;background:#1a2f1a;color:var(--v);border-radius:4px;padding:1px 5px;margin-left:4px}}
.fest{{font-size:.65rem;background:#2a2010;color:var(--e);border-radius:4px;padding:1px 5px;margin-left:4px}}
.ev-pos{{color:var(--v);font-size:.8rem}}.ev-neg{{color:var(--d);font-size:.8rem}}
.combo-patas{{margin-top:10px;border-top:1px solid var(--lin);padding-top:8px}}
.combo-pata{{display:flex;justify-content:space-between;align-items:center;
padding:4px 0;font-size:.78rem;color:var(--tx2)}}
.combo-pata span{{color:var(--go);margin-left:5px}}
.combo-x{{text-align:center;font-size:.7rem;color:var(--tx2);margin:2px 0}}
/* ── PICK PREMIUM BLOQUEADO ── */
.pick-prem-bloq{{background:var(--panel);border:2px solid var(--pu);border-radius:14px;
padding:18px;margin-bottom:12px;position:relative;overflow:hidden}}
.pick-prem-bloq::before{{content:'';position:absolute;inset:0;
background:rgba(13,18,32,.75);z-index:2;border-radius:12px}}
.prem-overlay{{position:absolute;inset:0;z-index:3;display:flex;flex-direction:column;
align-items:center;justify-content:center;gap:14px;padding:20px}}
.prem-badge{{background:var(--pu);color:#0d1220;border-radius:8px;
padding:5px 16px;font-size:.85rem;font-weight:700;letter-spacing:.03em}}
.prem-titulo{{font-size:1rem;font-weight:700;color:var(--tx);text-align:center}}
.prem-sub{{font-size:.78rem;color:var(--tx2);text-align:center}}
.prem-precio{{font-size:1.4rem;font-weight:700;color:var(--go)}}
.prem-btn{{display:block;background:linear-gradient(90deg,#a78bfa,#818cf8);
color:#fff;border-radius:10px;padding:10px 28px;font-weight:700;font-size:.9rem;
text-decoration:none;text-align:center;margin-top:4px}}
.prem-yape{{font-size:.75rem;color:var(--tx2);text-align:center}}
footer{{text-align:center;color:var(--tx2);font-size:.75rem;margin-top:22px}}
footer a{{color:var(--ac);text-decoration:none}}
</style>
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-J4LP4JRR1N"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-J4LP4JRR1N');
</script>
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
  <a class="tg-btn" href="https://t.me/sportpickoficial">📣 Unirte al canal de Telegram</a>
  <div class="resumen" id="res"></div>

  <div class="seccion-titulo"><span class="badge-gratis">✅ GRATIS</span> Picks públicos del día</div>
  <div id="picks"></div>

  <div class="seccion-titulo"><span class="badge-prem">💎 PREMIUM</span> Pick exclusivo</div>
  <div class="pick-prem-bloq">
    <div class="ph">
      <div class="ph-em">{prem_emoji}</div>
      <div class="ph-info">
        <div class="sub" style="filter:blur(5px);user-select:none">██████████ · Premium</div>
        <div class="merc" style="filter:blur(5px);user-select:none">████████████████</div>
      </div>
    </div>
    <div class="stats">
      <div class="sb"><div class="v" style="color:var(--v);filter:blur(4px)">{prem_prob}%</div><div class="l">Probabilidad</div></div>
      <div class="sb"><div class="v" style="color:var(--go);filter:blur(4px)">@{prem_cuota}</div><div class="l">Cuota</div></div>
      <div class="sb"><div class="v" style="color:var(--pu)">🔒</div><div class="l">Bloqueado</div></div>
    </div>
    <div class="prem-overlay">
      <span class="prem-badge">💎 PICK PREMIUM</span>
      <div class="prem-titulo">🔒 Pick Exclusivo del Día</div>
      <div class="prem-sub">Mercado y partido revelados al pagar · Análisis profundo del modelo</div>
      <div class="prem-precio">S/10 · $5 USD — Pick Seguro 🔥</div>
      <a class="prem-btn" href="https://wa.me/51982730164?text=Hola%2C%20quiero%20el%20pick%20seguro%20premium%20de%20hoy">
        📱 Activar por Yape/Plin
      </a>
      <div class="prem-yape">Yape/Plin: 982 730 164 · DM en Facebook: SportPicks Oficial</div>
    </div>
  </div>

  <div class="aviso">💡 Los picks premium incluyen el mercado exacto, análisis del modelo y seguimiento diario hasta el final del Mundial 2026.</div>
  <footer>
    Modelo: <a href="index_final.html">Simulaciones_Mundial</a> — XGBoost + Odds API + Dixon-Coles + Razonamiento por equipo —
    <a href="picks_publicos_v2.html">Ver picks</a>
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
    comboH='<div class="combo-patas">'+pk.picks_combo.map((s,si)=>`
      <div class="combo-pata">
        <span>${{fl(s.local)}} ${{s.partido}} · ${{s.mercado}}</span>
        <span class="v" style="color:var(--go);margin-left:5px">@${{s.cuota}}</span></div>
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

def html_premium(picks, hoy, fecha_gen, ts):
    import functools
    ISO_J   = json.dumps(BANDERAS_ISO, ensure_ascii=False)
    PICKS_J = json.dumps(picks, ensure_ascii=False, default=str)
    cuota_acum = round(functools.reduce(lambda a,b: a*b, [p['cuota'] for p in picks], 1), 2) if picks else 1

    # Codigo de acceso: "SP" + DDMM del dia (ej: SP0407 para 4 julio)
    # Cambia automaticamente cada dia
    import datetime
    hoy_dt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5)))
    codigo_hoy = f"SP{hoy_dt.strftime('%d%m')}"

    return f"""<!DOCTYPE html>
<html lang="es">
<!-- ts:{ts} -->
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Picks Premium 💎 — Mundial 2026</title>
<style>
:root{{--bg:#0d1220;--panel:#161d31;--panel2:#1c2540;--tx:#eef1f8;--tx2:#9aa5c0;
--lin:#2a3554;--v:#34d399;--e:#fbbf24;--d:#fb7185;--ac:#60a5fa;--pu:#a78bfa;--or:#fb923c;--go:#ffd700}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,sans-serif;padding-bottom:48px;
  min-height:100vh;display:flex;flex-direction:column}}
.wrap{{max-width:820px;margin:0 auto;padding:0 16px;flex:1}}
nav{{background:rgba(13,18,32,.95);border-bottom:1px solid var(--lin);padding:12px 16px;
position:sticky;top:0;z-index:50;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-weight:700;color:var(--pu);font-size:.95rem}}
.nav-links a{{color:var(--tx2);text-decoration:none;font-size:.82rem;margin-left:12px;font-weight:600}}

/* ── PANTALLA DE ACCESO ── */
.acceso-wrap{{display:flex;align-items:center;justify-content:center;
  min-height:70vh;padding:24px 16px}}
.acceso-card{{background:var(--panel);border:2px solid var(--pu);border-radius:20px;
  padding:36px 32px;max-width:420px;width:100%;text-align:center}}
.acceso-logo{{font-size:3rem;margin-bottom:8px}}
.acceso-titulo{{font-size:1.4rem;font-weight:700;color:var(--pu);margin-bottom:6px}}
.acceso-sub{{font-size:.85rem;color:var(--tx2);margin-bottom:28px;line-height:1.6}}
.acceso-input{{width:100%;background:var(--panel2);border:1.5px solid var(--lin);
  border-radius:10px;padding:13px 16px;font-size:1.1rem;color:var(--tx);
  text-align:center;letter-spacing:.15em;font-weight:700;margin-bottom:14px;
  outline:none;transition:border-color .2s}}
.acceso-input:focus{{border-color:var(--pu)}}
.acceso-input.error{{border-color:var(--d);animation:shake .3s}}
.acceso-btn{{width:100%;background:var(--pu);color:#0d1220;border:none;
  border-radius:10px;padding:13px;font-size:1rem;font-weight:700;cursor:pointer;
  margin-bottom:20px;transition:opacity .2s}}
.acceso-btn:hover{{opacity:.88}}
.acceso-error{{color:var(--d);font-size:.82rem;margin-bottom:12px;display:none}}
.acceso-sep{{border:none;border-top:1px solid var(--lin);margin:16px 0}}
.acceso-comprar{{font-size:.82rem;color:var(--tx2);margin-bottom:10px}}
.acceso-precio{{font-size:1.3rem;font-weight:700;color:var(--go);margin-bottom:16px}}
.btn-yape{{display:block;background:#1a3d2a;border:1.5px solid var(--v);color:var(--v);
  border-radius:10px;padding:11px;font-weight:700;font-size:.85rem;
  text-decoration:none;margin-bottom:8px}}
.btn-wa{{display:block;background:#1a2f1a;border:1.5px solid #25d366;color:#25d366;
  border-radius:10px;padding:11px;font-weight:700;font-size:.85rem;text-decoration:none}}

/* ── CONTENIDO PREMIUM (oculto hasta ingresar codigo) ── */
#contenido-premium{{display:none}}
header{{text-align:center;padding:26px 0 16px}}
header h1{{font-size:1.45rem;font-weight:700}}
header p{{color:var(--tx2);font-size:.84rem;margin-top:5px}}
.badge{{display:inline-block;border:1px solid var(--lin);border-radius:999px;
padding:2px 11px;font-size:.75rem;color:var(--tx2);margin:3px 2px}}
.badge.hoy{{border-color:var(--pu);color:var(--pu)}}
.resumen-p{{background:var(--panel);border:1px solid var(--pu);border-radius:12px;
padding:14px;margin-bottom:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:8px;text-align:center}}
.rs-v{{font-size:1.25rem;font-weight:700;color:var(--pu)}}
.rs-l{{font-size:.7rem;color:var(--tx2)}}
.acum{{background:var(--panel);border:1px solid var(--go);border-radius:12px;
padding:12px;text-align:center;margin-bottom:16px}}
.acum-v{{font-size:1.6rem;font-weight:700;color:var(--go)}}
.acum-l{{font-size:.75rem;color:var(--tx2);margin-top:2px}}
.pick{{background:var(--panel);border:1px solid var(--pu);border-radius:14px;
padding:18px;margin-bottom:12px;position:relative}}
.pick-n{{position:absolute;top:10px;right:12px;font-size:.72rem;color:var(--pu);
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
background:var(--panel2);border-radius:7px;border-left:3px solid var(--pu)}}
.freal{{font-size:.65rem;background:#1a2f1a;color:var(--v);border-radius:4px;padding:1px 5px;margin-left:4px}}
.fest{{font-size:.65rem;background:#2a2010;color:var(--e);border-radius:4px;padding:1px 5px;margin-left:4px}}
.ev-pos{{color:var(--v);font-size:.8rem}}.ev-neg{{color:var(--d);font-size:.8rem}}
.combo-patas{{margin-top:10px;border-top:1px solid var(--lin);padding-top:8px}}
.combo-pata{{display:flex;justify-content:space-between;align-items:center;
padding:4px 0;font-size:.78rem;color:var(--tx2)}}
footer{{text-align:center;color:var(--tx2);font-size:.75rem;margin-top:22px}}
footer a{{color:var(--ac);text-decoration:none}}
@keyframes shake{{0%,100%{{transform:translateX(0)}}25%{{transform:translateX(-6px)}}75%{{transform:translateX(6px)}}}}
</style>
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-J4LP4JRR1N"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-J4LP4JRR1N');
</script>
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

  <!-- PANTALLA DE ACCESO -->
  <div class="acceso-wrap" id="pantalla-acceso">
    <div class="acceso-card">
      <div class="acceso-logo">💎</div>
      <div class="acceso-titulo">Picks Premium</div>
      <div class="acceso-sub">
        Ingresa tu código de acceso para ver el pick premium de hoy.<br>
        Código válido solo por 24 horas.
      </div>
      <input class="acceso-input" id="codigo-input" type="text"
        placeholder="XXXXXX" maxlength="8" autocomplete="off"
        oninput="this.value=this.value.toUpperCase()">
      <div class="acceso-error" id="error-msg">❌ Código incorrecto. Verifica e intenta de nuevo.</div>
      <button class="acceso-btn" onclick="verificarCodigo()">Ingresar →</button>

      <hr class="acceso-sep">
      <div class="acceso-comprar">¿No tienes código? Accede al premium por:</div>
      <div class="acceso-precio">S/10 · $5 USD — Pick Seguro 🔥</div>
      <a class="btn-yape" href="https://wa.me/51982730164?text=Hola%2C%20quiero%20el%20pick%20premium%20de%20SportPicks">
        📱 Pagar por Yape/Plin — 982 730 164
      </a>
      <a class="btn-wa" href="https://wa.me/51982730164?text=Hola%2C%20quiero%20el%20pick%20premium">
        💬 Consultar por WhatsApp
      </a>
    </div>
  </div>

  <!-- CONTENIDO PREMIUM (oculto) -->
  <div id="contenido-premium">
    <header>
      <h1>💎 Picks Premium — {hoy}</h1>
      <p>Los picks con mayor probabilidad de acierto del modelo</p>
      <span class="badge hoy">📅 {fecha_gen}</span>
      <span class="badge">🔒 Acceso exclusivo suscriptores</span>
    </header>
    <div class="resumen-p" id="res"></div>
    <div class="acum">
      <div class="acum-v">@{cuota_acum}</div>
      <div class="acum-l">Cuota acumulador (combinadas)</div>
    </div>
    <div id="picks"></div>
    <footer>
      <a href="picks_dia.html">🎯 Picks públicos gratis</a> ·
      <a href="picks_publicos_v2.html">📊 Historial</a> ·
      <a href="https://t.me/sportpickoficial">📣 Telegram</a>
    </footer>
  </div>

</div>

<script>
const PICKS={PICKS_J};
const ISO={ISO_J};
const CODIGO_HOY="{codigo_hoy}";

function verificarCodigo(){{
  const input=document.getElementById('codigo-input');
  const err=document.getElementById('error-msg');
  const val=input.value.trim().toUpperCase();

  if(val===CODIGO_HOY){{
    // Guardar en sessionStorage para no pedir de nuevo en la misma sesion
    sessionStorage.setItem('sp_acceso','ok_'+CODIGO_HOY);
    mostrarContenido();
  }} else {{
    input.classList.add('error');
    err.style.display='block';
    setTimeout(()=>input.classList.remove('error'),400);
  }}
}}

document.getElementById('codigo-input').addEventListener('keydown',function(e){{
  if(e.key==='Enter') verificarCodigo();
}});

function mostrarContenido(){{
  document.getElementById('pantalla-acceso').style.display='none';
  document.getElementById('contenido-premium').style.display='block';
  renderPicks();
}}

// Si ya ingresó el codigo en esta sesion, mostrar directo
const sesion=sessionStorage.getItem('sp_acceso');
if(sesion==='ok_'+CODIGO_HOY) mostrarContenido();

const fl=eq=>ISO[eq]?`<img style="width:18px;height:13px;border-radius:2px;vertical-align:-2px;object-fit:cover" src="https://flagcdn.com/w20/${{ISO[eq]}}.png">`:'';

function renderPicks(){{
  const probP=PICKS.length?Math.round(PICKS.reduce((s,p)=>s+p.prob,0)/PICKS.length):0;
  const cuotaP=PICKS.length?(PICKS.reduce((s,p)=>s+(p.cuota_display||p.cuota),0)/PICKS.length).toFixed(2):0;
  document.getElementById('res').innerHTML=`
    <div><div class="rs-v">${{PICKS.length}}</div><div class="rs-l">Picks premium</div></div>
    <div><div class="rs-v">${{probP}}%</div><div class="rs-l">Prob. promedio</div></div>
    <div><div class="rs-v">${{cuotaP}}</div><div class="rs-l">Cuota prom.</div></div>`;
  const cont=document.getElementById('picks');
  PICKS.forEach((pk,i)=>{{
    const esC=pk.tipo==='combinada';
    const cuotaD=pk.cuota_display||pk.cuota;
    const fB=pk.fuente==='real'?'<span class="freal">real</span>':'<span class="fest">estimada</span>';
    const evH=pk.ev!=null?`<span class="${{pk.ev>0?'ev-pos':'ev-neg'}}">${{pk.ev>0?'+':''}}${{(pk.ev*100).toFixed(1)}}%</span>`:'—';
    let comboH='';
    if(esC&&pk.picks_combo){{
      comboH='<div class="combo-patas">'+pk.picks_combo.map((s,si)=>`
        <div class="combo-pata">
          <span>${{fl(s.local)}} ${{s.partido}} · ${{s.mercado}}</span>
          <span style="color:var(--go);margin-left:5px">@${{s.cuota}}</span></div>
        ${{si<pk.picks_combo.length-1?'<div style="text-align:center;font-size:.7rem;color:var(--tx2);margin:2px 0">✖️</div>':''}}
      `).join('')+'</div>';
    }}
    const d=document.createElement('div');
    d.className='pick';
    d.innerHTML=`
      <div class="pick-n">💎 #${{i+1}}</div>
      <div class="ph">
        <div class="ph-em">${{pk.emoji}}</div>
        <div class="ph-info">
          <div class="sub">${{esC?'🔗 COMBINADA PREMIUM':fl(pk.local)+' '+pk.partido}} · ${{pk.categoria}}</div>
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
}}
</script>
</body></html>"""

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

    # ── Leer reporte de análisis automático de mercado ──
    reporte_analisis = {}
    try:
        ruta_reporte = os.path.join(RAIZ, 'Data', 'analisis_mercado.json')
        if os.path.exists(ruta_reporte):
            reporte_analisis = json.load(open(ruta_reporte, encoding='utf-8'))
            hoy_reporte = reporte_analisis.get('fecha', '')
            if hoy_reporte == hoy_peru():
                picks_top = reporte_analisis.get('picks_top', [])
                n_alto = sum(1 for p in picks_top if p.get('nivel') == 'ALTO')
                print(f"  📊 Análisis de mercado cargado: {len(picks_top)} picks recomendados ({n_alto} ALTO valor)")
            else:
                reporte_analisis = {}
    except Exception as e:
        print(f"  ⚠️ Sin reporte de análisis: {e}")

    # ── Picks manuales basados en análisis del mercado ──
    picks_manuales = []

    # Agregar picks del análisis automático como candidatos
    if reporte_analisis:
        for pk_rep in reporte_analisis.get('picks_top', []):
            if pk_rep.get('nivel') == 'ALTO' and pk_rep.get('tiene_valor'):
                # Solo agregar si el pick tiene valor real confirmado
                partido_str = pk_rep.get('partido', '')
                picks_manuales.append({
                    'partido': partido_str,
                    'local': partido_str.split(' vs ')[0] if ' vs ' in partido_str else '',
                    'visitante': partido_str.split(' vs ')[1] if ' vs ' in partido_str else '',
                    'mercado': pk_rep['mercado'],
                    'prob': pk_rep['prob_modelo'],
                    'cuota': pk_rep['cuota'],
                    'cuota_display': pk_rep['cuota'],
                    'ev': pk_rep['ev'],
                    'emoji': pk_rep.get('emoji', '⚽'),
                    'categoria': pk_rep.get('categoria', 'Goles'),
                    'descripcion': f"Análisis automático: {pk_rep['nivel']} valor | EV{pk_rep['ev']:+.2f}",
                    'fuente': 'real' if pk_rep.get('prob_mercado') else 'estimada',
                    'tipo': 'individual',
                    'h2h_boost': pk_rep.get('nivel') == 'ALTO',
                })

    # Argentina vs Cabo Verde — HC -1.5 si existe el partido hoy
    if any('argentina' in pk.get('partido','').lower() and 'cabo' in pk.get('partido','').lower()
           for pk in todos):
        picks_manuales.append({
            'partido': 'Argentina vs Cabo Verde',
            'local': 'Argentina', 'visitante': 'Cabo Verde',
            'mercado': 'HC Argentina -1.5',
            'prob': 82.0,
            'cuota': 1.80, 'cuota_display': 1.80,
            'ev': round((0.82 * 1.80) - 1, 3),
            'emoji': '⚖️', 'categoria': 'Handicap',
            'descripcion': 'Argentina gana por 2+ goles — Messi 6 goles en el torneo',
            'fuente': 'real', 'tipo': 'individual',
            'h2h_boost': True,
        })

    # Paraguay vs Francia — Over 2.5 y Tarjetas si existe el partido hoy
    if any('paraguay' in pk.get('partido','').lower() and 'francia' in pk.get('partido','').lower()
           for pk in todos):
        # Over 2.5 goles — Francia marcó 10 goles en grupos, xG total 3.27
        picks_manuales.append({
            'partido': 'Paraguay vs Francia',
            'local': 'Paraguay', 'visitante': 'Francia',
            'mercado': 'Más de 2.5 goles',
            'prob': 72.0,
            'cuota': 1.85, 'cuota_display': 1.85,
            'ev': round((0.72 * 1.85) - 1, 3),
            'emoji': '🥅', 'categoria': 'Goles',
            'descripcion': 'Francia marcó 10 goles en grupos — xG total 3.27',
            'fuente': 'real', 'tipo': 'individual',
            'h2h_boost': True,
        })
        # Tarjetas +2.5 — Paraguay foulará para frenar a Francia (premium)
        picks_manuales.append({
            'partido': 'Paraguay vs Francia',
            'local': 'Paraguay', 'visitante': 'Francia',
            'mercado': 'Tarjetas +2.5',
            'prob': 76.0,
            'cuota': 2.10, 'cuota_display': 2.10,
            'ev': round((0.76 * 2.10) - 1, 3),
            'emoji': '🟨', 'categoria': 'Tarjetas',
            'descripcion': 'Paraguay foulará para frenar a Mbappé — partido físico intenso',
            'fuente': 'real', 'tipo': 'individual',
            'h2h_boost': True,
        })

    # Canada vs Marruecos — Under 2.5 si existe el partido hoy
    if any('canadá' in pk.get('partido','').lower() and 'marruecos' in pk.get('partido','').lower()
           for pk in todos):
        picks_manuales.append({
            'partido': 'Canadá vs Marruecos',
            'local': 'Canadá', 'visitante': 'Marruecos',
            'mercado': 'Menos de 2.5 goles',
            'prob': 75.0,
            'cuota': 1.65, 'cuota_display': 1.65,
            'ev': round((0.75 * 1.65) - 1, 3),
            'emoji': '🔒', 'categoria': 'Goles',
            'descripcion': 'Partido cerrado — Marruecos 33 partidos sin perder, equipo defensivo por naturaleza',
            'fuente': 'real', 'tipo': 'individual',
            'h2h_boost': True,
        })

    # México vs Inglaterra — Under 2.5 (partido táctico en altitud)
    if any('méxico' in pk.get('partido','').lower() and 'inglaterra' in pk.get('partido','').lower()
           for pk in todos):
        picks_manuales.append({
            'partido': 'México vs Inglaterra',
            'local': 'México', 'visitante': 'Inglaterra',
            'mercado': 'Menos de 2.5 goles',
            'prob': 72.0,
            'cuota': 1.90, 'cuota_display': 1.90,
            'ev': round((0.72 * 1.90) - 1, 3),
            'emoji': '🔒', 'categoria': 'Goles',
            'descripcion': 'Partido táctico en altitud del Azteca — México sin encajar en todo el torneo',
            'fuente': 'real', 'tipo': 'individual',
            'h2h_boost': True,
        })

    # Brasil vs Noruega — eliminar pick correlacionado Victoria Brasil si hay Over 2.5
    if any('brasil' in pk.get('partido','').lower() and 'noruega' in pk.get('partido','').lower()
           for pk in todos):
        todos = [pk for pk in todos if not (
            'brasil' in pk.get('partido','').lower() and
            'noruega' in pk.get('partido','').lower() and
            'victoria brasil' in pk.get('mercado','').lower()
        )]

    # Portugal vs España — corners premium + Under 2.5 publico
    if any('portugal' in pk.get('partido','').lower() and 'españa' in pk.get('partido','').lower()
           for pk in todos):
        # Premium: Corners +10.5 (España 7.5/partido en 8 seguidos)
        picks_manuales.append({
            'partido': 'Portugal vs España',
            'local': 'Portugal', 'visitante': 'España',
            'mercado': 'Córners totales +10.5',
            'prob': 82.0,
            'cuota': 1.70, 'cuota_display': 1.70,
            'ev': round((0.82 * 1.70) - 1, 3),
            'emoji': '⛳', 'categoria': 'Córners',
            'descripcion': 'España 7.5 corners/partido en 8 seguidos + Portugal 5.9 = 13+ esperados',
            'fuente': 'real', 'tipo': 'individual',
            'h2h_boost': True,
        })
        # Publico: Under 2.5 goles (España 0 goles encajados en 5 partidos)
        picks_manuales.append({
            'partido': 'Portugal vs España',
            'local': 'Portugal', 'visitante': 'España',
            'mercado': 'Menos de 2.5 goles',
            'prob': 68.0,
            'cuota': 2.00, 'cuota_display': 2.00,
            'ev': round((0.68 * 2.00) - 1, 3),
            'emoji': '🔒', 'categoria': 'Goles',
            'descripcion': 'España 0 goles encajados en 5 partidos — partido táctico ibérico',
            'fuente': 'real', 'tipo': 'individual',
        })
        # Eliminar Over 2.5 Portugal vs España (contradice Under)
        todos = [pk for pk in todos if not (
            'portugal' in pk.get('partido','').lower() and
            'españa' in pk.get('partido','').lower() and
            'más de 2.5' in pk.get('mercado','').lower()
        )]

    # EE.UU. vs Bélgica — faltas PREMIUM (forzado)
    if any('ee. uu.' in pk.get('partido','').lower() and 'bélgica' in pk.get('partido','').lower()
           for pk in todos):
        picks_manuales.append({
            'partido': 'EE. UU. vs Bélgica',
            'local': 'EE. UU.', 'visitante': 'Bélgica',
            'mercado': 'Faltas totales +22.5',
            'prob': 92.0,  # boost alto para forzar al premium
            'cuota': 1.65, 'cuota_display': 1.65,
            'ev': round((0.92 * 1.65) - 1, 3),
            'emoji': '🦵', 'categoria': 'Faltas',
            'descripcion': 'EE.UU. 15 + Bélgica 20 faltas/partido = 35 esperadas — Balogun habilitado — modelo 98.7%',
            'fuente': 'real', 'tipo': 'individual',
            'h2h_boost': True,
        })

    # México vs Inglaterra — eliminar picks contradictorios con Under 2.5 premium
    if any('méxico' in pk.get('partido','').lower() and 'inglaterra' in pk.get('partido','').lower()
           for pk in todos):
        todos = [pk for pk in todos if not (
            'méxico' in pk.get('partido','').lower() and
            'inglaterra' in pk.get('partido','').lower() and
            ('más de 2.5' in pk.get('mercado','').lower() or
             'ambos anotan' in pk.get('mercado','').lower())
        )]

    # ── Filtros finales ANTES de agregar picks manuales ──
    # 1. Eliminar picks con EV muy negativo (sin valor real)
    todos = [pk for pk in todos if pk.get('ev', 0) > -0.15 or pk.get('fuente') != 'real']
    # 2. Eliminar Under 2.5 Argentina cuando hay HC -1.5 (contradictorios)
    todos = [pk for pk in todos if not (
        'argentina' in pk.get('partido','').lower() and
        'menos de 2.5' in pk.get('mercado','').lower()
    )]
    # 3. Eliminar BTTS Portugal vs España (no es el pick correcto hoy)
    todos = [pk for pk in todos if not (
        'portugal' in pk.get('partido','').lower() and
        'españa' in pk.get('partido','').lower() and
        'ambos anotan' in pk.get('mercado','').lower()
    )]
    # 4. Eliminar Over 2.5 EE.UU. Bélgica si hay Faltas en el mismo partido en publico
    # (permitir Over 2.5 como pick publico — es diferente mercado)
    # 5. Recalcular EV correctamente para picks reales
    for pk in todos:
        if pk.get('fuente') == 'real' and pk.get('cuota', 0) > 0:
            pk['ev'] = round((pk['prob']/100) - (1/pk['cuota']), 3)

    # ── Agregar picks manuales DESPUES de filtros ──
    todos = todos + picks_manuales

    # ── DEBUG: mostrar todos los candidatos ordenados por prob ──
    print('\n📊 TODOS LOS CANDIDATOS:')
    for pk in sorted(todos, key=lambda x: x['prob'], reverse=True)[:25]:
        print(f"  {pk['prob']:5.1f}% @{pk['cuota']:.2f} [{pk.get('fuente','?'):8}] {pk.get('partido','')[:22]} — {pk['mercado'][:38]}")
    import sys; sys.exit()

    picks_prem  = seleccionar_premium(todos)  # Premium PRIMERO

    # Excluir del público los picks ya en premium
    mercados_premium = set(pk.get('mercado','') for pk in picks_prem)
    partidos_premium = set(pk.get('partido','') for pk in picks_prem)
    picks_pub = seleccionar_publicos(todos,
                                    publicos_excluidos=mercados_premium,
                                    partidos_premium=partidos_premium)

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
        f.write(html_publico(picks_pub,  hoy, fecha_gen, ts, picks_prem))
    with open('docs/picks_premium.html', 'w', encoding='utf-8') as f:
        f.write(html_premium(picks_prem, hoy, fecha_gen, ts))

    print(f"\n✅ docs/picks_dia.html generado")
    print(f"✅ docs/picks_premium.html generado")

if __name__ == '__main__':
    main()