from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import bcrypt
import os
import pytz
from datetime import datetime, date, timedelta
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
            SELECT U.user_id, U.username, U.avatar_id, L.daily_points,
                   RANK() OVER (ORDER BY L.daily_points DESC) AS ranking
            FROM LearningPointsLog L
            JOIN Users U ON L.user_id = U.user_id
            WHERE L.date = %s
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
                SELECT U.user_id, U.username, U.avatar_id, L.daily_points,
                       RANK() OVER (ORDER BY L.daily_points DESC) AS ranking
                FROM LearningPointsLog L
                JOIN Users U ON L.user_id = U.user_id
                WHERE L.date = %s
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
            SELECT U.user_id, U.username, U.avatar_id, SUM(L.daily_points) AS weekly_points,
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
                SELECT U.user_id, U.username, U.avatar_id, SUM(L.daily_points) AS weekly_points,
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

    # 查詢用戶的簽到記錄
    cursor.execute("SELECT signin_day, has_claimed_today, last_signin_date FROM SigninRecords WHERE user_id = %s", (user_id,))
    record = cursor.fetchone()

    cursor.close()
    conn.close()

    if not record:
        return jsonify({"error": "用戶簽到記錄不存在"}), 400

    # ✅ **取得今天的台灣時間**
    server_today = get_today()  # `get_today()` 已經回傳台灣時區

    # ✅ **判斷今天是否已經簽到過**
    already_signed_in = record["last_signin_date"] == server_today

    response_data = {
        "signin_day": record["signin_day"],
        "has_claimed_today": already_signed_in,  # 根據 `last_signin_date` 判斷
        "last_signin_date": record["last_signin_date"],
        "server_today": server_today  # ✅ **回傳後端的當前日期**
    }

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

    today = get_today()  # 確保日期格式統一 (YYYY-MM-DD)
    start_of_week, end_of_week = get_week_range()  # 取得本週的範圍（週一到週日）

    # 🔹 檢查簽到狀態
    cursor.execute("SELECT signin_day, last_signin_date, weekly_streak FROM SigninRecords WHERE user_id = %s", (user_id,))
    record = cursor.fetchone()

    if not record:
        return jsonify({"error": "用戶簽到記錄不存在"}), 400

    last_signin_date = record["last_signin_date"]
    weekly_streak = record["weekly_streak"]

    # 🔹 **防止重複簽到**
    if last_signin_date == today:
        return jsonify({
            "error": "今天已經領取過獎勵",
            "last_signin_date": last_signin_date
        }), 400

    signin_day = record["signin_day"]

    # ✅ **更新連續簽到計算**
    if last_signin_date and (last_signin_date + timedelta(days=1)) == today:
        # 連續簽到，weekly_streak +1
        weekly_streak += 1
    else:
        # 不是連續簽到，重置 weekly_streak
        weekly_streak = 1

    # ✅ **如果是新的一週，重新計算連續簽到**
    if today == start_of_week:
        weekly_streak = 1

    # 設定獎勵
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

    # 🔹 更新 `SigninRecords` 記錄簽到
    next_signin_day = 1 if signin_day == 7 else signin_day + 1
    cursor.execute("""
        UPDATE SigninRecords 
        SET signin_day = %s, last_signin_date = %s, weekly_streak = %s
        WHERE user_id = %s
    """, (next_signin_day, today, weekly_streak, user_id))

    # 🔹 更新 `Users` 表
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
        "weekly_streak": weekly_streak,  # ✅ 新增這個欄位
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
@app.route('/current_stage/<int:user_id>', methods=['GET'])
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
    }), 200


