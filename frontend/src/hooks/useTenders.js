// src/hooks/useTenders.js
import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchTenders,
  fetchTender,
  fetchRejectedTenders,
  updateTenderStatus,
  updateTenderFeedback,
} from "../api/tenders";

/**
 * Liste paginée (F-019).
 * Retourne { items, total, limit, offset, hasMore, nextPage, prevPage, resetPage, ...query }
 */
export function useTenders(filters = {}) {
  const limit = filters.limit ?? 50;
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["tenders", { ...filters, limit, offset }],
    queryFn: () => fetchTenders({ ...filters, limit, offset }),
    placeholderData: (previousData) => previousData,
  });

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const hasMore = offset + items.length < total;

  const resetPage = useCallback(() => setOffset(0), []);

  return {
    ...query,
    /** @deprecated préférer `items` — compat si une page lit encore `data` comme liste */
    data: items,
    items,
    total,
    limit: query.data?.limit ?? limit,
    offset,
    setOffset,
    resetPage,
    hasMore,
    nextPage: () => setOffset((o) => o + limit),
    prevPage: () => setOffset((o) => Math.max(0, o - limit)),
  };
}

/**
 * Détail d'un marché (TenderDetailPage).
 */
export function useTender(id) {
  return useQuery({
    queryKey: ["tender", id],
    queryFn: () => fetchTender(id),
    enabled: Boolean(id),
  });
}

/**
 * Liste paginée des non retenus.
 */
export function useRejectedTenders({ limit = 50 } = {}) {
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["rejected-tenders", limit, offset],
    queryFn: () => fetchRejectedTenders({ limit, offset }),
    placeholderData: (previousData) => previousData,
  });

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const hasMore = offset + items.length < total;

  return {
    ...query,
    data: items,
    items,
    total,
    limit,
    offset,
    setOffset,
    hasMore,
    nextPage: () => setOffset((o) => o + limit),
    prevPage: () => setOffset((o) => Math.max(0, o - limit)),
  };
}

/**
 * Mutations statut / feedback (détail + repêcher).
 */
export function useTenderMutations() {
  const queryClient = useQueryClient();

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["tenders"] });
    queryClient.invalidateQueries({ queryKey: ["tender"] });
    queryClient.invalidateQueries({ queryKey: ["rejected-tenders"] });
  };

  const statusMutation = useMutation({
    mutationFn: ({ id, statut }) => updateTenderStatus(id, statut),
    onSuccess: invalidate,
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ id, feedback }) => updateTenderFeedback(id, feedback),
    onSuccess: invalidate,
  });

  return { statusMutation, feedbackMutation };
}