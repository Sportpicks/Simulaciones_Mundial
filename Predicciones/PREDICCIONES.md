# 🏆 Predicción completa del Mundial 2026 — los 104 partidos

Generado con el modelo de este repositorio: regresores XGBoost (Tweedie) de goles + clasificador 1X2 XGBoost calibrado (isotónico), predicción a sede neutral con "efecto espejo", temperatura `T=0.27` en grupos y `T=0.5` en eliminatorias, y simulación de **Monte Carlo de 10.000 mundiales** para las probabilidades por selección.

> ⚠️ Predicción generada el 12-jun-2026, con los datos del repo (anteriores al torneo). La asignación de mejores terceros al cuadro usa la simplificación del notebook (ranking 1º-8º a huecos fijos), no la tabla oficial de la FIFA.

## Resumen

| | |
|---|---|
| 🥇 **Campeón predicho** | **🇫🇷 Francia** |
| 🥈 Subcampeón | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra |
| 🥉 Tercer puesto | 🇪🇸 España |

### Probabilidades de ser campeón (Top 10, Monte Carlo)

| # | Selección | Campeón | Final | Semis | Cuartos |
|---|---|---|---|---|---|
| 1 | 🇫🇷 Francia | **17.4%** | 26.4% | 39.6% | 53.2% |
| 2 | 🇧🇪 Bélgica | **11.6%** | 19.6% | 33.3% | 53.8% |
| 3 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra | **11.2%** | 19.8% | 31.6% | 48.9% |
| 4 | 🇪🇸 España | **9.8%** | 16.4% | 27.2% | 41.2% |
| 5 | 🇩🇪 Alemania | **8.9%** | 15.1% | 24.8% | 36.9% |
| 6 | 🇦🇷 Argentina | **6.8%** | 14.0% | 25.4% | 39.8% |
| 7 | 🇵🇹 Portugal | **6.1%** | 12.4% | 23.1% | 39.8% |
| 8 | 🇳🇱 Países Bajos | **3.8%** | 8.1% | 17.0% | 36.0% |
| 9 | 🇧🇷 Brasil | **3.8%** | 8.4% | 16.5% | 32.8% |
| 10 | 🇭🇷 Croacia | **3.3%** | 7.4% | 16.2% | 30.9% |

## Fase de grupos — 72 partidos

Marcador = marcador exacto más probable según los goles esperados del modelo, condicionado al resultado 1X2 más probable.

### Grupo A

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-11 | 🇲🇽 México – 🇿🇦 Sudáfrica | **1-0** | 47% | 34% | 19% |
| 06-12 | 🇰🇷 Corea del Sur – 🇨🇿 República Checa | **2-1** | 41% | 32% | 28% |
| 06-18 | 🇨🇿 República Checa – 🇿🇦 Sudáfrica | **1-0** | 36% | 33% | 32% |
| 06-19 | 🇲🇽 México – 🇰🇷 Corea del Sur | **1-1** | 36% | 37% | 27% |
| 06-25 | 🇨🇿 República Checa – 🇲🇽 México | **1-2** | 25% | 31% | 44% |
| 06-25 | 🇿🇦 Sudáfrica – 🇰🇷 Corea del Sur | **0-1** | 25% | 34% | 41% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇲🇽 México ✅ | 7 | +1.33 |
| 2 | 🇰🇷 Corea del Sur ✅ | 7 | +0.37 |
| 3 | 🇨🇿 República Checa 🟡 | 3 | -0.77 |
| 4 | 🇿🇦 Sudáfrica | 0 | -0.93 |

### Grupo B

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-12 | 🇨🇦 Canadá – 🇧🇦 Bosnia-Herzegovina | **1-0** | 40% | 31% | 29% |
| 06-13 | 🇶🇦 Catar – 🇨🇭 Suiza | **1-2** | 18% | 27% | 54% |
| 06-18 | 🇨🇭 Suiza – 🇧🇦 Bosnia-Herzegovina | **2-1** | 43% | 30% | 27% |
| 06-18 | 🇨🇦 Canadá – 🇶🇦 Catar | **1-0** | 47% | 30% | 23% |
| 06-24 | 🇨🇭 Suiza – 🇨🇦 Canadá | **2-1** | 41% | 31% | 28% |
| 06-24 | 🇧🇦 Bosnia-Herzegovina – 🇶🇦 Catar | **1-0** | 35% | 33% | 32% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇨🇭 Suiza ✅ | 9 | +2.06 |
| 2 | 🇨🇦 Canadá ✅ | 6 | +0.05 |
| 3 | 🇧🇦 Bosnia-Herzegovina 🟡 | 3 | -0.50 |
| 4 | 🇶🇦 Catar | 0 | -1.61 |

