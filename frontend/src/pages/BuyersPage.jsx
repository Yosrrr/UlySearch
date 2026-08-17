// src/pages/BuyersPage.jsx
import { useState } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { BadgeCheck, Pencil, Plus } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import BuyerImportZone from "../components/buyer/BuyerImportZone";
import Modal from "../components/ui/Modal";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import { useBuyers } from "../hooks/useBuyers";
import { updateBuyer, createBuyer } from "../api/buyers";
import BuyerScanImportZone from "../components/buyer/BuyerScanImportZone";

export default function BuyersPage() {
  const { data: buyers, isLoading } = useBuyers();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const queryClient = useQueryClient();

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }) => updateBuyer(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["buyers"] });
      setEditing(null);
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload) => createBuyer(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["buyers"] });
      setCreating(false);
    },
  });

  const toggleClient = (buyer) => {
    updateMutation.mutate({
      id: buyer.id,
      payload: { client_sotradies: buyer.client_sotradies === "Oui" ? "Non" : "Oui" },
    });
  };

  const filtered = (buyers || []).filter((b) =>
    b.nom_acheteur.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <PageWrapper
      title="Acheteurs"
      subtitle="Liste des acheteurs déjà clients SOTRADIES — utilisée pour prioriser les alertes."
      actions={
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-1.5 rounded-lg bg-ink-800 px-3 py-2 text-sm font-medium text-white hover:bg-ink-700"
        >
          <Plus size={14} /> Ajouter un acheteur
        </button>
      }
    >
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
  <BuyerImportZone onImported={() => queryClient.invalidateQueries({ queryKey: ["buyers"] })} />
  <BuyerScanImportZone onImported={() => queryClient.invalidateQueries({ queryKey: ["buyers"] })} />
</div>
      

      <input
        type="text"
        placeholder="Rechercher un acheteur..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-4 w-full max-w-sm rounded-lg border border-slate-200 px-3 py-2 text-sm"
      />

      {isLoading && (
        <div className="flex justify-center py-10"><Spinner /></div>
      )}

      {buyers && buyers.length === 0 && (
        <Alert variant="info">Aucun acheteur en base — importez un fichier Excel ou ajoutez-en un manuellement.</Alert>
      )}

      {buyers && buyers.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Acheteur</th>
                <th className="px-4 py-3">Variantes</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Notes</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((b) => (
                <tr key={b.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-medium text-ink-900">{b.nom_acheteur}</td>
                  <td className="px-4 py-3 text-slate-500">{b.variantes || "—"}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleClient(b)}
                      disabled={updateMutation.isPending}
                      className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${
                        b.client_sotradies === "Oui"
                          ? "bg-teal-500/10 text-teal-600"
                          : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {b.client_sotradies === "Oui" && <BadgeCheck size={12} />}
                      {b.client_sotradies === "Oui" ? "Client existant" : "Non client"}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{b.notes || "—"}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setEditing(b)}
                      className="text-slate-400 hover:text-ink-900"
                      aria-label="Corriger"
                    >
                      <Pencil size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modale de correction (acheteur existant) */}
      <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title="Corriger l'acheteur">
        {editing && (
          <BuyerForm
            initial={editing}
            onSave={(payload) => updateMutation.mutate({ id: editing.id, payload })}
            saving={updateMutation.isPending}
            error={updateMutation.isError}
          />
        )}
      </Modal>

      {/* Modale de création (nouvel acheteur) */}
      <Modal open={creating} onClose={() => setCreating(false)} title="Ajouter un acheteur">
        <BuyerForm
          initial={{ nom_acheteur: "", variantes: "", client_sotradies: "Non", notes: "" }}
          onSave={(payload) => createMutation.mutate(payload)}
          saving={createMutation.isPending}
          error={createMutation.isError}
          errorMessage={createMutation.error?.response?.data?.detail}
          submitLabel="Ajouter"
        />
      </Modal>
    </PageWrapper>
  );
}

function BuyerForm({ initial, onSave, saving, error, errorMessage, submitLabel = "Enregistrer" }) {
  const [nom, setNom] = useState(initial.nom_acheteur);
  const [variantes, setVariantes] = useState(initial.variantes || "");
  const [clientSotradies, setClientSotradies] = useState(initial.client_sotradies || "Non");
  const [notes, setNotes] = useState(initial.notes || "");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!nom.trim()) return;
        onSave({ nom_acheteur: nom.trim(), variantes, client_sotradies: clientSotradies, notes });
      }}
      className="space-y-3"
    >
      {error && (
        <Alert variant="error">{errorMessage || "Une erreur est survenue."}</Alert>
      )}

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          Nom de l'acheteur <span className="text-rose-500">*</span>
        </label>
        <input
          required
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="ex : Commune de Sfax"
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          Variantes (séparées par ;)
        </label>
        <input
          value={variantes}
          onChange={(e) => setVariantes(e.target.value)}
          placeholder="ex : Municipalité de Sfax; Mairie de Sfax"
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Statut</label>
        <select
          value={clientSotradies}
          onChange={(e) => setClientSotradies(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        >
          <option value="Non">Non client</option>
          <option value="Oui">Client existant</option>
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
      </div>

      <button
        type="submit"
        disabled={saving}
        className="w-full rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
      >
        {saving ? "Enregistrement..." : submitLabel}
      </button>
    </form>
  );
}