import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Save, Plus, Trash2 } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import Alert from "../components/ui/Alert";
import Spinner from "../components/ui/Spinner";
import Modal from "../components/ui/Modal";
import {
  getConfiguration,
  updateThresholds,
  updateCategories,
  updateExclusionKeywords,
  updateSources,
  updateAssignmentRules,
} from "../api/adminConfig";

const SOURCES = [
  { id: "tuneps", label: "TUNEPS" },
  { id: "tunisie_appel_offre", label: "Tunisie Appel d'Offre" },
  { id: "observatoire_national", label: "Observatoire National des Appels d'Offres" },
];

export default function SettingsPage() {
  const { data: config, isLoading, isError } = useQuery({
    queryKey: ["admin-config"],
    queryFn: getConfiguration,
  });

  if (isLoading) return <PageWrapper title="Configuration"><Spinner /></PageWrapper>;
  if (isError) return <PageWrapper title="Configuration"><Alert variant="error">Impossible de charger la configuration.</Alert></PageWrapper>;

  return (
    <PageWrapper
      title="Configuration"
      subtitle="Mots-clés, seuils de score, sources actives, assignation commerciale."
    >
      <div className="space-y-8">
        {config && (
          <>
            <ThresholdsSection initialConfig={config} />
            <CategoriesSection initialConfig={config} />
            <ExclusionKeywordsSection initialConfig={config} />
            <SourcesSection initialConfig={config} />
            <AssignmentSection initialConfig={config} />
          </>
        )}
      </div>
    </PageWrapper>
  );
}

