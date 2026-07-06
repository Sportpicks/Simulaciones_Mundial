# -*- coding: utf-8 -*-
"""
generar_web_v6.py
Web final con mercados razonados por equipo o total según datos.
El modelo decide automáticamente si mostrar estadísticas
por equipo individual o como total del partido.

Uso: python generar_web_v6.py
"""

import os, sys, json, math
from datetime import datetime, timezone
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
sys.path.insert(0, os.path.join(RAIZ, '04_Prediccion'))
import prediccion_mundial as pm
from razonador_mercados import razonar_partido, cargar_stats

CSV_FINAL  = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
JSON_STATS = os.path.join(RAIZ, 'Data', 'stats_equipos.json')

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

def p_poisson_mas_de(lam, linea):
    k_min = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(k_min))
    except:
        return 0.0

def mejor_apuesta_global(p):
    """
    Busca la MEJOR apuesta entre TODOS los mercados disponibles.
    No solo 1X2 — también goles, córners, tiros, faltas y tarjetas.
    Retorna el mercado con mayor probabilidad de acierto.
    """
    local  = p['local']
    visit  = p['visitante']
    p1     = p['p1']
    px     = p['px']
    p2     = p['p2']
    xgl    = p.get('xgl', 0)
    xgv    = p.get('xgv', 0)
    xg_total  = xgl + xgv
    lam_cor   = p.get('cor', 9.0)
    lam_tar   = p.get('tar', 4.0)
    lam_tiros = p.get('tiros', 7.0)
    lam_fal   = p.get('faltas', 22.0)

    candidatos = []

    # ── 1X2 ──
    if p1 > 60:
        candidatos.append({'mercado': f'Victoria {local}',   'prob': p1,  'emoji': '⚽', 'cat': '1X2'})
    if p2 > 60:
        candidatos.append({'mercado': f'Victoria {visit}',   'prob': p2,  'emoji': '⚽', 'cat': '1X2'})

    # ── Doble oportunidad ──
    do_1x = round(p1+px, 1)
    do_x2 = round(px+p2, 1)
    do_12 = round(p1+p2, 1)
    # Doble oportunidad: solo mostrar cuando tiene valor real (prob <= 88% para cuota >= 1.14)
    # "Sin empate" en eliminatorias casi siempre es 95%+ — no tiene valor
    if do_1x >= 70 and do_1x <= 85: candidatos.append({'mercado': f'1X ({local} o empate)',    'prob': do_1x, 'emoji': '🛡️', 'cat': 'Doble Op.'})
    if do_x2 >= 70 and do_x2 <= 85: candidatos.append({'mercado': f'X2 (empate o {visit})',    'prob': do_x2, 'emoji': '🛡️', 'cat': 'Doble Op.'})
    if do_12 >= 75 and do_12 <= 88: candidatos.append({'mercado': 'Sin empate (1 o 2)',         'prob': do_12, 'emoji': '🛡️', 'cat': 'Doble Op.'})

    # ── Goles via xG (sin líneas triviales) ──
    for linea, label in [(1.5,'1.5'),(2.5,'2.5'),(3.5,'3.5')]:
        prob = round(p_poisson_mas_de(xg_total, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Más de {label} goles', 'prob': prob, 'emoji': '🥅', 'cat': 'Goles'})
    prob_u25 = round((1-p_poisson_mas_de(xg_total, 2.5))*100 + p_poisson_mas_de(xg_total,2.5)*100)
    prob_u25 = 100 - round(p_poisson_mas_de(xg_total, 2.5)*100)
    if prob_u25 >= 60:
        candidatos.append({'mercado': 'Menos de 2.5 goles', 'prob': prob_u25, 'emoji': '🔒', 'cat': 'Goles'})

    # ── Córners ──
    for linea in [7.5, 8.5, 9.5, 10.5]:
        prob = round(p_poisson_mas_de(lam_cor, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Córners más de {linea}', 'prob': prob, 'emoji': '⛳', 'cat': 'Córners'})

    # ── Tiros a puerta ──
    for linea in [4.5, 5.5, 6.5]:
        prob = round(p_poisson_mas_de(lam_tiros, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Tiros a puerta más de {linea}', 'prob': prob, 'emoji': '🎯', 'cat': 'Tiros'})

    # ── Faltas ──
    for linea in [18.5, 20.5]:
        prob = round(p_poisson_mas_de(lam_fal, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Faltas más de {linea}', 'prob': prob, 'emoji': '🦵', 'cat': 'Faltas'})

    # ── Tarjetas ──
    for linea in [3.5, 4.5]:
        prob = round(p_poisson_mas_de(lam_tar, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Tarjetas más de {linea}', 'prob': prob, 'emoji': '🟨', 'cat': 'Tarjetas'})

    if not candidatos:
        return None

    # Elegir el mercado con mejor valor — no simplemente el de mayor prob
    # Penalizar mercados con prob > 90% (cuota demasiado baja, sin valor real)
    # Priorizar mercados de goles, corners, tarjetas sobre doble oportunidad
    def score_mejor(c):
        p = c['prob']
        penalidad = max(0, (p - 88) * 3)  # penalizar prob muy alta
        bonus_cat = 4 if c.get('cat') in ('Goles', 'Córners', 'Tarjetas', 'Tiros', 'Faltas') else 0
        return p - penalidad + bonus_cat
    mejor = max(candidatos, key=score_mejor)
    prob  = mejor['prob']

    if prob >= 85:   nivel, emoji_n, clase = 'Muy Alta', '🟢', 'muy-alta'
    elif prob >= 75: nivel, emoji_n, clase = 'Alta',     '🟢', 'alta'
    elif prob >= 65: nivel, emoji_n, clase = 'Media',    '🟡', 'media'
    elif prob >= 55: nivel, emoji_n, clase = 'Leve',     '🟠', 'leve'
    else: return None

    return {
        'mercado'    : mejor['mercado'],
        'prob'       : prob,
        'nivel'      : nivel,
        'emoji'      : emoji_n,
        'texto'      : nivel,
        'tipo_emoji' : mejor['emoji'],
        'categoria'  : mejor['cat'],
        'clase'      : clase,
    }

def construir_datos():
    if not os.path.exists(CSV_FINAL):
        print(f"❌ No se encontró {CSV_FINAL}")
        sys.exit(1)

    df_pred = pd.read_csv(CSV_FINAL)
    _, df_vars, _, fechas_reales = pm.cargar_mundial()
    stats_eq = cargar_stats()

    partidos = []
    for _, r in df_pred.iterrows():
        a, b = r['Local'], r['Visitante']

        # Estadísticas base del modelo
        try:
            from prediccion_mundial import cargar_mundial
            stats_model = df_vars.set_index('Equipo')
            lam_cor = (stats_model.loc[a,'avg_Córneres_5'] + stats_model.loc[b,'avg_Córneres_5'] +
                       stats_model.loc[a,'avg_Córneres_total'] + stats_model.loc[b,'avg_Córneres_total']) / 2
            lam_tar = (stats_model.loc[a,'avg_Tarjetas_amarillas_5'] + stats_model.loc[b,'avg_Tarjetas_amarillas_5'] +
                       stats_model.loc[a,'avg_Tarjetas_amarillas_total'] + stats_model.loc[b,'avg_Tarjetas_amarillas_total']) / 2
        except:
            lam_cor, lam_tar = 9.0, 4.0

        lam_tiros  = float(r.get('tiros_esp', 7.0))
        lam_faltas = float(r.get('faltas_esp', 22.0))

        vm_l = float(r.get('VM_Local', 100))
        vm_v = float(r.get('VM_Visitante', 100))
        ratio = vm_l / (vm_v + 1)
        es_sorpresa = ratio > 5 or (1/max(ratio,0.01)) > 5

        p = {
            'fecha'    : str(r.get('Fecha', '')),
            'grupo'    : r.get('Grupo', ''),
            'local'    : a, 'visitante': b,
            'marcador' : r.get('Marcador_Predicho', ''),
            'fuente'   : r.get('Fuente_Final', ''),
            'p1'  : round(float(r['Prob_1_Final']), 1),
            'px'  : round(float(r['Prob_X_Final']), 1),
            'p2'  : round(float(r['Prob_2_Final']), 1),
            'p1o' : round(float(r.get('Prob_1_Orig', r['Prob_1_Final'])), 1),
            'pxo' : round(float(r.get('Prob_X_Orig', r['Prob_X_Final'])), 1),
            'p2o' : round(float(r.get('Prob_2_Orig', r['Prob_2_Final'])), 1),
            'p1dc': round(float(r.get('DC_Prob_1', r['Prob_1_Final'])), 1),
            'pxdc': round(float(r.get('DC_Prob_X', r['Prob_X_Final'])), 1),
            'p2dc': round(float(r.get('DC_Prob_2', r['Prob_2_Final'])), 1),
            'xgl' : round(float(r.get('xG_L', 0)), 2),
            'xgv' : round(float(r.get('xG_V', 0)), 2),
            # Mercados adicionales
            'cor'   : round(lam_cor, 1),
            'tiros' : round(lam_tiros, 1),
            'faltas': round(lam_faltas, 1),
            'tar'   : round(lam_tar, 1),
            't35'   : round(p_poisson_mas_de(lam_tar,3.5)*100),
            't45'   : round(p_poisson_mas_de(lam_tar,4.5)*100),
            'vml'   : int(vm_l), 'vmv': int(vm_v),
            'es_sorpresa': es_sorpresa,
        }

        # Mejor apuesta GLOBAL (todos los mercados)
        p['mejor_apuesta'] = mejor_apuesta_global(p)

        # Mercados razonados por equipo o total
        mercados_razonados = razonar_partido(a, b, lam_tiros, lam_cor, lam_faltas)
        p['mercados_razonados'] = mercados_razonados[:4]  # Máx 4 mercados

        partidos.append(p)

    partidos.sort(key=lambda p: (p['fecha'], p['grupo']))

    mc = pd.read_csv('Predicciones/probabilidades_montecarlo.csv', index_col=0)
    campeon = [{'equipo': eq, 'r32': float(r['R32']), 'octavos': float(r['Octavos']),
                'cuartos': float(r['Cuartos']), 'semis': float(r['Semis']),
                'final': float(r['Final']), 'campeon': float(r['Campeon'])}
               for eq, r in mc.iterrows()]

    elim = pd.read_csv('Predicciones/predicciones_eliminatorias.csv')
    cuadro = [{'fase': r['Fase'], 'fechas': r['Fechas'], 'local': r['Local'],
               'visitante': r['Visitante'], 'marcador': r['Marcador_Predicho'],
               'avanza': r['Avanza'], 'p1': float(r['Prob_1']),
               'px': float(r['Prob_X']), 'p2': float(r['Prob_2'])}
              for _, r in elim.iterrows()]

    clasif = pd.read_csv('Predicciones/clasificacion_grupos.csv')
    tablas = {}
    for _, r in clasif.iterrows():
        tablas.setdefault(r['Grupo'], []).append({
            'pos': int(r['Posicion']), 'equipo': r['Equipo'],
            'pts': int(r['Pts']), 'dg': round(float(r['DG']), 2)})
    for g in tablas:
        tablas[g].sort(key=lambda x: x['pos'])

    return partidos, campeon, cuadro, tablas


HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mundial 2026 · Modelo Final v6</title>
<style>
:root{--bg:#0d1220;--panel:#161d31;--panel2:#1c2540;--tx:#eef1f8;--tx2:#9aa5c0;
--lin:#2a3554;--v:#34d399;--e:#fbbf24;--d:#fb7185;--ac:#60a5fa;--pu:#a78bfa;--or:#fb923c;--ro:#f43f5e}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:64px}
body{background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,sans-serif;padding-bottom:48px}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
nav{position:sticky;top:0;z-index:50;background:rgba(13,18,32,.95);backdrop-filter:blur(8px);border-bottom:1px solid var(--lin)}
nav .wrap{display:flex;gap:4px;overflow-x:auto;padding:10px 16px;scrollbar-width:none}
nav a{color:var(--tx2);text-decoration:none;font-size:.83rem;font-weight:600;padding:5px 12px;border-radius:999px;white-space:nowrap}
nav a:hover{color:var(--tx);background:var(--panel2)}
header{padding:28px 0 8px;text-align:center}
header h1{font-size:1.6rem;font-weight:700}
header p{color:var(--tx2);font-size:.88rem;max-width:700px;margin:8px auto 0}
.badges{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:10px}
.badge{display:inline-block;background:var(--panel2);border:1px solid var(--lin);color:var(--tx2);border-radius:999px;padding:2px 12px;font-size:.76rem}
.badge.v1{border-color:var(--ac);color:var(--ac)}.badge.v2{border-color:var(--pu);color:var(--pu)}
.badge.v3{border-color:var(--or);color:var(--or)}.badge.v4{border-color:var(--v);color:var(--v)}
h2{font-size:1.1rem;margin:32px 0 12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
h2 small{color:var(--tx2);font-weight:400;font-size:.82rem}
.fl{width:20px;height:15px;border-radius:2px;vertical-align:-2px;object-fit:cover;background:var(--panel2)}
.dias{display:flex;gap:6px;overflow-x:auto;padding:2px 2px 10px;scrollbar-width:none}
.dias button{flex:0 0 auto;background:var(--panel);border:1px solid var(--lin);color:var(--tx2);border-radius:999px;padding:5px 13px;font-size:.82rem;font-weight:600;cursor:pointer}
.dias button.sel{background:var(--ac);border-color:var(--ac);color:#0d1220}
.dias button.eshoy:not(.sel){border-color:var(--ac);color:var(--ac)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--lin);border-radius:14px;padding:16px}
.card.hoy{border-color:var(--ac)}.card.sorpresa{border-color:var(--ro)}
.enc{display:flex;justify-content:space-between;align-items:center;font-size:.76rem;color:var(--tx2);margin-bottom:8px;flex-wrap:wrap;gap:4px}
.eqs{display:flex;justify-content:space-between;align-items:center;gap:8px;font-weight:600;font-size:.98rem}
.eqs span{display:flex;align-items:center;gap:6px;min-width:0}
.eqs span:last-child{justify-content:flex-end;text-align:right}
.marc{background:var(--panel2);border:1px solid var(--lin);border-radius:10px;padding:2px 10px;font-size:1rem;white-space:nowrap}
.barra{display:flex;height:8px;border-radius:6px;overflow:hidden;margin:10px 0 3px;background:var(--panel2)}
.barra i{display:block;height:100%}
.leyenda{display:flex;justify-content:space-between;font-size:.76rem;margin-bottom:6px}
.mejor-apuesta{border-radius:10px;padding:10px 12px;margin:8px 0;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.mejor-apuesta.muy-alta{background:rgba(52,211,153,0.12);border:1px solid var(--v)}
.mejor-apuesta.alta{background:rgba(251,191,36,0.10);border:1px solid var(--e)}
.mejor-apuesta.media{background:rgba(251,146,60,0.10);border:1px solid var(--or)}
.mejor-apuesta .ma-label{font-size:.72rem;color:var(--tx2);margin-bottom:2px}
.mejor-apuesta .ma-mercado{font-size:.88rem;font-weight:700}
.mejor-apuesta .ma-right{text-align:right;flex-shrink:0}
.mejor-apuesta .ma-prob{font-size:1.1rem;font-weight:700}
.mejor-apuesta.muy-alta .ma-prob{color:var(--v)}
.mejor-apuesta.alta .ma-prob{color:var(--e)}
.mejor-apuesta.media .ma-prob{color:var(--or)}
.mejor-apuesta .ma-nivel{font-size:.72rem;color:var(--tx2)}
/* Mercados razonados */
.mercados-razonados{margin-top:10px}
.mercados-razonados .titulo-sec{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;
color:var(--tx2);font-weight:600;margin-bottom:5px;display:flex;align-items:center;gap:6px}
.mercados-razonados .titulo-sec::after{content:'';flex:1;height:1px;background:var(--lin)}
.mercado-item{background:var(--panel2);border-radius:6px;padding:5px 8px;margin-bottom:4px;
display:flex;justify-content:space-between;align-items:center;gap:8px}
.mercado-item .mi-left{display:flex;align-items:center;gap:5px;min-width:0;flex:1}
.mercado-item .mi-nombre{font-size:.78rem;font-weight:500;color:var(--tx);
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mi-tipo{font-size:.7rem;border-radius:3px;padding:1px 4px;flex-shrink:0}
.mi-tipo.total{background:rgba(96,165,250,0.15);color:var(--ac)}
.mi-tipo.equipo{background:rgba(167,139,250,0.15);color:var(--pu)}
.mercado-item .mi-prob{font-size:.9rem;font-weight:700;flex-shrink:0;white-space:nowrap}
.prob-alta{color:var(--v)}.prob-media{color:var(--e)}.prob-baja{color:var(--or)}
.fuentes{background:var(--panel2);border-radius:8px;padding:6px 10px;font-size:.72rem;color:var(--tx2);margin-bottom:8px}
.fuentes b{color:var(--tx);display:block;margin-bottom:3px;font-size:.74rem}
.fuentes-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;text-align:center}
.fuentes-grid div{background:var(--bg);border-radius:6px;padding:3px 6px}
.fuentes-grid span{display:block;font-size:.68rem;opacity:.7}
.vm-bar{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:.72rem;color:var(--tx2)}
.vm-bar-inner{flex:1;height:5px;background:var(--panel2);border-radius:3px;overflow:hidden}
.vm-bar-inner i{display:block;height:100%;background:var(--ac);border-radius:3px}
.etiq{font-size:.68rem;border:1px solid var(--lin);border-radius:6px;padding:1px 6px;color:var(--tx2);white-space:nowrap}
.etiq.jugado{border-color:var(--e);color:var(--e)}
.etiq.sorpresa{border-color:var(--ro);color:var(--ro)}
.etiq.multi{border-color:var(--pu);color:var(--pu)}
.vd{color:var(--v)}.em{color:var(--e)}.dr{color:var(--d)}
table{width:100%;border-collapse:collapse;font-size:.81rem}
th,td{padding:6px 8px;text-align:left;border-bottom:1px solid var(--lin)}
th{color:var(--tx2);font-weight:600;font-size:.74rem;text-transform:uppercase;letter-spacing:.04em}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.mcbar{height:7px;background:var(--panel2);border-radius:5px;overflow:hidden;min-width:60px}
.mcbar i{display:block;height:100%;background:var(--ac)}
details{background:var(--panel);border:1px solid var(--lin);border-radius:12px;margin-bottom:10px;overflow:hidden}
summary{cursor:pointer;padding:12px 16px;font-weight:600;list-style:none;display:flex;align-items:center;gap:8px}
summary::after{content:"+";color:var(--tx2);margin-left:auto}
details[open] summary::after{content:"–"}
details .inner{padding:0 16px 14px;overflow-x:auto}
.subtit{font-size:.74rem;text-transform:uppercase;letter-spacing:.04em;color:var(--tx2);margin:14px 0 6px;font-weight:600}
.oculto{display:none}
.btn{display:block;margin:12px auto 2px;background:var(--panel2);border:1px solid var(--lin);color:var(--tx);border-radius:999px;padding:7px 18px;font-size:.83rem;font-weight:600;cursor:pointer}
.btn:hover{border-color:var(--ac)}
.aviso{background:var(--panel);border-left:4px solid var(--e);border-radius:0 12px 12px 0;padding:14px 16px;font-size:.81rem;color:var(--tx2);margin-top:32px}
.vacio{background:var(--panel);border:1px dashed var(--lin);border-radius:12px;padding:22px;text-align:center;color:var(--tx2);grid-column:1/-1}
footer{text-align:center;color:var(--tx2);font-size:.76rem;margin-top:28px}
footer a{color:var(--ac);text-decoration:none}
@media(max-width:560px){.fuentes-grid{grid-template-columns:1fr 1fr}}

.tg-nav{background:#0088cc !important;color:#fff !important;border-radius:6px;
  padding:4px 12px !important;font-weight:700 !important}

/* ── HERO SECTION ── */
.hero-wrap{background:linear-gradient(180deg,#0d1a2e 0%,#0d1220 100%);
  border-bottom:1px solid #1a2a44;padding:20px 0 18px}
.hero-titulo{font-size:1.4rem;font-weight:800;text-align:center;
  color:#eef1f8;margin-bottom:4px}
.hero-sub{font-size:.78rem;color:#9aa5c0;text-align:center;margin-bottom:16px}
.hero-btns{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.hero-btn-pub{background:#34d399;color:#0d1220;border-radius:12px;
  padding:13px 8px;font-weight:800;font-size:.88rem;text-decoration:none;
  text-align:center;display:block;box-shadow:0 2px 10px rgba(52,211,153,.3)}
.hero-btn-prem{background:linear-gradient(135deg,#a78bfa,#7c3aed);color:#fff;
  border-radius:12px;padding:13px 8px;font-weight:800;font-size:.88rem;
  text-decoration:none;text-align:center;display:block;
  box-shadow:0 2px 10px rgba(167,139,250,.3)}
.hero-tg{display:flex;align-items:center;gap:12px;background:#004f7c;
  border:1.5px solid #0088cc;border-radius:12px;padding:12px 16px;
  text-decoration:none;margin-bottom:4px;transition:background .2s}
.hero-tg:hover{background:#005f8f}
.hero-tg-title{color:#fff;font-weight:700;font-size:.88rem}
.hero-tg-sub{color:rgba(255,255,255,.75);font-size:.72rem;margin-top:1px}
@media(min-width:640px){
  .hero-titulo{font-size:1.8rem}
  .hero-btns{grid-template-columns:repeat(2,auto);justify-content:center;gap:12px}
  .hero-btn-pub,.hero-btn-prem{padding:13px 28px;font-size:.95rem}
}
.tg-banner{display:flex;align-items:center;justify-content:space-between;
  background:#004f7c;border:1px solid #0088cc;border-radius:12px;
  padding:14px 20px;margin:16px 0;gap:12px;flex-wrap:wrap}
.tg-banner-txt{color:#fff;font-size:.9rem;font-weight:600}
.tg-banner-sub{color:rgba(255,255,255,.75);font-size:.78rem;margin-top:2px}
.tg-banner-btn{background:#0088cc;color:#fff;border-radius:8px;
  padding:8px 18px;font-weight:700;font-size:.85rem;text-decoration:none;white-space:nowrap}

.picks-aviso{display:flex;align-items:center;gap:14px;background:#0d2235;
  border:2px solid #60a5fa;border-radius:14px;padding:16px 20px;margin:16px 0;flex-wrap:wrap}
.picks-aviso-ico{font-size:2rem;flex-shrink:0}
.picks-aviso-txt{flex:1;min-width:180px}
.picks-aviso-title{font-size:1rem;font-weight:700;color:#eef1f8}
.picks-aviso-sub{font-size:.78rem;color:#9aa5c0;margin-top:2px}
.picks-aviso-btns{display:flex;gap:8px;flex-wrap:wrap}
.btn-picks-pub{background:#34d399;color:#0d1220;border-radius:8px;
  padding:8px 16px;font-weight:700;font-size:.82rem;text-decoration:none;white-space:nowrap}
.btn-picks-prem{background:#a78bfa;color:#0d1220;border-radius:8px;
  padding:8px 16px;font-weight:700;font-size:.82rem;text-decoration:none;white-space:nowrap}
</style>
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-J4LP4JRR1N"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-J4LP4JRR1N');
</script>
</head>
<body>
<nav><div class="wrap">
  <a href="#t-dias">📅 Partidos</a>
  <a href="#t-mc">🏆 Campeón</a>
  <a href="#t-elim">🗺️ Eliminatorias</a>
  <a href="picks_dia.html">🎯 Picks hoy</a>
  <a href="picks_publicos_v2.html">📊 Historial</a>
  <a class="tg-nav" href="https://t.me/sportpickoficial" target="_blank">📣 Telegram</a>
</div></nav>

<!-- HERO SECTION — primera impresion móvil -->
<div class="hero-wrap">
  <div class="wrap">
    <div class="hero-titulo">⚽ Mundial 2026 — Modelo Final</div>
    <div class="hero-sub">Predicciones con IA · XGBoost + Dixon-Coles · 25 casas de apuestas</div>

    <!-- CTA principal — picks -->
    <div class="hero-btns">
      <a href="picks_dia.html" class="hero-btn-pub">
        ✅ Ver picks GRATIS
      </a>
      <a href="picks_premium.html" class="hero-btn-prem">
        💎 Picks Premium S/25
      </a>
    </div>

    <!-- CTA Telegram -->
    <a href="https://t.me/sportpickoficial" target="_blank" class="hero-tg">
      <span style="font-size:1.3rem">📣</span>
      <div>
        <div class="hero-tg-title">Únete al canal GRATIS</div>
        <div class="hero-tg-sub">Picks diarios · SportPicks Oficial · t.me/sportpickoficial</div>
      </div>
      <span style="color:#fff;font-size:1.1rem">→</span>
    </a>

    <div class="badges" style="margin-top:12px">
      <span class="badge">📅 __FECHA_GEN__</span>
      <span class="badge v1">🤖 XGBoost</span>
      <span class="badge v3">📐 Dixon-Coles</span>
    </div>
  </div>
</div>

<main class="wrap">
  <h2 id="t-dias">📅 Partidos <small id="sub-dia"></small></h2>
  <div class="dias" id="dias"></div>
  <div id="dia" class="cards"></div>

  <h2 id="t-mc">🏆 Campeón <small>Monte Carlo · 10.000 simulaciones</small></h2>
  <div class="card"><div style="overflow-x:auto">
  <table id="tabla-mc">
    <thead><tr><th>#</th><th>Selección</th><th class="num">Campeón</th><th class="num">Final</th><th class="num">Semis</th><th class="num">Pasa grupos</th><th style="width:20%"></th></tr></thead>
    <tbody></tbody>
  </table></div>
  <button class="btn" id="btn-mc">Ver las 48 selecciones</button></div>

  <div class="tg-banner" onclick="window.open('https://t.me/sportpickoficial','_blank')" style="cursor:pointer">
    <div style="font-size:1.8rem">📣</div>
    <div style="flex:1">
      <div class="tg-banner-txt">Canal GRATIS de SportPicks — Únete ahora</div>
      <div class="tg-banner-sub">✅ Picks públicos diarios · 💎 Análisis del modelo · ⚽ Mundial 2026</div>
    </div>
    <a class="tg-banner-btn" href="https://t.me/sportpickoficial" target="_blank" onclick="event.stopPropagation()">
      Unirme →
    </a>
  </div>

  <div class="picks-aviso">
    <div class="picks-aviso-ico">🎯</div>
    <div class="picks-aviso-txt">
      <div class="picks-aviso-title">Pronósticos del día disponibles</div>
      <div class="picks-aviso-sub">Análisis con IA · Cuotas reales · Picks públicos gratis y premium</div>
    </div>
    <div class="picks-aviso-btns">
      <a href="picks_dia.html" class="btn-picks-pub">✅ Ver picks gratis</a>
      <a href="picks_premium.html" class="btn-picks-prem">💎 Ver premium</a>
    </div>
  </div>

  <h2 id="t-elim">🗺️ Eliminatorias</h2>
  <div id="cuadro"></div>

  <div class="aviso">
    <b>⚠️ Mercados razonados automáticamente.</b>
    <span class="mi-tipo total" style="display:inline-block">🏟️ Total</span> = estadística del partido completo.
    <span class="mi-tipo equipo" style="display:inline-block">👤 Equipo</span> = equipo destacado individualmente según datos históricos.
    El modelo elige el mercado con mayor probabilidad de acierto en cada caso.
  </div>
  <footer>
    Modelo: <a href="https://github.com/Sportpicks/Simulaciones_Mundial">Simulaciones_Mundial</a>
    · XGBoost + Odds API + Dixon-Coles + Razonamiento por equipo ·
    <a href="picks_dia.html">🎯 Picks hoy</a> ·
    <a href="picks_publicos_v2.html">📊 Historial</a> ·
    <a href="https://t.me/sportpickoficial" target="_blank">📣 Telegram</a>
  </footer>
</main>

<script>
const PARTIDOS = __PARTIDOS_JSON__;
const CAMPEON  = __CAMPEON_JSON__;
const CUADRO   = __CUADRO_JSON__;
const TABLAS   = __TABLAS_JSON__;
const ISO      = __ISO_JSON__;

const isoLocal = d => d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
const HOY    = isoLocal(new Date());
const FECHAS = [...new Set(PARTIDOS.map(p=>p.fecha))].sort();
const FIN_G  = FECHAS[FECHAS.length-1];
const fl = eq => ISO[eq]?`<img class="fl" loading="lazy" alt="" src="https://flagcdn.com/w20/${ISO[eq]}.png">`:'';
const fmtF = f => { const[y,m,d]=f.split('-'); const ms=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']; return(+d)+' '+ms[+m-1]; };

function probClass(prob){ return prob>=75?'prob-alta':prob>=60?'prob-media':'prob-baja'; }

function tarjeta(p){
  const div = document.createElement('div');
  const esHoy = p.fecha===HOY;
  const yaJugado = p.fecha < HOY;
  div.className = 'card'+(esHoy?' hoy':'')+(p.es_sorpresa?' sorpresa':'');

  const jugBadge = yaJugado?'<span class="etiq jugado">ya jugado</span>':'';
  const sorBadge = p.es_sorpresa?'<span class="etiq sorpresa">⚠️ underdog</span>':'';
  const mulBadge = p.fuente&&p.fuente.includes('cuotas')?'<span class="etiq multi">✨ 4 fuentes</span>':'<span class="etiq">3 fuentes</span>';

  // Mejor apuesta 1X2
  let mejorHTML = '';
  if(!yaJugado && p.mejor_apuesta){
    const ma = p.mejor_apuesta;
    mejorHTML = `
    <div class="mejor-apuesta ${ma.clase||ma.nivel}">
      <div>
        <div class="ma-label">🏆 Mejor apuesta · <span style="opacity:.7;font-size:.68rem">${ma.categoria||''}</span></div>
        <div class="ma-mercado">${ma.tipo_emoji} ${ma.mercado}</div>
      </div>
      <div class="ma-right">
        <div class="ma-prob">${ma.prob}%</div>
        <div class="ma-nivel">${ma.emoji} ${ma.texto}</div>
      </div>
    </div>`;
  }

  // Mercados razonados
  let mercadosHTML = '';
  if(!yaJugado && p.mercados_razonados && p.mercados_razonados.length > 0){
    const items = p.mercados_razonados.map(m => {
      const tipoBadge = m.tipo==='total'
        ? '<span class="mi-tipo total">🏟️</span>'
        : '<span class="mi-tipo equipo">👤</span>';
      const pc = probClass(m.prob);
      return `<div class="mercado-item" title="${m.razon}">
        <div class="mi-left">
          ${tipoBadge}
          <span class="mi-nombre">${m.emoji} ${m.mercado}</span>
        </div>
        <div class="mi-prob ${pc}">${m.prob}%</div>
      </div>`;
    }).join('');

    mercadosHTML = `
    <div class="mercados-razonados">
      <div class="titulo-sec">🧠 Mercados razonados</div>
      ${items}
    </div>`;
  }

  // Fuentes comparativa
  const diff1 = Math.abs(p.p1-p.p1o)>0.5||Math.abs(p.p1-p.p1dc)>0.5;
  const fuentesHTML = diff1?`
    <div class="fuentes">
      <b>📊 Comparativa de fuentes</b>
      <div class="fuentes-grid">
        <div><span>XGBoost</span>${p.p1o}%·${p.pxo}%·${p.p2o}%</div>
        <div><span>Dixon-Coles</span>${p.p1dc}%·${p.pxdc}%·${p.p2dc}%</div>
        <div><span>✅ Final</span><b>${p.p1}%·${p.px}%·${p.p2}%</b></div>
      </div>
    </div>`:'';

  // VM bar
  const vmMax = Math.max(p.vml, p.vmv, 1);
  const vmHTML = `
    <div class="vm-bar">
      <span>${fl(p.local)} €${p.vml}M</span>
      <div class="vm-bar-inner"><i style="width:${Math.round(p.vml/vmMax*100)}%"></i></div>
      <div class="vm-bar-inner"><i style="width:${Math.round(p.vmv/vmMax*100)}%;background:var(--d)"></i></div>
      <span>€${p.vmv}M ${fl(p.visitante)}</span>
    </div>`;

  // Tarjetas (siempre total)
  const tarHTML = `
    <div style="background:var(--panel2);border-radius:10px;padding:8px 10px;font-size:.76rem;margin-top:8px">
      <b style="color:var(--e)">🟨 Tarjetas: ${p.tar} esp.</b><br>
      <span style="color:var(--tx2)">+3.5: ${p.t35}% · +4.5: ${p.t45}%</span>
    </div>`;

  div.innerHTML = `
    <div class="enc">
      <span>Grupo ${p.grupo} · ${fmtF(p.fecha)}</span>
      <span style="display:flex;gap:4px;flex-wrap:wrap">${jugBadge}${sorBadge}${mulBadge}</span>
    </div>
    <div class="eqs">
      <span>${fl(p.local)}${p.local}</span>
      <span class="marc">${p.marcador}</span>
      <span>${p.visitante}${fl(p.visitante)}</span>
    </div>
    <div class="barra">
      <i style="width:${p.p1}%;background:var(--v)"></i>
      <i style="width:${p.px}%;background:var(--e)"></i>
      <i style="width:${p.p2}%;background:var(--d)"></i>
    </div>
    <div class="leyenda">
      <span class="vd">1·${p.p1}%</span><span class="em">X·${p.px}%</span><span class="dr">2·${p.p2}%</span>
    </div>
    ${mejorHTML}
    ${fuentesHTML}
    ${vmHTML}
    ${mercadosHTML}
    ${tarHTML}`;
  return div;
}

let fechaSel = FECHAS.includes(HOY)?HOY:(FECHAS.find(f=>f>HOY)||FIN_G);
function pintarDia(){
  const cont=document.getElementById('dia'); cont.innerHTML='';
  const lista=PARTIDOS.filter(p=>p.fecha===fechaSel);
  document.getElementById('sub-dia').textContent=fechaSel===HOY?'hoy · '+fmtF(fechaSel):fmtF(fechaSel);
  if(!lista.length){const v=document.createElement('div');v.className='vacio';v.textContent='No hay partidos este día.';cont.appendChild(v);}
  else{lista.forEach(p=>cont.appendChild(tarjeta(p)));}
  document.querySelectorAll('#dias button').forEach(b=>b.classList.toggle('sel',b.dataset.f===fechaSel));
}
const contD=document.getElementById('dias');
FECHAS.forEach(f=>{
  const b=document.createElement('button');b.type='button';b.dataset.f=f;
  b.textContent=f===HOY?'HOY · '+fmtF(f):fmtF(f);
  if(f===HOY)b.classList.add('eshoy');
  b.onclick=()=>{fechaSel=f;pintarDia();};
  contD.appendChild(b);
});
pintarDia();
const selBtn=document.querySelector('#dias button.sel');
if(selBtn)selBtn.scrollIntoView({block:'nearest',inline:'center'});

const tb=document.querySelector('#tabla-mc tbody');
CAMPEON.forEach((c,i)=>{
  const tr=document.createElement('tr');
  if(i>=12)tr.classList.add('oculto','fila-extra');
  tr.innerHTML=`<td>${i+1}</td><td>${fl(c.equipo)}${c.equipo}</td>
  <td class="num"><b>${c.campeon.toFixed(1)}%</b></td><td class="num">${c.final.toFixed(1)}%</td>
  <td class="num">${c.semis.toFixed(1)}%</td><td class="num">${c.r32.toFixed(0)}%</td>
  <td><div class="mcbar"><i style="width:${Math.min(100,c.campeon*3.3)}%"></i></div></td>`;
  tb.appendChild(tr);
});
document.getElementById('btn-mc').onclick=function(){
  const oc=document.querySelectorAll('.fila-extra');
  const abrir=oc[0]&&oc[0].classList.contains('oculto');
  oc.forEach(f=>f.classList.toggle('oculto',!abrir));
  this.textContent=abrir?'Mostrar solo el top 12':'Ver las 48 selecciones';
};

// Sección grupos eliminada — torneo en fase eliminatoria

const contC=document.getElementById('cuadro');
[...new Set(CUADRO.map(c=>c.fase))].forEach(f=>{
  const det=document.createElement('details');
  det.open=true;  // Abrir todas las fases eliminatorias por defecto
  const filas=CUADRO.filter(c=>c.fase===f).map(c=>`
    <tr><td>${fl(c.local)}${c.local} – ${fl(c.visitante)}${c.visitante}</td>
    <td class="num"><b>${c.marcador}</b></td><td><b>${fl(c.avanza)}${c.avanza}</b></td>
    <td class="num vd">${c.p1}%</td><td class="num em">${c.px}%</td><td class="num dr">${c.p2}%</td></tr>`).join('');
  det.innerHTML=`<summary>${f} <span class="etiq" style="margin-left:6px">${CUADRO.find(c=>c.fase===f).fechas}</span></summary>
    <div class="inner"><table><thead><tr><th>Cruce</th><th class="num">Pred.</th><th>Avanza</th>
    <th class="num">1</th><th class="num">X</th><th class="num">2</th></tr></thead>
    <tbody>${filas}</tbody></table></div>`;
  contC.appendChild(det);
});
</script>

<!-- Banner flotante Telegram -->
<div id="tg-float" style="position:fixed;bottom:16px;right:12px;left:12px;z-index:9999;
  background:linear-gradient(135deg,#0088cc,#005f8f);border-radius:14px;
  padding:12px 16px;box-shadow:0 4px 20px rgba(0,136,204,.5);
  display:flex;align-items:center;gap:12px;
  animation:tgSlide .6s ease;cursor:pointer;border:1px solid rgba(255,255,255,.15);
  max-width:460px;margin:0 auto;">
  <div style="font-size:2rem;flex-shrink:0">📣</div>
  <div style="flex:1">
    <div style="color:#fff;font-weight:700;font-size:.88rem;line-height:1.3">Canal GRATIS de SportPicks</div>
    <div style="color:rgba(255,255,255,.8);font-size:.74rem;margin-top:3px">Picks diarios · Mundial 2026</div>
  </div>
  <button id="tg-close" style="background:rgba(255,255,255,.15);border:none;color:#fff;
    border-radius:50%;width:24px;height:24px;cursor:pointer;font-size:.8rem;
    display:flex;align-items:center;justify-content:center;flex-shrink:0">✕</button>
</div>
<style>
@keyframes tgSlide{{
  from{{transform:translateY(80px);opacity:0}}
  to{{transform:translateY(0);opacity:1}}
}}
</style>
<script>
(function(){{
  var b=document.getElementById('tg-float');
  var c=document.getElementById('tg-close');
  if(sessionStorage.getItem('tg_cerrado')){{b.style.display='none';return;}}
  b.addEventListener('click',function(e){{
    if(e.target!==c && !c.contains(e.target))
      window.open('https://t.me/sportpickoficial','_blank');
  }});
  c.addEventListener('click',function(e){{
    e.stopPropagation();
    b.style.display='none';
    sessionStorage.setItem('tg_cerrado','1');
  }});
}})();
</script>
</body>
</html>"""

if __name__ == '__main__':
    partidos, campeon, cuadro, tablas = construir_datos()
    html = (HTML
            .replace('__PARTIDOS_JSON__', json.dumps(partidos, ensure_ascii=False))
            .replace('__CAMPEON_JSON__',  json.dumps(campeon,  ensure_ascii=False))
            .replace('__CUADRO_JSON__',   json.dumps(cuadro,   ensure_ascii=False))
            .replace('__TABLAS_JSON__',   json.dumps(tablas,   ensure_ascii=False))
            .replace('__ISO_JSON__',      json.dumps(BANDERAS_ISO, ensure_ascii=False))
            .replace('__FECHA_GEN__',     datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')))
    os.makedirs('docs', exist_ok=True)
    with open('docs/index_final.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'✅ Web v6 generada — {len(partidos)} partidos')

    # Mostrar mercados razonados del día
    from datetime import date
    hoy = date.today().strftime('%Y-%m-%d')
    hoy_p = [p for p in partidos if p['fecha']==hoy]
    if hoy_p:
        print(f'\n🧠 Mercados razonados de hoy:')
        for p in hoy_p:
            print(f"\n   ⚽ {p['local']} vs {p['visitante']}")
            for m in p.get('mercados_razonados',[]):
                tipo = "🏟️" if m['tipo']=='total' else "👤"
                print(f"      {tipo} {m['emoji']} {m['mercado']}: {m['prob']}% — {m['razon']}")