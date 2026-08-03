// src/utils/scoreColors.js
// Seuils alignés sur RELEVANCE_INSTANT_ALERT_THRESHOLD=80 et
// RELEVANCE_RETAIN_THRESHOLD=50 côté backend (config.py).
export function scoreTier(score) {
  if (score > 80) return { label: "Alerte instantanée", bg: "bg-amber-500", text: "text-white" };
  if (score >= 50) return { label: "Pertinent", bg: "bg-ink-700", text: "text-white" };
  return { label: "Faible", bg: "bg-slate-200", text: "text-slate-600" };
}