# -*- coding: utf-8 -*-
"""
generar_panel_picks.py
Genera docs/picks_dia.html — Panel de Picks del Día.

Muestra TODOS los mercados disponibles para los partidos de hoy
ordenados por probabilidad de acierto, combinando:
- Probabilidades 1X2 del modelo
- Mercados razonados (tiros, córners, faltas por equipo/total)
- EV vs Pinnacle cuando disponible
- Clasificación por nivel de confianza

Uso: python generar_panel_picks.py
"""

import os, sys, json, math
from datetime import datetime, timezone, date
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)
sys.path.insert(0, os.path.join(RAIZ, '04_Prediccion'))

from razonador_mercados import razonar_partido, cargar_stats

CSV_PRED = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
CSV_EV   = os.path.join(RAIZ, 'Predicciones', 'ev_tracking.csv')

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

def p_poisson(lam, linea):
    k = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k))
    except:
        return 0.0

def nivel_confianza(prob):
    if prob >= 85: return '🟢', 'Muy Alta', 'muy-alta'
    if prob >= 75: return '🟢', 'Alta',     'alta'
    if prob >= 65: return '🟡', 'Media',    'media'
    if prob >= 55: return '🟠', 'Leve',     'leve'
    return '⚪', 'Baja', 'baja'

def generar_picks_partido(r, ev_row=None):
    """
    Genera lista completa de picks para un partido,
    combinando TODOS los mercados disponibles.
    """
    local  = r['Local']
    visit  = r['Visitante']
    p1     = float(r['Prob_1_Final'])
    px     = float(r['Prob_X_Final'])
    p2     = float(r['Prob_2_Final'])
    xgl    = float(r.get('xG_L', 0))
    xgv    = float(r.get('xG_V', 0))
    lam_tiros  = float(r.get('tiros_esp', 7.0))
    lam_cor    = float(r.get('cor', 9.0))
    lam_tar    = float(r.get('tar', 4.0))
    lam_faltas = float(r.get('faltas', 22.0))

    picks = []

    # ── 1X2 y doble oportunidad ──
    do_1x = round(p1 + px, 1)
    do_x2 = round(px + p2, 1)
    do_12 = round(p1 + p2, 1)

    # Victoria favorito
    if p1 > p2 and p1 > 60:
        ev = None
        cuota_ref = None
        if ev_row is not None and ev_row.get('Cuota_Pinnacle_1', 0) > 1:
            c = float(ev_row['Cuota_Pinnacle_1'])
            ev = round((p1/100)*c - 1, 3)
            cuota_ref = c
        picks.append({
            'mercado'  : f'Victoria {local}',
            'prob'     : p1, 'categoria': '1X2',
            'ev'       : ev, 'cuota'    : cuota_ref,
            'tipo'     : 'resultado', 'emoji': '⚽',
            'razon'    : f'{local} favorito con {p1}% de probabilidad',
        })
    elif p2 > p1 and p2 > 60:
        ev = None
        cuota_ref = None
        if ev_row is not None and ev_row.get('Cuota_Pinnacle_2', 0) > 1:
            c = float(ev_row['Cuota_Pinnacle_2'])
            ev = round((p2/100)*c - 1, 3)
            cuota_ref = c
        picks.append({
            'mercado'  : f'Victoria {visit}',
            'prob'     : p2, 'categoria': '1X2',
            'ev'       : ev, 'cuota'    : cuota_ref,
            'tipo'     : 'resultado', 'emoji': '⚽',
            'razon'    : f'{visit} favorito con {p2}% de probabilidad',
        })

    # Doble oportunidad
    if do_1x >= 75:
        ev = None
        picks.append({
            'mercado': f'1X — {local} o Empate',
            'prob': do_1x, 'categoria': 'Doble Op.',
            'ev': ev, 'cuota': None,
            'tipo': 'doble', 'emoji': '🛡️',
            'razon': f'Cubre victoria {local} + empate = {do_1x}%',
        })
    if do_x2 >= 75:
        picks.append({
            'mercado': f'X2 — Empate o {visit}',
            'prob': do_x2, 'categoria': 'Doble Op.',
            'ev': None, 'cuota': None,
            'tipo': 'doble', 'emoji': '🛡️',
            'razon': f'Cubre empate + victoria {visit} = {do_x2}%',
        })
    if do_12 >= 80:
        picks.append({
            'mercado': 'Sin empate (1 o 2)',
            'prob': do_12, 'categoria': 'Doble Op.',
            'ev': None, 'cuota': None,
            'tipo': 'doble', 'emoji': '🛡️',
            'razon': f'Cualquier ganador = {do_12}%',
        })

    # ── Goles ──
    xg_total = xgl + xgv
    for linea, label in [(1.5,'1.5'),(2.5,'2.5'),(3.5,'3.5')]:
        prob = round(p_poisson(xg_total, linea)*100)
        if prob >= 60:
            picks.append({
                'mercado': f'Más de {label} goles',
                'prob': prob, 'categoria': 'Goles',
                'ev': None, 'cuota': None,
                'tipo': 'goles', 'emoji': '🥅',
                'razon': f'xG total {round(xg_total,1)} → {prob}% de superar {label}',
            })

    # Under goles (si xG total es bajo)
    if xg_total < 2.0:
        prob_u25 = round((1 - p_poisson(xg_total, 2.5))*100) + round(p_poisson(xg_total, 2.5)*100)
        prob_u15 = round((1-p_poisson(xg_total,1.5))*100)
        if prob_u15 >= 55:
            picks.append({
                'mercado': 'Menos de 1.5 goles',
                'prob': prob_u15, 'categoria': 'Goles',
                'ev': None, 'cuota': None,
                'tipo': 'goles', 'emoji': '🔒',
                'razon': f'xG total bajo ({round(xg_total,1)}) → partido cerrado',
            })

    # ── Mercados razonados por equipo ──
    stats = cargar_stats()
    mercados_r = razonar_partido(local, visit, lam_tiros, lam_cor, lam_faltas)
    for m in mercados_r:
        if m['prob'] >= 60:
            tipo_badge = '👤 Equipo' if m['tipo']=='equipo' else '🏟️ Total'
            picks.append({
                'mercado'  : m['mercado'],
                'prob'     : m['prob'],
                'categoria': f"{'Tiros' if 'tiro' in m['mercado'].lower() else 'Córners' if 'órner' in m['mercado'].lower() else 'Faltas'}",
                'ev'       : None, 'cuota': None,
                'tipo'     : m['tipo'],
                'emoji'    : m['emoji'],
                'razon'    : f"{tipo_badge} — {m['razon']}",
                'detalle'  : m.get('detalle',''),
            })

    # ── Tarjetas ──
    for linea, label in [(3.5,'3.5'),(4.5,'4.5')]:
        prob = round(p_poisson(lam_tar, linea)*100)
        if prob >= 60:
            picks.append({
                'mercado': f'Tarjetas más de {label}',
                'prob': prob, 'categoria': 'Tarjetas',
                'ev': None, 'cuota': None,
                'tipo': 'tarjeta', 'emoji': '🟨',
                'razon': f'{round(lam_tar,1)} tarjetas esperadas',
            })

    # EV especial de Pinnacle
    if ev_row is not None:
        for res, campo_ev, campo_c, nombre in [
            ('1','EV_1','Cuota_Pinnacle_1',f'Victoria {local}'),
            ('X','EV_X','Cuota_Pinnacle_X','Empate'),
            ('2','EV_2','Cuota_Pinnacle_2',f'Victoria {visit}'),
        ]:
            ev_val = ev_row.get(campo_ev)
            cuota  = ev_row.get(campo_c, 0)
            if ev_val and cuota and float(cuota) > 1 and float(ev_val) > 0.10:
                prob_imp = round(100/float(cuota), 1)
                picks.append({
                    'mercado'  : f'🔥 VALUE: {nombre}',
                    'prob'     : round({'1':p1,'X':px,'2':p2}[res], 1),
                    'categoria': 'Value Bet',
                    'ev'       : round(float(ev_val), 3),
                    'cuota'    : round(float(cuota), 2),
                    'tipo'     : 'value',
                    'emoji'    : '💰',
                    'razon'    : f'Modelo {round({"1":p1,"X":px,"2":p2}[res],1)}% vs Pinnacle {prob_imp}% (cuota {round(float(cuota),2)})',
                })

    # Ordenar por probabilidad descendente, eliminar duplicados
    picks_uniq = []
    mercados_vistos = set()
    for pk in sorted(picks, key=lambda x: x['prob'], reverse=True):
        key = pk['mercado'].lower()[:30]
        if key not in mercados_vistos:
            mercados_vistos.add(key)
            picks_uniq.append(pk)

    return picks_uniq