### Grupo C

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-13 | 🇧🇷 Brasil – 🇲🇦 Marruecos | **2-1** | 48% | 31% | 21% |
| 06-14 | 🇭🇹 Haití – 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escocia | **0-2** | 20% | 29% | 51% |
| 06-19 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escocia – 🇲🇦 Marruecos | **1-2** | 21% | 33% | 46% |
| 06-20 | 🇧🇷 Brasil – 🇭🇹 Haití | **3-0** | 69% | 19% | 12% |
| 06-24 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escocia – 🇧🇷 Brasil | **0-2** | 15% | 30% | 55% |
| 06-24 | 🇲🇦 Marruecos – 🇭🇹 Haití | **2-0** | 63% | 24% | 13% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇧🇷 Brasil ✅ | 9 | +3.70 |
| 2 | 🇲🇦 Marruecos ✅ | 6 | +1.55 |
| 3 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escocia 🟡 | 3 | -0.72 |
| 4 | 🇭🇹 Haití | 0 | -4.53 |

### Grupo D

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-13 | 🇺🇸 EE. UU. – 🇵🇾 Paraguay | **1-0** | 43% | 29% | 27% |
| 06-14 | 🇦🇺 Australia – 🇹🇷 Turquía | **1-2** | 32% | 30% | 38% |
| 06-19 | 🇺🇸 EE. UU. – 🇦🇺 Australia | **1-0** | 35% | 32% | 33% |
| 06-20 | 🇹🇷 Turquía – 🇵🇾 Paraguay | **1-0** | 44% | 31% | 26% |
| 06-26 | 🇹🇷 Turquía – 🇺🇸 EE. UU. | **1-1** | 33% | 34% | 34% |
| 06-26 | 🇵🇾 Paraguay – 🇦🇺 Australia | **0-1** | 26% | 32% | 41% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇹🇷 Turquía ✅ | 7 | +1.27 |
| 2 | 🇺🇸 EE. UU. ✅ | 7 | +0.83 |
| 3 | 🇦🇺 Australia 🟡 | 3 | -0.59 |
| 4 | 🇵🇾 Paraguay | 0 | -1.51 |

### Grupo E

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-14 | 🇩🇪 Alemania – 🇨🇼 Curazao | **3-0** | 71% | 21% | 8% |
| 06-14 | 🇨🇮 Costa de Marfil – 🇪🇨 Ecuador | **1-0** | 42% | 34% | 24% |
| 06-20 | 🇩🇪 Alemania – 🇨🇮 Costa de Marfil | **2-1** | 45% | 38% | 18% |
| 06-21 | 🇪🇨 Ecuador – 🇨🇼 Curazao | **2-0** | 50% | 30% | 20% |
| 06-25 | 🇨🇼 Curazao – 🇨🇮 Costa de Marfil | **0-2** | 12% | 29% | 59% |
| 06-25 | 🇪🇨 Ecuador – 🇩🇪 Alemania | **0-2** | 12% | 33% | 55% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇩🇪 Alemania ✅ | 9 | +3.60 |
| 2 | 🇨🇮 Costa de Marfil ✅ | 6 | +1.27 |
| 3 | 🇪🇨 Ecuador 🟡 | 3 | -0.86 |
| 4 | 🇨🇼 Curazao | 0 | -4.01 |

