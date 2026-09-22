import { useState } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import {
  Sparkles, Check, RotateCcw, AlertTriangle, Globe,
  Trash2, Building2, Target, ChevronRight, ChevronLeft,
  Users, Search,
} from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import Alert from "../components/ui/Alert";
import Spinner from "../components/ui/Spinner";
import apiClient from "../api/client";
import { suggestConfiguration } from "../api/adminAiSuggest";
import { getSources } from "../api/adminSources";
import {
  getConfiguration,
  updateCategories,
  updateExclusionKeywords,
  updateAssignmentRules,
} from "../api/adminConfig";

const STEPS = [
  { id: 1, label: "Entreprise", icon: Building2 },
  { id: 2, label: "Activité", icon: Target },
  { id: 3, label: "Équipe & Objectifs", icon: Users },
  { id: 4, label: "Génération IA", icon: Sparkles },
  { id: 5, label: "Validation", icon: Check },
];

export default function AiOnboardingPage() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    nom_entreprise: "",
    email: "",
    telephone: "",
    region: "",
    ville: "",
    description_activite: "",
    marques: "",
    clients_cibles: "",
    types_offres: "",
    concurrents: "",
    sites_connus: "",
  });
  const [commerciaux, setCommerciaux] = useState([{ nom: "", email: "" }]);
  const [suggestion, setSuggestion] = useState(null);
  const [applied, setApplied] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const queryClient = useQueryClient();

  const { data: currentConfig } = useQuery({
    queryKey: ["admin-config"],
    queryFn: getConfiguration,
  });

  const { data: sources, isLoading: sourcesLoading } = useQuery({
    queryKey: ["admin-sources"],
    queryFn: getSources,
  });

  const updateField = (field, value) => {
    setFormData({ ...formData, [field]: value });
  };

  const validCommerciaux = commerciaux.filter(
    (c) => c.nom.trim() && c.email.trim()
  );

  const unassignedCount = suggestion
    ? suggestion.categories.filter((c) => !c.commercial).length
    : 0;

  const totalKeywords = suggestion
    ? suggestion.categories.reduce((sum, cat) => sum + cat.keywords.length, 0)
    : 0;

  const buildAiDescription = () => {
    const parts = [];
    if (formData.description_activite)
      parts.push(`Activité : ${formData.description_activite}`);
    if (formData.marques)
      parts.push(`Marques principales : ${formData.marques}`);
    if (formData.clients_cibles)
      parts.push(`Clients cibles : ${formData.clients_cibles}`);
    if (formData.types_offres)
      parts.push(`Types d'offres recherchées : ${formData.types_offres}`);
    if (formData.concurrents)
      parts.push(`Concurrents connus : ${formData.concurrents}`);
    if (formData.region)
      parts.push(`Région principale : ${formData.region}`);
    if (formData.sites_connus)
      parts.push(`Sites déjà consultés : ${formData.sites_connus}`);
    return parts.join("\n");
  };

  const suggestMutation = useMutation({
    mutationFn: () => suggestConfiguration(buildAiDescription()),
    onSuccess: (data) => {
      // Si un seul commercial, l'assigner à toutes les catégories
      const defaultCommercial =
        validCommerciaux.length === 1 ? validCommerciaux[0].nom : null;

      const catsWithCommercial = data.categories.map((cat) => ({
        ...cat,
        commercial: defaultCommercial,
      }));
      setSuggestion({ ...data, categories: catsWithCommercial });
      setStep(5);
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      // 1. Créer les commerciaux
      for (const c of validCommerciaux) {
        try {
          await apiClient.post("/admin/commercials", {
            nom: c.nom.trim(),
            email: c.email.trim(),
            actif: true,
          });
        } catch {
          console.warn("Commercial existant :", c.nom);
        }
      }

      // 2. Fusionner les catégories
      const currentCats = currentConfig?.categories || {};
      const newCats = { ...currentCats };

      for (const cat of suggestion.categories) {
        if (!newCats[cat.id]) {
          newCats[cat.id] = {
            commercial: cat.commercial || null,
            keywords: cat.keywords,
            marques: cat.marques,
          };
        } else {
          if (cat.commercial) {
            newCats[cat.id].commercial = cat.commercial;
          }
          const existing = newCats[cat.id].keywords || [];
          for (const kw of cat.keywords) {
            if (!existing.includes(kw)) existing.push(kw);
          }
          newCats[cat.id].keywords = existing;

          const existingBrands = newCats[cat.id].marques || [];
          for (const m of cat.marques) {
            if (!existingBrands.includes(m)) existingBrands.push(m);
          }
          newCats[cat.id].marques = existingBrands;
        }
      }

      // 3. Fusionner les exclusions
      const currentExcl = currentConfig?.exclusion_keywords || [];
      const newExcl = [...currentExcl];
      for (const kw of suggestion.exclusion_keywords) {
        if (!newExcl.includes(kw)) newExcl.push(kw);
      }

      // 4. Construire les règles d'assignation
      const currentRules = currentConfig?.assignment_rules || {};
      const newRules = { ...currentRules };
      for (const cat of suggestion.categories) {
        if (cat.commercial) {
          newRules[cat.id] = [cat.commercial];
        }
      }

      // 5. Sauvegarder tout
      await updateCategories(newCats);
      await updateExclusionKeywords(newExcl);
      await updateAssignmentRules(newRules);

      // 6. Enregistrer les sites
      if (suggestion.sites?.length > 0) {
        for (const site of suggestion.sites) {
          try {
            await apiClient.post("/admin/sources", {
              nom: site.nom,
              url: site.url,
              notes: site.description,
            });
          } catch {
            console.warn("Site existant :", site.nom);
          }
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-config"] });
      queryClient.invalidateQueries({ queryKey: ["admin-sources"] });
      queryClient.invalidateQueries({ queryKey: ["admin-commercials"] });
      setApplied(true);
    },
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      const keywords = suggestion.categories.flatMap((c) => c.keywords);
      const r = await apiClient.get("/tenders", {
        params: { search: keywords.slice(0, 3).join(" "), include_rejected: true },
      });
      return r.data;
    },
    onSuccess: (data) => setTestResult(data),
  });

  return (
    <PageWrapper
      title="Onboarding Client"
      subtitle="Configurez la veille pour un nouveau client en quelques minutes."
    >
      <div className="mx-auto max-w-3xl">

        {/* Barre de progression */}
        {!applied && (
          <div className="mb-8 flex items-center justify-between">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              const isActive = s.id === step;
              const isDone = s.id < step;
              return (
                <div key={s.id} className="flex items-center">
                  <div className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                    isActive ? "bg-amber-500 text-white" :
                    isDone ? "bg-teal-500 text-white" :
                    "bg-slate-100 text-slate-400"
                  }`}>
                    {isDone ? <Check size={14} /> : <Icon size={14} />}
                    <span className="hidden sm:inline">{s.label}</span>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div className={`mx-2 h-0.5 w-8 ${isDone ? "bg-teal-500" : "bg-slate-200"}`} />
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ========== ÉTAPE 1 — ENTREPRISE ========== */}
        {step === 1 && (
          <StepCard
            title="Informations de l'entreprise"
            subtitle="Ces informations identifient le client."
            icon={<Building2 size={20} className="text-amber-500" />}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nom de l'entreprise *" placeholder="Ex: CoolAir SARL"
                value={formData.nom_entreprise} onChange={(v) => updateField("nom_entreprise", v)} />
              <Field label="Email *" type="email" placeholder="contact@coolair.tn"
                value={formData.email} onChange={(v) => updateField("email", v)} />
              <Field label="Téléphone" placeholder="+216 XX XXX XXX"
                value={formData.telephone} onChange={(v) => updateField("telephone", v)} />
              <Field label="Région" placeholder="Ex: Grand Tunis, Sfax..."
                value={formData.region} onChange={(v) => updateField("region", v)} />
              <Field label="Ville" placeholder="Ex: Sfax"
                value={formData.ville} onChange={(v) => updateField("ville", v)} />
            </div>
            <StepButtons onNext={() => setStep(2)}
              nextDisabled={!formData.nom_entreprise || !formData.email} />
          </StepCard>
        )}

        {/* ========== ÉTAPE 2 — ACTIVITÉ ========== */}
        {step === 2 && (
          <StepCard
            title="Décrivez votre activité"
            subtitle="Plus c'est détaillé, meilleure sera la configuration."
            icon={<Target size={20} className="text-amber-500" />}
          >
            <TextArea label="Que vendez-vous ou installez-vous ? *"
              placeholder="Ex: Climatiseurs, pompes à chaleur et VMC."
              value={formData.description_activite}
              onChange={(v) => updateField("description_activite", v)} rows={4} />
            <TextArea label="Marques principales ?"
              placeholder="Ex: Daikin, LG, Carrier"
              value={formData.marques}
              onChange={(v) => updateField("marques", v)} rows={2} />
            <TextArea label="Clients cibles ?"
              placeholder="Ex: Hôpitaux, écoles, administrations"
              value={formData.clients_cibles}
              onChange={(v) => updateField("clients_cibles", v)} rows={2} />
            <StepButtons onPrev={() => setStep(1)} onNext={() => setStep(3)}
              nextDisabled={!formData.description_activite} />
          </StepCard>
        )}

        {/* ========== ÉTAPE 3 — ÉQUIPE + OBJECTIFS ========== */}
        {step === 3 && (
          <StepCard
            title="Équipe commerciale et objectifs"
            subtitle="Définissez qui recevra les alertes et ce que vous cherchez."
            icon={<Users size={20} className="text-amber-500" />}
          >
            {/* Commerciaux */}
            <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
              <label className="mb-2 block text-sm font-semibold text-ink-900">
                Commerciaux qui recevront les alertes *
              </label>
              <p className="mb-3 text-xs text-slate-500">
                Ajoutez les personnes qui recevront les emails. Vous pourrez les
                assigner aux catégories à l'étape suivante.
              </p>
              <div className="space-y-2">
                {commerciaux.map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input value={c.nom}
                      onChange={(e) => {
                        const u = [...commerciaux]; u[i] = { ...c, nom: e.target.value }; setCommerciaux(u);
                      }}
                      placeholder="Nom complet"
                      className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm" />
                    <input value={c.email}
                      onChange={(e) => {
                        const u = [...commerciaux]; u[i] = { ...c, email: e.target.value }; setCommerciaux(u);
                      }}
                      placeholder="email@entreprise.tn" type="email"
                      className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm" />
                    {commerciaux.length > 1 && (
                      <button onClick={() => setCommerciaux(commerciaux.filter((_, idx) => idx !== i))}
                        className="text-rose-400 hover:text-rose-600">×</button>
                    )}
                  </div>
                ))}
              </div>
              <button onClick={() => setCommerciaux([...commerciaux, { nom: "", email: "" }])}
                className="mt-2 text-xs font-medium text-amber-600 hover:underline">
                + Ajouter un commercial
              </button>
            </div>

            <TextArea label="Types d'offres recherchées *"
              placeholder="Ex: Fourniture et installation de climatisation, maintenance CVC"
              value={formData.types_offres}
              onChange={(v) => updateField("types_offres", v)} rows={4} />
            <TextArea label="Concurrents connus ?"
              placeholder="Ex: FroidExpress, DirectClim"
              value={formData.concurrents}
              onChange={(v) => updateField("concurrents", v)} rows={2} />
            <TextArea label="Sites déjà consultés ?"
              placeholder="Ex: marchespublics.gov.tn, tuneps.tn"
              value={formData.sites_connus}
              onChange={(v) => updateField("sites_connus", v)} rows={2} />

            <StepButtons onPrev={() => setStep(2)}
              onNext={() => { setStep(4); suggestMutation.mutate(); }}
              nextLabel="Générer la configuration" nextIcon={<Sparkles size={14} />}
              nextDisabled={!formData.types_offres || validCommerciaux.length === 0} />
          </StepCard>
        )}

        {/* ========== ÉTAPE 4 — GÉNÉRATION ========== */}
        {step === 4 && suggestMutation.isPending && (
          <StepCard title="Génération en cours..."
            icon={<Sparkles size={20} className="animate-pulse text-amber-500" />}>
            <div className="flex flex-col items-center py-12">
              <Spinner className="h-10 w-10 text-amber-500" />
              <p className="mt-4 text-sm text-slate-500">
                Analyse de l'activité, génération des mots-clés et recherche des sites...
              </p>
            </div>
          </StepCard>
        )}

        {step === 4 && suggestMutation.isError && (
          <StepCard title="Erreur" icon={<AlertTriangle size={20} className="text-rose-500" />}>
            <Alert variant="error">
              {suggestMutation.error?.response?.data?.detail ||
               suggestMutation.error?.message || "Erreur inconnue"}
            </Alert>
            <StepButtons onPrev={() => setStep(3)}
              onNext={() => suggestMutation.mutate()} nextLabel="Réessayer" />
          </StepCard>
        )}

        {/* ========== ÉTAPE 5 — VALIDATION ÉDITABLE ========== */}
        {step === 5 && suggestion && !applied && (
          <section className="space-y-6">
            {/* Résumé client */}
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-3">
                <Building2 size={18} className="text-slate-400" />
                <div>
                  <p className="font-semibold text-ink-900">{formData.nom_entreprise}</p>
                  <p className="text-xs text-slate-500">
                    {formData.email} · {formData.region || "Tunisie"} · {validCommerciaux.length} commercial(s)
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border-2 border-amber-300 bg-amber-50/30 p-6">
              <h2 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold text-ink-900">
                <Sparkles size={18} className="text-amber-500" />
                Configuration — modifiez et assignez les commerciaux
              </h2>

              {suggestion.warnings?.length > 0 && (
                <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
                  {suggestion.warnings.map((w, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-amber-700">
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Bouton "Assigner à tous" */}
              {validCommerciaux.length > 0 && (
                <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3">
                  <span className="text-xs font-medium text-slate-500">Assigner à toutes les catégories :</span>
                  {validCommerciaux.map((c) => (
                    <button key={c.nom}
                      onClick={() => {
                        const updated = suggestion.categories.map((cat) => ({ ...cat, commercial: c.nom }));
                        setSuggestion({ ...suggestion, categories: updated });
                      }}
                      className="rounded-full bg-ink-800 px-3 py-1 text-xs font-medium text-white hover:bg-ink-700">
                      {c.nom}
                    </button>
                  ))}
                </div>
              )}

              {/* Catégories éditables */}
              <div className="mb-6">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-ink-900">
                    Catégories ({suggestion.categories.length})
                  </h3>
                  <button onClick={() => {
                    const id = prompt("ID catégorie (ex: PLOMBERIE)");
                    if (!id) return;
                    const label = prompt("Nom lisible") || id;
                    setSuggestion({ ...suggestion, categories: [...suggestion.categories,
                      { id: id.toUpperCase().replace(/\s/g, "_"), label, keywords: [], marques: [], commercial: null }] });
                  }} className="text-xs font-medium text-amber-600 hover:underline">+ Ajouter</button>
                </div>
                <div className="space-y-4">
                  {suggestion.categories.map((cat, ci) => (
                    <EditableCategory key={ci} cat={cat} commerciaux={validCommerciaux}
                      onUpdate={(updated) => {
                        const cats = [...suggestion.categories]; cats[ci] = updated;
                        setSuggestion({ ...suggestion, categories: cats });
                      }}
                      onDelete={() => setSuggestion({ ...suggestion,
                        categories: suggestion.categories.filter((_, i) => i !== ci) })} />
                  ))}
                </div>
              </div>

              {/* Exclusions */}
              <EditableTags title="Exclusions" tags={suggestion.exclusion_keywords} color="rose"
                onUpdate={(tags) => setSuggestion({ ...suggestion, exclusion_keywords: tags })} />

              {/* Sites */}
              {suggestion.sites?.length > 0 && (
                <div className="mb-6">
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-900">
                    <Globe size={16} /> Sites ({suggestion.sites.length})
                  </h3>
                  <div className="space-y-2">
                    {suggestion.sites.map((site, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3">
                        <div>
                          <p className="font-medium text-ink-900">{site.nom}</p>
                          <a href={site.url} target="_blank" rel="noreferrer"
                            className="text-xs text-blue-600 hover:underline">{site.url}</a>
                        </div>
                        <button onClick={() => setSuggestion({ ...suggestion,
                          sites: suggestion.sites.filter((_, idx) => idx !== i) })}
                          className="text-slate-400 hover:text-rose-500"><Trash2 size={14} /></button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Résumé */}
              <div className="mb-4 rounded-lg bg-slate-50 p-4">
                <h3 className="mb-2 text-sm font-semibold text-ink-900">Résumé de la configuration</h3>
                <div className="grid grid-cols-3 gap-2 text-xs text-slate-600">
                  <div>Catégories : <b>{suggestion.categories.length}</b></div>
                  <div>Mots-clés : <b>{totalKeywords}</b></div>
                  <div>Sites : <b>{suggestion.sites?.length || 0}</b></div>
                  <div>Commerciaux : <b>{validCommerciaux.length}</b></div>
                  <div>Exclusions : <b>{suggestion.exclusion_keywords.length}</b></div>
                  <div>
                    Non assignés : <b className={unassignedCount > 0 ? "text-rose-500" : "text-teal-600"}>
                      {unassignedCount}
                    </b>
                  </div>
                </div>
              </div>

              {/* Avertissement si non assigné */}
              {unassignedCount > 0 && (
                <Alert variant="info" className="mb-4">
                  ⚠️ {unassignedCount} catégorie(s) sans commercial. Les alertes ne partiront pas pour ces catégories.
                </Alert>
              )}

              {/* Test sur marchés existants */}
              {testResult && (
                <div className="mb-4 rounded-lg border border-teal-200 bg-teal-50 p-3">
                  <p className="text-sm font-medium text-teal-800">
                    🔍 {testResult.length} marché(s) existant(s) correspondent à vos mots-clés
                  </p>
                  {testResult.slice(0, 3).map((t, i) => (
                    <p key={i} className="mt-1 text-xs text-teal-600">• {t.objet?.slice(0, 60)}</p>
                  ))}
                </div>
              )}

              {/* Boutons */}
              <div className="flex flex-wrap gap-3">
                <button onClick={() => applyMutation.mutate()}
                  disabled={applyMutation.isPending || suggestion.categories.every((c) => !c.commercial)}
                  className="flex items-center gap-2 rounded-lg bg-ink-800 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60">
                  {applyMutation.isPending
                    ? <><Spinner className="h-4 w-4" /> Application...</>
                    : <><Check size={16} /> Valider et activer la veille</>}
                </button>
                <button onClick={() => testMutation.mutate()} disabled={testMutation.isPending}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-ink-900 hover:bg-slate-50">
                  <Search size={14} /> {testMutation.isPending ? "Test..." : "Tester sur les marchés"}
                </button>
                <button onClick={() => suggestMutation.mutate()} disabled={suggestMutation.isPending}
                  className="flex items-center gap-2 rounded-lg border border-amber-300 px-4 py-2.5 text-sm font-medium text-amber-700 hover:bg-amber-50">
                  <Sparkles size={14} /> Regénérer
                </button>
                <button onClick={() => { setStep(3); setSuggestion(null); setTestResult(null); }}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-ink-900 hover:bg-slate-50">
                  <RotateCcw size={14} /> Modifier les infos
                </button>
              </div>

              {applyMutation.isError && <Alert variant="error" className="mt-4">Erreur. Réessayez.</Alert>}
            </div>
          </section>
        )}

        {/* ========== CONFIRMATION ========== */}
        {applied && (
          <section className="rounded-xl border border-teal-300 bg-teal-50 p-8 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-teal-500">
              <Check size={32} className="text-white" />
            </div>
            <h2 className="font-display text-2xl font-semibold text-teal-800">
              Veille activée pour {formData.nom_entreprise} !
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-teal-600">
              {suggestion?.categories?.length || 0} catégories,{" "}
              {validCommerciaux.length} commercial(s),{" "}
              {suggestion?.sites?.length || 0} sites configurés.
              Le pipeline utilisera ces mots-clés dès le prochain scan.
            </p>
            <div className="mt-4 rounded-lg bg-teal-100/50 p-3 text-xs text-teal-700">
              <p className="font-medium">Prochaines étapes :</p>
              <ul className="mt-1 list-inside list-disc text-left">
                <li>Lancez un scan pour voir les premiers résultats</li>
                <li>Ajustez les mots-clés dans Configuration si nécessaire</li>
                <li>Vérifiez que les commerciaux reçoivent les emails</li>
              </ul>
            </div>
            <button onClick={() => {
              setFormData({ nom_entreprise: "", email: "", telephone: "", region: "", ville: "",
                description_activite: "", marques: "", clients_cibles: "",
                types_offres: "", concurrents: "", sites_connus: "" });
              setCommerciaux([{ nom: "", email: "" }]);
              setSuggestion(null); setApplied(false); setTestResult(null); setStep(1);
            }} className="mt-6 rounded-lg border border-teal-300 px-4 py-2 text-sm font-medium text-teal-700 hover:bg-teal-100">
              Configurer un autre client
            </button>
          </section>
        )}

        {/* Sites surveillés */}
        {!applied && (
          <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-2">
              <Globe size={20} className="text-slate-400" />
              <h2 className="font-display text-lg font-semibold text-ink-900">Sites surveillés</h2>
            </div>
            {sourcesLoading && <Spinner />}
            {sources && sources.length === 0 && (
              <p className="text-sm text-slate-500">Aucun site. La génération IA en ajoutera.</p>
            )}
            {sources && sources.length > 0 && (
              <div className="space-y-2">
                {sources.map((s) => (
                  <div key={s.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
                    <div>
                      <p className="font-medium text-ink-900">{s.nom}</p>
                      <a href={s.url} target="_blank" rel="noreferrer"
                        className="text-xs text-blue-600 hover:underline">{s.url}</a>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      s.actif ? "bg-teal-50 text-teal-600" : "bg-slate-100 text-slate-500"}`}>
                      {s.actif ? "Actif" : "Inactif"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Info */}
        {!applied && (
          <section className="mt-6 rounded-lg bg-slate-50 p-4 text-xs text-slate-500">
            <p className="font-medium text-slate-600">Comment ça fonctionne :</p>
            <ul className="mt-1 list-inside list-disc space-y-0.5">
              <li>L'IA propose — elle ne modifie jamais la base directement</li>
              <li>Vous assignez les commerciaux et validez</li>
              <li>Les catégories s'ajoutent sans supprimer les anciennes</li>
              <li>Les commerciaux sont créés automatiquement</li>
              <li>Les règles d'assignation sont sauvées</li>
            </ul>
          </section>
        )}
      </div>
    </PageWrapper>
  );
}

// ============ COMPOSANTS ============

function StepCard({ title, subtitle, icon, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center gap-2">
        {icon}
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-900">{title}</h2>
          {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

function Field({ label, value, onChange, placeholder, type = "text" }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none" />
    </div>
  );
}

function TextArea({ label, value, onChange, placeholder, rows = 3 }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      <textarea value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder} rows={rows}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none" />
    </div>
  );
}

function StepButtons({ onPrev, onNext, nextLabel = "Suivant", nextIcon, nextDisabled }) {
  return (
    <div className="flex justify-between pt-4">
      {onPrev ? (
        <button onClick={onPrev} className="flex items-center gap-1 text-sm text-slate-500 hover:text-ink-900">
          <ChevronLeft size={16} /> Précédent
        </button>
      ) : <div />}
      {onNext && (
        <button onClick={onNext} disabled={nextDisabled}
          className="flex items-center gap-2 rounded-lg bg-amber-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50">
          {nextIcon} {nextLabel} <ChevronRight size={16} />
        </button>
      )}
    </div>
  );
}

function EditableCategory({ cat, onUpdate, onDelete, commerciaux }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-mono text-slate-500">{cat.id}</span>
          <input value={cat.label} onChange={(e) => onUpdate({ ...cat, label: e.target.value })}
            className="border-b border-transparent text-sm font-semibold text-ink-900 focus:border-amber-500 focus:outline-none" />
        </div>
        <button onClick={() => { if (confirm(`Supprimer ${cat.label} ?`)) onDelete(); }}
          className="text-slate-400 hover:text-rose-500"><Trash2 size={14} /></button>
      </div>

      <div className="mb-3">
        <p className="mb-1 text-xs font-medium uppercase text-slate-400">Commercial assigné</p>
        <select value={cat.commercial || ""}
          onChange={(e) => onUpdate({ ...cat, commercial: e.target.value || null })}
          className={`w-full rounded-lg border px-3 py-2 text-sm ${
            cat.commercial ? "border-teal-300 bg-teal-50" : "border-rose-200 bg-rose-50"}`}>
          <option value="">— Non assigné ⚠️ —</option>
          {commerciaux.map((c) => (
            <option key={c.nom} value={c.nom}>{c.nom} ({c.email})</option>
          ))}
        </select>
      </div>

      <EditableTags title="Mots-clés" tags={cat.keywords} color="ink"
        onUpdate={(tags) => onUpdate({ ...cat, keywords: tags })} />
      <EditableTags title="Marques" tags={cat.marques} color="blue"
        onUpdate={(tags) => onUpdate({ ...cat, marques: tags })} />
    </div>
  );
}

