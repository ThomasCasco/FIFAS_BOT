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
    
    # Crear tabla de jugadores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )
    ''')
    
    # Crear tabla de partidos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            player1_id INTEGER REFERENCES players(id),
            player2_id INTEGER REFERENCES players(id),
            score1 INTEGER,
            score2 INTEGER
        )
    ''')
    
    # Crear tabla de apuestas
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
    
    # Crear tabla de estadísticas (logros)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            player TEXT PRIMARY KEY,
            goals INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            experience INTEGER DEFAULT 0 -- Para el sistema de logros y niveles
        )
    ''')
    
    conn.commit()
    conn.close()

# Función para manejar el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton("Registrar Partido", callback_data='register_match')],
        [InlineKeyboardButton("Ver Historial", callback_data='historial')],
        [InlineKeyboardButton("Ver Logros", callback_data='achievements')],
        [InlineKeyboardButton("Ayuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text('¡Bienvenido! ¿Qué te gustaría hacer?', reply_markup=reply_markup)

# Función para manejar los botones del menú principal
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    
    if data == 'register_match':
        await query.message.reply_text('Por favor, usa el formato: /match <jugador1> <goles1> <jugador2> <goles2>')
    elif data == 'historial':
        await historial(update, context)
    elif data == 'achievements':
        await achievements(update, context)
    elif data == 'help':
        await help_command(update, context)

# Función para calcular nivel en base a la experiencia
def calculate_level(experience):
    return experience // 1000  # Cada nivel requiere 1000 XP

# Función para calcular rango en base al nivel
def calculate_rank(level):
    if level <= 5:
        return "Bronce"
    elif level <= 10:
        return "Plata"
    elif level <= 15:
        return "Oro"
    elif level <= 20:
        return "Platino"
    else:
        return "Diamante"

# Función para mostrar los logros (sistema de niveles y rangos)
async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Consultar las estadísticas de los jugadores
    cursor.execute('SELECT player, goals, wins, losses, experience FROM statistics ORDER BY wins DESC, experience DESC')
    results = cursor.fetchall()
    
    achievements_message = '🏆 Logros:\n'
    for player, goals, wins, losses, experience in results:
        level = calculate_level(experience)
        rank = calculate_rank(level)
        achievements_message += f'{player} - Rango: {rank}, Nivel: {level}, Goles: {goals}, Victorias: {wins}, Derrotas: {losses}, XP: {experience}\n'
    
    await update.message.reply_text(achievements_message)
    conn.close()

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

        cursor.execute('INSERT INTO matches (player1_id, player2_id, score1, score2) VALUES (%s, %s, %s, %s)', 
                       (player1_id, player2_id, score1, score2))
        conn.commit()
        await update.message.reply_text(f'Partido registrado: {player1_name} {score1} - {player2_name} {score2}')
        
        # Actualizar estadísticas
        update_statistics(player1_name, score1, player2_name, score2)
        
    except Exception as e:
        await update.message.reply_text(f'Error al registrar partido: {e}')
    finally:
        conn.close()

# Función para actualizar estadísticas de los jugadores
def update_statistics(player1, score1, player2, score2):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    XP_WIN = 100  # Puntos de experiencia por ganar
    XP_LOSS = 20  # Puntos de experiencia por perder
    XP_GOAL = 10  # Puntos por cada gol marcado

    # Actualizar estadísticas del jugador 1
    xp_player1 = (XP_WIN if score1 > score2 else XP_LOSS) + (XP_GOAL * score1)
    cursor.execute('''
        INSERT INTO statistics (player, goals, wins, losses, experience)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (player)
        DO UPDATE SET goals = statistics.goals + %s,
                      wins = statistics.wins + CASE WHEN %s > %s THEN 1 ELSE 0 END,
                      losses = statistics.losses + CASE WHEN %s < %s THEN 1 ELSE 0 END,
                      experience = statistics.experience + %s
    ''', (player1, score1, 1 if score1 > score2 else 0, 1 if score1 < score2 else 0, xp_player1, score1, score1, score2, score1, score2, xp_player1))

    # Actualizar estadísticas del jugador 2
    xp_player2 = (XP_WIN if score2 > score1 else XP_LOSS) + (XP_GOAL * score2)
    cursor.execute('''
        INSERT INTO statistics (player, goals, wins, losses, experience)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (player)
        DO UPDATE SET goals = statistics.goals + %s,
                      wins = statistics.wins + CASE WHEN %s > %s THEN 1 ELSE 0 END,
                      losses = statistics.losses + CASE WHEN %s < %s THEN 1 ELSE 0 END,
                      experience = statistics.experience + %s
    ''', (player2, score2, 1 if score2 > score1 else 0, 1 if score2 < score1 else 0, xp_player2, score2, score2, score1, score2, score1, xp_player2))

    conn.commit()
    conn.close()

# Función para mostrar el historial global de partidos
async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT p1.name, p2.name, m.score1, m.score2
            FROM matches m
            JOIN players p1 ON m.player1_id = p1.id
            JOIN players p2 ON m.player2_id = p2.id
            ORDER BY m.id DESC
        ''')
        matches = cursor.fetchall()
        
        if matches:
            historial_message = '📜 Historial de Partidos:\n'
            for p1, p2, score1, score2 in matches:
                historial_message += f'{p1} {score1} - {p2} {score2}\n'
        else:
            historial_message = 'No se han registrado partidos aún.'
        
        await update.message.reply_text(historial_message)
    except Exception as e:
        await update.message.reply_text(f'Error al consultar el historial: {e}')
    finally:
        conn.close()

# Función para la ayuda
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_message = (
        '📝 Comandos Disponibles:\n'
        '/register <nombre> - Registra un nuevo jugador.\n'
        '/match <jugador1> <goles1> <jugador2> <goles2> - Registra un partido.\n'
        '/partido_con_apuesta <jugador1> <jugador2> <monto> - Registra un partido con apuesta.\n'
        '/historial - Muestra el historial global de partidos.\n'
        '/achievements - Muestra los logros y estadísticas de los jugadores.\n'
    )
    await update.message.reply_text(help_message)

# Inicializar la aplicación y ejecutar
if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register_player))
    application.add_handler(CommandHandler("match", register_match))
    application.add_handler(CommandHandler("achievements", achievements))
    application.add_handler(CommandHandler("historial", historial))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()
