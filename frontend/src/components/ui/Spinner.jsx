// src/components/ui/Spinner.jsx
export default function Spinner({ className = "" }) {
  return (
    <div
      className={`h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-ink-700 ${className}`}
      role="status"
      aria-label="Chargement"
    />
  );
}