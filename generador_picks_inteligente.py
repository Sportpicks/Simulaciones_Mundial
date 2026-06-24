# -*- coding: utf-8 -*-
"""
generador_picks_inteligente.py
Genera dos paneles de picks para el canal de Telegram.

PANEL PÚBLICO:  Máx 4 picks con cuota promedio +1.50
PANEL PREMIUM:  4 picks más seguros con cuota real mínima 1.05

Uso: python generador_picks_inteligente.py
"""

import os, sys, json, math, requests
from datetime import datetime, timezone, date
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
sys.path.insert(0, os.path.join(RAIZ, '04_Prediccion'))
from razonador_mercados import cargar_stats

API_KEY_ODDS = "622b4b772a4d155e032de1c17a83e41a"

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

def p_poisson(lam, linea):
    k = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k))
    except:
        return 0.0

def cuota_estimada(prob):
    """Cuota estimada con 5% margen de casa. Mínimo real 1.05."""
    if prob <= 0 or prob >= 100: return 1.05
    c = round((100/prob)*0.95, 2)
    return max(1.05, c)

def obtener_cuotas():
    """Obtiene cuotas h2h de The Odds API promediando todas las casas."""
    cuotas = {}
    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/",
            params={"apiKey":API_KEY_ODDS,"regions":"eu","markets":"h2h","oddsFormat":"decimal"},
            timeout=15
        )
        if r.status_code == 200:
            for partido in r.json():
                local_en = partido.get("home_team","")
                visit_en = partido.get("away_team","")
                local_es = NOMBRES_API.get(local_en, local_en)
                visit_es = NOMBRES_API.get(visit_en, visit_en)
                c1s,cxs,c2s = [],[],[]
                for bk in partido.get("bookmakers",[]):
                    for mkt in bk.get("markets",[]):
                        if mkt["key"]=="h2h":
                            outs = {o["name"]:o["price"] for o in mkt["outcomes"]}
                            if local_en in outs: c1s.append(outs[local_en])
                            if "Draw" in outs:   cxs.append(outs["Draw"])
                            if visit_en in outs: c2s.append(outs[visit_en])
                cuotas[(local_es,visit_es)] = {
                    'c1': round(sum(c1s)/len(c1s),2) if c1s else 0,
                    'cx': round(sum(cxs)/len(cxs),2) if cxs else 0,
                    'c2': round(sum(c2s)/len(c2s),2) if c2s else 0,
                }
    except Exception as e:
        print(f"   ⚠️ Error cuotas: {e}")
    print(f"   ✅ Cuotas: {len(cuotas)} partidos")
    return cuotas