# ✅ VR結束課程時更新current_stage
@app.route('/finish_course', methods=['POST'])
def finish_course():
    data = request.json
    course_id = data['course_id']
    current_stage = data['current_stage']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Courses
        SET current_stage = %s, vr_finished_at = NOW()
        WHERE course_id = %s
    """, (current_stage, course_id))
    
    conn.commit()

    cursor.close()
    conn.close()
    return jsonify({"message": "課程進度已更新"}), 200

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
    """, (data['user_id'], data['course_name'], data['file_type']))

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
@app.route('/update_progress', methods=['POST'])
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
    return jsonify({"message": "課程已標記為 VR Ready，並開始 VR 時間"}), 200

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

    week_start = get_week_range()[0]  # 取得本週的起始日期（週一）

    # ✅ 計算【完成 5 堂課】
    cursor.execute("""
        SELECT COUNT(*) AS completed_courses
        FROM Courses
        WHERE user_id = %s AND progress = 100 AND updated_at >= %s
    """, (user_id, week_start))
    completed_courses = cursor.fetchone()["completed_courses"]

    # ✅ 計算【學習點數達 1000】
    cursor.execute("""
        SELECT COALESCE(SUM(daily_points), 0) AS weekly_points
        FROM LearningPointsLog
        WHERE user_id = %s AND date >= %s
    """, (user_id, week_start))
    weekly_points = cursor.fetchone()["weekly_points"]

    # ✅ 計算【連續登入 7 天】
    cursor.execute("""
        SELECT weekly_streak FROM SigninRecords WHERE user_id = %s
    """, (user_id,))
    streak_record = cursor.fetchone()
    weekly_streak = streak_record["weekly_streak"] if streak_record else 0

    cursor.close()
    conn.close()

    # 回傳進度
    return jsonify({
        "tasks": [
            {"task_id": 1, "name": "完成 5 堂課", "progress": completed_courses, "target": 5},
            {"task_id": 2, "name": "學習點數達 1000", "progress": weekly_points, "target": 1000},
            {"task_id": 3, "name": "連續登入 7 天", "progress": weekly_streak, "target": 7},
        ]
    }), 200

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

    week_start = get_week_range()[0]  # 本週週一

    # **確保用戶沒有在本週重複領取**
    cursor.execute("""
        SELECT 1 FROM Achievements 
        WHERE user_id = %s AND badge_name = %s AND week_start = %s
    """, (user_id, f"weekly_task_{task_id}", week_start))
    
    if cursor.fetchone():
        return jsonify({"error": "本週已經領取過獎勵"}), 400

    # **檢查任務是否達標**
    if task_id == 1:
        cursor.execute("""
            SELECT COUNT(*) AS completed_courses FROM Courses 
            WHERE user_id = %s AND progress = 100 AND updated_at >= %s
        """, (user_id, week_start))
        is_completed = cursor.fetchone()["completed_courses"] >= 5
    elif task_id == 2:
        cursor.execute("""
            SELECT COALESCE(SUM(daily_points), 0) AS weekly_points FROM LearningPointsLog 
            WHERE user_id = %s AND date >= %s
        """, (user_id, week_start))
        is_completed = cursor.fetchone()["weekly_points"] >= 1000
    elif task_id == 3:
        cursor.execute("SELECT weekly_streak FROM SigninRecords WHERE user_id = %s", (user_id,))
        streak_record = cursor.fetchone()
        is_completed = streak_record["weekly_streak"] >= 7 if streak_record else False

    if not is_completed:
        return jsonify({"error": "任務尚未完成"}), 400

    # **發送獎勵**
    reward = {"coins": 500, "diamonds": 1}
    cursor.execute("""
        UPDATE Users SET coins = coins + %s, diamonds = diamonds + %s WHERE user_id = %s
    """, (reward["coins"], reward["diamonds"], user_id))

    # **標記已領取（記錄本週）**
    cursor.execute("""
        INSERT INTO Achievements (user_id, badge_name, is_claimed, claimed_at, week_start) 
        VALUES (%s, %s, TRUE, NOW(), %s)
    """, (user_id, f"weekly_task_{task_id}", week_start))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "成功領取獎勵！",
        "task_id": task_id,
        "coins_received": reward["coins"],
        "diamonds_received": reward["diamonds"]
    }), 200
    
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
