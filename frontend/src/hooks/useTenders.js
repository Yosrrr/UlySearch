// src/hooks/useTenders.js
import { useQuery } from "@tanstack/react-query";
import { getTenders, getTender } from "../api/tenders";

export function useTenders(filters) {
  return useQuery({
    queryKey: ["tenders", filters],
    queryFn: () => getTenders(filters),
    staleTime: 30_000,
  });
}

export function useTender(id) {
  return useQuery({
    queryKey: ["tender", id],
    queryFn: () => getTender(id),
    enabled: Boolean(id),
  });
}