def construir_datos_dia():
    """Construye picks para los partidos de hoy."""
    if not os.path.exists(CSV_PRED):
        return []

    df_pred = pd.read_csv(CSV_PRED)
    df_ev   = pd.read_csv(CSV_EV) if os.path.exists(CSV_EV) else pd.DataFrame()

    hoy     = date.today().strftime('%Y-%m-%d')
    hoy_df  = df_pred[df_pred['Fecha'] == hoy]

    partidos_picks = []
    for _, r in hoy_df.iterrows():
        local = r['Local']
        visit = r['Visitante']

        # Buscar EV
        ev_row = None
        if len(df_ev) > 0:
            ev_match = df_ev[(df_ev['Local']==local) & (df_ev['Visitante']==visit)]
            if len(ev_match) > 0:
                ev_row = ev_match.iloc[0].to_dict()

        picks = generar_picks_partido(r, ev_row)

        vm_l = int(r.get('VM_Local', 0))
        vm_v = int(r.get('VM_Visitante', 0))

        partidos_picks.append({
            'local'   : local,
            'visitante': visit,
            'grupo'   : r.get('Grupo',''),
            'marcador': r.get('Marcador_Predicho',''),
            'p1': round(float(r['Prob_1_Final']),1),
            'px': round(float(r['Prob_X_Final']),1),
            'p2': round(float(r['Prob_2_Final']),1),
            'vml': vm_l, 'vmv': vm_v,
            'picks': picks,
            'n_picks': len(picks),
            'mejor_prob': picks[0]['prob'] if picks else 0,
        })

    # Ordenar por mejor probabilidad disponible
    partidos_picks.sort(key=lambda x: x['mejor_prob'], reverse=True)
    return partidos_picks, hoy

