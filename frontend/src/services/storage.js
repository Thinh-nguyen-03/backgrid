import { JOB_HISTORY_KEY, JOB_HISTORY_MAX, JOB_HISTORY_VERSION } from '../config/constants.js';

function load() {
  try {
    const raw = localStorage.getItem(JOB_HISTORY_KEY);
    if (!raw) return { version: JOB_HISTORY_VERSION, entries: [] };
    const data = JSON.parse(raw);
    if (data.version !== JOB_HISTORY_VERSION) {
      localStorage.removeItem(JOB_HISTORY_KEY);
      return { version: JOB_HISTORY_VERSION, entries: [] };
    }
    return data;
  } catch {
    return { version: JOB_HISTORY_VERSION, entries: [] };
  }
}

function save(data) {
  localStorage.setItem(JOB_HISTORY_KEY, JSON.stringify(data));
}

export function getHistory() {
  return load().entries;
}

export function addHistoryEntry(entry) {
  const data = load();
  data.entries.unshift(entry);
  if (data.entries.length > JOB_HISTORY_MAX) {
    data.entries = data.entries.slice(0, JOB_HISTORY_MAX);
  }
  save(data);
}

export function clearHistory() {
  save({ version: JOB_HISTORY_VERSION, entries: [] });
}
