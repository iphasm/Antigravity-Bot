# 🧠 Lógica de Decisión: Modo PILOT

Este diagrama ilustra cómo Antigravity Bot toma decisiones autónomas, combinando Análisis Técnico, Inteligencia Artificial y Gestión de Riesgo.

## 🌊 Flujo de Decisiones (Deep Dive)

```mermaid
graph TD
    %% Estilos
    classDef input fill:#2d2d2d,stroke:#fff,stroke-width:2px,color:#fff;
    classDef tech fill:#005f99,stroke:#00aaff,stroke-width:2px,color:#fff;
    classDef ai fill:#6600cc,stroke:#cc00ff,stroke-width:2px,color:#fff;
    classDef risk fill:#990000,stroke:#ff3333,stroke-width:2px,color:#fff;
    classDef action fill:#006600,stroke:#00cc00,stroke-width:2px,color:#fff;

    Start((📡 Market Data)):::input --> TechEngine[⚙️ Strategy Engine]:::tech
    
    %% Technical Analysis
    subgraph Technical["1. Análisis Técnico (Quant)"]
        TechEngine --> |Calcula| Indicators[RSI, BBC, Keltner, ADX, ATR, HMA]
        Indicators --> Strategy{Estrategia?}
        Strategy -- "Squeeze & Breakout" --> SignalLong[🟢 Signal LONG]
        Strategy -- "Mean Reversion" --> SignalSpot[🔵 Signal SPOT]
        Strategy -- "Trend Velocity" --> SignalShort[🔴 Signal SHORT]
        Strategy -- "Trend Loss / Exhaustion" --> SignalClose[⚠️ Signal CLOSE]
    end

    %% Filters (AI & Macro)
    subgraph Filters["2. Filtros Inteligentes (AI & Macro)"]
        SignalLong --> AIGuard{🧠 AI Analyst}:::ai
        SignalShort --> AIGuard
        
        AIGuard -- "Score < -0.6 (Sentimiento Negativo)" --> Block[🚫 BLOQUEAR TRADE]:::risk
        AIGuard -- "News: FOMC / WAR (High Vol)" --> MacroShield[🛡️ ACTIVAR MACRO SHIELD]:::risk
        AIGuard -- "Sentimiento Neutro/Positivo" --> Pass[✅ APROBADO]
    end

    %% Execution & Risk
    subgraph Execution["3. Ejecución & Gestión de Riesgo"]
        Pass --> Sizing[📐 Position Sizing]:::risk
        MacroShield --> LevRed[📉 Reducir Apalancamiento (3x)]:::risk
        LevRed --> Sizing
        
        Sizing -- "Equity * 2% Risk" --> VolCalcs[Calcula Lotes]
        VolCalcs -- "ATR * 2.0" --> SL_TP[Establecer SL & TP Dinámicos]
        
        SL_TP --> Validate{Validaciones}
        Validate -- "Margin Suficiente?" --> ExeBinance[🚀 EJECUTAR BINANCE]:::action
        Validate -- "Posición Existente?" --> Reject[❌ Rechazar Duplicado]
    end

    %% Routes
    SignalSpot --> |Solo Spot| AutoBuy[🛒 Compra Spot Directa]:::action
    SignalClose --> ClosePos[📉 Cerrar Posición Futuros]:::action

```

## 🤝 Sinergias Implementadas

1.  **Tecnología + IA (The Veto)**:
    *   El motor técnico encuentra la oportunidad matemática.
    *   La IA (Analyst) actúa como un "oficial de riesgo" humano, vetando la operación si las noticias fundamentales son peligrosas, previniendo trampas de liquidez.

2.  **Volatilidad + Tamaño (Dynamic Risk)**:
    *   No usamos lotes fijos.
    *   Si el mercado está "loco" (ATR alto), el Stop Loss se aleja automáticamente.
    *   Para mantener el riesgo fijo al 2% de la cuenta, el tamaño de la posición se reduce proporcionalmente. **+Volatilidad = -Tamaño.**

3.  **Macro Shield**:
    *   Detecta eventos de alto impacto (Powell, IPC, Guerras).
    *   No bloquea, pero **fuerza** una reducción de apalancamiento (de 10x/20x a 3x) para sobrevivir a los "latigazos" del mercado.

4.  **Circuit Breaker (Anti-Tilt)**:
    *   Si el bot pierde 3 operaciones seguidas, se apaga a sí mismo (`/pilot` OFF) para evitar el "trader tilt" y liquidaciones en cascada.

## 🧪 Combinaciones Estratégicas (Presets)

Podemos configurar "Perfiles de Trading" ajustando estas variables:

| Perfil | Objetivo | IA Filter | Apalancamiento | Stop Loss | Descripción |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **⚔️ RONIN (Sniper)** | Scalping Agresivo | **Laxo (-0.8)** | Alto (Custom) | **Apretado (1.5 ATR)** | Toma casi todas las señales. Stop Loss corto. Alta rotación. |
| **🛡️ GUARDIAN** | Swing / Protección | **Estricto (-0.3)** | **Bajo (3x-5x)** | **Amplio (3.0 ATR)** | Solo entra en setups perfectos con noticias a favor. |
| **🌌 QUANTUM (Default)** | Equilibrio | **Balanceado (-0.6)** | **Dinámico (Macro Shield)** | **Estándar (2.0 ATR)** | El equilibrio actual. Reduce riesgo en eventos macro. |

---
**¿Siguiente Paso?**
Podemos implementar un comando `/mode <PERFIL>` para cambiar instantáneamente entre estas configuraciones de riesgo.
