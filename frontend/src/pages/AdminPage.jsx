
// src/pages/AdminPage.jsx
import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { Play, Square, Circle, Plus, Pencil, Trash2, ShieldAlert } from "lucide-react";
import Modal from "../components/ui/Modal";
import Spinner from "../components/ui/Spinner";
import Alert from "../components/ui/Alert";
import { useAuth } from "../context/AuthContext";
import { getSystemStatus, startWorker, stopWorker, startBeat, stopBeat } from "../api/adminSystem";
import { getUsers, createUser, updateUser, deleteUser } from "../api/adminUsers";

import { ScrollText } from "lucide-react";
import { getAuditLog } from "../api/audit";
import ExportButtons from "../components/ui/ExportButtons";
import { exportAuditLog } from "../api/audit";

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8 flex items-center gap-2">
        <ShieldAlert size={20} className="text-amber-500" />
        <h1 className="font-display text-2xl font-semibold text-ink-900">
          Administration technique
        </h1>
      </div>

      <SystemControlSection />
      <div className="mt-10">
        <UserManagementSection />
      </div>
      <div className="mt-10">
        <AuditLogSection />
      </div>
    </div>
  );
}

function SystemControlSection() {
  const queryClient = useQueryClient();
  const { data: status, isLoading, isError } = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus,
    refetchInterval: 5000,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["system-status"] });

  const controlError = (m) =>
    m.error?.response?.status === 409 ? m.error.response.data.detail : "Une erreur est survenue.";

  const workerStart = useMutation({ mutationFn: startWorker, onSuccess: invalidate });
  const workerStop = useMutation({ mutationFn: stopWorker, onSuccess: invalidate });
  const beatStart = useMutation({ mutationFn: startBeat, onSuccess: invalidate });
  const beatStop = useMutation({ mutationFn: stopBeat, onSuccess: invalidate });

  return (
    <section>
      <h2 className="mb-3 font-display text-base font-semibold text-ink-900">Processus système</h2>
      {isLoading && <Spinner />}
      {isError && <Alert variant="error">Impossible de récupérer le statut système.</Alert>}
      {status && (
        <div className="grid gap-4 sm:grid-cols-2">
          <ProcessCard
            title="Celery Worker" description="Scraping et scoring."
            running={status.worker.running} pid={status.worker.pid}
            onStart={() => workerStart.mutate()} onStop={() => workerStop.mutate()}
            starting={workerStart.isPending} stopping={workerStop.isPending}
            error={workerStart.isError ? controlError(workerStart) : workerStop.isError ? controlError(workerStop) : null}
          />
          <ProcessCard
            title="Celery Beat" description="Planification des cycles."
            running={status.beat.running} pid={status.beat.pid}
            onStart={() => beatStart.mutate()} onStop={() => beatStop.mutate()}
            starting={beatStart.isPending} stopping={beatStop.isPending}
            error={beatStart.isError ? controlError(beatStart) : beatStop.isError ? controlError(beatStop) : null}
          />
        </div>
      )}
    </section>
  );
}

function ProcessCard({ title, description, running, pid, onStart, onStop, starting, stopping, error }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-medium text-ink-900">{title}</h3>
          <p className="mt-0.5 text-xs text-slate-500">{description}</p>
        </div>
        <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${running ? "bg-teal-500/10 text-teal-600" : "bg-slate-100 text-slate-500"}`}>
          <Circle size={8} className={running ? "fill-teal-500 text-teal-500" : "fill-slate-400 text-slate-400"} />
          {running ? `Actif (PID ${pid})` : "Arrêté"}
        </span>
      </div>
      <div className="mt-4 flex gap-2">
        <button onClick={onStart} disabled={running || starting} className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium hover:bg-slate-50 disabled:opacity-40">
          <Play size={12} /> Démarrer
        </button>
        <button onClick={onStop} disabled={!running || stopping} className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium hover:bg-slate-50 disabled:opacity-40">
          <Square size={12} /> Arrêter
        </button>
      </div>
      {error && <div className="mt-3"><Alert variant="error">{error}</Alert></div>}
    </div>
  );
}

function UserManagementSection() {
  const { user: currentUser } = useAuth();
  const { data: users, isLoading } = useQuery({ queryKey: ["admin-users"], queryFn: getUsers });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });

  const createMutation = useMutation({ mutationFn: createUser, onSuccess: () => { invalidate(); setCreating(false); } });
  const updateMutation = useMutation({ mutationFn: ({ id, payload }) => updateUser(id, payload), onSuccess: () => { invalidate(); setEditing(null); } });
  const deleteMutation = useMutation({ mutationFn: deleteUser, onSuccess: invalidate });

  const toggleActiveMutation = useMutation({ mutationFn: ({ id, payload }) => updateUser(id, payload), onSuccess: invalidate });

  


  function handleDelete(u) {
    if (window.confirm(`Supprimer le compte de ${u.nom} (${u.email}) ?`)) deleteMutation.mutate(u.id);
  }
  function handleToggleActive(u) {
    toggleActiveMutation.mutate({ id: u.id, payload: { actif: !u.actif } });
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-base font-semibold text-ink-900">Comptes (tous profils)</h2>
        <button onClick={() => setCreating(true)} className="flex items-center gap-1.5 rounded-lg bg-ink-800 px-3 py-2 text-sm font-medium text-white hover:bg-ink-700">
          <Plus size={14} /> Ajouter un compte
        </button>
      </div>

      {deleteMutation.isError && <div className="mb-4"><Alert variant="error">{deleteMutation.error?.response?.data?.detail || "Échec."}</Alert></div>}
      {isLoading && <Spinner />}

      {users && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nom</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Profil</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-medium text-ink-900">{u.nom}</td>
                  <td className="px-4 py-3 text-slate-600">{u.email}</td>
                   <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                      u.profil === "superadmin" ? "bg-rose-500/10 text-rose-500"
                      : u.profil === "admin" ? "bg-amber-500/15 text-amber-600"
                      : "bg-slate-100 text-slate-600"}`}>
                      {u.profil}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggleActive(u)}
                      disabled={u.email === currentUser?.email || toggleActiveMutation.isPending}
                      className={`rounded-full px-2 py-1 text-xs font-medium disabled:opacity-40 ${
                        u.actif ? "bg-teal-500/10 text-teal-600" : "bg-rose-500/10 text-rose-500"
                      }`}
                    >
                      {u.actif ? "Actif" : "Désactivé"}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <button onClick={() => setEditing(u)} className="text-slate-400 hover:text-ink-900"><Pencil size={14} /></button>
                      <button onClick={() => handleDelete(u)} disabled={u.email === currentUser?.email} className="text-slate-400 hover:text-rose-500 disabled:opacity-30"><Trash2 size={14} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={creating} onClose={() => setCreating(false)} title="Ajouter un compte">
        <AdminUserForm mode="create" onSave={(p) => createMutation.mutate(p)} saving={createMutation.isPending} errorMessage={createMutation.error?.response?.data?.detail} />
      </Modal>
      <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title="Modifier le compte">
        {editing && <AdminUserForm mode="edit" initial={editing} onSave={(p) => updateMutation.mutate({ id: editing.id, payload: p })} saving={updateMutation.isPending} errorMessage={updateMutation.error?.response?.data?.detail} />}
      </Modal>
    </section>
  );
}


