from fasthtml.common import *
import json
import random
import sqlite3
import uuid
import os

# Load data from JSONL file
with open('initial_class_list.jsonl', 'r') as f:
    data = json.loads(f.read())

# Create pairs of real and fake classes
pairs = []
real_classes = [cls for cls in data if cls["real"] == True]
fake_classes = [cls for cls in data if cls["real"] == False]

# Create pairs with unique IDs
for i in range(min(len(real_classes), len(fake_classes))):
    pair_id = i + 1
    pairs.append({
        "id": pair_id,
        "real_class": real_classes[i],
        "fake_class": fake_classes[i]
    })

# Set up SQLite database
DB_PATH = "data/game_stats.db"
db_exists = os.path.exists(DB_PATH)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database if it doesn't exist
if not db_exists:
    conn = get_db()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS guesses (
        id INTEGER PRIMARY KEY,
        guesser_id TEXT NOT NULL,
        pair_id INTEGER NOT NULL,
        correct BOOLEAN NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY,
        guesser_id TEXT NOT NULL,
        score INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def record_guess(guesser_id, pair_id, correct):
    """Record a user's guess in the database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO guesses (guesser_id, pair_id, correct) VALUES (?, ?, ?)",
        (guesser_id, pair_id, correct)
    )
    conn.commit()
    conn.close()

def record_game(guesser_id, score, total_questions):
    """Record a completed game in the database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO games (guesser_id, score, total_questions) VALUES (?, ?, ?)",
        (guesser_id, score, total_questions)
    )
    conn.commit()
    conn.close()

def get_pair_stats(pair_id):
    """Get statistics for a specific pair"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get total guesses for this pair
    cursor.execute("SELECT COUNT(*) FROM guesses WHERE pair_id = ?", (pair_id,))
    total_guesses = cursor.fetchone()[0]
    
    # Get correct guesses for this pair
    cursor.execute("SELECT COUNT(*) FROM guesses WHERE pair_id = ? AND correct = 1", (pair_id,))
    correct_guesses = cursor.fetchone()[0]
    
    conn.close()
    
    percent_correct = 0
    if total_guesses > 0:
        percent_correct = int((correct_guesses / total_guesses) * 100)
        
    return {
        "total_guesses": total_guesses,
        "correct_guesses": correct_guesses,
        "percent_correct": percent_correct
    }

def get_percentile(score, total_questions):
    """Calculate percentile of a user's score compared to all other completed games"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get total completed games
    cursor.execute("SELECT COUNT(*) FROM games WHERE total_questions = ?", (total_questions,))
    total_games = cursor.fetchone()[0]
    
    if total_games == 0:
        return 50  # Default to 50th percentile if no other games
    
    # Get number of games with lower or equal scores (normalized by percentage)
    score_percent = (score / total_questions) * 100
    cursor.execute(
        "SELECT COUNT(*) FROM games WHERE total_questions = ? AND (score * 100.0 / total_questions) <= ?", 
        (total_questions, score_percent)
    )
    games_lower_or_equal = cursor.fetchone()[0]
    
    conn.close()
    
    # Calculate percentile (higher is better)
    percentile = int((games_lower_or_equal / total_games) * 100)
    
    # If no data yet, use a random value as fallback
    if percentile == 0:
        percentile = random.randint(max(int(score_percent)-15, 10), min(int(score_percent)+15, 95))
        
    return percentile

css = Style(""".option-card {
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .option-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }
        .fade-in {
            animation: fadeIn 0.5s ease-in-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }""")

hdrs = [Script(src="https://cdn.tailwindcss.com"), css]
app, rt = fast_app(pico=False, surreal=False, hdrs=hdrs)

def QuestionOption(o, is_real, pair_id, option_num):
    return Div(
            H3(o['class_name'], cls='text-xl font-semibold text-indigo-600 mb-3'),
            P(o['description'], cls='text-gray-700 mb-4'),
            hx_post='submit_answer',
            hx_vals=f'{{"chosen": "{option_num}", "is_real": "{str(is_real).lower()}", "pair_id": "{pair_id}"}}',
            hx_target='#quiz-content',
            hx_swap='innerHTML',
            cls='option-card bg-white rounded-lg shadow-md p-6 cursor-pointer'
        )

