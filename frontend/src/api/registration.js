import apiClient from "./client";

function prepareShortTerms(
  value,
  { label, maxItems, splitItems = false }
) {
  if (value === undefined) {
    return [];
  }

  // Accepte également une chaîne de marques séparées
  // par des virgules, pour les anciens formulaires.
  const entries =
    typeof value === "string" && splitItems
      ? [value]
      : value;

  if (!Array.isArray(entries)) {
    throw new Error(`${label} : une liste est attendue.`);
  }

  const result = [];
  const seen = new Set();

  for (const entry of entries) {
    if (typeof entry !== "string") {
      throw new Error(`${label} : chaque élément doit être un texte.`);
    }

    const parts = splitItems
      ? entry.split(/[,;\r\n،]+/)
      : [entry];

    for (const part of parts) {
      const text = part.trim().replace(/\s+/g, " ");

      if (!text) continue;

      const length = Array.from(text).length;

      if (length < 2) {
        throw new Error(
          `${label} : chaque élément doit contenir au moins 2 caractères.`
        );
      }

      if (length > 120) {
        throw new Error(
          `${label} : un élément contient ${length} caractères, ` +
          `maximum 120. Saisissez une expression courte, ` +
          `pas un paragraphe. Pour les marques, utilisez uniquement ` +
          `les noms séparés par des virgules.`
        );
      }

      const key = text.toLowerCase();

      if (seen.has(key)) continue;

      seen.add(key);
      result.push(text);
    }
  }

  if (result.length > maxItems) {
    throw new Error(
      `${label} : maximum ${maxItems} éléments autorisés.`
    );
  }

  return result;
}
export async function getRegistrationOptions() {
  const { data } = await apiClient.get("/register/options");
  return data;
}

export async function getRegistrationSourceCatalog() {
  const { data } = await apiClient.get("/register/source-catalog");
  return data;
}

export async function suggestConfigurationPublic(payload) {
  const originalBody =
    typeof payload === "string"
      ? { description: payload }
      : payload;

  if (
    !originalBody ||
    typeof originalBody !== "object" ||
    Array.isArray(originalBody)
  ) {
    throw new Error("Les données du formulaire sont invalides.");
  }

  const body = {
    ...originalBody,

    marques: prepareShortTerms(originalBody.marques, {
      label: "Marques",
      maxItems: 30,
      splitItems: true,
    }),

    exclusion_keywords: prepareShortTerms(
      originalBody.exclusion_keywords,
      {
        label: "Exclusions",
        maxItems: 20,
        splitItems: false,
      }
    ),
  };

  const { data } = await apiClient.post(
    "/admin/ai-suggest/public",
    body,
    { timeout: 900000 }
  );

  return data;
}

export async function registerClient(payload) {
  const { data } = await apiClient.post(
    "/register",
    payload,
    { timeout: 120000 }
  );

  return data;
}
