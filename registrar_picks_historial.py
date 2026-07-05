# -*- coding: utf-8 -*-
"""
registrar_picks_historial.py
Registra los picks del día en historial JSON y genera picks_publicos_v2.html

Flujo:
  1. Lee picks_dia.html y picks_premium.html del día (generados por generador_picks_inteligente.py)
  2. Los registra en Data/historial_picks.json con estado "Pendiente"
  3. Si existen resultados reales en Data/resultados_mundial.csv, audita automáticamente
  4. Genera picks_publicos_v2.html con historial completo + bankroll

Uso:
  python registrar_picks_historial.py           # registra picks de hoy
  python registrar_picks_historial.py --audit   # audita + actualiza resultados
"""

import os, sys, json, re, argparse
from datetime import date, datetime, timezone, timedelta

# Hora Perú UTC-5
PERU_TZ = timezone(timedelta(hours=-5))
def hoy_peru(): return datetime.now(PERU_TZ).strftime('%Y-%m-%d')
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

HISTORIAL_JSON = os.path.join(RAIZ, 'Data', 'historial_picks.json')
RESULTADOS_CSV = os.path.join(RAIZ, 'Data', 'resultados_mundial.csv')
PICKS_DIA_HTML = os.path.join(RAIZ, 'docs', 'picks_dia.html')
PICKS_PREM_HTML = os.path.join(RAIZ, 'docs', 'picks_premium.html')
OUTPUT_HTML    = os.path.join(RAIZ, 'docs', 'picks_publicos_v2.html')

BANKROLL_INICIAL = 100.0
STAKE_PUBLICO    = 2.0   # unidades por pick público
STAKE_PREMIUM    = 1.0   # unidades por pata de combinada premium


# ══════════════════════════════════════════════════════════════════════════════
# CARGA / GUARDADO HISTORIAL
# ══════════════════════════════════════════════════════════════════════════════

def cargar_historial():
    if os.path.exists(HISTORIAL_JSON):
        with open(HISTORIAL_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'bankroll': BANKROLL_INICIAL, 'dias': []}

def guardar_historial(h):
    os.makedirs(os.path.dirname(HISTORIAL_JSON), exist_ok=True)
    with open(HISTORIAL_JSON, 'w', encoding='utf-8') as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE PICKS DESDE HTML
# ══════════════════════════════════════════════════════════════════════════════

def extraer_picks_de_html(path):
    """Extrae el JSON de picks embebido en el HTML generado."""
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Buscar const PICKS=[...];
    m = re.search(r'const PICKS=(\[.*?\]);', content, re.DOTALL)
    if not m:
        return []
    try:
        picks = json.loads(m.group(1))
        return picks
    except:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE PICKS DEL DÍA
# ══════════════════════════════════════════════════════════════════════════════

