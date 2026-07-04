import pandas as pd
import mysql.connector
from config import Config

def get_db_connection():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )

def get_quiz_results_as_df(quiz_id=None):
    """Fetches results joined with users and quizzes from MySQL."""
    conn = get_db_connection()
    
    if quiz_id:
        query = """
            SELECT r.id, u.username, r.score, r.total_questions, r.percentage, 
                   r.created_at, q.title as quiz_title, q.id as quiz_id
            FROM results r
            JOIN users u ON r.user_id = u.id
            JOIN quizzes q ON r.quiz_id = q.id
            WHERE q.id = %s
        """
        df = pd.read_sql(query, conn, params=(quiz_id,))
    else:
        query = """
            SELECT r.id, u.username, r.score, r.total_questions, r.percentage, 
                   r.created_at, q.title as quiz_title, q.id as quiz_id
            FROM results r
            JOIN users u ON r.user_id = u.id
            JOIN quizzes q ON r.quiz_id = q.id
        """
        df = pd.read_sql(query, conn)
    
    conn.close()
    return df

def get_quiz_stats(quiz_id):
    """Generates analytics for a specific quiz using Pandas."""
    df = get_quiz_results_as_df(quiz_id)
    
    if df.empty:
        return None

    stats = {
        'total_attempts': len(df),
        'average_score': round(df['score'].mean(), 2),
        'average_percentage': round(df['percentage'].mean(), 2),
        'highest_score': int(df['score'].max()),
        'lowest_score': int(df['score'].min()),
        'pass_percentage': round((df['percentage'] >= 50).sum() / len(df) * 100, 2),
        'total_questions': int(df['total_questions'].iloc[0]) if not df.empty else 0
    }
    return stats

def get_top_students(limit=5):
    """Returns top performing students based on average percentage."""
    df = get_quiz_results_as_df()
    
    if df.empty:
        return []

    # Group by username and calculate mean percentage
    top_performers = df.groupby('username')['percentage'].mean().sort_values(ascending=False).head(limit)
    
    # Convert to list of dicts for easier JSON serialization
    result = [{'username': name, 'average_percentage': round(score, 2)} 
              for name, score in top_performers.items()]
    return result

def get_student_progress(username):
    """Get progress of a specific student over time."""
    df = get_quiz_results_as_df()
    student_df = df[df['username'] == username].sort_values('created_at')
    
    if student_df.empty:
        return None
    
    return {
        'total_quizzes': len(student_df),
        'average_percentage': round(student_df['percentage'].mean(), 2),
        'progress_trend': student_df['percentage'].tolist(),
        'quiz_dates': student_df['created_at'].dt.strftime('%Y-%m-%d').tolist()
    }

def get_leaderboard(quiz_id=None, limit=10):
    """Get leaderboard for a specific quiz or overall."""
    df = get_quiz_results_as_df(quiz_id)
    
    if df.empty:
        return []
    
    # Get best score per student
    leaderboard = df.loc[df.groupby('username')['percentage'].idxmax()]
    leaderboard = leaderboard.sort_values('percentage', ascending=False).head(limit)
    
    return leaderboard[['username', 'quiz_title', 'percentage', 'score', 'total_questions']].to_dict('records')