### Grupo F

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-14 | 🇳🇱 Países Bajos – 🇯🇵 Japón | **1-0** | 38% | 34% | 28% |
| 06-15 | 🇸🇪 Suecia – 🇹🇳 Túnez | **1-0** | 36% | 31% | 33% |
| 06-20 | 🇳🇱 Países Bajos – 🇸🇪 Suecia | **2-1** | 52% | 30% | 18% |
| 06-21 | 🇹🇳 Túnez – 🇯🇵 Japón | **0-1** | 20% | 33% | 46% |
| 06-25 | 🇯🇵 Japón – 🇸🇪 Suecia | **2-1** | 43% | 34% | 23% |
| 06-25 | 🇹🇳 Túnez – 🇳🇱 Países Bajos | **0-2** | 18% | 29% | 54% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇳🇱 Países Bajos ✅ | 9 | +1.93 |
| 2 | 🇯🇵 Japón ✅ | 6 | +0.13 |
| 3 | 🇸🇪 Suecia 🟡 | 3 | -0.88 |
| 4 | 🇹🇳 Túnez | 0 | -1.18 |

### Grupo G

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-15 | 🇧🇪 Bélgica – 🇪🇬 Egipto | **2-0** | 58% | 28% | 13% |
| 06-16 | 🇮🇷 Irán – 🇳🇿 Nueva Zelanda | **2-0** | 52% | 32% | 15% |
| 06-21 | 🇧🇪 Bélgica – 🇮🇷 Irán | **2-0** | 47% | 33% | 20% |
| 06-22 | 🇳🇿 Nueva Zelanda – 🇪🇬 Egipto | **0-1** | 20% | 31% | 49% |
| 06-27 | 🇳🇿 Nueva Zelanda – 🇧🇪 Bélgica | **0-3** | 14% | 23% | 63% |
| 06-27 | 🇪🇬 Egipto – 🇮🇷 Irán | **0-1** | 20% | 34% | 46% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇧🇪 Bélgica ✅ | 9 | +4.32 |
| 2 | 🇮🇷 Irán ✅ | 6 | +0.71 |
| 3 | 🇪🇬 Egipto 🟡 | 3 | -0.99 |
| 4 | 🇳🇿 Nueva Zelanda | 0 | -4.04 |

### Grupo H

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-15 | 🇪🇸 España – 🇨🇻 Cabo Verde | **2-0** | 54% | 29% | 16% |
| 06-15 | 🇸🇦 Arabia Saudí – 🇺🇾 Uruguay | **0-2** | 10% | 24% | 66% |
| 06-21 | 🇺🇾 Uruguay – 🇨🇻 Cabo Verde | **1-0** | 45% | 31% | 24% |
| 06-21 | 🇪🇸 España – 🇸🇦 Arabia Saudí | **3-0** | 68% | 25% | 7% |
| 06-27 | 🇺🇾 Uruguay – 🇪🇸 España | **1-2** | 17% | 36% | 46% |
| 06-27 | 🇨🇻 Cabo Verde – 🇸🇦 Arabia Saudí | **1-0** | 42% | 30% | 28% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇪🇸 España ✅ | 9 | +3.94 |
| 2 | 🇺🇾 Uruguay ✅ | 6 | +1.08 |
| 3 | 🇨🇻 Cabo Verde 🟡 | 3 | -1.62 |
| 4 | 🇸🇦 Arabia Saudí | 0 | -3.40 |

### Grupo I

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-16 | 🇮🇶 Irak – 🇳🇴 Noruega | **0-2** | 16% | 31% | 53% |
| 06-16 | 🇫🇷 Francia – 🇸🇳 Senegal | **2-1** | 48% | 33% | 19% |
| 06-22 | 🇫🇷 Francia – 🇮🇶 Irak | **3-0** | 73% | 20% | 7% |
| 06-23 | 🇳🇴 Noruega – 🇸🇳 Senegal | **1-2** | 28% | 34% | 38% |
| 06-26 | 🇳🇴 Noruega – 🇫🇷 Francia | **0-2** | 15% | 28% | 57% |
| 06-26 | 🇸🇳 Senegal – 🇮🇶 Irak | **2-0** | 58% | 27% | 15% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇫🇷 Francia ✅ | 9 | +3.99 |
| 2 | 🇸🇳 Senegal ✅ | 6 | +1.39 |
| 3 | 🇳🇴 Noruega 🟡 | 3 | -1.08 |
| 4 | 🇮🇶 Irak | 0 | -4.30 |