def main():
    partidos_data, hoy = construir_datos_dia()

    if not partidos_data:
        print("❌ No hay partidos para hoy")
        return

    # Contar picks totales
    total_picks = sum(p['n_picks'] for p in partidos_data)
    print(f"✅ {len(partidos_data)} partidos | {total_picks} picks generados")

    for p in partidos_data:
        print(f"\n⚽ {p['local']} vs {p['visitante']} — {p['n_picks']} picks")
        for pk in p['picks'][:5]:
            emoji, nivel, _ = nivel_confianza(pk['prob'])
            ev_str = f" | EV: {pk['ev']:+.3f}" if pk.get('ev') else ""
            cuota_str = f" @ {pk['cuota']}" if pk.get('cuota') else ""
            print(f"   {emoji} {pk['mercado']}{cuota_str}: {pk['prob']}% — {nivel}{ev_str}")

    # Generar HTML
    ISO_JSON    = json.dumps(BANDERAS_ISO, ensure_ascii=False)
    PICKS_JSON  = json.dumps(partidos_data, ensure_ascii=False)
    FECHA_GEN   = datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Picks del Día — Mundial 2026</title>
<style>
:root{{--bg:#0d1220;--panel:#161d31;--panel2:#1c2540;--tx:#eef1f8;--tx2:#9aa5c0;
--lin:#2a3554;--v:#34d399;--e:#fbbf24;--d:#fb7185;--ac:#60a5fa;--pu:#a78bfa;
--or:#fb923c;--ro:#f43f5e;--go:#ffd700}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,sans-serif;padding-bottom:48px}}
.wrap{{max-width:900px;margin:0 auto;padding:0 16px}}
nav{{background:rgba(13,18,32,.95);border-bottom:1px solid var(--lin);padding:12px 16px;
position:sticky;top:0;z-index:50;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-weight:700;color:var(--ac);font-size:1rem}}
.nav-links a{{color:var(--tx2);text-decoration:none;font-size:.83rem;font-weight:600;margin-left:16px}}
header{{text-align:center;padding:28px 0 16px}}
header h1{{font-size:1.5rem;font-weight:700}}
header p{{color:var(--tx2);font-size:.85rem;margin-top:6px}}
.badge{{display:inline-block;border:1px solid var(--lin);border-radius:999px;
padding:2px 12px;font-size:.76rem;color:var(--tx2);margin:4px 2px}}
.badge.hoy{{border-color:var(--ac);color:var(--ac)}}
.partido-wrap{{margin-bottom:20px}}
.partido-header{{background:var(--panel);border:1px solid var(--lin);border-radius:14px 14px 0 0;
padding:14px 16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}
.partido-equipos{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1rem}}
.marcador-badge{{background:var(--panel2);border:1px solid var(--lin);border-radius:8px;
padding:2px 10px;font-size:.95rem}}
.partido-probs{{font-size:.78rem;color:var(--tx2);display:flex;gap:10px}}
.barra{{display:flex;height:6px;border-radius:3px;overflow:hidden;background:var(--panel2);margin:4px 0}}
.barra i{{display:block;height:100%}}
.picks-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px;
background:var(--panel2);border:1px solid var(--lin);border-top:none;
border-radius:0 0 14px 14px;padding:12px}}
.pick-card{{background:var(--panel);border:1px solid var(--lin);border-radius:10px;padding:10px 12px;
position:relative;overflow:hidden}}
.pick-card.muy-alta{{border-color:var(--v)}}
.pick-card.alta{{border-color:var(--v)}}
.pick-card.media{{border-color:var(--e)}}
.pick-card.leve{{border-color:var(--or)}}
.pick-card.value{{border-color:var(--go);background:rgba(255,215,0,0.05)}}
.pick-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:6px;margin-bottom:4px}}
.pick-mercado{{font-size:.84rem;font-weight:600;line-height:1.3;flex:1}}
.pick-prob{{font-size:1.2rem;font-weight:700;flex-shrink:0;white-space:nowrap}}
.muy-alta .pick-prob,.alta .pick-prob{{color:var(--v)}}
.media .pick-prob{{color:var(--e)}}
.leve .pick-prob{{color:var(--or)}}
.value .pick-prob{{color:var(--go)}}
.pick-meta{{display:flex;justify-content:space-between;align-items:center;margin-top:4px;flex-wrap:wrap;gap:4px}}
.pick-cat{{font-size:.7rem;background:var(--panel2);border-radius:4px;padding:1px 6px;color:var(--tx2)}}
.pick-nivel{{font-size:.7rem;color:var(--tx2)}}
.pick-razon{{font-size:.72rem;color:var(--tx2);margin-top:4px;line-height:1.4}}
.pick-ev{{font-size:.75rem;font-weight:600;color:var(--go);margin-top:2px}}
.pick-cuota{{font-size:.75rem;color:var(--tx2)}}
.fl{{width:20px;height:15px;border-radius:2px;vertical-align:-2px;object-fit:cover}}
.resumen-box{{background:var(--panel);border:1px solid var(--lin);border-radius:12px;
padding:16px;margin-bottom:20px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;text-align:center}}
.res-stat .val{{font-size:1.4rem;font-weight:700;color:var(--ac)}}
.res-stat .lbl{{font-size:.74rem;color:var(--tx2)}}
.sin-picks{{text-align:center;color:var(--tx2);padding:20px;font-size:.85rem}}
.vd{{color:var(--v)}}.em{{color:var(--e)}}.dr{{color:var(--d)}}
footer{{text-align:center;color:var(--tx2);font-size:.76rem;margin-top:24px}}
footer a{{color:var(--ac);text-decoration:none}}
@media(max-width:560px){{.picks-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<nav>
  <span class="logo">⚽ Sportpicks — Mundial 2026</span>
  <div class="nav-links">
    <a href="index_final.html">🔮 Modelo</a>
    <a href="picks_publicos_v2.html">🎯 Picks</a>
  </div>
</nav>
<div class="wrap">
  <header>
    <h1>🎯 Picks del Día — {hoy}</h1>
    <p>Todos los mercados ordenados por probabilidad de acierto</p>
    <span class="badge hoy">📅 {FECHA_GEN}</span>
    <span class="badge">🤖 XGBoost + 25 casas + Razonamiento por equipo</span>
  </header>

  <div class="resumen-box" id="resumen"></div>
  <div id="partidos"></div>

  <footer>
    <a href="index_final.html">Ver modelo completo</a> ·
    <a href="picks_publicos_v2.html">Historial de picks</a> ·
    ⚠️ Apuesta con responsabilidad
  </footer>
</div>

<script>
const PARTIDOS = {PICKS_JSON};
const ISO      = {ISO_JSON};
const fl = eq => ISO[eq]?`<img class="fl" loading="lazy" alt="" src="https://flagcdn.com/w20/${{ISO[eq]}}.png">`:'';

// Resumen
const totalPicks  = PARTIDOS.reduce((s,p)=>s+p.picks.length,0);
const mejorProb   = Math.max(...PARTIDOS.map(p=>p.mejor_prob));
const nValueBets  = PARTIDOS.reduce((s,p)=>s+p.picks.filter(pk=>pk.tipo==='value').length,0);
document.getElementById('resumen').innerHTML = `
  <div class="res-stat"><div class="val">${{PARTIDOS.length}}</div><div class="lbl">Partidos hoy</div></div>
  <div class="res-stat"><div class="val">${{totalPicks}}</div><div class="lbl">Picks totales</div></div>
  <div class="res-stat"><div class="val" style="color:var(--go)">${{nValueBets}}</div><div class="lbl">Value Bets 💰</div></div>
`;

// Partidos
const cont = document.getElementById('partidos');
PARTIDOS.forEach(p => {{
  const div = document.createElement('div');
  div.className = 'partido-wrap';

  const vmMax = Math.max(p.vml, p.vmv, 1);
  div.innerHTML = `
    <div class="partido-header">
      <div>
        <div class="partido-equipos">
          ${{fl(p.local)}} ${{p.local}}
          <span class="marcador-badge">${{p.marcador}}</span>
          ${{p.visitante}} ${{fl(p.visitante)}}
        </div>
        <div class="barra" style="margin-top:6px;width:200px">
          <i style="width:${{p.p1}}%;background:var(--v)"></i>
          <i style="width:${{p.px}}%;background:var(--e)"></i>
          <i style="width:${{p.p2}}%;background:var(--d)"></i>
        </div>
      </div>
      <div class="partido-probs">
        <span class="vd">1·${{p.p1}}%</span>
        <span class="em">X·${{p.px}}%</span>
        <span class="dr">2·${{p.p2}}%</span>
        <span style="color:var(--tx2);font-size:.7rem">Grupo ${{p.grupo}}</span>
      </div>
    </div>
    <div class="picks-grid">
      ${{p.picks.length === 0
        ? '<div class="sin-picks">Sin picks disponibles con suficiente confianza</div>'
        : p.picks.map(pk => {{
          const nivel = pk.prob>=85?'muy-alta':pk.prob>=75?'alta':pk.prob>=65?'media':pk.prob>=55?'leve':'baja';
          const claseCard = pk.tipo==='value'?'value':nivel;
          const emoji_nivel = pk.prob>=75?'🟢':pk.prob>=65?'🟡':'🟠';
          const evHTML = pk.ev ? `<div class="pick-ev">💰 EV: ${{pk.ev>0?'+':''}}${{(pk.ev*100).toFixed(1)}}%</div>` : '';
          const cuotaHTML = pk.cuota ? `<div class="pick-cuota">Cuota: ${{pk.cuota}}</div>` : '';
          const razonHTML = pk.razon ? `<div class="pick-razon">💡 ${{pk.razon}}</div>` : '';
          return `<div class="pick-card ${{claseCard}}">
            <div class="pick-header">
              <div class="pick-mercado">${{pk.emoji}} ${{pk.mercado}}</div>
              <div class="pick-prob">${{pk.prob}}%</div>
            </div>
            <div class="pick-meta">
              <span class="pick-cat">${{pk.categoria}}</span>
              <span class="pick-nivel">${{emoji_nivel}} ${{pk.prob>=85?'Muy Alta':pk.prob>=75?'Alta':pk.prob>=65?'Media':'Leve'}}</span>
            </div>
            ${{evHTML}}${{cuotaHTML}}${{razonHTML}}
          </div>`;
        }}).join('')
      }}
    </div>`;
  cont.appendChild(div);
}});
</script>
</body>
</html>"""

    os.makedirs('docs', exist_ok=True)
    with open('docs/picks_dia.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n✅ Panel generado: docs/picks_dia.html")

if __name__ == '__main__':
    main()
