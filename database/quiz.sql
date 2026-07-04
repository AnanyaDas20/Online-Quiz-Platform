-- Create Database
CREATE DATABASE IF NOT EXISTS quiz_platform;
USE quiz_platform;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quizzes Table
CREATE TABLE IF NOT EXISTS quizzes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    time_limit INT NOT NULL COMMENT 'Time in minutes',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Questions Table
CREATE TABLE IF NOT EXISTS questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quiz_id INT NOT NULL,
    question_text TEXT NOT NULL,
    option_a VARCHAR(255) NOT NULL,
    option_b VARCHAR(255) NOT NULL,
    option_c VARCHAR(255) NOT NULL,
    option_d VARCHAR(255) NOT NULL,
    correct_option CHAR(1) NOT NULL COMMENT 'A, B, C, or D',
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
);

-- Results Table
CREATE TABLE IF NOT EXISTS results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    quiz_id INT NOT NULL,
    score INT NOT NULL,
    total_questions INT NOT NULL,
    percentage DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
);

-- Insert Sample Admin (Password: admin123)
INSERT INTO users (username, email, password_hash, is_admin) 
VALUES ('admin', 'admin@example.com', 'pbkdf2:sha256:600000$salt$hash', TRUE);

-- Insert Sample User (Password: user123)
-- Note: In a real scenario, generate the hash via Python. 
-- For this demo, use 'pbkdf2:sha256:600000$randomsalt$5e884898da28047' (represents 'password')
INSERT INTO users (username, email, password_hash, is_admin) 
VALUES ('student1', 'student@example.com', 'pbkdf2:sha256:600000$randomsalt$5e884898da28047', FALSE);

-- Sample Quiz
INSERT INTO quizzes (title, description, time_limit) 
VALUES ('Python Basics', 'Test your knowledge of Python syntax', 5);

-- Sample Questions
INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option)
VALUES 
(1, 'What is the output of 2**3?', '6', '8', '9', '5', 'B'),
(1, 'Which keyword is used to define a function in Python?', 'function', 'def', 'func', 'define', 'B'),
(1, 'How do you create a list in Python?', '{}', '[]', '()', '<>', 'B');