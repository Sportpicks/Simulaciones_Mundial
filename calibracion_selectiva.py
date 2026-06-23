# -*- coding: utf-8 -*-
"""
calibracion_selectiva.py
Aplica calibración de empates SOLO cuando el favorito tiene
probabilidad menor a 65% — preservando los pronósticos claros.

Lógica:
- Favorito > 65% → NO calibrar (confiar en el modelo)
- Favorito < 65% → Aplicar calibración de empates
- Favorito < 55% → Calibración máxima

Uso: python calibracion_selectiva.py
"""

import os
import json
import math
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

UMBRAL_ALTA_CONFIANZA = 65.0  # Si favorito > 65% → no tocar
UMBRAL_MEDIA          = 55.0  # Si favorito < 55% → calibración máxima

def calibrar_selectivo(p1, px, p2, p1_pre, px_pre, p2_pre):
    """
    Decide si aplicar calibración según la confianza del modelo.
    
    Alta confianza (>65%): revierte a valores pre-calibración
    Media confianza (55-65%): calibración parcial (50%)
    Baja confianza (<55%): mantiene calibración completa
    """
    max_prob = max(p1, px, p2)
    max_prob_pre = max(p1_pre, px_pre, p2_pre)

    if max_prob_pre > UMBRAL_ALTA_CONFIANZA:
        # Alta confianza → revertir a pre-calibración
        return p1_pre, px_pre, p2_pre, 'sin_calibrar'

    elif max_prob_pre > UMBRAL_MEDIA:
        # Media confianza → calibración parcial (50%)
        p1_mix = round((p1 + p1_pre) / 2, 1)
        px_mix = round((px + px_pre) / 2, 1)
        p2_mix = round((p2 + p2_pre) / 2, 1)
        # Normalizar
        total = p1_mix + px_mix + p2_mix
        return (round(p1_mix/total*100,1),
                round(px_mix/total*100,1),
                round(p2_mix/total*100,1),
                'calibracion_parcial')
    else:
        # Baja confianza → calibración completa
        return p1, px, p2, 'calibracion_completa'


def main():
    print("\n🎯 CALIBRACIÓN SELECTIVA DE EMPATES")
    print("="*55)
    print("Alta confianza (>65%): SIN calibración")
    print("Media confianza (55-65%): calibración parcial")
    print("Baja confianza (<55%): calibración completa")
    print()

    csv = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
    df  = pd.read_csv(csv)

    if 'Prob_1_PreCal' not in df.columns:
        print("⚠️  No se encontraron valores pre-calibración")
        print("   Ejecuta primero: python calibrar_empates.py")
        return

    sin_cal = cal_par = cal_com = 0
    for i, r in df.iterrows():
        p1    = float(r['Prob_1_Final'])
        px    = float(r['Prob_X_Final'])
        p2    = float(r['Prob_2_Final'])
        p1_pre = float(r['Prob_1_PreCal'])
        px_pre = float(r['Prob_X_PreCal'])
        p2_pre = float(r['Prob_2_PreCal'])

        p1_n, px_n, p2_n, modo = calibrar_selectivo(
            p1, px, p2, p1_pre, px_pre, p2_pre
        )

        df.at[i, 'Prob_1_Final'] = p1_n
        df.at[i, 'Prob_X_Final'] = px_n
        df.at[i, 'Prob_2_Final'] = p2_n
        df.at[i, 'Modo_Calibracion'] = modo

        if modo == 'sin_calibrar':        sin_cal += 1
        elif modo == 'calibracion_parcial': cal_par += 1
        else:                               cal_com += 1

    df.to_csv(csv, index=False, encoding='utf-8-sig')

    print(f"✅ Sin calibración (>65%):     {sin_cal} partidos")
    print(f"✅ Calibración parcial (55-65%): {cal_par} partidos")
    print(f"✅ Calibración completa (<55%):  {cal_com} partidos")

    # Backtesting inmediato
    csv_real = os.path.join(RAIZ, 'Data', 'resultados_mundial.csv')
    if not os.path.exists(csv_real):
        return

    print("\n📊 BACKTESTING CALIBRACIÓN SELECTIVA")
    print("-"*55)
    df_real = pd.read_csv(csv_real)
    jugados = df_real[df_real['Estado'] == 'FINISHED']

    orig_ok = sel_ok = 0
    emp_orig = emp_sel = 0
    n = 0

    for _, real in jugados.iterrows():
        marc = str(real.get('Marcador', ''))
        if '-' not in marc and ':' not in marc:
            continue
        sep = '-' if '-' in marc else ':'
        try:
            gl, gv = map(int, marc.split(sep))
        except:
            continue
        res_real = '1' if gl > gv else ('X' if gl == gv else '2')

        pred = df[(df['Local'] == real['Local']) &
                  (df['Visitante'] == real['Visitante'])]
        if len(pred) == 0:
            continue
        p = pred.iloc[0]

        # Original (pre-calibración)
        p1o = float(p['Prob_1_PreCal'])
        pxo = float(p['Prob_X_PreCal'])
        p2o = float(p['Prob_2_PreCal'])
        pred_o = max({'1':p1o,'X':pxo,'2':p2o}, key=lambda k: {'1':p1o,'X':pxo,'2':p2o}[k])

        # Selectivo
        p1s = float(p['Prob_1_Final'])
        pxs = float(p['Prob_X_Final'])
        p2s = float(p['Prob_2_Final'])
        pred_s = max({'1':p1s,'X':pxs,'2':p2s}, key=lambda k: {'1':p1s,'X':pxs,'2':p2s}[k])

        if pred_o == res_real: orig_ok += 1
        if pred_s == res_real: sel_ok  += 1
        if pred_o == 'X': emp_orig += 1
        if pred_s == 'X': emp_sel  += 1
        n += 1

    if n > 0:
        pct_orig = round(orig_ok/n*100, 1)
        pct_sel  = round(sel_ok/n*100,  1)
        mejora   = round(pct_sel - pct_orig, 1)

        print(f"   Partidos analizados       : {n}")
        print(f"   Acierto SIN calibración   : {orig_ok}/{n} → {pct_orig}%")
        print(f"   Acierto calibración SELECT: {sel_ok}/{n} → {pct_sel}%")
        print(f"   {'📈 Mejora' if mejora>=0 else '📉 Cambio'}: {mejora:+.1f}%")
        print(f"   Empates predichos antes   : {emp_orig}")
        print(f"   Empates predichos ahora   : {emp_sel}")

        print(f"\n{'='*55}")
        print(f"  🏆 COMPARATIVA FINAL")
        print(f"{'='*55}")
        print(f"  Modelo original:           63.2%")
        print(f"  Calibración total:         57.9%")
        print(f"  Calibración selectiva:     {pct_sel}%")
        if pct_sel >= 63.2:
            print(f"  ✅ La calibración selectiva MEJORA el modelo")
        elif pct_sel >= 60.0:
            print(f"  🟡 La calibración selectiva mantiene buen rendimiento")
        else:
            print(f"  ⚠️  Ajustar umbrales de calibración")

if __name__ == '__main__':
    main()
