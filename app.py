from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import bcrypt
import os
import pytz
from datetime import datetime, date, timedelta
from urllib.parse import urlparse
import json
from flask_cors import CORS  # ✅ 新增這一行

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)  # ✅ 加這一行讓前端（Unity WebGL / Netlify）能存取 Flask API

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
        cursor = conn.cursor()
        # 設置數據庫時間為台灣時區
        cursor.execute("SET time_zone = '+08:00'")
        cursor.close()
        return conn
    except Error as e:
        print(f"資料庫連接錯誤: {e}")
        return None

# ✅ 取得台灣當下時間
def get_taiwan_now():
    taiwan = pytz.timezone('Asia/Taipei')
    return datetime.now(taiwan)

# ✅ 取得今天日期（台灣時區）
def get_today():
    return get_taiwan_now().date()

# ✅ 計算台灣本週範圍（週一~週日）
def get_week_range():
    today = get_today()
    start_of_week = today - timedelta(days=today.weekday())  # 週一
    end_of_week = start_of_week + timedelta(days=6)          # 週日
    return start_of_week, end_of_week

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
        VALUES (%s, %s, %s, 0, 500, 0, %s, 1)
    """, (username, email, hashed_password.decode('utf-8'), get_taiwan_now()))

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

# ✅ 取得日排名 (強制台灣時區)
@app.route('/daily_rankings', methods=['GET'])
def daily_rankings():
    query_date = request.args.get('date', get_today().isoformat())
    user_id = request.args.get('user_id', type=int)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ 查詢前10名
    cursor.execute("""
        SELECT t.user_id, t.username, t.avatar_id, t.daily_points, t.ranking
        FROM (
            SELECT U.user_id, U.username, U.avatar_id, 
                   SUM(L.daily_points) AS daily_points,
                   RANK() OVER (ORDER BY SUM(L.daily_points) DESC) AS ranking
            FROM LearningPointsLog L
            JOIN Users U ON L.user_id = U.user_id
            WHERE L.date = %s
            GROUP BY U.user_id, U.username, U.avatar_id
        ) t
        ORDER BY t.ranking
        LIMIT 10
    """, (query_date,))
    top10 = cursor.fetchall()

    # 2️⃣ 查詢用戶自己的名次
    user_rank = None
    if user_id:
        cursor.execute("""
            SELECT t.user_id, t.username, t.avatar_id, t.daily_points, t.ranking
            FROM (
                SELECT U.user_id, U.username, U.avatar_id, 
                       SUM(L.daily_points) AS daily_points,
                       RANK() OVER (ORDER BY SUM(L.daily_points) DESC) AS ranking
                FROM LearningPointsLog L
                JOIN Users U ON L.user_id = U.user_id
                WHERE L.date = %s
                GROUP BY U.user_id, U.username, U.avatar_id
            ) t
            WHERE t.user_id = %s
        """, (query_date, user_id))
        user_rank = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        "date": query_date,
        "rankings": top10,
        "userRank": user_rank
    })

# ✅ 取得週排名 (強制台灣時區+週一到週日)
@app.route('/weekly_rankings', methods=['GET'])
def weekly_rankings():
    user_id = request.args.get('user_id', type=int)

    start_of_week, end_of_week = get_week_range()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ 查詢前10名
    cursor.execute("""
        SELECT t.user_id, t.username, t.avatar_id, t.weekly_points, t.ranking
        FROM (
            SELECT U.user_id, U.username, U.avatar_id, 
                   SUM(L.daily_points) AS weekly_points,
                   RANK() OVER (ORDER BY SUM(L.daily_points) DESC) AS ranking
            FROM LearningPointsLog L
            JOIN Users U ON L.user_id = U.user_id
            WHERE L.date BETWEEN %s AND %s
            GROUP BY U.user_id, U.username, U.avatar_id
        ) t
        ORDER BY t.ranking
        LIMIT 10
    """, (start_of_week, end_of_week))
    top10 = cursor.fetchall()

    # 2️⃣ 查詢用戶自己的名次
    user_rank = None
    if user_id:
        cursor.execute("""
            SELECT t.user_id, t.username, t.avatar_id, t.weekly_points, t.ranking
            FROM (
                SELECT U.user_id, U.username, U.avatar_id, 
                       SUM(L.daily_points) AS weekly_points,
                       RANK() OVER (ORDER BY SUM(L.daily_points) DESC) AS ranking
                FROM LearningPointsLog L
                JOIN Users U ON L.user_id = U.user_id
                WHERE L.date BETWEEN %s AND %s
                GROUP BY U.user_id, U.username, U.avatar_id
            ) t
            WHERE t.user_id = %s
        """, (start_of_week, end_of_week, user_id))
        user_rank = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        "weekStart": start_of_week.isoformat(),
        "weekEnd": end_of_week.isoformat(),
        "rankings": top10,
        "userRank": user_rank
    })

# ✅ 檢查簽到狀態，確認今天是否簽到過
@app.route('/signin/status/<int:user_id>', methods=['GET'])
def check_signin_status(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT signin_day, last_signin_date, weekly_streak FROM SigninRecords WHERE user_id = %s", (user_id,))
    record = cursor.fetchone()

    if not record:
        cursor.close()
        conn.close()
        return jsonify({"error": "用戶簽到記錄不存在"}), 400

    server_today = get_today()
    start_of_week, end_of_week = get_week_range()
    
    last_signin_date = record["last_signin_date"]
    signin_day = record["signin_day"]
    weekly_streak = record["weekly_streak"]

    # 新增：判斷是否是新的一週
    is_new_week = False
    if last_signin_date and last_signin_date < start_of_week:
        is_new_week = True
        signin_day = 1  # 重置為第一天
        weekly_streak = 0  # 重置連續簽到

    already_signed_in = (last_signin_date == server_today)

    response_data = {
        "signin_day": signin_day,
        "weekly_streak": weekly_streak,
        "has_claimed_today": already_signed_in,
        "last_signin_date": last_signin_date,
        "server_today": server_today,
        "is_new_week": is_new_week  # 新增這個回傳值
    }

    cursor.close()
    conn.close()
    return jsonify(response_data), 200

# ✅ 初始化簽到記錄，以防用戶沒有簽到過
@app.route('/signin/init/<int:user_id>', methods=['POST'])
def initialize_signin_record(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 檢查用戶是否已有簽到記錄
    cursor.execute("SELECT * FROM SigninRecords WHERE user_id = %s", (user_id,))
    record = cursor.fetchone()

    if record:
        return jsonify({"message": "簽到記錄已存在"}), 200

    # 如果沒有簽到記錄，則建立初始記錄
    cursor.execute("""
        INSERT INTO SigninRecords (user_id, signin_day, has_claimed_today, last_signin_date) 
        VALUES (%s, 1, FALSE, NULL)
    """, (user_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "簽到記錄初始化成功"}), 201

# ✅ 領取簽到獎勵
@app.route('/signin/claim/<int:user_id>', methods=['POST'])
def claim_signin_reward(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    today = get_today()  # 取得今天（台灣時區）
    start_of_week, end_of_week = get_week_range()

    # 🔹 查詢目前的簽到記錄
    cursor.execute("SELECT signin_day, last_signin_date, weekly_streak FROM SigninRecords WHERE user_id = %s", (user_id,))
    record = cursor.fetchone()

    if not record:
        return jsonify({"error": "用戶簽到記錄不存在"}), 400

    last_signin_date = record["last_signin_date"]
    weekly_streak = record["weekly_streak"]
    signin_day = record["signin_day"]

    # 🔹 防止重複簽到
    if last_signin_date == today:
        return jsonify({
            "error": "今天已經領取過獎勵",
            "last_signin_date": last_signin_date
        }), 400

    # ✅ 檢查是否是新的一週的第一次簽到
    if last_signin_date and last_signin_date < start_of_week:
        signin_day = 1
        weekly_streak = 1
    # ✅ 判斷是否為連續簽到（昨天有簽到）
    elif last_signin_date and (last_signin_date + timedelta(days=1)) == today:
        weekly_streak += 1
    else:
        weekly_streak = 1  # 不是連續簽到就重設

    # 設定獎勵內容（根據簽到第幾天）
    rewards = {
        1: {"coins": 100, "diamonds": 0},
        2: {"coins": 300, "diamonds": 0},
        3: {"coins": 500, "diamonds": 0},
        4: {"coins": 1000, "diamonds": 0},
        5: {"coins": 0, "diamonds": 1},
        6: {"coins": 0, "diamonds": 3},
        7: {"coins": 500, "diamonds": 5},
    }
    reward = rewards.get(signin_day, {"coins": 0, "diamonds": 0})

    # 🔹 更新 SigninRecords
    next_signin_day = 1 if signin_day == 7 else signin_day + 1
    cursor.execute("""
        UPDATE SigninRecords 
        SET signin_day = %s, last_signin_date = %s, weekly_streak = %s
        WHERE user_id = %s
    """, (next_signin_day, today, weekly_streak, user_id))

    # 🔹 更新 Users 的金幣與鑽石、總簽到天數
    cursor.execute("""
        UPDATE Users SET total_signin_days = total_signin_days + 1, 
        coins = coins + %s, diamonds = diamonds + %s WHERE user_id = %s
    """, (reward["coins"], reward["diamonds"], user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "簽到成功",
        "signin_day": next_signin_day,
        "weekly_streak": weekly_streak,
        "coins_received": reward["coins"],
        "diamonds_received": reward["diamonds"],
        "last_signin_date": today
    }), 200
    
# ✅ 更新學習點數（留給VR端呼叫）
@app.route('/update_learning_points', methods=['POST'])
def update_learning_points():
    data = request.json
    user_id = data['user_id']
    points_to_add = data['points']
    today = date.today().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    # 先確認今天是否已有紀錄
    cursor.execute("SELECT daily_points FROM LearningPointsLog WHERE user_id=%s AND date=%s", (user_id, today))
    row = cursor.fetchone()

    if row:
        # 更新今天的累計點數
        new_points = row[0] + points_to_add
        cursor.execute("UPDATE LearningPointsLog SET daily_points=%s WHERE user_id=%s AND date=%s", (new_points, user_id, today))
    else:
        # 新增今日點數紀錄
        cursor.execute("INSERT INTO LearningPointsLog (user_id, date, daily_points) VALUES (%s, %s, %s)", (user_id, today, points_to_add))

    # 2️⃣ 同時更新 Users 表的 total_learning_points（生涯總積分）
    cursor.execute("UPDATE Users SET total_learning_points = total_learning_points + %s WHERE user_id = %s", 
                   (points_to_add, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "學習點數更新完成"})

# ✅ 取得用戶當週的每日學習數
@app.route('/weekly_points/<int:user_id>', methods=['GET'])
def get_weekly_points(user_id):
    today = get_today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT date, daily_points 
        FROM LearningPointsLog
        WHERE user_id = %s AND date BETWEEN %s AND %s
    """
    cursor.execute(query, (user_id, start_of_week, end_of_week))
    rows = cursor.fetchall()

    print(f"🔍 查詢到的記錄: {rows}")  # ✅ 看看有沒有查到數據

    weekly_data = { (start_of_week + timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(7)}

    for row in rows:
        weekly_data[str(row['date'])] = row['daily_points']

    cursor.close()
    conn.close()

    print(f"✅ 回傳的 weekly_points: {list(weekly_data.values())}")
    return jsonify({"weekly_points": list(weekly_data.values())})

# ✅ 取得用戶課程數量
@app.route('/courses_count/<int:user_id>', methods=['GET'])
def get_courses_count(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Courses WHERE user_id=%s", (user_id,))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return jsonify({"courses_count": count})

# ✅ 取得用戶資料（不含敏感資料）
@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, username, email, total_learning_points, coins, diamonds, avatar_id, total_signin_days FROM Users WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user:
        return jsonify({"error": "找不到用戶"}), 404
    return jsonify(user), 200

# ✅ current_stage（每次呼叫都即時計算進度+更新progress+回傳最新current_stage）
'''@app.route('/current_stage/<int:user_id>', methods=['GET'])
def get_current_stage(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 取最新ready課程
    cursor.execute("""
        SELECT course_id, course_name, current_stage, progress, progress_one_to_one, progress_classroom
        FROM Courses
        WHERE user_id = %s AND is_vr_ready = TRUE
        ORDER BY vr_started_at DESC
        LIMIT 1
    """, (user_id,))

    course = cursor.fetchone()
    if not course:
        return jsonify({"hasReadyCourse": False}), 200

    course_id = course['course_id']

    # 計算一對一目錄進度
    cursor.execute("""
        SELECT COUNT(*) as total, SUM(is_completed) as completed
        FROM CourseChapters
        WHERE course_id = %s AND chapter_type = 'one_to_one'
    """, (course_id,))
    one_to_one_progress = cursor.fetchone()
    progress_one_to_one = (one_to_one_progress['completed'] / one_to_one_progress['total']) * 100 if one_to_one_progress['total'] > 0 else 0

    # 計算一對多目錄進度
    cursor.execute("""
        SELECT COUNT(*) as total, SUM(is_completed) as completed
        FROM CourseChapters
        WHERE course_id = %s AND chapter_type = 'classroom'
    """, (course_id,))
    classroom_progress = cursor.fetchone()
    progress_classroom = (classroom_progress['completed'] / classroom_progress['total']) * 100 if classroom_progress['total'] > 0 else 0

    # 重新計算總progress (可自行決定計算邏輯)
    total_progress = (progress_one_to_one + progress_classroom) / 2  # 這裡假設各佔50%權重

    # 判斷是否要更新current_stage
    if course['current_stage'] == 'one_to_one' and progress_one_to_one >= 100:
        course['current_stage'] = 'classroom'
    elif course['current_stage'] == 'classroom' and progress_classroom >= 100:
        course['current_stage'] = 'completed'

    # 更新最新進度和階段回到Courses
    cursor.execute("""
        UPDATE Courses
        SET progress = %s, progress_one_to_one = %s, progress_classroom = %s, current_stage = %s
        WHERE course_id = %s
    """, (total_progress, progress_one_to_one, progress_classroom, course['current_stage'], course_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "hasReadyCourse": True,
        "course_id": course_id,
        "course_name": course['course_name'],
        "current_stage": course['current_stage'],
        "progress": total_progress,
        "progress_one_to_one": progress_one_to_one,
        "progress_classroom": progress_classroom
    }), 200'''

# ✅ current_stage（每次呼叫都即時計算進度+更新progress+回傳最新current_stage）
@app.route('/current_stage/<int:user_id>', methods=['GET'])
def get_current_stage(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 取最新ready課程
    cursor.execute("""
        SELECT course_id, course_name, current_stage, progress, progress_one_to_one, progress_classroom, teacher_card_id
        FROM Courses
        WHERE user_id = %s AND is_vr_ready = TRUE
        ORDER BY vr_started_at DESC
        LIMIT 1
    """, (user_id,))

    course = cursor.fetchone()
    if not course:
        return jsonify({"hasReadyCourse": False}), 200

    course_id = course['course_id']

    # 計算一對一目錄進度
    cursor.execute("""
        SELECT COUNT(*) as total, SUM(is_completed) as completed
        FROM CourseChapters
        WHERE course_id = %s AND chapter_type = 'one_to_one'
    """, (course_id,))
    one_to_one_progress = cursor.fetchone()
    progress_one_to_one = (one_to_one_progress['completed'] / one_to_one_progress['total']) * 100 if one_to_one_progress['total'] > 0 else 0

    # 計算一對多目錄進度
    cursor.execute("""
        SELECT COUNT(*) as total, SUM(is_completed) as completed
        FROM CourseChapters
        WHERE course_id = %s AND chapter_type = 'classroom'
    """, (course_id,))
    classroom_progress = cursor.fetchone()
    progress_classroom = (classroom_progress['completed'] / classroom_progress['total']) * 100 if classroom_progress['total'] > 0 else 0

    # 重新計算總progress (可自行決定計算邏輯)
    total_progress = (progress_one_to_one + progress_classroom) / 2  # 這裡假設各佔50%權重

    # 判斷是否要更新current_stage
    if course['current_stage'] == 'one_to_one' and progress_one_to_one >= 100:
        course['current_stage'] = 'classroom'
    elif course['current_stage'] == 'classroom' and progress_classroom >= 100:
        course['current_stage'] = 'completed'

    # 更新最新進度和階段回到Courses
    cursor.execute("""
        UPDATE Courses
        SET progress = %s, progress_one_to_one = %s, progress_classroom = %s, current_stage = %s
        WHERE course_id = %s
    """, (total_progress, progress_one_to_one, progress_classroom, course['current_stage'], course_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "hasReadyCourse": True,
        "course_id": course_id,
        "course_name": course['course_name'],
        "current_stage": course['current_stage'],
        "progress": total_progress,
        "progress_one_to_one": progress_one_to_one,
        "progress_classroom": progress_classroom,
        "teacher_card_id": course['teacher_card_id']  # 新增：返回老师卡片ID
    }), 200

# ✅ 取得最新上完的課程
@app.route('/latest_course/<int:user_id>', methods=['GET'])
def get_latest_course(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 直接獲取最新的課程（不一定是正在進行的）
        cursor.execute("""
            SELECT course_id, course_name, current_stage, progress, 
                   progress_one_to_one, progress_classroom
            FROM Courses
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
        """, (user_id,))
        
        course = cursor.fetchone()
        if not course:
            return jsonify({"hasCourse": False}), 200
            
        return jsonify({
            "hasCourse": True,
            "course_id": course['course_id'],
            "course_name": course['course_name'],
            "current_stage": course['current_stage'],
            "progress": course['progress'],
            "progress_one_to_one": course['progress_one_to_one'],
            "progress_classroom": course['progress_classroom']
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ✅ VR結束課程時更新current_stage
@app.route('/finish_course', methods=['POST'])
def finish_course():
    try:
        data = request.json
        if not data or 'course_id' not in data:
            return jsonify({"error": "缺少必要參數"}), 400

        course_id = data['course_id']
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "資料庫連接失敗"}), 500
            
        cursor = conn.cursor()
        
        try:
            # 1. 先檢查課程是否存在
            cursor.execute("SELECT 1 FROM Courses WHERE course_id = %s", (course_id,))
            if not cursor.fetchone():
                return jsonify({"error": "課程不存在"}), 404

            # 2. 強制將所有章節標記為完成（移除 updated_at）
            cursor.execute("""
                UPDATE CourseChapters 
                SET is_completed = 1
                WHERE course_id = %s
            """, (course_id,))

            # 3. 更新課程狀態
            cursor.execute("""
                UPDATE Courses 
                SET current_stage = 'completed',
                    progress = 100,
                    progress_one_to_one = 100,
                    progress_classroom = 100,
                    is_vr_ready = 0,
                    vr_finished_at = NOW()
                WHERE course_id = %s
            """, (course_id,))

            conn.commit()
            
            return jsonify({
                "message": "課程已成功結束",
                "course_id": course_id,
                "status": "completed",
                "progress": 100
            }), 200

        except Exception as db_error:
            print(f"資料庫操作錯誤: {str(db_error)}")
            conn.rollback()
            raise
            
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"結束課程錯誤: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({"error": f"結束課程時發生錯誤: {str(e)}"}), 500
        
# ✅ 課程列表
@app.route('/courses/<int:user_id>', methods=['GET'])
def get_courses(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Courses WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
    return jsonify(cursor.fetchall()), 200

# ✅ 新增課程
@app.route('/add_course', methods=['POST'])
def add_course():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO Courses (user_id, course_name, progress, progress_one_to_one, progress_classroom, current_stage, is_favorite, is_vr_ready, file_type, created_at)
        VALUES (%s, %s, 0, 0, 0, 'one_to_one', FALSE, 0, %s, NOW())
    """, (data['user_id'], data['course_name'], data['file_type'], get_taiwan_now()))

    conn.commit()
    return jsonify({"message": "課程已新增"}), 201

# ✅ 搜尋課程
@app.route('/search_courses/<int:user_id>', methods=['GET'])
def search_courses(user_id):
    query = f"%{request.args.get('query', '').strip()}%"
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM Courses WHERE user_id=%s AND course_name LIKE %s ORDER BY created_at DESC
    """, (user_id, query))
    courses = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(courses), 200


# ✅ 刪除課程
@app.route('/delete_course/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Courses WHERE course_id=%s", (course_id,))
    conn.commit()
    return jsonify({"message": "課程已刪除"}), 200

# ✅ 切換收藏
@app.route('/toggle_favorite/<int:course_id>', methods=['POST'])
def toggle_favorite(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Courses SET is_favorite = NOT is_favorite WHERE course_id=%s", (course_id,))
    conn.commit()
    return jsonify({"message": "收藏狀態已更新"}), 200

# ✅ 課程進度更新
'''@app.route('/update_progress', methods=['POST'])
def update_progress():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE Courses
        SET progress = %s, progress_one_to_one = %s, progress_classroom = %s, current_stage = %s, 
            is_vr_ready = 0, updated_at = NOW()  -- ✅ 讓 updated_at 自動更新
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

    # 加上 is_vr_ready = TRUE
    cursor.execute("""
        UPDATE Courses
        SET is_vr_ready = TRUE, vr_started_at = NOW()
        WHERE course_id = %s
    """, (data['course_id'],))

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "課程已標記為 VR Ready，並開始 VR 時間"}), 200 '''

# ✅ 課程進度更新
@app.route('/update_progress', methods=['POST'])
def update_progress():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "請求數據為空"}), 400
            
        required_fields = ['progress', 'progress_one_to_one', 'progress_classroom', 'current_stage', 'course_id']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"缺少必要字段: {field}"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "資料庫連接失敗"}), 500
            
        cursor = conn.cursor()
        
        # 先檢查課程是否存在
        cursor.execute("SELECT 1 FROM Courses WHERE course_id = %s", (data['course_id'],))
        if not cursor.fetchone():
            return jsonify({"error": "課程不存在"}), 404

        # 更新進度
        cursor.execute("""
            UPDATE Courses
            SET progress = %s, 
                progress_one_to_one = %s, 
                progress_classroom = %s, 
                current_stage = %s, 
                is_vr_ready = 0, 
                updated_at = NOW()
            WHERE course_id = %s
        """, (
            data['progress'], 
            data['progress_one_to_one'], 
            data['progress_classroom'], 
            data['current_stage'], 
            data['course_id']
        ))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "更新失敗，可能是課程ID不存在"}), 404
            
        conn.commit()
        return jsonify({"message": "進度更新成功"}), 200
        
    except Exception as e:
        print(f"更新進度錯誤: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"error": "更新進度時發生錯誤"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            
# ✅ 拿取課程目錄進度
@app.route('/get_chapter_progress', methods=['GET'])
def get_chapter_progress():
    course_id = request.args.get('course_id')
    chapter_type = request.args.get('chapter_type')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 获取完成和总章节数
    cursor.execute("""
        SELECT COUNT(*) as total, 
               SUM(is_completed) as completed
        FROM CourseChapters
        WHERE course_id = %s AND chapter_type = %s
    """, (course_id, chapter_type))
    
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        "total": result['total'],
        "completed": result['completed'] or 0
    })

