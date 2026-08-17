// src/components/ui/ExportButtons.jsx

import { FileSpreadsheet, FileText } from "lucide-react";

export default function ExportButtons({ onExport, exporting }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Bouton Excel */}
      <button
        type="button"
        onClick={() => onExport("xlsx")}
        disabled={exporting}
        className="
          inline-flex items-center justify-center gap-2
          rounded-lg
          border border-slate-200
          bg-white
          px-3.5 py-2
          text-sm font-medium text-ink-900
          shadow-sm
          transition-colors
          hover:bg-slate-50
          focus:outline-none
          focus:ring-2
          focus:ring-slate-300
          disabled:cursor-not-allowed
          disabled:opacity-50
        "
      >
        <FileSpreadsheet size={16} strokeWidth={2} />
        <span>Excel</span>
      </button>

      {/* Bouton PDF */}
      <button
        type="button"
        onClick={() => onExport("pdf")}
        disabled={exporting}
        className="
          inline-flex items-center justify-center gap-2
          rounded-lg
          border border-slate-200
          bg-white
          px-3.5 py-2
          text-sm font-medium text-ink-900
          shadow-sm
          transition-colors
          hover:bg-slate-50
          focus:outline-none
          focus:ring-2
          focus:ring-slate-300
          disabled:cursor-not-allowed
          disabled:opacity-50
        "
      >
        <FileText size={16} strokeWidth={2} />
        <span>PDF</span>
      </button>
    </div>
  );
}