def registrar_dia(historial, hoy_str):
    """Registra los picks de hoy en el historial si no están ya."""
    # Verificar si el día ya existe
    dias_existentes = [d['fecha'] for d in historial['dias']]
    if hoy_str in dias_existentes:
        dia_existente = next(d for d in historial['dias'] if d['fecha'] == hoy_str)
        publicos_existentes = len([p for p in dia_existente['picks'] if 'Público' in p.get('tipo','')])
        # Si no hay públicos registrados, permitir re-registro (picks nuevos disponibles)
        if publicos_existentes > 0:
            print(f"   ℹ️  Día {hoy_str} ya registrado ({len(dia_existente['picks'])} picks).")
            return historial
        else:
            print(f"   🔄 Re-registrando {hoy_str} — faltan picks públicos...")
            historial['dias'] = [d for d in historial['dias'] if d['fecha'] != hoy_str]

    picks_pub  = extraer_picks_de_html(PICKS_DIA_HTML)
    picks_prem = extraer_picks_de_html(PICKS_PREM_HTML)

    picks_del_dia = []

    # Picks públicos individuales
    for i, pk in enumerate(picks_pub):
        if pk.get('tipo') == 'combinada':
            # Combinada pública → registrar como una entrada
            picks_del_dia.append({
                'id': f"{hoy_str}_pub_combo_{i}",
                'tipo': 'Público Combinada',
                'partido': pk.get('local', ''),
                'mercado': pk.get('mercado', ''),
                'cuota': pk.get('cuota_display', pk.get('cuota', 1)),
                'prob': pk.get('prob', 0),
                'stake': STAKE_PUBLICO,
                'estado': 'Pendiente',
                'ganancia': 0,
                'picks_combo': pk.get('picks_combo', []),
            })
        else:
            picks_del_dia.append({
                'id': f"{hoy_str}_pub_{i}",
                'tipo': 'Público',
                'partido': pk.get('partido', ''),
                'mercado': pk.get('mercado', ''),
                'cuota': pk.get('cuota_display', pk.get('cuota', 1)),
                'prob': pk.get('prob', 0),
                'stake': STAKE_PUBLICO,
                'estado': 'Pendiente',
                'ganancia': 0,
                'emoji': pk.get('emoji', '🎯'),
                'categoria': pk.get('categoria', ''),
                'descripcion': pk.get('descripcion', ''),
            })

    # Picks premium
    for i, pk in enumerate(picks_prem):
        picks_del_dia.append({
            'id': f"{hoy_str}_prem_{i}",
            'tipo': 'Premium',
            'partido': pk.get('local', pk.get('partido', '')),
            'mercado': pk.get('mercado', ''),
            'cuota': pk.get('cuota_display', pk.get('cuota', 1)),
            'prob': pk.get('prob', 0),
            'stake': STAKE_PREMIUM,
            'estado': 'Pendiente',
            'ganancia': 0,
            'emoji': pk.get('emoji', '💎'),
            'categoria': pk.get('categoria', ''),
            'descripcion': pk.get('descripcion', ''),
            'picks_combo': pk.get('picks_combo', []),
        })

    historial['dias'].append({
        'fecha': hoy_str,
        'picks': picks_del_dia,
        'auditado': False,
        'resumen': None,
    })

    print(f"   ✅ {len(picks_del_dia)} picks registrados para {hoy_str}")
    print(f"      {len([p for p in picks_del_dia if 'Público' in p['tipo']])} públicos + "
          f"{len([p for p in picks_del_dia if p['tipo']=='Premium'])} premium")
    return historial


# ══════════════════════════════════════════════════════════════════════════════
# AUDITORÍA AUTOMÁTICA
# ══════════════════════════════════════════════════════════════════════════════

# Mapa de normalización de nombres — variantes entre CSV y picks
_NORM_NOMBRES = {
    'curaçao': 'curazao', 'cape verde islands': 'cabo verde',
    'congo dr': 'rd congo', 'dr congo': 'rd congo',
    'república checa': 'república checa', 'czechia': 'república checa',
    'ee. uu.': 'ee. uu.', 'united states': 'ee. uu.',
    'corea del sur': 'corea del sur', 'south korea': 'corea del sur',
}

def _normalizar(nombre):
    n = nombre.lower().strip()
    return _NORM_NOMBRES.get(n, n)


