import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import { Play, Save, Plus, Trash2, ShieldCheck } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import Alert from "../components/ui/Alert";
import Spinner from "../components/ui/Spinner";
import Modal from "../components/ui/Modal";
import {
  getConfiguration,
  updateThresholds,
  updateCategories,
  updateExclusionKeywords,
} from "../api/adminConfig";
import {
  getCommercials,
  createCommercial,
  updateCommercial,
  deleteCommercial,
} from "../api/adminCommercials";
import {
  getSources,
  createSource,
  deleteSource,
  toggleSource,
  testSource,
} from "../api/adminSources";
import { getCompanies } from "../api/adminCompanies";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("entreprise");
  const { user } = useAuth();
  const isSuperadmin = user?.profil === "superadmin";
  const [selectedCompanyId, setSelectedCompanyId] = useState(() =>
    localStorage.getItem("settings_company_id") || user?.company_id || ""
  );
  const { data: companies = [], isLoading: companiesLoading } = useQuery({
    queryKey: ["admin-companies"],
    queryFn: getCompanies,
    enabled: Boolean(user),
  });
  useEffect(() => {
    if (isSuperadmin && !selectedCompanyId && companies[0]?.id) {
      const firstCompanyId = String(companies[0].id);
      localStorage.setItem("settings_company_id", firstCompanyId);
      // The first company is the persisted default context for superadmins.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedCompanyId(firstCompanyId);
    }
  }, [companies, isSuperadmin, selectedCompanyId]);

  const effectiveCompanyId = isSuperadmin
    ? String(selectedCompanyId || "")
    : String(user?.company_id || "");

  const { data: config, isLoading, isError } = useQuery({
    queryKey: ["admin-config", effectiveCompanyId],
    queryFn: getConfiguration,
    enabled: Boolean(effectiveCompanyId),
  });

  if (isLoading || companiesLoading) return <PageWrapper title="Configuration"><Spinner /></PageWrapper>;
  if (isError) return <PageWrapper title="Configuration"><Alert variant="error">Impossible de charger la configuration.</Alert></PageWrapper>;

  return (
    <PageWrapper
      title="Configuration"
      subtitle="Entreprise, catégories, sources, emails, alertes et sécurité."
    >
      <div className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {[
          ["entreprise", "Mon entreprise"],
          ["categories", "Catégories et mots-clés"],
          ["sources", "Sources"],
          ["commerciaux", "Commerciaux et emails"],
          ["alertes", "Alertes"],
          ["securite", "Sécurité"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveTab(id)}
            className={`rounded-lg px-3 py-2 text-sm font-medium ${
              activeTab === id
                ? "bg-ink-800 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="space-y-8">
        {config && (
          <>
            {activeTab === "entreprise" && (
              <CompanySection
                companies={companies}
                selectedCompanyId={effectiveCompanyId}
                isSuperadmin={isSuperadmin}
                onSelect={(value) => {
                  localStorage.setItem("settings_company_id", value);
                  setSelectedCompanyId(value);
                }}
              />
            )}
            {activeTab === "categories" && (
              <>
                <CategoriesSection key={`categories-${effectiveCompanyId}`} initialConfig={config} />
                <ExclusionKeywordsSection key={`exclusions-${effectiveCompanyId}`} initialConfig={config} />
              </>
            )}
            {activeTab === "sources" && <SourcesSection companyId={effectiveCompanyId} />}
            {activeTab === "commerciaux" && <CommercialsSection companyId={effectiveCompanyId} />}
            {activeTab === "alertes" && <ThresholdsSection key={`thresholds-${effectiveCompanyId}`} initialConfig={config} />}
            {activeTab === "securite" && <SecuritySection />}
          </>
        )}
      </div>
    </PageWrapper>
  );
}

// ===== THRESHOLDS SECTION =====
function ThresholdsSection({ initialConfig }) {
  const [decisionScore, setDecisionScore] = useState(initialConfig?.score_decision_threshold || 50);
  const [instantScore, setInstantScore] = useState(initialConfig?.score_instant_alert_threshold || 70);
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
            <label className="mb-2 block text-sm font-medium text-slate-700">Seuil de décision (%)</label>
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
            <label className="mb-2 block text-sm font-medium text-slate-700">Seuil d'alerte instantanée (%)</label>
            <p className="mb-2 text-xs text-slate-500">
              Score pour déclencher une alerte immédiate (au lieu du digest quotidien)
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                max="100"
                value={instantScore}
                onChange={(e) => setInstantScore(parseInt(e.target.value) || 70)}
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
  const [testTitle, setTestTitle] = useState("");
  const [testResult, setTestResult] = useState(null);
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

      <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-4">
        <h3 className="font-display text-base font-semibold text-ink-900">Tester une offre</h3>
        <p className="mt-1 text-sm text-slate-600">Vérifiez les mots-clés sans lancer le pipeline.</p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            value={testTitle}
            onChange={(event) => setTestTitle(event.target.value)}
            placeholder="Coller le titre d'un marché"
            className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => setTestResult(testCategory(testTitle, categories))}
            disabled={!testTitle.trim()}
            className="rounded-lg bg-ink-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Tester
          </button>
        </div>
        {testResult && (
          <p className="mt-3 text-sm text-slate-700">
            Résultat : <strong>{testResult.category || "Aucune catégorie"}</strong>
            {` · score ${testResult.score}% · `}
            {testResult.matches.length
              ? `mots-clés : ${testResult.matches.join(", ")}`
              : "aucun mot-clé détecté"}
          </p>
        )}
      </div>

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

function testCategory(title, categories) {
  const normalized = title.toLowerCase();
  let best = { category: null, score: 0, matches: [] };

  Object.entries(categories).forEach(([category, data]) => {
    const terms = [...(data.keywords || []), ...(data.marques || [])];
    const matches = terms.filter((term) =>
      normalized.includes(String(term).toLowerCase())
    );
    const score = Math.min(100, matches.length * 25);
    if (score > best.score) best = { category, score, matches };
  });

  return best;
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
                  <span key={m} className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">{m}</span>
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
          <button onClick={onEdit} className="text-slate-400 hover:text-ink-900">✏️</button>
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
        <input value={commercial} onChange={(e) => setCommercial(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Marques (séparées par virgule)</label>
        <input value={marques} onChange={(e) => setMarques(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Mots-clés (séparés par virgule)</label>
        <textarea value={keywords} onChange={(e) => setKeywords(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" rows="3" />
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

  const handleRemove = (kw) => setKeywords(keywords.filter((k) => k !== kw));
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
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Ajouter un mot-clé..."
        />
        <button onClick={handleAdd} className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium hover:bg-slate-200">
          <Plus size={14} />
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {keywords.map((kw) => (
          <div key={kw} className="flex items-center gap-2 rounded-full bg-rose-100 px-3 py-1.5 text-sm text-rose-700">
            <span>{kw}</span>
            <button onClick={() => handleRemove(kw)} className="hover:text-rose-900">✕</button>
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
function SourcesSection({ companyId }) {
  const queryClient = useQueryClient();
  const { data: sources, isLoading, isError } = useQuery({
    queryKey: ["admin-sources", companyId],
    queryFn: getSources,
  });
  const [showAdd, setShowAdd] = useState(false);

  const toggleMutation = useMutation({
    mutationFn: toggleSource,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-sources", companyId] }),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-sources", companyId] }),
  });
  const createMutation = useMutation({
    mutationFn: createSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-sources", companyId] });
      setShowAdd(false);
    },
  });

  const handleTest = async (source) => {
    try {
      const result = await testSource(source.id);
      window.alert(`${result.source}: ${result.offres_trouvees} offre(s) trouvée(s).`);
    } catch (error) {
      window.alert(error?.response?.data?.detail || "Le test de la source a échoué.");
    }
  };

  const handleDelete = (source) => {
    if (window.confirm(`Supprimer « ${source.nom} » de votre configuration ?`)) {
      deleteMutation.mutate(source.id);
    }
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">Sources de scraping</h2>
          <p className="mt-1 text-sm text-slate-600">Les sites enregistrés pour votre entreprise et leur abonnement.</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 rounded-lg bg-ink-800 px-3 py-2 text-sm font-medium text-white hover:bg-ink-700"
        >
          <Plus size={14} /> Ajouter un site
        </button>
      </div>

      {isError && <Alert variant="error" className="mb-4">Impossible de charger les sources.</Alert>}
      {isLoading && <Spinner />}

      <div className="space-y-3">
        {sources?.map((src) => (
          <div key={src.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-4">
            <div className="flex min-w-0 items-center gap-3">
              <input
                type="checkbox"
                checked={Boolean(src.abonne && src.actif)}
                onChange={() => toggleMutation.mutate(src.id)}
                disabled={toggleMutation.isPending}
                className="h-4 w-4"
              />
              <div className="min-w-0">
                <p className="truncate font-medium text-ink-900">{src.nom}</p>
                <p className="truncate text-xs text-slate-500">{src.url}</p>
                <p className="text-xs text-slate-500">{src.type === "universel" ? "Scraper universel" : "Connecteur dédié"}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleTest(src)}
                disabled={!src.abonne || !src.actif || deleteMutation.isPending}
                title="Tester cette source"
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:border-ink-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Play size={13} /> Tester
              </button>
              <button
                type="button"
                onClick={() => handleDelete(src)}
                disabled={deleteMutation.isPending}
                title="Supprimer cette source de votre configuration"
                className="rounded-lg border border-rose-200 p-2 text-rose-500 hover:bg-rose-50 disabled:opacity-40"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {!isLoading && !sources?.length && (
        <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">Aucun site enregistré.</p>
      )}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Ajouter un site de veille">
        <SourceForm
          onSave={(payload) => createMutation.mutate(payload)}
          saving={createMutation.isPending}
          errorMessage={createMutation.error?.response?.data?.detail}
        />
      </Modal>
    </section>
  );
}

function SourceForm({ onSave, saving, errorMessage }) {
  const [nom, setNom] = useState("");
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState(3);
  const [useBrowser, setUseBrowser] = useState(false);
  const [prive, setPrive] = useState(false);
  const [login, setLogin] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = (event) => {
    event.preventDefault();
    onSave({
      nom: nom.trim(),
      url: url.trim(),
      type: "universel",
      max_pages: Number(maxPages),
      use_browser: useBrowser,
      prive,
      login: prive ? login.trim() : null,
      mot_de_passe: prive ? motDePasse : null,
      notes: notes.trim() || null,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {errorMessage && <Alert variant="error">{errorMessage}</Alert>}
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Nom du site</label>
        <input required value={nom} onChange={(e) => setNom(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Ex: Portail fournisseur" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">URL de la liste des offres</label>
        <input required type="url" value={url} onChange={(e) => setUrl(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="https://exemple.tn/appels-offres" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Pages maximum</label>
          <input type="number" min="1" max="10" value={maxPages} onChange={(e) => setMaxPages(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        </div>
        <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-700">
          <input type="checkbox" checked={useBrowser} onChange={(e) => setUseBrowser(e.target.checked)} />
          Site JavaScript
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={prive} onChange={(e) => setPrive(e.target.checked)} />
        Site privé avec compte obligatoire
      </label>
      {prive && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Login</label>
            <input required value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Mot de passe</label>
            <input required type="password" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} autoComplete="new-password" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          </div>
        </div>
      )}
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows="2" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Notes ou sélecteurs utiles" />
      <button type="submit" disabled={saving} className="w-full rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60">
        {saving ? "Enregistrement..." : "Enregistrer et activer"}
      </button>
    </form>
  );
}


// ===== COMMERCIALS SECTION (emails) =====
function CommercialsSection({ companyId }) {
  const queryClient = useQueryClient();
  const { data: commercials, isLoading } = useQuery({
    queryKey: ["admin-commercials", companyId],
    queryFn: getCommercials,
  });

  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);

  const createMutation = useMutation({
    mutationFn: createCommercial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-commercials", companyId] });
      setShowAdd(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }) => updateCommercial(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-commercials", companyId] });
      setEditing(null);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteCommercial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-commercials", companyId] });
      queryClient.invalidateQueries({ queryKey: ["admin-config"] });
    },
  });

  const handleDelete = (commercial) => {
    if (window.confirm(`Supprimer le commercial « ${commercial.nom} » et son email ?`)) {
      deleteMutation.mutate(commercial.id);
    }
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">Commerciaux &amp; emails</h2>
          <p className="mt-1 text-sm text-slate-600">
            Emails utilisés pour les alertes commerciales de votre entreprise.
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 rounded-lg bg-ink-800 px-3 py-2 text-sm font-medium text-white hover:bg-ink-700"
        >
          <Plus size={14} /> Ajouter
        </button>
      </div>

      {isLoading && <Spinner />}

      {commercials && commercials.length === 0 && (
        <Alert variant="info">
          Aucun commercial configuré — les alertes email ne partiront pas tant que la liste est vide.
        </Alert>
      )}

      {commercials && commercials.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nom</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {commercials.map((c) => (
                <tr key={c.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-medium text-ink-900">{c.nom}</td>
                  <td className="px-4 py-3 text-slate-600">{c.email}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                      c.actif ? "bg-teal-500/10 text-teal-600" : "bg-slate-100 text-slate-500"
                    }`}>
                      {c.actif ? "Actif" : "Inactif"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-3">
                      <button onClick={() => setEditing(c)} className="text-slate-400 hover:text-ink-900" title="Modifier">
                        ✏️
                      </button>
                      <button
                        onClick={() => handleDelete(c)}
                        disabled={deleteMutation.isPending}
                        className="text-slate-400 hover:text-rose-500 disabled:opacity-40"
                        title="Supprimer"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Ajouter un commercial">
        <CommercialForm
          onSave={(payload) => createMutation.mutate(payload)}
          saving={createMutation.isPending}
          errorMessage={createMutation.error?.response?.data?.detail}
        />
      </Modal>

      <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title="Modifier le commercial">
        {editing && (
          <CommercialForm
            initial={editing}
            onSave={(payload) => updateMutation.mutate({ id: editing.id, payload })}
            saving={updateMutation.isPending}
            errorMessage={updateMutation.error?.response?.data?.detail}
          />
        )}
      </Modal>
    </section>
  );
}

function CommercialForm({ initial, onSave, saving, errorMessage }) {
  const [nom, setNom] = useState(initial?.nom || "");
  const [email, setEmail] = useState(initial?.email || "");
  const [actif, setActif] = useState(initial?.actif ?? true);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!nom.trim() || !email.trim()) return;
    onSave({ nom: nom.trim(), email: email.trim(), actif });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {errorMessage && <Alert variant="error">{errorMessage}</Alert>}
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Nom complet</label>
        <input
          required
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Ex: Ramzi Trabelsi"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Email</label>
        <input
          required
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="ramzi@sotradies.tn"
        />
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={actif} onChange={(e) => setActif(e.target.checked)} />
        Actif
      </label>
      <button
        type="submit"
        disabled={saving}
        className="w-full rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
      >
        {saving ? "Enregistrement..." : "Enregistrer"}
      </button>
    </form>
  );
}

