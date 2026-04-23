# Meteor Focus — Issue Reports Dashboard

דשבורד חי ל־triage של דיווחי "Issue Reported" שמגיעים מהמערכת ל־Gmail. מתעדכן אוטומטית כל 15 דקות.

🌐 **Live:** https://dianam242.github.io/MeteorFocus/

---

## שתי דרכים להפעיל — בחרי אחת

### 🟢 דרך מומלצת: Google Apps Script (פשוט)

הכי מהיר להתקין, בלי Google Cloud, בלי OAuth consent screen.

📖 **ראי: [`SETUP_APPS_SCRIPT.md`](SETUP_APPS_SCRIPT.md)**

### 🟡 דרך חלופית: GitHub Actions + Google Cloud

אם את מעדיפה שכל הפעולות יירוצו מ־GitHub (ולא מ־Gmail שלך), ראי את ההוראות למטה.
לא מומלץ אלא אם יש סיבה ספציפית להעדיף את זה על פני Apps Script.

---

## מבנה הקבצים

```
MeteorFocus/
├── index.html              ← הדשבורד עצמו (UI)
├── data.json               ← הנתונים, מתעדכן אוטומטית
├── apps_script.gs          ← הגרסה של Apps Script (מומלץ)
├── update_data.py          ← סקריפט ששולף מ־Gmail (גרסת GitHub Actions)
├── get_refresh_token.py    ← סקריפט חד־פעמי לקבלת token (גרסת GitHub Actions)
├── requirements.txt        ← Python dependencies
├── SETUP_APPS_SCRIPT.md    ← הוראות הפעלה של גרסת Apps Script
├── .gitignore
└── .github/workflows/
    └── update-data.yml     ← GitHub Actions — רץ כל 15 דק׳ (גרסת GitHub Actions)
```

---

## 🚀 התקנה ראשונית — גרסת GitHub Actions (פעם אחת בלבד)

### שלב 1 — יצירת פרויקט ב־Google Cloud

