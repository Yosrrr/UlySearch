import { useState } from "react";
import { ScanLine } from "lucide-react";
import { importBuyersScan } from "../../api/buyers";

export default function BuyerScanImportZone({ onImported }) {
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setStatus("loading");
    try {
      const result = await importBuyersScan(file);
      setStatus("done");
      setMessage(
        `${result.detectes} détecté(s) — ${result.crees} créé(s), ${result.fusionnes} fusionné(s) avec l'existant.`
      );
      onImported?.();
    } catch (err) {
      setStatus("error");
      setMessage(err.response?.data?.detail || "Échec de l'analyse du document.");
    }
  }

  return (
    <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 bg-white px-6 py-8 text-center hover:border-ink-700">
      <ScanLine className="text-slate-400" size={28} />
      <span className="text-sm font-medium text-ink-900">
        Scanner une liste d'acheteurs (PDF ou photo)
      </span>
      <span className={`text-xs ${status === "error" ? "text-rose-500" : "text-slate-500"}`}>
        {status === "loading" && "Analyse OCR en cours..."}
        {status === "idle" && "Cliquez ou déposez un PDF, JPG ou PNG"}
        {(status === "done" || status === "error") && message}
      </span>
      <input type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={handleFile} />
    </label>
  );
}