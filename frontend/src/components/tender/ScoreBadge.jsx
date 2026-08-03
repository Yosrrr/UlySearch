// src/components/tender/ScoreBadge.jsx
import { scoreTier } from "../../utils/scoreColors";

export default function ScoreBadge({ score }) {
  const tier = scoreTier(score);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-xs font-semibold ${tier.bg} ${tier.text}`}
      title={tier.label}
    >
      {score}%
    </span>
  );
}