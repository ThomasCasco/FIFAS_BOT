from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Aquí coloca tu token
TOKEN = '7266284922:AAEkwTlo1C4rH74ziFTw8ySQMz8HU1JRGPM'

# Diccionario para almacenar estadísticas de los jugadores
partidos = []
estadisticas = {}

# Función que maneja el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('¡Hola! Soy tu bot de FIFA. ¡Empecemos a registrar los partidos!')

# Función para registrar un partido
async def registrar_partido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Validar argumentos
        if len(context.args) != 4:
            await update.message.reply_text('Por favor, usa el formato: /partido @jugador1 goles1 @jugador2 goles2')
            return

        jugador1 = context.args[0]
        goles1 = int(context.args[1])
        jugador2 = context.args[2]
        goles2 = int(context.args[3])

        # Almacenar el resultado del partido
        partidos.append((jugador1, goles1, jugador2, goles2))
        actualizar_estadisticas(jugador1, goles1, jugador2, goles2)

        await update.message.reply_text(f'Partido registrado: {jugador1} {goles1} - {jugador2} {goles2}')

    except (IndexError, ValueError):
        await update.message.reply_text('Error en el formato. Usa: /partido @jugador1 goles1 @jugador2 goles2')

# Función para actualizar las estadísticas de los jugadores
def actualizar_estadisticas(jugador1, goles1, jugador2, goles2):
    # Actualizar estadísticas para jugador1
    if jugador1 not in estadisticas:
        estadisticas[jugador1] = {'goles': 0, 'victorias': 0, 'derrotas': 0}
    estadisticas[jugador1]['goles'] += goles1
    if goles1 > goles2:
        estadisticas[jugador1]['victorias'] += 1
    elif goles1 < goles2:
        estadisticas[jugador1]['derrotas'] += 1

    # Actualizar estadísticas para jugador2
    if jugador2 not in estadisticas:
        estadisticas[jugador2] = {'goles': 0, 'victorias': 0, 'derrotas': 0}
    estadisticas[jugador2]['goles'] += goles2
    if goles2 > goles1:
        estadisticas[jugador2]['victorias'] += 1
    elif goles2 < goles1:
        estadisticas[jugador2]['derrotas'] += 1

# Función para mostrar estadísticas de los jugadores
async def mostrar_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not estadisticas:
        await update.message.reply_text('No hay estadísticas disponibles todavía.')
        return

    # Crear un mensaje con las estadísticas
    mensaje = "Estadísticas de los jugadores:\n"
    for jugador, stats in estadisticas.items():
        mensaje += f"{jugador}: {stats['goles']} goles, {stats['victorias']} victorias, {stats['derrotas']} derrotas\n"

    await update.message.reply_text(mensaje)

def main():
    # Inicializa la aplicación
    app = ApplicationBuilder().token(TOKEN).build()

    # Maneja el comando /start
    app.add_handler(CommandHandler('start', start))
    
    # Maneja el comando /partido
    app.add_handler(CommandHandler('partido', registrar_partido))

    # Maneja el comando /estadisticas
    app.add_handler(CommandHandler('estadisticas', mostrar_estadisticas))

    # Comienza a recibir actualizaciones de Telegram
    app.run_polling()

if __name__ == '__main__':
    main()
