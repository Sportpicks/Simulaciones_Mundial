# -*- coding: utf-8 -*-
"""
calibrar_empates.py
Calibración específica para empates basada en la auditoría del modelo.

Problema detectado: 0/9 empates reales fueron predichos correctamente.
Solución: Aumentar la probabilidad de empate cuando los equipos están
parejos, usando múltiples factores de ajuste.

Factores de calibración:
1. Diferencia de probabilidades (si p1-px < 20 → empate más probable)
2. Historial de empates de cada equipo
3. Factor de paridad de planteles (valor mercado similar)
4. Ajuste Dixon-Coles mejorado

Uso: python calibrar_empates.py
"""

import os
import json
import math
import pandas as pd
import numpy as np

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

# ── Parámetros de calibración (ajustados con auditoría) ──────────────────────
UMBRAL_PARIDAD      = 20.0   # Si |p1-p2| < 20% → partidos parejos
BOOST_EMPATE_BASE   = 0.08   # +8% base cuando hay paridad
BOOST_EMPATE_EXTRA  = 0.05   # +5% extra si hay historial de empates
MAX_BOOST_EMPATE    = 0.18   # Máximo +18% al empate

def calcular_tasa_empates_equipo(df_hist, equipo):
    """Calcula la tasa histórica de empates de un equipo."""
    local = df_hist[df_hist['Equipo_Local'] == equipo]
    visit = df_hist[df_hist['Equipo_Visitante'] == equipo]

    total = len(local) + len(visit)
    if total == 0:
        return 0.28  # promedio mundial ~28%

    empates_l = len(local[local['Goles_Local'] == local['Goles_Visitante']])
    empates_v = len(visit[visit['Goles_Visitante'] == visit['Goles_Local']])
    tasa = (empates_l + empates_v) / total
    return round(float(tasa), 3)

def factor_paridad_mercado(vm_local, vm_visit):
    """
    Calcula factor de paridad basado en valor de mercado.
    Si los planteles tienen valor similar → más probable el empate.
    """
    if vm_local <= 0 or vm_visit <= 0:
        return 0
    ratio = min(vm_local, vm_visit) / max(vm_local, vm_visit)
    # ratio = 1.0 → planteles iguales → máximo boost
    # ratio = 0.1 → uno vale 10x más → mínimo boost
    return round(ratio * 0.06, 4)  # Hasta +6% extra por paridad de planteles

def calibrar_probabilidades(p1, px, p2, tasa_emp_l, tasa_emp_v,
                             vm_local, vm_visit, factor_forma=0):
    """
    Recalibra las probabilidades aumentando el empate cuando corresponde.

    Factores:
    - Paridad: |p1-p2| < umbral
    - Historial de empates de ambos equipos
    - Paridad de planteles (valor mercado)
    - Factor de forma (si ambos están estables)
    """
    diferencia = abs(p1 - p2)
    boost_total = 0

    # Factor 1: Paridad de resultados
    if diferencia < UMBRAL_PARIDAD:
        # Boost proporcional a la paridad (más parejo → más boost)
        factor_paridad = (UMBRAL_PARIDAD - diferencia) / UMBRAL_PARIDAD
        boost_total += BOOST_EMPATE_BASE * factor_paridad

    # Factor 2: Historial de empates
    tasa_emp_prom = (tasa_emp_l + tasa_emp_v) / 2
    if tasa_emp_prom > 0.30:  # Si ambos empatan más del 30% del tiempo
        boost_total += BOOST_EMPATE_EXTRA * (tasa_emp_prom - 0.28)

    # Factor 3: Paridad de planteles
    boost_total += factor_paridad_mercado(vm_local, vm_visit)

    # Factor 4: Forma similar (si factor_forma es neutro)
    if abs(factor_forma) < 0.03:
        boost_total += 0.02  # +2% extra si la forma es similar

    # Limitar el boost máximo
    boost_total = min(boost_total, MAX_BOOST_EMPATE)

    if boost_total <= 0.01:
        return p1, px, p2  # Sin cambios significativos

    # Aplicar boost: tomar de p1 y p2 proporcional a su tamaño
    px_nuevo = px + boost_total * 100
    reduccion = boost_total * 100
    # Reducir de local y visitante proporcional a sus probabilidades
    total_no_x = p1 + p2
    if total_no_x > 0:
        p1_nuevo = p1 - reduccion * (p1 / total_no_x)
        p2_nuevo = p2 - reduccion * (p2 / total_no_x)
    else:
        p1_nuevo, p2_nuevo = p1, p2

    # Normalizar
    total = p1_nuevo + px_nuevo + p2_nuevo
    p1_f  = round(p1_nuevo / total * 100, 1)
    px_f  = round(px_nuevo  / total * 100, 1)
    p2_f  = round(p2_nuevo  / total * 100, 1)

    return p1_f, px_f, p2_f

