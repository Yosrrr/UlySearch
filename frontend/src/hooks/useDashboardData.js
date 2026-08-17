// src/hooks/useDashboardData.js
import { useMemo } from "react";
import { useTenders } from "./useTenders";


export function useDashboardData() {
  const { data: tenders, isLoading, isError } = useTenders({});

  const dashboard = useMemo(() => {
    if (!tenders) return null;

    const retenus = tenders.filter((t) => t.statut === "retenu");
    const assignes = tenders.filter((t) => Boolean(t.commercial_assigne));
    const alertesDuJour = [...tenders]
      .filter((t) => t.score > 80)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);

    const parCommercial = {};
    for (const t of assignes) {
      const key = t.commercial_assigne;
      if (!parCommercial[key]) {
        parCommercial[key] = { commercial: key, categorie: t.top_categorie, nb_marches: 0 };
      }
      parCommercial[key].nb_marches += 1;
    }

    const dernierMarche = [...tenders].sort(
      (a, b) => new Date(b.date_detection) - new Date(a.date_detection)
    )[0];

    return {
  stats: {
    nouveaux_marches: tenders.length,
    retenus: retenus.length,
    assignes: assignes.length,
  },
  alertes_du_jour: alertesDuJour,
  repartition_commerciaux: Object.values(parCommercial),
  derniere_detection: dernierMarche?.date_detection ?? null,
  weekly_counts: computeWeeklyCounts(tenders),
};
  }, [tenders]);

  return { dashboard, isLoading, isError };
}

function computeWeeklyCounts(tenders, weeksBack = 8) {
  const now = new Date();
  const weeks = [];

  for (let i = weeksBack - 1; i >= 0; i--) {
    const weekStart = new Date(now);
    weekStart.setDate(now.getDate() - now.getDay() - i * 7); // début de semaine (dimanche)
    weekStart.setHours(0, 0, 0, 0);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 7);

    const count = tenders.filter((t) => {
      const d = new Date(t.date_detection);
      return d >= weekStart && d < weekEnd;
    }).length;

    weeks.push({
      semaine: weekStart.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }),
      marches: count,
    });
  }

  return weeks;
}