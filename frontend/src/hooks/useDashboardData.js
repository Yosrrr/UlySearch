// src/hooks/useDashboardData.js
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTenders } from "./useTenders";
import { getRuntimeThresholds } from "../api/config";
import { daysUntil } from "../utils/formatters";

/**
 * Dashboard : s'appuie sur useTenders (page F-019).
 * - items = marchés de la page (ou data renvoyé comme liste par le hook)
 * - decision === "retenu" (pas statut commercial)
 * - limit élevé pour stats globales approximatives côté client
 */
export function useDashboardData() {
  const {
    items,
    data, // compat : useTenders peut exposer data === items
    total: totalApi,
    isLoading,
    isError,
  } = useTenders({
    limit: 100, // max API ; stats sur cet échantillon + totalApi si dispo
    // include_rejected: false par défaut côté API (score > 0)
  });

  // Liste exploitable
  const tenders = useMemo(() => {
    if (Array.isArray(items) && items.length >= 0 && items !== undefined) {
      // items prioritaire
      if (items.length || totalApi === 0) return items;
    }
    if (Array.isArray(data)) return data;
    if (data?.items && Array.isArray(data.items)) return data.items;
    return [];
  }, [items, data, totalApi]);

  const thresholdsQuery = useQuery({
    queryKey: ["runtime-thresholds"],
    queryFn: getRuntimeThresholds,
    staleTime: 60_000,
  });

  const instantThreshold =
    thresholdsQuery.data?.score_instant_alert_threshold ?? 70;

  const dashboard = useMemo(() => {
    // tenders peut être [] au premier rendu
    const list = Array.isArray(tenders) ? tenders : [];

    // Verdict moteur (CompanyTender.decision), pas le cycle commercial
    const isRetenu = (t) =>
      t.decision === "retenu" ||
      // filet si ancienne API sans decision
      (t.decision == null && t.statut === "retenu");

    const retenus = list.filter(isRetenu);
    const assignes = list.filter((t) => Boolean(t.commercial_assigne));
    const urgentes = list.filter((t) => {
      const remaining = daysUntil(t.date_limite);
      return remaining !== null && remaining >= 0 && remaining <= 7;
    });
    const feedbacks = list.filter((t) => Boolean(t.feedback));

    const alertesDuJour = [...list]
      .filter((t) => (t.score ?? 0) > instantThreshold)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, 5);

    const parCommercial = {};
    for (const t of assignes) {
      const key = t.commercial_assigne;
      if (!parCommercial[key]) {
        parCommercial[key] = {
          commercial: key,
          categorie: t.top_categorie,
          nb_marches: 0,
        };
      }
      parCommercial[key].nb_marches += 1;
    }

    const dernierMarche = [...list].sort(
      (a, b) => new Date(b.date_detection) - new Date(a.date_detection)
    )[0];

    // nouveaux_marches : préférer total API (toutes pages) si fourni
    const nouveaux =
      typeof totalApi === "number" && totalApi >= list.length
        ? totalApi
        : list.length;

    return {
      stats: {
        nouveaux_marches: nouveaux,
        retenus: retenus.length,
        assignes: assignes.length,
        urgentes: urgentes.length,
        feedbacks: feedbacks.length,
      },
      alertes_du_jour: alertesDuJour,
      repartition_commerciaux: Object.values(parCommercial),
      derniere_detection: dernierMarche?.date_detection ?? null,
      weekly_counts: computeWeeklyCounts(list),
      // méta debug éventuelle
      _sample_size: list.length,
      _total_api: totalApi ?? null,
    };
  }, [tenders, instantThreshold, totalApi]);

  return {
    dashboard: tenders ? dashboard : null,
    isLoading: isLoading || thresholdsQuery.isLoading,
    isError: isError || thresholdsQuery.isError,
    instantThreshold,
  };
}

function computeWeeklyCounts(tenders, weeksBack = 8) {
  const list = Array.isArray(tenders) ? tenders : [];
  const now = new Date();
  const weeks = [];

  for (let i = weeksBack - 1; i >= 0; i--) {
    const weekStart = new Date(now);
    weekStart.setDate(now.getDate() - now.getDay() - i * 7);
    weekStart.setHours(0, 0, 0, 0);

    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 7);

    const count = list.filter((t) => {
      const d = new Date(t.date_detection);
      return d >= weekStart && d < weekEnd;
    }).length;

    weeks.push({
      semaine: weekStart.toLocaleDateString("fr-FR", {
        day: "2-digit",
        month: "short",
      }),
      marches: count,
    });
  }

  return weeks;
}