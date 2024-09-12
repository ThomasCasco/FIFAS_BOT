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

    # Crear tabla de partidos sin relación con torneos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            player1_id INTEGER REFERENCES players(id),
            player2_id INTEGER REFERENCES players(id),
            score1 INTEGER,
            score2 INTEGER
        )
    ''')

    # Crear tabla de estadísticas
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
        [InlineKeyboardButton("Logros", callback_data='achievements')],
        [InlineKeyboardButton("Ayuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text('¡Hola, campeón! ⚽️ Bienvenido al bot de los partidos 1 a 1, ¿qué te gustaría hacer?', reply_markup=reply_markup)

# Función para manejar los botones del menú principal
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data

    if data == 'register':
        await query.message.reply_text('Por favor, usa el formato: /register NombreJugador')
    elif data == 'achievements':
        await achievements(update, context)
    elif data == 'help':
        await help_command(update, context)

# Función para mostrar el historial de enfrentamientos entre dos jugadores
async def consultar_historial_entre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 2:
        await update.message.reply_text('⚠️ Por favor, proporciona los nombres de dos jugadores.')
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

        # Obtener la cantidad de victorias para cada jugador
        cursor.execute('''
            SELECT
                (SELECT COUNT(*) FROM matches WHERE player1_id = %s AND player2_id = %s AND score1 > score2) +
                (SELECT COUNT(*) FROM matches WHERE player1_id = %s AND player2_id = %s AND score2 > score1)
        ''', (player1_id, player2_id, player2_id, player1_id))

        result = cursor.fetchone()

        if result:
            player1_wins = result[0]
            player2_wins = result[1]
        else:
            player1_wins = 0
            player2_wins = 0

        # Mostrar el historial de enfrentamientos
        historial_message = (
            f'📊 Historial de Enfrentamientos entre {player1_name} y {player2_name}:\n'
            f'{player1_name} ha ganado {player1_wins} veces.\n'
            f'{player2_name} ha ganado {player2_wins} veces.'
        )
        await update.message.reply_text(historial_message)
        
    except Exception as e:
        await update.message.reply_text(f'Error al obtener el historial de enfrentamientos: {e}')
    finally:
        conn.close()

# Función para mostrar el historial de partidos global
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

# Función para registrar un partido con apuesta y generar un link de transferencia
async def register_match_apuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) != 6:
            await update.message.reply_text('⚠️ Por favor, usa el formato: /match_apuesta @jugador1 goles1 @jugador2 goles2 monto_apuesta alias')
            return
        
        player1_name, score1, player2_name, score2, monto_apuesta, alias = context.args
        score1, score2 = int(score1), int(score2)
        monto_apuesta = float(monto_apuesta)  # Convertir el monto a número flotante

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Obtener los IDs de los jugadores
        cursor.execute('SELECT id FROM players WHERE name = %s', (player1_name,))
        player1_id = cursor.fetchone()
        cursor.execute('SELECT id FROM players WHERE name = %s', (player2_name,))
        player2_id = cursor.fetchone()

        if player1_id and player2_id:
            player1_id = player1_id[0]
            player2_id = player2_id[0]
            
            # Registrar el partido
            cursor.execute('INSERT INTO matches (player1_id, player2_id, score1, score2) VALUES (%s, %s, %s, %s)', (player1_id, player2_id, score1, score2))
            conn.commit()

            # Actualizar estadísticas
            update_statistics(player1_name, score1, player2_name, score2)

            # Crear un link de transferencia bancaria usando el alias
            link_transferencia = generar_link_transferencia(alias, monto_apuesta)

            await update.message.reply_text(
                f'Partido registrado: {player1_name} {score1} - {player2_name} {score2} ⚽️\n'
                f'Apuesta: {monto_apuesta} ARS\n'
                f'Link de transferencia para {alias}: {link_transferencia}'
            )
        else:
            await update.message.reply_text('Uno o ambos jugadores no están registrados.')
    except ValueError:
        await update.message.reply_text('⚠️ Error en el formato de los goles o el monto de la apuesta. Verifica que los goles sean números enteros y el monto de la apuesta sea un número válido.')
    except Exception as e:
        await update.message.reply_text(f'Error: {e}')
    finally:
        conn.close()

# Función para generar un link de transferencia bancaria
def generar_link_transferencia(alias, monto):
    # Estructura del link de MercadoPago para transferencias directas
    link_transferencia = f"https://www.mercadopago.com.ar"
    return link_transferencia


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

        cursor.execute('SELECT id FROM players WHERE name = %s', (player1_name,))
        player1_id = cursor.fetchone()
        cursor.execute('SELECT id FROM players WHERE name = %s', (player2_name,))
        player2_id = cursor.fetchone()

        if player1_id and player2_id:
            player1_id = player1_id[0]
            player2_id = player2_id[0]
            cursor.execute('INSERT INTO matches (player1_id, player2_id, score1, score2) VALUES (%s, %s, %s, %s)', (player1_id, player2_id, score1, score2))
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
        '/match <jugador1> <goles1> <jugador2> <goles2> - Registra un partido.\n'
        '/consultar_historial_entre <jugador1> <jugador2> - Consulta el historial entre dos jugadores.\n'
        '/historial - Muestra el historial global de partidos.\n'
        '/achievements - Muestra los logros y estadísticas de los jugadores.\n'
    )
    await update.message.reply_text(help_message)

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register_player))
    application.add_handler(CommandHandler("match", register_match))
    application.add_handler(CommandHandler("consultar_historial_entre", consultar_historial_entre))
    application.add_handler(CommandHandler("historial", historial))
    application.add_handler(CommandHandler("achievements", achievements))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()
