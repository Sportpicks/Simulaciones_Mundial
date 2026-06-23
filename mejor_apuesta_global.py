# Test de la nueva lógica de mejor apuesta global
# Simula los datos de los partidos de hoy para verificar

import math

def p_poisson(lam, linea):
    k = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k))
    except:
        return 0.0

def mejor_apuesta_global(p):
    """
    Busca la mejor apuesta entre TODOS los mercados disponibles:
    - 1X2 (victoria local, empate, visitante)
    - Doble oportunidad (1X, X2, 12)
    - Goles (over/under via xG)
    - Córners (via lam_cor)
    - Tiros a puerta (via tiros)
    - Faltas (via faltas)
    - Tarjetas (via tar)
    - Mercados razonados por equipo
    
    Retorna el mercado con MAYOR probabilidad de acierto.
    """
    local  = p['local']
    visit  = p['visitante']
    p1     = p['p1']
    px     = p['px']
    p2     = p['p2']
    xgl    = p.get('xgl', 0)
    xgv    = p.get('xgv', 0)
    lam_cor   = p.get('cor', 9.0)
    lam_tar   = p.get('tar', 4.0)
    lam_tiros = p.get('tiros', 7.0)
    lam_fal   = p.get('faltas', 22.0)
    xg_total  = xgl + xgv

    candidatos = []

    # ── 1X2 ──
    if p1 > 60:
        candidatos.append({'mercado': f'Victoria {local}', 'prob': p1,
                          'emoji': '⚽', 'categoria': '1X2'})
    if p2 > 60:
        candidatos.append({'mercado': f'Victoria {visit}', 'prob': p2,
                          'emoji': '⚽', 'categoria': '1X2'})
    if px > 40:
        candidatos.append({'mercado': 'Empate', 'prob': px,
                          'emoji': '⚖️', 'categoria': '1X2'})

    # ── Doble oportunidad ──
    do_1x = round(p1+px, 1)
    do_x2 = round(px+p2, 1)
    do_12 = round(p1+p2, 1)
    if do_1x >= 70: candidatos.append({'mercado': f'1X ({local} o empate)',
                                        'prob': do_1x, 'emoji': '🛡️', 'categoria': 'Doble Op.'})
    if do_x2 >= 70: candidatos.append({'mercado': f'X2 (empate o {visit})',
                                        'prob': do_x2, 'emoji': '🛡️', 'categoria': 'Doble Op.'})
    if do_12 >= 75: candidatos.append({'mercado': 'Sin empate (1 o 2)',
                                        'prob': do_12, 'emoji': '🛡️', 'categoria': 'Doble Op.'})

    # ── Goles via xG ──
    for linea, label in [(1.5,'1.5'),(2.5,'2.5'),(3.5,'3.5')]:
        prob = round(p_poisson(xg_total, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Más de {label} goles',
                               'prob': prob, 'emoji': '🥅', 'categoria': 'Goles'})
    # Under
    prob_u15 = round((1-p_poisson(xg_total, 1.5))*100 + p_poisson(xg_total,1.5)*100)
    prob_u15 = round((1 - p_poisson(xg_total, 2.5))*100)  # prob de que haya 0,1,2 goles
    if prob_u15 >= 55:
        candidatos.append({'mercado': 'Menos de 2.5 goles',
                           'prob': prob_u15, 'emoji': '🔒', 'categoria': 'Goles'})

    # ── Córners ──
    for linea in [7.5, 8.5, 9.5, 10.5]:
        prob = round(p_poisson(lam_cor, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Córners más de {linea}',
                               'prob': prob, 'emoji': '⛳', 'categoria': 'Córners'})

    # ── Tiros a puerta ──
    for linea in [4.5, 5.5, 6.5, 7.5]:
        prob = round(p_poisson(lam_tiros, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Tiros a puerta más de {linea}',
                               'prob': prob, 'emoji': '🎯', 'categoria': 'Tiros'})

    # ── Faltas ──
    for linea in [18.5, 20.5, 22.5]:
        prob = round(p_poisson(lam_fal, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Faltas más de {linea}',
                               'prob': prob, 'emoji': '🦵', 'categoria': 'Faltas'})

    # ── Tarjetas ──
    for linea in [3.5, 4.5]:
        prob = round(p_poisson(lam_tar, linea)*100)
        if prob >= 55:
            candidatos.append({'mercado': f'Tarjetas más de {linea}',
                               'prob': prob, 'emoji': '🟨', 'categoria': 'Tarjetas'})

    if not candidatos:
        return None

    # Elegir el de MAYOR probabilidad
    mejor = max(candidatos, key=lambda x: x['prob'])
    prob  = mejor['prob']

    if prob >= 85:   nivel, emoji_n, clase = 'Muy Alta', '🟢', 'muy-alta'
    elif prob >= 75: nivel, emoji_n, clase = 'Alta',     '🟢', 'alta'
    elif prob >= 65: nivel, emoji_n, clase = 'Media',    '🟡', 'media'
    elif prob >= 55: nivel, emoji_n, clase = 'Leve',     '🟠', 'leve'
    else: return None

    return {
        'mercado'   : mejor['mercado'],
        'prob'      : prob,
        'emoji'     : mejor['emoji'],
        'categoria' : mejor['categoria'],
        'nivel'     : nivel,
        'emoji_nivel': emoji_n,
        'clase'     : clase,
    }

# Test con los 4 partidos de hoy
partidos_test = [
    {'local':'Colombia',  'visitante':'RD Congo',    'p1':44.7,'px':35.5,'p2':19.9,
     'xgl':1.5,'xgv':0.8,'cor':10.5,'tar':2.9,'tiros':7.0,'faltas':23.0},
    {'local':'Portugal',  'visitante':'Uzbekistán',  'p1':59.7,'px':28.2,'p2':12.1,
     'xgl':2.1,'xgv':0.8,'cor':12.6,'tar':3.4,'tiros':8.6,'faltas':17.5},
    {'local':'Panamá',    'visitante':'Croacia',      'p1':13.6,'px':25.8,'p2':60.6,
     'xgl':0.9,'xgv':2.1,'cor':11.0,'tar':3.4,'tiros':7.0,'faltas':23.5},
    {'local':'Inglaterra','visitante':'Ghana',        'p1':71.1,'px':18.8,'p2':10.1,
     'xgl':2.3,'xgv':0.8,'cor':14.0,'tar':3.4,'tiros':7.0,'faltas':18.5},
]

print("\n🧠 TEST — Mejor apuesta global por partido")
print("="*55)
for p in partidos_test:
    ba = mejor_apuesta_global(p)
    if ba:
        print(f"\n⚽ {p['local']} vs {p['visitante']}")
        print(f"   {ba['emoji_nivel']} [{ba['categoria']}] {ba['emoji']} {ba['mercado']}: {ba['prob']}% — {ba['nivel']}")
    else:
        print(f"\n⚽ {p['local']} vs {p['visitante']} → Sin pick recomendado")