# ✅ 繼續上課
@app.route('/continue_course', methods=['POST'])
def continue_course():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "請求數據為空"}), 400
            
        course_id = data.get('course_id')
        if not course_id:
            return jsonify({"error": "缺少課程ID"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "資料庫連接失敗"}), 500
            
        cursor = conn.cursor()
        
        # 先檢查課程是否存在
        cursor.execute("SELECT 1 FROM Courses WHERE course_id = %s", (course_id,))
        if not cursor.fetchone():
            return jsonify({"error": "課程不存在"}), 404
            
        # 更新課程狀態，使用台灣時區
        cursor.execute("""
            UPDATE Courses
            SET is_vr_ready = TRUE, 
                vr_started_at = %s
            WHERE course_id = %s
        """, (get_taiwan_now(), course_id))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "更新課程狀態失敗"}), 500
            
        conn.commit()
        return jsonify({"message": "課程已標記為 VR Ready，並開始 VR 時間"}), 200
        
    except Exception as e:
        print(f"繼續課程錯誤: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"error": "繼續課程時發生錯誤"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# ✅ 更新暱稱與頭像
@app.route('/update_nickname/<int:user_id>', methods=['PUT'])
def update_nickname(user_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET username=%s WHERE user_id=%s", (data['nickname'], user_id))
    conn.commit()
    return jsonify({"message": "暱稱更新成功"}), 200

# ✅ 更新頭貼
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


# ✅ 檢查成就
@app.route('/check_achievements/<int:user_id>', methods=['POST'])
def check_achievements(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 取得該用戶的相關數據
    cursor.execute("SELECT COUNT(*) AS course_count FROM Courses WHERE user_id=%s", (user_id,))
    course_count = cursor.fetchone()["course_count"]

    cursor.execute("SELECT total_learning_points FROM Users WHERE user_id=%s", (user_id,))
    total_points = cursor.fetchone()["total_learning_points"]

    cursor.execute("SELECT COUNT(*) AS completed_courses FROM Courses WHERE user_id=%s AND progress=100", (user_id,))
    completed_courses = cursor.fetchone()["completed_courses"]

    # **成就條件**
    ACHIEVEMENT_RULES = {
        "新增一門課程": {"condition": course_count >= 1, "reward": {"coins": 500, "diamonds": 0}},
        "完整上完一門課": {"condition": completed_courses >= 1, "reward": {"coins": 1000, "diamonds": 1}},
        "學習積分達到 500 分": {"condition": total_points >= 500, "reward": {"coins": 2000, "diamonds": 0}},
    }

    new_achievements = []

    for badge_name, rule in ACHIEVEMENT_RULES.items():
        if rule["condition"]:
            # 檢查是否已經擁有該成就
            cursor.execute("SELECT 1 FROM Achievements WHERE user_id = %s AND badge_name = %s", (user_id, badge_name))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO Achievements (user_id, badge_name) VALUES (%s, %s)", (user_id, badge_name))
                new_achievements.append(badge_name)

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "成就檢查完成", "new_achievements": new_achievements}), 200

# ✅ 領取成就獎勵
@app.route('/claim_achievement/<int:user_id>', methods=['POST'])
def claim_achievement(user_id):
    data = request.json
    badge_name = data.get("badge_name")

    if not badge_name:
        return jsonify({"error": "請提供要領取的成就名稱"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 確保用戶擁有該成就，且還未領取
    cursor.execute("""
        SELECT * FROM Achievements WHERE user_id = %s AND badge_name = %s AND is_claimed = FALSE
    """, (user_id, badge_name))
    achievement = cursor.fetchone()

    if not achievement:
        return jsonify({"error": "該成就不存在或已領取"}), 400

    # **獎勵對應表**
    ACHIEVEMENT_REWARDS = {
        "新增一門課程": {"coins": 500, "diamonds": 0},
        "完整上完一門課": {"coins": 1000, "diamonds": 1},
        "學習積分達到 500 分": {"coins": 2000, "diamonds": 0},
    }

    reward = ACHIEVEMENT_REWARDS.get(badge_name)

    if not reward:
        return jsonify({"error": "無法獲取該成就的獎勵"}), 400

    # **更新用戶的金幣 & 鑽石**
    cursor.execute("""
        UPDATE Users SET coins = coins + %s, diamonds = diamonds + %s WHERE user_id = %s
    """, (reward["coins"], reward["diamonds"], user_id))

    # **標記成就為已領取**
    cursor.execute("""
        UPDATE Achievements SET is_claimed = TRUE, claimed_at = NOW() WHERE user_id = %s AND badge_name = %s
    """, (user_id, badge_name))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": f"成功領取 {badge_name} 的獎勵！",
        "coins_received": reward["coins"],
        "diamonds_received": reward["diamonds"]
    }), 200

# ✅ 查詢用戶所有擁有的徽章
@app.route('/get_user_achievements/<int:user_id>', methods=['GET'])
def get_user_achievements(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 取得用戶所有擁有的成就
    cursor.execute("""
        SELECT badge_name, is_claimed FROM Achievements WHERE user_id = %s
    """, (user_id,))
    achievements = cursor.fetchall()

    cursor.close()
    conn.close()

    # 格式化輸出
    return jsonify({"achievements": achievements}), 200
    
# ✅ 查詢當週任務進度
@app.route('/weekly_tasks/<int:user_id>', methods=['GET'])
def get_weekly_tasks(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    week_start = get_week_range()[0]  # 本週週一
    today = get_today()              # 今天（台灣日期）

    # 刪除該用戶前一週（或非本週）的任務記錄
    cursor.execute("DELETE FROM WeeklyTasks WHERE user_id = %s AND week_start <> %s", (user_id, week_start))
    conn.commit()

    # 若今天就是週一，則重置本週的所有任務 is_claimed 為 0
    if today == week_start:
        cursor.execute("""
            UPDATE WeeklyTasks
            SET is_claimed = 0
            WHERE user_id = %s AND week_start = %s
        """, (user_id, week_start))
        conn.commit()

    # 確保 WeeklyTasks 表中有該用戶該週的三筆記錄（若無則插入預設 0）
    for task_id in [1, 2, 3]:
        cursor.execute("""
            INSERT INTO WeeklyTasks (user_id, task_id, week_start, is_claimed)
            VALUES (%s, %s, %s, 0)
            ON DUPLICATE KEY UPDATE is_claimed = is_claimed
        """, (user_id, task_id, week_start))
    conn.commit()

    # 取得 WeeklyTasks 中的 is_claimed 狀態（回傳 0 或 1）
    cursor.execute("""
        SELECT task_id, is_claimed FROM WeeklyTasks
        WHERE user_id = %s AND week_start = %s
    """, (user_id, week_start))
    claimed_tasks = {row["task_id"]: int(row["is_claimed"]) for row in cursor.fetchall()}

    # 計算任務完成度
    cursor.execute("""
        SELECT COUNT(*) AS completed_courses FROM Courses
        WHERE user_id = %s AND progress = 100 AND updated_at >= %s
    """, (user_id, week_start))
    completed_courses = cursor.fetchone()["completed_courses"]

    cursor.execute("""
        SELECT COALESCE(SUM(daily_points), 0) AS weekly_points FROM LearningPointsLog
        WHERE user_id = %s AND date >= %s
    """, (user_id, week_start))
    weekly_points = cursor.fetchone()["weekly_points"]

    cursor.execute("SELECT weekly_streak FROM SigninRecords WHERE user_id = %s", (user_id,))
    streak_record = cursor.fetchone()
    weekly_streak = streak_record["weekly_streak"] if streak_record else 0

    cursor.close()
    conn.close()

    # 回傳 JSON，將 is_claimed 以 0 或 1 表示
    return jsonify({
        "tasks": [
            {"task_id": 1, "name": "完成 5 堂課", "progress": completed_courses, "target": 5, "is_claimed": claimed_tasks.get(1, 0)},
            {"task_id": 2, "name": "學習點數達到 1000", "progress": weekly_points, "target": 1000, "is_claimed": claimed_tasks.get(2, 0)},
            {"task_id": 3, "name": "連續登入 7 天", "progress": weekly_streak, "target": 7, "is_claimed": claimed_tasks.get(3, 0)},
        ]
    }), 200

# ✅ 領取每週任務獎勵
'''@app.route('/claim_weekly_task', methods=['POST'])
def claim_weekly_task():
    data = request.json
    user_id = data.get("user_id")
    task_id = data.get("task_id")

    if task_id not in [1, 2, 3]:
        return jsonify({"error": "無效的任務 ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    week_start = get_week_range()[0]

    # 確保有 WeeklyTasks 記錄（若無則插入預設 0）
    cursor.execute("""
        INSERT INTO WeeklyTasks (user_id, task_id, week_start, is_claimed)
        VALUES (%s, %s, %s, 0)
        ON DUPLICATE KEY UPDATE is_claimed = is_claimed
    """, (user_id, task_id, week_start))
    conn.commit()

    # 檢查是否達標（依據不同任務條件）
    task_conditions = {
        1: "SELECT COUNT(*) AS completed FROM Courses WHERE user_id = %s AND progress = 100 AND updated_at >= %s",
        2: "SELECT COALESCE(SUM(daily_points), 0) AS completed FROM LearningPointsLog WHERE user_id = %s AND date >= %s",
        3: "SELECT weekly_streak AS completed FROM SigninRecords WHERE user_id = %s"
    }
    cursor.execute(task_conditions[task_id], (user_id, week_start))
    completed = cursor.fetchone()["completed"]

    if (task_id == 1 and completed < 5) or (task_id == 2 and completed < 1000) or (task_id == 3 and completed < 7):
        return jsonify({"error": "任務尚未完成"}), 400

    # 標記該任務已領取（設為 1）
    cursor.execute("""
        UPDATE WeeklyTasks SET is_claimed = 1
        WHERE user_id = %s AND task_id = %s AND week_start = %s
    """, (user_id, task_id, week_start))

    # 給用戶加獎勵金幣（此處設定每個任務獎勵 1000 金幣，可依需求調整）
    reward_coins = 1000
    cursor.execute("UPDATE Users SET coins = coins + %s WHERE user_id = %s", (reward_coins, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "成功領取獎勵！",
        "task_id": task_id,
        "reward_coins": reward_coins
    }), 200'''

# ✅ 領取每週任務獎勵
@app.route('/claim_weekly_task', methods=['POST'])
def claim_weekly_task():
    data = request.json
    user_id = data.get("user_id")
    task_id = data.get("task_id")

    if task_id not in [1, 2, 3]:
        return jsonify({"error": "無效的任務 ID"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    week_start = get_week_range()[0]

    # 確保有 WeeklyTasks 記錄（若無則插入預設 0）
    cursor.execute("""
        INSERT INTO WeeklyTasks (user_id, task_id, week_start, is_claimed)
        VALUES (%s, %s, %s, 0)
        ON DUPLICATE KEY UPDATE is_claimed = is_claimed
    """, (user_id, task_id, week_start))
    conn.commit()

    # 檢查是否達標（依據不同任務條件）
    task_conditions = {
        1: "SELECT COUNT(*) AS completed FROM Courses WHERE user_id = %s AND progress = 100 AND updated_at >= %s",
        2: "SELECT COALESCE(SUM(daily_points), 0) AS completed FROM LearningPointsLog WHERE user_id = %s AND date >= %s",
        3: "SELECT weekly_streak AS completed FROM SigninRecords WHERE user_id = %s"
    }
    # 根據 task_id 決定傳入幾個參數
    if task_id == 3:
        cursor.execute(task_conditions[task_id], (user_id,))
    else:
        cursor.execute(task_conditions[task_id], (user_id, week_start))
    completed = cursor.fetchone()["completed"]

    if (task_id == 1 and completed < 5) or (task_id == 2 and completed < 1000) or (task_id == 3 and completed < 7):
        return jsonify({"error": "任務尚未完成"}), 400

    # 標記該任務已領取（設為 1）
    cursor.execute("""
        UPDATE WeeklyTasks SET is_claimed = 1
        WHERE user_id = %s AND task_id = %s AND week_start = %s
    """, (user_id, task_id, week_start))

    # 給用戶加獎勵金幣（此處設定每個任務獎勵 1000 金幣，可依需求調整）
    reward_coins = 1000
    cursor.execute("UPDATE Users SET coins = coins + %s WHERE user_id = %s", (reward_coins, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "成功領取獎勵！",
        "task_id": task_id,
        "reward_coins": reward_coins
    }), 200
    
# ✅ 收藏pre課程（修正重複插入問題）
@app.route('/save_course', methods=['POST'])
def save_course():
    data = request.json
    user_id = data.get("user_id")
    course_name = data.get("course_name")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT IGNORE INTO SavedCourses (user_id, course_name) VALUES (%s, %s)
    """, (user_id, course_name))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "課程收藏成功"}), 200

# ✅ 查詢用戶的收藏 pre 課程
@app.route('/saved_courses/<int:user_id>', methods=['GET'])
def get_saved_courses(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT course_name FROM SavedCourses WHERE user_id = %s", (user_id,))
    saved_courses = [row["course_name"] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify({"saved_courses": saved_courses}), 200

# ✅ 取消收藏 pre 課程
@app.route('/remove_course', methods=['POST'])
def remove_course():
    data = request.json
    user_id = data.get("user_id")
    course_name = data.get("course_name")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM SavedCourses WHERE user_id = %s AND course_name = %s
    """, (user_id, course_name))
    rows_affected = cursor.rowcount  # 獲取影響的行數
    conn.commit()

    cursor.close()
    conn.close()

    if rows_affected > 0:
        return jsonify({"message": "課程已取消收藏"}), 200
    else:
        return jsonify({"error": "該課程未收藏或已刪除"}), 400

# ✅ 獲取課程回顧資料
@app.route('/course_review/<int:course_id>', methods=['GET'])
def get_course_review(course_id):
    print(f"🔍 开始获取课程回顾数据 - CourseID: {course_id}")
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ 数据库连接失败")
            return jsonify({"error": "数据库连接失败"}), 500
            
        cursor = conn.cursor(dictionary=True, buffered=True)  # 使用 buffered cursor
        
        # 检查课程是否存在，并获取 user_id
        print(f"🔍 查询课程信息 - CourseID: {course_id}")
        cursor.execute("""
            SELECT course_id, user_id, course_name 
            FROM Courses 
            WHERE course_id = %s
        """, (course_id,))
        course = cursor.fetchone()
        
        if not course:
            print(f"❌ 课程不存在 - CourseID: {course_id}")
            return jsonify({"error": "课程不存在"}), 404

        print(f"✅ 找到课程信息 - CourseID: {course_id}, UserID: {course['user_id']}, CourseName: {course['course_name']}")

        # 查询课程评价数据
        print(f"🔍 查询课程评价数据 - CourseID: {course_id}, UserID: {course['user_id']}")
        cursor.execute("""
            SELECT accuracy_score, understanding_score, expression_score, interaction_score,
                   teacher_comment, student1_feedback, student2_feedback, student3_feedback,
                   good_points, improvement_points, review_id
            FROM CourseReviews
            WHERE course_id = %s AND user_id = %s
        """, (course_id, course['user_id']))
        
        review_data = cursor.fetchone()
        print(f"📊 评价数据查询结果: {review_data}")
        
        # 如果没有找到评价数据，使用默认值
        if not review_data:
            print(f"⚠️ 未找到评价数据，尝试创建默认评价 - CourseID: {course_id}, UserID: {course['user_id']}")
            try:
                default_review = {
                    "accuracy_score": 50,
                    "understanding_score": 50,
                    "expression_score": 50,
                    "interaction_score": 50,
                    "teacher_comment": "今天的表现非常出色，特别是在概念解释方面有明显进步。你对核心理论的掌握度很高，建议下次可以多举一些生活中的例子，让概念更容易理解。",
                    "student1_feedback": "你把复杂的概念讲得很清楚！尤其是在解释那个难懂的部分时，用了很好的比喻，让我一下就理解了。",
                    "student2_feedback": "我觉得你的逻辑思维很清晰，解题过程也很有条理。如果能多分享一些实际应用的场景就更好了。",
                    "student3_feedback": "你提出的观点很有创意！让我看到这个理论的新角度。期待下次能听到更多你的想法。",
                    "good_points": json.dumps(["概念解释清晰准确", "举例生动有趣", "与同学互动热络"]),
                    "improvement_points": json.dumps(["可以多分享实际应用场景", "建议控制节奏，不要说太快"])
                }
                
                print("📝 准备插入默认评价数据")
                cursor.execute("""
                    INSERT INTO CourseReviews 
                    (course_id, user_id, accuracy_score, understanding_score, expression_score, 
                     interaction_score, teacher_comment, student1_feedback, student2_feedback, 
                     student3_feedback, good_points, improvement_points)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    course_id, course['user_id'],
                    default_review["accuracy_score"],
                    default_review["understanding_score"],
                    default_review["expression_score"],
                    default_review["interaction_score"],
                    default_review["teacher_comment"],
                    default_review["student1_feedback"],
                    default_review["student2_feedback"],
                    default_review["student3_feedback"],
                    default_review["good_points"],
                    default_review["improvement_points"]
                ))
                conn.commit()
                print("✅ 已插入默认评价数据")
                review_data = default_review
            except Exception as e:
                print(f"❌ 插入默认评价数据失败: {str(e)}")
                print(f"❌ 错误详情: {type(e).__name__}")
                if hasattr(e, 'args'):
                    print(f"❌ 错误参数: {e.args}")
                return jsonify({"error": f"创建默认评价数据失败: {str(e)}"}), 500

        print("✅ 开始查询课程积分")
        # 查询课程积分
        cursor.execute("""
            SELECT earned_points
            FROM CoursePointsLog
            WHERE course_id = %s
        """, (course_id,))
        
        points_data = cursor.fetchone()
        earned_points = points_data['earned_points'] if points_data else 156
        print(f"📈 积分数据: {earned_points}")

        # 处理 JSON 字段
        good_points = []
        improvement_points = []
        
        try:
            if review_data.get('good_points'):
                good_points = json.loads(review_data['good_points'])
            if review_data.get('improvement_points'):
                improvement_points = json.loads(review_data['improvement_points'])
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析错误: {str(e)}")
            print(f"⚠️ good_points 原始数据: {review_data.get('good_points')}")
            print(f"⚠️ improvement_points 原始数据: {review_data.get('improvement_points')}")
            good_points = []
            improvement_points = []

        # 组合返回数据
        response_data = {
            "accuracy_score": review_data.get("accuracy_score", 50),
            "understanding_score": review_data.get("understanding_score", 50),
            "expression_score": review_data.get("expression_score", 50),
            "interaction_score": review_data.get("interaction_score", 50),
            "teacher_comment": review_data.get("teacher_comment", ""),
            "student1_feedback": review_data.get("student1_feedback", ""),
            "student2_feedback": review_data.get("student2_feedback", ""),
            "student3_feedback": review_data.get("student3_feedback", ""),
            "earned_points": earned_points,
            "good_points": good_points,
            "improvement_points": improvement_points
        }

        print("✅ 成功获取课程回顾数据")
        return jsonify(response_data)

    except Exception as e:
        print(f"❌ 获取课程回顾数据时发生错误: {str(e)}")
        print(f"❌ 错误类型: {type(e).__name__}")
        if hasattr(e, 'args'):
            print(f"❌ 错误参数: {e.args}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        return jsonify({"error": f"获取课程回顾数据时发生错误: {str(e)}"}), 500

    finally:
        try:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
            print("✅ 数据库连接已关闭")
        except Exception as e:
            print(f"⚠️ 关闭数据库连接时发生错误: {str(e)}")
            # 不抛出异常，因为这是在 finally 块中 
        
# ✅ 抽卡
@app.route('/draw_card/<int:user_id>', methods=['POST'])
def draw_card(user_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "資料庫連接失敗"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # 獲取抽卡類型（普通/高級）
        draw_type = request.args.get('type', 'normal')
        
        # 獲取用戶當前資源
        cursor.execute("SELECT coins, diamonds FROM Users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "用戶不存在"}), 404
        
        # 檢查資源是否足夠
        if draw_type == 'normal' and user['coins'] < 500:
            return jsonify({"error": "金幣不足"}), 400
        elif draw_type == 'premium' and user['diamonds'] < 3:
            return jsonify({"error": "鑽石不足"}), 400
        
        # 設定抽卡機率
        if draw_type == 'normal':
            probabilities = {
                '絕密': 0.05,   # 絕密 5%
                '機密': 0.25,  # 機密 25%
                '隱密': 0.7   # 隱密 70%
            }
        else:
            probabilities = {
                '絕密': 0.15,   # 絕密 15%
                '機密': 0.35,  # 機密 35%
                '隱密': 0.5   # 隱密 50%
            }
        
        # 隨機抽取卡片
        import random
        rarity = random.choices(list(probabilities.keys()), weights=list(probabilities.values()))[0]
        
        # 根據稀有度選擇卡片
        cursor.execute("""
            SELECT card_id, name, rarity 
            FROM Cards 
            WHERE rarity = %s 
            ORDER BY RAND() 
            LIMIT 1
        """, (rarity,))
        card = cursor.fetchone()
        
        if not card:
            return jsonify({"error": "找不到對應稀有度的卡片"}), 500

        # 檢查用戶是否已經擁有這張卡片
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM UserCards 
            WHERE user_id = %s AND card_id = %s
        """, (user_id, card['card_id']))
        card_count = cursor.fetchone()['count']
        
        # 扣除資源
        if draw_type == 'normal':
            cursor.execute("UPDATE Users SET coins = coins - 500 WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("UPDATE Users SET diamonds = diamonds - 3 WHERE user_id = %s", (user_id,))
        
        # 記錄抽卡結果（使用 UserCards 表）

        cursor.execute("""
            INSERT INTO UserCards (user_id, card_id, obtained_date)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE obtained_date = %s
        """, (user_id, card['card_id'], get_taiwan_now(), get_taiwan_now()))
        
        # 獲取更新後的資源數量
        cursor.execute("SELECT coins, diamonds FROM Users WHERE user_id = %s", (user_id,))
        updated_user = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "card_id": card['card_id'],
            "card_name": card['name'],
            "rarity": card['rarity'],
            "remaining_coins": updated_user['coins'],
            "remaining_diamonds": updated_user['diamonds'],
            "is_new_teacher_card": (card_count == 0)  # 如果是第一次獲得這張卡片就是 true
        }), 200
        
    except Exception as e:
        print(f"抽卡錯誤: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({"error": "抽卡過程中發生錯誤"}), 500

# ✅ 獲取用戶擁有的卡片
@app.route('/user_cards/<int:user_id>', methods=['GET'])
def get_user_cards(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 查询用户拥有的所有卡片
    cursor.execute("""
        SELECT C.card_id, C.name, C.rarity, UC.is_selected
        FROM Cards C
        JOIN UserCards UC ON C.card_id = UC.card_id
        WHERE UC.user_id = %s
    """, (user_id,))
    
    cards = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        "cards": cards
    }), 200

# ✅ 選擇老師卡片
'''@app.route('/select_teacher_card', methods=['POST'])
def select_teacher_card():
    data = request.json
    user_id = data.get('user_id')
    card_id = data.get('card_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 先将该用户所有卡片设置为未选中
        cursor.execute("""
            UPDATE UserCards 
            SET is_selected = 0,
                updated_at = %s
            WHERE user_id = %s
        """, (get_taiwan_now(), user_id))
        
        # 将选中的卡片设置为已选中
        cursor.execute("""
            UPDATE UserCards 
            SET is_selected = 1,
                updated_at = %s
            WHERE user_id = %s AND card_id = %s
        """, (get_taiwan_now(), user_id, card_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "message": "老師卡片選擇成功",
            "selected_card_id": card_id
        }), 200
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({
            "error": f"選擇老師卡片發生錯誤: {str(e)}"
        }), 500'''

# ✅ 選擇老師卡片
@app.route('/select_teacher_card', methods=['POST'])
def select_teacher_card():
    data = request.json
    user_id = data.get('user_id')
    card_id = data.get('card_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 先将该用户所有卡片设置为未选中
        cursor.execute("""
            UPDATE UserCards 
            SET is_selected = 0
            WHERE user_id = %s
        """, (user_id,))
        
        # 将选中的卡片设置为已选中
        cursor.execute("""
            UPDATE UserCards 
            SET is_selected = 1
            WHERE user_id = %s AND card_id = %s
        """, (user_id, card_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "message": "老師卡片選擇成功",
            "selected_card_id": card_id,
            "success": True
        }), 200
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({
            "error": f"選擇老師卡片發生錯誤: {str(e)}",
            "success": False
        }), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
