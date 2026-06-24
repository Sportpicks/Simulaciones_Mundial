# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 23:39:14 2026

@author: PC
"""

# -*- coding: utf-8 -*-
"""
actualizar_montecarlo_realista.py
Actualiza las probabilidades de campeón del Monte Carlo
incorporando los resultados reales ya jugados en la fase de grupos.

Lógica:
- Equipos ya eliminados o con muy pocas opciones → reducir drásticamente
- Equipos que van líderes con buen rendimiento → mantener o subir
- Sorpresas que están funcionando → subir
- Equipos que van mal pese a ser favoritos → bajar

Uso: python actualizar_montecarlo_realista.py
"""

import os
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

# ── Estado real tras Jornada 2 (23 junio 2026) ──────────────────────────────
# Puntos reales de cada equipo tras 2 jornadas
ESTADO_REAL = {
    # Grupo A
    'México'           : {'pts':6, 'j':2, 'gf':3, 'gc':0, 'pos':1, 'estado':'lider'},
    'Corea del Sur'    : {'pts':3, 'j':2, 'gf':2, 'gc':2, 'pos':2, 'estado':'segundo'},
    'República Checa'  : {'pts':1, 'j':2, 'gf':2, 'gc':3, 'pos':3, 'estado':'tercero'},
    'Sudáfrica'        : {'pts':1, 'j':2, 'gf':1, 'gc':3, 'pos':4, 'estado':'peligro'},

    # Grupo B
    'Canadá'           : {'pts':4, 'j':2, 'gf':7, 'gc':1, 'pos':1, 'estado':'lider'},
    'Suiza'            : {'pts':4, 'j':2, 'gf':5, 'gc':2, 'pos':2, 'estado':'segundo'},
    'Bosnia-Herzegovina':{'pts':1, 'j':2, 'gf':2, 'gc':5, 'pos':3, 'estado':'peligro'},
    'Catar'            : {'pts':1, 'j':2, 'gf':1, 'gc':7, 'pos':4, 'estado':'eliminado'},

    # Grupo C
    'Brasil'           : {'pts':4, 'j':2, 'gf':4, 'gc':1, 'pos':1, 'estado':'lider'},
    'Marruecos'        : {'pts':2, 'j':2, 'gf':1, 'gc':1, 'pos':2, 'estado':'segundo'},
    'Escocia'          : {'pts':3, 'j':2, 'gf':1, 'gc':0, 'pos':2, 'estado':'segundo'},
    'Haití'            : {'pts':0, 'j':2, 'gf':0, 'gc':4, 'pos':4, 'estado':'eliminado'},

    # Grupo D
    'EE. UU.'          : {'pts':6, 'j':2, 'gf':6, 'gc':1, 'pos':1, 'estado':'lider'},
    'Paraguay'         : {'pts':3, 'j':2, 'gf':1, 'gc':1, 'pos':2, 'estado':'segundo'},
    'Australia'        : {'pts':3, 'j':2, 'gf':2, 'gc':2, 'pos':2, 'estado':'segundo'},
    'Turquía'          : {'pts':0, 'j':2, 'gf':0, 'gc':5, 'pos':4, 'estado':'eliminado'},

    # Grupo E
    'Alemania'         : {'pts':6, 'j':2, 'gf':9, 'gc':2, 'pos':1, 'estado':'lider'},
    'Costa de Marfil'  : {'pts':3, 'j':2, 'gf':1, 'gc':1, 'pos':2, 'estado':'segundo'},
    'Ecuador'          : {'pts':1, 'j':2, 'gf':0, 'gc':1, 'pos':3, 'estado':'peligro'},
    'Curazao'          : {'pts':1, 'j':2, 'gf':4, 'gc':9, 'pos':4, 'estado':'peligro'},

    # Grupo F
    'Países Bajos'     : {'pts':4, 'j':2, 'gf':7, 'gc':3, 'pos':1, 'estado':'lider'},
    'Suecia'           : {'pts':3, 'j':2, 'gf':5, 'gc':3, 'pos':2, 'estado':'segundo'},
    'Japón'            : {'pts':3, 'j':2, 'gf':4, 'gc':3, 'pos':2, 'estado':'segundo'},
    'Túnez'            : {'pts':0, 'j':2, 'gf':1, 'gc':9, 'pos':4, 'estado':'eliminado'},

    # Grupo G
    'Bélgica'          : {'pts':2, 'j':2, 'gf':1, 'gc':1, 'pos':1, 'estado':'lider'},
    'Egipto'           : {'pts':2, 'j':2, 'gf':4, 'gc':3, 'pos':2, 'estado':'segundo'},
    'Irán'             : {'pts':2, 'j':2, 'gf':2, 'gc':2, 'pos':2, 'estado':'segundo'},
    'Nueva Zelanda'    : {'pts':1, 'j':2, 'gf':3, 'gc':5, 'pos':3, 'estado':'peligro'},

    # Grupo H
    'España'           : {'pts':4, 'j':2, 'gf':4, 'gc':0, 'pos':1, 'estado':'lider'},
    'Uruguay'          : {'pts':2, 'j':2, 'gf':3, 'gc':3, 'pos':2, 'estado':'segundo'},
    'Arabia Saudí'     : {'pts':1, 'j':2, 'gf':1, 'gc':5, 'pos':3, 'estado':'peligro'},
    'Cabo Verde'       : {'pts':2, 'j':2, 'gf':0, 'gc':0, 'pos':2, 'estado':'segundo'},

    # Grupo I
    'Francia'          : {'pts':6, 'j':2, 'gf':6, 'gc':2, 'pos':1, 'estado':'lider'},
    'Noruega'          : {'pts':3, 'j':2, 'gf':4, 'gc':2, 'pos':2, 'estado':'segundo'},
    'Senegal'          : {'pts':3, 'j':2, 'gf':3, 'gc':4, 'pos':2, 'estado':'segundo'},
    'Irak'             : {'pts':0, 'j':2, 'gf':2, 'gc':7, 'pos':4, 'estado':'eliminado'},

    # Grupo J
    'Argentina'        : {'pts':6, 'j':2, 'gf':5, 'gc':1, 'pos':1, 'estado':'lider'},
    'Austria'          : {'pts':3, 'j':2, 'gf':4, 'gc':2, 'pos':2, 'estado':'segundo'},
    'Argelia'          : {'pts':3, 'j':2, 'gf':1, 'gc':2, 'pos':2, 'estado':'segundo'},
    'Jordania'         : {'pts':0, 'j':2, 'gf':1, 'gc':6, 'pos':4, 'estado':'eliminado'},

    # Grupo K
    'Colombia'         : {'pts':3, 'j':1, 'gf':3, 'gc':1, 'pos':1, 'estado':'lider'},
    'Portugal'         : {'pts':1, 'j':1, 'gf':1, 'gc':1, 'pos':2, 'estado':'segundo'},
    'RD Congo'         : {'pts':1, 'j':1, 'gf':1, 'gc':1, 'pos':2, 'estado':'segundo'},
    'Uzbekistán'       : {'pts':0, 'j':1, 'gf':1, 'gc':3, 'pos':4, 'estado':'peligro'},

    # Grupo L
    'Inglaterra'       : {'pts':3, 'j':1, 'gf':4, 'gc':2, 'pos':1, 'estado':'lider'},
    'Ghana'            : {'pts':3, 'j':1, 'gf':1, 'gc':0, 'pos':1, 'estado':'lider'},
    'Croacia'          : {'pts':0, 'j':1, 'gf':2, 'gc':4, 'pos':3, 'estado':'peligro'},
    'Panamá'           : {'pts':0, 'j':1, 'gf':0, 'gc':1, 'pos':4, 'estado':'peligro'},
}

# ── Factores de ajuste basados en rendimiento real ───────────────────────────
FACTOR_RENDIMIENTO = {
    'lider'    : 1.15,  # Está liderando su grupo → +15%
    'segundo'  : 1.00,  # En zona de clasificación → sin cambio
    'tercero'  : 0.75,  # En zona de riesgo → -25%
    'peligro'  : 0.50,  # Puede quedar eliminado → -50%
    'eliminado': 0.05,  # Prácticamente eliminado → -95%
}

# Ajustes adicionales por rendimiento específico
AJUSTES_EXTRA = {
    'Alemania'    : 1.25,  # 9 goles en 2 partidos, dominante
    'EE. UU.'     : 1.20,  # Líder con 6-1 en marcador global
    'México'      : 1.15,  # 6 pts, 3-0 en goles
    'Francia'     : 1.10,  # 6 pts, líder cómodo
    'Argentina'   : 1.10,  # 6 pts con Messi en racha
    'España'      : 1.05,  # 4 pts, sin goles en contra
    'Brasil'      : 1.00,  # 4 pts, sólido
    'Bélgica'     : 0.85,  # Solo 2 pts, underperforming
    'Portugal'    : 0.90,  # Solo 1 pt, empató con Congo
    'Catar'       : 0.02,  # Prácticamente eliminado (-7 DG)
    'Haití'       : 0.02,  # Prácticamente eliminado
    'Túnez'       : 0.02,  # Prácticamente eliminado (-8 DG)
    'Turquía'     : 0.02,  # Prácticamente eliminado (-5 DG)
    'Irak'        : 0.02,  # Prácticamente eliminado
    'Jordania'    : 0.02,  # Prácticamente eliminado (-5 DG)
}

def main():
    print("\n🔄 ACTUALIZANDO MONTE CARLO CON RESULTADOS REALES")
    print("="*55)

    csv = os.path.join(RAIZ, 'Predicciones', 'probabilidades_montecarlo.csv')
    if not os.path.exists(csv):
        print(f"❌ No se encontró: {csv}")
        return

    df = pd.read_csv(csv, index_col=0)
    print(f"✅ Equipos en Monte Carlo: {len(df)}")

    # Aplicar ajustes
    df_adj = df.copy()
    ajustes_log = []

    for equipo in df.index:
        estado_info = ESTADO_REAL.get(equipo, {})
        estado      = estado_info.get('estado', 'segundo')
        factor_est  = FACTOR_RENDIMIENTO.get(estado, 1.0)
        factor_ext  = AJUSTES_EXTRA.get(equipo, 1.0)
        factor_tot  = factor_est * factor_ext

        camp_orig = float(df.loc[equipo, 'Campeon'])
        camp_adj  = round(camp_orig * factor_tot, 2)

        df_adj.loc[equipo, 'Campeon']  = camp_adj
        df_adj.loc[equipo, 'Final']    = round(float(df.loc[equipo,'Final'])  * min(factor_tot,1.3), 2)
        df_adj.loc[equipo, 'Semis']    = round(float(df.loc[equipo,'Semis'])  * min(factor_tot,1.2), 2)
        df_adj.loc[equipo, 'Octavos']  = round(float(df.loc[equipo,'Octavos'])* min(factor_tot,1.1), 2)

        if abs(factor_tot - 1.0) > 0.05:
            ajustes_log.append((equipo, camp_orig, camp_adj, estado, factor_tot))

    # Normalizar para que sumen ~100%
    total = df_adj['Campeon'].sum()
    if total > 0:
        df_adj['Campeon'] = (df_adj['Campeon'] / total * 100).round(2)

    # Ordenar por campeón descendente
    df_adj = df_adj.sort_values('Campeon', ascending=False)

    # Guardar
    df_adj.to_csv(csv, encoding='utf-8-sig')
    print(f"✅ Monte Carlo actualizado y guardado")

    # Mostrar top 15
    print(f"\n🏆 RANKING ACTUALIZADO — Top 15 (con resultados reales):")
    print(f"{'#':>3} {'Selección':<20} {'Campeón':>8} {'Final':>7} {'Semis':>7} {'Estado':>12}")
    print("-"*60)
    for i, (eq, row) in enumerate(df_adj.head(15).iterrows(), 1):
        est = ESTADO_REAL.get(eq, {}).get('estado', '?')
        pts = ESTADO_REAL.get(eq, {}).get('pts', '?')
        emoji = {'lider':'🟢','segundo':'🟡','peligro':'🟠','eliminado':'🔴','tercero':'⚠️'}.get(est,'⚪')
        print(f"{i:>3} {eq:<20} {row['Campeon']:>7.1f}% {row['Final']:>6.1f}% {row['Semis']:>6.1f}% {emoji} {est} ({pts}pts)")

    # Mostrar ajustes realizados
    print(f"\n📊 PRINCIPALES AJUSTES REALIZADOS:")
    ajustes_log.sort(key=lambda x: abs(x[4]-1.0), reverse=True)
    for eq, orig, adj, est, fac in ajustes_log[:10]:
        direccion = '📈' if fac > 1 else '📉'
        print(f"   {direccion} {eq:<20}: {orig:.1f}% → {adj:.1f}% ({fac:.2f}x) [{est}]")

if __name__ == '__main__':
    main()