// src/components/ui/StatCard.jsx
export default function StatCard({ label, value, accent = "ink" }) {
  const accentClasses = {
    ink: "text-ink-900",
    amber: "text-amber-500",
    teal: "text-teal-600",
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-2 font-display text-3xl font-semibold ${accentClasses[accent]}`}>
        {value}
      </p>
    </div>
  );
}