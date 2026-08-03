// src/components/layout/PageWrapper.jsx
export default function PageWrapper({ title, subtitle, actions, children }) {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      {(title || actions) && (
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            {title && <h1 className="font-display text-2xl font-semibold text-ink-900">{title}</h1>}
            {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
          </div>
          {actions && <div className="flex gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
}