def evaluar_pick(pick, resultados_df):
    """
    Evalúa si un pick ganó o perdió según resultados reales.
    Retorna: 'Ganado', 'Perdido', 'Pendiente'
    """
    mercado = pick.get('mercado', '').lower()
    partido = pick.get('partido', '').lower()

    # Buscar resultado del partido — con normalización de nombres
    fila = None
    for _, row in resultados_df.iterrows():
        local_csv  = _normalizar(str(row.get('Local', '')))
        visit_csv  = _normalizar(str(row.get('Visitante', '')))
        # Verificar si alguno de los equipos del CSV aparece en el pick
        if local_csv in partido or visit_csv in partido:
            fila = row
            break
        # También verificar al revés — palabras del pick en el CSV
        palabras_partido = partido.replace(' vs ', ' ').split()
        if any(p in local_csv or p in visit_csv for p in palabras_partido if len(p) > 3):
            fila = row
            break

    if fila is None:
        return 'Pendiente'

    # Columnas reales del CSV: Goles_Local / Goles_Visitante
    gl = fila.get('Goles_Local', fila.get('Goles_L', -1))
    gv = fila.get('Goles_Visitante', fila.get('Goles_V', -1))
    try:
        goles_l = int(float(gl))
        goles_v = int(float(gv))
    except:
        return 'Pendiente'

    if goles_l < 0 or goles_v < 0:
        return 'Pendiente'

    # Verificar que el partido ya terminó
    estado = str(fila.get('Estado', fila.get('estado', 'FINISHED'))).upper()
    if estado not in ('FINISHED', 'FT', 'FULL_TIME', 'AWARDED'):
        return 'Pendiente'

    total_goles = goles_l + goles_v
    resultado = 'local' if goles_l > goles_v else ('visita' if goles_v > goles_l else 'empate')

    # 1X2
    if 'victoria' in mercado:
        equipo = mercado.replace('victoria', '').strip()
        local_name = fila.get('Local', '').lower()
        visit_name = fila.get('Visitante', '').lower()
        if equipo in local_name and resultado == 'local': return 'Ganado'
        if equipo in visit_name and resultado == 'visita': return 'Ganado'
        return 'Perdido'

    # Empate
    if mercado.strip() == 'empate':
        return 'Ganado' if resultado == 'empate' else 'Perdido'

    # Goles over/under
    if 'más de 1.5' in mercado or 'over 1.5' in mercado:
        return 'Ganado' if total_goles > 1 else 'Perdido'
    if 'más de 2.5' in mercado or 'over 2.5' in mercado:
        return 'Ganado' if total_goles > 2 else 'Perdido'
    if 'más de 3.5' in mercado:
        return 'Ganado' if total_goles > 3 else 'Perdido'
    if 'menos de 2.5' in mercado or 'under 2.5' in mercado:
        return 'Ganado' if total_goles < 3 else 'Perdido'
    if 'menos de 1.5' in mercado:
        return 'Ganado' if total_goles < 2 else 'Perdido'

    # Doble oportunidad
    if '1x' in mercado or '1 o empate' in mercado:
        return 'Ganado' if resultado in ('local', 'empate') else 'Perdido'
    if 'x2' in mercado or 'empate o' in mercado:
        return 'Ganado' if resultado in ('visita', 'empate') else 'Perdido'
    if 'sin empate' in mercado or '1 o 2' in mercado:
        return 'Ganado' if resultado != 'empate' else 'Perdido'

    # Faltas, tiros, córners — comparar con stats si disponibles
    for stat_key, col in [('faltas', 'Faltas_Total'), ('tiros', 'Tiros_Total'), ('córners', 'Corners_Total')]:
        if stat_key in mercado:
            m_linea = re.search(r'\+(\d+\.?\d*)', mercado)
            if m_linea and col in fila and pd.notna(fila[col]):
                linea = float(m_linea.group(1))
                valor = float(fila[col])
                return 'Ganado' if valor > linea else 'Perdido'

    # HC
    if 'hc' in mercado:
        m_hc = re.search(r'([+-]?\d+\.?\d*)\s*$', mercado)
        if m_hc:
            handicap = float(m_hc.group(1))
            # Determinar si es local o visitante
            local_name = fila.get('Local', '').lower()
            if local_name in mercado:
                diff = goles_l - goles_v + handicap
            else:
                diff = goles_v - goles_l + handicap
            if diff > 0: return 'Ganado'
            if diff < 0: return 'Perdido'
            return 'Pendiente'  # push

    return 'Pendiente'


