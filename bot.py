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
    
    conn.commit()
    conn.close()

# Función que maneja el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton("Registrar Partido", callback_data='register_match')],
        [InlineKeyboardButton("Ver Historial", callback_data='historial')],
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
    )
    await update.message.reply_text(help_message)

# Inicializar la aplicación y ejecutar
if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register_player))
    application.add_handler(CommandHandler("match", register_match))
    application.add_handler(CommandHandler("partido_con_apuesta", partido_con_apuesta))
    application.add_handler(CommandHandler("historial", historial))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()
