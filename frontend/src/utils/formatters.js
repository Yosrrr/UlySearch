// src/utils/formatters.js
export function formatDate(isoDate) {
  if (!isoDate) return "—";
  return new Date(isoDate).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function daysUntil(isoDate) {
  if (!isoDate) return null;
  const diff = new Date(isoDate) - new Date();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}