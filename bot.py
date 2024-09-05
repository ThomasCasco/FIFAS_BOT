import psycopg2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

# Aquí coloca tu token
TOKEN = '7266284922:AAEkwTlo1C4rH74ziFTw8ySQMz8HU1JRGPM'
# Obtener credenciales de la base de datos desde las variables de entorno
DATABASE_URL = os.getenv('postgresql://postgres:GqFvdCyCCVNFJgqPsWvKWgKuFxYxnYlV@junction.proxy.rlwy.net:57801/railway')

# Crear base de datos y tablas
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            player1 TEXT,
            player2 TEXT,
            score1 INTEGER,
            score2 INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            player TEXT PRIMARY KEY,
            goals INTEGER,
            wins INTEGER,
            losses INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# Función que maneja el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('¡Hola! Soy el bot de fifa de los pibardos, favor de no tardar 1000 horas en hacer formaciones. Usa /register para agregar jugadores y /start_tournament para iniciar el torneo.')

# Función para registrar jugadores
async def register_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_name = ' '.join(context.args)
    if not player_name:
        await update.message.reply_text('Por favor, usa el formato: /register NombreJugador')
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO players (name) VALUES (%s)', (player_name,))
        conn.commit()
        await update.message.reply_text(f'Jugador {player_name} registrado con éxito.')
    except psycopg2.IntegrityError:
        await update.message.reply_text(f'El jugador {player_name} ya está registrado.')
    conn.close()

# Función para iniciar el torneo
async def start_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM players')
    players = [row[0] for row in cursor.fetchall()]
    conn.close()

    if len(players) < 2:
        await update.message.reply_text('Necesitamos al menos 2 jugadores para iniciar el torneo.')
        return

    await update.message.reply_text('El torneo ha comenzado! Usa /match para registrar los resultados de los partidos.')

# Función para registrar un partido
async def register_match(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) != 4:
            await update.message.reply_text('Por favor, usa el formato: /match @jugador1 goles1 @jugador2 goles2')
            return
        
        player1, score1, player2, score2 = context.args
        score1, score2 = int(score1), int(score2)

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO matches (player1, player2, score1, score2) VALUES (%s, %s, %s, %s)', (player1, player2, score1, score2))
        conn.commit()

        # Actualizar estadísticas
        update_statistics(player1, score1, player2, score2)
        
        await update.message.reply_text(f'Partido registrado: {player1} {score1} - {player2} {score2}')
    except ValueError:
        await update.message.reply_text('Error en el formato. Usa: /match @jugador1 goles1 @jugador2 goles2')
    conn.close()

# Función para actualizar las estadísticas
def update_statistics(player1, score1, player2, score2):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Actualizar estadísticas de player1
    cursor.execute('INSERT INTO statistics (player, goals, wins, losses) VALUES (%s, 0, 0, 0) ON CONFLICT (player) DO NOTHING', (player1,))
    cursor.execute('UPDATE statistics SET goals = goals + %s, wins = wins + (CASE WHEN %s > %s THEN 1 ELSE 0 END), losses = losses + (CASE WHEN %s < %s THEN 1 ELSE 0 END) WHERE player = %s', (score1, score1, score2, score1, score2, player1))

    # Actualizar estadísticas de player2
    cursor.execute('INSERT INTO statistics (player, goals, wins, losses) VALUES (%s, 0, 0, 0) ON CONFLICT (player) DO NOTHING', (player2,))
    cursor.execute('UPDATE statistics SET goals = goals + %s, wins = wins + (CASE WHEN %s > %s THEN 1 ELSE 0 END), losses = losses + (CASE WHEN %s < %s THEN 1 ELSE 0 END) WHERE player = %s', (score2, score2, score1, score2, score1, player2))

    conn.commit()
    conn.close()

# Función para mostrar estadísticas
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT player, goals, wins, losses FROM statistics')
    stats = cursor.fetchall()
    conn.close()

    if not stats:
        await update.message.reply_text('No hay estadísticas disponibles todavía.')
        return

    message = "Estadísticas de los jugadores:\n"
    for player, goals, wins, losses in stats:
        message += f'{player}: {goals} goles, {wins} victorias, {losses} derrotas\n'
    
    await update.message.reply_text(message)

def main():
    # Inicializa la aplicación
    app = ApplicationBuilder().token(TOKEN).build()

    # Configurar comandos
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('register', register_player))
    app.add_handler(CommandHandler('start_tournament', start_tournament))
    app.add_handler(CommandHandler('match', register_match))
    app.add_handler(CommandHandler('statistics', show_statistics))

    # Crear base de datos
    init_db()

    # Comienza a recibir actualizaciones de Telegram
    app.run_polling()

if __name__ == '__main__':
    main()


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
