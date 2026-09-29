import { useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
  RotateCcw,
  Sparkles,
  Trash2,
} from "lucide-react";

import {
  getRegistrationSourceCatalog,
  registerClient,
  suggestConfigurationPublic,
} from "../api/registration";

import Alert from "../components/ui/Alert";
import Spinner from "../components/ui/Spinner";


const MAX_SITES = 10;
const MAX_CATEGORIES = 5;

const STEPS = [
  "Entreprise",
  "Activité",
  "Équipe et sources",
  "Génération IA",
  "Validation",
];

const INITIAL_FORM = {
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
};

const FIELD_CLASS =
  "w-full min-w-0 rounded-lg border border-slate-200 px-3 py-2 " +
  "text-sm text-ink-900 focus:border-amber-500 focus:outline-none " +
  "disabled:bg-slate-50 disabled:text-slate-500";


function makeLocalId() {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
}

function textKey(value) {
  return String(value || "")
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function uniqueTerms(values) {
  const seen = new Set();
  const result = [];

  for (const value of values || []) {
    if (typeof value !== "string") continue;

    const cleaned = value.trim().replace(/\s+/g, " ");
    const key = textKey(cleaned);

    if (!key || seen.has(key)) continue;

    seen.add(key);
    result.push(cleaned);
  }

  return result;
}

function isEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
    String(value || "").trim()
  );
}

function apiErrorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const labels = {
      marques: "Marques",
      exclusion_keywords: "Exclusions",
      description: "Description",
      activite: "Activité",
      types_offres: "Offres recherchées",
      clients_cibles: "Clients cibles",
      sites_connus: "Sites déjà consultés",
      concurrents: "Concurrents",
    };

    return detail
      .map((issue) => {
        const location = (issue.loc || []).filter(
          (part) => part !== "body"
        );

        const field =
          labels[location[0]] ||
          location[0] ||
          "Formulaire";

        const position =
          typeof location[1] === "number"
            ? ` — élément ${location[1] + 1}`
            : "";

        if (issue.type === "string_too_long") {
          const maximum = issue.ctx?.max_length;

          return (
            `${field}${position} : texte trop long` +
            (maximum ? `, maximum ${maximum} caractères` : "") +
            "."
          );
        }

        if (issue.type === "string_too_short") {
          const minimum = issue.ctx?.min_length;

          return (
            `${field}${position} : texte trop court` +
            (minimum ? `, minimum ${minimum} caractères` : "") +
            "."
          );
        }

        return `${field}${position} : ${issue.msg || "Valeur invalide"}`;
      })
      .join(" — ");
  }

  return error?.message || "Une erreur est survenue.";
}

function normalizeHttpUrl(value) {
  const input = String(value || "").trim();

  if (!input) {
    throw new Error("Le lien d’un site est vide.");
  }

  if (input.length > 1000) {
    throw new Error("Le lien d’un site est trop long.");
  }

  const hasScheme = /^[a-z][a-z0-9+.-]*:/i.test(input);
  const candidate = hasScheme ? input : `https://${input}`;

  let url;

  try {
    url = new URL(candidate);
  } catch {
    throw new Error(`URL invalide : ${input}`);
  }

  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("Seuls les liens HTTP et HTTPS sont acceptés.");
  }

  if (url.username || url.password) {
    throw new Error(
      "Ne placez pas d’identifiant ou de mot de passe dans une URL."
    );
  }

  return url.href;
}

function safeLink(value) {
  try {
    return normalizeHttpUrl(value);
  } catch {
    return null;
  }
}

function prepareCommercials(rows) {
  const filledRows = rows.filter(
    (row) => row.nom.trim() || row.email.trim()
  );

  if (!filledRows.length) {
    throw new Error("Ajoutez au moins un commercial.");
  }

  const names = new Set();
  const emails = new Set();

  return filledRows.map((row) => {
    const nom = row.nom.trim().replace(/\s+/g, " ");
    const email = row.email.trim().toLowerCase();

    if (nom.length < 2 || !isEmail(email)) {
      throw new Error(
        "Chaque commercial doit avoir un nom et un email valides."
      );
    }

    const nameKey = nom.toLowerCase();

    if (names.has(nameKey) || emails.has(email)) {
      throw new Error(
        "Deux commerciaux ne peuvent pas avoir le même nom ou email."
      );
    }

    names.add(nameKey);
    emails.add(email);

    return { nom, email };
  });
}

function categoryError(categories, commerciaux) {
  if (!categories?.length) {
    return "Conservez ou ajoutez au moins une catégorie.";
  }

  if (categories.length > MAX_CATEGORIES) {
    return `Maximum ${MAX_CATEGORIES} catégories.`;
  }

  const knownCommercials = new Set(
    commerciaux.map((commercial) => commercial.nom)
  );
  const ids = new Set();

  for (const category of categories) {
    const id = String(category.id || "").trim();

    if (!/^[A-Z][A-Z0-9_]{1,49}$/.test(id)) {
      return "Chaque catégorie doit avoir un identifiant unique en majuscules.";
    }

    if (ids.has(id)) {
      return `L’identifiant ${id} est utilisé plusieurs fois.`;
    }

    ids.add(id);

    if (!category.label?.trim()) {
      return `Ajoutez un nom à la catégorie ${id}.`;
    }

    if (!category.keywords?.length) {
      return `Ajoutez au moins un mot-clé à ${category.label}.`;
    }

    if (!knownCommercials.has(category.commercial)) {
      return `Assignez un commercial valide à ${category.label}.`;
    }
  }

  return "";
}