function SecuritySection() {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex items-start gap-3">
        <ShieldCheck className="text-teal-600" size={20} />
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">Sécurité</h2>
          <p className="mt-1 text-sm text-slate-600">
            La gestion des rôles et de l'authentification est contrôlée par les comptes administrateurs.
          </p>
          <p className="mt-4 text-sm text-slate-700">
            Les données, marchés, sources et emails sont isolés par entreprise côté API.
          </p>
        </div>
      </div>
    </section>
  );
}

function CompanySection({ companies, selectedCompanyId, isSuperadmin, onSelect }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="font-display text-lg font-semibold text-ink-900">Mon entreprise</h2>
      <p className="mt-1 text-sm text-slate-600">
        {isSuperadmin
          ? "Sélectionnez une entreprise pour consulter ses catégories, sources, commerciaux et alertes."
          : "Votre entreprise et son périmètre de veille."}
      </p>
      <div className="mt-6 divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200">
        {companies.map((company) => {
          const isSelected = String(company.id) === selectedCompanyId;
          return (
            <button
              key={company.id}
              type="button"
              onClick={() => onSelect(String(company.id))}
              className={`block w-full p-5 text-left transition ${
                isSelected
                  ? "bg-ink-50 ring-2 ring-inset ring-ink-800"
                  : "bg-white hover:bg-slate-50"
              }`}
            >
              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="text-base font-semibold text-ink-900">{company.nom}</h3>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                    {company.description || "Aucune description d'activité renseignée."}
                  </p>
                </div>
                {isSelected && (
                  <span className="shrink-0 rounded-full bg-ink-800 px-3 py-1 text-xs font-medium text-white">
                    Sélectionnée
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}