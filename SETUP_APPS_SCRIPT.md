# הגדרה דרך Google Apps Script (בלי Google Cloud)

גרסה הרבה יותר פשוטה — רצה בתוך חשבון Google שלך, בלי פרויקט נפרד, בלי OAuth consent screen. סך הכל 5 שלבים, כ־10 דקות.

---

## שלב 1 — GitHub Personal Access Token (PAT)

1. פתחי: https://github.com/settings/personal-access-tokens/new
2. **Token name:** `meteor-focus-apps-script`
3. **Expiration:** לבחור "No expiration" (או 90/180/365 יום — תצטרכי לחדש)
4. **Repository access:** "Only select repositories" → בחרי **DianaM242/MeteorFocus**
5. **Repository permissions:**
   - **Contents:** Read and write ✓
   - שאר ההרשאות — השאירי "No access"
6. לחצי **Generate token** → **העתיקי את הטוקן מיד!** (לא תוכלי לראות אותו שוב)
   - הטוקן נראה כמו: `github_pat_11AXXXX...` (ארוך)

---

## שלב 2 — יצירת Apps Script project

1. לכי ל: https://script.google.com
2. **New project** (כפתור עליון שמאל)
3. מחקי את הקוד הדוגמה ב־`Code.gs`
4. פתחי את הקובץ **`apps_script.gs`** מהחבילה, העתיקי את כל התוכן והדביקי ל־`Code.gs`
5. שני את שם הפרויקט ל: `Meteor Focus Dashboard Updater` (לחיצה על "Untitled project" למעלה)
6. **Save** (⌘+S / Ctrl+S)

---

## שלב 3 — שמירת ה־GitHub Token ב־Script Properties

1. ב־Apps Script, בצד שמאל, לחצי על **Project Settings** (אייקון הגלגל שיניים ⚙️)
2. גללי למטה ל־**Script Properties**
3. לחצי **Add script property**:
   - **Property:** `GITHUB_TOKEN`
   - **Value:** (הדביקי את הטוקן שיצרת בשלב 1)
4. לחצי **Save script properties**

---

## שלב 4 — הפעלה ראשונה + אישור הרשאות

1. חזרי לקובץ `Code.gs` (בתפריט הצד)
2. בתפריט הפונקציות למעלה (dropdown), בחרי **`updateDataJson`**
3. לחצי **Run** ▶
4. Google תבקש הרשאות:
   - **Authorization required** → **Review permissions** → בחרי את החשבון `meteorfocus@gmail.com`
   - **Google hasn't verified this app** → לחצי **Advanced** → **Go to Meteor Focus Dashboard Updater (unsafe)**
     (זה OK כי את הבונה — לא מדובר בצד ג')
   - אשרי:
     - ✓ Read your email
     - ✓ Connect to external service (כדי לדחוף ל־GitHub)
5. הפונקציה תרוץ. ב־**Execution log** למטה תראי את השלבים:
   - `Found X threads`
   - `Parsed: X threads`
   - `Pushed to GitHub`

אם הכל ירוק — הצלחה! `data.json` התעדכן ב־repo.

---

## שלב 5 — הפעלת ה־Trigger האוטומטי

1. עדיין ב־Apps Script, בתפריט הפונקציות למעלה, בחרי **`setupTrigger`**
2. לחצי **Run** ▶
3. בלוג תראי: `✓ Trigger created — updateDataJson יופעל כל 15 דקות`
4. לבדיקה: בצד שמאל → **Triggers** (אייקון שעון) — תראי trigger של `updateDataJson` שרץ כל 15 דקות

---

## ✅ זה הכל!

מעכשיו:
- כל 15 דקות `data.json` יתעדכן אוטומטית
- `https://dianam242.github.io/MeteorFocus/` יציג נתונים עדכניים
- **לא צריך GitHub Actions** — אפשר למחוק את `.github/workflows/update-data.yml` מה־repo
- **לא צריך Google Cloud** — הכל רץ על החשבון האישי שלך

---

## 📊 מעקב ודיבוג

### ראות הרצות קודמות
Apps Script → **Executions** (אייקון רשימה בתפריט הצד). תראי כל הרצה, משך, ולוג מלא.

### הרצה ידנית
לחצי **Run** על `updateDataJson` בכל עת — לא מחליף את ה־trigger, פשוט מריץ נוסף.

### שינוי תדירות
ב־`setupTrigger` החליפי את `everyMinutes(15)` ל:
- `everyMinutes(5)` — כל 5 דק׳ (מינימום ב־Apps Script הוא 1 דק׳)
- `everyHours(1)` — כל שעה
- `everyDays(1).atHour(8)` — כל יום בשמונה בבוקר

לאחר השינוי, הריצי שוב `setupTrigger` (ימחק את הישן ויצור חדש).

### הוספת מילות מפתח לסיווג
בקובץ `apps_script.gs` → `classifyIssue` → ערכי את `rules`. הוסיפי מחרוזות לקטגוריה הרלוונטית.

### הפסקת עדכונים אוטומטיים
הריצי את `removeTrigger` (פונקציה שיש בקובץ).

---

## 🔒 אבטחה

- ה־GitHub token שמור רק ב־Script Properties של Apps Script — לא גלוי בקוד, לא נכנס ל־git
- רק לך יש גישה ל־Apps Script project שלך (חשבון Google פרטי)
- הטוקן מוגבל ל־repo הספציפי שלך בלבד (הגדרת "Only select repositories")
- כשהטוקן פג (אם בחרת Expiration): Google Apps Script ייתן שגיאה ב־Executions. פשוט יצרי טוקן חדש בשלב 1 והחליפי את הערך ב־Script Properties

---

## 🆚 אפשרות חלופית: GitHub Actions + Google Cloud

ראי `README.md` — עובד באותה הצורה, רק ההתקנה מורכבת יותר (Google Cloud project + OAuth credentials). לא מומלץ אלא אם יש סיבה ספציפית.
