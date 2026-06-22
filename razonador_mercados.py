# -*- coding: utf-8 -*-
"""
razonador_mercados.py
Motor de razonamiento que analiza estadísticas por equipo
y decide automáticamente qué mercados mostrar y cómo.

Lógica:
- Si un equipo tiene promedio individual muy alto → muestra mercado por equipo
- Si el total combinado es más significativo → muestra mercado total
- Siempre elige el mercado con mayor probabilidad de acierto

Uso: importar como módulo desde generar_web_v6.py
"""

import os
import json
import math
import pandas as pd

RAIZ      = os.path.dirname(os.path.abspath(__file__))
JSON_STATS = os.path.join(RAIZ, 'Data', 'stats_equipos.json')

# Umbrales para considerar un equipo "destacado" en un mercado
UMBRAL_TIROS_EQUIPO   = 5.0   # Si un equipo promedia +5 tiros → mercado individual
UMBRAL_CORNERS_EQUIPO = 5.5   # Si un equipo promedia +5.5 córners → mercado individual
UMBRAL_FALTAS_EQUIPO  = 11.0  # Si un equipo promedia +11 faltas → mercado individual

def p_poisson(lam, linea):
    """P(N > linea) con N ~ Poisson(lam)."""
    k_min = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(k_min))
    except:
        return 0.0