function AdminUserForm({ mode, initial, onSave, saving, errorMessage }) {
  const [email, setEmail] = useState(initial?.email || "");
  const [nom, setNom] = useState(initial?.nom || "");
  const [profil, setProfil] = useState(initial?.profil || "user");
  const [password, setPassword] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (mode === "create") onSave({ email, nom, password, profil });
    else {
      const payload = { nom, profil };
      if (password) payload.password = password;
      onSave(payload);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {errorMessage && <Alert variant="error">{errorMessage}</Alert>}
      {mode === "create" && (
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Email</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        </div>
      )}
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Nom complet</label>
        <input required value={nom} onChange={(e) => setNom(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Profil</label>
        <select value={profil} onChange={(e) => setProfil(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">
          <option value="user">Utilisateur</option>
          <option value="admin">Administrateur (Direction générale)</option>
          <option value="superadmin">Superadmin (équipe technique)</option>
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          {mode === "create" ? "Mot de passe" : "Nouveau mot de passe (laisser vide pour ne pas changer)"}
        </label>
        <input type="password" required={mode === "create"} value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
      </div>
      <button type="submit" disabled={saving} className="w-full rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60">
        {saving ? "Enregistrement..." : mode === "create" ? "Créer le compte" : "Enregistrer"}
      </button>
    </form>
  );
}
const ACTION_LABELS = {
  connexion: { label: "Connexion", cls: "bg-slate-100 text-slate-600" },
  consultation: { label: "Consultation", cls: "bg-ink-800/10 text-ink-800" },
  changement_statut: { label: "Changement de statut", cls: "bg-amber-500/15 text-amber-600" },
};

function AuditLogSection() {
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("Toutes");

  const { data: logs, isLoading } = useQuery({
    queryKey: ["audit-log", search, actionFilter],
    queryFn: () => getAuditLog({ utilisateur_email: search || undefined, action: actionFilter }),
  });
  const [exporting, setExporting] = useState(false);

async function handleExport(format) {
  setExporting(true);
  try {
    await exportAuditLog({ utilisateur_email: search || undefined, action: actionFilter }, format);
  } catch (err) {
    console.error("Export échoué", err);
  } finally {
    setExporting(false);
  }
}

  return (
    <section> 
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
        <ScrollText size={18} className="text-slate-500" />
        <h2 className="font-display text-base font-semibold text-ink-900">Journal d'audit</h2>
        </div>
       <ExportButtons onExport={handleExport} exporting={exporting} />
    </div>
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Filtrer par utilisateur..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-w-[220px] rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
        >
          <option value="Toutes">Toutes les actions</option>
          <option value="connexion">Connexions</option>
          <option value="consultation">Consultations</option>
          <option value="changement_statut">Changements de statut</option>
        </select>
      </div>

      {isLoading && <Spinner />}

      {logs && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Utilisateur</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Détail</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => {
                const info = ACTION_LABELS[log.action] ?? { label: log.action, cls: "bg-slate-100 text-slate-600" };
                return (
                  <tr key={log.id} className="border-t border-slate-100">
                    <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                      {new Date(log.date_action).toLocaleString("fr-FR")}
                    </td>
                    <td className="px-4 py-3 text-ink-900">{log.utilisateur_email}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-1 text-xs font-medium ${info.cls}`}>{info.label}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {log.tender_objet || log.detail || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {logs.length === 0 && (
            <p className="py-6 text-center text-sm text-slate-400">Aucune entrée pour ce filtre.</p>
          )}
        </div>
      )}
    </section>
  );
}