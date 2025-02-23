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

# **用戶資料 API（獲取最新數據）**
@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, username, coins, diamonds FROM Users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        return jsonify({"error": "找不到用戶"}), 404

    return jsonify(user), 200

# **📌 獲取使用者的所有課程 `/courses/<user_id>`**
@app.route('/courses/<int:user_id>', methods=['GET'])
def get_courses(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT course_id, course_name, created_at, progress, is_favorite, file_type
        FROM Courses
        WHERE user_id = %s
        ORDER BY is_favorite DESC, created_at DESC
    """, (user_id,))

    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(courses), 200

# **📌 搜尋使用者的課程 `/search_courses/<user_id>?query=xxx`**
@app.route('/search_courses/<int:user_id>', methods=['GET'])
def search_courses(user_id):
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({"error": "缺少搜尋關鍵字"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT course_id, course_name, created_at, progress, is_favorite, file_type
        FROM Courses 
        WHERE user_id = %s AND course_name LIKE %s 
        ORDER BY is_favorite DESC, created_at DESC
    """, (user_id, f"%{query}%"))

    courses = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(courses), 200

# **📌 新增課程 `/add_course`**
@app.route('/add_course', methods=['POST'])
def add_course():
    data = request.json
    user_id = data.get("user_id")
    course_name = data.get("course_name")
    file_type = data.get("file_type")  # ✅ 新增 file_type 參數

    if not user_id or not course_name or not file_type:
        return jsonify({"error": "缺少必要參數"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor()

    query = """INSERT INTO Courses (user_id, course_name, progress, is_favorite, file_type, created_at)
               VALUES (%s, %s, %s, %s, %s, NOW())"""
    cursor.execute(query, (user_id, course_name, 0, False, file_type))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "課程已新增"}), 201

# **📌 切換課程收藏狀態 `/toggle_favorite/<course_id>`**
@app.route('/toggle_favorite/<int:course_id>', methods=['POST'])
def toggle_favorite(course_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor()
    
    # 先檢查當前收藏狀態
    cursor.execute("SELECT is_favorite FROM Courses WHERE course_id = %s", (course_id,))
    course = cursor.fetchone()

    if not course:
        return jsonify({"error": "找不到課程"}), 404

    new_favorite_status = not course[0]  # 反轉收藏狀態
    cursor.execute("UPDATE Courses SET is_favorite = %s WHERE course_id = %s", (new_favorite_status, course_id))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "課程收藏狀態已更新", "is_favorite": new_favorite_status}), 200

# **📌 刪除課程 `/delete_course/<course_id>`**
@app.route('/delete_course/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "資料庫連接失敗"}), 500

    cursor = conn.cursor()
    
    # 檢查課程是否存在
    cursor.execute("SELECT * FROM Courses WHERE course_id = %s", (course_id,))
    if not cursor.fetchone():
        return jsonify({"error": "找不到課程"}), 404

    cursor.execute("DELETE FROM Courses WHERE course_id = %s", (course_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "課程已刪除"}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
