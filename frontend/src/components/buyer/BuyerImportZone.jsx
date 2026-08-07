BuyerImportZone.jsx// src/components/buyer/BuyerImportZone.jsx
import { useState } from "react";
import { UploadCloud } from "lucide-react";
import { importBuyersFile } from "../../api/buyers";

export default function BuyerImportZone({ onImported }) {
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setStatus("loading");
    try {
      const result = await importBuyersFile(file);
      setStatus("done");
      setMessage(`${result.imported} acheteur(s) importé(s).`);
      onImported?.();
    } catch (err) {
      setStatus("error");
      setMessage(err.response?.data?.detail || "Échec de l'import.");
    }
  }

  return (
    <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 bg-white px-6 py-8 text-center hover:border-ink-700">
      <UploadCloud className="text-slate-400" size={28} />
      <span className="text-sm font-medium text-ink-900">
        Importer la liste des acheteurs (Excel)
      </span>
      <span className={`text-xs ${status === "error" ? "text-rose-500" : "text-slate-500"}`}>
        {status === "loading" && "Import en cours..."}
        {status === "idle" && "Cliquez ou déposez un fichier .xlsx"}
        {(status === "done" || status === "error") && message}
      </span>
      <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFile} />
    </label>
  );
}