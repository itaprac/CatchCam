const STORAGE_KEY = "spadajace-kulki-open-day-leaderboard";
const MAX_ENTRIES = 12;

export function loadLeaderboard() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((entry) => entry && typeof entry.name === "string")
      .map((entry) => ({
        name: entry.name.slice(0, 20),
        score: clampInt(entry.score),
        combo: clampInt(entry.combo),
        playedAt: typeof entry.playedAt === "string" ? entry.playedAt : new Date().toISOString(),
      }))
      .sort((a, b) => b.score - a.score || b.combo - a.combo)
      .slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

export function saveScore(entry) {
  const next = [normalizeEntry(entry), ...loadLeaderboard()]
    .sort((a, b) => b.score - a.score || b.combo - a.combo)
    .slice(0, MAX_ENTRIES);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function clearLeaderboard() {
  localStorage.removeItem(STORAGE_KEY);
}

export function getRank(entries, score, combo) {
  return (
    entries.findIndex((entry) => entry.score === score && entry.combo === combo) + 1 || null
  );
}

function normalizeEntry(entry) {
  const trimmedName = String(entry.name || "Gracz").trim().slice(0, 20) || "Gracz";
  return {
    name: trimmedName,
    score: clampInt(entry.score),
    combo: clampInt(entry.combo),
    playedAt: new Date().toISOString(),
  };
}

function clampInt(value) {
  return Math.max(0, Number.parseInt(value, 10) || 0);
}