def Question(pair, randomize=True):
    real_class = pair["real_class"]
    fake_class = pair["fake_class"]
    pair_id = pair["id"]
    
    # Randomly decide which option appears first
    if randomize and random.random() > 0.5:
        return Div(
            QuestionOption(fake_class, False, pair_id, 0),
            QuestionOption(real_class, True, pair_id, 1),
            cls='grid md:grid-cols-2 gap-6'
        )
    else:
        return Div(
            QuestionOption(real_class, True, pair_id, 0),
            QuestionOption(fake_class, False, pair_id, 1),
            cls='grid md:grid-cols-2 gap-6'
        )

def ResultDiv(real_class, correct, pair_id,is_final=False):
    # Set result details based on whether they got it right
    if correct:
        result_icon = "✓"
        result_color = "text-green-500" 
        result_text = "Correct!"
        result_text_color = "text-green-600"
    else:
        result_icon = "✗"
        result_color = "text-red-500"
        result_text = "Incorrect!"
        result_text_color = "text-red-600"
    
    # Get stats from database
    stats = get_pair_stats(pair_id)
    percent_correct = stats["percent_correct"]
    
    # If no data yet, use a reasonable default
    if stats["total_guesses"] < 2:
        percent_correct = random.randint(60, 95)
    
    return Div(
        Div(
            Div(result_icon, cls=f'{result_color} text-6xl mb-4'),
            H3(result_text, cls=f'text-2xl font-bold mb-2 {result_text_color}'),
            P(f'{real_class["class_name"]} is the real class', cls='text-gray-700 mb-2 text-lg font-medium'),
            P(f'Course Code: {real_class["class_code"]}', cls='text-gray-700 mb-4'),
            P(f'{percent_correct}% of players got this right', cls='text-gray-500 text-sm mb-4'),
            cls='mb-6'
        ),
        Button('Next Question' if not is_final else 'View Results',
               hx_get='/next_question', hx_target='#quiz-content', hx_swap='innerHTML', 
               cls='bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-6 rounded-lg transition duration-300 shadow-md',
               id='next-button'),
        Script("document.addEventListener('keydown', function(e) { if (e.key === 'Enter') { document.getElementById('next-button')?.click(); } });"),
        cls='bg-white rounded-lg shadow-md p-8 text-center max-w-2xl mx-auto'
    )

def FinalResults(session):
    # Make sure user has a unique ID
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    # Calculate score
    if 'correct' not in session:
        session['correct'] = 0
    
    total_questions = len(session.get('done', []))
    score = session.get('correct', 0)
    
    # Record the completed game in the database
    record_game(session['user_id'], score, total_questions)
    
    # Calculate percentage
    if total_questions > 0: score_percent = int((score / total_questions) * 100)
    else: score_percent = 0
    
    # Get real percentile from database
    percentile = get_percentile(score, total_questions)
    
    return Div(
        H2('Quiz Complete!', cls='text-3xl font-bold text-indigo-600 mb-4'),
        P(
            'Your Score: ',
            Span(f'{score}/{total_questions}', cls='font-bold'),
            cls='text-xl mb-6'
        ),
        Div(
            Div(
                Div(style=f'width: {score_percent}%', cls='bg-indigo-600 h-4 rounded-full transition-all duration-500'),
                cls='w-full bg-gray-200 rounded-full h-4 mb-2'
            ),
            P(f'You did better than {percentile}% of players!', cls='text-gray-600'),
            cls='mb-8'
        ),
        Button('Play Again', hx_get='/restart', hx_target='#quiz-content', hx_swap='innerHTML', cls='bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg transition duration-300 shadow-md'),
        cls='bg-white rounded-lg shadow-md p-8 text-center max-w-2xl mx-auto'
    )

