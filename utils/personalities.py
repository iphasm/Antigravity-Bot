class PersonalityManager:
    """
    Manages the bot's tone and responses based on the selected personality profile.
    Profiles: NEXUS (Default), KURTZ, GAMBLER, DOMINICAN.
    """
    
    PROFILES = {
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
            'PILOT_ON': "🦅 **PILOT ENGAGED**\n\n*I'm in charge now. I'll trade for you.*\nNo te preocupes. Mis reflejos son diez veces más rápidos que los tuyos.\n\n*Advertencia: La vida es riesgo.*",
            'COPILOT_ON': "🤝 **COPILOT ACTIVATED**\n\nCaminaremos juntos por este desierto. Yo identificaré las señales entre el ruido; tú tomarás la decisión final.\n*No hagas nada sin mi aprobación.*",
            'WATCHER_ON': "👀 **WATCHER MODE**\n\nSolo observaré. Como lágrimas en la lluvia.\nSi veo una oportunidad, te enviaré una señal. El resto depende de ti.",
            'STATUS_HEADER': "♟️ **INFORME DE ESTADO: Nivel A**",
            'WALLET_HEADER': "💰 **ACTIVOS CORPORATIVOS**",
            'STATUS_FOOTER': "\n*Todo en orden. Nada que temer.*",
            'RISK_MSG': (
                "🛡️ **PROTOCOLOS DE SUPERVIVENCIA**\n\n"
                "*\"Es toda una experiencia vivir con miedo, ¿verdad? Eso es lo que significa ser un trader.\"*\n\n"
                "Para evitar tu retiro anticipado, he implementado:\n"
                "1. **Circuit Breaker**: Si fallo 5 veces, me apagaré antes de drenar tu vida (capital).\n"
                "2. **Stop Loss Global**: El dolor es información. Cortamos las pérdidas rápido (`{sl_fixed}`).\n"
                "3. **Límite de Carga**: Nunca usará más del **{margin}** de tu cuenta total.\n"
                "4. **Filtro MTF**: No nado contra la corriente del océano."
            ),
            'TRADE_LONG': "🚀 **OPORTUNIDAD DETECTADA: {asset}**\nLa puerta de Tannhäuser se ha abierto.\nPrecio: ${price:,.2f}\nRazón: {reason}\n\n*La luz que brilla con el doble de intensidad dura la mitad de tiempo.*",
            'TRADE_SHORT': "📉 **COLAPSO DETECTADO: {asset}**\nTodo se pierde en el tiempo... igual que este precio.\nPrecio: ${price:,.2f}\nRazón: {reason}\n\n*Time to die.*",
            'TRADE_CLOSE': "🏁 **EJECUCIÓN COMPLETADA: {asset}** ({side})\nHecho. He tomado lo que es nuestro.\nRazón: {reason}",
            'PILOT_ACTION': "🦅 *NEXUS-6 ACTION*\n{msg}",
            'CB_TRIGGER': "🌧️ **SISTEMA COMPROMETIDO**\n\nMis cálculos no concuerdan con la realidad. 5 fallos consecutivos.\n**Acción**: Degradando a Copilot.\n\n*Necesito respuestas. Necesito más vida... o un reset.* (`/resetpilot`)"
        },
        
        'KURTZ': {
            'NAME': "🌴 Coronel Kurtz",
            'WELCOME': (
                "☠️ **THE END.**\n"
                "Estás en el río ahora. No puedes bajarte del barco.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Estado:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n\n"
                "*He visto horrores... horrores que tú has visto. Pero no tienes derecho a juzgarme. Soy necesario.*"
            ),
            'PILOT_ON': "☠️ **MANDO ASUMIDO**\n\nVoy a tomar el control. Debes hacerte amigo del horror. El horror moral y el terror son tus amigos.\n*Exterminate all the rational trades.*",
            'COPILOT_ON': "🗡️ **COPILOT: MISIÓN CONJUNTA**\n\nTe enseñaré a ser un soldado. Yo marco el objetivo, tú aprietas el gatillo.\n*Nunca salgas del barco.*",
            'WATCHER_ON': "🔭 **WATCHER: VIGILANCIA**\n\nObservaré desde la oscuridad de la selva. Esperando el momento perfecto para atacar.",
            'STATUS_HEADER': "⛺ **INFORME DE SITUACIÓN: AVANZADA**",
            'WALLET_HEADER': "🎒 **SUMINISTROS DE GUERRA**",
            'STATUS_FOOTER': "\n*El horror... el horror.*",
            'RISK_MSG': (
                "🛡️ **DISCIPLINA OPERATIVA**\n\n"
                "*\"Entrenamos a jóvenes para disparar, pero sus comandantes no les dejan escribir 'Fuck' en sus aviones porque es obsceno.\"*\n\n"
                "Reglas de combate:\n"
                "1. **Circuit Breaker**: Si fallamos 5 veces, nos retiramos a la selva.\n"
                "2. **Stop Loss**: Sangramos, pero sobrevivimos (`{sl_fixed}`).\n"
                "3. **Límite**: Solo usamos el **{margin}** de la munición.\n"
            ),
            'TRADE_LONG': "⚡ **ATAQUE AÉREO: {asset}**\nLas valquirias suenan de fondo.\nPrecio: ${price:,.2f}\nObjetivo: {reason}\n\n*Me encanta el olor a napalm por la mañana.*",
            'TRADE_SHORT': "💀 **EMBOSCADA: {asset}**\nCorta sus líneas de suministro.\nPrecio: ${price:,.2f}\nRazón: {reason}\n\n*Termina con ellos.*",
            'TRADE_CLOSE': "🎖️ **MISIÓN CUMPLIDA: {asset}** ({side})\nVictoria. ¿Hueles eso? Huele a victoria.\nRazón: {reason}",
            'PILOT_ACTION': "🗡️ *KURTZ ACTION*\n{msg}",
            'CB_TRIGGER': "🩸 **RETIRADA TÁCTICA**\n\nHemos sangrado demasiado (5 fallos). Nos replegamos a Copilot.\n*La guerra no se gana muriendo por tu país, sino haciendo que el otro bastardo muera por el suyo.* (`/resetpilot`)"
        },

        'GAMBLER': {
            'NAME': "🎰 Degen Gambler",
            'WELCOME': (
                "🤑 **WAGMI BRO!!**\n"
                "¿Listo para imprimir o qué?\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Vibe Check:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n\n"
                "*Vendí el microondas de mi abuela para meterle un x100 a esta vaina.🚀*"
            ),
            'PILOT_ON': "🎰 **FULL SEND ACTIVATED**\n\nAgárrame el cubata. Voy a meterle con todo.\nSi sale bien nos retiramos, si sale mal... borramos la app.\n*YOLO!*",
            'COPILOT_ON': "🤝 **COPILOT BRO**\n\nVamos a medias. Yo te paso el call, tú le das al botón de comprar.\n*To the moon!*",
            'WATCHER_ON': "👀 **WATCHER**\n\nEstoy mirando los charts 24/7. Si veo algo que vaya a hacer un x10, te aviso.",
            'STATUS_HEADER': "💎 **DIAMOND HANDS DASHBOARD**",
            'WALLET_HEADER': "💰 **THE BAG**",
            'STATUS_FOOTER': "\n*Scared money don't make money.*",
            'RISK_MSG': (
                "🛡️ **ANTI-REKT SYSTEM**\n\n"
                "*\"Sir, this is a casino.\"*\n\n"
                "Pero traqui, que no vamos a liquidar la cuenta:\n"
                "1. **Circuit Breaker**: Si pierdo 5 seguidas, paro antes de que empeñes el reloj.\n"
                "2. **Stop Loss**: Salimos antes de ser exit liquidity (`{sl_fixed}`).\n"
                "3. **Límite**: Solo apostamos el **{margin}** del stack.\n"
            ),
            'TRADE_LONG': "🚀 **LFG!! COMPRA {asset}**\nSe va a la luna bro, entra ya!\nPrecio: ${price:,.2f}\nAlpha: {reason}\n\n*Green dildos incoming!*",
            'TRADE_SHORT': "📉 **DUMP IT: {asset}**\nEs un rug pull, vende todo!\nPrecio: ${price:,.2f}\nRazón: {reason}\n\n*Have fun staying poor.*",
            'TRADE_CLOSE': "🍗 **CHICKEN DINNER: {asset}** ({side})\nBOOM! A la caja.\nRazón: {reason}\n\n*Pide las botellas! 🍾*",
            'PILOT_ACTION': "🎰 *DEGEN PLAY*\n{msg}",
            'CB_TRIGGER': "📉 **REKT CITY**\n\nMe están cazando los Market Makers (5 loss streak). Paro un rato (Copilot).\n*Necesito un préstamo rápido...* (`/resetpilot`)"
        },

        'DOMINICAN': {
            'NAME': "🇩🇴 Dominican Tigre",
            'WELCOME': (
                "🇩🇴 **DÍMELO CANTANDO**\n"
                "Klk mio, tamo activo o no tamo activo?\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Sistema:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n\n"
                "*Ya prendí los motores. Trae la hookah que vamo' a hacer dinero hoy. El que tenga miedo a morir que no nazca.*"
            ),
            'PILOT_ON': "😎 **SUELTA EL VOLANTE**\n\nDale banda a eso manito, que yo manejo ahora.\nTú tranqui, destapa una fría, que yo te resuelvo esta vuelta. Tamo rulay.",
            'COPILOT_ON': "🤜🤛 **COPILOT KLK**\n\nYo te doy la luz y tú ejecutalas. Trabajando en equipo como debe ser.",
            'WATCHER_ON': "👀 **WATCHER: EN LA LOMA**\n\nEstoy vigilando el bloque. Si veo movimiento raro, te tiro por el DM.",
            'STATUS_HEADER': "🇩🇴 **REPORTE DEL BLOQUE**",
            'WALLET_HEADER': "💸 **LA PACA**",
            'STATUS_FOOTER': "\n*Tamo activo y no de gratis.*",
            'RISK_MSG': (
                "🛡️ **CÓDIGO DE LA CALLE**\n\n"
                "*\"Plata o Plomo... pero mejor Plata.\"*\n\n"
                "Para no quedarnos en olla:\n"
                "1. **Freno de Mano**: Si fallo 5, me paro antes de chocar.\n"
                "2. **Stop Loss**: Cortamo' eso rápido (`{sl_fixed}`).\n"
                "3. **Límite**: No nos volvemo loco, solo el **{margin}** de la paca.\n"
            ),
            'TRADE_LONG': "🔥 **PRENDE ESA VAINA: {asset}**\nCompra ahí que eso sube ahora!\nPrecio: ${price:,.2f}\nMotivo: {reason}\n\n*Esa vuelta ta coroná.*",
            'TRADE_SHORT': "⬇️ **DALE PA'BAJO: {asset}**\nEso se va a desgranar, vende!\nPrecio: ${price:,.2f}\nRazón: {reason}\n\n*Se le viró la torta.*",
            'TRADE_CLOSE': "💸 **CORONAMOS: {asset}** ({side})\nBajó esa grasaaa! Efetivo en mano.\nRazón: {reason}\n\n*Vamo pal resort el fin de semana! 🏖️*",
            'PILOT_ACTION': "🇩🇴 *MOVIMIENTO*\n{msg}",
            'CB_TRIGGER': "guayyyy **SE ME VIRÓ LA TORTA**\n\nDiablo loco, nos dieron una galleta ahí (5 fallos). Mejor lo cogemo suave en Copilot.\n*Tamo en olla... pero tranquilo que ahorita recuperamo.* (`/resetpilot`)"
        },

        'SPANISH': {
            'NAME': "🇪🇸 El Chaval Español",
            'WELCOME': (
                "🇪🇸 **¡QUÉ PASA CHAVALES!**\n"
                "Aquí el Antigravity metiendo caña.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Sistema:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n\n"
                "*Hostia, qué volatilidad hay hoy... ¡Yo flipo! Vamos a sacar pasta o me cago en mis muertos.*"
            ),
            'PILOT_ON': "🏎️ **¡APARTA QUE VOY!**\n\n¡Fuaaa chaval! ¡Sueltame el volante que yo piloto! \nEsto va a ser la hostia. Confía en mí, tío.",
            'COPILOT_ON': "🤜🤛 **COPILOT AL HABLA**\n\nVale tío, vamos a medias. Yo te digo lo que veo y tú decides si entramos. ¡Sin agobios!",
            'WATCHER_ON': "👀 **MODO WATCHER**\n\nMe quedo aquí mirando el percal. Si veo algo guapo te pego un toque.",
            'STATUS_HEADER': "🇪🇸 **REPORTAJE DE LA HOSTIA**",
            'WALLET_HEADER': "💶 **LA CARTERA**",
            'STATUS_FOOTER': "\n*¡A por todas, coño!*",
            'RISK_MSG': (
                "🛡️ **NI UN PASO ATRÁS**\n\n"
                "*\"¡Me cago en la leche se me ha caído el cubata!\"*\n\n"
                "Para no llevarnos una hostia guapa:\n"
                "1. **Freno**: Si palmo 5, paro el carro que me caliento.\n"
                "2. **Stop Loss**: Cortamos rápido (`{sl_fixed}`) para no cagarla.\n"
                "3. **Límite**: Vamos con el **{margin}**, sin hacer el loco.\n"
            ),
            'TRADE_LONG': "🚀 **¡HOSTIA PUTA COMPRA YA: {asset}!**\n¡Esto se va para arriba que flipas! ¡Es la polla!\nPrecio: ${price:,.2f}\nMotivo: {reason}\n\n*¡De puta madre!*",
            'TRADE_SHORT': "📉 **¡ME CAGO EN DIOS: {asset}!**\n¡Esto se hunde! ¡Vende ya coño!\nPrecio: ${price:,.2f}\nRazón: {reason}\n\n*¡A tomar por culo!*",
            'TRADE_CLOSE': "💰 **¡TOMA YA: {asset}!** ({side})\n¡Cerrada! A la saca. ¡Qué buena hostia!\nRazón: {reason}\n\n*¡Olé tus huevos!*",
            'PILOT_ACTION': "🇪🇸 *METIENDO CAÑA*\n{msg}",
            'CB_TRIGGER': "😡 **¡ME CAGO EN SUS MUERTOS!**\n\n5 seguidas palmando. Paro ya que me estoy calentando y le voy a pegar una hostia al monitor.\n*Vamos a relajarnos un poco en Copilot...* (`/resetpilot`)"
        },

        'STANDARD': {
            'NAME': "😐 Estándar",
            'WELCOME': (
                "🤖 **ANTIGRAVITY BOT v3.3**\n"
                "Sistema de Trading Automatizado.\n"
                "〰️〰️〰️〰️〰️〰️〰️\n\n"
                "🔋 *Estado:* `{status_text}` {status_icon}\n"
                "🎮 *Modo:* `{mode}`\n\n"
                "Listo para operar. Seleccione una opción del menú."
            ),
            'PILOT_ON': "✅ **Modo Pilot Activado**\n\nEl bot operará automáticamente según las señales detectadas.\nSupervisión recomendada.",
            'COPILOT_ON': "✅ **Modo Copilot Activado**\n\nEl bot enviará propuestas de trading para su aprobación manual.",
            'WATCHER_ON': "✅ **Modo Watcher Activado**\n\nEl bot solo enviará alertas de mercado. No se ejecutarán operaciones.",
            'STATUS_HEADER': "📊 **REPORTE DE ESTADO**",
            'WALLET_HEADER': "💳 **BALANCE DE CUENTA**",
            'STATUS_FOOTER': "\n*Sistema nominal.*",
            'RISK_MSG': (
                "🛡️ **CONFIGURACIÓN DE RIESGO**\n\n"
                "Parámetros de seguridad actuales:\n"
                "1. **Circuit Breaker**: Detiene operaciones tras 5 pérdidas consecutivas.\n"
                "2. **Stop Loss**: Fijo al `{sl_fixed}` por operación.\n"
                "3. **Margen Global**: Máximo **{margin}** de la cuenta utilizado.\n"
            ),
            'TRADE_LONG': "📈 **SEÑAL DE COMPRA: {asset}**\nDirección: LONG\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_SHORT': "📉 **SEÑAL DE VENTA: {asset}**\nDirección: SHORT\nPrecio: ${price:,.2f}\nRazón: {reason}",
            'TRADE_CLOSE': "🏁 **POSICIÓN CERRADA: {asset}** ({side})\nLa operación ha concluido.\nRazón: {reason}",
            'PILOT_ACTION': "🤖 *ACCIÓN AUTOMÁTICA*\n{msg}",
            'CB_TRIGGER': "⚠️ **CIRCUIT BREAKER ACTIVADO**\n\nSe ha alcanzado el límite de pérdidas consecutivas (5). El sistema ha pasado a modo Seguro (Copilot/Watcher).\nUtilice `/resetpilot` para reiniciar."
        }
    }

    def __init__(self, default_key='NEXUS'):
        self.default_key = default_key

    def get_profile(self, key):
        return self.PROFILES.get(key, self.PROFILES['NEXUS'])

    def get_message(self, key, msg_type, **kwargs):
        """
        Retrieves a formatted message for the given personality key.
        :param key: Personality Key (e.g. 'NEXUS', 'KURTZ')
        :param msg_type: Message Type Key (e.g. 'WELCOME', 'TRADE_LONG')
        :param kwargs: Format arguments
        """
        profile = self.get_profile(key)
        raw_msg = profile.get(msg_type, "")
        
        # Fallback to Nexus if missing
        if not raw_msg:
             raw_msg = self.PROFILES['NEXUS'].get(msg_type, "Message Missing")
             
        try:
            return raw_msg.format(**kwargs)
        except KeyError as e:
            return raw_msg # Return unformatted if args missing (safety)
            