1. לכי ל־ [Google Cloud Console](https://console.cloud.google.com/)
2. צרי פרויקט חדש (או בחרי קיים). שם מוצע: `meteor-focus-dashboard`
3. בתפריט → **APIs & Services** → **Library** → חפשי **Gmail API** → **Enable**

### שלב 2 — יצירת OAuth Credentials

1. **APIs & Services** → **OAuth consent screen**
   - User Type: **External**
   - App name: `Meteor Focus Dashboard`
   - Support email: `meteorfocus@gmail.com`
   - Scopes: הוסיפי `https://www.googleapis.com/auth/gmail.readonly`
   - Test users: הוסיפי את `meteorfocus@gmail.com`
   - שמרי. **אל תגישי ל־Publishing** — נשאר ב־Testing זה בסדר.

2. **APIs & Services** → **Credentials** → **Create credentials** → **OAuth client ID**
   - Application type: **Desktop app**
   - Name: `Meteor Focus Dashboard Local`
   - הורידי את ה־JSON ושמרי כ־`credentials.json` בתיקיית הפרויקט (לא לעשות commit!)

### שלב 3 — קבלת Refresh Token (מקומית, פעם אחת)

במסוף, בתוך תיקיית הפרויקט:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python get_refresh_token.py
```

ייפתח דפדפן, תתחברי עם `meteorfocus@gmail.com`, תאשרי הרשאה. הסקריפט ידפיס 3 ערכים:
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

**שמרי אותם — הם יכנסו ל־GitHub Secrets.**

### שלב 4 — הוספת Secrets ל־GitHub

1. לכי ל־ https://github.com/DianaM242/MeteorFocus/settings/secrets/actions
2. **New repository secret** × 3:
   - `GMAIL_CLIENT_ID` = (מהשלב הקודם)
   - `GMAIL_CLIENT_SECRET` = (מהשלב הקודם)
   - `GMAIL_REFRESH_TOKEN` = (מהשלב הקודם)

### שלב 5 — הפעלה

1. **Actions** tab → **Update data.json from Gmail** → **Run workflow** → **Run workflow**
2. תוך דקה־שתיים, `data.json` יתעדכן ויתבצע commit אוטומטי
3. GitHub Pages יטען את הגרסה החדשה תוך 1-2 דקות

מעכשיו זה רץ אוטומטית כל 15 דקות — בלי התערבות שלך.

---

## 🧪 הפעלה מקומית (אופציונלי — לבדיקות)

```bash
export GMAIL_CLIENT_ID="..."
export GMAIL_CLIENT_SECRET="..."
export GMAIL_REFRESH_TOKEN="..."
export DAYS_BACK=30
python update_data.py
```

זה מייצר `data.json` מקומי. לתצוגה פתוחי `index.html` בדפדפן (רצוי דרך שרת מקומי, למשל `python -m http.server 8000`).

---

## 🎛 מה יש בדשבורד

### הפרדה ויזואלית
- **🐛 דיווחי שאלות (Type A)** — טור ימני רחב, רקע פסטל סגול של MF
- **📩 פניות חדשות (Type B)** — טור שמאלי צר, רקע פסטל אדום (פניות של לקוחות — דחוף!)

### סיווג אוטומטי (Type A)
כל תלונה מסווגת לפי מילות מפתח בטקסט:
- 🟣 **ניסוח** — ("לא ברור", "לא הבנתי", "השאלה לא ברורה"...)
- 🔴 **תשובה שגויה** — ("תשובה שגויה", "סומן לא נכון"...)
- 🟠 **יותר מתשובה אחת** — ("שתי תשובות", "יותר מתשובה"...)
- 🔵 **הסבר לא ברור** — ("הסבר לא ברור", "אין הסבר"...)
- ⚪ **אחר** — לא מתאים לאף קטגוריה

(הכללים נמצאים ב־`update_data.py` → `CLASSIFICATION_RULES` (או ב־`apps_script.gs` → `CLASSIFICATION_RULES`). קל להוסיף/לערוך מילות מפתח.)

### פעולות על כל פריט
- 📋 **שאלה** — העתקה מלאה של השאלה + תשובות לפי `question_order` + הסבר + קטגוריה (מוכן להדבקה למפתח)
- 📋 **Q-ID** / **User-ID** / **קישור Gmail**
- ✓ **טופל** — הסרה מהרשימה (נשמר ב־localStorage מקומית בדפדפן)
- ↩ **החזר** — ביטול סימון "טופל"

### סינונים
- טווח זמן (שבוע / שבועיים / חודש / 3 חודשים / הכל)
- חיפוש חופשי בכל הטקסטים
- רק משלמים 💎
- רק לא נקראו 📬
- תצוגה לפי זמן או לפי משתמש

---

## 🔧 תחזוקה

### שינוי תדירות העדכון
ערכי את השורה ב־`.github/workflows/update-data.yml`:
```yaml
- cron: "*/15 * * * *"    # כל 15 דק׳ (ברירת מחדל)
- cron: "*/5 * * * *"     # כל 5 דק׳
- cron: "0 * * * *"       # בראש כל שעה
```
⚠️ GitHub Actions מוגבל ל־2000 דק׳ בחודש בחשבון חינמי. `*/15` = ~2880 הרצות/חודש × ~30 שניות/הרצה = ~24 דק׳. מרווח.

### שינוי טווח הימים
ב־workflow:
```yaml
env:
  DAYS_BACK: "30"   # ← שנו ל־60 / 90 / וכו׳
```

### הוספת מילות מפתח לסיווג
ב־`update_data.py` → `CLASSIFICATION_RULES`. הוסיפי מחרוזות לרשימה המתאימה.

### אם ה־Refresh Token פג
בהגדרות OAuth ב־**Testing mode** — tokens פגים כעבור 7 ימים.
פתרון: הפעילי את ה־app ל־**Production** ב־OAuth consent screen, או הריצי את `get_refresh_token.py` שוב.

---

## 🐛 פתרון בעיות

| בעיה | פתרון |
|------|-------|
| Workflow נכשל: `invalid_grant` | ה־refresh token פג. הריצי `get_refresh_token.py` מחדש ועדכני את ה־secret |
| לא רואה עדכונים באתר | לחצי **Ctrl+Shift+R** (hard reload). Pages מוגש עם cache של 10 דקות |
| `data.json` ריק | בדקי ב־Actions tab את ה־log של ה־workflow |
| סיווג לא נכון | הוסיפי מילות מפתח ל־`CLASSIFICATION_RULES` ב־`update_data.py` |
| Workflow לא רץ אוטומטית | GitHub משהה cron אחרי 60 יום חוסר פעילות ב־repo. גשי ל־Actions → Enable |

---

## 📄 License

פרטי. לשימוש פנימי של Meteor Focus בלבד.
