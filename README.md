🎓 FeynDora 學習系統 API (Flask + MySQL)

這是一個使用 Flask 框架搭配 MySQL 資料庫所建構的完整學習平台後端 API，支援使用者註冊、登入、課程管理、簽到系統、學習點數更新、排行榜、成就系統、任務系統、抽卡與卡牌選擇等功能。適合應用於教育科技相關產品的 MVP 原型或正式平台開發。

🚀 技術架構
	•	後端框架：Flask
	•	資料庫：MySQL (支援 DATABASE_URL 環境變數配置)
	•	使用套件：
	•	mysql-connector-python
	•	bcrypt（密碼雜湊）
	•	pytz（處理時區）
	•	datetime（時間操作）
	•	random（抽卡功能）
	•	佈署方式：可透過 gunicorn + nginx 或 Docker 進行伺服器佈署

📚 功能總覽

🔐 使用者相關
	•	註冊與登入（含密碼加密）
	•	更新暱稱與頭像
	•	刪除帳號

📘 課程功能
	•	新增、刪除、搜尋與收藏課程
	•	課程進度追蹤（支援一對一、一對多學習階段）
	•	課程回顧資料與學習分數查詢

🏆 任務與成就
	•	週任務系統（課程完成、學習點數、連續登入）
	•	成就系統（首次完成課程、學習積分達標等）
	•	領取任務與成就獎勵

🎲 抽卡系統
	•	支援普通/高級抽卡
	•	根據機率分配稀有度（絕密、機密、隱密）
	•	卡片收藏與老師卡片選擇功能

📈 排行榜系統
	•	每日與每週學習積分排行榜
	•	用戶個人排名查詢

🕓 簽到系統
	•	每日簽到與連續簽到獎勵
	•	每週自動重置簽到記錄

🔧 使用方式
	1.	安裝所需套件：

pip install -r requirements.txt


 2.	設定環境變數（可選）：

export DATABASE_URL=mysql://user:password@host:port/database

 3.	啟動伺服器：

python app.py

伺服器會預設在 http://0.0.0.0:8000 運行。

📂 API 端點列表（部分）

Method	Endpoint	說明
POST	/register	註冊帳號
POST	/login	使用者登入
GET	/daily_rankings	每日積分排行榜
POST	/update_learning_points	更新學習點數
GET	/weekly_tasks/<user_id>	查詢本週任務
POST	/draw_card/<user_id>	抽卡
GET	/user_cards/<user_id>	查詢卡片收藏
POST	/select_teacher_card	選擇老師卡片

👉 更多 API 請參考 app.py 原始碼內註解

🙋‍♀️ 作者

魏莘儒
資訊管理系 | 國立中正大學
對教育科技、AI 與後端開發有高度熱情！

📬 聯絡方式
jessie910812@gmail.com
