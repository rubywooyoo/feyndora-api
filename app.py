from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import bcrypt
import os
from urllib.parse import urlparse

app = Flask(__name__)

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
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print(f"資料庫連接錯誤: {e}")
        return None
        
@app.route('/')
def index():
    return "Flask 伺服器運行中拉拉拉!"

# **註冊 API**
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

    # **檢查 Username 是否已存在**
    cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
    if cursor.fetchone():
        return jsonify({"error": "該使用者名稱已被使用"}), 400

    # **檢查 Email 是否已存在**
    cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
    if cursor.fetchone():
        return jsonify({"error": "該 Email 已被註冊"}), 400

    # 加密密碼
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # 插入新用戶
    query = """INSERT INTO Users (username, email, password, total_learning_points, coins, diamonds, account_created_at) 
               VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
    cursor.execute(query, (username, email, hashed_password.decode('utf-8'), 0, 0, 0))
    conn.commit()

    cursor.close()
    conn.close()
    return jsonify({"message": "註冊成功"}), 201

# **登入 API**
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

    cursor.close()
    conn.close()

    # 確保使用 bcrypt 驗證密碼
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({"error": "帳號或密碼錯誤"}), 401

    return jsonify({
        "message": "登入成功",
        "user_id": user["user_id"],
        "username": user["username"],
        "total_learning_points": user["total_learning_points"],
        "coins": user["coins"],
        "diamonds": user["diamonds"],
        "account_created_at": user["account_created_at"]
    }), 200
    
# **獲取用戶資訊 API**
@app.route('/get_user_info', methods=['GET'])
def get_user_info():
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, total_learning_points, coins, diamonds FROM Users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        return jsonify({"error": "用戶不存在"}), 404

    return jsonify({
        "username": user["username"],
        "total_learning_points": user["total_learning_points"],
        "coins": user["coins"],
        "diamonds": user["diamonds"]
    }), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