def auditar_dia(historial, fecha_str):
    """Audita los picks de un día con resultados reales."""
    if not os.path.exists(RESULTADOS_CSV):
        print("   ⚠️ No se encontró resultados_mundial.csv — auditoría no posible")
        return historial

    resultados_df = pd.read_csv(RESULTADOS_CSV)
    # Usar todos los resultados — partidos de un día pueden estar en fecha siguiente en UTC
    resultados_hoy = resultados_df

    dia = next((d for d in historial['dias'] if d['fecha'] == fecha_str), None)
    if not dia:
        print(f"   ⚠️ No hay picks registrados para {fecha_str}")
        return historial

    ganados = perdidos = pendientes = 0
    unidades = 0.0

    for pick in dia['picks']:
        if pick.get('tipo') == 'Premium' and pick.get('picks_combo'):
            # Combinada: todas las patas deben ganar
            estados_patas = []
            for pata in pick['picks_combo']:
                pata_pick = {**pick, 'mercado': pata.get('mercado',''), 'partido': pata.get('partido','')}
                estados_patas.append(evaluar_pick(pata_pick, resultados_hoy))

            if all(e == 'Ganado' for e in estados_patas):
                pick['estado'] = 'Ganado'
                pick['ganancia'] = round(pick['stake'] * (pick['cuota'] - 1), 2)
            elif any(e == 'Perdido' for e in estados_patas):
                pick['estado'] = 'Perdido'
                pick['ganancia'] = -pick['stake']
            else:
                pick['estado'] = 'Pendiente'
        else:
            pick['estado'] = evaluar_pick(pick, resultados_hoy)
            if pick['estado'] == 'Ganado':
                pick['ganancia'] = round(pick['stake'] * (pick['cuota'] - 1), 2)
            elif pick['estado'] == 'Perdido':
                pick['ganancia'] = -pick['stake']

        if pick['estado'] == 'Ganado': ganados += 1; unidades += pick['ganancia']
        elif pick['estado'] == 'Perdido': perdidos += 1; unidades += pick['ganancia']
        else: pendientes += 1

    total_picks = ganados + perdidos
    pct = round(ganados / total_picks * 100, 1) if total_picks > 0 else 0

    dia['auditado'] = pendientes == 0
    dia['resumen'] = {
        'ganados': ganados, 'perdidos': perdidos, 'pendientes': pendientes,
        'porcentaje': pct, 'unidades': round(unidades, 2),
    }

    historial['bankroll'] = round(historial['bankroll'] + unidades, 2)

    print(f"   ✅ Auditoría {fecha_str}: {ganados}G/{perdidos}P/{pendientes}? | "
          f"{pct}% | {unidades:+.2f}u | Bankroll: {historial['bankroll']:.2f}u")
    return historial


# ══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN HTML
# ══════════════════════════════════════════════════════════════════════════════

