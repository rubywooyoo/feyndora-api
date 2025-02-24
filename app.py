from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import bcrypt
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # ✅ 確保 JSON 使用 UTF-8，支援中文輸出

# 讀取 Render 提供的 DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    url = urlparse(DATABASE_URL)
    db_config = {
        'host': url.hostname,
        'user': url.username,
        'password': url.password,
        'database': url.path[1:],  # 去掉 "/" 取得資料庫名稱
        'port': url.port
    }
else:
    # 本地測試用 MySQL 設定
    db_config = {
        'host': '127.0.0.1',
        'user': 'root',
        'password': 'my-secret-pw',
        'database': 'feyndora'
    }

# 建立 MySQL 連線
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config, charset='utf8mb4')  # ✅ 設定 utf8mb4，支援中文
        return conn
    except Error as e:
        print(f"資料庫連接錯誤: {e}")
        return None

@app.route('/')
def index():
    return "Flask 伺服器運行中!"

# **✅ 獲取用戶資料**
@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, username, email, coins, diamonds FROM Users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        return jsonify({"error": "找不到用戶"}), 404

    return jsonify(user), 200

# **✅ 更新用戶暱稱**
@app.route('/update_nickname/<int:user_id>', methods=['PUT'])
def update_nickname(user_id):
    data = request.json
    new_nickname = data.get('nickname')

    if not new_nickname:
        return jsonify({"error": "暱稱不能為空"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET username = %s WHERE user_id = %s", (new_nickname, user_id))
    conn.commit()

    cursor.close()
    conn.close()
    return jsonify({"message": "暱稱更新成功"}), 200

# **✅ 刪除帳號**
@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor()

    # **檢查用戶是否存在**
    cursor.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
    if not cursor.fetchone():
        return jsonify({"error": "用戶不存在"}), 404

    # **刪除用戶**
    cursor.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "帳號已刪除"}), 200

# **✅ 註冊 API**
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "缺少必要欄位"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor()

    # **檢查 Email 是否已存在**
    cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
    if cursor.fetchone():
        return jsonify({"error": "該 Email 已被註冊"}), 400

    # **加密密碼**
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # **插入新用戶**
    query = """INSERT INTO Users (username, email, password, total_learning_points, coins, diamonds, account_created_at) 
               VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
    cursor.execute(query, (username, email, hashed_password.decode('utf-8'), 0, 0, 0))
    conn.commit()

    cursor.close()
    conn.close()
    return jsonify({"message": "註冊成功"}), 201

# **✅ 登入 API**
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "缺少必要欄位"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        cursor.close()
        conn.close()
        return jsonify({"error": "帳號或密碼錯誤"}), 401

    response = {
        "message": "登入成功",
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "coins": user["coins"],
        "diamonds": user["diamonds"]
    }

    cursor.close()
    conn.close()
    return jsonify(response), 200

# **✅ 取得用戶課程**
@app.route('/courses/<int:user_id>', methods=['GET'])
def get_courses(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT course_id, course_name, created_at, progress, is_favorite, file_type FROM Courses WHERE user_id = %s", (user_id,))
    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(courses), 200

# **✅ 刪除課程**
@app.route('/delete_course/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor()
    cursor.execute("DELETE FROM Courses WHERE course_id = %s", (course_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "課程已刪除"}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