// ===== THRESHOLDS SECTION =====
function ThresholdsSection({ initialConfig }) {
  const [decisionScore, setDecisionScore] = useState(initialConfig?.score_decision_threshold || 50);
  const [instantScore, setInstantScore] = useState(initialConfig?.score_instant_alert_threshold || 80);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => updateThresholds(decisionScore, instantScore),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-config"] }),
  });

  const handleSave = (e) => {
    e.preventDefault();
    if (decisionScore < 0 || decisionScore > 100 || instantScore < 0 || instantScore > 100) {
      alert("Les scores doivent être entre 0 et 100");
      return;
    }
    if (instantScore < decisionScore) {
      alert("Le seuil d'alerte instantanée doit être >= au seuil de décision");
      return;
    }
    mutation.mutate();
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="mb-4 font-display text-lg font-semibold text-ink-900">Seuils de pertinence</h2>
      <p className="mb-6 text-sm text-slate-600">
        Définissez les seuils de score pour la classification des marchés.
      </p>

      {mutation.isError && <Alert variant="error" className="mb-4">{mutation.error?.response?.data?.detail}</Alert>}

      <form onSubmit={handleSave} className="space-y-5">
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Seuil de décision (%)
            </label>
            <p className="mb-2 text-xs text-slate-500">
              Score minimum pour qu'un marché soit "retenu" et passe au traitement suivant
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                max="100"
                value={decisionScore}
                onChange={(e) => setDecisionScore(parseInt(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <span className="text-sm font-semibold text-ink-900">{decisionScore}%</span>
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Seuil d'alerte instantanée (%)
            </label>
            <p className="mb-2 text-xs text-slate-500">
              Score pour déclencher une alerte immédiate (au lieu du digest quotidien)
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                max="100"
                value={instantScore}
                onChange={(e) => setInstantScore(parseInt(e.target.value) || 80)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <span className="text-sm font-semibold text-ink-900">{instantScore}%</span>
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
        >
          <Save size={14} /> {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
        </button>
      </form>
    </section>
  );
}

// ===== CATEGORIES SECTION =====
function CategoriesSection({ initialConfig }) {
  const [categories, setCategories] = useState(initialConfig?.categories || {});
  const [editingCategory, setEditingCategory] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => updateCategories(categories),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-config"] }),
  });

  const handleAddCategory = (newCat) => {
    setCategories({ ...categories, [newCat.id]: newCat });
    setShowAddModal(false);
  };

  const handleEditCategory = (id, updated) => {
    setCategories({ ...categories, [id]: updated });
    setEditingCategory(null);
  };

  const handleDeleteCategory = (id) => {
    if (window.confirm(`Supprimer la catégorie ${id} ?`)) {
      const newCats = { ...categories };
      delete newCats[id];
      setCategories(newCats);
    }
  };

  const handleSave = () => mutation.mutate();

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">Catégories & Mots-clés</h2>
          <p className="mt-1 text-sm text-slate-600">Gérez les catégories et leurs mots-clés de détection.</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1.5 rounded-lg bg-ink-800 px-3 py-2 text-sm font-medium text-white hover:bg-ink-700"
        >
          <Plus size={14} /> Ajouter
        </button>
      </div>

      {mutation.isError && <Alert variant="error" className="mb-4">{mutation.error?.response?.data?.detail}</Alert>}

      <div className="space-y-3">
        {Object.entries(categories).map(([catId, catData]) => (
          <CategoryCard
            key={catId}
            id={catId}
            data={catData}
            onEdit={() => setEditingCategory(catId)}
            onDelete={() => handleDeleteCategory(catId)}
          />
        ))}
      </div>

      <button
        onClick={handleSave}
        disabled={mutation.isPending}
        className="mt-6 flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
      >
        <Save size={14} /> {mutation.isPending ? "Enregistrement..." : "Enregistrer les changements"}
      </button>

      {/* Modals */}
      <Modal open={showAddModal} onClose={() => setShowAddModal(false)} title="Ajouter une catégorie">
        <AddCategoryForm onSave={handleAddCategory} />
      </Modal>

      <Modal open={Boolean(editingCategory)} onClose={() => setEditingCategory(null)} title="Modifier la catégorie">
        {editingCategory && (
          <EditCategoryForm
            id={editingCategory}
            data={categories[editingCategory]}
            onSave={(updated) => handleEditCategory(editingCategory, updated)}
          />
        )}
      </Modal>
    </section>
  );
}

function CategoryCard({ id, data, onEdit, onDelete }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-semibold text-ink-900">{id}</h3>
          <p className="mt-1 text-sm text-slate-600">
            Commercial: <span className="font-medium">{data.commercial || "Non assigné"}</span>
          </p>
          {data.marques?.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium text-slate-600 uppercase">Marques:</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {data.marques.map((m) => (
                  <span key={m} className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}
          {data.keywords?.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium text-slate-600 uppercase">Mots-clés ({data.keywords.length}):</p>
              <p className="mt-1 text-xs text-slate-600">{data.keywords.slice(0, 3).join(", ")}...</p>
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={onEdit} className="text-slate-400 hover:text-ink-900">
            ✏️
          </button>
          <button onClick={onDelete} className="text-slate-400 hover:text-rose-500">
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function AddCategoryForm({ onSave }) {
  const [id, setId] = useState("");
  const [commercial, setCommercial] = useState("");
  const [marques, setMarques] = useState("");
  const [keywords, setKeywords] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      id,
      commercial: commercial || null,
      marques: marques.split(",").map((m) => m.trim()).filter(Boolean),
      keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">ID Catégorie (ex: MATERIEL_ROULANT)</label>
        <input
          required
          value={id}
          onChange={(e) => setId(e.target.value.toUpperCase())}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="CATEGORIE_NOM"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Commercial assigné</label>
        <input
          value={commercial}
          onChange={(e) => setCommercial(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Ex: Ramzi Trabelsi"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Marques (séparées par virgule)</label>
        <input
          value={marques}
          onChange={(e) => setMarques(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="IVECO, Otokar, CASE"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Mots-clés (séparés par virgule)</label>
        <textarea
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="camion, camionnette, poids lourd"
          rows="3"
        />
      </div>
      <button type="submit" className="w-full rounded-lg bg-ink-800 px-4 py-2 text-sm font-medium text-white hover:bg-ink-700">
        Ajouter
      </button>
    </form>
  );
}

function EditCategoryForm({ id, data, onSave }) {
  const [commercial, setCommercial] = useState(data.commercial || "");
  const [marques, setMarques] = useState(data.marques?.join(", ") || "");
  const [keywords, setKeywords] = useState(data.keywords?.join(", ") || "");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      commercial: commercial || null,
      marques: marques.split(",").map((m) => m.trim()).filter(Boolean),
      keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="rounded-lg bg-slate-50 p-3">
        <p className="text-sm font-medium text-slate-700">Catégorie: <span className="font-bold">{id}</span></p>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Commercial assigné</label>
        <input
          value={commercial}
          onChange={(e) => setCommercial(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Marques (séparées par virgule)</label>
        <input
          value={marques}
          onChange={(e) => setMarques(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Mots-clés (séparés par virgule)</label>
        <textarea
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          rows="3"
        />
      </div>
      <button type="submit" className="w-full rounded-lg bg-ink-800 px-4 py-2 text-sm font-medium text-white hover:bg-ink-700">
        Enregistrer
      </button>
    </form>
  );
}

// ===== EXCLUSION KEYWORDS SECTION =====
function ExclusionKeywordsSection({ initialConfig }) {
  const [keywords, setKeywords] = useState(initialConfig?.exclusion_keywords || []);
  const [newKeyword, setNewKeyword] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => updateExclusionKeywords(keywords),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-config"] }),
  });

  const handleAdd = () => {
    if (newKeyword.trim() && !keywords.includes(newKeyword.trim())) {
      setKeywords([...keywords, newKeyword.trim().toLowerCase()]);
      setNewKeyword("");
    }
  };

  const handleRemove = (kw) => {
    setKeywords(keywords.filter((k) => k !== kw));
  };

  const handleSave = () => mutation.mutate();

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="mb-4 font-display text-lg font-semibold text-ink-900">Mots-clés d'exclusion</h2>
      <p className="mb-4 text-sm text-slate-600">
        Ces mots-clés éliminent automatiquement un marché, indépendamment de la catégorie.
      </p>

      {mutation.isError && <Alert variant="error" className="mb-4">{mutation.error?.response?.data?.detail}</Alert>}

      <div className="mb-4 flex gap-2">
        <input
          type="text"
          value={newKeyword}
          onChange={(e) => setNewKeyword(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && handleAdd()}
          className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Ajouter un mot-clé..."
        />
        <button
          onClick={handleAdd}
          className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium hover:bg-slate-200"
        >
          <Plus size={14} />
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {keywords.map((kw) => (
          <div
            key={kw}
            className="flex items-center gap-2 rounded-full bg-rose-100 px-3 py-1.5 text-sm text-rose-700"
          >
            <span>{kw}</span>
            <button onClick={() => handleRemove(kw)} className="hover:text-rose-900">
              ✕
            </button>
          </div>
        ))}
      </div>

      <button
        onClick={handleSave}
        disabled={mutation.isPending}
        className="mt-4 flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
      >
        <Save size={14} /> {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
      </button>
    </section>
  );
}

// ===== SOURCES SECTION =====
function SourcesSection({ initialConfig }) {
  const [sources, setSources] = useState(
    initialConfig?.active_sources || SOURCES.reduce((acc, s) => ({ ...acc, [s.id]: { actif: true, frequence: "daily" } }), {})
  );
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => updateSources(sources),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-config"] }),
  });

  const handleToggleSource = (sourceId) => {
    setSources({
      ...sources,
      [sourceId]: { ...sources[sourceId], actif: !sources[sourceId]?.actif },
    });
  };

  const handleChangeFrequence = (sourceId, freq) => {
    setSources({
      ...sources,
      [sourceId]: { ...sources[sourceId], frequence: freq },
    });
  };

  const handleSave = () => mutation.mutate();

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="mb-4 font-display text-lg font-semibold text-ink-900">Sources de scraping</h2>
      <p className="mb-6 text-sm text-slate-600">Activez/désactivez les sources et définissez leur fréquence.</p>

      {mutation.isError && <Alert variant="error" className="mb-4">{mutation.error?.response?.data?.detail}</Alert>}

      <div className="space-y-3">
        {SOURCES.map((src) => (
          <div key={src.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={sources[src.id]?.actif || false}
                onChange={() => handleToggleSource(src.id)}
                className="h-4 w-4"
              />
              <label className="font-medium text-ink-900">{src.label}</label>
            </div>
            {sources[src.id]?.actif && (
              <select
                value={sources[src.id]?.frequence || "daily"}
                onChange={(e) => handleChangeFrequence(src.id, e.target.value)}
                className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
              >
                <option value="daily">Quotidien</option>
                <option value="weekly">Hebdomadaire</option>
                <option value="realtime">Temps réel</option>
              </select>
            )}
          </div>
        ))}
      </div>

      <button
        onClick={handleSave}
        disabled={mutation.isPending}
        className="mt-6 flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
      >
        <Save size={14} /> {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
      </button>
    </section>
  );
}

// ===== ASSIGNMENT SECTION =====
function AssignmentSection({ initialConfig }) {
  const [rules, setRules] = useState(initialConfig?.assignment_rules || {});
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => updateAssignmentRules(rules),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-config"] }),
  });

  const handleUpdateRule = (categoryId, commercials) => {
    setRules({
      ...rules,
      [categoryId]: commercials.filter(Boolean),
    });
  };

  const handleSave = () => mutation.mutate();

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="mb-4 font-display text-lg font-semibold text-ink-900">Assignation commerciale</h2>
      <p className="mb-6 text-sm text-slate-600">Définissez qui reçoit les alertes pour chaque catégorie.</p>

      {mutation.isError && <Alert variant="error" className="mb-4">{mutation.error?.response?.data?.detail}</Alert>}

      <div className="space-y-4">
        {Object.keys(initialConfig?.categories || {}).map((catId) => (
          <div key={catId} className="rounded-lg border border-slate-200 p-4">
            <label className="mb-3 block text-sm font-semibold text-ink-900">{catId}</label>
            <input
              type="text"
              value={rules[catId]?.join(", ") || ""}
              onChange={(e) =>
                handleUpdateRule(
                  catId,
                  e.target.value.split(",").map((c) => c.trim())
                )
              }
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Commercial 1, Commercial 2"
            />
            <p className="mt-2 text-xs text-slate-500">Séparez par des virgules</p>
          </div>
        ))}
      </div>

      <button
        onClick={handleSave}
        disabled={mutation.isPending}
        className="mt-6 flex items-center gap-2 rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
      >
        <Save size={14} /> {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
      </button>
    </section>
  );
}