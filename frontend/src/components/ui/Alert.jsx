// src/components/ui/Alert.jsx
const VARIANTS = {
  info: "bg-ink-800/5 text-ink-800 border-ink-800/10",
  error: "bg-rose-500/10 text-rose-500 border-rose-500/20",
  success: "bg-teal-500/10 text-teal-600 border-teal-500/20",
};

export default function Alert({ variant = "info", children }) {
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${VARIANTS[variant]}`}>
      {children}
    </div>
  );
}