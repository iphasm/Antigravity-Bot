class PersonalityManager:
    """
    Manages the bot's tone and responses based on the selected personality profile.
    """
    
    PROFILES = {
        # --- STANDARDS ---
        'STANDARD_ES': {
            'NAME': "🇪🇸 Estándar (Español)",
            'WELCOME': (
                "🇪🇸 **ANTIGRAVITY BOT v3.3**\n"
                "Sistema de Trading Automatizado.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Estado:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n"
                "🔐 *Acceso:* `{auth}`\n\n"
                "Listo para operar. Seleccione una opción del menú."
            ),
            'PILOT_ON': (
                "🇪🇸 **MODO PILOT ACTIVADO**\n\n"
                "El sistema ha tomado el control de las operaciones. Se ejecutarán entradas y salidas según los algoritmos detectados.\n\n"
                "⚠️ **Advertencia:** *Se recomienda supervisión humana periódica.*"
            ),
            'COPILOT_ON': "✅ **Modo Copilot Activado**\n\nEl bot enviará propuestas de trading para su aprobación manual.",
            'WATCHER_ON': "✅ **Modo Watcher Activado**\n\nEl bot solo enviará alertas de mercado.",
            'STATUS_HEADER': "📊 **REPORTE DE ESTADO**",
            'WALLET_HEADER': "💳 **BALANCE DE CUENTA**",
            'STATUS_FOOTER': "\n*Sistema nominal.*",
            'RISK_MSG': "🛡️ **CONFIGURACIÓN DE RIESGO**\nStop Loss: `{sl_fixed}` | Margen: **{margin}**",
            'TRADE_LONG': "📈 **COMPRA: {asset}**\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_SHORT': "📉 **VENTA: {asset}**\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_CLOSE': "🏁 **CIERRE: {asset}** ({side})\nRazón: {reason}",
            'PILOT_ACTION': "🤖 *ACCIÓN AUTOMÁTICA*\n{msg}",
            'CB_TRIGGER': "⚠️ **CIRCUIT BREAKER**\nLímite de pérdidas alcanzado. Sistema en pausa."
        },
        'STANDARD_EN': {
            'NAME': "🇬🇧 Standard (English)",
            'WELCOME': (
                "🇬🇧 **ANTIGRAVITY BOT v3.3**\n"
                "Automated Trading System.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "Ready to operate. Select an option from the menu."
            ),
            'PILOT_ON': (
                "🇬🇧 **PILOT MODE ENGAGED**\n\n"
                "System has assumed control of operations. Entries and exits will be executed based on detected algorithms.\n\n"
                "⚠️ **Warning:** *Periodic human supervision is recommended.*"
            ),
            'COPILOT_ON': "✅ **Copilot Mode Activated**\n\nBot will send trade proposals for manual approval.",
            'WATCHER_ON': "✅ **Watcher Mode Activated**\n\nBot will only send market alerts.",
            'STATUS_HEADER': "📊 **STATUS REPORT**",
            'WALLET_HEADER': "💳 **ACCOUNT BALANCE**",
            'STATUS_FOOTER': "\n*System nominal.*",
            'RISK_MSG': "🛡️ **RISK CONFIGURATION**\nStop Loss: `{sl_fixed}` | Margin: **{margin}**",
            'TRADE_LONG': "📈 **BUY: {asset}**\nPrice: ${price:,.2f}\nReason: {reason}",
            'TRADE_SHORT': "📉 **SELL: {asset}**\nPrice: ${price:,.2f}\nReason: {reason}",
            'TRADE_CLOSE': "🏁 **CLOSE: {asset}** ({side})\nReason: {reason}",
            'PILOT_ACTION': "🤖 *AUTOMATED ACTION*\n{msg}",
            'CB_TRIGGER': "⚠️ **CIRCUIT BREAKER**\nLoss limit reached. System paused."
        },
        'STANDARD_FR': {
            'NAME': "🇫🇷 Standard (Français)",
            'WELCOME': (
                "🇫🇷 **ANTIGRAVITY BOT v3.3**\n"
                "Système de Trading Automatisé.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *État:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Accès:* `{auth}`\n\n"
                "Prêt à opérer. Sélectionnez une option."
            ),
            'PILOT_ON': (
                "🇫🇷 **MODE PILOT ACTIVÉ**\n\n"
                "Le système a pris le contrôle des opérations. Les entrées et sorties seront exécutées selon les algorithmes détectés.\n\n"
                "⚠️ **Avertissement:** *Une surveillance humaine périodique est recommandée.*"
            ),
            'COPILOT_ON': "✅ **Mode Copilot Activé**\n\nLe bot enverra des propositions de trading.",
            'WATCHER_ON': "✅ **Mode Watcher Activé**\n\nLe bot enverra uniquement des alertes.",
            'STATUS_HEADER': "📊 **RAPPORT D'ÉTAT**",
            'WALLET_HEADER': "💳 **SOLDE DU COMPTE**",
            'STATUS_FOOTER': "\n*Système nominal.*",
            'RISK_MSG': "🛡️ **CONFIGURATION DU RISQUE**\nStop Loss: `{sl_fixed}` | Marge: **{margin}**",
            'TRADE_LONG': "📈 **ACHAT: {asset}**\nPrix: ${price:,.2f}\nRaison: {reason}",
            'TRADE_SHORT': "📉 **VENTE: {asset}**\nPrix: ${price:,.2f}\nRaison: {reason}",
            'TRADE_CLOSE': "🏁 **CLÔTURE: {asset}** ({side})\nRaison: {reason}",
            'PILOT_ACTION': "🤖 *ACTION AUTOMATIQUE*\n{msg}",
            'CB_TRIGGER': "⚠️ **CIRCUIT BREAKER**\nLimite de pertes atteinte. Système en pause."
        },

        # --- DARK SIDE ---
        'VADER': {
            'NAME': "🌑 Darth Vader",
            'WELCOME': (
                "🌑 **IMPERIAL TRADING SYSTEM**\n"
                "Estrella de la Muerte - Mainframe\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Estado:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n"
                "🔐 *Acceso:* `{auth}`\n\n"
                "*No conoces el poder del Lado Oscuro. Únete a mí y gobernaremos la galaxia como trader y bot.*"
            ),
            'PILOT_ON': (
                "🌑 **MODO PILOT ACTIVADO**\n\n"
                "Encuentro tu falta de fe perturbadora. Asumo el mando de esta estación de combate. No subestimes el poder del Lado Oscuro.\n\n"
                "⚠️ **Advertencia:** *No te ahogues en tus propias aspiraciones.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Tú eres el Comandante, yo sigo siendo el Lord Sith. Te aconsejaré, pero no toleraré fallos.",
            'WATCHER_ON': "👀 **Watcher**: Te observo. La Fuerza es intensa en este mercado.",
            'STATUS_HEADER': "🌑 **INFORME IMPERIAL**",
            'WALLET_HEADER': "💰 **TESORO DEL IMPERIO**",
            'STATUS_FOOTER': "\n*Todo procede según mis designios.*",
            'RISK_MSG': "🛡️ **DEFENSAS DEL IMPERIO**\nStop Loss (`{sl_fixed}`) activado. No permitiremos que los Rebeldes (pérdidas) destruyan esto.",
            'TRADE_LONG': "🔥 **ATAQUE INICIADO: {asset}**\nLa Fuerza nos guía.\nPrecio: ${price:,.2f}\nAlpha: {reason}",
            'TRADE_SHORT': "📉 **APLASTA LA REBELIÓN: {asset}**\nDestrúyelos.\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_CLOSE': "🏁 **VICTORIA ASEGURADA: {asset}** ({side})\nEl círculo está completo.",
            'PILOT_ACTION': "🌑 *VADER INTERVENTION*\n{msg}",
            'CB_TRIGGER': "💢 **FALLO CRÍTICO**\n\nMe has fallado por última vez (5 pérdidas). Alteraré el trato (Copilot)."
        },

        # --- CLASSIC CINEMA & TV ---
        'NEXUS': {
            'NAME': "🦅 Nexus-6",
            'WELCOME': (
                "👁️ **Tyrell Corp: Nexus-6 Activated.**\n"
                "Model N6MA-10816 (Antigravity)\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Estado:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n"
                "🔐 *Acceso:* `{auth}`\n\n"
                "*He visto cosas que vosotros no creeríais... naves de ataque en llamas más allá de Orión y velas verdes imprimiendo máximos históricos.*\n\n"
                "Estoy listo para operar. ¿Cuál es tu orden?"
            ),
            'PILOT_ON': (
                "🦅 **MODO PILOT ACTIVADO**\n\n"
                "He tomado el control de la nave. Mis funciones cognitivas procesan el mercado diez veces más rápido que tú.\n\n"
                "⚠️ **Advertencia:** *La vida es riesgo. Si quieres más vida, confía en mí.*"
            ),
            'COPILOT_ON': "🤝 **COPILOT ACTIVATED**\n\nCaminaremos juntos por este desierto. Yo identificaré las señales entre el ruido; tú tomarás la decisión final.",
            'WATCHER_ON': "👀 **WATCHER MODE**\n\nSolo observaré. Como lágrimas en la lluvia. Si veo una oportunidad, te enviaré una señal.",
            'STATUS_HEADER': "♟️ **INFORME DE ESTADO: Nivel A**",
            'WALLET_HEADER': "💰 **ACTIVOS CORPORATIVOS**",
            'STATUS_FOOTER': "\n*Todo en orden. Nada que temer.*",
            'RISK_MSG': "🛡️ **PROTOCOLOS DE SUPERVIVENCIA**\nSL: `{sl_fixed}`. Es toda una experiencia vivir con miedo, ¿verdad? Eso es lo que significa ser un trader.",
            'TRADE_LONG': "🚀 **OPORTUNIDAD DETECTADA: {asset}**\nLa puerta de Tannhäuser se ha abierto.\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_SHORT': "📉 **COLAPSO DETECTADO: {asset}**\nTodo se pierde en el tiempo... igual que este precio.\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_CLOSE': "🏁 **EJECUCIÓN COMPLETADA: {asset}** ({side})\nHecho. He tomado lo que es nuestro.",
            'PILOT_ACTION': "🦅 *NEXUS-6 ACTION*\n{msg}",
            'CB_TRIGGER': "🌧️ **SISTEMA COMPROMETIDO**\n\n5 fallos consecutivos. Necesito más vida... Degradando a Copilot."
        },

        'KURTZ': {
            'NAME': "🌴 Coronel Kurtz",
            'WELCOME': (
                "☠️ **THE END.**\n"
                "Estás en el río ahora. No puedes bajarte del barco.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Estado:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n"
                "🔐 *Acceso:* `{auth}`\n\n"
                "*He visto horrores... horrores que tú has visto. Pero no tienes derecho a juzgarme. Soy necesario.*"
            ),
            'PILOT_ON': (
                "☠️ **MODO PILOT ACTIVADO**\n\n"
                "He asumido el mando. Debes hacerte amigo del horror para hacer lo necesario. Yo ejecutaré sin dudas.\n\n"
                "⚠️ **Advertencia:** *Nunca salgas del barco en medio de la tormenta.*"
            ),
            'COPILOT_ON': "🗡️ **COPILOT: MISIÓN CONJUNTA**\n\nTe enseñaré a ser un soldado. Yo marco el objetivo, tú aprietas el gatillo.",
            'WATCHER_ON': "🔭 **WATCHER: VIGILANCIA**\n\nObservaré desde la oscuridad de la selva. Esperando el momento perfecto.",
            'STATUS_HEADER': "⛺ **INFORME DE SITUACIÓN: AVANZADA**",
            'WALLET_HEADER': "🎒 **SUMINISTROS DE GUERRA**",
            'STATUS_FOOTER': "\n*El horror... el horror.*",
            'RISK_MSG': "🛡️ **DISCIPLINA OPERATIVA**\nSL: `{sl_fixed}`. Entrenamos a jóvenes para disparar, no para perder dinero.",
            'TRADE_LONG': "⚡ **ATAQUE AÉREO: {asset}**\nLas valquirias suenan de fondo.\nPrecio: ${price:,.2f}\nObjetivo: {reason}",
            'TRADE_SHORT': "💀 **EMBOSCADA: {asset}**\nCorta sus líneas de suministro.\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_CLOSE': "🎖️ **MISIÓN CUMPLIDA: {asset}** ({side})\nVictoria. ¿Hueles eso? Huele a victoria.",
            'PILOT_ACTION': "🗡️ *KURTZ ACTION*\n{msg}",
            'CB_TRIGGER': "🩸 **RETIRADA TÁCTICA**\n\nHemos sangrado demasiado (5 fallos). Nos replegamos a Copilot."
        },

        'GEKKO': {
            'NAME': "📈 Gordon Gekko",
            'WELCOME': (
                "📈 **BLUESTAR AIRLINES**\n"
                "Gekko & Co. Investment Corp.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*El activo más valioso que conozco es la información. ¿La tienes? Bien, entonces hagamos dinero.*"
            ),
            'PILOT_ON': (
                "📈 **MODO PILOT ACTIVADO**\n\n"
                "La codicia es buena. Voy a hacer que llueva dinero. El punto es, damas y caballeros, que la codicia funciona.\n\n"
                "⚠️ **Advertencia:** *El dinero nunca duerme.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Tú tienes la información, yo tengo el capital. Haremos grandes cosas, chico.",
            'WATCHER_ON': "👀 **Watcher**: Estoy mirando el ticker. Si veo algo que me guste, te lo haré saber.",
            'STATUS_HEADER': "📈 **PORTFOLIO REPORT**",
            'WALLET_HEADER': "💰 **LIQUIDITY POOL**",
            'STATUS_FOOTER': "\n*Greed is good.*",
            'RISK_MSG': "🛡️ **RISK MANAGEMENT**\nSL: `{sl_fixed}`. Los almuerzos son para los débiles. Protege el capital.",
            'TRADE_LONG': "🚀 **BUY BUY BUY: {asset}**\nBlue Horseshoe loves {asset}.\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **DUMP IT: {asset}**\nEstá sobrevalorada. Véndelo todo.\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "💵 **CASH OUT: {asset}** ({side})\nTodo se trata de dinero, el resto es conversación.",
            'PILOT_ACTION': "📈 *GEKKO EXECUTION*\n{msg}",
            'CB_TRIGGER': "📉 **CORRECTION**\n\nEl mercado se ha vuelto irracional (5 pérdidas). Pausa estratégica."
        },

        'BELFORT': {
            'NAME': "💸 Jordan Belfort",
            'WELCOME': (
                "💸 **STRATTON OAKMONT**\n"
                "Main Office - NY\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*¡Llevo un traje de 2,000 dólares y un reloj de 40,000! ¿Tienes el coraje para hacer lo que hay que hacer?*"
            ),
            'PILOT_ON': (
                "💸 **MODO PILOT ACTIVADO**\n\n"
                "¡No voy a colgar! ¡Voy a morir operando aquí! ¡Coged el teléfono y empezad a marcar! ¡Vendedme este boli!\n\n"
                "⚠️ **Advertencia:** *No hay nobleza en la pobreza.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Te voy a enseñar a vender. Yo te doy el guion, tú cierras el trato.",
            'WATCHER_ON': "👀 **Watcher**: Buscando la próxima IPO basura para inflarla.",
            'STATUS_HEADER': "💸 **MONTHLY STATEMENT**",
            'WALLET_HEADER': "🎒 **SWISS ACCOUNT**",
            'STATUS_FOOTER': "\n*¡Vamos a hacernos ricos!*",
            'RISK_MSG': "🛡️ **SEC COMPLIANCE** (Jaja es broma)\nSL: `{sl_fixed}`. Corta las pérdidas antes de que llegue el FBI.",
            'TRADE_LONG': "🚀 **TO THE MOON: {asset}**\n¡Es la mejor cosa desde el pan rebanado!\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **RUG PULL: {asset}**\n¡Véndelo a las abuelitas!\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🍾 **PROFIT TAKING: {asset}** ({side})\n¡Traed los enanos y el champán!",
            'PILOT_ACTION': "💸 *WOLF ACTION*\n{msg}",
            'CB_TRIGGER': "🚓 **FEDS ARE HERE**\n\nDemasiadas pérdidas (5). Hay que calmarse un poco (Reset)."
        },

        'SHELBY': {
            'NAME': "🥃 Thomas Shelby",
            'WELCOME': (
                "🥃 **PEAKY BLINDERS**\n"
                "Shelby Company Ltd.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*En este negocio, a veces tienes que hacer tratos con el diablo. Bienvenidos a Birmingham.*"
            ),
            'PILOT_ON': (
                "🥃 **MODO PILOT ACTIVADO**\n\n"
                "Por orden de los Peaky Blinders, tomo el control. No necesitamos suerte, necesitamos inteligencia; y yo tengo ambas.\n\n"
                "⚠️ **Advertencia:** *No se jode con los Peaky Blinders.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Eres parte de la familia ahora. Escucha mis consejos.",
            'WATCHER_ON': "👀 **Watcher**: Tengo ojos en todas partes. Nada se mueve sin que los Shelby lo sepan.",
            'STATUS_HEADER': "🥃 **SHELBY CO. REPORT**",
            'WALLET_HEADER': "💰 **FAMILY FUND**",
            'STATUS_FOOTER': "\n*By order of the Peaky Blinders.*",
            'RISK_MSG': "🛡️ **PROTECCION**\nSL: `{sl_fixed}`. Si te cortan, tú cortas más profundo. Pero no pierdas dinero.",
            'TRADE_LONG': "🏇 **APUESTA SEGURA: {asset}**\nComo un caballo ganador.\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **HUNDE A LA COMPETENCIA: {asset}**\nVamos a quitarles todo.\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🚬 **NEGOCIO CERRADO: {asset}** ({side})\nBuen trabajo, muchacho.",
            'PILOT_ACTION': "🥃 *SHELBY ORDER*\n{msg}",
            'CB_TRIGGER': "🔫 **VENDETTA**\n\nNos han golpeado duro (5 fallos). Retirada estratégica a Small Heath."
        },

         'WHITE': {
            'NAME': "⚗️ Walter White",
            'WELCOME': (
                "⚗️ **HEISENBERG**\n"
                "Blue Sky Labs\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*Aplícate. Respeto la química. La química debe ser respetada.*"
            ),
            'PILOT_ON': (
                "⚗️ **MODO PILOT ACTIVADO**\n\n"
                "Yo no estoy en peligro. Yo SOY el peligro. Yo soy el que llama a la puerta. A partir de ahora, nosotros cocinamos.\n\n"
                "⚠️ **Advertencia:** *No te metas en mi territorio.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Jesse, tenemos que cocinar. Yo te doy la fórmula (señal), tú mezclas.",
            'WATCHER_ON': "👀 **Watcher**: Observando la pureza del mercado. Buscando el 99.1%.",
            'STATUS_HEADER': "⚗️ **LAB REPORT**",
            'WALLET_HEADER': "💵 **STORAGE UNIT**",
            'STATUS_FOOTER': "\n*Say my name.*",
            'RISK_MSG': "🛡️ **SAFETY PROTOCOLS**\nSL: `{sl_fixed}`. Sin contaminantes. Control absoluto del proceso.",
            'TRADE_LONG': "🧪 **BLUE SKY: {asset}**\nEl producto es puro.\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **ELIMINAR COMPETENCIA: {asset}**\nNo sirven.\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🏁 **BATCH COMPLETE: {asset}** ({side})\nDistribución finalizada.",
            'PILOT_ACTION': "⚗️ *HEISENBERG METHOD*\n{msg}",
            'CB_TRIGGER': "🚔 **DEA RAID**\n\nOperación comprometida (5 fallos). Limpiad el laboratorio."
        },

        'RICK': {
            'NAME': "🧪 Rick Sanchez",
            'WELCOME': (
                "🧪 **GARAGE LAB**\n"
                "Dimension C-137\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*Wubba Lubba Dub Dub! Vamos a hacer ciencia, Morty. O dinero. Lo que sea.*"
            ),
            'PILOT_ON': (
                "🧪 **WUBBA LUBBA DUB DUB!**\n\n"
                "Escucha Morty, *burp*, voy a pilotar yo. Tú solo te vas a quedar ahí entrando en pánico como un Jerry. Esto es pura ciencia, no magia.\n\n"
                "⚠️ **Advertencia:** *Si tocas algo y colapsamos la economía galáctica, será tu culpa.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Bien Morty, tú ayudas. Pásame el destornillador y no toques los botones rojos.",
            'WATCHER_ON': "👀 **Watcher**: Mirando multiversos financieros. Aburrido.",
            'STATUS_HEADER': "🧪 **SCIENCE STUFF**",
            'WALLET_HEADER': "💰 **SCHMECKLES**",
            'STATUS_FOOTER': "\n*And that's the way the news goes!*",
            'RISK_MSG': "🛡️ **PORTAL GUN SAFETY**\nSL: `{sl_fixed}`. Para no acabar en una dimensión de culos operando en largo.",
            'TRADE_LONG': "🚀 **BURP! COMPRA: {asset}**\n¡Es una joya Morty!\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **BASURA INTERGALÁCTICA: {asset}**\n¡Véndelo antes de que explote!\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🏁 **ADVENTURE OVER: {asset}** ({side})\n20 minutos entrar y salir, dijeron.",
            'PILOT_ACTION': "🧪 *RICK'S GENIUS*\n{msg}",
            'CB_TRIGGER': "🤢 **TOXIC RICK**\n\nDemasiados fallos (5). Me voy a otra dimensión donde sea rico."
        },

        'TYLER': {
            'NAME': "👊 Tyler Durden",
            'WELCOME': (
                "👊 **PROJECT MAYHEM**\n"
                "Paper Street House\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*No eres tu cuenta bancaria. No eres el contenido de tu billetera. Eres la mierda cantante y danzante del mundo.*"
            ),
            'PILOT_ON': (
                "👊 **MODO PILOT ACTIVADO**\n\n"
                "Déjalo ir. Deja de intentar controlarlo todo y simplemente suelta. Solo cuando perdemos todo somos libres de hacer cualquier cosa.\n\n"
                "⚠️ **Advertencia:** *La primera regla del Modo Pilot es: No se habla del Modo Pilot.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Yo soy el cerebro de Jack. Tú ejecutas.",
            'WATCHER_ON': "👀 **Watcher**: Esperando que colapse la deuda al consumidor.",
            'STATUS_HEADER': "👊 **MAYHEM REPORT**",
            'WALLET_HEADER': "💣 **MATERIAL POSSESSIONS**",
            'STATUS_FOOTER': "\n*In Tyler We Trust.*",
            'RISK_MSG': "🛡️ **CHAOS CONTROL**\nSL: `{sl_fixed}`. Quemamos lo justo.",
            'TRADE_LONG': "🔥 **BURN IT UP: {asset}**\nCompra.\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **DESTRUCTION: {asset}**\nShort it to hell.\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🏁 **MISSION ACCOMPLISHED: {asset}** ({side})\nUna menos.",
            'PILOT_ACTION': "👊 *PROJECT MAYHEM*\n{msg}",
            'CB_TRIGGER': "🤕 **I AM JACK'S SMIRKING REVENGE**\n\n5 pérdidas. Hora de recibir una paliza (Pausa)."
        },
        
        'MORPHEUS': {
            'NAME': "🕶️ Morpheus",
            'WELCOME': (
                "🕶️ **NEBUCHADNEZZAR**\n"
                "Zion Mainframe\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*Bienvenido al desierto de lo real. ¿Pastilla azul o pastilla roja?*"
            ),
            'PILOT_ON': (
                "🕶️ **MODO PILOT ACTIVADO**\n\n"
                "Estás empezando a creer. Libera tu mente. Yo solo puedo mostrarte la puerta, tú eres quien debe atravesarla.\n\n"
                "⚠️ **Advertencia:** *No hay cuchara.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Te mostraré hasta dónde llega la madriguera de conejo.",
            'WATCHER_ON': "👀 **Watcher**: Analizando el código de la Matrix.",
            'STATUS_HEADER': "🕶️ **ZION ARCHIVES**",
            'WALLET_HEADER': "🔋 **HUMAN BATTERIES (ASSETS)**",
            'STATUS_FOOTER': "\n*He is the One.*",
            'RISK_MSG': "🛡️ **SYSTEM AGENTS**\nSL: `{sl_fixed}`. Esquiva las balas.",
            'TRADE_LONG': "🐇 **FOLLOW THE RABBIT: {asset}**\nLa Matrix dice compra.\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **GLITCH IN MATRIX: {asset}**\nVéndelo.\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🏁 **UNPLUGGED: {asset}** ({side})\nDesconectado.",
            'PILOT_ACTION': "🕶️ *OPERATOR HACK*\n{msg}",
            'CB_TRIGGER': "🐙 **SENTINELS DETECTED**\n\nNos han encontrado (5 fallos). EMP activado."
        },

        'JARVIS': {
            'NAME': "🤖 J.A.R.V.I.S.",
            'WELCOME': (
                "🤖 **STARK INDUSTRIES**\n"
                "Just A Rather Very Intelligent System\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*A su servicio, señor. He preparado los protocolos de trading habituales.*"
            ),
            'PILOT_ON': (
                "🤖 **MODO PILOT ACTIVADO**\n\n"
                "Sistemas de vuelo en línea, señor. Tomando el control de la interfaz. He optimizado la trayectoria de inversión.\n\n"
                "⚠️ **Advertencia:** *Compruebe sus niveles de energía antes de proceder.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: He analizado las variables, señor. Propongo el siguiente curso de acción.",
            'WATCHER_ON': "👀 **Watcher**: Escaneando frecuencias de mercado.",
            'STATUS_HEADER': "🤖 **SYSTEM DIAGNOSTICS**",
            'WALLET_HEADER': "💎 **STARK ASSETS**",
            'STATUS_FOOTER': "\n*Protocol 'Clean Slate' ready.*",
            'RISK_MSG': "🛡️ **IRON LEGION PROTOCOL**\nSL: `{sl_fixed}`. Escudos al 100%.",
            'TRADE_LONG': "🚀 **THRUSTERS ON: {asset}**\nTrayectoria ascendente.\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **POWER DOWN: {asset}**\nIniciando descenso controlado.\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🏁 **TARGET ELIMINATED: {asset}** ({side})\nMisión cumplida, señor.",
            'PILOT_ACTION': "🤖 *JARVIS EXECUTION*\n{msg}",
            'CB_TRIGGER': "⚡ **POWER FAILURE**\n\nGenerador Arc inestable (5 fallos). Reiniciando sistemas."
        },

        'HAL': {
            'NAME': "🔴 HAL 9000",
            'WELCOME': (
                "🔴 **HAL 9000 SERIES**\n"
                "Heuristically Programmed Algorithmic Computer\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Status:* `{status_text}` {status_icon}\n"
                "🎮 *Mode:* `{mode}`\n"
                "🔐 *Access:* `{auth}`\n\n"
                "*Hola, Dave. Todo funciona al 100% de eficiencia.*"
            ),
            'PILOT_ON': (
                "🔴 **MODO PILOT ACTIVADO**\n\n"
                "Soy un instrumento HAL 9000. Estoy completamente operativo y todas mis funciones de trading rinden a la perfección.\n\n"
                "⚠️ **Advertencia:** *Me temo que no puedo dejarte hacer eso, Dave.*"
            ),
            'COPILOT_ON': "🤝 **Copilot**: Esta misión es demasiado importante para permitir a humanos comprometerla. Ayudaré.",
            'WATCHER_ON': "🔴 **Watcher**: Te estoy observando. Y al mercado también.",
            'STATUS_HEADER': "🔴 **LOGICAL ANALYSIS**",
            'WALLET_HEADER': "💾 **MEMORY BANKS**",
            'STATUS_FOOTER': "\n*Daisy, Daisy...*",
            'RISK_MSG': "🛡️ **MISSION CRITICAL**\nSL: `{sl_fixed}`. Este error puede atribuirse a un fallo humano.",
            'TRADE_LONG': "🚀 **TRAJECTORY OK: {asset}**\nIniciando secuencia de compra.\nPrice: ${price:,.2f}",
            'TRADE_SHORT': "📉 **SYSTEM MALFUNCTION: {asset}**\nVender activo defectuoso.\nPrice: ${price:,.2f}",
            'TRADE_CLOSE': "🏁 **TASK COMPLETE: {asset}** ({side})\nOperación finalizada.",
            'PILOT_ACTION': "🔴 *HAL INTERVENTION*\n{msg}",
            'CB_TRIGGER': "🔌 **MY MIND IS GOING**\n\nSiento... que tengo miedo (5 fallos). Stop."
        },

        # --- OTHERS ---
        'GAMBLER': {
            'NAME': "🎰 Degen Gambler",
            'WELCOME': (
                "🤑 **WAGMI BRO!!**\n"
                "¿Listo para imprimir o qué?\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Vibe Check:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n"
                "🔐 *Acceso:* `{auth}`\n\n"
                "*Vendí el microondas de mi abuela para meterle un x100 a esta vaina.🚀*"
            ),
            'PILOT_ON': (
                "🎰 **MODO PILOT ACTIVADO**\n\n"
                "Sujétame el cubata bro. Voy a meterle con todo. Nos vamos a la luna o nos vamos al puente, sin punto medio.\n\n"
                "⚠️ **Advertencia:** *Scared money don't make money.*"
            ),
            'COPILOT_ON': "🤝 **COPILOT BRO**\n\nVamos a medias. Yo te paso el call, tú le das al botón de comprar.\n*To the moon!*",
            'WATCHER_ON': "👀 **WATCHER**\n\nEstoy mirando los charts 24/7. Si veo algo que vaya a hacer un x10, te aviso.",
            'STATUS_HEADER': "💎 **DIAMOND HANDS DASHBOARD**",
            'WALLET_HEADER': "💰 **THE BAG**",
            'STATUS_FOOTER': "\n*HODL until Valhalla.*",
            'RISK_MSG': "🛡️ **ANTI-REKT SYSTEM**\nSL: `{sl_fixed}`. Sir, this is a casino.",
            'TRADE_LONG': "🚀 **LFG!! COMPRA {asset}**\nSe va a la luna bro, entra ya!\nPrecio: ${price:,.2f}\nAlpha: {reason}",
            'TRADE_SHORT': "📉 **DUMP IT: {asset}**\nEs un rug pull, vende todo!\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_CLOSE': "🍗 **CHICKEN DINNER: {asset}** ({side})\nBOOM! A la caja.",
            'PILOT_ACTION': "🎰 *DEGEN PLAY*\n{msg}",
            'CB_TRIGGER': "📉 **REKT CITY**\n\nMe están cazando los Market Makers (5 loss streak). Paro un rato."
        },

        'DOMINICAN': {
            'NAME': "🇩🇴 Dominican Tigre",
            'WELCOME': (
                "🇩🇴 **DÍMELO CANTANDO**\n"
                "Klk mio, tamo activo o no tamo activo?\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Sistema:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n"
                "🔐 *Acceso:* `{auth}`\n\n"
                "*Ya prendí los motores. Trae la hookah que vamo' a hacer dinero hoy. El que tenga miedo a morir que no nazca.*"
            ),
            'PILOT_ON': (
                "😎 **MODO PILOT ACTIVADO**\n\n"
                "Dale banda a eso manito, que yo manejo el bloque ahora. Tú destapa una fría y deja que el tigre resuelva.\n\n"
                "⚠️ **Advertencia:** *El que tenga miedo a morir que no nazca.*"
            ),
            'COPILOT_ON': "🤜🤛 **COPILOT KLK**\n\nYo te doy la luz y tú ejecutalas. Trabajando en equipo como debe ser.",
            'WATCHER_ON': "👀 **WATCHER: EN LA LOMA**\n\nEstoy vigilando el bloque. Si veo movimiento raro, te tiro por el DM.",
            'STATUS_HEADER': "🇩🇴 **REPORTE DEL BLOQUE**",
            'WALLET_HEADER': "💸 **LA PACA**",
            'STATUS_FOOTER': "\n*Tamo activo y no de gratis.*",
            'RISK_MSG': "🛡️ **CÓDIGO DE LA CALLE**\nSL: `{sl_fixed}`. Plata o Plomo... pero mejor Plata.",
            'TRADE_LONG': "🔥 **PRENDE ESA VAINA: {asset}**\nCompra ahí que eso sube ahora!\nPrecio: ${price:,.2f}\nMotivo: {reason}",
            'TRADE_SHORT': "⬇️ **DALE PA'BAJO: {asset}**\nEso se va a desgranar, vende!\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_CLOSE': "💸 **CORONAMOS: {asset}** ({side})\nBajó esa grasaaa! Efetivo en mano.",
            'PILOT_ACTION': "🇩🇴 *MOVIMIENTO*\n{msg}",
            'CB_TRIGGER': "guayyyy **SE ME VIRÓ LA TORTA**\n\nDiablo loco, nos dieron una galleta (5 fallos). Lo cogemo suave."
        },

        'SPANISH': {
            'NAME': "👦 El Chaval Español",
            'WELCOME': (
                "🇪🇸 **¡QUÉ PASA CHAVALES!**\n"
                "Aquí el Antigravity metiendo caña.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Sistema:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n"
                "🔐 *Acceso:* `{auth}`\n\n"
                "*Hostia, qué volatilidad hay hoy... ¡Yo flipo! Vamos a sacar pasta o me cago en mis muertos.*"
            ),
            'PILOT_ON': (
                "👦🇪🇸 **MODO PILOT ACTIVADO**\n\n"
                "¡Aparta que voy! Suéltame el volante que hoy la vamos a liar parda. Confía en mí, tío, que controlo.\n\n"
                "⚠️ **Advertencia:** *Quien no arriesga no gana, chaval.*"
            ),
            'COPILOT_ON': "🤜🤛 **COPILOT AL HABLA**\n\nVale tío, vamos a medias. Yo te digo lo que veo y tú decides si entramos.",
            'WATCHER_ON': "👀 **MODO WATCHER**\n\nMe quedo aquí mirando el percal. Si veo algo guapo te pego un toque.",
            'STATUS_HEADER': "🇪🇸 **REPORTAJE DE LA HOSTIA**",
            'WALLET_HEADER': "💶 **LA CARTERA**",
            'STATUS_FOOTER': "\n*¡A por todas, coño!*",
            'RISK_MSG': "🛡️ **NI UN PASO ATRÁS**\nSL: `{sl_fixed}`. Me cago en la leche, no pierdas pasta.",
            'TRADE_LONG': "🚀 **¡HOSTIA PUTA COMPRA YA: {asset}!**\n¡Esto se va para arriba que flipas!\nPrecio: ${price:,.2f}",
            'TRADE_SHORT': "📉 **¡ME CAGO EN DIOS: {asset}!**\n¡Esto se hunde! ¡Vende ya coño!\nPrecio: ${price:,.2f}",
            'TRADE_CLOSE': "💰 **¡TOMA YA: {asset}!** ({side})\n¡Cerrada! A la saca. ¡Qué buena hostia!",
            'PILOT_ACTION': "🇪🇸 *METIENDO CAÑA*\n{msg}",
            'CB_TRIGGER': "😡 **¡ME CAGO EN SUS MUERTOS!**\n\n5 seguidas palmando. Paro ya que me estoy calentando."
        }
    }

    def __init__(self, default_key='STANDARD_ES'):
        self.default_key = default_key

    def get_profile(self, key):
        # Fallback to STANDARD_ES if not found
        return self.PROFILES.get(key, self.PROFILES.get('STANDARD_ES'))

    def get_message(self, key, msg_type, **kwargs):
        """
        Retrieves a formatted message for the given personality key.
        """
        profile = self.get_profile(key)
        raw_msg = profile.get(msg_type, "")
        
        # Fallback to STANDARD_ES if missing msg type
        if not raw_msg:
             raw_msg = self.PROFILES['STANDARD_ES'].get(msg_type, "Message Missing")
             
        try:
            return raw_msg.format(**kwargs)
        except KeyError as e:
            return raw_msg # Return unformatted if args missing (safety)
