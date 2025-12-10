# Guía de Despliegue en Railway 🚂

Tu proyecto ya está listo para Railway gracias al archivo `Dockerfile` que creamos.

## Pasos para desplegar:

1.  **Sube tu código a GitHub**
    *   Crea un nuevo repositorio en GitHub.
    *   Sube los archivos de este proyecto (asegúrate de que `.env` **NO** se suba, ya está ignorado).

2.  **Crea un proyecto en Railway**
    *   Ve a [railway.app](https://railway.app/).
    *   Haz clic en **"New Project"** > **"Deploy from GitHub repo"**.
    *   Selecciona tu repositorio.

3.  **Configura las Variables de Entorno (IMPORTANTE)**
    *   Una vez creado el proyecto, ve a la pestaña **"Variables"**.
    *   Añade las mismas variables que tienes en tu `.env` local:
        *   `TELEGRAM_TOKEN`: (Tu token)
        *   `TELEGRAM_CHAT_ID`: (Tu ID o lista de IDs separados por comas: `123,456`)

4.  **Verifica el Despliegue**
    *   Railway detectará automáticamente el `Dockerfile` y construirá la imagen.
    *   En la pestaña "Deployments" verás el proceso.
    *   Una vez que diga "Active", revisa los "Logs" para ver: `Bot de Trading iniciado...`.

## Notas:
*   El bot correrá 24/7 en la nube.
*   Si necesitas detenerlo, puedes pausar el servicio en Railway.

## 5. Configuración Avanzada (Binance & Security)

Una vez desplegado, ve a la pestaña **Variables** en Railway y AGREGA las siguientes para activar el trading:

| Variable | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `TELEGRAM_ADMIN_ID` | **(Requerido)** Tu ID personal de Telegram. Solo este ID podrá usar `/long`. | `123456789` |
| `BINANCE_API_KEY` | Tu API Key de Binance Futures. | `vmPUZE...` |
| `BINANCE_SECRET` | Tu Secret Key de Binance Futures. | `NhqPt...` |
| `LEVERAGE` | Apalancamiento para operaciones (x). | `5` |
| `STOP_LOSS_PCT` | Porcentaje de Stop Loss (0.02 = 2%). | `0.02` |
| `MAX_CAPITAL_PCT` | Máximo % de balance a arriesgar por trade. | `0.10` |
| `PROXY_URL` | **(Requerido para IP Estática)** Proxy HTTP. | `http://user:pass@ip:port` |

> **Nota de Seguridad**: Railway encripta estas variables. Para el bot, solo tu `TELEGRAM_ADMIN_ID` tendrá permisos para ejecutar operaciones de compra/venta.
