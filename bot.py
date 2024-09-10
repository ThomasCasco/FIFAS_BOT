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
            experience INTEGER DEFAULT 0 -- Columna de experiencia para gamificación
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
    await update.message.reply_text('¡Hola, campeón! ⚽️ Bienvenido al bot de los pibardos, estás listo para el FIFA? ¿Qué te gustaría hacer?', reply_markup=reply_markup)

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

# Función para calcular nivel en base a experiencia
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

# Función para mostrar logros y títulos
async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT player, goals, wins, losses, experience FROM statistics ORDER BY wins DESC, goals DESC')
    results = cursor.fetchall()

    # Obtener el jugador con más goles
    cursor.execute('SELECT player, goals FROM statistics ORDER BY goals DESC LIMIT 1')
    top_scorer = cursor.fetchone()
    top_scorer_title = f'⚽ Goleador Supremo: {top_scorer[0]} con {top_scorer[1]} goles.\n' if top_scorer else ''

    achievements_message = '🏆 Logros:\n' + top_scorer_title
    for player, goals, wins, losses, experience in results:
        level = calculate_level(experience)
        rank = calculate_rank(level)
        achievements_message += f'{player} - Rango: {rank}, Nivel: {level}, Goles: {goals}, Victorias: {wins}, Derrotas: {losses}, XP: {experience}\n'

    await update.message.reply_text(achievements_message)
    conn.close()

# Función para mostrar la tabla de clasificación
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT player, experience FROM statistics ORDER BY experience DESC LIMIT 10')
    results = cursor.fetchall()
    
    leaderboard_message = '🏅 Tabla de Clasificación:\n'
    for rank, (player, experience) in enumerate(results, 1):
        level = calculate_level(experience)
        leaderboard_message += f'{rank}. {player} - Nivel {level}, XP: {experience}\n'

    await update.message.reply_text(leaderboard_message)
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
        '/achievements - Muestra los logros y estadísticas de los jugadores.\n'
        '/leaderboard - Muestra la tabla de clasificación (XP).\n'
    )
    await update.message.reply_text(help_message)

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


async def partido_con_apuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 3 or not context.args[2].isdigit():
        await update.message.reply_text('⚠️ Usa el formato: /partido_con_apuesta @jugador1 @jugador2 <monto>')
        return

    player1_name, player2_name, amount = context.args
    amount = int(amount)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

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
    conn.close()

    await update.message.reply_text(f'Apuesta creada entre {player1_name} y {player2_name} por {amount} pesos. ¡Esperando resultado del partido!')



# Función para registrar un partido
async def register_match(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) != 4:
            await update.message.reply_text('⚠️ Usa el formato: /match @jugador1 goles1 @jugador2 goles2')
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

            # Verificar si hay una apuesta
            cursor.execute('SELECT id FROM bets WHERE player1_id = %s AND player2_id = %s AND is_paid = FALSE', (player1_id, player2_id))
            bet = cursor.fetchone()
            if bet:
                winner_id = player1_id if score1 > score2 else player2_id
                cursor.execute('UPDATE bets SET winner_id = %s WHERE id = %s', (winner_id, bet[0]))
                conn.commit()
                await update.message.reply_text(f'Partido registrado: {player1_name} {score1} - {player2_name} {score2}. Se asignó el ganador para la apuesta. Solicita el alias para transferencia con /pagar_apuesta.')

        else:
            await update.message.reply_text('Uno o ambos jugadores no están registrados.')
    except ValueError:
        await update.message.reply_text('⚠️ Error en el formato de los goles. Deben ser números.')
    finally:
        conn.close()

# Función para actualizar estadísticas
def update_statistics(player1, score1, player2, score2):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Definir los puntos de experiencia
    XP_WIN = 100
    XP_LOSS = 20
    XP_GOAL = 10

    # Actualizar estadísticas para el jugador 1
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

    # Actualizar estadísticas para el jugador 2
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

async def pagar_apuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text('⚠️ Usa el formato: /pagar_apuesta <alias>')
        return

    alias = context.args[0]
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Obtener la apuesta no pagada
    cursor.execute('SELECT amount FROM bets WHERE is_paid = FALSE ORDER BY id DESC LIMIT 1')
    bet = cursor.fetchone()

    if bet:
        amount = bet[0]
        # Aquí es donde llamarías a la API de MercadoPago para crear el link de pago
        mercadopago_link = f'https://www.mercadopago.com/pagar?amount={amount}&alias={alias}'
        await update.message.reply_text(f'Por favor, realiza la transferencia usando este link: {mercadopago_link}')
        
        # Marcar la apuesta como pagada
        cursor.execute('UPDATE bets SET is_paid = TRUE WHERE id = (SELECT id FROM bets ORDER BY id DESC LIMIT 1)')
        conn.commit()
    else:
        await update.message.reply_text('No hay apuestas pendientes.')

    conn.close()

# Función para mostrar el historial de partidos
async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT p1.name, p2.name, m.score1, m.score2, t.start_date
            FROM matches m
            JOIN players p1 ON m.player1_id = p1.id
            JOIN players p2 ON m.player2_id = p2.id
            JOIN tournaments t ON m.tournament_id = t.id
            ORDER BY t.start_date DESC
        ''')
        matches = cursor.fetchall()
        
        if matches:
            historial_message = '📜 Historial de Partidos:\n'
            for p1, p2, score1, score2, start_date in matches:
                historial_message += f'{start_date}: {p1} {score1} - {p2} {score2}\n'
        else:
            historial_message = 'No se han registrado partidos aún.'
        
        await update.message.reply_text(historial_message)
    except Exception as e:
        await update.message.reply_text(f'Error al consultar el historial: {e}')
    finally:
        conn.close()

# Función para consultar el historial de enfrentamientos entre dos jugadores
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

        # Consulta del historial
        cursor.execute('''
            SELECT
                SUM(CASE WHEN player1_id = %s AND score1 > score2 THEN 1 ELSE 0 END) AS player1_wins,
                SUM(CASE WHEN player2_id = %s AND score2 > score1 THEN 1 ELSE 0 END) AS player2_wins
            FROM matches
            WHERE (player1_id = %s AND player2_id = %s) OR (player1_id = %s AND player2_id = %s)
        ''', (player1_id, player2_id, player1_id, player2_id, player2_id, player1_id))
        
        result = cursor.fetchone()
        player1_wins = result[0] if result[0] is not None else 0
        player2_wins = result[1] if result[1] is not None else 0

        # Mostrar el historial de enfrentamientos
        historial_message = (
            f'📊 Historial de Enfrentamientos entre {player1_name} y {player2_name}:\n'
            f'{player1_name} ha ganado {player1_wins} veces contra {player2_name}.\n'
            f'{player2_name} ha ganado {player2_wins} veces contra {player1_name}.'
        )
        await update.message.reply_text(historial_message)
        
    except Exception as e:
        await update.message.reply_text(f'Error al obtener el historial de enfrentamientos: {e}')
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
    application.add_handler(CommandHandler("end_tournament", end_tournament))
    application.add_handler(CommandHandler("historial", historial))
    application.add_handler(CommandHandler("consultar_historial_entre", consultar_historial_entre))
    application.add_handler(CommandHandler("achievements", achievements))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("pagar_apuesta", pagar_apuesta))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()