### Grupo J

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-17 | 🇦🇷 Argentina – 🇩🇿 Argelia | **1-0** | 48% | 32% | 20% |
| 06-17 | 🇦🇹 Austria – 🇯🇴 Jordania | **2-0** | 73% | 20% | 6% |
| 06-22 | 🇦🇷 Argentina – 🇦🇹 Austria | **2-1** | 39% | 37% | 24% |
| 06-23 | 🇯🇴 Jordania – 🇩🇿 Argelia | **0-2** | 16% | 24% | 60% |
| 06-28 | 🇩🇿 Argelia – 🇦🇹 Austria | **0-1** | 29% | 32% | 39% |
| 06-28 | 🇯🇴 Jordania – 🇦🇷 Argentina | **0-3** | 7% | 14% | 79% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇦🇷 Argentina ✅ | 9 | +3.17 |
| 2 | 🇦🇹 Austria ✅ | 6 | +1.12 |
| 3 | 🇩🇿 Argelia 🟡 | 3 | +0.52 |
| 4 | 🇯🇴 Jordania | 0 | -4.81 |

### Grupo K

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-17 | 🇵🇹 Portugal – 🇨🇩 RD Congo | **2-0** | 55% | 29% | 16% |
| 06-18 | 🇺🇿 Uzbekistán – 🇨🇴 Colombia | **0-2** | 17% | 25% | 58% |
| 06-23 | 🇵🇹 Portugal – 🇺🇿 Uzbekistán | **3-0** | 59% | 27% | 14% |
| 06-24 | 🇨🇴 Colombia – 🇨🇩 RD Congo | **1-0** | 48% | 32% | 20% |
| 06-27 | 🇨🇴 Colombia – 🇵🇹 Portugal | **1-2** | 21% | 34% | 45% |
| 06-27 | 🇨🇩 RD Congo – 🇺🇿 Uzbekistán | **1-0** | 41% | 30% | 29% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🇵🇹 Portugal ✅ | 9 | +3.54 |
| 2 | 🇨🇴 Colombia ✅ | 6 | +0.96 |
| 3 | 🇨🇩 RD Congo 🟡 | 3 | -1.46 |
| 4 | 🇺🇿 Uzbekistán | 0 | -3.04 |

### Grupo L

| Fecha | Partido | Pred. | P(1) | P(X) | P(2) |
|---|---|:-:|--:|--:|--:|
| 06-17 | 🇬🇭 Ghana – 🇵🇦 Panamá | **0-1** | 31% | 29% | 39% |
| 06-17 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra – 🇭🇷 Croacia | **1-1** | 38% | 41% | 21% |
| 06-23 | 🇵🇦 Panamá – 🇭🇷 Croacia | **0-2** | 13% | 27% | 60% |
| 06-23 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra – 🇬🇭 Ghana | **3-0** | 68% | 20% | 12% |
| 06-27 | 🇵🇦 Panamá – 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra | **0-2** | 12% | 27% | 61% |
| 06-27 | 🇭🇷 Croacia – 🇬🇭 Ghana | **2-0** | 58% | 28% | 14% |

| Pos | Equipo | Pts | DG (xG) |
|---|---|--:|--:|
| 1 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra ✅ | 7 | +3.59 |
| 2 | 🇭🇷 Croacia ✅ | 7 | +2.06 |
| 3 | 🇵🇦 Panamá 🟡 | 3 | -2.94 |
| 4 | 🇬🇭 Ghana | 0 | -2.71 |

✅ clasificado directo · 🟡 tercero (pasan los 8 mejores)

## Eliminatorias — 32 partidos

Si el empate es el resultado más probable, el cruce se decide por penaltis a favor del equipo con mayor probabilidad de victoria.

### Dieciseisavos de final (16 cruces) · *28 jun - 3 jul*

