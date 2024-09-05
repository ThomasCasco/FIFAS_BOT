import os
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, CallbackContext

# Aquí coloca tu token
TOKEN = '7266284922:AAEkwTlo1C4rH74ziFTw8ySQMz8HU1JRGPM'

# Obtener credenciales de la base de datos desde las variables de entorno
DATABASE_URL = os.getenv('DATABASE_URL')

# Crear base de datos y tablas
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournaments (
            id SERIAL PRIMARY KEY,
            start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_date TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER REFERENCES tournaments(id),
            player1 TEXT,
            player2 TEXT,
            score1 INTEGER,
            score2 INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            player TEXT PRIMARY KEY,
            goals INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            average_goals FLOAT DEFAULT 0,
            achievements TEXT DEFAULT '',
            challenges_completed INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id SERIAL PRIMARY KEY,
            name TEXT,
            description TEXT,
            player TEXT REFERENCES statistics(player)
        )
    ''')
    conn.commit()
    conn.close()

# Función que maneja el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton("Registrar Jugador", callback_data='register')],
        [InlineKeyboardButton("Iniciar Torneo", callback_data='start_tournament')],
        [InlineKeyboardButton("Modos de Juego", callback_data='game_modes')],
        [InlineKeyboardButton("Logros", callback_data='achievements')],
        [InlineKeyboardButton("Ayuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text('¡Hola, campeón! ⚽️ Bienvenido al bot de FIFA. ¿Qué te gustaría hacer?', reply_markup=reply_markup)

# Función para manejar los botones del menú principal
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    
    if data == 'register':
        await query.message.reply_text('Por favor, usa el formato: /register NombreJugador')
    elif data == 'start_tournament':
        await start_tournament(update, context)
    elif data == 'game_modes':
        await game_modes(update, context)
    elif data == 'achievements':
        await achievements(update, context)
    elif data == 'help':
        await help_command(update, context)

# Función para registrar jugadores
async def register_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_name = ' '.join(context.args)
    if not player_name:
        await update.message.reply_text('⚠️ Por favor, usa el formato: /register NombreJugador')
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO statistics (player) VALUES (%s)', (player_name,))
        conn.commit()
        await update.message.reply_text(f'¡{player_name} ha sido registrado con éxito! ⚽️')
    except psycopg2.IntegrityError:
        await update.message.reply_text(f'El jugador {player_name} ya está registrado. 📝')
    conn.close()

# Función para iniciar el torneo
async def start_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM tournaments WHERE end_date IS NULL')
    active_tournament = cursor.fetchone()
    
    if active_tournament:
        await update.message.reply_text('⚠️ Ya hay un torneo en curso. Usa /end_tournament para finalizarlo.')
    else:
        cursor.execute('INSERT INTO tournaments DEFAULT VALUES RETURNING id')
        tournament_id = cursor.fetchone()[0]
        conn.commit()
        await update.message.reply_text(f'¡El torneo ha comenzado! 🏁 ID del torneo: {tournament_id} 🏆')
    conn.close()

# Función para registrar un partido
async def register_match(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) != 4:
            await update.message.reply_text('⚠️ Por favor, usa el formato: /match @jugador1 goles1 @jugador2 goles2')
            return
        
        player1, score1, player2, score2 = context.args
        score1, score2 = int(score1), int(score2)

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tournaments WHERE end_date IS NULL ORDER BY start_date DESC LIMIT 1')
        tournament_id = cursor.fetchone()
        if not tournament_id:
            await update.message.reply_text('No hay un torneo en curso. 🏳️')
            conn.close()
            return

        tournament_id = tournament_id[0]
        cursor.execute('INSERT INTO matches (tournament_id, player1, player2, score1, score2) VALUES (%s, %s, %s, %s, %s)', (tournament_id, player1, player2, score1, score2))
        conn.commit()

        # Actualizar estadísticas
        update_statistics(player1, score1, player2, score2)
        
        await update.message.reply_text(f'Partido registrado: {player1} {score1} - {player2} {score2} ⚽️')
    except ValueError:
        await update.message.reply_text('⚠️ Error en el formato de los goles. Deben ser números.')

# Función para finalizar el torneo
async def end_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM tournaments WHERE end_date IS NULL ORDER BY start_date DESC LIMIT 1')
    tournament_id = cursor.fetchone()

    if not tournament_id:
        await update.message.reply_text('No hay torneos en curso para finalizar. 🏳️')
    else:
        tournament_id = tournament_id[0]
        cursor.execute('UPDATE tournaments SET end_date = CURRENT_TIMESTAMP WHERE id = %s', (tournament_id,))
        conn.commit()

        # Mostrar estadísticas del torneo
        await show_tournament_stats(update, tournament_id)

        await update.message.reply_text(f'🏁 El torneo {tournament_id} ha finalizado.')
    conn.close()

# Función para mostrar estadísticas del torneo
async def show_tournament_stats(update: Update, tournament_id) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Obtener estadísticas de los jugadores
    cursor.execute('''
        SELECT player, SUM(goals) as total_goals, SUM(wins) as total_wins, SUM(losses) as total_losses
        FROM matches
        JOIN statistics ON player = ANY (ARRAY[player1, player2])
        WHERE tournament_id = %s
        GROUP BY player
        ORDER BY total_goals DESC
    ''', (tournament_id,))
    stats = cursor.fetchall()
    
    if stats:
        message = "📊 Estadísticas del Torneo 📊\n\n"
        for player, total_goals, total_wins, total_losses in stats:
            message += f"{player}: Goles Totales: {total_goals}, Victorias: {total_wins}, Derrotas: {total_losses}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("No se encontraron estadísticas para este torneo.")
    
    conn.close()

# Función para mostrar logros
async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT player, achievements FROM statistics WHERE achievements != \'\'')
    achievements_data = cursor.fetchall()
    conn.close()

    if achievements_data:
        message = "🏅 Logros de Jugadores 🏅\n\n"
        for player, achievements in achievements_data:
            message += f"{player}: {achievements}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("No hay logros registrados aún. ¡Participa en torneos y gana logros!")

# Función para manejar los modos de juego
async def game_modes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton("Modo 2 Jugadores", callback_data='mode_2')],
        [InlineKeyboardButton("Modo 4 Jugadores", callback_data='mode_4')],
        [InlineKeyboardButton("Modo 6 Jugadores", callback_data='mode_6')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text('Selecciona el modo de juego:', reply_markup=reply_markup)

# Función para aplicar el modo de juego
async def apply_game_mode(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    
    if data == 'mode_2':
        await query.message.reply_text('Modo de juego 2 jugadores seleccionado.')
    elif data == 'mode_4':
        await query.message.reply_text('Modo de juego 4 jugadores seleccionado.')
    elif data == 'mode_6':
        await query.message.reply_text('Modo de juego 6 jugadores seleccionado.')

# Función para actualizar estadísticas
def update_statistics(player1, score1, player2, score2):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Actualizar estadísticas para el jugador 1
    cursor.execute('''
        INSERT INTO statistics (player, goals, wins, losses)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (player)
        DO UPDATE SET goals = statistics.goals + %s, wins = wins + CASE WHEN %s > %s THEN 1 ELSE wins END, losses = losses + CASE WHEN %s < %s THEN 1 ELSE losses END
    ''', (player1, score1, 1 if score1 > score2 else 0, 1 if score1 < score2 else 0, score1, score1, score2, score1, score2))

    # Actualizar estadísticas para el jugador 2
    cursor.execute('''
        INSERT INTO statistics (player, goals, wins, losses)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (player)
        DO UPDATE SET goals = statistics.goals + %s, wins = wins + CASE WHEN %s > %s THEN 1 ELSE wins END, losses = losses + CASE WHEN %s < %s THEN 1 ELSE losses END
    ''', (player2, score2, 1 if score2 > score1 else 0, 1 if score2 < score1 else 0, score2, score2, score1, score2, score1))

    conn.commit()
    conn.close()

# Comando de ayuda
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Comandos disponibles:
/start - Iniciar el bot
/register NombreJugador - Registrar un jugador
/start_tournament - Iniciar un torneo
/end_tournament - Finalizar el torneo actual
/match @jugador1 goles1 @jugador2 goles2 - Registrar un partido
/achievements - Mostrar los logros de los jugadores
/help - Mostrar este mensaje de ayuda
    """
    await update.message.reply_text(help_text)

# Configuración de la aplicación de Telegram
def main():
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()

    # Agregar manejadores de comandos
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('register', register_player))
    application.add_handler(CommandHandler('start_tournament', start_tournament))
    application.add_handler(CommandHandler('match', register_match))
    application.add_handler(CommandHandler('end_tournament', end_tournament))
    application.add_handler(CommandHandler('achievements', achievements))
    application.add_handler(CommandHandler('help', help_command))
    
    # Agregar manejador de botones
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(apply_game_mode))  # Manejador para los modos de juego
    
    # Iniciar la aplicación
    application.run_polling()

if __name__ == '__main__':
    main()
