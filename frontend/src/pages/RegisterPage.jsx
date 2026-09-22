import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { suggestConfigurationPublic, registerClient } from "../api/registration";

import {
  Sparkles, Check, RotateCcw, 
  Trash2, Building2, Target, ChevronRight, ChevronLeft,
  Users,
} from "lucide-react";
import Alert from "../components/ui/Alert";
import Spinner from "../components/ui/Spinner";
//import { suggestConfigurationPublic, registerClient } from "../api/registration";


const STEPS = [
  { id: 1, label: "Entreprise", icon: Building2 },
  { id: 2, label: "Activité", icon: Target },
  { id: 3, label: "Équipe", icon: Users },
  { id: 4, label: "IA", icon: Sparkles },
  { id: 5, label: "Validation", icon: Check },
];

export default function RegisterPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    nom_entreprise: "",
    email: "",
    password: "",
    password_confirm: "",
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
  const [registered, setRegistered] = useState(false);

  const updateField = (field, value) => setFormData({ ...formData, [field]: value });

  const validCommerciaux = commerciaux.filter((c) => c.nom.trim() && c.email.trim());

  const buildAiDescription = () => {
    const parts = [];
    if (formData.description_activite) parts.push(`Activité : ${formData.description_activite}`);
    if (formData.marques) parts.push(`Marques : ${formData.marques}`);
    if (formData.clients_cibles) parts.push(`Clients : ${formData.clients_cibles}`);
    if (formData.types_offres) parts.push(`Offres recherchées : ${formData.types_offres}`);
    if (formData.concurrents) parts.push(`Concurrents : ${formData.concurrents}`);
    if (formData.region) parts.push(`Région : ${formData.region}`);
    return parts.join("\n");
  };

  const suggestMutation = useMutation({
  mutationFn: () => suggestConfigurationPublic(buildAiDescription()),
    onSuccess: (data) => {
      const defaultCommercial = validCommerciaux.length === 1 ? validCommerciaux[0].nom : null;
      setSuggestion({
        ...data,
        categories: data.categories.map((c) => ({ ...c, commercial: defaultCommercial })),
      });
      setStep(5);
    },
  });

  const registerMutation = useMutation({
    mutationFn: () =>
      registerClient({
        nom_entreprise: formData.nom_entreprise,
        email: formData.email,
        password: formData.password,
        telephone: formData.telephone,
        region: formData.region,
        ville: formData.ville,
        categories: suggestion.categories,
        exclusion_keywords: suggestion.exclusion_keywords,
        sites: suggestion.sites || [],
        commerciaux: validCommerciaux,
      }),
    onSuccess: () => setRegistered(true),
  });

  const passwordsMatch = formData.password === formData.password_confirm;
  const passwordLong = formData.password.length >= 8;

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4 py-8">
      <div className="w-full max-w-2xl">

        {/* Logo */}
        <div className="mb-6 text-center">
          <p className="text-2xl font-bold text-white">VEILLEAO</p>
          <p className="text-sm text-slate-400">Créez votre compte de veille</p>
        </div>

        <div className="rounded-2xl bg-white p-8 shadow-xl">

          {/* Progression */}
          {!registered && (
            <div className="mb-6 flex items-center justify-between">
              {STEPS.map((s, i) => {
                const Icon = s.icon;
                const isActive = s.id === step;
                const isDone = s.id < step;
                return (
                  <div key={s.id} className="flex items-center">
                    <div className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${
                      isActive ? "bg-amber-500 text-white" :
                      isDone ? "bg-teal-500 text-white" :
                      "bg-slate-100 text-slate-400"
                    }`}>
                      {isDone ? <Check size={12} /> : <Icon size={12} />}
                      <span className="hidden sm:inline">{s.label}</span>
                    </div>
                    {i < STEPS.length - 1 && (
                      <div className={`mx-1 h-0.5 w-6 ${isDone ? "bg-teal-500" : "bg-slate-200"}`} />
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ÉTAPE 1 */}
          {step === 1 && (
            <div className="space-y-4">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900">
                <Building2 size={20} className="text-amber-500" /> Votre entreprise
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Nom *" value={formData.nom_entreprise}
                  onChange={(v) => updateField("nom_entreprise", v)} placeholder="CoolAir SARL" />
                <Input label="Email *" type="email" value={formData.email}
                  onChange={(v) => updateField("email", v)} placeholder="contact@coolair.tn" />
                <Input label="Mot de passe *" type="password" value={formData.password}
                  onChange={(v) => updateField("password", v)} placeholder="Min. 8 caractères" />
                <Input label="Confirmer *" type="password" value={formData.password_confirm}
                  onChange={(v) => updateField("password_confirm", v)} placeholder="Répétez le mot de passe" />
                <Input label="Téléphone" value={formData.telephone}
                  onChange={(v) => updateField("telephone", v)} placeholder="+216 XX XXX XXX" />
                <Input label="Région" value={formData.region}
                  onChange={(v) => updateField("region", v)} placeholder="Sfax, Tunis..." />
              </div>
              {formData.password && !passwordLong && (
                <p className="text-xs text-rose-500">Le mot de passe doit contenir au moins 8 caractères.</p>
              )}
              {formData.password_confirm && !passwordsMatch && (
                <p className="text-xs text-rose-500">Les mots de passe ne correspondent pas.</p>
              )}
              <NavButtons onNext={() => setStep(2)}
                nextDisabled={!formData.nom_entreprise || !formData.email || !passwordLong || !passwordsMatch} />
            </div>
          )}

          {/* ÉTAPE 2 */}
          {step === 2 && (
            <div className="space-y-4">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900">
                <Target size={20} className="text-amber-500" /> Votre activité
              </h2>
              <Area label="Décrivez votre activité *" value={formData.description_activite}
                onChange={(v) => updateField("description_activite", v)}
                placeholder="Ex: Nous vendons des climatiseurs Daikin et des pompes à chaleur." rows={4} />
              <Area label="Marques" value={formData.marques}
                onChange={(v) => updateField("marques", v)} placeholder="Daikin, LG, Carrier" rows={2} />
              <Area label="Clients cibles" value={formData.clients_cibles}
                onChange={(v) => updateField("clients_cibles", v)} placeholder="Hôpitaux, écoles, hôtels" rows={2} />
              <NavButtons onPrev={() => setStep(1)} onNext={() => setStep(3)}
                nextDisabled={!formData.description_activite} />
            </div>
          )}

          {/* ÉTAPE 3 */}
          {step === 3 && (
            <div className="space-y-4">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900">
                <Users size={20} className="text-amber-500" /> Équipe et objectifs
              </h2>

              <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
                <p className="mb-2 text-sm font-semibold text-ink-900">Commerciaux *</p>
                <div className="space-y-2">
                  {commerciaux.map((c, i) => (
                    <div key={i} className="flex gap-2">
                      <input value={c.nom} onChange={(e) => {
                        const u = [...commerciaux]; u[i] = { ...c, nom: e.target.value }; setCommerciaux(u);
                      }} placeholder="Nom" className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm" />
                      <input value={c.email} onChange={(e) => {
                        const u = [...commerciaux]; u[i] = { ...c, email: e.target.value }; setCommerciaux(u);
                      }} placeholder="Email" type="email" className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm" />
                      {commerciaux.length > 1 && (
                        <button onClick={() => setCommerciaux(commerciaux.filter((_, idx) => idx !== i))}
                          className="text-rose-400">×</button>
                      )}
                    </div>
                  ))}
                  <button onClick={() => setCommerciaux([...commerciaux, { nom: "", email: "" }])}
                    className="text-xs text-amber-600 hover:underline">+ Ajouter</button>
                </div>
              </div>

              <Area label="Types d'offres recherchées *" value={formData.types_offres}
                onChange={(v) => updateField("types_offres", v)}
                placeholder="Fourniture et installation de climatisation, maintenance CVC" rows={3} />
              <Area label="Concurrents" value={formData.concurrents}
                onChange={(v) => updateField("concurrents", v)} placeholder="FroidExpress, DirectClim" rows={2} />

              <NavButtons onPrev={() => setStep(2)}
                onNext={() => { setStep(4); suggestMutation.mutate(); }}
                nextLabel="Générer ma configuration" nextIcon={<Sparkles size={14} />}
                nextDisabled={!formData.types_offres || validCommerciaux.length === 0} />
            </div>
          )}

          {/* ÉTAPE 4 — Loading */}
          {step === 4 && suggestMutation.isPending && (
            <div className="flex flex-col items-center py-12">
              <Spinner className="h-10 w-10 text-amber-500" />
              <p className="mt-4 text-sm text-slate-500">Configuration en cours...</p>
            </div>
          )}
          {step === 4 && suggestMutation.isError && (
            <div className="space-y-4">
              <Alert variant="error">
                {suggestMutation.error?.response?.data?.detail || suggestMutation.error?.message || "Erreur"}
              </Alert>
              <NavButtons onPrev={() => setStep(3)} onNext={() => suggestMutation.mutate()} nextLabel="Réessayer" />
            </div>
          )}

          {/* ÉTAPE 5 — Validation */}
          {step === 5 && suggestion && !registered && (
            <div className="space-y-4">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-ink-900">
                <Check size={20} className="text-amber-500" /> Vérifiez votre configuration
              </h2>

              {validCommerciaux.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3">
                  <span className="text-xs text-slate-500">Assigner à toutes :</span>
                  {validCommerciaux.map((c) => (
                    <button key={c.nom} onClick={() => setSuggestion({
                      ...suggestion,
                      categories: suggestion.categories.map((cat) => ({ ...cat, commercial: c.nom })),
                    })} className="rounded-full bg-ink-800 px-3 py-1 text-xs text-white hover:bg-ink-700">
                      {c.nom}
                    </button>
                  ))}
                </div>
              )}

              {suggestion.categories.map((cat, ci) => (
                <EditCat key={ci} cat={cat} commerciaux={validCommerciaux}
                  onUpdate={(u) => {
                    const c = [...suggestion.categories]; c[ci] = u;
                    setSuggestion({ ...suggestion, categories: c });
                  }}
                  onDelete={() => setSuggestion({
                    ...suggestion, categories: suggestion.categories.filter((_, i) => i !== ci),
                  })} />
              ))}

              <Tags title="Exclusions" tags={suggestion.exclusion_keywords} color="rose"
                onUpdate={(t) => setSuggestion({ ...suggestion, exclusion_keywords: t })} />

              {suggestion.sites?.length > 0 && (
                <div>
                  <p className="mb-2 text-sm font-semibold text-ink-900">Sites ({suggestion.sites.length})</p>
                  {suggestion.sites.map((s, i) => (
                    <div key={i} className="mb-1 flex items-center justify-between rounded border p-2 text-xs">
                      <a href={s.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{s.nom}</a>
                      <button onClick={() => setSuggestion({
                        ...suggestion, sites: suggestion.sites.filter((_, idx) => idx !== i),
                      })} className="text-slate-400 hover:text-rose-500">×</button>
                    </div>
                  ))}
                </div>
              )}

              {suggestion.categories.some((c) => !c.commercial) && (
                <Alert variant="info">
                  ⚠️ Assignez un commercial à chaque catégorie pour recevoir les alertes.
                </Alert>
              )}

              <div className="flex gap-3">
                <button onClick={() => registerMutation.mutate()}
                  disabled={registerMutation.isPending || suggestion.categories.every((c) => !c.commercial)}
                  className="flex-1 rounded-lg bg-ink-800 py-3 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-50">
                  {registerMutation.isPending ? "Création du compte..." : "Créer mon compte et activer la veille"}
                </button>
                <button onClick={() => { setStep(3); setSuggestion(null); }}
                  className="rounded-lg border px-4 py-3 text-sm hover:bg-slate-50">
                  <RotateCcw size={14} />
                </button>
              </div>
              {registerMutation.isError && (
                <Alert variant="error">
                  {registerMutation.error?.response?.data?.detail || "Erreur lors de la création."}
                </Alert>
              )}
            </div>
          )}

          {/* INSCRIPTION RÉUSSIE */}
          {registered && (
            <div className="py-8 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-teal-500">
                <Check size={32} className="text-white" />
              </div>
              <h2 className="text-xl font-bold text-teal-800">Compte créé avec succès !</h2>
              <p className="mt-2 text-sm text-slate-600">
                Votre veille est configurée. Connectez-vous pour voir vos marchés.
              </p>
              <button onClick={() => navigate("/login")}
                className="mt-6 rounded-lg bg-ink-800 px-6 py-3 text-sm font-medium text-white hover:bg-ink-700">
                Se connecter
              </button>
            </div>
          )}

          {/* Lien login */}
          {!registered && step === 1 && (
            <p className="mt-6 text-center text-sm text-slate-500">
              Déjà un compte ?{" "}
              <button onClick={() => navigate("/login")} className="font-medium text-ink-800 hover:underline">
                Se connecter
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// Composants
function Input({ label, value, onChange, placeholder, type = "text" }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
    </div>
  );
}

function Area({ label, value, onChange, placeholder, rows = 3 }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      <textarea value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder} rows={rows}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
    </div>
  );
}

function NavButtons({ onPrev, onNext, nextLabel = "Suivant", nextIcon, nextDisabled }) {
  return (
    <div className="flex justify-between pt-2">
      {onPrev ? <button onClick={onPrev} className="text-sm text-slate-500 hover:text-ink-900">
        <ChevronLeft size={16} className="inline" /> Retour
      </button> : <div />}
      {onNext && <button onClick={onNext} disabled={nextDisabled}
        className="flex items-center gap-2 rounded-lg bg-amber-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50">
        {nextIcon} {nextLabel} <ChevronRight size={16} />
      </button>}
    </div>
  );
}

function EditCat({ cat, onUpdate, onDelete, commerciaux }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold">{cat.label} <span className="text-xs text-slate-400">({cat.id})</span></span>
        <button onClick={() => { if (confirm("Supprimer ?")) onDelete(); }} className="text-slate-400 hover:text-rose-500">
          <Trash2 size={14} />
        </button>
      </div>
      <select value={cat.commercial || ""} onChange={(e) => onUpdate({ ...cat, commercial: e.target.value || null })}
        className={`mb-2 w-full rounded border px-2 py-1.5 text-sm ${cat.commercial ? "border-teal-300 bg-teal-50" : "border-rose-200 bg-rose-50"}`}>
        <option value="">— Assignez un commercial —</option>
        {commerciaux.map((c) => <option key={c.nom} value={c.nom}>{c.nom}</option>)}
      </select>
      <Tags title="Mots-clés" tags={cat.keywords} color="ink" onUpdate={(t) => onUpdate({ ...cat, keywords: t })} />
      <Tags title="Marques" tags={cat.marques} color="blue" onUpdate={(t) => onUpdate({ ...cat, marques: t })} />
    </div>
  );
}

function Tags({ title, tags, color, onUpdate }) {
  const bg = color === "rose" ? "bg-rose-100 text-rose-700" : color === "blue" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-700";
  return (
    <div className="mb-1">
      <p className="text-[10px] font-medium uppercase text-slate-400">{title}</p>
      <div className="flex flex-wrap gap-1">
        {tags.map((t, i) => (
          <span key={i} className={`group rounded-full px-2 py-0.5 text-xs ${bg}`}>
            {t} <button onClick={() => onUpdate(tags.filter((_, idx) => idx !== i))}
              className="hidden text-rose-400 group-hover:inline">×</button>
          </span>
        ))}
        <button onClick={() => { const v = prompt("Ajouter :"); if (v?.trim()) onUpdate([...tags, v.trim()]); }}
          className="rounded-full border border-dashed px-2 py-0.5 text-xs text-slate-400">+</button>
      </div>
    </div>
  );
}