from flask import Flask, render_template, request, redirect, session, url_for, jsonify, g
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2, os

app = Flask(__name__)
app.secret_key = "Y_hCNIs3pMVxxoDhrBfyMo522foKQhJ3"
socketio = SocketIO(app, cors_allowed_origins="*")

# ✅ PostgreSQL 連線設定
DB_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://admin:8M1l69VLNxzuNABPnJGatCp00w5XrkiO@dpg-d3qvvrogjchc73bmbgsg-a.singapore-postgres.render.com/chat_app_whw7'
)

# ✅ 從環境變數讀取管理員密碼，更安全
ADMIN_CLEAR_PASSWORD = os.getenv('ADMIN_CLEAR_PASSWORD', 'admin0521')

def get_conn():
    """
    透過 Flask g 物件管理 PostgreSQL 連線。
    如果 g 中沒有 conn，就建立一個新的，並在請求結束後自動關閉。
    """
    if 'conn' not in g:
        g.conn = psycopg2.connect(DB_URL, sslmode='require')
    return g.conn

@app.teardown_appcontext
def close_conn(e=None):
    """在應用程式上下文結束時自動關閉資料庫連線"""
    conn = g.pop('conn', None)
    if conn is not None:
        conn.close()

def init_db():
    """建立 users 和 messages 資料表"""
    with app.app_context():
        conn = get_conn()
        with conn.cursor() as c:
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    nickname VARCHAR(50) NOT NULL
                );
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50),
                    message TEXT,
                    reply_to_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
        conn.commit()

init_db()

# =====================
# 使用者系統
# =====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '')
        if not username or not nickname or not password:
            return render_template('register.html', error='請填寫所有欄位')
        pw_hash = generate_password_hash(password)
        try:
            conn = get_conn()
            with conn.cursor() as c:
                c.execute('INSERT INTO users (username, password_hash, nickname) VALUES (%s, %s, %s)',
                          (username, pw_hash, nickname))
            conn.commit()
        except psycopg2.IntegrityError:
            conn.rollback()
            return render_template('register.html', error='帳號已存在')
        return redirect(url_for('login'))
    return render_template('register.html', error='')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_conn()
        with conn.cursor() as c:
            c.execute('SELECT password_hash, nickname FROM users WHERE username=%s', (username,))
            row = c.fetchone()
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

# =====================
# 聊天系統
# =====================
@app.route('/')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', nickname=session.get('nickname', ''))

@app.route('/clear', methods=['POST'])
def clear_chat():
    data_pw = request.form.get('pw') or request.args.get('pw') or (request.get_json() or {}).get('pw')
    if data_pw != ADMIN_CLEAR_PASSWORD:
        return jsonify({'status': 'error', 'message': '密碼錯誤'}), 403
    conn = get_conn()
    with conn.cursor() as c:
        c.execute('DELETE FROM messages')
    conn.commit()
    return jsonify({'status': 'ok'})

# =====================
# WebSocket handlers
# =====================
@socketio.on('connect')
def handle_connect():
    conn = get_conn()
    with conn.cursor() as c:
        c.execute("SELECT id, username, message, reply_to_id FROM messages ORDER BY id ASC")
        rows = c.fetchall()
    msgs = [{'id': r[0], 'username': r[1], 'message': r[2], 'reply_to_id': r[3]} for r in rows]
    emit('load_history', msgs)

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username')
    message = data.get('message')
    reply_to_id = data.get('reply_to_id')
    conn = get_conn()
    with conn.cursor() as c:
        c.execute('INSERT INTO messages (username, message, reply_to_id) VALUES (%s, %s, %s) RETURNING id',
                  (username, message, reply_to_id))
        msg_id = c.fetchone()[0]
        conn.commit()

    emit('receive_message', {'id': msg_id, 'username': username, 'message': message, 'reply_to_id': reply_to_id}, broadcast=True)

# =====================
# 啟動伺服器
# =====================
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