@rt
def index(session):
    # Make sure user has a unique ID
    if 'user_id' not in session: session['user_id'] = str(uuid.uuid4())
    
    # Build up the main page
    header = Header(
            H1('Which Class Is Real?', cls='text-4xl font-bold text-indigo-600 mb-2'),
            P('PCC has such a great ', 
            A('class list', href='https://www.pcc.edu/community/wp-content/uploads/sites/202/2019/11/SP25_PCC_CED_021425.pdf'), 
             ' that this quiz had to exist. See how well you can do at spotting the fakes!', cls='text-gray-600 mb-6'),
            Div(
                Div(id='progress-bar', style='width: 0%', cls='bg-indigo-600 h-2.5 rounded-full transition-all duration-500'),
                cls='w-full bg-gray-200 rounded-full h-2.5 mb-4'
            ),
            P('Question ', Span('0', id='current-question'), ' of 20',cls='text-sm text-gray-500'),
            cls='text-center mb-8'
        )
    footer = Footer(
            P('© 2025 Jonathan Whitaker. ', 
            A('Code on GitHub', href='https://github.com/johnowhitaker/community_got_class', cls='text-indigo-600 hover:underline'),),
            cls='mt-12 text-center text-gray-500 text-sm'
        ),  
    main = Main(
            Div(
                P('Try to guess which classes are actually offered at our local community college!', cls='text-lg mb-6'),
                Button(
                    'Start Quiz' if 'done' not in session else 'Resume Quiz', 
                    hx_get='next_question', hx_target='#quiz-content', hx_swap='innerHTML', 
                    cls='bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg transition duration-300 shadow-md'),
                id='start-screen',
                cls='text-center py-8'
            ),
            id='quiz-content',
            cls='fade-in'
        ),

    return Title("Community College Got Class"), Body(
        Div(header, main, footer, cls='container mx-auto px-4 py-8 max-w-5xl'),
        cls='bg-gray-100 min-h-screen font-sans text-gray-800')

@rt
def next_question(session):
    # Initialize session if needed
    if 'done' not in session:  session['done'] = []
    if 'correct' not in session: session['correct'] = 0
    
    # If they've done all questions, show final results
    total_questions = min(20, len(pairs))  # Cap at 20 questions
    if len(session['done']) >= total_questions:
        return FinalResults(session)
    
    # Pick a random pair that hasn't been used yet
    available_ids = [p['id'] for p in pairs if p['id'] not in session['done']]
    if not available_ids:  # If somehow we run out (shouldn't happen with our cap)
        return FinalResults(session)
    pair_id = random.choice(available_ids)
    pair = next(p for p in pairs if p['id'] == pair_id)
    
    # Update progress bar and question counter
    question_num = len(session['done']) + 1
    progress_percent = int((question_num / total_questions) * 100)
    
    return [Question(pair),
            Div('', id='progress-bar', style=f'width: {progress_percent}%', 
                cls='bg-indigo-600 h-2.5 rounded-full transition-all duration-500', 
                hx_swap_oob='true'),
            Span(f'{question_num}', id='current-question', hx_swap_oob='true')]

@rt
def submit_answer(session, chosen:str, is_real:str, pair_id:str):
    # Make sure user has a unique ID
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    # Convert types and add to done list
    pair_id = int(pair_id)
    
    # Add to done list if not already there
    if pair_id not in session['done']:
        session['done'].append(pair_id)
    
    # Determine if they chose correctly
    # is_real tells us if the option they chose is real or fake
    correct = (is_real == "true")
    if correct and 'correct' in session:
        session['correct'] += 1
    
    # Record this guess in the database
    record_guess(session['user_id'], pair_id, correct)
    
    # Find the real class for this pair
    pair = next(p for p in pairs if p['id'] == pair_id)
    real_class = pair['real_class']

    # Check if that was the last question
    total_questions = min(20, len(pairs))
    is_final = len(session['done']) >= total_questions
    
    return ResultDiv(real_class, correct, pair_id, is_final)

@rt
def restart(session):
    # Reset session
    session['done'] = []
    session['correct'] = 0
    session['user_id'] = str(uuid.uuid4())+"-restart"
    
    # Reset progress indicators
    result = [
        Div(
            P('Try to guess which classes are actually offered at our local community college!', cls='text-lg mb-6'),
            Button('Start Quiz', hx_get='next_question', hx_target='#quiz-content', hx_swap='innerHTML', 
                   cls='bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg transition duration-300 shadow-md'),
            cls='text-center py-8'
        ),
        Div('', id='progress-bar', style='width: 0%', 
            cls='bg-indigo-600 h-2.5 rounded-full transition-all duration-500', 
            hx_swap_oob='true'),
        Span('0', id='current-question', hx_swap_oob='true')
    ]
    
    return result

serve()