def cargar_stats():
    """Carga estadísticas por equipo desde JSON."""
    if not os.path.exists(JSON_STATS):
        return {}
    with open(JSON_STATS, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_stat(stats, equipo, campo, fallback=0):
    """Obtiene una estadística con fallback seguro."""
    eq_data = stats.get(equipo, {})
    # Priorizar últimos 5, si no hay usar total
    val_5   = eq_data.get(f'{campo}_5',   None)
    val_tot = eq_data.get(f'{campo}_tot', None)
    if val_5 is not None and val_5 > 0:
        return float(val_5)
    if val_tot is not None and val_tot > 0:
        return float(val_tot)
    return fallback

def razonar_tiros(stats, local, visitante, lam_total):
    """
    Razona el mejor mercado de tiros a puerta.
    Decide si mostrar total o por equipo.
    Retorna lista de mercados razonados.
    """
    mercados = []

    tiros_l = get_stat(stats, local,    'tiros_favor', lam_total/2)
    tiros_v = get_stat(stats, visitante, 'tiros_favor', lam_total/2)
    total   = tiros_l + tiros_v

    # ── Mercado total ──
    for linea in [4.5, 5.5, 6.5]:
        prob = round(p_poisson(total, linea) * 100)
        if prob >= 55:
            mercados.append({
                'tipo'    : 'total',
                'mercado' : f'Tiros a puerta +{linea}',
                'prob'    : prob,
                'detalle' : f'{local} ({tiros_l:.1f}) + {visitante} ({tiros_v:.1f}) = {total:.1f} esp.',
                'razon'   : f'Ambos equipos generan tiros — total esperado {total:.1f}',
                'emoji'   : '🎯',
            })
            break  # Solo la línea más alta con prob suficiente

    # ── Mercado por equipo (si uno destaca) ──
    for equipo, tiros, rival_tiros in [
        (local, tiros_l, tiros_v),
        (visitante, tiros_v, tiros_l)
    ]:
        if tiros >= UMBRAL_TIROS_EQUIPO:
            for linea in [2.5, 3.5, 4.5]:
                prob = round(p_poisson(tiros, linea) * 100)
                if prob >= 60:
                    mercados.append({
                        'tipo'    : 'equipo',
                        'mercado' : f'{equipo} +{linea} tiros a puerta',
                        'prob'    : prob,
                        'detalle' : f'{equipo} promedia {tiros:.1f} tiros | {rival_tiros:.1f} del rival',
                        'razon'   : f'{equipo} es dominante en tiros ({tiros:.1f} por partido)',
                        'emoji'   : '🎯',
                    })
                    break

    return mercados

def razonar_corners(stats, local, visitante, lam_total):
    """
    Razona el mejor mercado de córners.
    """
    mercados = []

    corners_l = get_stat(stats, local,    'corners_favor', lam_total/2)
    corners_v = get_stat(stats, visitante, 'corners_favor', lam_total/2)
    total     = corners_l + corners_v

    # ── Mercado total ──
    for linea in [7.5, 8.5, 9.5]:
        prob = round(p_poisson(total, linea) * 100)
        if prob >= 55:
            mercados.append({
                'tipo'    : 'total',
                'mercado' : f'Córners totales +{linea}',
                'prob'    : prob,
                'detalle' : f'{local} ({corners_l:.1f}) + {visitante} ({corners_v:.1f}) = {total:.1f} esp.',
                'razon'   : f'Ambos equipos generan córners — total esperado {total:.1f}',
                'emoji'   : '⛳',
            })
            break

    # ── Mercado por equipo (si uno destaca) ──
    for equipo, corners, rival_corners in [
        (local, corners_l, corners_v),
        (visitante, corners_v, corners_l)
    ]:
        if corners >= UMBRAL_CORNERS_EQUIPO:
            for linea in [3.5, 4.5, 5.5]:
                prob = round(p_poisson(corners, linea) * 100)
                if prob >= 60:
                    mercados.append({
                        'tipo'    : 'equipo',
                        'mercado' : f'{equipo} +{linea} córners',
                        'prob'    : prob,
                        'detalle' : f'{equipo} promedia {corners:.1f} córners | rival {rival_corners:.1f}',
                        'razon'   : f'{equipo} domina en córners ({corners:.1f} por partido)',
                        'emoji'   : '⛳',
                    })
                    break

    return mercados

def razonar_faltas(stats, local, visitante, lam_total):
    """
    Razona el mejor mercado de faltas.
    """
    mercados = []

    faltas_l = get_stat(stats, local,    'faltas_cometidas', lam_total/2)
    faltas_v = get_stat(stats, visitante, 'faltas_cometidas', lam_total/2)
    total    = faltas_l + faltas_v

    # ── Mercado total ──
    for linea in [18.5, 20.5, 22.5]:
        prob = round(p_poisson(total, linea) * 100)
        if prob >= 55:
            mercados.append({
                'tipo'    : 'total',
                'mercado' : f'Faltas totales +{linea}',
                'prob'    : prob,
                'detalle' : f'{local} ({faltas_l:.1f}) + {visitante} ({faltas_v:.1f}) = {total:.1f} esp.',
                'razon'   : f'Partido físico esperado — {total:.1f} faltas proyectadas',
                'emoji'   : '🦵',
            })
            break

    # ── Mercado por equipo (si uno es muy faltador) ──
    for equipo, faltas, rival_faltas in [
        (local, faltas_l, faltas_v),
        (visitante, faltas_v, faltas_l)
    ]:
        if faltas >= UMBRAL_FALTAS_EQUIPO:
            for linea in [8.5, 9.5, 10.5]:
                prob = round(p_poisson(faltas, linea) * 100)
                if prob >= 60:
                    mercados.append({
                        'tipo'    : 'equipo',
                        'mercado' : f'{equipo} +{linea} faltas',
                        'prob'    : prob,
                        'detalle' : f'{equipo} promedia {faltas:.1f} faltas | rival {rival_faltas:.1f}',
                        'razon'   : f'{equipo} es un equipo físico ({faltas:.1f} faltas por partido)',
                        'emoji'   : '🦵',
                    })
                    break

    return mercados

def razonar_partido(local, visitante, lam_tiros, lam_corners, lam_faltas):
    """
    Función principal: razona todos los mercados para un partido.
    Retorna los mercados ordenados por probabilidad.
    """
    stats = cargar_stats()

    todos_mercados = []
    todos_mercados += razonar_tiros(stats, local, visitante, lam_tiros)
    todos_mercados += razonar_corners(stats, local, visitante, lam_corners)
    todos_mercados += razonar_faltas(stats, local, visitante, lam_faltas)

    # Ordenar por probabilidad descendente
    todos_mercados.sort(key=lambda x: x['prob'], reverse=True)

    return todos_mercados


if __name__ == '__main__':
    print("\n🧠 TEST — Razonador de mercados")
    print("="*50)

    stats = cargar_stats()
    print(f"✅ Estadísticas cargadas: {len(stats)} equipos")

    # Test con Argentina vs Austria
    print("\n📊 Argentina vs Austria:")
    mercados = razonar_partido('Argentina', 'Austria', 6.0, 9.3, 23.0)
    for m in mercados:
        tipo = "🏟️ Total" if m['tipo']=='total' else "👤 Equipo"
        print(f"   {m['emoji']} [{tipo}] {m['mercado']}: {m['prob']}%")
        print(f"      📊 {m['detalle']}")
        print(f"      💡 {m['razon']}")

    print("\n📊 Noruega vs Senegal:")
    mercados2 = razonar_partido('Noruega', 'Senegal', 4.6, 11.3, 16.5)
    for m in mercados2:
        tipo = "🏟️ Total" if m['tipo']=='total' else "👤 Equipo"
        print(f"   {m['emoji']} [{tipo}] {m['mercado']}: {m['prob']}%")
        print(f"      💡 {m['razon']}")