export default function RegisterPage() {
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({ ...INITIAL_FORM });

  const [commerciaux, setCommerciaux] = useState(() => [
    { localId: makeLocalId(), nom: "", email: "" },
  ]);

  const [suggestion, setSuggestion] = useState(null);
  const [registered, setRegistered] = useState(false);
  const [formError, setFormError] = useState("");

  const [knowsSites, setKnowsSites] = useState(false);
  const [manualSites, setManualSites] = useState([]);

  const [languages, setLanguages] = useState(["fr", "ar"]);
  const [maxCategories, setMaxCategories] = useState(3);

  // null : pas encore de choix explicite.
  // rejected : sources retirées par l'utilisateur.
  const [sourceChoice, setSourceChoice] = useState({
    ids: null,
    rejected: [],
  });

  const catalogQuery = useQuery({
    queryKey: ["public-onboarding-source-catalog"],
    queryFn: getRegistrationSourceCatalog,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const catalogSources = catalogQuery.data || [];

  // Conserver aussi les sources reçues dans une proposition,
  // même si un rechargement du catalogue est momentanément indisponible.
  const sourceMap = new Map();

  for (const source of [
    ...(suggestion?.sites || []),
    ...catalogSources,
  ]) {
    if (
      Number.isInteger(source.source_id) &&
      source.source_id > 0
    ) {
      sourceMap.set(source.source_id, source);
    }
  }

  const visibleSources = [...sourceMap.values()];

  const declaredBrands = uniqueTerms(
    formData.marques.split(/[,;\n]+/)
  );

  let validCommerciaux = [];
  let teamError = "";

  try {
    validCommerciaux = prepareCommercials(commerciaux);
  } catch (error) {
    teamError = error.message;
  }

  const accountValid = Boolean(
    formData.nom_entreprise.trim().length >= 2 &&
    isEmail(formData.email) &&
    formData.password.length >= 8 &&
    formData.password.length <= 128 &&
    formData.password === formData.password_confirm
  );

  const activityValid = Boolean(
    formData.description_activite.trim().length >= 10 &&
    declaredBrands.length <= 30 &&
    languages.length > 0
  );

  const passwordChecks = {
    length: formData.password.length >= 8,
    mixedCase: /[a-z]/.test(formData.password) && /[A-Z]/.test(formData.password),
    number: /\d/.test(formData.password),
  };
  const passwordScore = Object.values(passwordChecks).filter(Boolean).length;

  const categoriesError = suggestion
    ? categoryError(suggestion.categories, validCommerciaux)
    : "";

  const updateField = (field, value) => {
    setFormData((current) => ({
      ...current,
      [field]: value,
    }));
    setFormError("");
  };

  const updateCommercial = (localId, field, value) => {
    setCommerciaux((current) =>
      current.map((commercial) =>
        commercial.localId === localId
          ? { ...commercial, [field]: value }
          : commercial
      )
    );
  };

  const addCommercial = () => {
    const row = { localId: makeLocalId(), nom: "", email: "" };
    setCommerciaux((current) => [...current, row]);
  };

  const toggleSource = (sourceId) => {
    setSourceChoice((current) => {
      const ids = current.ids || [];
      const selected = ids.includes(sourceId);

      return selected
        ? {
            ids: ids.filter((id) => id !== sourceId),
            rejected: [...new Set([...current.rejected, sourceId])],
          }
        : {
            ids: [...new Set([...ids, sourceId])],
            rejected: current.rejected.filter(
              (id) => id !== sourceId
            ),
          };
    });
  };

  const addManualSite = () => {
    const row = {
      localId: makeLocalId(),
      nom: "",
      url: "",
      description: "",
      prive: false,
      login: "",
      mot_de_passe: "",
    };

    setManualSites((current) => [...current, row]);
  };

  const updateManualSite = (localId, field, value) => {
    setManualSites((current) =>
      current.map((site) =>
        site.localId === localId
          ? { ...site, [field]: value }
          : site
      )
    );
  };

  const toggleLanguage = (language) => {
    setLanguages((current) => {
      if (current.includes(language)) {
        return current.length > 1
          ? current.filter((item) => item !== language)
          : current;
      }

      return [...current, language];
    });
  };

  const buildAiPayload = () => {
    const payload = {
      description: formData.description_activite.trim(),
      activite: formData.description_activite.trim(),
      types_offres: formData.types_offres.trim(),
      clients_cibles: formData.clients_cibles.trim(),
      concurrents: formData.concurrents.trim(),
      marques: declaredBrands,

      sites_connus: knowsSites
        ? formData.sites_connus.trim()
        : "",

      pays_cibles: ["TN"],
      veille_internationale: false,
      langues: languages,
      max_categories: maxCategories,
      exclusion_keywords: suggestion?.exclusion_keywords || [],
    };

    // Si absent, le backend peut reconnaître ONMP/TUNEPS
    // dans le texte sites_connus.
    if (sourceChoice.ids !== null) {
      payload.source_ids = sourceChoice.ids
        .map(Number)
        .filter((sourceId) => Number.isInteger(sourceId) && sourceId > 0);
    }

    return payload;
  };

  const suggestMutation = useMutation({
    mutationFn: async (payload) => {
      const data = await suggestConfigurationPublic(payload);

      if (!Array.isArray(data?.categories) || !data.categories.length) {
        throw new Error("La réponse ne contient aucune catégorie exploitable.");
      }

      return data;
    },

    retry: false,

    onSuccess: (data) => {
      const defaultCommercial =
        validCommerciaux.length === 1
          ? validCommerciaux[0].nom
          : null;

      const proposedIds = (data.sites || [])
        .map((site) => site.source_id)
        .filter((id) => Number.isInteger(id) && id > 0);

      setSourceChoice((current) => ({
        ...current,
        ids: [
          ...new Set([
            ...(current.ids || []),
            ...proposedIds.filter(
              (id) => !current.rejected.includes(id)
            ),
          ]),
        ],
      }));

      setSuggestion({
        ...data,
        exclusion_keywords: uniqueTerms(
          data.exclusion_keywords || []
        ),
        categories: data.categories.map((category) => ({
          ...category,
          localId: makeLocalId(),
          keywords: uniqueTerms(category.keywords || []),
          marques: uniqueTerms(category.marques || []),
          commercial: defaultCommercial,
        })),
      });

      // Les sources manuelles et les marques du formulaire
      // ne sont pas remplacées par la réponse IA.
      setFormError("");
      setStep(5);
    },
  });

  const buildRegistrationPayload = () => {
    if (!accountValid) {
      throw new Error(
        "Vérifiez les informations du compte et les mots de passe."
      );
    }

    if (!activityValid || !formData.types_offres.trim()) {
      throw new Error("Vérifiez votre activité et les offres recherchées.");
    }

    const team = prepareCommercials(commerciaux);
    const error = categoryError(suggestion?.categories, team);

    if (error) throw new Error(error);

    const sourceIds = new Set(
      (sourceChoice.ids || [])
        .map(Number)
        .filter((sourceId) => Number.isInteger(sourceId) && sourceId > 0)
    );

    for (const sourceId of sourceIds) {
      if (!sourceMap.has(sourceId)) {
        throw new Error(
          "Une source sélectionnée n’est plus disponible dans le catalogue."
        );
      }
    }

    const catalogByUrl = new Map();

    for (const source of visibleSources) {
      const url = safeLink(source.url);

      if (url) {
        catalogByUrl.set(url, source.source_id);
      }
    }

    const sites = [];
    const seenUrls = new Set();

    for (const site of knowsSites ? manualSites : []) {
      if (
        !site.nom.trim() &&
        !site.url.trim() &&
        !site.description.trim()
      ) {
        continue;
      }

      const url = normalizeHttpUrl(site.url);
      const existingSourceId = catalogByUrl.get(url);

      if (existingSourceId !== undefined) {
        sourceIds.add(existingSourceId);
        continue;
      }

      if (seenUrls.has(url)) continue;
      seenUrls.add(url);

      sites.push({
        nom: site.nom.trim() || new URL(url).hostname,
        url,
        description: site.description.trim(),
        prive: Boolean(site.prive),
        login: site.prive ? site.login.trim() : null,
        mot_de_passe: site.prive ? site.mot_de_passe : null,
      });
    }

    if (sourceIds.size + sites.length > MAX_SITES) {
      throw new Error(
        `Choisissez au maximum ${MAX_SITES} sources au total.`
      );
    }

    return {
      nom_entreprise: formData.nom_entreprise.trim(),
      email: formData.email.trim().toLowerCase(),
      password: formData.password,

      telephone: formData.telephone.trim(),
      region: formData.region.trim(),
      ville: formData.ville.trim(),

      description_activite: formData.description_activite.trim(),
      marques_representees: declaredBrands,
      clients_cibles: formData.clients_cibles.trim(),
      types_offres: formData.types_offres.trim(),
      concurrents: formData.concurrents.trim(),

      sites_consultes: knowsSites
        ? formData.sites_connus.trim()
        : "",

      categories: suggestion.categories.map((category) => ({
        id: category.id.trim(),
        label: category.label.trim(),
        keywords: uniqueTerms(category.keywords),
        marques: uniqueTerms(category.marques),
        commercial: category.commercial,
      })),

      exclusion_keywords: uniqueTerms(
        suggestion.exclusion_keywords || []
      ),

      source_ids: [...sourceIds],
      sites,
      commerciaux: team,
    };
  };

  const registerMutation = useMutation({
    mutationFn: () => registerClient(buildRegistrationPayload()),
    retry: false,

    onSuccess: () => {
      setRegistered(true);

      setFormData((current) => ({
        ...current,
        password: "",
        password_confirm: "",
      }));
    },
  });

  const busy =
    suggestMutation.isPending || registerMutation.isPending;

  const generate = () => {
    setFormError("");

    if (!accountValid) {
      setStep(1);
      setFormError("Complétez les informations du compte.");
      return;
    }

    if (!activityValid) {
      setStep(2);
      setFormError(
        "Décrivez votre activité et vérifiez les marques."
      );
      return;
    }

    if (teamError || !formData.types_offres.trim()) {
      setFormError(teamError || "Indiquez les offres recherchées.");
      return;
    }

    if (
      suggestion &&
      !window.confirm(
        "La régénération remplacera les catégories, mots-clés et " +
        "assignations de la proposition. Vos sources choisies, liens " +
        "manuels et marques du formulaire seront conservés. Continuer ?"
      )
    ) {
      return;
    }

    suggestMutation.reset();
    setStep(4);
    suggestMutation.mutate(buildAiPayload());
  };

  const updateCategory = (localId, changes) => {
    setSuggestion((current) => ({
      ...current,
      categories: current.categories.map((category) =>
        category.localId === localId
          ? { ...category, ...changes }
          : category
      ),
    }));
  };

  const addCategory = () => {
    if (!suggestion || suggestion.categories.length >= MAX_CATEGORIES) {
      return;
    }

    const existingIds = new Set(
      suggestion.categories.map((category) => category.id)
    );

    let number = 1;
    while (existingIds.has(`CATEGORIE_${number}`)) number += 1;

    const category = {
      localId: makeLocalId(),
      id: `CATEGORIE_${number}`,
      label: "Nouvelle catégorie",
      keywords: [],
      marques: [],
      commercial:
        validCommerciaux.length === 1
          ? validCommerciaux[0].nom
          : null,
    };

    setSuggestion((current) => ({
      ...current,
      categories: [...current.categories, category],
    }));
  };

  const renderSourceFields = () => (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-slate-50/60 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-amber-700">
            Étape 3 · Sources
          </p>
          <h3 className="font-semibold text-ink-900">
            Où trouvez-vous vos appels d’offres ?
          </h3>
          <p className="mt-1 max-w-xl text-xs leading-5 text-slate-500">
            Vos choix aident l’IA à comprendre votre veille. Les nouvelles
            URLs restent des propositions à vérifier avant activation.
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200">
          {(sourceChoice.ids || []).length} sélectionnée(s)
        </span>
      </div>

      {catalogQuery.isPending && (
        <p className="text-sm text-slate-500">
          Chargement du catalogue…
        </p>
      )}

      {catalogQuery.isError && (
        <Alert variant="error">
          {apiErrorMessage(catalogQuery.error)}
          <button
            type="button"
            onClick={() => catalogQuery.refetch()}
            className="ml-2 underline"
          >
            Réessayer
          </button>
        </Alert>
      )}

      <div className="space-y-2">
        {visibleSources.map((source) => {
          const href = safeLink(source.url);

          return (
            <div
              key={source.source_id}
              className={`rounded-lg border p-3 transition-colors ${
                sourceChoice.ids?.includes(source.source_id)
                  ? "border-amber-300 bg-amber-50/70"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={
                    sourceChoice.ids?.includes(source.source_id) || false
                  }
                  onChange={() => toggleSource(source.source_id)}
                />
                <span>
                  <span className="block text-sm font-semibold">
                    {source.nom}
                  </span>
                  <span className="block text-xs text-slate-500">
                    {source.description}
                  </span>
                </span>
              </label>

              {href && (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 block break-all text-xs text-blue-600 hover:underline"
                >
                  {source.url}
                </a>
              )}
            </div>
          );
        })}
      </div>

      {!catalogQuery.isPending &&
        !catalogQuery.isError &&
        visibleSources.length === 0 && (
          <p className="text-sm text-slate-500">
            Aucune source disponible dans le catalogue public.
          </p>
        )}

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">
          Consultez-vous déjà des sites d’appels d’offres ?
        </legend>

        <div className="flex gap-5 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="known-sites"
              checked={!knowsSites}
              onChange={() => setKnowsSites(false)}
            />
            Non
          </label>

          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="known-sites"
              checked={knowsSites}
              onChange={() => setKnowsSites(true)}
            />
            Oui
          </label>
        </div>
      </fieldset>

      {knowsSites && (
        <div className="space-y-3">
          <Area
            label="Plateformes déjà consultées"
            value={formData.sites_connus}
            onChange={(value) => updateField("sites_connus", value)}
            placeholder="Exemple : ONMP, TUNEPS, portail d’un acheteur…"
            rows={2}
            maxLength={3000}
          />

          <p className="text-xs text-slate-500">
            Pour un autre site, indiquez la page contenant les annonces.
            Pour un site privé, cochez la case et renseignez ses identifiants.
          </p>

          {manualSites.map((site) => (
            <div
              key={site.localId}
              className="space-y-3 rounded-lg border border-amber-200 bg-amber-50/40 p-3"
            >
              <Input
                label="Nom du site — facultatif"
                value={site.nom}
                onChange={(value) =>
                  updateManualSite(site.localId, "nom", value)
                }
                maxLength={255}
                placeholder="Portail de mon acheteur"
              />

              <Input
                label="Lien de la page d’annonces *"
                type="url"
                value={site.url}
                onChange={(value) =>
                  updateManualSite(site.localId, "url", value)
                }
                maxLength={1000}
                placeholder="https://..."
              />

              <Area
                label="Pourquoi ce site vous intéresse ?"
                value={site.description}
                onChange={(value) =>
                  updateManualSite(
                    site.localId,
                    "description",
                    value
                  )
                }
                rows={2}
                maxLength={1000}
              />

              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={Boolean(site.prive)}
                  onChange={(event) =>
                    updateManualSite(
                      site.localId,
                      "prive",
                      event.target.checked
                    )
                  }
                />
                Site privé avec compte obligatoire
              </label>

              {site.prive && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Input
                    label="Login *"
                    value={site.login}
                    onChange={(value) =>
                      updateManualSite(site.localId, "login", value)
                    }
                    autoComplete="username"
                  />
                  <Input
                    label="Mot de passe *"
                    type="password"
                    value={site.mot_de_passe}
                    onChange={(value) =>
                      updateManualSite(site.localId, "mot_de_passe", value)
                    }
                    autoComplete="new-password"
                  />
                </div>
              )}

              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-amber-800">
                  Proposition manuelle — non testée
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setManualSites((current) =>
                      current.filter(
                        (item) => item.localId !== site.localId
                      )
                    )
                  }
                  className="text-xs text-rose-600 hover:underline"
                >
                  Supprimer ce site
                </button>
              </div>
            </div>
          ))}

          <button
            type="button"
            onClick={addManualSite}
            disabled={manualSites.length >= MAX_SITES}
            className="text-sm font-medium text-amber-700 hover:underline disabled:opacity-50"
          >
            + Ajouter un site
          </button>
        </div>
      )}

      {!knowsSites && manualSites.length > 0 && (
        <p className="text-xs text-slate-500">
          Vos liens restent en brouillon. Ils ne seront transmis
          que si vous sélectionnez « Oui ».
        </p>
      )}

      <p className="text-xs text-slate-500">
        Maximum {MAX_SITES} sources au total. Cette page utilise le
        catalogue et vos liens manuels ; elle ne recherche pas de
        nouveaux sites sur Internet.
      </p>
    </section>
  );

  return (
    <div className="min-h-screen bg-ink-950 px-4 py-8">
      <div className="mx-auto w-full max-w-3xl">
        <header className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-white">UlySearch</h1>
          <p className="text-sm text-slate-400">
            Créez votre compte de veille
          </p>
        </header>

        <main className="rounded-2xl bg-white p-5 shadow-xl sm:p-8">
          {registered ? (
            <section className="py-8 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-teal-500">
                <Check size={32} className="text-white" />
              </div>

              <h2 className="text-xl font-bold text-teal-800">
                Compte créé avec succès !
              </h2>

              <p className="mx-auto mt-3 max-w-lg text-sm text-slate-600">
                Votre configuration a été envoyée. Les nouvelles sources
                doivent être vérifiées avant activation. Les premiers
                résultats apparaîtront après leur collecte.
              </p>

              <button
                type="button"
                onClick={() => navigate("/login")}
                className="mt-6 rounded-lg bg-ink-800 px-6 py-3 text-sm font-medium text-white"
              >
                Se connecter
              </button>
            </section>
          ) : (
            <>
              <ol className="mb-6 flex flex-wrap gap-2">
                {STEPS.map((label, index) => (
                  <li
                    key={label}
                    aria-current={step === index + 1 ? "step" : undefined}
                    className={
                      "rounded-full px-3 py-1 text-xs font-medium " +
                      (step === index + 1
                        ? "bg-amber-500 text-white"
                        : step > index + 1
                          ? "bg-teal-100 text-teal-700"
                          : "bg-slate-100 text-slate-500")
                    }
                  >
                    {index + 1}. {label}
                  </li>
                ))}
              </ol>

              {formError && (
                <div className="mb-4">
                  <Alert variant="error">{formError}</Alert>
                </div>
              )}

              <fieldset disabled={busy} className="min-w-0">
                {step === 1 && (
                  <section className="space-y-4">
                    <h2 className="text-lg font-semibold">Votre entreprise</h2>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <Input
                        label="Nom de l’entreprise *"
                        value={formData.nom_entreprise}
                        onChange={(v) => updateField("nom_entreprise", v)}
                        maxLength={255}
                        autoComplete="organization"
                        placeholder="Ex. : CoolAir SARL"
                      />
                      <Input
                        label="Email de connexion *"
                        type="email"
                        value={formData.email}
                        onChange={(v) => updateField("email", v)}
                        maxLength={255}
                        autoComplete="email"
                        placeholder="contact@entreprise.tn"
                      />
                      <Input
                        label="Mot de passe *"
                        type="password"
                        value={formData.password}
                        onChange={(v) => updateField("password", v)}
                        maxLength={128}
                        autoComplete="new-password"
                        placeholder="Minimum 8 caractères"
                      />
                      <Input
                        label="Confirmer le mot de passe *"
                        type="password"
                        value={formData.password_confirm}
                        onChange={(v) => updateField("password_confirm", v)}
                        maxLength={128}
                        autoComplete="new-password"
                        placeholder="Répétez votre mot de passe"
                      />
                      <Input
                        label="Téléphone"
                        type="tel"
                        value={formData.telephone}
                        onChange={(v) => updateField("telephone", v)}
                        maxLength={30}
                        autoComplete="tel"
                        placeholder="+216 XX XXX XXX"
                      />
                      <Input
                        label="Région / Gouvernorat"
                        value={formData.region}
                        onChange={(v) => updateField("region", v)}
                        maxLength={100}
                        placeholder="Ex. : Tunis, Sfax, Sousse"
                      />
                      <Input
                        label="Ville"
                        value={formData.ville}
                        onChange={(v) => updateField("ville", v)}
                        maxLength={100}
                        placeholder="Ex. : Sfax"
                      />
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <div className="mb-2 flex items-center justify-between text-xs">
                        <span className="font-medium text-slate-600">Sécurité du mot de passe</span>
                        <span className={passwordScore === 3 ? "font-medium text-teal-600" : "text-slate-500"}>
                          {passwordScore === 0 ? "À renseigner" : passwordScore === 3 ? "Bon mot de passe" : "À renforcer"}
                        </span>
                      </div>
                      <div className="mb-2 flex gap-1" aria-hidden="true">
                        {[1, 2, 3].map((level) => (
                          <span key={level} className={`h-1.5 flex-1 rounded-full ${level <= passwordScore ? "bg-teal-500" : "bg-slate-200"}`} />
                        ))}
                      </div>
                      <p className="text-xs text-slate-500">
                        Utilisez au moins 8 caractères, une majuscule, une minuscule et un chiffre.
                      </p>
                    </div>

                    {formData.password_confirm &&
                      formData.password !== formData.password_confirm && (
                        <Alert variant="error">
                          Les mots de passe ne correspondent pas.
                        </Alert>
                      )}

                    <NavButtons
                      onNext={() => {
                        setFormError("");
                        setStep(2);
                      }}
                      nextDisabled={!accountValid}
                    />

                    <p className="text-center text-sm text-slate-500">
                      Déjà un compte ?{" "}
                      <button
                        type="button"
                        onClick={() => navigate("/login")}
                        className="font-medium text-ink-800 underline"
                      >
                        Se connecter
                      </button>
                    </p>
                  </section>
                )}

                {step === 2 && (
                  <section className="space-y-4">
                    <h2 className="text-lg font-semibold">Votre activité</h2>

                    <Area
                      label="Que vendez-vous, installez-vous ou louez-vous ? *"
                      value={formData.description_activite}
                      onChange={(v) => updateField("description_activite", v)}
                      rows={5}
                      maxLength={4000}
                      placeholder="Décrivez précisément vos produits et prestations."
                    />
                    <Area
                        label="Marques — noms uniquement, séparés par des virgules"
                        value={formData.marques}
                        onChange={(value) => updateField("marques", value)}
                        rows={2}
                        maxLength={2000}
                        placeholder="Danfoss, Carrier, Bitzer, Copeland, GEA, Carel, Tecumseh"
                      />

                      <p className="text-xs text-slate-500">
                        Une marque par élément, sans phrase descriptive.
                        Placez les explications complémentaires dans votre activité.
                      </p>

                    <Area
                      label="Qui sont vos clients cibles ?"
                      value={formData.clients_cibles}
                      onChange={(v) => updateField("clients_cibles", v)}
                      rows={3}
                      maxLength={3000}
                      placeholder="Ex. : hôtels, hôpitaux, collectivités, industriels"
                    />

                    <fieldset>
                      <legend className="mb-2 text-sm font-medium">
                        Langues des mots-clés
                      </legend>
                      <div className="flex flex-wrap gap-4 text-sm">
                        {[
                          ["fr", "Français"],
                          ["ar", "Arabe"],
                          ["en", "Anglais"],
                        ].map(([code, label]) => (
                          <label key={code} className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={languages.includes(code)}
                              onChange={() => toggleLanguage(code)}
                            />
                            {label}
                          </label>
                        ))}
                      </div>
                    </fieldset>

                    <label className="block text-sm">
                      Maximum de catégories proposées
                      <select
                        value={maxCategories}
                        onChange={(event) =>
                          setMaxCategories(Number(event.target.value))
                        }
                        className={`${FIELD_CLASS} mt-1`}
                      >
                        {[1, 2, 3, 4, 5].map((number) => (
                          <option key={number} value={number}>
                            {number}
                          </option>
                        ))}
                      </select>
                    </label>

                    <NavButtons
                      onPrev={() => setStep(1)}
                      onNext={() => setStep(3)}
                      nextDisabled={!activityValid}
                    />
                  </section>
                )}

                {step === 3 && (
                  <section className="space-y-4">
                    <h2 className="text-lg font-semibold">
                      Équipe, besoins et sources
                    </h2>

                    <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50/40 p-4">
                      <h3 className="text-sm font-semibold">Commerciaux *</h3>
                      <p className="text-xs text-slate-500">
                        Ajoutez les personnes qui recevront les alertes correspondant à leurs catégories.
                      </p>

                      {commerciaux.map((commercial) => (
                        <div
                          key={commercial.localId}
                          className="grid items-end gap-2 sm:grid-cols-[1fr_1fr_auto]"
                        >
                          <Input
                            label="Nom"
                            value={commercial.nom}
                            onChange={(value) =>
                              updateCommercial(
                                commercial.localId,
                                "nom",
                                value
                              )
                            }
                            maxLength={255}
                            placeholder="Nom complet"
                          />
                          <Input
                            label="Email"
                            type="email"
                            value={commercial.email}
                            onChange={(value) =>
                              updateCommercial(
                                commercial.localId,
                                "email",
                                value
                              )
                            }
                            maxLength={255}
                            placeholder="email@entreprise.tn"
                          />
                          {commerciaux.length > 1 && (
                            <button
                              type="button"
                              aria-label="Supprimer ce commercial"
                              onClick={() =>
                                setCommerciaux((current) =>
                                  current.filter(
                                    (item) =>
                                      item.localId !== commercial.localId
                                  )
                                )
                              }
                              className="p-2 text-rose-600"
                            >
                              <Trash2 size={16} />
                            </button>
                          )}
                        </div>
                      ))}

                      <button
                        type="button"
                        onClick={addCommercial}
                        disabled={commerciaux.length >= 20}
                        className="text-sm text-amber-700 hover:underline"
                      >
                        + Ajouter un commercial
                      </button>

                      {teamError && (
                        <p className="text-xs text-rose-600">{teamError}</p>
                      )}
                    </div>

                    <Area
                      label="Quels types d’offres recherchez-vous ? *"
                      value={formData.types_offres}
                      onChange={(v) => updateField("types_offres", v)}
                      rows={4}
                      maxLength={3000}
                      placeholder="Ex. : fourniture, installation et maintenance de systèmes de climatisation"
                    />
                    <Area
                      label="Concurrents connus"
                      value={formData.concurrents}
                      onChange={(v) => updateField("concurrents", v)}
                      rows={2}
                      maxLength={2000}
                      placeholder="Ex. : entreprise concurrente ou acteur local"
                    />

                    {renderSourceFields()}

                    <NavButtons
                      onPrev={() => setStep(2)}
                      onNext={generate}
                      nextLabel={
                        suggestion
                          ? "Régénérer la proposition"
                          : "Générer ma configuration"
                      }
                      nextDisabled={
                        Boolean(teamError) ||
                        !formData.types_offres.trim()
                      }
                    />
                  </section>
                )}

                {step === 4 && (
                  <section className="space-y-5 py-8">
                    {suggestMutation.isPending ? (
                      <div
                        role="status"
                        aria-live="polite"
                        className="flex flex-col items-center text-center"
                      >
                        <Spinner className="h-10 w-10 text-amber-500" />
                        <h2 className="mt-4 text-lg font-semibold">
                          Génération de votre proposition
                        </h2>
                        <p className="mt-2 text-sm text-slate-500">
                          Analyse de l’activité, des catégories et des mots-clés.
                          Vos liens manuels sont conservés.
                        </p>
                      </div>
                    ) : (
                      <>
                        <Alert variant="error">
                          {apiErrorMessage(suggestMutation.error)}
                        </Alert>
                        <NavButtons
                          onPrev={() => setStep(3)}
                          onNext={generate}
                          nextLabel="Réessayer"
                        />
                      </>
                    )}
                  </section>
                )}

                {step === 5 && suggestion && (
                  <section className="space-y-5">
                    <h2 className="text-lg font-semibold">
                      Vérifiez votre configuration
                    </h2>

                    <Alert variant="info">
                      L’IA propose une configuration. Vérifiez les catégories,
                      traductions, mots-clés et assignations avant validation.
                    </Alert>

                    {suggestion.warnings?.length > 0 && (
                      <Alert variant="info">
                        <ul className="list-inside list-disc space-y-1">
                          {suggestion.warnings.map((warning, index) => (
                            <li key={index}>{warning}</li>
                          ))}
                        </ul>
                      </Alert>
                    )}

                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs font-semibold">
                        Marques déclarées par votre entreprise
                      </p>
                      <p className="mt-1 text-sm text-slate-600">
                        {declaredBrands.join(", ") ||
                          "Aucune marque déclarée"}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-slate-500">
                        Assigner toutes les catégories à :
                      </span>
                      {validCommerciaux.map((commercial) => (
                        <button
                          key={commercial.email}
                          type="button"
                          onClick={() =>
                            setSuggestion((current) => ({
                              ...current,
                              categories: current.categories.map(
                                (category) => ({
                                  ...category,
                                  commercial: commercial.nom,
                                })
                              ),
                            }))
                          }
                          className="rounded-full bg-ink-800 px-3 py-1 text-xs text-white"
                        >
                          {commercial.nom}
                        </button>
                      ))}
                    </div>

                    {suggestion.categories.map((category) => (
                      <CategoryEditor
                        key={category.localId}
                        category={category}
                        commerciaux={validCommerciaux}
                        onUpdate={(changes) =>
                          updateCategory(category.localId, changes)
                        }
                        onDelete={() => {
                          if (!window.confirm("Supprimer cette catégorie ?")) {
                            return;
                          }

                          setSuggestion((current) => ({
                            ...current,
                            categories: current.categories.filter(
                              (item) => item.localId !== category.localId
                            ),
                          }));
                        }}
                      />
                    ))}

                    <button
                      type="button"
                      onClick={addCategory}
                      disabled={
                        suggestion.categories.length >= MAX_CATEGORIES
                      }
                      className="text-sm text-amber-700 hover:underline disabled:opacity-50"
                    >
                      + Ajouter une catégorie
                    </button>

                    <TagEditor
                      title="Exclusions explicites"
                      tags={suggestion.exclusion_keywords || []}
                      color="rose"
                      max={20}
                      onUpdate={(tags) =>
                        setSuggestion((current) => ({
                          ...current,
                          exclusion_keywords: tags,
                        }))
                      }
                    />

                    {renderSourceFields()}

                    {categoriesError && (
                      <Alert variant="info">{categoriesError}</Alert>
                    )}

                    {registerMutation.isError && (
                      <Alert variant="error">
                        {apiErrorMessage(registerMutation.error)}
                      </Alert>
                    )}

                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => registerMutation.mutate()}
                        disabled={
                          registerMutation.isPending ||
                          Boolean(categoriesError)
                        }
                        className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-ink-800 px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
                      >
                        {registerMutation.isPending ? (
                          <>
                            <Spinner className="h-4 w-4" />
                            Création du compte…
                          </>
                        ) : (
                          <>
                            <Check size={16} />
                            Créer mon compte et enregistrer ma veille
                          </>
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={generate}
                        className="flex items-center gap-2 rounded-lg border px-4 py-3 text-sm"
                      >
                        <Sparkles size={15} />
                        Régénérer
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setFormError("");
                          registerMutation.reset();
                          setStep(3);
                        }}
                        className="flex items-center gap-2 rounded-lg border px-4 py-3 text-sm"
                      >
                        <RotateCcw size={15} />
                        Modifier mes réponses
                      </button>
                    </div>
                  </section>
                )}
              </fieldset>
            </>
          )}
        </main>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Composants du formulaire
// ---------------------------------------------------------------------------

function Input({
  label,
  value,
  onChange,
  type = "text",
  ...props
}) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const isPassword = type === "password";
  const inputType = isPassword && visible ? "text" : type;

  return (
    <div className="min-w-0">
      <label
        htmlFor={id}
        className="mb-1 block text-xs font-medium text-slate-600"
      >
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={inputType}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={`${FIELD_CLASS} ${isPassword ? "pr-11" : ""}`}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setVisible((current) => !current)}
            aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
            title={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-slate-400 hover:text-ink-900"
          >
            {visible ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        )}
      </div>
    </div>
  );
}

function Area({
  label,
  value,
  onChange,
  rows = 3,
  ...props
}) {
  const id = useId();

  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1 block text-xs font-medium text-slate-600"
      >
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        rows={rows}
        onChange={(event) => onChange(event.target.value)}
        className={FIELD_CLASS}
        {...props}
      />
    </div>
  );
}

function NavButtons({
  onPrev,
  onNext,
  nextLabel = "Suivant",
  nextDisabled = false,
}) {
  return (
    <div className="flex items-center justify-between gap-3 pt-3">
      {onPrev ? (
        <button
          type="button"
          onClick={onPrev}
          className="flex items-center gap-1 text-sm text-slate-600"
        >
          <ChevronLeft size={16} />
          Retour
        </button>
      ) : (
        <span />
      )}

      <button
        type="button"
        onClick={onNext}
        disabled={nextDisabled}
        className="flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
      >
        {nextLabel}
        <ChevronRight size={16} />
      </button>
    </div>
  );
}

function CategoryEditor({
  category,
  commerciaux,
  onUpdate,
  onDelete,
}) {
  return (
    <section className="space-y-3 rounded-xl border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="grid flex-1 gap-3 sm:grid-cols-2">
          <Input
            label="Nom de la catégorie"
            value={category.label || ""}
            onChange={(value) => onUpdate({ label: value })}
            maxLength={100}
          />
          <Input
            label="Identifiant"
            value={category.id || ""}
            onChange={(value) =>
              onUpdate({
                id: value.toUpperCase().replace(/[\s-]+/g, "_"),
              })
            }
            maxLength={50}
          />
        </div>

        <button
          type="button"
          onClick={onDelete}
          aria-label="Supprimer cette catégorie"
          className="mt-6 text-rose-600"
        >
          <Trash2 size={17} />
        </button>
      </div>

      {category.perimetre && (
        <p className="text-xs text-slate-500">
          Périmètre proposé : {category.perimetre}
        </p>
      )}

      <label className="block text-xs font-medium text-slate-600">
        Commercial assigné
        <select
          value={category.commercial || ""}
          onChange={(event) =>
            onUpdate({
              commercial: event.target.value || null,
            })
          }
          className={`${FIELD_CLASS} mt-1`}
        >
          <option value="">— Choisir un commercial —</option>
          {commerciaux.map((commercial) => (
            <option key={commercial.email} value={commercial.nom}>
              {commercial.nom}
            </option>
          ))}
        </select>
      </label>

      <TagEditor
        title="Mots-clés"
        tags={category.keywords || []}
        onUpdate={(tags) => onUpdate({ keywords: tags })}
        max={80}
      />

      <TagEditor
        title="Marques associées à cette catégorie"
        tags={category.marques || []}
        color="blue"
        onUpdate={(tags) => onUpdate({ marques: tags })}
        max={30}
      />
    </section>
  );
}

function TagEditor({
  title,
  tags,
  onUpdate,
  color = "slate",
  max = 80,
}) {
  const id = useId();
  const [value, setValue] = useState("");

  const badgeClass =
    color === "rose"
      ? "bg-rose-100 text-rose-800"
      : color === "blue"
        ? "bg-blue-100 text-blue-800"
        : "bg-slate-100 text-slate-700";

  const add = () => {
    const cleaned = value.trim();
    if (!cleaned || tags.length >= max) return;

    onUpdate(uniqueTerms([...tags, cleaned]));
    setValue("");
  };

  return (
    <div>
      <label
        htmlFor={id}
        className="mb-2 block text-xs font-medium text-slate-600"
      >
        {title} — {tags.length}
      </label>

      <div className="mb-2 flex flex-wrap gap-1.5">
        {tags.map((tag, index) => (
          <span
            key={`${tag}-${index}`}
            className={`flex items-center gap-2 rounded-full px-2.5 py-1 text-xs ${badgeClass}`}
          >
            <span dir="auto">{tag}</span>
            <button
              type="button"
              aria-label={`Retirer ${tag}`}
              onClick={() =>
                onUpdate(tags.filter((_, itemIndex) => itemIndex !== index))
              }
              className="font-bold hover:text-rose-600"
            >
              ×
            </button>
          </span>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          id={id}
          value={value}
          maxLength={120}
          disabled={tags.length >= max}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
          placeholder="Ajouter une expression"
          className={FIELD_CLASS}
        />

        <button
          type="button"
          onClick={add}
          disabled={!value.trim() || tags.length >= max}
          className="rounded-lg border px-3 text-sm disabled:opacity-50"
        >
          Ajouter
        </button>
      </div>
    </div>
  );
}