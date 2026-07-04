from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import time
from config import Config
from analytics.score_analysis import get_quiz_stats, get_top_students

app = Flask(__name__)
app.config.from_object(Config)

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User Class
class User(UserMixin):
    def __init__(self, id, username, is_admin):
        self.id = id
        self.username = username
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['is_admin'])
    return None

# Database Helper
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        return conn
    except mysql.connector.Error as err:
        flash(f'Database connection error: {err}', 'danger')
        return None

# --- Routes: Authentication ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return render_template('register.html')
            
        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        if not conn:
            return render_template('register.html')
            
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)", 
                           (username, email, hashed_pw))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f'Error: {err}', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
            return render_template('login.html')
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            print("LOGIN USER =", user)
            print("LOGIN ADMIN =", user['is_admin'])
            user_obj = User(user['id'], user['username'], user['is_admin'])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check credentials.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Routes: Student ---

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    if not conn:
        return render_template('dashboard.html', history=[])
        
    cursor = conn.cursor(dictionary=True)
    
    # Get user history with quiz titles
    cursor.execute("""
        SELECT r.*, q.title as quiz_title 
        FROM results r 
        JOIN quizzes q ON r.quiz_id = q.id 
        WHERE r.user_id = %s 
        ORDER BY r.created_at DESC
    """, (current_user.id,))
    history = cursor.fetchall()
    
    # Get available quizzes (not yet taken)
    cursor.execute("""
        SELECT * FROM quizzes 
        WHERE id NOT IN (
            SELECT quiz_id FROM results WHERE user_id = %s
        )
    """, (current_user.id,))
    available_quizzes = cursor.fetchall()
    
    conn.close()
    return render_template('dashboard.html', history=history, available_quizzes=available_quizzes)

@app.route('/quiz/list')
@login_required
def quiz_list():
    conn = get_db_connection()
    if not conn:
        return render_template('quiz_list.html', quizzes=[])
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM quizzes")
    quizzes = cursor.fetchall()
    conn.close()
    return render_template('quiz_list.html', quizzes=quizzes)

@app.route('/quiz/start/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def start_quiz(quiz_id):
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'danger')
        return redirect(url_for('dashboard'))
        
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Check if already taken
        cursor.execute("SELECT * FROM results WHERE user_id = %s AND quiz_id = %s", 
                      (current_user.id, quiz_id))
        if cursor.fetchone():
            conn.close()
            flash('You have already taken this quiz!', 'warning')
            return redirect(url_for('dashboard'))
        
        # Submit Quiz Logic
        questions = request.form.to_dict()
        # Remove CSRF token or other non-question fields
        questions = {k: v for k, v in questions.items() if k.isdigit()}
        
        score = 0
        total = 0
        
        # Fetch questions to check answers
        cursor.execute("SELECT id, correct_option FROM questions WHERE quiz_id = %s", (quiz_id,))
        db_questions = cursor.fetchall()
        
        for q in db_questions:
            total += 1
            qid = str(q['id'])
            if qid in questions and questions[qid] == q['correct_option']:
                score += 1
        
        percentage = round((score / total) * 100, 2) if total > 0 else 0
        
        # Save result
        cursor.execute("""
            INSERT INTO results (user_id, quiz_id, score, total_questions, percentage) 
            VALUES (%s, %s, %s, %s, %s)
        """, (current_user.id, quiz_id, score, total, percentage))
        conn.commit()
        conn.close()
        
        flash(f'Quiz completed! Score: {score}/{total}', 'success')
        return redirect(url_for('result_view', quiz_id=quiz_id, score=score, total=total))

    # GET Request - Check if already taken
    cursor.execute("SELECT * FROM results WHERE user_id = %s AND quiz_id = %s", 
                  (current_user.id, quiz_id))
    if cursor.fetchone():
        conn.close()
        flash('Quiz already taken!', 'warning')
        return redirect(url_for('dashboard'))
    
    # Get Quiz Details
    cursor.execute("SELECT * FROM quizzes WHERE id = %s", (quiz_id,))
    quiz = cursor.fetchone()
    
    if not quiz:
        conn.close()
        flash('Quiz not found!', 'danger')
        return redirect(url_for('dashboard'))
    
    cursor.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
    questions = cursor.fetchall()
    conn.close()
    
    # Store start time in session for timer
    session['quiz_start_time'] = time.time()
    session['quiz_time_limit'] = quiz['time_limit'] * 60  # Convert to seconds
    
    return render_template('quiz.html', quiz=quiz, questions=questions)

@app.route('/result/<int:quiz_id>/<int:score>/<int:total>')
@login_required
def result_view(quiz_id, score, total):
    percentage = round((score / total) * 100, 2) if total > 0 else 0
    
    # Get quiz details
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT title FROM quizzes WHERE id = %s", (quiz_id,))
        quiz = cursor.fetchone()
        conn.close()
    else:
        quiz = None
        
    return render_template('result.html', score=score, total=total, percentage=percentage, quiz=quiz)

