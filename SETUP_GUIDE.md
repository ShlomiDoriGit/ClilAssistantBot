# 🌿 בוט וואטסאפ — כלילת דורי, דיאטנית קלינית
## מדריך הפעלה מלא

---

## מה הבוט עושה?

1. **מאזין** להודעות נכנסות בוואטסאפ של כלילת
2. **מתמלל** הקלטות קוליות אוטומטית (Whisper)
3. **מנסח** תשובה מקצועית (Claude AI)
4. **שולח לטלגרם** של כלילת עם 3 אפשרויות:
   - ✅ **שלחי** — שולח מיד ללקוח
   - ✏️ **ערכי** — כלילת כותבת נוסח אחר
   - 🚫 **דלגי** — לא שולח כלום

---

## שלב 1 — Green API (חיבור וואטסאפ, חינם)

1. היכנסי לאתר: **https://green-api.com**
2. לחצי על **"Free"** → צרי חשבון
3. לחצי **"Create Instance"**
4. בממשק, לחצי **"Scan QR"** וסרקי מהאפליקציה של כלילת
5. שמרי את שני הערכים הבאים:
   - `idInstance` (מספר, לדוגמה: `1234567890`)
   - `apiTokenInstance` (מחרוזת ארוכה)

---

## שלב 2 — בוט טלגרם

1. פתחי שיחה עם **@BotFather** בטלגרם
2. שלחי: `/newbot`
3. תני שם לבוט (לדוגמה: `KalilaAssistantBot`)
4. שמרי את ה-**Token** שמתקבל

### מציאת ה-Chat ID שלך:
1. שלחי הודעה לבוט שיצרת
2. היכנסי לכתובת זו בדפדפן (החלפי את ה-TOKEN):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
3. חפשי `"id"` בתוך `"chat"` — זה ה-Chat ID שלך

---

## שלב 3 — API Keys

- **Claude:** https://console.anthropic.com → API Keys → Create Key
- **OpenAI (Whisper):** https://platform.openai.com/api-keys → Create Key

---

## שלב 4 — העלאה ל-Railway (חינם)

### הכנת הקוד ל-GitHub:
1. צרי חשבון GitHub אם אין: **https://github.com**
2. צרי Repository חדש בשם `kalila-bot`
3. העלי את 4 הקבצים:
   - `main.py`
   - `requirements.txt`
   - `railway.toml`
   - `.gitignore`
   - ⚠️ **אל תעלי את `.env.example`** עם פרטים אמיתיים!

### הפעלה ב-Railway:
1. היכנסי לאתר: **https://railway.app**
2. לחצי **"New Project"** → **"Deploy from GitHub repo"**
3. בחרי את ה-repo `kalila-bot`
4. לחצי **"Variables"** והוסיפי את המשתנים הבאים:

```
GREEN_API_INSTANCE    =  [ה-idInstance מGreen API]
GREEN_API_TOKEN       =  [ה-apiTokenInstance]
TELEGRAM_BOT_TOKEN    =  [Token מBotFather]
TELEGRAM_CHAT_ID      =  [ה-Chat ID שלך]
CLAUDE_API_KEY        =  [Claude API Key]
OPENAI_API_KEY        =  [OpenAI API Key]
```

5. לחצי **"Deploy"** — הבוט יעלה תוך ~2 דקות!

---

## שלב 5 — בדיקה

1. שלחי הודעת בדיקה לוואטסאפ של כלילת ממספר אחר
2. תוך שניות צריכה להגיע הודעה בטלגרם עם התשובה המוצעת
3. לחצי ✅ — ההודעה תישלח ללקוח

---

## עלויות

| שירות | עלות |
|-------|------|
| Green API | חינם עד 500 הודעות/חודש |
| Railway | חינם עד $5 credit/חודש |
| Whisper (OpenAI) | ~$0.006 לדקת קול |
| Claude API | ~$0.01-0.03 לפנייה |
| **סה"כ** | **כמעט חינם לעסק קטן** |

---

## שאלות נפוצות

**ש: מה קורה אם כלילת לא עונה בטלגרם?**
ת: הלקוח לא מקבל תשובה עד שכלילת מאשרת — שום דבר לא נשלח אוטומטית ללא אישור.

**ש: האם ניתן לשנות את נוסח התשובות?**
ת: כן, ב-`main.py` בחלק `SYSTEM_PROMPT` ניתן לשנות את ההנחיות לבוט.

**ש: מה אם כלילת רוצה לערוך תשובה?**
ת: לוחצת ✏️ ואז שולחת את הנוסח הרצוי כהודעה בטלגרם.

---

## תמיכה טכנית
במקרה של בעיות, בדקי את לוגי Railway תחת **"Deployments → View Logs"**
