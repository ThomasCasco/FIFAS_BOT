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
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_players (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER REFERENCES tournaments(id),
            player_id INTEGER REFERENCES players(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER REFERENCES tournaments(id),
            player1_id INTEGER REFERENCES players(id),
            player2_id INTEGER REFERENCES players(id),
            score1 INTEGER,
            score2 INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            player TEXT PRIMARY KEY,
            goals INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# Función que maneja el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton("Registrar Jugador", callback_data='register')],
        [InlineKeyboardButton("Iniciar Torneo", callback_data='start_tournament')],
        [InlineKeyboardButton("Foto de la cola de valen", callback_data='game_modes')],
        [InlineKeyboardButton("Logros", callback_data='achievements')],
        [InlineKeyboardButton("Ayuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text('¡Hola, campeón! ⚽️ Bienvenido al bot de los pibardos, estás listo para el FIFA? ¿Qué te gustaría hacer?', reply_markup=reply_markup)

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

# Función para consultar el historial entre dos jugadores
async def consultar_historial_entre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Verificar que se pasen exactamente dos argumentos (nombres de los jugadores)
    if len(context.args) != 2:
        await update.message.reply_text('⚠️ Usa el formato: /consultar_historial_entre @jugador1 @jugador2')
        return

    player1_name, player2_name = context.args

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Obtener los IDs de los jugadores
        cursor.execute('SELECT id FROM players WHERE name = %s', (player1_name,))
        player1_id = cursor.fetchone()
        cursor.execute('SELECT id FROM players WHERE name = %s', (player2_name,))
        player2_id = cursor.fetchone()

        if not player1_id or not player2_id:
            await update.message.reply_text('Uno o ambos jugadores no están registrados.')
            return

        player1_id = player1_id[0]
        player2_id = player2_id[0]

        # Consultar cuántas veces ganó cada jugador contra el otro
        cursor.execute('''
            SELECT 
                (SELECT COUNT(*) FROM matches WHERE player1_id = %s AND player2_id = %s AND score1 > score2) AS player1_wins,
                (SELECT COUNT(*) FROM matches WHERE player1_id = %s AND player2_id = %s AND score1 < score2) AS player2_wins
        ''', (player1_id, player2_id, player1_id, player2_id))
        
        result = cursor.fetchone()
        player1_wins, player2_wins = result
        
        # Mostrar el historial de enfrentamientos
        historial_message = (
            f'📊 Historial de Enfrentamientos entre {player1_name} y {player2_name}:\n'
            f'{player1_name} ha ganado {player1_wins} veces contra {player2_name}.\n'
            f'{player2_name} ha ganado {player2_wins} veces contra {player1_name}.'
        )
        await update.message.reply_text(historial_message)
        
    except Exception as e:
        await update.message.reply_text(f'Error al consultar el historial: {e}')
    finally:
        conn.close()

# Función para registrar jugadores
async def register_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_name = ' '.join(context.args)
    if not player_name:
        await update.message.reply_text('⚠️ Por favor, usa el formato: /register NombreJugador')
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO players (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id', (player_name,))
        player_id = cursor.fetchone()
        conn.commit()
        
        if player_id:
            await update.message.reply_text(f'¡{player_name} ha sido registrado con éxito! ⚽️')
        else:
            await update.message.reply_text(f'El jugador {player_name} ya está registrado. 📝')
    except Exception as e:
        await update.message.reply_text(f'Error: {e}')
    conn.close()

# Función para iniciar el torneo
async def start_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text('⚠️ Por favor, usa el formato: /start_tournament <número de participantes>')
        return

    num_participants = int(context.args[0])
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM tournaments WHERE end_date IS NULL')
    active_tournament = cursor.fetchone()
    
    if active_tournament:
        await update.message.reply_text('⚠️ Ya hay un torneo en curso. Usa /end_tournament para finalizarlo.')
        conn.close()
        return

    cursor.execute('INSERT INTO tournaments DEFAULT VALUES RETURNING id')
    tournament_id = cursor.fetchone()[0]
    conn.commit()

    # Guardar el modo de torneo
    if num_participants <= 4:
        mode = 'Eliminación'
    else:
        mode = 'Todos contra todos'
    
    cursor.execute('INSERT INTO tournament_modes (tournament_id, mode) VALUES (%s, %s)', (tournament_id, mode))
    conn.commit()

    await update.message.reply_text(f'¡El torneo ha comenzado! 🏁 ID del torneo: {tournament_id} 🏆\nModo: {mode}\nPor favor, registra a los jugadores usando el comando /register_player <nombre>')
    conn.close()

# Función para registrar un partido
async def register_match(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) != 4:
            await update.message.reply_text('⚠️ Por favor, usa el formato: /match @jugador1 goles1 @jugador2 goles2')
            return
        
        player1_name, score1, player2_name, score2 = context.args
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
        cursor.execute('SELECT id FROM players WHERE name = %s', (player1_name,))
        player1_id = cursor.fetchone()
        cursor.execute('SELECT id FROM players WHERE name = %s', (player2_name,))
        player2_id = cursor.fetchone()

        if player1_id and player2_id:
            player1_id = player1_id[0]
            player2_id = player2_id[0]
            cursor.execute('INSERT INTO matches (tournament_id, player1_id, player2_id, score1, score2) VALUES (%s, %s, %s, %s, %s)', (tournament_id, player1_id, player2_id, score1, score2))
            conn.commit()

            # Actualizar estadísticas
            update_statistics(player1_name, score1, player2_name, score2)
            
            await update.message.reply_text(f'Partido registrado: {player1_name} {score1} - {player2_name} {score2} ⚽️')
        else:
            await update.message.reply_text('Uno o ambos jugadores no están registrados.')
    except ValueError:
        await update.message.reply_text('⚠️ Error en el formato de los goles. Deben ser números.')

# Función para actualizar estadísticas
def update_statistics(player1, score1, player2, score2):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Actualizar estadísticas para el jugador 1
    cursor.execute('''
        INSERT INTO statistics (player, goals, wins, losses)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (player)
        DO UPDATE SET goals = statistics.goals + %s,
                      wins = statistics.wins + CASE WHEN %s > %s THEN 1 ELSE 0 END,
                      losses = statistics.losses + CASE WHEN %s < %s THEN 1 ELSE 0 END
    ''', (player1, score1, 1 if score1 > score2 else 0, 1 if score1 < score2 else 0, score1, score1, score2, score1, score2))

    # Actualizar estadísticas para el jugador 2
    cursor.execute('''
        INSERT INTO statistics (player, goals, wins, losses)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (player)
        DO UPDATE SET goals = statistics.goals + %s,
                      wins = statistics.wins + CASE WHEN %s > %s THEN 1 ELSE 0 END,
                      losses = statistics.losses + CASE WHEN %s < %s THEN 1 ELSE 0 END
    ''', (player2, score2, 1 if score2 > score1 else 0, 1 if score2 < score1 else 0, score2, score2, score1, score2, score1))

    conn.commit()
    conn.close()

# Función para finalizar el torneo
async def end_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM tournaments WHERE end_date IS NULL ORDER BY start_date DESC LIMIT 1')
    tournament_id = cursor.fetchone()

    if tournament_id:
        tournament_id = tournament_id[0]
        cursor.execute('UPDATE tournaments SET end_date = CURRENT_TIMESTAMP WHERE id = %s', (tournament_id,))
        conn.commit()

        # Obtener estadísticas finales
        cursor.execute('''
            SELECT player, goals, wins, losses
            FROM statistics
        ''')
        results = cursor.fetchall()

        stats_message = '📊 Estadísticas Finales del Torneo:\n'
        for player, goals, wins, losses in results:
            stats_message += f'{player} - Goles: {goals}, Victorias: {wins}, Derrotas: {losses}\n'

        await update.message.reply_text(f'El torneo con ID {tournament_id} ha finalizado. 🏆\n{stats_message}')
    else:
        await update.message.reply_text('No hay torneos en curso.')

    conn.close()

# Función para mostrar los modos de juego
async def game_modes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    modes_message = (
        '🔢 Modos de Torneo:\n'
        '- Eliminación: Cada jugador es eliminado después de una derrota.\n'
        '- Todos contra todos: Todos los jugadores se enfrentan entre sí.\n'
    )
    await update.message.reply_text(modes_message)

# Función para mostrar los logros
async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT player, goals, wins, losses FROM statistics ORDER BY wins DESC, goals DESC')
    results = cursor.fetchall()
    
    achievements_message = '🏆 Logros:\n'
    for player, goals, wins, losses in results:
        achievements_message += f'{player} - Goles: {goals}, Victorias: {wins}, Derrotas: {losses}\n'
    
    await update.message.reply_text(achievements_message)
    conn.close()

# Función para la ayuda
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_message = (
        '📝 Comandos Disponibles:\n'
        '/start - Inicia el bot y muestra el menú principal.\n'
        '/register <nombre> - Registra un nuevo jugador.\n'
        '/start_tournament <número de participantes> - Inicia un nuevo torneo.\n'
        '/match <jugador1> <goles1> <jugador2> <goles2> - Registra un partido.\n'
        '/end_tournament - Finaliza el torneo actual.\n'
        '/game_modes - Muestra los modos de juego disponibles.\n'
        '/achievements - Muestra los logros y estadísticas de los jugadores.\n'
    )
    await update.message.reply_text(help_message)

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register_player))
    application.add_handler(CommandHandler("start_tournament", start_tournament))
    application.add_handler(CommandHandler("match", register_match))
    application.add_handler(CommandHandler("end_tournament", end_tournament))
    application.add_handler(CommandHandler("game_modes", game_modes))
    application.add_handler(CommandHandler("achievements", achievements))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("consultar_historial_entre", consultar_historial_entre))  # Añadir el nuevo comando aquí
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()