| Cruce | Pred. | Avanza | P(1) | P(X) | P(2) |
|---|:-:|---|--:|--:|--:|
| 🇩🇪 Alemania – 🇩🇿 Argelia | **2-0** | **🇩🇪 Alemania** | 54% | 30% | 16% |
| 🇫🇷 Francia – 🇧🇦 Bosnia-Herzegovina | **3-0** | **🇫🇷 Francia** | 61% | 27% | 12% |
| 🇰🇷 Corea del Sur – 🇨🇦 Canadá | **1-0** | **🇰🇷 Corea del Sur** | 39% | 33% | 28% |
| 🇳🇱 Países Bajos – 🇲🇦 Marruecos | **2-1** | **🇳🇱 Países Bajos** | 48% | 30% | 21% |
| 🇨🇴 Colombia – 🇭🇷 Croacia | **1-2** | **🇭🇷 Croacia** | 22% | 35% | 44% |
| 🇪🇸 España – 🇦🇹 Austria | **2-1** | **🇪🇸 España** | 38% | 38% | 24% |
| 🇹🇷 Turquía – 🇦🇺 Australia | **2-1** | **🇹🇷 Turquía** | 38% | 30% | 32% |
| 🇧🇪 Bélgica – 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escocia | **2-0** | **🇧🇪 Bélgica** | 60% | 27% | 12% |
| 🇧🇷 Brasil – 🇯🇵 Japón | **1-0** | **🇧🇷 Brasil** | 41% | 35% | 24% |
| 🇨🇮 Costa de Marfil – 🇸🇳 Senegal | **0-1** | **🇸🇳 Senegal** | 29% | 34% | 37% |
| 🇲🇽 México – 🇨🇿 República Checa | **2-1** | **🇲🇽 México** | 44% | 31% | 25% |
| 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra – 🇪🇨 Ecuador | **2-0** | **🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra** | 56% | 30% | 14% |
| 🇦🇷 Argentina – 🇺🇾 Uruguay | **1-0** | **🇦🇷 Argentina** | 46% | 34% | 20% |
| 🇺🇸 EE. UU. – 🇮🇷 Irán | **0-1** | **🇮🇷 Irán** | 24% | 36% | 41% |
| 🇨🇭 Suiza – 🇸🇪 Suecia | **2-1** | **🇨🇭 Suiza** | 41% | 30% | 29% |
| 🇵🇹 Portugal – 🇪🇬 Egipto | **2-0** | **🇵🇹 Portugal** | 55% | 29% | 16% |

### Octavos de final · *4 - 7 jul*

| Cruce | Pred. | Avanza | P(1) | P(X) | P(2) |
|---|:-:|---|--:|--:|--:|
| 🇩🇪 Alemania – 🇫🇷 Francia | **1-1 (pen)** | **🇫🇷 Francia** | 23% | 38% | 38% |
| 🇰🇷 Corea del Sur – 🇳🇱 Países Bajos | **1-2** | **🇳🇱 Países Bajos** | 20% | 32% | 48% |
| 🇭🇷 Croacia – 🇪🇸 España | **1-1 (pen)** | **🇪🇸 España** | 20% | 42% | 38% |
| 🇹🇷 Turquía – 🇧🇪 Bélgica | **1-2** | **🇧🇪 Bélgica** | 18% | 27% | 56% |
| 🇧🇷 Brasil – 🇸🇳 Senegal | **2-1** | **🇧🇷 Brasil** | 38% | 31% | 30% |
| 🇲🇽 México – 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra | **1-2** | **🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra** | 19% | 33% | 48% |
| 🇦🇷 Argentina – 🇮🇷 Irán | **2-0** | **🇦🇷 Argentina** | 44% | 33% | 23% |
| 🇨🇭 Suiza – 🇵🇹 Portugal | **1-2** | **🇵🇹 Portugal** | 21% | 35% | 43% |

### Cuartos de final · *9 - 11 jul*

| Cruce | Pred. | Avanza | P(1) | P(X) | P(2) |
|---|:-:|---|--:|--:|--:|
| 🇫🇷 Francia – 🇳🇱 Países Bajos | **2-1** | **🇫🇷 Francia** | 44% | 36% | 20% |
| 🇪🇸 España – 🇧🇪 Bélgica | **1-1 (pen)** | **🇪🇸 España** | 32% | 37% | 31% |
| 🇧🇷 Brasil – 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra | **1-1 (pen)** | **🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra** | 23% | 39% | 38% |
| 🇦🇷 Argentina – 🇵🇹 Portugal | **1-1 (pen)** | **🇦🇷 Argentina** | 29% | 41% | 29% |

