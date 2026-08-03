// src/components/tender/TenderStatusBadge.jsx
const LABELS = {
  nouveau: { label: "Nouveau", cls: "bg-ink-800/10 text-ink-800" },
  retenu: { label: "Retenu", cls: "bg-teal-500/15 text-teal-600" },
  sans_suite: { label: "Sans suite", cls: "bg-slate-200 text-slate-600" },
};

export default function TenderStatusBadge({ statut }) {
  const info = LABELS[statut] ?? LABELS.nouveau;
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${info.cls}`}>{info.label}</span>
  );
}