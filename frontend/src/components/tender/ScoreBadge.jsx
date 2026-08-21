// src/components/tender/ScoreBadge.jsx
import { scoreTier } from "../../utils/scoreColors";
import { useQuery } from "@tanstack/react-query";
import { getRuntimeThresholds } from "../../api/config";

export default function ScoreBadge({ score }) {
  const { data } = useQuery({
    queryKey: ["runtime-thresholds"],
    queryFn: getRuntimeThresholds,
    staleTime: 60_000,
  });
  const tier = scoreTier(score, data?.score_instant_alert_threshold ?? 70);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-xs font-semibold ${tier.bg} ${tier.text}`}
      title={tier.label}
    >
      {score}%
    </span>
  );
}