def main():
    print("\n🎯 CALIBRACIÓN DE EMPATES")
    print("="*55)
    print("Problema: 0/9 empates reales fueron predichos (0%)")
    print("Solución: Calibración multi-factor de probabilidades")
    print()

    # Cargar datos
    df_hist = pd.read_csv(os.path.join(RAIZ, 'Data', 'datos_historicos.csv'))
    df_pred = pd.read_csv(os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv'))

    print(f"✅ Histórico: {len(df_hist)} partidos")
    print(f"✅ Predicciones: {len(df_pred)} partidos")

    # Cargar forma si existe
    forma_path = os.path.join(RAIZ, 'Data', 'forma_equipos.json')
    forma = {}
    if os.path.exists(forma_path):
        with open(forma_path) as f:
            forma = json.load(f)
        print(f"✅ Forma cargada: {len(forma)} equipos")

    # Calcular tasa de empates por equipo
    print("\n📊 Calculando tasa histórica de empates...")
    equipos = list(set(df_pred['Local'].tolist() + df_pred['Visitante'].tolist()))
    tasas   = {eq: calcular_tasa_empates_equipo(df_hist, eq) for eq in equipos}

    # Mostrar equipos con mayor tasa de empates
    tasas_ord = sorted(tasas.items(), key=lambda x: x[1], reverse=True)
    print("\n   Top 8 equipos que más empatan históricamente:")
    for eq, t in tasas_ord[:8]:
        print(f"   {eq:<25} {round(t*100,1)}% de sus partidos")

    # Aplicar calibración
    print("\n🔧 Aplicando calibración a predicciones...")
    filas = []
    cambios = 0

    for _, r in df_pred.iterrows():
        local  = r['Local']
        visit  = r['Visitante']
        p1_orig = float(r['Prob_1_Final'])
        px_orig = float(r['Prob_X_Final'])
        p2_orig = float(r['Prob_2_Final'])

        tasa_l  = tasas.get(local,  0.28)
        tasa_v  = tasas.get(visit,  0.28)
        vm_l    = float(r.get('VM_Local',    100))
        vm_v    = float(r.get('VM_Visitante', 100))
        f_forma = float(r.get('Factor_Forma', 0))

        p1_cal, px_cal, p2_cal = calibrar_probabilidades(
            p1_orig, px_orig, p2_orig,
            tasa_l, tasa_v, vm_l, vm_v, f_forma
        )

        boost = round(px_cal - px_orig, 1)
        if boost > 0.5:
            cambios += 1

        fila = r.to_dict()
        # Guardar originales para comparación
        fila['Prob_1_PreCal'] = p1_orig
        fila['Prob_X_PreCal'] = px_orig
        fila['Prob_2_PreCal'] = p2_orig
        # Actualizar con calibración
        fila['Prob_1_Final']  = p1_cal
        fila['Prob_X_Final']  = px_cal
        fila['Prob_2_Final']  = p2_cal
        fila['Boost_Empate']  = boost
        fila['Tasa_Emp_Local'] = round(tasa_l * 100, 1)
        fila['Tasa_Emp_Visit'] = round(tasa_v * 100, 1)
        filas.append(fila)

    df_cal = pd.DataFrame(filas)
    print(f"✅ Predicciones calibradas: {cambios} partidos ajustados")

    # Mostrar partidos más afectados
    afectados = df_cal[df_cal['Boost_Empate'] > 1].sort_values(
        'Boost_Empate', ascending=False
    )
    if len(afectados) > 0:
        print(f"\n   🎯 Partidos con mayor ajuste al empate:")
        print(f"   {'Partido':<35} {'X ant':>6} {'X cal':>6} {'Boost':>6}")
        print(f"   {'-'*55}")
        for _, r in afectados.head(10).iterrows():
            partido = f"{r['Local'][:15]} vs {r['Visitante'][:15]}"
            print(f"   {partido:<35} {r['Prob_X_PreCal']:>5.1f}% "
                  f"{r['Prob_X_Final']:>5.1f}% {r['Boost_Empate']:>+5.1f}%")

    # Validar con resultados reales (backtesting)
    csv_real = os.path.join(RAIZ, 'Data', 'resultados_mundial.csv')
    if os.path.exists(csv_real):
        print("\n📊 BACKTESTING — ¿Mejora la calibración?")
        print("-"*55)
        df_real = pd.read_csv(csv_real)
        jugados = df_real[df_real['Estado']=='FINISHED']

        orig_ok = cal_ok = 0
        n_jugados = 0
        empates_orig = empates_cal = 0

        for _, real in jugados.iterrows():
            local_r = real['Local']
            visit_r = real['Visitante']
            marc    = str(real.get('Marcador',''))
            if '-' not in marc and ':' not in marc: continue
            sep = '-' if '-' in marc else ':'
            try: gl, gv = map(int, marc.split(sep))
            except: continue
            res_real = '1' if gl>gv else ('X' if gl==gv else '2')

            pred_orig = df_cal[
                (df_cal['Local']==local_r) &
                (df_cal['Visitante']==visit_r)
            ]
            if len(pred_orig) == 0: continue
            p = pred_orig.iloc[0]

            # Predicción original
            p1o = float(p['Prob_1_PreCal'])
            pxo = float(p['Prob_X_PreCal'])
            p2o = float(p['Prob_2_PreCal'])
            pred_o = max({'1':p1o,'X':pxo,'2':p2o}, key=lambda k: {'1':p1o,'X':pxo,'2':p2o}[k])

            # Predicción calibrada
            p1c = float(p['Prob_1_Final'])
            pxc = float(p['Prob_X_Final'])
            p2c = float(p['Prob_2_Final'])
            pred_c = max({'1':p1c,'X':pxc,'2':p2c}, key=lambda k: {'1':p1c,'X':pxc,'2':p2c}[k])

            if pred_o == res_real: orig_ok += 1
            if pred_c == res_real: cal_ok  += 1
            if pred_o == 'X': empates_orig += 1
            if pred_c == 'X': empates_cal  += 1
            n_jugados += 1

        if n_jugados > 0:
            pct_orig = round(orig_ok/n_jugados*100, 1)
            pct_cal  = round(cal_ok/n_jugados*100,  1)
            print(f"   Partidos analizados     : {n_jugados}")
            print(f"   Acierto SIN calibración : {orig_ok}/{n_jugados} → {pct_orig}%")
            print(f"   Acierto CON calibración : {cal_ok}/{n_jugados} → {pct_cal}%")
            mejora = round(pct_cal - pct_orig, 1)
            if mejora > 0:
                print(f"   📈 Mejora: +{mejora}% ✅")
            elif mejora == 0:
                print(f"   ➡️  Sin cambio en acierto global")
            else:
                print(f"   📉 Reducción: {mejora}% (normal si aumentamos empates)")
            print(f"   Empates predichos antes : {empates_orig}")
            print(f"   Empates predichos ahora : {empates_cal}")

    # Guardar
    salida = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
    df_cal.to_csv(salida, index=False, encoding='utf-8-sig')
    print(f"\n✅ Predicciones calibradas guardadas")
    print(f"   Partidos ajustados: {cambios}")

if __name__ == '__main__':
    main()
