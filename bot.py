import os
import psycopg2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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
            average_goals FLOAT DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# Función que maneja el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('¡Hola! Soy tu bot de FIFA. Usa /register para agregar jugadores y /start_tournament para iniciar el torneo.')

# Función para registrar jugadores
async def register_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_name = ' '.join(context.args)
    if not player_name:
        await update.message.reply_text('Por favor, usa el formato: /register NombreJugador')
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO statistics (player) VALUES (%s)', (player_name,))
        conn.commit()
        await update.message.reply_text(f'Jugador {player_name} registrado con éxito.')
    except psycopg2.IntegrityError:
        await update.message.reply_text(f'El jugador {player_name} ya está registrado.')
    conn.close()

# Función para iniciar el torneo
async def start_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tournaments DEFAULT VALUES RETURNING id')
    tournament_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    await update.message.reply_text(f'El torneo ha comenzado! Usa /match para registrar los resultados de los partidos. ID del torneo: {tournament_id}')

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
        cursor.execute('SELECT id FROM tournaments WHERE end_date IS NULL ORDER BY start_date DESC LIMIT 1')
        tournament_id = cursor.fetchone()
        if not tournament_id:
            await update.message.reply_text('No hay un torneo en curso.')
            conn.close()
            return

        tournament_id = tournament_id[0]
        cursor.execute('INSERT INTO matches (tournament_id, player1, player2, score1, score2) VALUES (%s, %s, %s, %s, %s)', (tournament_id, player1, player2, score1, score2))
        conn.commit()

        # Actualizar estadísticas
        update_statistics(player1, score1, player2, score2)
        
        await update.message.reply_text(f'Partido registrado: {player1} {score1} - {player2} {score2}')
    except ValueError:
        await update.message.reply_text('Error en el formato de los goles. Deben ser números.')

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

# Función para finalizar el torneo
async def end_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Finalizar el torneo actual
    cursor.execute('UPDATE tournaments SET end_date = CURRENT_TIMESTAMP WHERE end_date IS NULL RETURNING id')
    tournament_id = cursor.fetchone()
    if not tournament_id:
        await update.message.reply_text('No hay un torneo en curso.')
        conn.close()
        return

    tournament_id = tournament_id[0]

    # Obtener estadísticas
    cursor.execute('''
        SELECT player1, SUM(score1) AS total_goals
        FROM matches
        WHERE tournament_id = %s
        GROUP BY player1
        ORDER BY total_goals DESC
        LIMIT 1
    ''', (tournament_id,))
    top_scorer = cursor.fetchone()

    cursor.execute('''
        SELECT player1, SUM(score1) AS total_goals
        FROM matches
        WHERE tournament_id = %s
        GROUP BY player1
        ORDER BY total_goals ASC
        LIMIT 1
    ''', (tournament_id,))
    worst_performance = cursor.fetchone()

    cursor.execute('''
        SELECT player1, AVG(score1) AS average_goals
        FROM matches
        WHERE tournament_id = %s
        GROUP BY player1
        ORDER BY average_goals DESC
        LIMIT 1
    ''', (tournament_id,))
    best_average_goals = cursor.fetchone()

    # Determinar el campeón y la valla menos vencida
    cursor.execute('''
        SELECT player1, COUNT(*) AS wins
        FROM matches
        WHERE tournament_id = %s AND score1 > score2
        GROUP BY player1
        ORDER BY wins DESC
        LIMIT 1
    ''', (tournament_id,))
    champion = cursor.fetchone()

    cursor.execute('''
        SELECT player1, SUM(score2) AS goals_received
        FROM matches
        WHERE tournament_id = %s
        GROUP BY player1
        ORDER BY goals_received ASC
        LIMIT 1
    ''', (tournament_id,))
    best_defense = cursor.fetchone()

    # Mensaje con estadísticas
    message = "Torneo Finalizado!\n\n"
    if top_scorer:
        message += f"Goleador de la fecha: {top_scorer[0]} con {top_scorer[1]} goles\n"
    if worst_performance:
        message += f"Peor desempeño: {worst_performance[0]} con {worst_performance[1]} goles\n"
    if best_average_goals:
        message += f"Mejor promedio de goles: {best_average_goals[0]} con un promedio de {best_average_goals[1]:.2f}\n"
    if champion:
        message += f"Campeón: {champion[0]} con {champion[1]} victorias\n"
    if best_defense:
        message += f"Valla menos vencida: {best_defense[0]} con {best_defense[1]} goles recibidos\n"

    await update.message.reply_text(message)

    conn.close()

# Función para borrar todos los datos
async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Eliminar todos los datos
    cursor.execute('DELETE FROM matches')
    cursor.execute('DELETE FROM statistics')
    cursor.execute('DELETE FROM tournaments')

    conn.commit()
    conn.close()

    await update.message.reply_text('Todos los datos han sido eliminados.')

# Crear y ejecutar el bot
if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('register', register_player))
    application.add_handler(CommandHandler('start_tournament', start_tournament))
    application.add_handler(CommandHandler('match', register_match))
    application.add_handler(CommandHandler('end_tournament', end_tournament))
    application.add_handler(CommandHandler('clear_data', clear_data))

    application.run_polling()