# --- Routes: Admin ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    print("ADMIN VALUE =", current_user.is_admin)
    if not current_user.is_admin:
        flash('Admin access required!', 'danger')
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    if not conn:
        return render_template('admin/admin_dashboard.html')
        
    cursor = conn.cursor(dictionary=True)
    
    # Stats
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE is_admin = FALSE")
    total_students = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM quizzes")
    total_quizzes = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM results")
    total_attempts = cursor.fetchone()['total']
    
    # Recent results
    cursor.execute("""
        SELECT r.*, u.username, q.title as quiz_title 
        FROM results r 
        JOIN users u ON r.user_id = u.id 
        JOIN quizzes q ON r.quiz_id = q.id 
        ORDER BY r.created_at DESC LIMIT 10
    """)
    recent_results = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin/admin_dashboard.html', 
                         total_students=total_students,
                         total_quizzes=total_quizzes,
                         total_attempts=total_attempts,
                         recent_results=recent_results)

@app.route('/admin/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    if not current_user.is_admin:
        flash('Admin access required!', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['description']
        time_limit = request.form.get('time_limit', 10)
        
        if not title:
            flash('Title is required!', 'danger')
            return render_template('admin/create_quiz.html')
        
        conn = get_db_connection()
        if not conn:
            return render_template('admin/create_quiz.html')
            
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quizzes (title, description, time_limit) 
            VALUES (%s, %s, %s)
        """, (title, desc, int(time_limit)))
        conn.commit()
        quiz_id = cursor.lastrowid
        conn.close()
        
        flash('Quiz Created! Now add questions.', 'success')
        return redirect(url_for('add_question', quiz_id=quiz_id))
        
    return render_template('admin/create_quiz.html')

@app.route('/admin/quiz/<int:quiz_id>/add_question', methods=['GET', 'POST'])
@login_required
def add_question(quiz_id):
    if not current_user.is_admin:
        flash('Admin access required!', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('admin_dashboard'))
        
    cursor = conn.cursor(dictionary=True)
    
    # Verify quiz exists
    cursor.execute("SELECT * FROM quizzes WHERE id = %s", (quiz_id,))
    quiz = cursor.fetchone()
    
    if not quiz:
        conn.close()
        flash('Quiz not found!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        question_text = request.form['question_text']
        option_a = request.form['option_a']
        option_b = request.form['option_b']
        option_c = request.form['option_c']
        option_d = request.form['option_d']
        correct_option = request.form['correct_option']
        
        if not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
            flash('All fields are required!', 'danger')
            conn.close()
            return render_template('admin/add_question.html', quiz=quiz)
        
        cursor.execute("""
            INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option))
        conn.commit()
        
        flash('Question added!', 'success')
        conn.close()
        return redirect(url_for('add_question', quiz_id=quiz_id))
    
    # Get existing questions
    cursor.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
    questions = cursor.fetchall()
    conn.close()
    
    return render_template('admin/add_question.html', quiz=quiz, questions=questions)

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    if not current_user.is_admin:
        flash('Admin access required!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get analytics for all quizzes
    conn = get_db_connection()
    if not conn:
        return render_template(
            'admin/analytics.html', 
            quiz_stats={}, 
            top_students=[]
            )
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title FROM quizzes")
    quizzes = cursor.fetchall()
    conn.close()

    quiz_stats = {}
    for quiz in quizzes:
        stats = get_quiz_stats(quiz['id'])
        if stats:
            quiz_stats[quiz['title']] = stats

    top_students = get_top_students(10)

    return render_template(
        'admin/analytics.html',
        quiz_stats=quiz_stats,
        top_students=top_students
    )
@app.route('/admin/results')
@login_required
def admin_results():
    if not current_user.is_admin:
        flash('Admin access required!', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if not conn:
        return render_template('admin/results.html', results=[])
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.*, u.username, q.title as quiz_title 
        FROM results r 
        JOIN users u ON r.user_id = u.id 
        JOIN quizzes q ON r.quiz_id = q.id 
        ORDER BY r.created_at DESC
    """)
    results = cursor.fetchall()
    conn.close()
    
    return render_template('admin/results.html', results=results)

@app.route('/admin/quiz/<int:quiz_id>/delete', methods=['POST'])
@login_required
def delete_quiz(quiz_id):
    if not current_user.is_admin:
        flash('Admin access required!', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('admin_dashboard'))
        
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))
    conn.commit()
    conn.close()
    
    flash('Quiz deleted!', 'success')
    return redirect(url_for('admin_dashboard'))

# API Routes for AJAX
@app.route('/api/quiz/<int:quiz_id>/stats')
@login_required
def api_quiz_stats(quiz_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    stats = get_quiz_stats(quiz_id)
    return jsonify(stats) if stats else jsonify({'error': 'No data'})

@app.route('/api/top-students')
@login_required
def api_top_students():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    limit = request.args.get('limit', 5, type=int)
    return jsonify(get_top_students(limit))

if __name__ == '__main__':
    app.run(debug=True)