// src/components/tender/TenderCard.jsx
import { Link } from "react-router-dom";
import { Building2, CalendarClock } from "lucide-react";
import ScoreBadge from "./ScoreBadge";
import TenderStatusBadge from "./TenderStatusBadge";
import { formatDate, daysUntil } from "../../utils/formatters";

function hasScore(tender) {
  return (
    tender.score_details &&
    Object.values(tender.score_details).some((v) => typeof v === "number")
  );
}

export default function TenderCard({ tender }) {
  const remaining = daysUntil(tender.date_limite);
  const urgent = remaining !== null && remaining <= 5;

  return (
    <Link
      to={`/tenders/${tender.id}`}
      className="block rounded-xl border border-slate-200 bg-white p-4 transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-ink-900">{tender.objet}</p>
          <div className="mt-1 flex items-center gap-1.5 text-sm text-slate-600">
            <Building2 size={14} />
            <span className="truncate">{tender.acheteur}</span>
          </div>
        </div>
        {hasScore(tender) ? (
          <ScoreBadge score={tender.score} />
        ) : (
          <span className="whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-400">
            Score à venir
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
        {tender.categorie && (
          <span className="rounded-full bg-slate-100 px-2 py-1">{tender.categorie}</span>
        )}
        <span className="rounded-full bg-slate-100 px-2 py-1 uppercase">{tender.source}</span>
        <span
          className={`flex items-center gap-1 rounded-full px-2 py-1 ${
            urgent ? "bg-rose-500/10 text-rose-500" : "bg-slate-100"
          }`}
        >
          <CalendarClock size={12} />
          Limite : {formatDate(tender.date_limite)}
          {remaining !== null && ` (${remaining >= 0 ? `J-${remaining}` : "dépassé"})`}
        </span>
        <TenderStatusBadge statut={tender.statut} />
        {tender.commercial_assigne && (
          <span className="rounded-full bg-ink-800/10 px-2 py-1 text-ink-800">
            {tender.commercial_assigne}
          </span>
        )}
      </div>
    </Link>
  );
}