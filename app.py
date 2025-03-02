from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import bcrypt
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    url = urlparse(DATABASE_URL)
    db_config = {
        'host': url.hostname,
        'user': url.username,
        'password': url.password,
        'database': url.path[1:], 
        'port': url.port
    }
else:
    db_config = {
        'host': '127.0.0.1',
        'user': 'root',
        'password': 'my-secret-pw',
        'database': 'feyndora'
    }

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config, charset='utf8mb4')
        return conn
    except Error as e:
        print(f"資料庫連接錯誤: {e}")
        return None

@app.route('/')
def index():
    return "Flask 伺服器運行中!"

# ✅ 註冊
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username, email, password = data['username'], data['email'], data['password']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM Users WHERE username=%s OR email=%s", (username, email))
    if cursor.fetchone():
        return jsonify({"error": "使用者名稱或Email已存在"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    cursor.execute("""
        INSERT INTO Users (username, email, password, total_learning_points, coins, diamonds, account_created_at, avatar_id)
        VALUES (%s, %s, %s, 0, 0, 0, NOW(), 1)
    """, (username, email, hashed_password.decode('utf-8')))

    conn.commit()
    return jsonify({"message": "註冊成功"}), 201

# ✅ 登入
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email, password = data['email'], data['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({"error": "帳號或密碼錯誤"}), 401

    return jsonify({
        "message": "登入成功",
        "user_id": user['user_id'],
        "username": user['username'],
        "email": user['email'],
        "coins": user['coins'],
        "diamonds": user['diamonds'],
        "avatar_id": user['avatar_id']
    }), 200

# ✅ 查詢當前課程狀態 (current_stage)
@app.route('/current_stage/<int:user_id>', methods=['GET'])
def get_current_stage(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT course_id, course_name, current_stage, progress, progress_one_to_one, progress_classroom
        FROM Courses
        WHERE user_id = %s AND is_vr_ready = TRUE
        ORDER BY vr_started_at DESC
        LIMIT 1
    """, (user_id,))

    course = cursor.fetchone()
    if not course:
        return jsonify({"error": "目前沒有準備好的課程"}), 404

    return jsonify(course), 200

# ✅ 課程相關API
@app.route('/courses/<int:user_id>', methods=['GET'])
def get_courses(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Courses WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
    return jsonify(cursor.fetchall()), 200

@app.route('/add_course', methods=['POST'])
def add_course():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Courses (user_id, course_name, progress, progress_one_to_one, progress_classroom, is_favorite, file_type, created_at)
        VALUES (%s, %s, 0, 0, 0, FALSE, %s, NOW())
    """, (data['user_id'], data['course_name'], data['file_type']))
    conn.commit()
    return jsonify({"message": "課程已新增"}), 201

@app.route('/delete_course/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Courses WHERE course_id=%s", (course_id,))
    conn.commit()
    return jsonify({"message": "課程已刪除"}), 200

@app.route('/toggle_favorite/<int:course_id>', methods=['POST'])
def toggle_favorite(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Courses SET is_favorite = NOT is_favorite WHERE course_id=%s", (course_id,))
    conn.commit()
    return jsonify({"message": "收藏狀態已更新"}), 200

# ✅ 課程進度更新
@app.route('/update_progress', methods=['POST'])
def update_progress():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE Courses
        SET progress = %s, progress_one_to_one = %s, progress_classroom = %s, current_stage = %s
        WHERE course_id = %s
    """, (data['progress'], data['progress_one_to_one'], data['progress_classroom'], data['current_stage'], data['course_id']))
    conn.commit()
    return jsonify({"message": "進度更新成功"}), 200

# ✅ 繼續上課
@app.route('/continue_course', methods=['POST'])
def continue_course():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Courses SET vr_started_at=NOW() WHERE course_id=%s", (data['course_id'],))
    conn.commit()
    return jsonify({"message": "課程VR開始"}), 200

# ✅ 更新暱稱與頭像
@app.route('/update_nickname/<int:user_id>', methods=['PUT'])
def update_nickname(user_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET username=%s WHERE user_id=%s", (data['nickname'], user_id))
    conn.commit()
    return jsonify({"message": "暱稱更新成功"}), 200

@app.route('/update_avatar/<int:user_id>', methods=['PUT'])
def update_avatar(user_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET avatar_id=%s WHERE user_id=%s", (data['avatar_id'], user_id))
    conn.commit()
    return jsonify({"message": "頭像更新成功"}), 200

# ✅ 刪除帳號
@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Users WHERE user_id=%s", (user_id,))
    conn.commit()
    return jsonify({"message": "帳號已刪除"}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
