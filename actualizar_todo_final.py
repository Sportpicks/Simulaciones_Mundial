# -*- coding: utf-8 -*-
"""
actualizar_todo_final.py
Pipeline COMPLETO y FINAL del modelo Mundial 2026.
Un solo comando hace todo.

Pipeline:
  PASO 1  — Resultados reales del Mundial (football-data.org)
  PASO 1b — Corrige fechas hora Perú + nombres equipos
  PASO 2  — Re-entrena modelo XGBoost
  PASO 3  — Genera informe
  PASO 4  — Cuotas de 25 casas de apuestas
  PASO 5  — Mejoras base (Dixon-Coles + Valor Mercado)
  PASO 5b — Sincroniza fechas Perú en predicciones
  PASO 5c — Stats por equipo
  PASO 6  — Mejoras avanzadas (Decaimiento + EV + Forma)
  PASO 7  — Genera web final v6 con mercados razonados
  PASO 8  — Push automático a GitHub

Uso: python actualizar_todo_final.py
"""

import os, sys, time, subprocess, pandas as pd
from datetime import datetime, timezone, date

RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)

VERDE   = '\033[92m'; ROJO  = '\033[91m'
AMARILLO= '\033[93m'; AZUL  = '\033[94m'
RESET   = '\033[0m';  NEG   = '\033[1m'

def ok(m):   print(f"  {VERDE}✅ {m}{RESET}")
def err(m):  print(f"  {ROJO}❌ {m}{RESET}")
def info(m): print(f"  {AZUL}ℹ️  {m}{RESET}")
def warn(m): print(f"  {AMARILLO}⚠️  {m}{RESET}")
def titulo(n, m):
    print(f"\n{NEG}{'='*60}{RESET}")
    print(f"{NEG}  PASO {n} — {m}{RESET}")
    print(f"{NEG}{'='*60}{RESET}")

def ejecutar(cmd, desc, timeout=1800):
    info(f"Ejecutando: {cmd}")
    t = time.time()
    try:
        r = subprocess.run(cmd, shell=True, timeout=timeout)
        d = round(time.time()-t, 1)
        if r.returncode == 0:
            ok(f"{desc} ({d}s)")
            return True
        err(f"{desc} falló (código {r.returncode})")
        return False
    except subprocess.TimeoutExpired:
        err(f"{desc} timeout ({timeout}s)")
        return False
    except Exception as e:
        err(f"{desc}: {e}")
        return False

def verificar():
    scripts = [
        ('actualizar_resultados_mundial.py', 'Resultados API'),
        ('corregir_fechas_peru.py',          'Fechas Perú'),
        ('actualizar_fechas_peru.py',        'Fechas predicciones'),
        ('04_Prediccion/prediccion_mundial.py','Modelo XGBoost'),
        ('04_Prediccion/generar_informe.py', 'Informe'),
        ('integrar_cuotas_v3.py',            'Cuotas API'),
        ('mejorar_modelo.py',                'Mejoras base'),
        ('stats_por_equipo.py',              'Stats equipo'),
        ('mejoras_avanzadas.py',             'Mejoras avanzadas'),
        ('razonador_mercados.py',            'Razonador mercados'),
        ('generar_web_v6.py',               'Web v6'),
    ]
    todos = True
    for f, n in scripts:
        if os.path.exists(os.path.join(RAIZ, f)):
            ok(f"Encontrado: {n}")
        else:
            err(f"Falta: {f}")
            todos = False
    return todos

def corregir_nombres():
    csv = os.path.join(RAIZ, 'Data', 'partidos_mundial.csv')
    if not os.path.exists(csv): return
    try:
        df = pd.read_csv(csv)
        fixes = {'Congo DR':'RD Congo','Cape Verde Islands':'Cabo Verde',
                 'Curaçao':'Curazao','USA':'EE. UU.'}
        for col in ['Equipo_Local','Equipo_Visitante']:
            if col in df.columns:
                for v, n in fixes.items():
                    df[col] = df[col].str.replace(v, n, regex=False)
        df.to_csv(csv, index=False, encoding='utf-8-sig')
        ok("Nombres corregidos")
    except Exception as e:
        warn(f"Error nombres: {e}")

def sincronizar_fechas():
    csv_m = os.path.join(RAIZ, 'Data', 'partidos_mundial.csv')
    csv_p = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
    if not os.path.exists(csv_m) or not os.path.exists(csv_p): return
    try:
        dm = pd.read_csv(csv_m)
        dp = pd.read_csv(csv_p)
        mapa = {(r['Equipo_Local'],r['Equipo_Visitante']):r['Fecha'] for _,r in dm.iterrows()}
        n = 0
        for i,r in dp.iterrows():
            k = (r['Local'],r['Visitante'])
            if k in mapa:
                dp.at[i,'Fecha'] = mapa[k]; n += 1
        dp.to_csv(csv_p, index=False, encoding='utf-8-sig')
        ok(f"Fechas sincronizadas: {n} partidos")
    except Exception as e:
        warn(f"Error fechas: {e}")

