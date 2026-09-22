// Mirrors apps/api/agent/validation.py's looks_like_gibberish -- client-side
// copy is for instant feedback only; the backend re-checks authoritatively
// (never trust the client for the actual cost-saving gate).
const REPEATED_CHAR_RUN = /(.)\1{4,}/;
const WORD_RE = /[A-Za-z']{2,}/g;

export function looksLikeGibberish(text: string): boolean {
  const normalized = text.trim();
  if (!normalized) return true;

  if (REPEATED_CHAR_RUN.test(normalized.toLowerCase())) return true;

  const words = new Set((normalized.match(WORD_RE) ?? []).map((w) => w.toLowerCase()));
  if (words.size < 3) return true;

  const uniqueRatio = new Set(normalized.toLowerCase()).size / normalized.length;
  if (uniqueRatio < 0.15) return true;

  return false;
}