function EditableTags({ title, tags, color, onUpdate }) {
  const bgClass = color === "rose" ? "bg-rose-100 text-rose-700" :
    color === "blue" ? "bg-blue-100 text-blue-700" : "bg-ink-800/10 text-ink-800";
  const borderClass = color === "rose" ? "border-rose-200 text-rose-400 hover:border-rose-500" :
    color === "blue" ? "border-blue-200 text-blue-400 hover:border-blue-500" :
    "border-slate-300 text-slate-400 hover:border-amber-500 hover:text-amber-600";

  return (
    <div className="mb-2">
      <p className="mb-1 text-xs font-medium uppercase text-slate-400">{title} ({tags.length})</p>
      <div className="flex flex-wrap gap-1">
        {tags.map((tag, i) => (
          <span key={i} className={`group flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${bgClass}`}>
            {tag}
            <button onClick={() => onUpdate(tags.filter((_, idx) => idx !== i))}
              className="hidden text-rose-400 hover:text-rose-600 group-hover:inline">×</button>
          </span>
        ))}
        <button onClick={() => {
          const v = prompt(`Ajouter (${title.toLowerCase()}) :`);
          if (v?.trim()) onUpdate([...tags, v.trim()]);
        }} className={`rounded-full border border-dashed px-2 py-0.5 text-xs ${borderClass}`}>
          + ajouter
        </button>
      </div>
    </div>
  );
}