def mostrar_resumen_dia():
    try:
        csv = os.path.join(RAIZ, 'Data', 'resultados_mundial.csv')
        if not os.path.exists(csv): return
        df  = pd.read_csv(csv)
        hoy = date.today().strftime('%Y-%m-%d')
        jug = df[(df['Fecha']==hoy) & (df['Estado']=='FINISHED')]
        if len(jug):
            print(f"\n  {VERDE}⚽ Resultados de hoy:{RESET}")
            for _, r in jug.iterrows():
                print(f"     {r['Local']} {r['Marcador']} {r['Visitante']}")
        prox = df[df['Estado']!='FINISHED'].head(4)
        if len(prox):
            print(f"\n  {AZUL}📅 Próximos partidos:{RESET}")
            for _, r in prox.iterrows():
                print(f"     {r['Fecha']} — {r['Local']} vs {r['Visitante']}")
    except: pass

def mostrar_ev_hoy():
    try:
        csv = os.path.join(RAIZ, 'Predicciones', 'ev_tracking.csv')
        if not os.path.exists(csv): return
        df  = pd.read_csv(csv)
        hoy = date.today().strftime('%Y-%m-%d')
        val = df[(df['Fecha']==hoy) & (df['EV_Categoria'].isin(['alto','medio','leve']))]
        if len(val):
            print(f"\n  {VERDE}💰 Partidos con VALUE hoy:{RESET}")
            for _, r in val.iterrows():
                print(f"     {r['EV_Etiqueta']} {r['Local']} vs {r['Visitante']}")
                print(f"     Resultado {r['Mejor_resultado']} | EV: {r['Mejor_EV']:+.3f}")
    except: pass

def mostrar_mejores_apuestas():
    try:
        csv = os.path.join(RAIZ, 'Predicciones', 'predicciones_finales.csv')
        if not os.path.exists(csv): return
        df  = pd.read_csv(csv)
        hoy = date.today().strftime('%Y-%m-%d')
        hoy_df = df[df['Fecha']==hoy]
        if not len(hoy_df): return
        print(f"\n  {VERDE}🏆 Mejores apuestas de hoy:{RESET}")
        for _, r in hoy_df.iterrows():
            p1 = float(r['Prob_1_Final'])
            px = float(r['Prob_X_Final'])
            p2 = float(r['Prob_2_Final'])
            tend_l = r.get('Tendencia_Local','?')
            tend_v = r.get('Tendencia_Visitante','?')
            candidatos = []
            if p1+px > 75: candidatos.append((p1+px, '1X (local o empate)'))
            if px+p2 > 75: candidatos.append((px+p2, 'X2 (empate o visitante)'))
            if p1 > 65:    candidatos.append((p1, f'Victoria {r["Local"]}'))
            if p2 > 65:    candidatos.append((p2, f'Victoria {r["Visitante"]}'))
            if candidatos:
                mejor = max(candidatos, key=lambda x: x[0])
                emoji = '🟢' if mejor[0]>=80 else '🟡'
                print(f"     {emoji} {r['Local']} ({tend_l}) vs {r['Visitante']} ({tend_v}): {mejor[1]} ({mejor[0]:.1f}%)")
    except: pass

def push_github():
    titulo("8", "Push automático a GitHub")
    fecha = datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')
    archivos = [
        'docs/index_final.html', 'docs/picks.json',
        'Data/resultados_mundial.csv', 'Data/partidos_mundial.csv',
        'Data/forma_equipos.json',
        'Predicciones/predicciones_finales.csv',
        'Predicciones/probabilidades_montecarlo.csv',
        'Predicciones/predicciones_eliminatorias.csv',
        'Predicciones/clasificacion_grupos.csv',
        'Predicciones/PREDICCIONES.md',
        'Predicciones/ev_tracking.csv',
    ]
    existentes = [f for f in archivos if os.path.exists(os.path.join(RAIZ,f))]
    info(f"Archivos a subir: {len(existentes)}")

    subprocess.run(f'git add {" ".join(existentes)}', shell=True,
                   capture_output=True, text=True)

    rs = subprocess.run('git status --porcelain', shell=True,
                        capture_output=True, text=True)
    if not rs.stdout.strip():
        warn("Sin cambios nuevos")
        return True

    rc = subprocess.run(f'git commit -m "Actualización automática {fecha}"',
                        shell=True, capture_output=True, text=True)
    if rc.returncode != 0:
        err(f"Commit falló: {rc.stderr}")
        return False
    ok(f"Commit: {fecha}")

    rp = subprocess.run('git push origin main', shell=True,
                        capture_output=True, text=True)
    if rp.returncode != 0:
        err(f"Push falló: {rp.stderr}")
        warn("Verifica que el token de GitHub no haya expirado")
        return False

    ok("Push exitoso — web pública actualizada en ~2 minutos")
    return True