### Semifinales · *14 - 15 jul*

| Cruce | Pred. | Avanza | P(1) | P(X) | P(2) |
|---|:-:|---|--:|--:|--:|
| 🇫🇷 Francia – 🇪🇸 España | **1-1 (pen)** | **🇫🇷 Francia** | 30% | 43% | 27% |
| 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra – 🇦🇷 Argentina | **1-1 (pen)** | **🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra** | 33% | 39% | 28% |

### Partido por el 3er puesto · *18 jul*

| Cruce | Pred. | Avanza | P(1) | P(X) | P(2) |
|---|:-:|---|--:|--:|--:|
| 🇪🇸 España – 🇦🇷 Argentina | **1-1 (pen)** | **🇪🇸 España** | 30% | 44% | 26% |

### 🏆 Gran Final — MetLife Stadium, Nueva York/Nueva Jersey · *19 jul*

| Cruce | Pred. | Avanza | P(1) | P(X) | P(2) |
|---|:-:|---|--:|--:|--:|
| 🇫🇷 Francia – 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra | **1-1 (pen)** | **🇫🇷 Francia** | 32% | 42% | 26% |

## Probabilidades por selección — 10.000 mundiales simulados

| Selección | Pasa grupos | Octavos | Cuartos | Semis | Final | 🏆 Campeón |
|---|--:|--:|--:|--:|--:|--:|
| 🇫🇷 Francia | 95.7% | 75.5% | 53.2% | 39.6% | 26.4% | **17.4%** |
| 🇧🇪 Bélgica | 94.1% | 73.8% | 53.8% | 33.3% | 19.6% | **11.6%** |
| 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra | 94.3% | 69.8% | 48.9% | 31.6% | 19.8% | **11.2%** |
| 🇪🇸 España | 94.5% | 60.1% | 41.2% | 27.2% | 16.4% | **9.8%** |
| 🇩🇪 Alemania | 95.7% | 66.4% | 36.9% | 24.8% | 15.1% | **8.9%** |
| 🇦🇷 Argentina | 95.2% | 59.6% | 39.8% | 25.4% | 14.0% | **6.8%** |
| 🇵🇹 Portugal | 92.2% | 62.8% | 39.8% | 23.1% | 12.4% | **6.1%** |
| 🇳🇱 Países Bajos | 88.3% | 56.9% | 36.0% | 17.0% | 8.1% | **3.8%** |
| 🇧🇷 Brasil | 94.5% | 58.3% | 32.8% | 16.5% | 8.4% | **3.8%** |
| 🇭🇷 Croacia | 89.2% | 57.2% | 30.9% | 16.2% | 7.4% | **3.3%** |
| 🇦🇹 Austria | 89.6% | 44.9% | 23.8% | 11.7% | 5.2% | **2.1%** |
| 🇸🇳 Senegal | 81.7% | 45.8% | 23.3% | 12.2% | 5.1% | **2.0%** |
| 🇮🇷 Irán | 81.1% | 51.3% | 26.1% | 12.6% | 5.1% | **1.7%** |
| 🇲🇽 México | 83.8% | 53.0% | 23.9% | 9.8% | 4.2% | **1.5%** |
| 🇨🇮 Costa de Marfil | 84.0% | 41.0% | 18.7% | 8.4% | 3.5% | **1.3%** |
| 🇺🇾 Uruguay | 86.3% | 37.9% | 19.0% | 8.8% | 3.6% | **1.3%** |
| 🇯🇵 Japón | 78.5% | 38.7% | 20.7% | 7.7% | 3.0% | **1.0%** |
| 🇨🇭 Suiza | 86.1% | 46.9% | 20.7% | 7.8% | 2.9% | **0.9%** |
| 🇨🇴 Colombia | 83.6% | 41.4% | 19.6% | 8.0% | 2.8% | **0.9%** |
| 🇲🇦 Marruecos | 86.1% | 37.1% | 17.6% | 5.9% | 2.1% | **0.7%** |
| 🇳🇴 Noruega | 65.5% | 28.6% | 11.0% | 4.3% | 1.5% | **0.5%** |
| 🇰🇷 Corea del Sur | 75.2% | 41.8% | 15.1% | 4.7% | 1.7% | **0.5%** |
| 🇹🇷 Turquía | 77.6% | 36.9% | 13.5% | 4.6% | 1.5% | **0.5%** |
| 🇨🇦 Canadá | 76.9% | 34.0% | 13.3% | 4.0% | 1.2% | **0.4%** |
| 🇩🇿 Argelia | 76.7% | 27.4% | 10.5% | 3.9% | 1.1% | **0.4%** |
| 🇨🇿 República Checa | 62.6% | 28.7% | 10.5% | 3.3% | 0.8% | **0.2%** |
| 🇸🇪 Suecia | 55.0% | 20.8% | 8.4% | 2.5% | 0.7% | **0.2%** |
| 🇹🇳 Túnez | 46.7% | 16.5% | 6.0% | 1.8% | 0.6% | **0.2%** |
| 🇦🇺 Australia | 70.7% | 28.6% | 8.9% | 2.8% | 0.9% | **0.2%** |
| 🇺🇸 EE. UU. | 75.0% | 31.3% | 9.8% | 2.8% | 0.7% | **0.2%** |
| 🇨🇻 Cabo Verde | 54.9% | 17.2% | 5.7% | 1.9% | 0.6% | **0.1%** |
| 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escocia | 64.4% | 18.3% | 6.4% | 1.5% | 0.4% | **0.1%** |
| 🇨🇩 RD Congo | 52.4% | 17.3% | 5.7% | 1.8% | 0.5% | **0.1%** |
| 🇪🇨 Ecuador | 64.1% | 20.8% | 6.8% | 2.0% | 0.5% | **0.1%** |
| 🇧🇦 Bosnia-Herzegovina | 63.1% | 22.2% | 6.8% | 1.9% | 0.4% | **0.1%** |
| 🇵🇦 Panamá | 39.5% | 12.7% | 3.7% | 0.9% | 0.2% | **0.1%** |
| 🇿🇦 Sudáfrica | 49.6% | 20.9% | 6.6% | 1.8% | 0.5% | **0.0%** |
| 🇪🇬 Egipto | 58.7% | 22.9% | 6.9% | 1.9% | 0.4% | **0.0%** |
| 🇺🇿 Uzbekistán | 35.2% | 9.6% | 2.7% | 0.6% | 0.1% | **0.0%** |
| 🇳🇿 Nueva Zelanda | 28.7% | 8.4% | 2.2% | 0.6% | 0.1% | **0.0%** |
| 🇬🇭 Ghana | 34.8% | 9.5% | 2.3% | 0.5% | 0.1% | **0.0%** |
| 🇨🇼 Curazao | 21.8% | 4.8% | 1.2% | 0.3% | 0.0% | **0.0%** |
| 🇮🇶 Irak | 20.8% | 4.6% | 0.8% | 0.2% | 0.0% | **0.0%** |
| 🇵🇾 Paraguay | 49.9% | 16.1% | 4.2% | 1.0% | 0.2% | **0.0%** |
| 🇶🇦 Catar | 45.2% | 12.5% | 2.8% | 0.7% | 0.1% | **0.0%** |
| 🇸🇦 Arabia Saudí | 25.3% | 3.8% | 0.7% | 0.1% | 0.0% | **0.0%** |
| 🇯🇴 Jordania | 12.4% | 1.8% | 0.4% | 0.0% | 0.0% | **0.0%** |
| 🇭🇹 Haití | 22.7% | 3.7% | 0.7% | 0.0% | 0.0% | **0.0%** |

## Validación con los partidos ya jugados

| Partido | Predicción del modelo | Resultado real |
|---|:-:|:-:|
| 🇲🇽 México – 🇿🇦 Sudáfrica | 1-0 (P1 47%) | 2-0 ✅ ganador acertado |
| 🇰🇷 Corea del Sur – 🇨🇿 República Checa | 2-1 (P1 41%) | 2-1 ✅ ganador acertado |

---
*Predicciones generadas automáticamente con `prediccion_mundial.py`. El fútbol, por suerte, no entiende de modelos.* ⚽