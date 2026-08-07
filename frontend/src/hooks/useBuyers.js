// src/hooks/useBuyers.js
import { useQuery } from "@tanstack/react-query";
import { getBuyers } from "../api/buyers";

export function useBuyers() {
  return useQuery({ queryKey: ["buyers"], queryFn: getBuyers, staleTime: 30_000 });
}