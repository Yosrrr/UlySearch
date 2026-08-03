// src/utils/scoreDetails.js
// Miroir de extract_best_score côté backend (app/schemas/tender.py).
// score_details a la forme : {"MATERIEL_ROULANT": {"score": 90, "mots_cles_matches": [...]}, ...}
export function extractScoreInfo(scoreDetails) {
  if (!scoreDetails || typeof scoreDetails !== "object") {
    return { hasScore: false, score: 0, topCategory: null };
  }

  let best = null;
  for (const [category, value] of Object.entries(scoreDetails)) {
    const numericScore =
      typeof value === "number"
        ? value
        : value && typeof value === "object" && typeof value.score === "number"
        ? value.score
        : null;

    if (numericScore !== null && (best === null || numericScore > best.score)) {
      best = { category, score: numericScore };
    }
  }

  if (!best) return { hasScore: false, score: 0, topCategory: null };
  return { hasScore: true, score: best.score, topCategory: best.category };
}