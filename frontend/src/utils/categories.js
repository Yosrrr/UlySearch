// src/utils/categories.js
// Miroir de app/core/keywords.py (CATEGORIES) — à garder synchronisé
// si les catégories changent côté backend.
export const CATEGORY_LABELS = {
  MATERIEL_ROULANT: "Matériel roulant",
  ENGINS_TP: "Engins TP",
  MANUTENTION: "Manutention",
  ENGINS_SPECIAUX: "Engins spéciaux",
  GROUPES_ELECTROGENES: "Groupes électrogènes",
};

export function categoryLabel(key) {
  return CATEGORY_LABELS[key] ?? key ?? "—";
}