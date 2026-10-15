/* Hesburgh Lecture matching engine, in JavaScript for the browser page.
 *
 * A line-by-line port of the Python engine in engine/ (text.py, columns.py,
 * loader.py, scoring.py, modes.py, solver.py, plans.py). Same rules, same
 * scores, same plans: `node web/parity_check.js` runs both on the same files
 * and fails on any difference. If you change the Python engine, change this
 * file the same way.
 *
 * One addition the Python engine doesn't have: `pins`, pairs staff fixed by
 * hand in the page. They are booked first and the plan is solved around them.
 */
(function (root) {
  "use strict";

  // ================================================================ difflib
  function matchingBlocks(a, b) {
    const b2j = new Map();
    for (let i = 0; i < b.length; i++) {
      if (!b2j.has(b[i])) b2j.set(b[i], []);
      b2j.get(b[i]).push(i);
    }
    if (b.length >= 200) {
      const ntest = Math.floor(b.length / 100) + 1;
      for (const [ch, idx] of [...b2j]) if (idx.length > ntest) b2j.delete(ch);
    }
    function longest(alo, ahi, blo, bhi) {
      let besti = alo, bestj = blo, bestsize = 0, j2len = new Map();
      for (let i = alo; i < ahi; i++) {
        const next = new Map();
        for (const j of b2j.get(a[i]) || []) {
          if (j < blo) continue;
          if (j >= bhi) break;
          const k = (j2len.get(j - 1) || 0) + 1;
          next.set(j, k);
          if (k > bestsize) { besti = i - k + 1; bestj = j - k + 1; bestsize = k; }
        }
        j2len = next;
      }
      while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) { besti--; bestj--; bestsize++; }
      while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) bestsize++;
      return [besti, bestj, bestsize];
    }
    const queue = [[0, a.length, 0, b.length]], blocks = [];
    while (queue.length) {
      const [alo, ahi, blo, bhi] = queue.pop();
      const [i, j, k] = longest(alo, ahi, blo, bhi);
      if (k) {
        blocks.push(k);
        if (alo < i && blo < j) queue.push([alo, i, blo, j]);
        if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
      }
    }
    return blocks.reduce((s, k) => s + k, 0);
  }
  function ratio(a, b) {
    const total = a.length + b.length;
    return total ? 2.0 * matchingBlocks(a, b) / total : 1.0;
  }
  function closeMatches(word, possibilities, n, cutoff) {
    const hits = [];
    for (const x of possibilities) { const r = ratio(x, word); if (r >= cutoff) hits.push([r, x]); }
    hits.sort((p, q) => (q[0] - p[0]) || (q[1] < p[1] ? -1 : q[1] > p[1] ? 1 : 0));
    return hits.slice(0, n).map((h) => h[1]);
  }

  // ================================================================ text.py
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];
  const MONTH_NUMBER = Object.fromEntries(MONTHS.map((m, i) => [m.toLowerCase(), i]));
  const TITLE_THEN_MONTHS = new RegExp(`^([\\s\\S]*?)\\s*-\\s*((?:${MONTHS.join("|")})[\\s\\S]*)$`, "i");
  const TYPOGRAPHY = { "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " " };

  const typo = (s) => String(s ?? "").replace(/[‘’“”–— ]/g, (c) => TYPOGRAPHY[c]);
  const clean = (s) => typo(s).replace(/\s+/g, " ").trim().toLowerCase();
  const tidy = (s) => String(s ?? "").replace(/\s+/g, " ").trim();
  const strip = (s) => String(s ?? "").trim();

  function nameKey(name) {
    let s = clean(name);
    s = s.replace(/\b(fr|father|rev|dr|sr|br)\.?\s+/g, "");
    s = s.replace(/,?\s*c\.?\s*s\.?\s*c\.?$/, "");
    s = s.replace(/[.']/g, "");
    s = s.replace(/[-,]/g, " ");
    return s.replace(/\s+/g, " ").trim();
  }
  function nameSimilarity(a, b) {
    const ka = nameKey(a), kb = nameKey(b);
    if (!ka || !kb) return 0.0;
    return ka === kb ? 1.0 : ratio(ka, kb);
  }
  const samePerson = (a, b, threshold = 0.85) => nameSimilarity(a, b) >= threshold;

  function parseMonths(raw) {
    const text = clean(raw);
    if (!text) return [];
    if (text.includes("all of the above") || text.replace(/ /g, "") === "january-december") return MONTHS.slice();
    const found = new Set();
    for (const part of text.split(/[,;/]/)) {
      const ends = part.split("-").map((e) => e.trim());
      const numbers = ends.filter((e) => e in MONTH_NUMBER).map((e) => MONTH_NUMBER[e]);
      if (ends.length === 2 && numbers.length === 2) {
        const [start, stop] = numbers;
        if (start <= stop) for (let i = start; i <= stop; i++) found.add(i);
        else { for (let i = start; i < 12; i++) found.add(i); for (let i = 0; i <= stop; i++) found.add(i); }
      } else numbers.forEach((n) => found.add(n));
    }
    return [...found].sort((x, y) => x - y).map((i) => MONTHS[i]);
  }

  function splitRequest(cell) {
    if (!cell || !cell.includes("|")) return [null, null];
    const at = cell.indexOf("|");
    const theme = cell.slice(0, at).trim(), rest = cell.slice(at + 1).trim();
    const m = TITLE_THEN_MONTHS.exec(rest);
    const title = m ? m[1].trim() : rest;
    return [theme || null, title || null];
  }
  const ordinal = (n) => (n === null || n === undefined ? "?" : ({ 1: "1st", 2: "2nd", 3: "3rd" }[n] || `${n}th`));

  // ================================================================ columns.py
  const FILES = { club: "club_info.csv", prof: "prof_info.csv", lecture: "lecture_info.csv" };
  const F = (file, key, header, meaning, required = false, also = [], extra = {}) =>
    Object.assign({ file, key, header, meaning, required, also, pattern: null, many: false, newestFirst: false }, extra);
  const SCHEMA = [
    F("club", "id", "ID Number", "Unique club ID", true, ["Club ID", "ID"]),
    F("club", "name", "Club Check", "Club name", true, ["Club", "Club Name"]),
    F("club", "availability", "Availability", "Months the club can host, comma-separated", true, ["Months", "Available Months"]),
    F("club", "themes", "Theme 1 … Theme 5", "The club's ranked requests, 'Theme | Lecture- months'", true, [], { pattern: /^theme(\d+)$/, many: true }),
    F("club", "size", "Size", "Club size code AA … F", false, ["Club Size"]),
    F("club", "hls_score", "HLS Score", "Engagement score", false, ["Engagement Score", "Engagement"]),
    F("club", "region", "Region", "Region name"),
    F("club", "format", "Format", "Talk formats the club wants, comma-separated", false, ["Formats", "Format(s)"]),
    F("club", "invited", "Invited 2026", "'Invited' marks a club in this year's program", false, [], { pattern: /^invited(\d{4})?$/, newestFirst: true }),
    F("club", "past_speakers", "2025 Speaker … 2022 Speaker", "Speakers from earlier years", false, [], { pattern: /^(\d{4})speaker$/, many: true, newestFirst: true }),
    F("club", "staff_pick", "2026 Assignment", "Staff's own pick, used only for comparison", false, [], { pattern: /^(\d{4})assignment$/, newestFirst: true }),
    F("prof", "name", "Recipient Full Name", "Professor's full name", true, ["Full Name", "Name", "Professor", "Faculty"]),
    F("prof", "availability", "Availability", "Months available, or 'All of the above'", true, ["Months", "Available Months"]),
    F("prof", "max_events", "# of Events", "Most events this professor will do (blank = 1)", false, ["Number of Events", "Max Events", "Events"]),
    F("prof", "title", "Title", "Job title, for the title boost", false, ["Job Title", "Position"]),
    F("prof", "formats", "Format(s)", "Talk formats offered, comma-separated", false, ["Formats", "Format"]),
    F("prof", "participate", "Participate in the Hesburgh Lecture program in 2026?", "Answers starting 'No' are skipped", false, [], { pattern: /^participate/ }),
    F("prof", "travel", "Particular clubs or areas of the country you are interested in traveling?", "Free-text travel wishes, for the Balanced plan", false, [], { pattern: /^particularclubs|areasofthecountry|travelpref/ }),
    F("lecture", "faculty", "Faculty", "Professor who gives the lecture", true, ["Professor", "Speaker", "Name"]),
    F("lecture", "theme", "Theme", "Theme the lecture belongs to", true, ["Category"]),
    F("lecture", "topic", "Topic", "Lecture title, spelled as clubs request it", true, ["Title", "Lecture", "Lecture Title"]),
    F("lecture", "availability", "Availability", "Months the lecture is offered (blank = all year)", false, ["Months"]),
  ];
  const fieldsFor = (file) => SCHEMA.filter((f) => f.file === file);
  const squash = (h) => String(h || "").toLowerCase().replace(/[^a-z0-9]/g, "");

  class Columns {
    constructor(file, headers, found) { Object.assign(this, { file, headers, found }); }
    get(row, key) { const h = this.found[key]; return typeof h === "string" ? (row[h] ?? "") : ""; }
    getAll(row, key) { return (this.found[key] || []).map((h) => row[h] ?? ""); }
    has(key) { const v = this.found[key]; return Array.isArray(v) ? v.length > 0 : !!v; }
  }

  function resolve(file, headers, overrides, issues) {
    overrides = overrides || {};
    const squashed = {};
    for (const h of headers) squashed[squash(h)] = h;
    const taken = new Set(), found = {}, fname = FILES[file];
    for (const field of fieldsFor(file)) {
      const want = overrides[field.key];
      if (want === undefined || want === null || want === "" || (Array.isArray(want) && !want.length)) continue;
      const names = Array.isArray(want) ? want : [want];
      const missing = names.filter((n) => !headers.includes(n));
      if (missing.length) {
        issues.error("missing_column", fname, `Column '${missing[0]}' chosen for '${field.header}' is not in ${fname}.`);
        continue;
      }
      found[field.key] = field.many ? names : names[0];
      names.forEach((n) => taken.add(n));
    }
    for (const field of fieldsFor(file)) {
      if (field.key in found) continue;
      const match = automatic(field, headers, squashed, taken);
      const any = Array.isArray(match) ? match.length : match;
      if (any) {
        found[field.key] = match;
        (Array.isArray(match) ? match : [match]).forEach((h) => taken.add(h));
        const first = Array.isArray(match) ? match[0] : match;
        const usual = new Set([squash(field.header), ...field.also.map(squash)]);
        if (!field.many && !field.pattern && !usual.has(squash(first))) {
          issues.note("column_matched", fname, `Using column '${first}' for '${field.header}'.`);
        }
      } else if (field.required) {
        issues.error("missing_column", fname, `Required column '${field.header}' (${field.meaning.toLowerCase()}) was not found. `
          + "Rename it back or choose the column in Settings.");
      } else {
        found[field.key] = field.many ? [] : null;
        issues.note("missing_column", fname, `Optional column '${field.header}' not found (${field.meaning.toLowerCase()}); `
          + "matching works without it.");
      }
    }
    return new Columns(file, headers, found);
  }

  function automatic(field, headers, squashed, taken) {
    const free = (h) => !taken.has(h);
    if (!field.many) {
      for (const name of [field.header, ...field.also]) {
        const h = squashed[squash(name)];
        if (h && free(h)) return h;
      }
    }
    if (field.pattern) {
      const hits = [];
      for (const h of headers) {
        const m = field.pattern.exec(squash(h));
        if (m && free(h)) hits.push([m[1] ? parseInt(m[1], 10) : 0, h]);
      }
      if (hits.length) {
        hits.sort((x, y) => (field.newestFirst ? y[0] - x[0] : x[0] - y[0]));
        return field.many ? hits.map((x) => x[1]) : hits[0][1];
      }
    }
    if (!field.many) {
      const candidates = headers.filter(free);
      const close = closeMatches(squash(field.header), candidates.map(squash), 1, 0.88);
      if (close.length) return candidates.find((h) => squash(h) === close[0]);
    }
    return field.many ? [] : null;
  }

  const defaultsFor = (f) => (f.key === "themes" ? [1, 2, 3, 4, 5].map((i) => `Theme ${i}`)
    : f.key === "past_speakers" ? [2025, 2024, 2023, 2022].map((y) => `${y} Speaker`) : [f.header]);
  const COLUMN_SPEC = Object.fromEntries(Object.keys(FILES).map((g) => [g, fieldsFor(g).map((f) => ({
    field: f.key, label: f.many ? f.header.replace(" … ", " to ") : f.header, required: f.required, multi: f.many,
    default: defaultsFor(f), meaning: f.meaning,
  }))]));

  // ================================================================ loader.py
  const SIZE_CODES = ["AA", "A", "B", "C", "D", "E", "F"];
  const SEVERITY_ORDER = { error: 0, warning: 1, info: 2 };

  class Issues extends Array {
    add(severity, kind, subject, message) {
      if (!this.some((i) => i.severity === severity && i.kind === kind && i.subject === subject && i.message === message)) {
        this.push({ severity, kind, subject, message });
      }
    }
    error(k, s, m) { this.add("error", k, s, m); }
    warn(k, s, m) { this.add("warning", k, s, m); }
    note(k, s, m) { this.add("info", k, s, m); }
  }

  // Python's csv module: a quote only opens quoting at the start of a field; blank lines are skipped.
  function parseCSV(text) {
    const rows = [];
    let row = [], field = "", inQ = false, atStart = true, i = 0;
    const endRow = () => { row.push(field); if (!(row.length === 1 && row[0] === "" && !row.quoted)) rows.push(row); row = []; field = ""; atStart = true; };
    while (i < text.length) {
      const c = text[i];
      if (inQ) {
        if (c === '"') { if (text[i + 1] === '"') { field += '"'; i += 2; continue; } inQ = false; i++; continue; }
        field += c; i++; continue;
      }
      if (c === '"' && atStart) { inQ = true; atStart = false; row.quoted = true; i++; continue; }
      if (c === ",") { row.push(field); field = ""; atStart = true; i++; continue; }
      if (c === "\r" || c === "\n") { if (c === "\r" && text[i + 1] === "\n") i++; i++; endRow(); continue; }
      field += c; atStart = false; i++;
    }
    if (field !== "" || row.length || row.quoted) endRow();
    return rows;
  }

  function readTable(text) {
    text = String(text || "").replace(/^﻿/, "");
    const all = parseCSV(text);
    if (!all.length) return [[], []];
    const raw = all[0];
    const headers = raw.map((h) => (h || "").trim());
    const rows = all.slice(1).map((r) => {
      const d = {};
      raw.forEach((h, i) => { d[(h || "").trim()] = r[i] ?? ""; });
      return d;
    });
    return [headers, rows];
  }

  function firstNumber(text) { const m = /\d+/.exec(text || ""); return m ? parseInt(m[0], 10) : null; }
  const splitList = (text) => (text || "").split(",").map((x) => x.trim()).filter(Boolean);

  function seniorTitle(raw) {
    let text = clean(raw);
    const held = [];
    for (const t of Object.keys(TITLE_BOOST).sort((a, b) => b.length - a.length)) {
      if (text.includes(t)) { held.push(t); text = text.split(t).join(" "); }
    }
    let best = "professor";
    if (held.length) { best = held[0]; for (const t of held) if (TITLE_BOOST[t] > TITLE_BOOST[best]) best = t; }
    return best;
  }

  function loadLectures(rows, col, issues) {
    const lectures = [], seen = new Set();
    for (const row of rows) {
      const [faculty, theme, topic] = ["faculty", "theme", "topic"].map((k) => col.get(row, k).trim());
      if (!(faculty && theme && topic)) {
        if (Object.values(row).some((v) => v.trim())) {
          issues.warn("dropped_row", faculty || topic || "lecture_info.csv", "Lecture row skipped because Faculty, Theme or Topic is blank.");
        }
        continue;
      }
      const key = [nameKey(faculty), clean(theme), clean(topic)].join("\u0000");
      if (seen.has(key)) continue;
      seen.add(key);
      const months = parseMonths(col.get(row, "availability"));
      lectures.push({ theme, title: topic, months: months.length ? months : MONTHS.slice(), listed_under: faculty });
    }
    return lectures;
  }

  function attachLectures(profs, lectures, issues) {
    for (const lecture of lectures) {
      let owner = null, best = -Infinity;
      for (const p of profs) { const s = nameSimilarity(p.name, lecture.listed_under); if (s > best) { best = s; owner = p; } }
      const similarity = owner ? best : 0.0;
      if (similarity < 0.85) {
        issues.warn("lecture_not_found", lecture.listed_under, `Lecture '${lecture.title}' belongs to '${lecture.listed_under}', who is not in prof_info.csv.`);
        continue;
      }
      if (similarity < 1.0) issues.warn("name_mismatch", owner.name, `Catalog lists this professor as '${lecture.listed_under}'; matched automatically.`);
      owner.lectures.push(lecture);
    }
    for (const prof of profs) {
      if (!prof.lectures.length) {
        issues.error("prof_no_lectures", prof.name, "No lectures found in lecture_info.csv for this professor, so they can never be matched.");
      }
    }
  }

  const isSurveyLabelRow = (name, header) => name.toLowerCase() === "recipient full name" || name.toLowerCase() === header.toLowerCase() || name.startsWith("{");

  function makeProf(o) {
    const p = Object.assign({ lectures: [] }, o);
    Object.defineProperty(p, "themes", { get() { return new Set(this.lectures.map((l) => clean(l.theme))); } });
    p.offers = function (title) { const k = clean(title); return k ? this.lectures.find((l) => clean(l.title) === k) || null : null; };
    return p;
  }

  function loadProfs(rows, col, issues) {
    const profs = [];
    rows.forEach((row, idx) => {
      const number = idx + 2, name = tidy(col.get(row, "name"));
      if (number === 2 && isSurveyLabelRow(name, col.found.name)) { issues.note("dropped_row", "prof_info.csv row 2", "Dropped a survey label row (not a professor)."); return; }
      if (!name) {
        if (Object.values(row).some((v) => v.trim())) issues.warn("dropped_row", `prof_info.csv row ${number}`, "Professor row skipped because the name is blank.");
        return;
      }
      if (col.get(row, "participate").trim().toLowerCase().startsWith("no")) { issues.note("declined", name, "Declined to participate in 2026; not matched."); return; }
      const months = parseMonths(col.get(row, "availability"));
      if (!months.length) issues.warn("missing_availability", name, "No availability months, so this professor cannot be matched.");
      const maxEvents = firstNumber(col.get(row, "max_events"));
      if (maxEvents === null && col.has("max_events")) issues.warn("blank_score", name, "# of Events is blank; assuming 1.");
      const titleRaw = col.get(row, "title").trim();
      if (titleRaw && !Object.keys(TITLE_BOOST).some((t) => clean(titleRaw).includes(t))) {
        issues.note("unknown_title", name, `Title '${titleRaw.split(/\r\n|\r|\n/)[0]}' not recognised; treated as professor.`);
      }
      profs.push(makeProf({
        name, title: seniorTitle(titleRaw), title_raw: titleRaw, months, max_events: Math.max(1, maxEvents || 1),
        formats: splitList(col.get(row, "formats")), travel_wishes: col.get(row, "travel"),
      }));
    });
    return profs;
  }

  function isInProgram(row, col) {
    const themes = col.getAll(row, "themes");
    return col.get(row, "invited").trim().toLowerCase() === "invited" || !!(themes.length && themes[0].trim());
  }

  function readRequests(row, col, catalog, club, issues) {
    const requests = [], seen = new Set();
    col.getAll(row, "themes").forEach((cell, i) => {
      const [theme, title] = splitRequest(cell);
      const key = clean(theme) + "\u0000" + clean(title);
      if (!(theme || title) || seen.has(key)) return;
      seen.add(key);
      requests.push({ rank: i + 1, theme, title });
      if (title && !catalog.has(clean(title))) issues.warn("lecture_not_found", club, `Requested lecture '${title}' is not in lecture_info.csv.`);
    });
    return requests;
  }

  function makeClub(o) {
    const seen = new Map();
    for (const r of o.requests) if (r.theme && !seen.has(clean(r.theme))) seen.set(clean(r.theme), r.theme);
    return Object.assign(o, { requested_themes: [...seen.values()], submitted_form: !!(o.requests.length || o.months.length) });
  }

  function loadClubs(rows, col, lectures, issues) {
    const catalog = new Set(lectures.map((l) => clean(l.title))), clubs = [];
    for (const row of rows.filter((r) => isInProgram(r, col))) {
      const id = col.get(row, "id").trim(), name = col.get(row, "name").trim();
      if (!(id && name)) { issues.warn("dropped_row", name || id || "club_info.csv", "Club row skipped because the ID or club name is blank."); continue; }
      let size = col.get(row, "size").trim().toUpperCase();
      if (!SIZE_CODES.includes(size) && col.has("size")) issues.warn("blank_size", name, size ? `Size '${size}' is not AA-F; using a middle value.` : "Size is blank; using a middle value.");
      if (!SIZE_CODES.includes(size)) size = "";
      const engagement = firstNumber(col.get(row, "hls_score").split(",").join(""));
      if (engagement === null && col.has("hls_score")) issues.warn("blank_score", name, "HLS Score is blank; using a middle value.");
      const months = parseMonths(col.get(row, "availability"));
      const requests = readRequests(row, col, catalog, name, issues);
      if (!(requests.length || months.length)) issues.warn("missing_availability", name, "No request form: Availability and Theme 1-5 are blank.");
      else if (!months.length) issues.warn("missing_availability", name, "Availability is blank.");
      else if (!requests.length) issues.warn("missing_availability", name, "No themes or lectures requested.");
      clubs.push(makeClub({
        id, name, size, region: col.get(row, "region").trim(), engagement, months, formats: splitList(col.get(row, "format")),
        requests, past_speakers: col.getAll(row, "past_speakers").map((p) => p.trim()).filter(Boolean),
        staff_pick: tidy(col.get(row, "staff_pick")), comments: tidy(row.Comments || ""),
      }));
    }
    return clubs;
  }

  const usable = (col, rows) => (fieldsFor(col.file).filter((f) => f.required).every((f) => col.has(f.key)) ? rows : []);

  function readAll(texts, columns, issues) {
    const tables = {};
    for (const group of ["club", "prof", "lecture"]) {
      const [headers, rows] = readTable(texts[group]);
      if (!rows.length) issues.error("empty_file", FILES[group], `${FILES[group]} has no data rows.`);
      tables[group] = [resolve(group, headers, (columns || {})[group], issues), rows];
    }
    return tables;
  }

  /** texts = {club, prof, lecture} as CSV text. columns = optional overrides, as in COLUMN_SPEC. */
  function loadInputs(texts, columns) {
    const issues = new Issues();
    const t = readAll(texts, columns, issues);
    const [clubCol, clubRows] = t.club, [profCol, profRows] = t.prof, [lecCol, lecRows] = t.lecture;
    const lectures = loadLectures(usable(lecCol, lecRows), lecCol, issues);
    const profs = loadProfs(usable(profCol, profRows), profCol, issues);
    attachLectures(profs, lectures, issues);
    const clubs = loadClubs(usable(clubCol, clubRows), clubCol, lectures, issues);
    return {
      clubs, profs, lectures, issues: [...issues],
      columns: Object.fromEntries(Object.entries(t).map(([g, [c]]) => [g, Object.assign({}, c.found)])),
      headers: Object.fromEntries(Object.entries(t).map(([g, [c]]) => [g, c.headers])),
    };
  }

  function dataIssues(data) {
    const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
    return data.issues.slice().sort((a, b) => ((SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))
      || cmp(a.kind, b.kind) || cmp(a.subject, b.subject));
  }

  // ================================================================ scoring.py
  const TITLE_BOOST = {
    "provost": 1.30, "vice president": 1.25, "vice provost": 1.20, "dean": 1.20,
    "associate provost": 1.15, "director": 1.15, "associate dean": 1.10, "program director": 1.10,
    "assistant dean": 1.05, "associate professor": 1.05, "professor of the practice": 1.02,
    "teaching professor": 1.00, "assistant professor": 1.00, "professor": 1.00,
  };
  const SIZE_VALUE = { AA: 1.00, A: 0.90, B: 0.80, C: 0.70, D: 0.60, E: 0.50, F: 0.40 };
  const ENGAGEMENT_BANDS = [[600, 1.00], [450, 0.90], [350, 0.80], [250, 0.70], [150, 0.60], [0, 0.55]];
  const UNKNOWN = 0.5, TITLE_BOOST_FROM_PRIORITY = 0.7, MIN_POINTS = 0.01;

  const DEFAULT_WEIGHTS = {
    lecture_match: 1.0, theme_match: 1.0, month_overlap: 1.0, format_match: 1.0, choice_rank: 1.0,
    size: 1.0, engagement: 1.0, title: 1.0, repeat_penalty: 1.0, spread: 1.0, travel_bonus: 1.0, staff_pick: 0.0,
  };
  const OLD_NAMES = { size_weight: "size", eng_weight: "engagement", title_weight: "title" };
  function coerceWeights(value) {
    const w = Object.assign({}, DEFAULT_WEIGHTS);
    for (let [k, v] of Object.entries(value || {})) {
      k = OLD_NAMES[k] || k;
      if (k in DEFAULT_WEIGHTS && v !== null && v !== undefined) w[k] = Math.max(0.0, Number(v));
    }
    return w;
  }

  const ALL_PLANS = "All plans", FAIRNESS_PLANS = "Recommended and Balanced";
  const WEIGHT_INFO = {
    lecture_match: { label: "Requested lecture", help: "Points when the professor gives a lecture the club asked for by name (10 each at 1x). Raise it to favour exact talks over loose theme matches.", group: "What the club asked for", applies_to: ALL_PLANS },
    theme_match: { label: "Shared theme", help: "Points when the professor covers a theme the club asked for, even without the exact talk (5 each at 1x).", group: "What the club asked for", applies_to: ALL_PLANS },
    choice_rank: { label: "Respect club's ranking", help: "How much a club's 1st choice beats its 5th. At 1x each step down the list is worth 10% less; 0 treats all five choices the same.", group: "What the club asked for", applies_to: ALL_PLANS },
    month_overlap: { label: "Calendar flexibility", help: "Points for each month both sides are free (2 each at 1x). More shared months make scheduling easier. One shared month is always required.", group: "Logistics", applies_to: ALL_PLANS },
    format_match: { label: "Talk format", help: "Points when the professor offers the format the club wants, such as a fireside chat (1 each at 1x).", group: "Logistics", applies_to: ALL_PLANS },
    size: { label: "Club size", help: "How much bigger clubs (AA, A) are favoured over smaller ones (E, F). 0 treats every size alike.", group: "Which clubs come first", applies_to: ALL_PLANS + " except Most clubs served" },
    engagement: { label: "Club engagement", help: "How much clubs with a high HLS Score are favoured. 0 ignores engagement.", group: "Which clubs come first", applies_to: ALL_PLANS + " except Most clubs served" },
    title: { label: "Senior speakers for top clubs", help: "Boost for deans, provosts and directors when matched with high-priority clubs (up to 1.3x at 1x). 0 treats every title alike.", group: "Which clubs come first", applies_to: ALL_PLANS },
    repeat_penalty: { label: "Avoid repeat speakers", help: "Penalty for sending a professor who spoke at this club in the last four years.", group: "Fairness", applies_to: FAIRNESS_PLANS },
    spread: { label: "Spread events across faculty", help: "Makes a professor's 2nd and 3rd events cost more, so more faculty take part. 0 lets the best professors take every slot they offered.", group: "Fairness", applies_to: FAIRNESS_PLANS },
    travel_bonus: { label: "Honour travel wishes", help: "Bonus when a professor asked to visit the club's city or region.", group: "Fairness", applies_to: FAIRNESS_PLANS },
    staff_pick: { label: "Agree with staff's picks", help: "Bonus when the professor is the one already in the club's '2026 Assignment' column (10 points at 1x). Off by default so the plans stay an independent second opinion.", group: "Fairness", applies_to: ALL_PLANS },
  };
  for (const [k, info] of Object.entries(WEIGHT_INFO)) Object.assign(info, { default: DEFAULT_WEIGHTS[k], min: 0.0, max: k !== "staff_pick" ? 3.0 : 5.0 });

  const engagementValue = (s) => (s === null || s === undefined ? UNKNOWN : ENGAGEMENT_BANDS.find(([floor]) => s >= floor)[1]);
  function clubPriority(club, w) {
    const a = 0.65 * w.size, b = 0.35 * w.engagement;
    if (a + b === 0) return 1.0;
    return (a * (SIZE_VALUE[club.size] ?? UNKNOWN) + b * engagementValue(club.engagement)) / (a + b);
  }
  const titleBoost = (prof, w) => 1.0 + w.title * ((TITLE_BOOST[prof.title] ?? 1.0) - 1.0);
  const choiceFactor = (rank, w) => (rank === null || rank === undefined ? 1.0 : Math.max(0.2, 1.0 - 0.1 * w.choice_rank * (rank - 1)));

  const PLACE_ALIASES = {
    "bay area": ["san francisco", "san jose"], "silicon valley": ["san francisco", "san jose"],
    "dc": ["washington", "maryland"], "nyc": ["new york city"], "new england": ["boston", "new haven"],
    "california": ["san francisco", "san diego", "orange county", "los angeles", "palm springs", "san jose"],
    "arizona": ["phoenix"], "colorado": ["denver", "southern colorado"],
  };
  const reEscape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  function wantsToVisit(prof, club) {
    const wish = clean(prof.travel_wishes);
    if (!wish) return false;
    const mentions = (phrase) => new RegExp(`(?<![\\p{L}\\p{N}_])${reEscape(phrase)}(?![\\p{L}\\p{N}_])`, "u").test(wish);
    const places = club.name.split(/[/,]/).filter((p) => p.trim().length >= 4).map(clean);
    if (club.region) places.push(clean(club.region));
    if (places.some(mentions)) return true;
    const clubName = clean(club.name), region = clean(club.region);
    return Object.entries(PLACE_ALIASES).some(([alias, targets]) => mentions(alias) && targets.some((t) => clubName.includes(t) || t === region));
  }

  function why(pair) {
    let reasons;
    if (pair.lectures.length) {
      const [rank, title] = pair.lectures[0];
      reasons = [`${ordinal(rank)}-choice lecture '${title}'`];
      if (pair.lectures.length > 1) reasons.push(`+${pair.lectures.length - 1} more requested`);
    } else reasons = [`${ordinal(pair.choice_rank)}-choice theme ${pair.shared_themes[0]}`];
    const n = pair.shared_months.length;
    reasons.push(`${n} shared month${n === 1 ? "" : "s"}`);
    if (pair.travel) reasons.push("in professor's preferred area");
    if (pair.repeat) reasons.push("REPEAT speaker");
    return reasons.join("; ");
  }

  function scorePair(club, prof, w) {
    const months = MONTHS.filter((m) => club.months.includes(m) && prof.months.includes(m));
    const profThemes = prof.themes;
    const themes = club.requested_themes.filter((t) => profThemes.has(clean(t)));
    const lectures = [];
    for (const r of club.requests) {
      const lec = prof.offers(r.title);
      if (lec && months.some((m) => lec.months.includes(m))) lectures.push([r.rank, lec.title]);
    }
    lectures.sort((x, y) => (x[0] - y[0]) || (x[1] < y[1] ? -1 : x[1] > y[1] ? 1 : 0));
    const profFormats = new Set(prof.formats.map(clean));
    const formats = club.formats.filter((f) => profFormats.has(clean(f)));

    let rank = null;
    if (lectures.length) rank = lectures[0][0];
    else if (themes.length) rank = Math.min(...club.requests.filter((r) => r.theme && profThemes.has(clean(r.theme))).map((r) => r.rank));

    const allowed = months.length > 0 && (themes.length > 0 || lectures.length > 0);
    let fit = 0.0, score = 0.0, priority = null, boost = 1.0;
    if (allowed) {
      const staffChoice = !!club.staff_pick && samePerson(club.staff_pick, prof.name);
      let lecSum = 0;
      for (const [r] of lectures) lecSum += choiceFactor(r, w);
      fit = 10 * w.lecture_match * lecSum
        + 5 * w.theme_match * themes.length * choiceFactor(rank, w)
        + 2 * w.month_overlap * months.length
        + 1 * w.format_match * formats.length
        + 10 * w.staff_pick * (staffChoice ? 1 : 0);
      fit = Math.max(fit, MIN_POINTS);
      priority = clubPriority(club, w);
      boost = priority >= TITLE_BOOST_FROM_PRIORITY ? titleBoost(prof, w) : 1.0;
      score = fit * priority * boost;
    }
    const pair = {
      club, prof, shared_months: months, shared_themes: themes, lectures, shared_formats: formats, choice_rank: rank,
      fit, score, priority, boost, repeat: club.past_speakers.some((s) => samePerson(prof.name, s)),
      travel: wantsToVisit(prof, club), allowed,
    };
    pair.first_choice_lecture = lectures.length > 0 && lectures[0][0] === 1;
    pair.why = () => why(pair);
    return pair;
  }

  class PairGrid {
    constructor(clubs, profs, w) {
      this.clubs = clubs; this.profs = profs; this.weights = w;
      this.pairs = clubs.map((club) => profs.map((prof) => scorePair(club, prof, w)));
    }
    at(c, p) { return this.pairs[c][p]; }
    allowed() { const out = []; this.pairs.forEach((row, c) => row.forEach((pair, p) => { if (pair.allowed) out.push([c, p, pair]); })); return out; }
    forClub(c) { return this.pairs[c]; }
  }

  // ================================================================ modes.py
  const EVERY_CLUB_FIRST = 1000.0, PREFERENCE_FIRST = 100.0;
  const clubPreference = (pair) => (pair.lectures.length ? Math.max(1, 6 - pair.lectures[0][0]) : Math.max(0.5, (6 - pair.choice_rank) / 2));
  const spreadCost = (k, ctx) => ctx.weights.spread * 0.3 * ctx.typical_score * (k - 1);

  const MODES = {
    recommended: {
      label: "Recommended",
      description: "Serves as many clubs as possible, then gives each the lecture it wanted most, while avoiding repeat speakers, spreading events across faculty and honouring travel wishes.",
      seatCost: spreadCost,
      worth(pair, ctx) {
        const w = ctx.weights;
        let value = EVERY_CLUB_FIRST + PREFERENCE_FIRST * clubPreference(pair) + pair.score;
        if (pair.repeat) value -= 60 * w.repeat_penalty;
        if (pair.travel) value += 0.15 * w.travel_bonus * pair.score;
        return value;
      },
    },
    best_fit: { label: "Best fit", description: "The highest possible total match score: strongest content fit, favouring large, engaged clubs.", worth: (pair) => pair.score },
    most_clubs: { label: "Most clubs served", description: "Serves as many clubs as possible and treats every club equally, regardless of size or engagement.", worth: (pair) => EVERY_CLUB_FIRST + pair.fit },
    balanced: {
      label: "Balanced",
      description: "Strong fit while spreading events across more faculty, avoiding repeat speakers and honouring professors' preferred travel areas.",
      seatCost: spreadCost,
      worth(pair, ctx) {
        const w = ctx.weights;
        let value = pair.score;
        if (pair.repeat) value *= Math.max(0.0, 1.0 - 0.6 * w.repeat_penalty);
        if (pair.travel) value *= 1.0 + 0.15 * w.travel_bonus;
        return value;
      },
    },
    top_choices: { label: "Clubs' top choices", description: "Gives as many clubs as possible the exact lecture they ranked highest, then the best fit.", worth: (pair) => PREFERENCE_FIRST * clubPreference(pair) + pair.score },
    legacy_greedy: { label: "Old method (greedy)", description: "The previous greedy algorithm on the cleaned data, for comparison.", worth: (pair) => pair.score, method: "greedy" },
  };
  const DEFAULT_MODES = ["recommended", "best_fit", "most_clubs", "balanced"];

  function median(xs) {
    if (!xs.length) return 0.0;
    const s = xs.slice().sort((a, b) => a - b), n = s.length, h = Math.floor(n / 2);
    return n % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
  }
  const contextFor = (grid) => ({ weights: grid.weights, typical_score: median(grid.allowed().map(([, , p]) => p.score)) });

  // ================================================================ solver.py
  const FORBIDDEN = 1e12;

  function hungarian(cost) {
    const rows = cost.length;
    if (!rows) return [];
    const cols = cost[0].length;
    const rowPot = new Array(rows + 1).fill(0.0), colPot = new Array(cols + 1).fill(0.0);
    const owner = new Array(cols + 1).fill(0), cameFrom = new Array(cols + 1).fill(0);
    for (let row = 1; row <= rows; row++) {
      owner[0] = row;
      let col = 0;
      const best = new Array(cols + 1).fill(Infinity), done = new Array(cols + 1).fill(false);
      for (;;) {
        done[col] = true;
        const r = owner[col];
        let delta = Infinity, nextCol = 0;
        for (let j = 1; j <= cols; j++) {
          if (done[j]) continue;
          const reduced = cost[r - 1][j - 1] - rowPot[r] - colPot[j];
          if (reduced < best[j]) { best[j] = reduced; cameFrom[j] = col; }
          if (best[j] < delta) { delta = best[j]; nextCol = j; }
        }
        for (let j = 0; j <= cols; j++) {
          if (done[j]) { rowPot[owner[j]] += delta; colPot[j] -= delta; } else best[j] -= delta;
        }
        col = nextCol;
        if (owner[col] === 0) break;
      }
      while (col) { const prev = cameFrom[col]; owner[col] = owner[prev]; col = prev; }
    }
    const assignment = new Array(rows).fill(-1);
    for (let j = 1; j <= cols; j++) if (owner[j]) assignment[owner[j] - 1] = j - 1;
    return assignment;
  }

  // seatCost(p, k) where k is the professor's k-th event overall (pins included)
  function bestAssignment(nClubs, capacity, worth, seatCost, firstSeat) {
    const seats = [];
    capacity.forEach((cap, p) => { for (let k = 1; k <= cap; k++) seats.push([p, k + (firstSeat ? firstSeat[p] : 0)]); });
    const cost = (c, p, k) => {
      const value = worth(c, p);
      if (value === null) return FORBIDDEN;
      const net = value - (seatCost ? seatCost(p, k) : 0.0);
      return net > 0 ? -net : FORBIDDEN;
    };
    const matrix = [];
    for (let c = 0; c < nClubs; c++) matrix.push(seats.map(([p, k]) => cost(c, p, k)).concat(new Array(nClubs).fill(0.0)));
    return hungarian(matrix).map((column, c) => (column < seats.length && matrix[c][column] < FORBIDDEN ? seats[column][0] : null));
  }

  function greedyAssignment(nClubs, capacity, worth) {
    const cands = [];
    for (let p = 0; p < capacity.length; p++) for (let c = 0; c < nClubs; c++) { const v = worth(c, p); if (v !== null) cands.push([v, c, p]); }
    cands.sort((x, y) => y[0] - x[0]);
    const chosen = new Array(nClubs).fill(null), used = new Array(capacity.length).fill(0);
    for (const [, c, p] of cands) if (chosen[c] === null && used[p] < capacity[p]) { chosen[c] = p; used[p]++; }
    return chosen;
  }

  // ================================================================ plans.py
  const SUMMARY_LABELS = {
    clubs_matched: "Clubs matched", clubs_unmatched: "Clubs without a speaker",
    first_choice_lectures: "Got their 1st-choice lecture", requested_lecture_matches: "Got a lecture they asked for",
    top_choice_matches: "Got their 1st-choice theme or lecture", total_score: "Total match score", avg_score: "Average match score",
    profs_used: "Professors used", profs_available: "Professors who could be used", max_events_per_prof: "Most events for one professor",
    profs_with_multiple_events: "Professors with 2+ events", repeat_speakers: "Repeat speakers",
    month_clashes: "Professors double-booked in a month", staff_pick_agreement: "Same as staff's 2026 pick", clubs_total: "Clubs in the program",
  };

  /** Each club's professor index (or null). pins = [[clubId, profName]] booked first. */
  function choose(modeKey, grid, ctx, pins, notes) {
    const mode = MODES[modeKey];
    const nC = grid.clubs.length, nP = grid.profs.length;
    const fixed = new Array(nC).fill(null), used = new Array(nP).fill(0);
    for (const [clubId, profName] of pins || []) {
      const c = grid.clubs.findIndex((x) => x.id === clubId);
      const p = grid.profs.findIndex((x) => x.name === profName);
      if (c < 0 || p < 0) continue;
      if (!grid.at(c, p).allowed) { if (notes) notes.push(`${profName} can't be booked for ${grid.clubs[c].name}: no shared month and topic.`); continue; }
      if (fixed[c] !== null || used[p] >= grid.profs[p].max_events) { if (notes) notes.push(`${profName} couldn't also be booked for ${grid.clubs[c].name}: all their events are taken.`); continue; }
      fixed[c] = p; used[p]++;
    }
    const worth = (c, p) => {
      if (fixed[c] !== null) return null;
      const pair = grid.at(c, p);
      return pair.allowed ? mode.worth(pair, ctx) : null;
    };
    const capacity = grid.profs.map((prof, p) => prof.max_events - used[p]);
    let chosen;
    if (mode.method === "greedy") chosen = greedyAssignment(nC, capacity, worth);
    else chosen = bestAssignment(nC, capacity, worth, mode.seatCost ? (p, k) => mode.seatCost(k, ctx) : null, used);
    return chosen.map((p, c) => (fixed[c] !== null ? fixed[c] : p));
  }

  function suggestMonths(made) {
    const byProf = new Map();
    for (const pair of made) { if (!byProf.has(pair.prof.name)) byProf.set(pair.prof.name, []); byProf.get(pair.prof.name).push(pair); }
    const months = new Map();
    let clashes = 0;
    for (const pairs of byProf.values()) {
      const [picked, forced] = distinctMonths(pairs);
      for (const [k, v] of picked) months.set(k, v);
      if (forced > 0) clashes++;
    }
    return [months, clashes];
  }
  function distinctMonths(pairs) {
    const order = pairs.map((p, i) => [p, i]).sort((a, b) => (a[0].shared_months.length - b[0].shared_months.length) || (a[1] - b[1])).map((x) => x[0]);
    const best = { months: new Map(), forced: pairs.length + 1 };
    const place = (i, taken, picked, forced) => {
      if (forced >= best.forced) return;
      if (i === order.length) { best.months = picked; best.forced = forced; return; }
      const pair = order[i];
      for (const m of pair.shared_months) if (!taken.has(m)) place(i + 1, new Set([...taken, m]), new Map([...picked, [pair, m]]), forced);
      place(i + 1, taken, new Map([...picked, [pair, pair.shared_months[0]]]), forced + 1);
    };
    place(0, new Set(), new Map(), 0);
    return [best.months, best.forced];
  }

  function fmt1(x) {
    // Python's f"{x:.1f}" (round half to even on the exact value)
    const t = x * 10, fl = Math.floor(t);
    if (t - fl === 0.5) return ((fl % 2 === 0 ? fl : fl + 1) / 10).toFixed(1);
    return x.toFixed(1);
  }
  const plural = (n, word) => `${n} ${word}${n > 1 ? "s" : ""}`;

  function stillFree(c, grid, events) {
    const club = grid.clubs[c], options = [];
    grid.profs.forEach((prof, p) => {
      const pair = grid.at(c, p), open = prof.max_events - (events[p] || 0);
      if (open <= 0 || pair.repeat || !prof.lectures.length) return;
      const named = clean(prof.travel_wishes).includes(clean(club.name.split("/")[0]));
      let note = plural(open, "open slot");
      if (named) note += `; asked for ${club.name} by name`;
      else if (pair.travel) note += "; asked to visit this area";
      options.push([[named ? 1 : 0, pair.travel ? 1 : 0, open, prof.months.length], prof.name, note]);
    });
    options.sort((a, b) => { for (let i = 0; i < 4; i++) if (a[0][i] !== b[0][i]) return b[0][i] - a[0][i]; return 0; });
    return options.slice(0, 3).map(([, name, note]) => [name, `still free: ${note}`]);
  }

  function explainUnmatched(c, grid, events) {
    const club = grid.clubs[c];
    if (!club.submitted_form) return ["No request form submitted", stillFree(c, grid, events)];
    if (!club.months.length) return ["Missing availability", stillFree(c, grid, events)];
    if (!club.requests.length) return ["No themes or lectures requested", stillFree(c, grid, events)];
    const pairs = grid.forClub(c);
    if (!pairs.some((p) => p.shared_months.length)) return ["No shared months with any professor", []];
    const allowed = pairs.filter((p) => p.allowed).sort((a, b) => b.score - a.score);
    if (!allowed.length) {
      const key = (p) => [(p.shared_themes.length || p.lectures.length) ? 1 : 0, p.shared_months.length];
      const nearest = pairs.slice().sort((a, b) => { const ka = key(a), kb = key(b); return (kb[0] - ka[0]) || (kb[1] - ka[1]); });
      return ["No content overlap with any available professor", nearest.slice(0, 3).map((p) =>
        [p.prof.name, "near miss: " + (!p.shared_months.length ? "no shared month" : "no requested theme or lecture")])];
    }
    const suggestions = [];
    let anyOpen = false;
    for (const pair of allowed.slice(0, 3)) {
      const used = events[grid.profs.indexOf(pair.prof)] || 0, cap = pair.prof.max_events, open = cap - used;
      anyOpen = anyOpen || open > 0;
      const st = open <= 0 ? `fully booked (${used}/${cap})` : plural(open, "open slot");
      suggestions.push([pair.prof.name, `score ${fmt1(pair.score)}; ${st}; ${pair.why()}`]);
    }
    return [anyOpen ? "Left out so suitable professors are not overloaded" : "All suitable professors are fully booked", suggestions];
  }

  function summarize(made, grid, events, clashes) {
    const n = made.length;
    let total = 0;
    for (const p of made) total += p.score;
    const counts = Object.values(events);
    const allowedProfs = new Set(grid.allowed().map(([, p]) => p));
    const r = (x, d) => Number(x.toFixed(d));
    return {
      clubs_matched: n, clubs_total: grid.clubs.length, clubs_unmatched: grid.clubs.length - n,
      profs_used: counts.length, profs_available: allowedProfs.size,
      total_score: r(total, 1), avg_score: n ? r(total / n, 2) : 0.0,
      top_choice_matches: made.filter((p) => p.choice_rank === 1).length,
      first_choice_lectures: made.filter((p) => p.first_choice_lecture).length,
      requested_lecture_matches: made.filter((p) => p.lectures.length).length,
      repeat_speakers: made.filter((p) => p.repeat).length,
      max_events_per_prof: counts.length ? Math.max(...counts) : 0,
      profs_with_multiple_events: counts.filter((x) => x > 1).length,
      month_clashes: clashes,
      staff_pick_agreement: made.filter((p) => !!p.club.staff_pick && samePerson(p.club.staff_pick, p.prof.name)).length,
    };
  }

  const byClubName = (a, b) => (a.club.name < b.club.name ? -1 : a.club.name > b.club.name ? 1 : 0);

  function buildPlan(modeKey, grid, ctx, pins) {
    const mode = MODES[modeKey], pinNotes = [];
    const choice = choose(modeKey, grid, ctx, pins, pinNotes);
    const made = [], events = {};
    choice.forEach((p, c) => { if (p !== null) { made.push(grid.at(c, p)); events[p] = (events[p] || 0) + 1; } });
    const [months, clashes] = suggestMonths(made);
    const pinSet = new Set((pins || []).map(([c, p]) => c + "\u0000" + p));
    const matches = made.map((pair) => ({
      pair, suggested_month: months.get(pair), prof_events: events[grid.profs.indexOf(pair.prof)],
      pinned: pinSet.has(pair.club.id + "\u0000" + pair.prof.name),
    })).sort((a, b) => byClubName(a.pair, b.pair));
    const unmatched = [];
    choice.forEach((p, c) => {
      if (p !== null) return;
      const [reason, suggestions] = explainUnmatched(c, grid, events);
      unmatched.push({ club: grid.clubs[c], reason, suggestions });
    });
    unmatched.sort((a, b) => (a.club.name < b.club.name ? -1 : a.club.name > b.club.name ? 1 : 0));
    return { key: modeKey, label: mode.label, description: mode.description, matches, unmatched, events, choice,
      summary: summarize(made, grid, events, clashes), pin_notes: pinNotes };
  }

  /** Score every pair once, then build each requested plan. */
  function runPlans(data, weights, modes, pins) {
    modes = modes || DEFAULT_MODES;
    const grid = new PairGrid(data.clubs, data.profs, coerceWeights(weights));
    const ctx = contextFor(grid);
    const plans = {};
    for (const key of modes) {
      if (!MODES[key]) throw new Error(`Unknown mode '${key}'. Choose from: ${Object.keys(MODES).join(", ")}`);
      plans[key] = buildPlan(key, grid, ctx, pins);
    }
    return { grid, ctx, plans };
  }

  // Which of the three files is this? Looks at the headers only.
  function sniffKind(text) {
    const [headers] = readTable(text);
    const s = new Set(headers.map(squash));
    const has = (...names) => names.some((n) => s.has(squash(n)));
    if (has("Club Check", "HLS Score") || headers.some((h) => /^theme\d+$/.test(squash(h)))) return "club";
    if (has("Recipient Full Name", "# of Events") || headers.some((h) => /^participate/.test(squash(h)))) return "prof";
    if (has("Topic", "Lecture Title") && has("Faculty", "Professor", "Speaker")) return "lecture";
    return null;
  }

  const api = {
    MONTHS, MODES, DEFAULT_MODES, WEIGHT_INFO, DEFAULT_WEIGHTS, COLUMN_SPEC, SUMMARY_LABELS, FILES,
    loadInputs, dataIssues, runPlans, coerceWeights, sniffKind, readTable, parseCSV, clean, nameKey, samePerson, ordinal,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Engine = api;
})(typeof self !== "undefined" ? self : this);
