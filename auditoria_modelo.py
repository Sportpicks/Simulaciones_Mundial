# -*- coding: utf-8 -*-
"""
auditoria_modelo.py
Compara las predicciones del modelo vs resultados reales del Mundial 2026.
Calcula el % de acierto en todos los mercados disponibles.
"""

import os
import math
import pandas as pd
import numpy as np
from datetime import date

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

def p_poisson(lam, linea):
    k = int(linea) + 1
    try:
        return 1 - sum(math.exp(-lam)*lam**i/math.factorial(i) for i in range(k))
    except:
        return 0.0

def resultado_real_1x2(gl, gv):
    if gl > gv:  return '1'
    if gl == gv: return 'X'
    return '2'

def main():
    print("\n🔍 AUDITORÍA COMPLETA DEL MODELO")
    print("="*60)

    # Cargar resultados reales
    csv_real = os.path.join(RAIZ, 'Data', 'resultados_mundial.csv')
    csv_pred = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')

    if not os.path.exists(csv_real):
        print("❌ No se encontró resultados_mundial.csv")
        return
    if not os.path.exists(csv_pred):
        print("❌ No se encontró predicciones_finales.csv")
        return

    df_real = pd.read_csv(csv_real)
    df_pred = pd.read_csv(csv_pred)

    # Solo partidos ya jugados
    jugados = df_real[df_real['Estado'] == 'FINISHED'].copy()
    print(f"✅ Partidos jugados disponibles: {len(jugados)}")
    print(f"✅ Predicciones disponibles: {len(df_pred)}")

    # Unir predicciones con resultados reales
    resultados = []

    for _, real in jugados.iterrows():
        local_r = real['Local']
        visit_r = real['Visitante']
        gl      = real.get('Goles_Local', None)
        gv      = real.get('Goles_Visitante', None)

        if pd.isna(gl) or pd.isna(gv):
            # Intentar parsear desde marcador
            marc = str(real.get('Marcador', ''))
            if '-' in marc or ':' in marc:
                sep = '-' if '-' in marc else ':'
                try:
                    gl, gv = map(int, marc.split(sep))
                except:
                    continue
            else:
                continue

        gl, gv = int(gl), int(gv)
        res_real = resultado_real_1x2(gl, gv)
        total_goles = gl + gv

        # Buscar predicción correspondente
        pred = df_pred[
            (df_pred['Local'] == local_r) &
            (df_pred['Visitante'] == visit_r)
        ]

        if len(pred) == 0:
            # Intentar invertido (por si hay diferencia en nombre)
            for _, p in df_pred.iterrows():
                if local_r in p['Local'] or p['Local'] in local_r:
                    if visit_r in p['Visitante'] or p['Visitante'] in visit_r:
                        pred = df_pred[(df_pred['Local']==p['Local']) &
                                      (df_pred['Visitante']==p['Visitante'])]
                        break

        if len(pred) == 0:
            continue

        p = pred.iloc[0]
        p1 = float(p['Prob_1_Final'])
        px = float(p['Prob_X_Final'])
        p2 = float(p['Prob_2_Final'])

        # Resultado predicho (mayor probabilidad)
        probs = {'1': p1, 'X': px, '2': p2}
        pred_resultado = max(probs, key=probs.get)
        acierto_1x2 = pred_resultado == res_real

        # Marcador predicho vs real
        marc_pred = str(p.get('Marcador_Predicho', ''))
        acierto_marcador = False
        if marc_pred and '-' in marc_pred:
            try:
                gl_p, gv_p = map(int, marc_pred.split('-'))
                acierto_marcador = (gl_p == gl and gv_p == gv)
            except:
                pass

        # Over/Under goles
        over_pred_25  = (p1 + p2) > 55  # proxy: si hay favorito claro → más goles
        over_real_25  = total_goles > 2
        # Mejor proxy: usar xG si disponible
        xgl = float(p.get('xG_L', 0))
        xgv = float(p.get('xG_V', 0))
        xg_total = xgl + xgv
        over_pred_25_xg = xg_total > 2.5
        over_real_25    = total_goles > 2

        # BTTS (ambos anotan)
        btts_real = gl > 0 and gv > 0
        btts_pred = xgl > 0.9 and xgv > 0.7  # proxy por xG

        # Doble oportunidad
        do_1x_pred = p1 + px
        do_x2_pred = px + p2
        do_12_pred = p1 + p2
        acierto_1x = (res_real in ['1','X'])
        acierto_x2 = (res_real in ['X','2'])
        acierto_12 = (res_real in ['1','2'])

        # Corners (usando lam_cor del modelo)
        lam_cor = float(p.get('cor', 9.0))
        over_75_pred = p_poisson(lam_cor, 7.5) > 0.5
        over_85_pred = p_poisson(lam_cor, 8.5) > 0.5

        # Faltas
        lam_fal = float(p.get('faltas', 22.0))
        over_18_pred = p_poisson(lam_fal, 18.5) > 0.5

        resultados.append({
            'Fecha'          : real.get('Fecha',''),
            'Local'          : local_r,
            'Visitante'      : visit_r,
            'Goles_Real'     : f"{gl}-{gv}",
            'Res_Real'       : res_real,
            'Res_Predicho'   : pred_resultado,
            'Prob_Pred'      : round(probs[pred_resultado], 1),
            'Acierto_1X2'    : acierto_1x2,
            'Marcador_Pred'  : marc_pred,
            'Acierto_Marcador': acierto_marcador,
            'xG_Total'       : round(xg_total, 2),
            'Over25_Pred_xG' : over_pred_25_xg,
            'Over25_Real'    : over_real_25,
            'Acierto_Over25' : over_pred_25_xg == over_real_25,
            'BTTS_Pred'      : btts_pred,
            'BTTS_Real'      : btts_real,
            'Acierto_BTTS'   : btts_pred == btts_real,
            'DO_1X_Prob'     : round(do_1x_pred, 1),
            'Acierto_DO_1X'  : acierto_1x,
            'DO_X2_Prob'     : round(do_x2_pred, 1),
            'Acierto_DO_X2'  : acierto_x2,
            'Cor_Pred_O75'   : over_75_pred,
            'Cor_Pred_O85'   : over_85_pred,
            'Fal_Pred_O18'   : over_18_pred,
            'Tendencia_L'    : p.get('Tendencia_Local','?'),
            'Tendencia_V'    : p.get('Tendencia_Visitante','?'),
        })

    if not resultados:
        print("❌ No se pudieron cruzar predicciones con resultados reales")
        return

    df = pd.DataFrame(resultados)
    n  = len(df)

    print(f"\n{'='*60}")
    print(f"  📊 RESULTADOS DE LA AUDITORÍA ({n} partidos)")
    print(f"{'='*60}")

    # ── 1X2 ──
    ac_1x2 = df['Acierto_1X2'].sum()
    pct_1x2 = round(ac_1x2/n*100, 1)
    print(f"\n⚽ RESULTADO 1X2:")
    print(f"   Aciertos: {ac_1x2}/{n} → {pct_1x2}%")
    print(f"   Referencia profesional: ~55-65%")
    if pct_1x2 >= 65:   print(f"   🟢 EXCELENTE — supera el estándar profesional")
    elif pct_1x2 >= 55: print(f"   🟡 BUENO — dentro del rango profesional")
    else:               print(f"   🔴 POR DEBAJO — normal en torneos con sorpresas")

    # Por confianza
    alta_conf = df[df['Prob_Pred'] >= 50]
    if len(alta_conf) > 0:
        ac_alta = alta_conf['Acierto_1X2'].sum()
        print(f"   Aciertos con prob >50%: {ac_alta}/{len(alta_conf)} → {round(ac_alta/len(alta_conf)*100,1)}%")

    # ── Marcador exacto ──
    ac_marc = df['Acierto_Marcador'].sum()
    pct_marc = round(ac_marc/n*100, 1)
    print(f"\n🎯 MARCADOR EXACTO:")
    print(f"   Aciertos: {ac_marc}/{n} → {pct_marc}%")
    print(f"   Referencia: ~8-12% es excelente")

    # ── Over/Under 2.5 goles ──
    ac_ou = df['Acierto_Over25'].sum()
    pct_ou = round(ac_ou/n*100, 1)
    print(f"\n⚽ OVER/UNDER 2.5 GOLES (via xG):")
    print(f"   Aciertos: {ac_ou}/{n} → {pct_ou}%")

    # ── BTTS ──
    ac_btts = df['Acierto_BTTS'].sum()
    pct_btts = round(ac_btts/n*100, 1)
    print(f"\n🔄 BTTS (ambos anotan):")
    print(f"   Aciertos: {ac_btts}/{n} → {pct_btts}%")

    # ── Detalle partido a partido ──
    print(f"\n{'='*60}")
    print(f"  📋 DETALLE PARTIDO A PARTIDO")
    print(f"{'='*60}")
    print(f"{'Partido':<35} {'Real':^5} {'Pred':^5} {'Prob':>5} {'1X2':^5} {'Marc':^5}")
    print("-"*60)

    for _, r in df.sort_values('Fecha').iterrows():
        partido = f"{r['Local'][:12]} vs {r['Visitante'][:12]}"
        ac1 = "✅" if r['Acierto_1X2'] else "❌"
        acm = "✅" if r['Acierto_Marcador'] else "❌"
        print(f"{partido:<35} {r['Res_Real']:^5} {r['Res_Predicho']:^5} "
              f"{r['Prob_Pred']:>4.0f}% {ac1:^5} {acm:^5}")

    # ── Análisis por tipo de resultado ──
    print(f"\n{'='*60}")
    print(f"  📊 ANÁLISIS POR TIPO DE RESULTADO")
    print(f"{'='*60}")
    for res in ['1','X','2']:
        sub = df[df['Res_Real']==res]
        if len(sub) == 0: continue
        ac = sub['Acierto_1X2'].sum()
        print(f"   Cuando el resultado real fue '{res}': "
              f"{ac}/{len(sub)} aciertos ({round(ac/len(sub)*100,1)}%)")

    # ── Partidos con alta confianza ──
    print(f"\n{'='*60}")
    print(f"  🎯 PARTIDOS CON MAYOR CONFIANZA (prob > 60%)")
    print(f"{'='*60}")
    alta = df[df['Prob_Pred'] >= 60].sort_values('Prob_Pred', ascending=False)
    for _, r in alta.iterrows():
        ac = "✅" if r['Acierto_1X2'] else "❌"
        print(f"   {ac} {r['Local']} vs {r['Visitante']}: "
              f"predijo '{r['Res_Predicho']}' ({r['Prob_Pred']:.0f}%) → real '{r['Res_Real']}' ({r['Goles_Real']})")

    # ── Resumen ejecutivo ──
    print(f"\n{'='*60}")
    print(f"  🏆 RESUMEN EJECUTIVO")
    print(f"{'='*60}")
    print(f"   Partidos analizados : {n}")
    print(f"   Acierto 1X2         : {pct_1x2}% {'✅' if pct_1x2>=55 else '⚠️'}")
    print(f"   Marcador exacto     : {pct_marc}% {'✅' if pct_marc>=8 else '⚠️'}")
    print(f"   Over/Under 2.5      : {pct_ou}% {'✅' if pct_ou>=55 else '⚠️'}")
    print(f"   BTTS                : {pct_btts}% {'✅' if pct_btts>=55 else '⚠️'}")

    # Guardar reporte
    salida = os.path.join(RAIZ, 'Predicciones', 'auditoria_modelo.csv')
    df.to_csv(salida, index=False, encoding='utf-8-sig')
    print(f"\n✅ Reporte guardado en: Predicciones/auditoria_modelo.csv")

if __name__ == '__main__':
    main()
