/**
 * Meteor Focus Dashboard Updater — Google Apps Script
 *
 * Runs inside the meteorfocus@gmail.com account, fetches "Issue Reported"
 * feedback emails, parses the JSON body of each, classifies by keyword
 * heuristics, and pushes the resulting data.json to GitHub via the
 * Contents API.
 *
 * Setup: see SETUP_APPS_SCRIPT.md
 */

const CONFIG = {
  GITHUB_REPO: 'DianaM242/MeteorFocus',
  GITHUB_BRANCH: 'main',
  DATA_FILE: 'data.json',
  GMAIL_QUERY: 'subject:"Issue Reported" newer_than:30d',
  MAX_THREADS: 2000,
  TRIGGER_MINUTES: 15,
};

// Classification: first match wins. Substring match, case-insensitive.
// Edit these lists to tune the classifier.
const CLASSIFICATION_RULES = [
  ['wrong', [
    'תשובה שגוי', 'שגויה', 'לא נכון', 'לא נכונה',
    'התשובה הנכונה היא', 'התשובה צריכה', 'טעות בתשובה',
    'סימן שגוי', 'סימנה שגוי', 'מסומן לא נכון', 'סומן לא נכון',
  ]],
  ['multiple', [
    'יותר מתשובה', 'שתי תשובות', 'שלוש תשובות',
    'שתיהן נכונות', 'שתיהן תקינות', 'יכולה להיות גם',
    'שלוש נכונות', 'מספר תשובות', 'אין תשובה אחת',
  ]],
  ['explanation', [
    'הסבר לא ברור', 'הסבר לא מובן', 'ההסבר לא', 'לא מבינה את ההסבר',
    'אין הסבר', 'חסר הסבר', 'ההסבר חסר', 'הסבר חסר',
    'הסבר לא תואם', 'ההסבר סותר',
  ]],
  ['phrasing', [
    'לא מובן', 'לא ברור', 'לא הבנתי', 'קשה להבין',
    'ניסוח', 'לא ברורה', 'הניסוח', 'השאלה לא ברורה',
    'לא מובנת', 'מבלבל', 'לא מבינה את השאלה',
  ]],
];

// =====================================================================
// Public entry points — call these from the Apps Script UI
// =====================================================================

/**
 * Main function. Runs on the cron trigger and on manual invocation.
 * Fetches emails, parses, classifies, and pushes data.json to GitHub.
 */
function updateDataJson() {
  const startMs = Date.now();
  const token = getGitHubToken();

  const threads = GmailApp.search(CONFIG.GMAIL_QUERY, 0, CONFIG.MAX_THREADS);
  console.log(`Found ${threads.length} threads`);

  const parsed = parseThreads(threads);
  console.log(`Parsed: ${parsed.length} threads`);

  const unreadCount = parsed.filter((t) => t.isUnread).length;

  const output = {
    fetched_at: isoNow(),
    total_count: parsed.length,
    unread_count: unreadCount,
    threads: parsed,
  };

  const newContent = JSON.stringify(output, null, 2);
  const result = pushToGitHub(token, newContent);

  const elapsed = ((Date.now() - startMs) / 1000).toFixed(1);
  console.log(`${result} (${elapsed}s)`);
}

/**
 * Creates a time-based trigger to run updateDataJson every N minutes.
 * Removes any existing trigger for this function first.
 */
function setupTrigger() {
  removeTrigger();
  ScriptApp.newTrigger('updateDataJson')
    .timeBased()
    .everyMinutes(CONFIG.TRIGGER_MINUTES)
    .create();
  console.log(
    `✓ Trigger created — updateDataJson יופעל כל ${CONFIG.TRIGGER_MINUTES} דקות`
  );
}

/**
 * Removes all triggers for updateDataJson.
 */
function removeTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  let removed = 0;
  for (const t of triggers) {
    if (t.getHandlerFunction() === 'updateDataJson') {
      ScriptApp.deleteTrigger(t);
      removed++;
    }
  }
  console.log(`Removed ${removed} existing trigger(s)`);
}

// =====================================================================
// Internals
// =====================================================================

