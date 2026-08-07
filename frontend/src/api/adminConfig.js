import apiClient from "./client";

export async function getConfiguration() {
  const { data } = await apiClient.get("/admin/config");
  return data;
}

export async function updateThresholds(score_decision_threshold, score_instant_alert_threshold) {
  const { data } = await apiClient.put("/admin/config/thresholds", {
    score_decision_threshold,
    score_instant_alert_threshold,
  });
  return data;
}

export async function updateCategories(categories) {
  const { data } = await apiClient.put("/admin/config/categories", { categories });
  return data;
}

export async function updateExclusionKeywords(exclusion_keywords) {
  const { data } = await apiClient.put("/admin/config/exclusion-keywords", { exclusion_keywords });
  return data;
}

export async function updateSources(active_sources) {
  const { data } = await apiClient.put("/admin/config/sources", { active_sources });
  return data;
}

export async function updateAssignmentRules(assignment_rules) {
  const { data } = await apiClient.put("/admin/config/assignment-rules", { assignment_rules });
  return data;
}
