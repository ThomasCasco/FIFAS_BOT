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
        CREATE TABLE IF NOT EXISTS bets (
            id SERIAL PRIMARY KEY,
            player1_id INTEGER REFERENCES players(id),
            player2_id INTEGER REFERENCES players(id),
            amount INTEGER,
            winner_id INTEGER,
            is_paid BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            player TEXT PRIMARY KEY,
            goals INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            experience INTEGER DEFAULT 0
        )
    ''')

    # Crear la tabla 'tournament_modes' para almacenar el modo de torneo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_modes (
            id SERIAL PRIMARY KEY,
            tournament_id INTEGER REFERENCES tournaments(id),
            mode TEXT
        )
    ''')

    conn.commit()
    conn.close()

# Función que maneja el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton("Iniciar Torneo", callback_data='start_tournament')],
        [InlineKeyboardButton("Logros", callback_data='achievements')],
        [InlineKeyboardButton("Leaderboard", callback_data='leaderboard')],
        [InlineKeyboardButton("Ayuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text('¡Hola, campeón! ⚽️ Bienvenido al bot de los pibardos. ¿Qué te gustaría hacer?', reply_markup=reply_markup)

# Función para manejar los botones del menú principal
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    
    if data == 'start_tournament':
        await start_tournament(update, context)
    elif data == 'achievements':
        await achievements(update, context)
    elif data == 'leaderboard':
        await leaderboard(update, context)
    elif data == 'help':
        await help_command(update, context)

# Función para registrar jugadores
async def register_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text('⚠️ Usa el formato: /register <nombre>')
        return
    
    player_name = context.args[0]
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO players (name) VALUES (%s) ON CONFLICT (name) DO NOTHING', (player_name,))
        conn.commit()
        await update.message.reply_text(f'Jugador {player_name} registrado con éxito.')
    except Exception as e:
        await update.message.reply_text(f'Error al registrar jugador: {e}')
    finally:
        conn.close()

# Función para iniciar el torneo
async def start_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text('⚠️ Usa el formato: /start_tournament <número de participantes>')
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

    # Guardar el modo de torneo basado en la cantidad de participantes
    mode = 'Eliminación' if num_participants <= 4 else 'Todos contra todos'
    cursor.execute('INSERT INTO tournament_modes (tournament_id, mode) VALUES (%s, %s)', (tournament_id, mode))
    conn.commit()

    await update.message.reply_text(f'Torneo iniciado con {num_participants} participantes. ID del torneo: {tournament_id}. Modo: {mode}')
    conn.close()

# Función para registrar un partido
async def register_match(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 4:
        await update.message.reply_text('⚠️ Usa el formato: /match <jugador1> <goles1> <jugador2> <goles2>')
        return

    player1_name, score1, player2_name, score2 = context.args
    score1, score2 = int(score1), int(score2)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT id FROM players WHERE name = %s', (player1_name,))
        player1_id = cursor.fetchone()

        cursor.execute('SELECT id FROM players WHERE name = %s', (player2_name,))
        player2_id = cursor.fetchone()

        if not player1_id or not player2_id:
            await update.message.reply_text('Uno o ambos jugadores no están registrados.')
            return

        player1_id = player1_id[0]
        player2_id = player2_id[0]

        cursor.execute('SELECT id FROM tournaments WHERE end_date IS NULL LIMIT 1')
        tournament = cursor.fetchone()
        if tournament:
            tournament_id = tournament[0]
            cursor.execute('INSERT INTO matches (tournament_id, player1_id, player2_id, score1, score2) VALUES (%s, %s, %s, %s, %s)',
                           (tournament_id, player1_id, player2_id, score1, score2))
            conn.commit()
            await update.message.reply_text(f'Partido registrado: {player1_name} {score1} - {player2_name} {score2}')
        else:
            await update.message.reply_text('No hay un torneo activo.')

    except Exception as e:
        await update.message.reply_text(f'Error al registrar partido: {e}')
    finally:
        conn.close()

# Función para crear apuestas
async def partido_con_apuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 3 or not context.args[2].isdigit():
        await update.message.reply_text('⚠️ Usa el formato: /partido_con_apuesta <jugador1> <jugador2> <monto>')
        return

    player1_name, player2_name, amount = context.args
    amount = int(amount)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT id FROM players WHERE name = %s', (player1_name,))
        player1_id = cursor.fetchone()

        cursor.execute('SELECT id FROM players WHERE name = %s', (player2_name,))
        player2_id = cursor.fetchone()

        if not player1_id or not player2_id:
            await update.message.reply_text('Uno o ambos jugadores no están registrados.')
            return

        player1_id = player1_id[0]
        player2_id = player2_id[0]

        cursor.execute('INSERT INTO bets (player1_id, player2_id, amount) VALUES (%s, %s, %s)', (player1_id, player2_id, amount))
        conn.commit()
        await update.message.reply_text(f'Apuesta registrada entre {player1_name} y {player2_name} por {amount} pesos.')
    except Exception as e:
        await update.message.reply_text(f'Error al registrar apuesta: {e}')
    finally:
        conn.close()

# Inicializar la aplicación y ejecutar
if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register_player))
    application.add_handler(CommandHandler("start_tournament", start_tournament))
    application.add_handler(CommandHandler("match", register_match))
    application.add_handler(CommandHandler("partido_con_apuesta", partido_con_apuesta))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()