function getGitHubToken() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    throw new Error(
      'GITHUB_TOKEN not set. Open Project Settings (⚙️) → Script Properties, ' +
        'add property GITHUB_TOKEN with your GitHub PAT as the value.'
    );
  }
  return token;
}

function parseThreads(threads) {
  const out = [];
  for (const thread of threads) {
    const messages = thread.getMessages();
    if (messages.length === 0) continue;
    // Use the first (original) message in the thread.
    const msg = messages[0];

    const body = extractEmailBody(msg);
    const parsed = parseJsonFromText(body);
    if (!parsed || typeof parsed !== 'object') continue;

    const issueText = (parsed.issue_text || '').trim();
    const hasExtra = parsed.extra_details != null;

    out.push({
      id: thread.getId(),
      date: msg.getDate().toISOString().replace(/\.\d{3}Z$/, 'Z'),
      isUnread: msg.isUnread(),
      classification: hasExtra ? classifyIssue(issueText) : null,
      body: parsed,
    });
  }
  // Newest first.
  out.sort((a, b) => b.date.localeCompare(a.date));
  return out;
}

function extractEmailBody(message) {
  const plain = message.getPlainBody();
  if (plain && plain.trim()) return plain;
  // Fallback: strip HTML tags from rich body.
  const html = message.getBody() || '';
  return html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').trim();
}

function parseJsonFromText(text) {
  if (!text) return null;
  const trimmed = text.trim();
  try {
    return JSON.parse(trimmed);
  } catch (_) {
    // fallthrough to balanced-brace scan
  }
  // Find the first balanced {...} block and try to parse that.
  const start = trimmed.indexOf('{');
  if (start === -1) return null;
  let depth = 0;
  let inStr = false;
  let escape = false;
  for (let i = start; i < trimmed.length; i++) {
    const ch = trimmed[i];
    if (escape) {
      escape = false;
      continue;
    }
    if (ch === '\\' && inStr) {
      escape = true;
      continue;
    }
    if (ch === '"') {
      inStr = !inStr;
      continue;
    }
    if (inStr) continue;
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) {
        try {
          return JSON.parse(trimmed.slice(start, i + 1));
        } catch (_) {
          return null;
        }
      }
    }
  }
  return null;
}

function classifyIssue(text) {
  if (!text) return 'other';
  const lower = text.toLowerCase();
  for (const [label, keywords] of CLASSIFICATION_RULES) {
    for (const kw of keywords) {
      if (lower.indexOf(kw.toLowerCase()) !== -1) return label;
    }
  }
  return 'other';
}

function pushToGitHub(token, content) {
  const baseUrl =
    `https://api.github.com/repos/${CONFIG.GITHUB_REPO}/contents/${CONFIG.DATA_FILE}`;
  const getUrl = `${baseUrl}?ref=${encodeURIComponent(CONFIG.GITHUB_BRANCH)}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };

  // Get current file SHA (and compare content to avoid empty commits).
  let currentSha = null;
  const getResp = UrlFetchApp.fetch(getUrl, {
    method: 'get',
    headers: headers,
    muteHttpExceptions: true,
  });
  const getCode = getResp.getResponseCode();
  if (getCode === 200) {
    const json = JSON.parse(getResp.getContentText());
    currentSha = json.sha;
    const existingB64 = (json.content || '').replace(/\n/g, '');
    const existingBytes = Utilities.base64Decode(existingB64);
    const existing = Utilities.newBlob(existingBytes).getDataAsString('UTF-8');
    if (existing === content) {
      return 'No changes — skipped commit';
    }
  } else if (getCode !== 404) {
    throw new Error(
      `GitHub GET failed: HTTP ${getCode} — ${getResp.getContentText()}`
    );
  }

  const payload = {
    message: `data: auto-update ${isoNow()}`,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: CONFIG.GITHUB_BRANCH,
  };
  if (currentSha) payload.sha = currentSha;

  const putResp = UrlFetchApp.fetch(baseUrl, {
    method: 'put',
    headers: headers,
    payload: JSON.stringify(payload),
    contentType: 'application/json',
    muteHttpExceptions: true,
  });
  const code = putResp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(
      `GitHub PUT failed: HTTP ${code} — ${putResp.getContentText()}`
    );
  }
  return `Pushed to GitHub (HTTP ${code})`;
}

function isoNow() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}