def main():
    inicio = time.time()
    fecha  = datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')

    print(f"\n{NEG}{'='*60}{RESET}")
    print(f"{NEG}  🚀 PIPELINE FINAL — MUNDIAL 2026{RESET}")
    print(f"{NEG}  📅 {fecha}{RESET}")
    print(f"{NEG}{'='*60}{RESET}")

    titulo("0", "Verificando archivos")
    if not verificar():
        err("Faltan archivos — abortando")
        sys.exit(1)

    res = {}

    # PASO 1
    titulo("1", "Resultados reales del Mundial")
    res['resultados'] = ejecutar('python actualizar_resultados_mundial.py',
                                  'Resultados', timeout=60)
    if res['resultados']: mostrar_resumen_dia()

    # PASO 1b
    titulo("1b", "Fechas hora Perú + nombres equipos")
    ejecutar('python corregir_fechas_peru.py', 'Fechas Perú', timeout=30)
    corregir_nombres()

    # PASO 2
    titulo("2", "Re-entrenando modelo XGBoost")
    warn("Puede tardar 5-15 minutos...")
    res['modelo'] = ejecutar('python 04_Prediccion/prediccion_mundial.py',
                              'XGBoost', timeout=1800)
    if not res['modelo']:
        err("Modelo falló — abortando")
        sys.exit(1)

    # PASO 3
    titulo("3", "Generando informe")
    res['informe'] = ejecutar('python 04_Prediccion/generar_informe.py',
                               'Informe', timeout=120)

    # PASO 4
    titulo("4", "Cuotas de 25 casas de apuestas")
    res['cuotas'] = ejecutar('python integrar_cuotas_v3.py', 'Cuotas', timeout=120)
    if not res['cuotas']: warn("Sin cuotas — usando solo modelo")

    # PASO 5
    titulo("5", "Dixon-Coles + Valor de Mercado")
    res['mejoras'] = ejecutar('python mejorar_modelo.py', 'Mejoras base', timeout=120)

    # PASO 5b
    titulo("5b", "Sincronizando fechas hora Perú")
    sincronizar_fechas()

    # PASO 5c
    titulo("5c", "Stats por equipo")
    ejecutar('python stats_por_equipo.py', 'Stats equipo', timeout=30)

    # PASO 6
    titulo("6", "Mejoras avanzadas: Decaimiento + EV + Forma")
    res['avanzadas'] = ejecutar('python mejoras_avanzadas.py',
                                 'Mejoras avanzadas', timeout=60)
    if res['avanzadas']:
        mostrar_ev_hoy()
        mostrar_mejores_apuestas()
        
        ejecutar('python calibrar_empates.py', 'Calibracion empates', timeout=60)
        ejecutar('python calibracion_selectiva.py', 'Calibracion selectiva', timeout=30)

    # PASO 7
    titulo("7", "Generando web final v6")
    res['web'] = ejecutar('python generar_web_v6.py', 'Web v6', timeout=120)
    ejecutar('python generar_panel_picks.py', 'Panel picks del dia', timeout=60)

    # PASO 8
    res['github'] = push_github()

    # Resumen
    dur = round(time.time()-inicio, 0)
    print(f"\n{NEG}{'='*60}{RESET}")
    print(f"{NEG}  📊 RESUMEN{RESET}")
    print(f"{NEG}{'='*60}{RESET}")

    pasos = [
        ('resultados','⚽ Resultados Mundial'),
        ('modelo',    '🤖 Modelo XGBoost'),
        ('informe',   '📄 Informe'),
        ('cuotas',    '📈 Cuotas 25 casas'),
        ('mejoras',   '📐 Dixon-Coles + Mercado'),
        ('avanzadas', '🧠 Decaimiento + EV + Forma'),
        ('web',       '🌍 Web final v6'),
        ('github',    '🚀 GitHub'),
    ]
    for k, n in pasos:
        s = f"{VERDE}✅{RESET}" if res.get(k) else f"{ROJO}❌{RESET}"
        print(f"  {s} {n}")

    print(f"\n  ⏱️  Tiempo total: {int(dur//60)}m {int(dur%60)}s")
    print(f"  📅 {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')}")

    if res.get('web') and res.get('github'):
        print(f"\n  {VERDE}{NEG}🎉 Web pública actualizada:{RESET}")
        print(f"  {AZUL}https://sportpicks.github.io/Simulaciones_Mundial/index_final.html{RESET}")
        print(f"  {AZUL}https://sportpicks.github.io/Simulaciones_Mundial/picks_publicos_v2.html{RESET}")
        os.system(f'start "" "{os.path.join(RAIZ,"docs","index_final.html")}"')

    print(f"\n{NEG}{'='*60}{RESET}\n")

if __name__ == '__main__':
    main()
