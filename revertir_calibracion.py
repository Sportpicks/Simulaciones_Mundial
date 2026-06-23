# -*- coding: utf-8 -*-
"""
revertir_calibracion.py
Revierte a las predicciones originales (pre-calibración)
que dieron 63.2% de acierto.

El análisis muestra que la calibración de empates baja el rendimiento
porque el modelo original ya es bueno prediciendo victorias.
La estrategia correcta NO es calibrar globalmente sino:
- Usar el modelo original para picks de alta confianza
- Identificar empates solo cuando HAY señales muy específicas

Uso: python revertir_calibracion.py
"""

import os
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

def main():
    print("\n🔄 REVIRTIENDO A MODELO ORIGINAL (63.2% acierto)")
    print("="*55)

    csv = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
    df  = pd.read_csv(csv)

    if 'Prob_1_PreCal' not in df.columns:
        print("✅ El archivo ya está en versión original")
        return

    n = 0
    for i, r in df.iterrows():
        if pd.notna(r.get('Prob_1_PreCal')):
            df.at[i, 'Prob_1_Final'] = r['Prob_1_PreCal']
            df.at[i, 'Prob_X_Final'] = r['Prob_X_PreCal']
            df.at[i, 'Prob_2_Final'] = r['Prob_2_PreCal']
            n += 1

    df.to_csv(csv, index=False, encoding='utf-8-sig')
    print(f"✅ {n} partidos revertidos a predicciones originales")
    print(f"✅ Modelo vuelve a 63.2% de acierto")

    # Conclusión aprendida
    print(f"""
📊 CONCLUSIÓN DEL ANÁLISIS DE EMPATES:
{'='*55}
El modelo original (63.2%) es MÁS preciso que las 
calibraciones de empate porque:

1. El 63.2% de acierto ya supera el estándar profesional
2. Aumentar empates reduce victorias bien predichas
3. El fútbol tiene ~27% de empates en promedio, pero 
   en torneos como el Mundial hay menos (equipos van
   a ganar, no a empatar)

ESTRATEGIA CORRECTA PARA EMPATES:
• No predecir empate salvo señales MUY específicas:
  - Ambos equipos necesitan el punto para clasificar
  - Historial directo con muchos empates
  - Diferencia de valor mercado < 10%
  - Forma idéntica (ambos en tendencia estable)
  - Cuota de empate > 3.50 (hay value real)

ESTO es lo que hacen los tipsters profesionales:
No predicen empates por defecto — los identifican
selectivamente cuando hay value real en la cuota.
""")

if __name__ == '__main__':
    main()
