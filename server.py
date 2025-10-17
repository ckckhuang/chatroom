from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os

app = Flask(__name__)
app.secret_key = "Y_hCNIs3pMVxxoDhrBfyMo522foKQhJ3"
socketio = SocketIO(app, cors_allowed_origins="*")

DB_FILE = 'chat.db'
ADMIN_CLEAR_PASSWORD = 'admin0521'  # management clear password

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nickname TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            reply_to_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        nickname = request.form.get('nickname','').strip()
        password = request.form.get('password','')
        if not username or not nickname or not password:
            return render_template('register.html', error='請填寫所有欄位')
        pw_hash = generate_password_hash(password)
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password_hash, nickname) VALUES (?, ?, ?)', (username, pw_hash, nickname))
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            return render_template('register.html', error='帳號已存在')
        return redirect(url_for('login'))
    return render_template('register.html', error='')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT password_hash, nickname FROM users WHERE username=?', (username,))
        row = c.fetchone()
        conn.close()
        if row and check_password_hash(row[0], password):
            session['username'] = username
            session['nickname'] = row[1]
            return redirect(url_for('chat'))
        return render_template('login.html', error='帳號或密碼錯誤')
    return render_template('login.html', error='')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', nickname=session.get('nickname',''))

@app.route('/clear', methods=['POST'])
def clear_chat():
    data_pw = request.form.get('pw') or request.args.get('pw') or (request.get_json() or {}).get('pw')
    if data_pw != ADMIN_CLEAR_PASSWORD:
        return jsonify({'status':'error','message':'密碼錯誤'}), 403
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM messages')
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, username, message, reply_to_id FROM messages ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    msgs = [{'id': r[0], 'username': r[1], 'message': r[2], 'reply_to_id': r[3]} for r in rows]
    emit('load_history', msgs)

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username')
    message = data.get('message')
    reply_to_id = data.get('reply_to_id')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO messages (username, message, reply_to_id) VALUES (?, ?, ?)', (username, message, reply_to_id))
    msg_id = c.lastrowid
    conn.commit()
    conn.close()
    emit('receive_message', {'id': msg_id, 'username': username, 'message': message, 'reply_to_id': reply_to_id}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