def generar_html(historial):
    hoy = hoy_peru()  # Hora Perú UTC-5
    ts = int(__import__('time').time())

    # Calcular estadísticas globales
    todos_picks = [p for d in historial['dias'] for p in d['picks'] if p['estado'] != 'Pendiente']
    total_g = sum(1 for p in todos_picks if p['estado'] == 'Ganado')
    total_p = sum(1 for p in todos_picks if p['estado'] == 'Perdido')
    total_u = sum(p['ganancia'] for p in todos_picks)
    pct_global = round(total_g / (total_g + total_p) * 100, 1) if (total_g + total_p) > 0 else 0
    bankroll = historial['bankroll']
    roi = round((bankroll - BANKROLL_INICIAL) / BANKROLL_INICIAL * 100, 1)

    # Datos para gráfica de evolución
    evolucion = [BANKROLL_INICIAL]
    labels_graf = ['Inicio']
    bk_acum = BANKROLL_INICIAL
    for d in sorted(historial['dias'], key=lambda x: x['fecha']):
        if d.get('resumen'):
            bk_acum = round(bk_acum + d['resumen']['unidades'], 2)
            evolucion.append(bk_acum)
            labels_graf.append(d['fecha'][5:])  # MM-DD

    evolucion_j = json.dumps(evolucion)
    labels_j    = json.dumps(labels_graf)
    historial_j = json.dumps(historial, ensure_ascii=False, default=str)

    return f"""<!DOCTYPE html>
<html lang="es">
<!-- ts:{ts} -->
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Historial & Bankroll — Sportpicks Mundial 2026</title>
<style>
:root{{--bg:#0d1220;--panel:#161d31;--panel2:#1c2540;--tx:#eef1f8;--tx2:#9aa5c0;
--lin:#2a3554;--v:#34d399;--e:#fbbf24;--d:#fb7185;--ac:#60a5fa;--pu:#a78bfa;--or:#fb923c;--go:#ffd700}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--tx);font:15px/1.6 system-ui,sans-serif;padding-bottom:60px}}
.wrap{{max-width:900px;margin:0 auto;padding:0 16px}}
nav{{background:rgba(13,18,32,.95);border-bottom:1px solid var(--lin);padding:12px 16px;
position:sticky;top:0;z-index:50;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-weight:700;color:var(--ac);font-size:.95rem}}
.nav-links a{{color:var(--tx2);text-decoration:none;font-size:.82rem;margin-left:14px;font-weight:600}}
header{{text-align:center;padding:28px 0 16px}}
header h1{{font-size:1.45rem;font-weight:700}}
header p{{color:var(--tx2);font-size:.84rem;margin-top:5px}}
.stats-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:20px 0}}
@media(min-width:560px){{.stats-grid{{grid-template-columns:repeat(4,1fr)}}}}
.stat{{background:var(--panel);border:1px solid var(--lin);border-radius:12px;padding:14px;text-align:center}}
.stat .val{{font-size:1.4rem;font-weight:700}}
.stat .lbl{{font-size:.73rem;color:var(--tx2);margin-top:3px}}
.green{{color:var(--v)}}.red{{color:var(--d)}}.yellow{{color:var(--e)}}.blue{{color:var(--ac)}}.gold{{color:var(--go)}}
.chart-box{{background:var(--panel);border:1px solid var(--lin);border-radius:12px;padding:16px;margin-bottom:24px}}
.chart-title{{font-size:.85rem;color:var(--tx2);margin-bottom:12px;font-weight:600}}
canvas{{width:100%!important}}
.section-title{{font-size:.85rem;font-weight:600;color:var(--tx2);letter-spacing:.05em;
margin:24px 0 12px;padding-bottom:6px;border-bottom:.5px solid var(--lin)}}
.dia-card{{background:var(--panel);border:1px solid var(--lin);border-radius:14px;
margin-bottom:16px;overflow:hidden}}
.dia-header{{display:flex;justify-content:space-between;align-items:center;
padding:12px 16px;cursor:pointer;user-select:none}}
.dia-fecha{{font-weight:600;font-size:.95rem}}
.dia-badges{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.badge{{font-size:.72rem;font-weight:600;padding:3px 9px;border-radius:999px}}
.b-g{{background:rgba(52,211,153,.15);color:var(--v)}}
.b-p{{background:rgba(251,113,133,.15);color:var(--d)}}
.b-e{{background:rgba(251,191,36,.15);color:var(--e)}}
.b-u{{background:rgba(96,165,250,.12);color:var(--ac)}}
.dia-resumen{{font-size:.8rem;color:var(--tx2);padding:0 16px 10px}}
.dia-picks{{padding:0 12px 12px;display:none}}
.dia-picks.open{{display:block}}
.pick-row{{background:var(--panel2);border-radius:10px;padding:10px 12px;margin-bottom:7px;
border-left:3px solid var(--lin)}}
.pick-row.ganado{{border-left-color:var(--v)}}
.pick-row.perdido{{border-left-color:var(--d)}}
.pick-row.pendiente{{border-left-color:var(--e)}}
.pick-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}}
.pick-info{{flex:1}}
.pick-tipo{{font-size:.7rem;color:var(--tx2);margin-bottom:2px;font-weight:600;letter-spacing:.04em}}
.pick-mercado{{font-size:.88rem;font-weight:600;color:var(--tx)}}
.pick-partido{{font-size:.78rem;color:var(--tx2);margin-top:2px}}
.pick-right{{text-align:right;flex-shrink:0}}
.pick-cuota{{font-size:.82rem;color:var(--go);font-weight:600}}
.pick-stake{{font-size:.72rem;color:var(--tx2)}}
.pick-ganancia{{font-size:.82rem;font-weight:600;margin-top:2px}}
.pick-estado{{font-size:.72rem;font-weight:700;padding:2px 8px;border-radius:5px;display:inline-block;margin-top:4px}}
.e-g{{background:rgba(52,211,153,.15);color:var(--v)}}
.e-p{{background:rgba(251,113,133,.15);color:var(--d)}}
.e-pen{{background:rgba(251,191,36,.15);color:var(--e)}}
.combo-legs{{margin-top:6px;padding-top:6px;border-top:.5px solid var(--lin)}}
.combo-leg{{font-size:.75rem;color:var(--tx2);padding:2px 0}}
.tg-btn{{display:block;text-align:center;background:var(--ac);color:#0d1220;border-radius:10px;
padding:11px;font-weight:700;text-decoration:none;margin:14px 0;font-size:.88rem}}
.empty{{text-align:center;color:var(--tx2);font-size:.85rem;padding:32px;}}
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
    <a href="picks_dia.html">🎯 Picks hoy</a>
    <a href="picks_premium.html">💎 Premium</a>
  </div>
</nav>
<div class="wrap">
  <header>
    <h1>📊 Historial & Bankroll</h1>
    <p>Transparencia total — todos los picks públicos y premium con resultado real</p>
  </header>
  <a class="tg-btn" href="https://t.me/TU_CANAL" target="_blank">📱 Unirte al canal de Telegram</a>

  <div class="stats-grid">
    <div class="stat"><div class="val green">{total_g}</div><div class="lbl">Picks ganados</div></div>
    <div class="stat"><div class="val red">{total_p}</div><div class="lbl">Picks perdidos</div></div>
    <div class="stat"><div class="val yellow">{pct_global}%</div><div class="lbl">Precisión global</div></div>
    <div class="stat"><div class="val {'green' if roi >= 0 else 'red'}">{roi:+.1f}%</div><div class="lbl">ROI total</div></div>
    <div class="stat"><div class="val blue">{bankroll:.1f}u</div><div class="lbl">Bankroll actual</div></div>
    <div class="stat"><div class="val {'green' if total_u >= 0 else 'red'}">{total_u:+.2f}u</div><div class="lbl">Unidades netas</div></div>
    <div class="stat"><div class="val gold">{len(historial['dias'])}</div><div class="lbl">Días registrados</div></div>
    <div class="stat"><div class="val">{total_g+total_p}</div><div class="lbl">Picks evaluados</div></div>
  </div>

  <div class="chart-box">
    <div class="chart-title">📈 Evolución del bankroll</div>
    <canvas id="grafica" height="180"></canvas>
  </div>

  <div class="section-title">HISTORIAL POR DÍA</div>
  <div id="historial-container"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const HIST = {historial_j};
const EVOLUCION = {evolucion_j};
const LABELS = {labels_j};

// ── Gráfica ──
const ctx = document.getElementById('grafica').getContext('2d');
new Chart(ctx, {{
  type: 'line',
  data: {{
    labels: LABELS,
    datasets: [{{
      label: 'Bankroll',
      data: EVOLUCION,
      borderColor: '#60a5fa',
      backgroundColor: 'rgba(96,165,250,0.08)',
      pointBackgroundColor: EVOLUCION.map((v,i) => i===0?'#60a5fa':v>=EVOLUCION[i-1]?'#34d399':'#fb7185'),
      pointRadius: 5,
      tension: 0.3,
      fill: true,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{
      label: ctx => ctx.parsed.y.toFixed(2) + 'u'
    }} }} }},
    scales: {{
      x: {{ grid: {{ color: '#2a3554' }}, ticks: {{ color: '#9aa5c0', font: {{ size: 11 }} }} }},
      y: {{ grid: {{ color: '#2a3554' }}, ticks: {{ color: '#9aa5c0', font: {{ size: 11 }},
        callback: v => v.toFixed(1) + 'u' }} }}
    }}
  }}
}});

// ── Historial ──
const cont = document.getElementById('historial-container');
const dias = [...HIST.dias].sort((a,b) => b.fecha.localeCompare(a.fecha));

if (!dias.length) {{
  cont.innerHTML = '<div class="empty">No hay picks registrados aún.</div>';
}}

dias.forEach(dia => {{
  const res = dia.resumen || {{}};
  const g = res.ganados || 0, p = res.perdidos || 0, pen = res.pendientes || 0;
  const u = res.unidades || 0;
  const pct = res.porcentaje || 0;

  let badgesHtml = `
    <span class="badge b-g">✅ ${{g}} G</span>
    <span class="badge b-p">❌ ${{p}} P</span>
  `;
  if (pen > 0) badgesHtml += `<span class="badge b-e">⏳ ${{pen}}</span>`;
  if (res.unidades !== undefined)
    badgesHtml += `<span class="badge b-u">${{u >= 0 ? '+' : ''}}${{u.toFixed(2)}}u</span>`;

  const picksHtml = dia.picks.map(pk => {{
    const esC = pk.picks_combo && pk.picks_combo.length > 0;
    const estadoCls = pk.estado === 'Ganado' ? 'ganado' : pk.estado === 'Perdido' ? 'perdido' : 'pendiente';
    const estadoBadge = pk.estado === 'Ganado'
      ? '<span class="pick-estado e-g">✅ GANADO</span>'
      : pk.estado === 'Perdido'
      ? '<span class="pick-estado e-p">❌ PERDIDO</span>'
      : '<span class="pick-estado e-pen">⏳ PENDIENTE</span>';

    const gananciaStr = pk.ganancia !== 0
      ? `<div class="pick-ganancia ${{pk.ganancia > 0 ? 'green' : 'red'}}">${{pk.ganancia > 0 ? '+' : ''}}${{pk.ganancia.toFixed(2)}}u</div>`
      : '';

    let comboLegs = '';
    if (esC && pk.picks_combo) {{
      comboLegs = '<div class="combo-legs">' +
        pk.picks_combo.map(l => `<div class="combo-leg">⚡ ${{l.partido || ''}} · ${{l.mercado || ''}}</div>`).join('') +
        '</div>';
    }}

    const tipoLabel = pk.tipo === 'Premium' ? '💎 PREMIUM' : pk.tipo === 'Público Combinada' ? '🔗 COMBINADA' : '🎯 PÚBLICO';
    const esPremium = pk.tipo === 'Premium';

    // Pick premium: ocultar mercado exacto en el historial público
    const mercadoHTML = esPremium
      ? `<div class="pick-mercado" style="filter:blur(4px);user-select:none;color:var(--pu)">████████████</div>
         <div style="font-size:.72rem;color:var(--pu);margin-top:2px">🔒 Exclusivo suscriptores premium</div>`
      : `<div class="pick-mercado">${{pk.mercado}}</div>`;

    return `<div class="pick-row ${{estadoCls}}">
      <div class="pick-top">
        <div class="pick-info">
          <div class="pick-tipo">${{tipoLabel}}</div>
          ${{mercadoHTML}}
          <div class="pick-partido">${{pk.partido}}</div>
          ${{estadoBadge}}
          ${{esPremium ? '' : comboLegs}}
        </div>
        <div class="pick-right">
          <div class="pick-cuota">@${{pk.cuota}}</div>
          <div class="pick-stake">Stake: ${{pk.stake}}u</div>
          ${{gananciaStr}}
        </div>
      </div>
    </div>`;
  }}).join('');

  const card = document.createElement('div');
  card.className = 'dia-card';
  card.innerHTML = `
    <div class="dia-header" onclick="this.nextElementSibling.nextElementSibling.classList.toggle('open')">
      <div>
        <div class="dia-fecha">📅 ${{dia.fecha}}</div>
        <div class="dia-badges" style="margin-top:4px">${{badgesHtml}}</div>
      </div>
      <span style="color:var(--tx2);font-size:.8rem">${{pct}}% · ${{dia.picks.length}} picks ▾</span>
    </div>
    <div class="dia-resumen">
      ${{dia.auditado ? '✅ Auditado' : '⏳ Pendiente de auditoría'}} ·
      ${{g}} ganados · ${{p}} perdidos · ${{pen}} pendientes
    </div>
    <div class="dia-picks">${{picksHtml}}</div>
  `;
  cont.appendChild(card);
}});
</script>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', action='store_true', help='Auditar picks del día')
    parser.add_argument('--fecha', default=None, help='Fecha a auditar (YYYY-MM-DD)')
    args = parser.parse_args()

    hoy = args.fecha or hoy_peru()  # Hora Perú UTC-5

    print(f"\n📊 REGISTRADOR DE PICKS — {hoy}")
    print("="*50)

    historial = cargar_historial()

    # Registrar picks de hoy
    historial = registrar_dia(historial, hoy)

    # Auditar si se pide o si hay resultados disponibles
    if args.audit:
        print("\n🔍 Auditando picks...")
        historial = auditar_dia(historial, hoy)

    # Guardar historial
    guardar_historial(historial)
    print(f"\n✅ Historial guardado ({len(historial['dias'])} días)")

    # Generar HTML
    os.makedirs('docs', exist_ok=True)
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(generar_html(historial))
    print(f"✅ docs/picks_publicos_v2.html generado")
    print(f"   Bankroll actual: {historial['bankroll']:.2f}u")

if __name__ == '__main__':
    main()