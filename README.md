<h1 align="center">🎓 FeynDora 學習系統 API</h1>
<h3 align="center">🚀 Powered by Flask + MySQL</h3>
<p align="center">完整支援教育平台的後端服務：用戶管理、課程進度、排行榜、抽卡與成就系統</p>

---

## 📖 專案簡介

這是一個使用 **Flask** 框架搭配 **MySQL** 資料庫所建構的完整學習平台後端 API，支援使用者註冊、登入、課程管理、簽到系統、學習點數更新、排行榜、成就系統、任務系統、抽卡與卡牌選擇等功能。  
適合應用於教育科技相關產品的 MVP 原型或正式平台開發。

---

## 🚀 技術架構

- **後端框架**：Flask  
- **資料庫**：MySQL（支援 `DATABASE_URL` 環境變數配置）
- **使用套件**：
  - `mysql-connector-python`
  - `bcrypt`（密碼雜湊）
  - `pytz`（處理時區）
  - `datetime`（時間操作）
  - `random`（抽卡功能）
- **佈署方式**：
  - Gunicorn + Nginx
  - Docker（可選）

---

## 📚 功能總覽

### 🔐 使用者相關
- 註冊與登入（含密碼加密）
- 更新暱稱與頭像
- 刪除帳號

### 📘 課程功能
- 新增、刪除、搜尋與收藏課程
- 課程進度追蹤（支援一對一、一對多學習階段）
- 課程回顧資料與學習分數查詢

### 🏆 任務與成就
- 週任務系統（課程完成、學習點數、連續登入）
- 成就系統（首次完成課程、學習積分達標等）
- 領取任務與成就獎勵

### 🎲 抽卡系統
- 支援普通/高級抽卡
- 根據機率分配稀有度（絕密、機密、隱密）
- 卡片收藏與老師卡片選擇功能

### 📈 排行榜系統
- 每日與每週學習積分排行榜
- 用戶個人排名查詢

### 🕓 簽到系統
- 每日簽到與連續簽到獎勵
- 每週自動重置簽到記錄

---
## 🙋‍♀️ 作者

魏莘儒
資訊管理系 | 國立中正大學
對教育科技、AI 與後端開發有高度熱情！

📬 聯絡方式

📧 jessie910812@gmail.com
📍 Taiwan