def generar_picks_partido(r, cuotas_p):
    """Genera todos los picks válidos para un partido."""
    local  = r['Local']
    visit  = r['Visitante']
    p1     = float(r['Prob_1_Final'])
    px     = float(r['Prob_X_Final'])
    p2     = float(r['Prob_2_Final'])
    xgl    = float(r.get('xG_L',0))
    xgv    = float(r.get('xG_V',0))
    xg_t   = xgl + xgv
    lam_cor   = float(r.get('cor',9.0))
    lam_tar   = float(r.get('tar',4.0))
    lam_tiros = float(r.get('tiros_esp',7.0))
    lam_fal   = float(r.get('faltas_esp',22.0))

    c1 = cuotas_p.get('c1',0)
    cx = cuotas_p.get('cx',0)
    c2 = cuotas_p.get('c2',0)

    picks = []

    def add(mercado, prob, cuota, emoji, cat, desc="", partido_key=None):
        if prob < 52 or cuota < 1.05: return
        ev = round((prob/100)*cuota - 1, 3)
        picks.append({
            'partido'  : f"{local} vs {visit}",
            'local'    : local, 'visitante': visit,
            'mercado'  : mercado, 'prob': round(prob,1),
            'cuota'    : cuota, 'ev': ev,
            'emoji'    : emoji, 'categoria': cat,
            'descripcion': desc,
            'fuente'   : 'real' if cuota > 1.10 else 'estimada',
        })

    # 1X2
    if c1 > 1.05: add(f"Victoria {local}", p1, c1, '⚽','1X2', f"{local} favorito ({p1:.0f}%)")
    if cx > 1.05: add("Empate",            px, cx, '⚖️','1X2', f"Empate esperado ({px:.0f}%)")
    if c2 > 1.05: add(f"Victoria {visit}", p2, c2, '⚽','1X2', f"{visit} favorito ({p2:.0f}%)")

    # Doble oportunidad (cuota estimada)
    for prob_do, label, desc_do in [
        (round(p1+px,1), f"1X — {local} o Empate", f"Cubre victoria {local} + empate"),
        (round(px+p2,1), f"X2 — Empate o {visit}", f"Cubre empate + victoria {visit}"),
        (round(p1+p2,1), "Sin empate (1 o 2)", "Cualquier equipo gana"),
    ]:
        add(label, prob_do, cuota_estimada(prob_do), '🛡️','Doble Op.', desc_do)

    # Goles (solo líneas con cuota real >1.15 estimada)
    for lin, lab in [(1.5,'1.5'),(2.5,'2.5'),(3.5,'3.5')]:
        pr = round(p_poisson(xg_t, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:  # Solo si hay cuota real interesante
            add(f"Más de {lab} goles", pr, cu, '🥅','Goles', f"xG total {round(xg_t,1)}")
    pr_u = 100 - round(p_poisson(xg_t,2.5)*100)
    cu_u = cuota_estimada(pr_u)
    if cu_u >= 1.15:
        add("Menos de 2.5 goles", pr_u, cu_u, '🔒','Goles', f"xG bajo ({round(xg_t,1)})")

    # Córners (solo líneas con cuota estimada >1.15 = prob <87%)
    for lin in [7.5, 8.5, 9.5, 10.5]:
        pr = round(p_poisson(lam_cor, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Córners +{lin}", pr, cu, '⛳','Córners', f"{round(lam_cor,1)} córners esperados")

    # Tiros (solo cuota >1.15)
    for lin in [4.5, 5.5, 6.5, 7.5]:
        pr = round(p_poisson(lam_tiros, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Tiros a puerta +{lin}", pr, cu, '🎯','Tiros', f"{round(lam_tiros,1)} tiros esperados")

    # Faltas (solo cuota >1.15)
    for lin in [18.5, 20.5, 22.5]:
        pr = round(p_poisson(lam_fal, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Faltas +{lin}", pr, cu, '🦵','Faltas', f"{round(lam_fal,1)} faltas esperadas")

    # Tarjetas
    for lin in [3.5, 4.5]:
        pr = round(p_poisson(lam_tar, lin)*100, 1)
        cu = cuota_estimada(pr)
        if cu >= 1.15:
            add(f"Tarjetas +{lin}", pr, cu, '🟨','Tarjetas', f"{round(lam_tar,1)} tarjetas esperadas")

    # Stats por equipo — mercados avanzados
    stats = cargar_stats()
    for eq in [local, visit]:
        s = stats.get(eq,{})

        # Tiros a puerta por equipo
        t = s.get('tiros_favor_5', s.get('tiros_favor_tot',0))
        if t >= 4:
            for lin in [2.5, 3.5, 4.5]:
                pr = round(p_poisson(t, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} tiros a puerta +{lin}", pr, cu, '🎯', f'Tiros {eq}',
                        f"{eq} promedia {round(t,1)} tiros/partido")

        # Remates totales por equipo
        rt = s.get('remates_tot_favor_5', s.get('remates_tot_favor_tot',0))
        if rt >= 10:
            for lin in [8.5, 10.5, 12.5]:
                pr = round(p_poisson(rt, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} remates totales +{lin}", pr, cu, '🎯', f'Remates {eq}',
                        f"{eq} promedia {round(rt,1)} remates/partido")

        # Córners por equipo
        c = s.get('corners_favor_5', s.get('corners_favor_tot',0))
        if c >= 5:
            for lin in [3.5, 4.5, 5.5]:
                pr = round(p_poisson(c, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} córners +{lin}", pr, cu, '⛳', f'Córners {eq}',
                        f"{eq} promedia {round(c,1)} córners/partido")

        # Faltas por equipo
        f = s.get('faltas_cometidas_5', s.get('faltas_cometidas_tot',0))
        if f >= 10:
            for lin in [8.5, 9.5, 10.5]:
                pr = round(p_poisson(f, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.15:
                    add(f"{eq} faltas +{lin}", pr, cu, '🦵', f'Faltas {eq}',
                        f"{eq} promedia {round(f,1)} faltas/partido")

        # Paradas del portero por equipo
        p_par = s.get('paradas_5', s.get('paradas_tot',0))
        if p_par >= 3:
            for lin in [2.5, 3.5, 4.5]:
                pr = round(p_poisson(p_par, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.20:
                    add(f"{eq} portero +{lin} paradas", pr, cu, '🧤', f'Paradas {eq}',
                        f"Portero de {eq} promedia {round(p_par,1)} paradas/partido")

        # Grandes ocasiones por equipo
        go = s.get('grandes_ocas_5', s.get('grandes_ocas_tot',0))
        if go >= 2.5:
            for lin in [1.5, 2.5, 3.5]:
                pr = round(p_poisson(go, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.20:
                    add(f"{eq} grandes ocasiones +{lin}", pr, cu, '💥', f'Ocasiones {eq}',
                        f"{eq} promedia {round(go,1)} grandes ocasiones/partido")

        # Saques de banda por equipo
        sb = s.get('saques_banda_5', s.get('saques_banda_tot',0))
        if sb >= 15:
            for lin in [12.5, 14.5, 16.5]:
                pr = round(p_poisson(sb, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.20:
                    add(f"{eq} saques de banda +{lin}", pr, cu, '🏳️', f'Saques {eq}',
                        f"{eq} promedia {round(sb,1)} saques de banda/partido")

        # Centros por equipo
        ce = s.get('centros_5', s.get('centros_tot',0))
        if ce >= 8:
            for lin in [6.5, 8.5, 10.5]:
                pr = round(p_poisson(ce, lin)*100, 1)
                cu = cuota_estimada(pr)
                if cu >= 1.20:
                    add(f"{eq} centros +{lin}", pr, cu, '🎯', f'Centros {eq}',
                        f"{eq} promedia {round(ce,1)} centros/partido")

        # Goles por equipo (via histórico)
        gl = s.get('goles_5', s.get('goles_tot',0))
        if gl >= 1.5:
            pr = round(p_poisson(gl, 0.5)*100, 1)
            cu = cuota_estimada(pr)
            if cu >= 1.20:
                add(f"{eq} marca al menos 1 gol", pr, cu, '⚽', f'Goles {eq}',
                    f"{eq} promedia {round(gl,1)} goles/partido")

    # Saques de banda totales del partido
    sb_tot_l = stats.get(local,{}).get('saques_banda_5', stats.get(local,{}).get('saques_banda_tot',0))
    sb_tot_v = stats.get(visit,{}).get('saques_banda_5', stats.get(visit,{}).get('saques_banda_tot',0))
    sb_total = sb_tot_l + sb_tot_v
    if sb_total >= 25:
        for lin in [22.5, 25.5, 28.5]:
            pr = round(p_poisson(sb_total, lin)*100, 1)
            cu = cuota_estimada(pr)
            if cu >= 1.20:
                add(f"Saques de banda totales +{lin}", pr, cu, '🏳️', 'Saques Banda',
                    f"Total esperado {round(sb_total,1)} saques de banda")

    # Eliminar duplicados, ordenar por cuota desc luego prob desc
    vistos = set()
    result = []
    for pk in sorted(picks, key=lambda x: (x['cuota'], x['prob']), reverse=True):
        key = pk['mercado'][:25].lower()
        if key not in vistos:
            vistos.add(key)
            result.append(pk)
    return result

def seleccionar_publicos(todos, max_picks=4, cuota_min=1.50):
    """
    Selecciona picks con cuota >= 1.50 y prob >= 55%.
    Si faltan, combina picks seguros de distintos partidos.
    Máximo 4 picks.
    """
    # Candidatos individuales — prob >60% y cuota >1.50
    # Ordenar por probabilidad primero, luego EV — el modelo elige el más confiable
    individuales = [pk for pk in todos
                   if pk['cuota'] >= cuota_min and pk['prob'] >= 60]
    individuales.sort(key=lambda x: (x['prob'], x.get('ev',0)), reverse=True)
    individuales.sort(key=lambda x: (x.get('ev',0), x['prob']), reverse=True)

    resultado = []
    partidos_usados = set()
    for pk in individuales:
        if pk['partido'] not in partidos_usados or len(resultado) == 0:
            pk['tipo'] = 'individual'
            resultado.append(pk)
            partidos_usados.add(pk['partido'])
        if len(resultado) >= max_picks:
            break

    # Si faltan picks, crear combinadas de 2 de distintos partidos
    if len(resultado) < max_picks:
        seguros = [pk for pk in todos if pk['prob'] >= 65 and pk['cuota'] >= 1.15]
        seguros.sort(key=lambda x: x['prob'], reverse=True)

        partidos_en_res = set(pk['partido'] for pk in resultado)

        for i in range(len(seguros)):
            for j in range(i+1, len(seguros)):
                pk1, pk2 = seguros[i], seguros[j]
                if pk1['partido'] == pk2['partido']: continue
                cuota_c = round(pk1['cuota'] * pk2['cuota'], 2)
                prob_c  = round(pk1['prob']/100 * pk2['prob']/100 * 100, 1)
                if cuota_c < cuota_min or prob_c < 55: continue

                combo = {
                    'partido': 'COMBINADA',
                    'local': f"{pk1['partido']} + {pk2['partido']}",
                    'visitante': '',
                    'mercado': f"{pk1['emoji']} {pk1['mercado'][:30]} + {pk2['emoji']} {pk2['mercado'][:30]}",
                    'prob': prob_c,
                    'cuota': cuota_c,
                    'cuota_display': cuota_c,
                    'ev': round((prob_c/100)*cuota_c - 1, 3),
                    'emoji': '🔗',
                    'categoria': 'Combinada',
                    'descripcion': f"Prob. combinada: {prob_c}% | {pk1['partido']} + {pk2['partido']}",
                    'fuente': 'calculada',
                    'tipo': 'combinada',
                    'picks_combo': [pk1, pk2],
                }
                resultado.append(combo)
                if len(resultado) >= max_picks: break
            if len(resultado) >= max_picks: break

    # Asegurar cuota_display en individuales
    for pk in resultado:
        if 'cuota_display' not in pk:
            pk['cuota_display'] = pk['cuota']
        if 'tipo' not in pk:
            pk['tipo'] = 'individual'

    return resultado[:max_picks]

def seleccionar_premium(todos, max_picks=3, prob_min=75):
    """
    Selecciona 3 picks premium: solos o combinados.
    - prob >= 75% y cuota >= 1.15
    - Variedad de mercados: no repetir categoría del mismo partido
    - Incluye combinadas de 2 picks muy seguros si mejoran la cuota
    """
    candidatos = [pk for pk in todos
                 if pk['prob'] >= prob_min and pk['cuota'] >= 1.15]
    candidatos.sort(key=lambda x: x['prob'], reverse=True)

    resultado = []
    vistos = set()

    # Primero picks individuales variados
    for pk in candidatos:
        key = f"{pk['partido']}|{pk['categoria'][:10]}"
        if key not in vistos:
            vistos.add(key)
            pk['tipo'] = 'premium'
            resultado.append(pk)
        if len(resultado) >= max_picks: break

    # Si faltan, crear combinadas de 2 picks muy seguros de distintos partidos
    if len(resultado) < max_picks:
        muy_seguros = [pk for pk in candidatos if pk['prob'] >= 80 and pk['cuota'] >= 1.12]
        for i in range(len(muy_seguros)):
            for j in range(i+1, len(muy_seguros)):
                pk1, pk2 = muy_seguros[i], muy_seguros[j]
                if pk1['partido'] == pk2['partido']: continue
                cuota_c = round(pk1['cuota'] * pk2['cuota'], 2)
                prob_c  = round(pk1['prob']/100 * pk2['prob']/100 * 100, 1)
                if cuota_c < 1.25 or prob_c < 60: continue
                combo = {
                    'partido': 'COMBINADA PREMIUM',
                    'local': f"{pk1['partido']} + {pk2['partido']}",
                    'visitante': '',
                    'mercado': f"{pk1['emoji']} {pk1['mercado'][:28]} + {pk2['emoji']} {pk2['mercado'][:28]}",
                    'prob': prob_c,
                    'cuota': cuota_c,
                    'cuota_display': cuota_c,
                    'ev': round((prob_c/100)*cuota_c - 1, 3),
                    'emoji': '💎',
                    'categoria': 'Combinada Premium',
                    'descripcion': f"Dos picks de máxima seguridad combinados — prob. {prob_c}%",
                    'fuente': 'calculada',
                    'tipo': 'combinada',
                    'picks_combo': [pk1, pk2],
                }
                resultado.append(combo)
                if len(resultado) >= max_picks: break
            if len(resultado) >= max_picks: break

    # Si aún faltan, bajar umbral a 70%
    if len(resultado) < max_picks:
        for pk in sorted(todos, key=lambda x: x['prob'], reverse=True):
            if pk['cuota'] >= 1.12 and pk['prob'] >= 70:
                key = f"{pk['partido']}|{pk['categoria'][:10]}"
                if key not in vistos:
                    vistos.add(key)
                    pk['tipo'] = 'premium'
                    resultado.append(pk)
            if len(resultado) >= max_picks: break

    return resultado[:max_picks]


# ── HTML PÚBLICO ──────────────────────────────────────────────────────────────
def html_publico(picks, hoy, fecha_gen):
    ISO_J   = json.dumps(BANDERAS_ISO, ensure_ascii=False)
    PICKS_J = json.dumps(picks, ensure_ascii=False, default=str)
    return f"""<!DOCTYPE html>
<html lang="es">
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
.nav-links a:hover{{color:var(--tx)}}
header{{text-align:center;padding:26px 0 16px}}
header h1{{font-size:1.45rem;font-weight:700}}
header p{{color:var(--tx2);font-size:.84rem;margin-top:5px}}
.badge{{display:inline-block;border:1px solid var(--lin);border-radius:999px;
padding:2px 11px;font-size:.75rem;color:var(--tx2);margin:3px 2px}}
.badge.hoy{{border-color:var(--ac);color:var(--ac)}}
.tg-btn{{display:block;text-align:center;background:var(--ac);color:#0d1220;border-radius:10px;
padding:11px;font-weight:700;text-decoration:none;margin:14px 0;font-size:.88rem}}
.tg-btn:hover{{opacity:.9}}
.resumen{{background:var(--panel);border:1px solid var(--lin);border-radius:12px;
padding:14px;margin-bottom:18px;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center}}
.rs-v{{font-size:1.25rem;font-weight:700;color:var(--ac)}}
.rs-l{{font-size:.7rem;color:var(--tx2)}}
.pick{{background:var(--panel);border:1px solid var(--lin);border-radius:14px;
padding:18px;margin-bottom:12px;position:relative}}
.pick.alta{{border-color:var(--v)}}
.pick.combo{{border-color:var(--pu)}}
.pick.value{{border-color:var(--go)}}
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
const nC=PICKS.filter(p=>p.tipo==='combinada').length;
const nV=PICKS.filter(p=>p.ev&&p.ev>0.05).length;
document.getElementById('res').innerHTML=`
  <div><div class="rs-v">${{PICKS.length}}</div><div class="rs-l">Picks</div></div>
  <div><div class="rs-v" style="color:var(--v)">${{probP}}%</div><div class="rs-l">Prob. prom.</div></div>
  <div><div class="rs-v" style="color:var(--go)">${{cuotaP}}</div><div class="rs-l">Cuota prom.</div></div>
  <div><div class="rs-v" style="color:var(--pu)">${{nV}}</div><div class="rs-l">Con EV+</div></div>`;

const cont=document.getElementById('picks');
PICKS.forEach((pk,i)=>{{
  const esC=pk.tipo==='combinada';
  const esV=pk.ev&&pk.ev>0.10;
  const cls=esC?'combo':esV?'value':'alta';
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

# ── HTML PREMIUM ──────────────────────────────────────────────────────────────
def html_premium(picks, hoy, fecha_gen):
    ISO_J   = json.dumps(BANDERAS_ISO, ensure_ascii=False)
    PICKS_J = json.dumps(picks, ensure_ascii=False, default=str)
    cuota_acum = round(__import__('functools').reduce(lambda a,b: a*b, [p['cuota'] for p in picks], 1), 2) if picks else 1
    return f"""<!DOCTYPE html>
<html lang="es">
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
.resumen{{background:linear-gradient(135deg,var(--panel),rgba(255,215,0,.04));
border:1px solid rgba(255,215,0,.2);border-radius:12px;
padding:14px;margin-bottom:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:8px;text-align:center}}
.rs-v{{font-size:1.25rem;font-weight:700;color:var(--go)}}
.rs-l{{font-size:.7rem;color:var(--tx2)}}
.acum-box{{background:rgba(255,215,0,.07);border:1px solid rgba(255,215,0,.25);border-radius:10px;
padding:12px 16px;text-align:center;margin-bottom:16px}}
.acum-box .title{{font-size:.8rem;color:var(--tx2);margin-bottom:4px}}
.acum-box .val{{font-size:1.6rem;font-weight:700;color:var(--go)}}
.pick{{background:linear-gradient(135deg,var(--panel),rgba(255,215,0,.03));
border:1px solid rgba(255,215,0,.25);border-radius:14px;padding:18px;margin-bottom:12px;position:relative}}
.pick-n{{position:absolute;top:10px;right:12px;font-size:.72rem;color:var(--go);
font-weight:700;background:rgba(255,215,0,.1);border-radius:5px;padding:1px 7px}}
.seg-bar{{height:7px;background:var(--panel2);border-radius:4px;overflow:hidden;margin:10px 0}}
.seg-inner{{height:100%;background:linear-gradient(90deg,var(--v),var(--go));border-radius:4px;transition:width .5s}}
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
    <p>Los 4 picks con mayor probabilidad de acierto del día</p>
    <span class="badge">📅 {fecha_gen}</span>
    <span class="badge">🔐 Acceso exclusivo suscriptores</span>
  </header>
  <div class="resumen" id="res"></div>
  <div class="acum-box">
    <div class="title">📈 Cuota acumulador (los 4 combinados)</div>
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
  d.innerHTML=`
    <div class="pick-n">💎 #${{i+1}}</div>
    <div class="ph">
      <div class="ph-em">${{pk.emoji}}</div>
      <div class="ph-info">
        <div class="sub">${{fl(pk.local)}} ${{pk.partido}} · ${{pk.categoria}}</div>
        <div class="merc">${{pk.mercado}}</div>
      </div>
    </div>
    <div class="seg-bar"><div class="seg-inner" style="width:${{pk.prob}}%"></div></div>
    <div class="stats">
      <div class="sb"><div class="v" style="color:var(--v)">${{pk.prob}}%</div><div class="l">Probabilidad</div></div>
      <div class="sb"><div class="v" style="color:var(--go)">@${{pk.cuota}}</div><div class="l">Cuota est.</div></div>
      <div class="sb"><div class="v" style="color:var(--pu)">#${{i+1}}</div><div class="l">Ranking</div></div>
    </div>
    ${{pk.descripcion?`<div class="desc">💡 ${{pk.descripcion}}</div>`:''}}
  `;
  cont.appendChild(d);
}});
</script>
</body></html>"""

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("\n🚀 GENERADOR DE PICKS INTELIGENTE")
    print("="*55)
    hoy      = date.today().strftime('%Y-%m-%d')
    fecha_gen = datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')

    csv = os.path.join(RAIZ,'Predicciones','predicciones_finales.csv')
    df  = pd.read_csv(csv)
    hoy_df = df[df['Fecha']==hoy]
    print(f"✅ Partidos de hoy: {len(hoy_df)}")

    print("📡 Obteniendo cuotas...")
    cuotas = obtener_cuotas()

    todos = []
    for _, r in hoy_df.iterrows():
        key   = (r['Local'], r['Visitante'])
        cq    = cuotas.get(key, {})
        picks = generar_picks_partido(r, cq)
        todos.extend(picks)
        print(f"   ⚽ {r['Local']} vs {r['Visitante']}: {len(picks)} picks")

    print(f"\n✅ Total picks: {len(todos)}")

    picks_pub  = seleccionar_publicos(todos)
    picks_prem = seleccionar_premium(todos, max_picks=3)

    print(f"\n📋 PANEL PÚBLICO ({len(picks_pub)} picks):")
    for i,pk in enumerate(picks_pub,1):
        ev = f" EV:{pk['ev']:+.1%}" if pk.get('ev') else ""
        print(f"   #{i} {pk['emoji']} {pk['mercado'][:45]}")
        print(f"      {pk['partido']} | {pk['prob']}% | @{pk.get('cuota_display',pk['cuota'])}{ev}")

    print(f"\n💎 PANEL PREMIUM ({len(picks_prem)} picks):")
    for i,pk in enumerate(picks_prem,1):
        print(f"   #{i} {pk['emoji']} {pk['mercado'][:45]}")
        print(f"      {pk['partido']} | {pk['prob']}% | @{pk['cuota']}")

    os.makedirs('docs', exist_ok=True)
    with open('docs/picks_dia.html',     'w', encoding='utf-8') as f: f.write(html_publico(picks_pub,  hoy, fecha_gen))
    with open('docs/picks_premium.html', 'w', encoding='utf-8') as f: f.write(html_premium(picks_prem, hoy, fecha_gen))

    print(f"\n✅ docs/picks_dia.html generado")
    print(f"✅ docs/picks_premium.html generado")

if __name__ == '__main__':
    main()