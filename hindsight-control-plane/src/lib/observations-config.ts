export type ObservationsEdits = {
  enable_observations: boolean | null;
  observation_scope_tag_key_whitelist: string[] | null;
  consolidation_llm_batch_size: number | null;
  consolidation_source_facts_max_tokens: number | null;
  consolidation_source_facts_max_tokens_per_observation: number | null;
  observations_mission: string | null;
  max_observations_per_scope: number | null;
};

type ObservationsConfig = Partial<ObservationsEdits> & Record<string, unknown>;
type ObservationsOverridesSnapshot = Pick<
  Partial<ObservationsEdits>,
  "enable_observations" | "observation_scope_tag_key_whitelist"
> &
  Record<string, unknown>;
type ObservationsOverridesResponse = ObservationsOverridesSnapshot | null | undefined;
const OBSERVATIONS_KEYS = [
  "enable_observations",
  "observation_scope_tag_key_whitelist",
  "consolidation_llm_batch_size",
  "consolidation_source_facts_max_tokens",
  "consolidation_source_facts_max_tokens_per_observation",
  "observations_mission",
  "max_observations_per_scope",
] as const satisfies readonly (keyof ObservationsEdits)[];
const OVERRIDE_AWARE_OBSERVATIONS_KEYS = [
  "enable_observations",
  "observation_scope_tag_key_whitelist",
] as const satisfies readonly (keyof ObservationsEdits)[];

function resolvedObservationsSlice(resolvedConfig: ObservationsConfig): ObservationsEdits {
  return {
    enable_observations: resolvedConfig.enable_observations ?? null,
    observation_scope_tag_key_whitelist: resolvedConfig.observation_scope_tag_key_whitelist ?? null,
    consolidation_llm_batch_size: resolvedConfig.consolidation_llm_batch_size ?? null,
    consolidation_source_facts_max_tokens:
      resolvedConfig.consolidation_source_facts_max_tokens ?? null,
    consolidation_source_facts_max_tokens_per_observation:
      resolvedConfig.consolidation_source_facts_max_tokens_per_observation ?? null,
    observations_mission: resolvedConfig.observations_mission ?? null,
    max_observations_per_scope: resolvedConfig.max_observations_per_scope ?? null,
  };
}

export function observationsSlice(
  resolvedConfig: ObservationsConfig,
  overrides: ObservationsOverridesResponse
): ObservationsEdits {
  return {
    ...resolvedObservationsSlice(resolvedConfig),
    // The resolved value cannot distinguish inheritance from an explicit bank
    // override. Keep policy fields override-aware so their controls can express
    // the inherited, explicitly empty, and configured states independently.
    enable_observations: overrides?.enable_observations ?? null,
    observation_scope_tag_key_whitelist: overrides?.observation_scope_tag_key_whitelist ?? null,
  };
}

export function mergeResolvedObservations(
  currentConfig: Record<string, unknown>,
  submittedEdits: ObservationsEdits,
  resolvedConfig: ObservationsConfig
): Record<string, unknown> {
  // A section save must not move another editor's baseline if the response also
  // reflects a concurrent or canonicalized value outside Observations. Config
  // may omit permission-filtered fields, so accepted submitted values become
  // their baseline unless the response supplies a canonical value.
  const next = { ...currentConfig };
  for (const key of OBSERVATIONS_KEYS) {
    if (Object.prototype.hasOwnProperty.call(resolvedConfig, key)) {
      next[key] = resolvedConfig[key] ?? null;
    } else if (
      OVERRIDE_AWARE_OBSERVATIONS_KEYS.includes(
        key as (typeof OVERRIDE_AWARE_OBSERVATIONS_KEYS)[number]
      ) &&
      submittedEdits[key] === null
    ) {
      // After clearing an override, the old resolved value represented that
      // override. Drop it when permissions hide the new parent value.
      delete next[key];
    } else {
      next[key] = submittedEdits[key];
    }
  }
  return next;
}

export function mergeObservationsOverrides(
  currentOverrides: Record<string, unknown>,
  responseOverrides: ObservationsOverridesResponse
): Record<string, unknown> {
  // PATCH returns a complete bank-override snapshot. An absent key therefore
  // means the null tombstone was applied and the bank now inherits its parent.
  const next = { ...currentOverrides };
  for (const key of OVERRIDE_AWARE_OBSERVATIONS_KEYS) {
    const value = responseOverrides?.[key];
    if (value === null || value === undefined) delete next[key];
    else next[key] = value;
  }
  return next;
}

export function reconcileObservationsEdits(
  currentEdits: ObservationsEdits,
  submittedEdits: ObservationsEdits,
  resolvedConfig: ObservationsConfig,
  responseOverrides: ObservationsOverridesResponse
): ObservationsEdits {
  const responseEdits = observationsSlice(
    { ...submittedEdits, ...resolvedConfig },
    responseOverrides
  );
  const reconcileField = <K extends keyof ObservationsEdits>(key: K): ObservationsEdits[K] =>
    Object.is(currentEdits[key], submittedEdits[key]) ? responseEdits[key] : currentEdits[key];

  // Inputs remain editable during a save. Preserve only fields changed after
  // submission, while accepting canonical response values for untouched fields.
  return {
    enable_observations: reconcileField("enable_observations"),
    observation_scope_tag_key_whitelist: reconcileField("observation_scope_tag_key_whitelist"),
    consolidation_llm_batch_size: reconcileField("consolidation_llm_batch_size"),
    consolidation_source_facts_max_tokens: reconcileField("consolidation_source_facts_max_tokens"),
    consolidation_source_facts_max_tokens_per_observation: reconcileField(
      "consolidation_source_facts_max_tokens_per_observation"
    ),
    observations_mission: reconcileField("observations_mission"),
    max_observations_per_scope: reconcileField("max_observations_per_scope"),
  };
}
