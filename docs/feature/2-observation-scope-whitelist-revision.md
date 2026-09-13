# Hindsight Bank-Level Observation Scope Tag-Key Whitelist

## Objective

Add an optional **bank-level tag-key whitelist** that defines which memory tag dimensions are permitted to participate in observation scopes.

The feature must separate two concerns:

```text
Fact tags
    = provenance, filtering, context, retrieval

Observation-scope tag keys
    = semantic dimensions that are allowed to form durable observations
```

The whitelist belongs to the **memory bank configuration**, not to individual clients or retain requests.

A bank may receive memories from many sources:

```text
coding agents
chat ingestion
ticket ingestion
documents
manual uploads
future integrations
```

All producers should obey the same observation-dimension policy.

The existing `observation_scopes` retain parameter remains responsible for choosing **how eligible tags are combined**.

---

# Primary Design

Add an optional bank configuration field:

```json
{
  "observation_scope_tag_key_whitelist": [
    "scope",
    "project",
    "person",
    "topic"
  ]
}
```

A retain request remains unchanged:

```json
{
  "tags": [
    "scope:work",
    "project:example-project",
    "person:alice",
    "topic:authentication",
    "source:chat",
    "channel:engineering"
  ],
  "observation_scopes": "all_combinations"
}
```

The server resolves the bank configuration first:

```text
allowed observation tag keys:

scope
project
person
topic
```

It then filters only the tag set used for observation scope generation:

```text
eligible observation tags:

scope:work
project:example-project
person:alice
topic:authentication
```

The original stored fact must still retain:

```text
scope:work
project:example-project
person:alice
topic:authentication
source:chat
channel:engineering
```

The server then runs the existing `all_combinations` algorithm against only the eligible observation tags.

The whitelist is **not itself an observation strategy**.

---

# Why This Belongs to the Bank

The whitelist defines the bank's semantic ontology:

> Which tag dimensions are meaningful enough to maintain independent durable observations?

That is a property of the memory bank, not of one ingestion client.

Without a bank-level policy, different producers can drift:

```text
coding agent:
project, topic

chat importer:
project, person, channel

ticket importer:
project, ticket

manual upload:
all tags
```

This creates inconsistent observation scopes inside the same bank.

Instead:

```text
                    Memory Bank
                        |
        observation_scope_tag_key_whitelist
                        |
          scope / project / person / topic
                        |
          +-------------+-------------+
          |             |             |
      coding agent     chat        tickets
```

Every producer uses the same semantic dimensions.

---

# Existing `observation_scopes` Remains Per Retain

Do NOT move `observation_scopes` itself into bank configuration.

Existing retain behavior remains:

```text
combined
per_tag
all_combinations
shared
explicit custom scopes
```

Different memories may legitimately use different strategies.

The bank configuration answers:

> Which tag keys are eligible?

The retain request answers:

> How should this memory contribute to scopes built from those eligible tags?

---

# Processing Pipeline

The intended processing order is:

```text
incoming memory
      |
      v
full fact tags
      |
      v
load resolved bank config
      |
      v
observation_scope_tag_key_whitelist configured?
      |
      +-- no --> existing behavior unchanged
      |
      +-- yes
             |
             v
      filter tags by key
             |
             v
      eligible observation tags
             |
             v
      apply observation_scopes strategy
             |
             v
      concrete observation scopes
```

Filtering applies only to observation generation.

Never mutate the actual fact tags.

---

# Bank Configuration Field

Preferred server-side field:

```text
observation_scope_tag_key_whitelist
```

Type:

```text
list[str] | null
```

Semantics:

```text
null / unset
    existing Hindsight behavior;
    every fact tag remains eligible.

[]
    no tagged observation dimensions are permitted.

["project", "topic"]
    only tags whose keys are project or topic
    may participate in tagged observation scopes.
```

Follow current bank-config serialization and PATCH semantics.

If the repository distinguishes field omission from explicit `null`, preserve its existing conventions.

---

# Tag-Key Semantics

For:

```text
project:example-project
```

the tag key is:

```text
project
```

For:

```text
person:alice
```

the key is:

```text
person
```

The whitelist filters by key while preserving the complete tag.

Example:

```text
whitelist:
["project"]

fact tag:
project:example-project

eligible observation tag:
project:example-project
```

Do not rewrite the tag to merely:

```text
project
```

Reuse existing Hindsight tag parsing utilities if available.

Do not introduce competing tag parsing semantics.

---

# Preset Strategy: `combined`

Input tags:

```text
project:example-project
topic:authentication
source:chat
harness:codex
```

Bank whitelist:

```text
project
topic
```

Retain:

```json
{
  "observation_scopes": "combined"
}
```

Eligible tags:

```text
project:example-project
topic:authentication
```

Generated scope:

```json
[
  [
    "project:example-project",
    "topic:authentication"
  ]
]
```

---

# Preset Strategy: `per_tag`

Same input and whitelist:

```json
{
  "observation_scopes": "per_tag"
}
```

Generated scopes:

```json
[
  ["project:example-project"],
  ["topic:authentication"]
]
```

No observation scope is created for:

```text
source:chat
harness:codex
```

Those tags remain on the facts.

---

# Preset Strategy: `all_combinations`

Input:

```text
scope:work
project:example-project
person:alice
topic:authentication
source:chat
channel:engineering
```

Whitelist:

```text
scope
project
person
topic
```

`all_combinations` operates only on:

```text
scope:work
project:example-project
person:alice
topic:authentication
```

It creates all non-empty subsets of those four eligible tags.

It must NOT generate observation scopes containing:

```text
source:chat
channel:engineering
```

This is one of the primary use cases for the feature.

---

# Preset Strategy: `shared`

`shared` always means:

```json
[
  []
]
```

The whitelist does not alter this.

Example:

```text
whitelist:
["project", "topic"]

observation_scopes:
shared
```

Result:

```json
[
  []
]
```

---

# No Eligible Tags

If a whitelist is configured but none of the memory's tags match it, preset strategies must fall back to the explicit shared scope:

```json
[
  []
]
```

Example:

```text
fact tags:
source:chat
harness:codex

bank whitelist:
project
topic
```

For:

```text
combined
per_tag
all_combinations
```

the result is:

```json
[
  []
]
```

Do NOT produce:

```json
[]
```

The empty outer list has different existing Hindsight semantics and must not be used as the shared fallback.

---

# Empty Whitelist

An explicitly configured empty whitelist:

```json
{
  "observation_scope_tag_key_whitelist": []
}
```

means:

> This bank permits no tagged observation dimensions.

Therefore preset strategies:

```text
combined
per_tag
all_combinations
```

must resolve to:

```json
[
  []
]
```

This differs from the field being unset.

---

# Multiple Values for One Key

Input:

```text
project:project-a
project:project-b
topic:authentication
source:chat
```

Whitelist:

```text
project
topic
```

Both project tags remain eligible.

For `combined`:

```json
[
  [
    "project:project-a",
    "project:project-b",
    "topic:authentication"
  ]
]
```

For `per_tag`:

```json
[
  ["project:project-a"],
  ["project:project-b"],
  ["topic:authentication"]
]
```

For `all_combinations`, use the existing combination algorithm over all three eligible tags.

Do not arbitrarily select one value.

---

# Explicit Custom Observation Scopes

Because the whitelist is now a **bank policy**, explicit custom scopes must not bypass it.

Example bank config:

```json
{
  "observation_scope_tag_key_whitelist": [
    "project",
    "topic"
  ]
}
```

Allowed:

```json
[
  ["project:project-a"],
  ["topic:authentication"],
  ["project:project-a", "topic:authentication"],
  []
]
```

Rejected:

```json
[
  ["source:chat"]
]
```

Rejected:

```json
[
  ["project:project-a", "harness:codex"]
]
```

Preferred behavior:

```text
HTTP 400 / validation error
```

with a clear explanation that the scope contains a tag key not permitted by the bank's observation-scope whitelist.

Do NOT silently strip tags from explicit custom scopes.

An explicit empty scope:

```json
[]
```

as one inner scope, i.e.:

```json
[
  []
]
```

is always valid because it represents shared observations and contains no prohibited key.

---

# Manual Consolidation API

Inspect every server entry point that can create observations, not only Retain.

If Hindsight exposes a consolidation endpoint that accepts explicit observation scopes, the bank whitelist must apply there as well.

A caller must not be able to bypass bank policy by:

```text
retain
    → whitelist enforced

manual consolidate
    → arbitrary prohibited scope accepted
```

The invariant is:

> No newly created tagged observation scope may contain a tag key prohibited by the bank's configured whitelist.

Reuse one central validation/filtering implementation wherever possible.

Do not duplicate policy logic across endpoints.

---

# Stored Fact Tags

This is a critical invariant.

Given:

```text
project:project-a
topic:authentication
source:chat
channel:engineering
harness:codex
```

with whitelist:

```text
project
topic
```

stored facts must still contain all five tags.

The whitelist affects only:

```text
observation scope generation
```

It must not affect:

```text
fact persistence
recall filtering
document provenance
UI attribution
source tracing
metadata
```

---

# Observation Complexity

The feature should reduce unnecessary `all_combinations` expansion.

For `n` eligible tags, normal `all_combinations` behavior remains:

```text
2^n - 1
```

scopes.

Example:

```text
6 total fact tags
but only 3 whitelisted tag dimensions

without whitelist:
63 possible scopes

with whitelist:
7 possible scopes
```

Do not change the existing combination algorithm or any existing safety limits.

Only reduce its input tag set.

---

# Bank Config API

Expose the field through the normal bank configuration API.

It must be readable and writable wherever other bank-level observation settings are managed.

Investigate current bank config surfaces including:

```text
create/update bank API
bank config GET/PATCH
Python client
TypeScript/other first-party client if applicable
CLI
bank templates/manifests
Control Plane UI
OpenAPI schema
```

Follow repository conventions rather than inventing a parallel configuration mechanism.

---

# Control Plane UI

If the Control Plane already exposes editable bank configuration, expose this setting there.

Preferred interaction:

```text
Observation Scope Tag-Key Whitelist

[ scope ]
[ project ]
[ person ]
[ topic ]
```

An empty configured list should be distinguishable from an unset field if the existing UI/config model supports that distinction.

Provide concise help text explaining:

> Limits which tag keys may participate in tagged observation scopes. Fact tags themselves are not removed.

Do not build a new configuration page solely for this feature.

Integrate with the existing bank configuration UI.

---

# Bank Templates / Manifests

If bank configuration is represented in Hindsight bank templates/manifests, include:

```text
observation_scope_tag_key_whitelist
```

in the schema and apply/export behavior.

A bank template should be able to define the observation ontology consistently.

Do not introduce separate template-only naming.

---

# Coding-Agent Integration

Remove the experimental client-side whitelist configuration from the fork.

Remove:

```json
{
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

and any previous experimental:

```text
tag_key
tag_keys
```

scope modes.

The coding-agent integration should retain only the existing strategy setting:

```json
{
  "observationScopes": "all_combinations"
}
```

or another existing supported strategy.

The bank controls eligible observation dimensions.

The coding-agent should not duplicate the bank whitelist.

---

# Coding-Agent Bank Management

The coding-agent's `manageBankConfig` behavior must not overwrite an existing bank whitelist.

If the integration automatically creates or enriches bank configuration, follow its current additive semantics.

Do not automatically invent a default whitelist for users.

The feature should remain opt-in at the bank level.

---

# Other Clients / Integrations

No ingestion client should need to understand this new policy.

A chat importer may retain:

```text
project:project-a
person:alice
source:chat
channel:engineering
```

A ticket importer may retain:

```text
project:project-a
topic:authentication
source:ticket
ticket:ABC-123
```

A coding agent may retain:

```text
project:project-a
topic:authentication
source:chat
harness:codex
```

All clients simply send complete useful tags.

The bank decides which keys are observation dimensions.

---

# Backward Compatibility

This feature must be fully opt-in.

When:

```text
observation_scope_tag_key_whitelist
```

is unset, Hindsight must behave exactly as before.

No defaults should change.

Existing uses of:

```text
combined
per_tag
all_combinations
shared
custom scopes
```

must retain their existing semantics when the bank has no whitelist.

---

# Existing Observations

Changing the bank whitelist must NOT automatically rewrite historical observations.

Example:

```text
old observations:
["project:project-a", "source:chat"]

new bank whitelist:
["project", "topic"]
```

The old observation remains where it was created.

Only future scope generation uses the new policy.

Do not trigger:

```text
observation deletion
reconsolidation
fact rewriting
bank-wide migration
```

when the config changes.

Historical migration is a separate operation.

Document this clearly.

---

# Existing Retained Documents

Do not rewrite existing fact tags.

The feature is specifically intended to let rich provenance tags remain on facts.

Only future observation-scope generation is affected unless a user explicitly performs a separate reconsolidation/migration.

---

# Configuration Changes Over Time

Changing:

```json
{
  "observation_scope_tag_key_whitelist": [
    "project"
  ]
}
```

to:

```json
{
  "observation_scope_tag_key_whitelist": [
    "project",
    "topic"
  ]
}
```

changes future eligible scopes.

It does not retroactively modify already-derived observations.

The documentation must make this temporal behavior explicit.

---

# Suggested Server Architecture

Prefer a reusable policy helper conceptually equivalent to:

```text
resolve_observation_scope_tags(
    fact_tags,
    bank_config
)
```

and:

```text
validate_observation_scope(
    scope,
    bank_config
)
```

Responsibilities:

```text
preset scopes:
    filter fact tags before expansion

custom/manual scopes:
    validate that every tag key is permitted
```

Do not scatter whitelist parsing across:

```text
retain
batch retain
consolidation
MCP
clients
```

The policy belongs in the shared server/engine layer.

---

# Investigation Before Implementation

Before editing code, inspect the current fork and upstream implementation.

Locate:

```text
bank configuration models
bank configuration persistence
bank config API
bank config client methods
observation scope expansion
combined
per_tag
all_combinations
shared
custom scope handling
manual consolidation API
retain pipeline
batch retain pipeline
fact tag persistence
Control Plane bank settings
bank template schema
coding-agent observationScopes handling
experimental observationScopesParam/tag_keys code
relevant tests
generated OpenAPI/client workflows
documentation generation workflows
```

Do not assume paths from this document are current.

---

# Migration from the Experimental Implementation

The fork may currently contain an unfinished or completed implementation based on:

```json
{
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

or:

```json
{
  "observationScopes": {
    "mode": "tag_keys",
    "tagKeys": ["project"]
  }
}
```

Those are superseded.

Remove them unless they have already become a released compatibility contract.

This fork work has not been accepted upstream, so prefer the cleaner bank-level architecture rather than preserving experimental APIs.

Reuse useful underlying filtering/test code where appropriate.

---

# Required Server Tests

## No whitelist

Verify exact legacy behavior for:

```text
combined
per_tag
all_combinations
shared
custom scopes
```

---

## Whitelisted `combined`

Fact tags:

```text
project:project-a
topic:authentication
source:chat
harness:codex
```

Whitelist:

```text
project
topic
```

Expected:

```json
[
  [
    "project:project-a",
    "topic:authentication"
  ]
]
```

---

## Whitelisted `per_tag`

Expected:

```json
[
  ["project:project-a"],
  ["topic:authentication"]
]
```

---

## Whitelisted `all_combinations`

Expected:

```json
[
  ["project:project-a"],
  ["topic:authentication"],
  ["project:project-a", "topic:authentication"]
]
```

Use current canonical ordering.

---

## `shared`

Whitelist present or absent:

```json
[
  []
]
```

---

## No Matching Tags

Fact:

```text
source:chat
harness:codex
```

Whitelist:

```text
project
topic
```

For preset modes:

```text
combined
per_tag
all_combinations
```

expected:

```json
[
  []
]
```

---

## Explicit Empty Whitelist

Whitelist:

```json
[]
```

Preset modes resolve to:

```json
[
  []
]
```

---

## Stored Fact Tags

Verify that filtering observation dimensions does not mutate stored memory tags.

---

## Multiple Values Per Key

Verify all matching tags survive filtering.

---

## Custom Scope Allowed

Whitelist:

```text
project
topic
```

Custom:

```json
[
  ["project:project-a", "topic:authentication"]
]
```

accepted.

---

## Custom Scope Rejected

Custom:

```json
[
  ["project:project-a", "source:chat"]
]
```

rejected because `source` is not whitelisted.

---

## Manual Consolidation Policy

If manual consolidation can specify scopes, verify it cannot create a prohibited tagged scope.

---

## Different Banks

Bank A:

```text
whitelist:
project
```

Bank B:

```text
whitelist:
person
topic
```

The same retained tags must resolve differently according to each bank's configuration.

This confirms policy is bank-scoped rather than global server state.

---

# Bank Config Tests

Verify:

```text
create bank with whitelist
read bank config
update whitelist
clear/unset whitelist
explicit empty whitelist
config persistence
template import/export if applicable
```

Follow existing PATCH/null semantics.

---

# Control Plane Tests

If UI support is added, verify:

```text
load configured whitelist
edit values
save
reload
clear to empty
unset if supported
```

Do not require extensive end-to-end browser tests if the repository's normal UI testing strategy is lighter.

Follow existing patterns.

---

# Documentation

Update generic Hindsight documentation.

Explain:

```text
tags
    ↓
bank observation tag-key whitelist
    ↓
observation_scopes strategy
    ↓
concrete observation scopes
```

Clearly distinguish:

```text
fact tags
```

from:

```text
observation dimensions
```

Include an `all_combinations` example showing provenance tags retained on facts but excluded from scope generation.

Document:

```text
unset whitelist
empty whitelist
no matching tags
shared
custom scope validation
historical observations
```

---

# Upstream PR Rationale

Frame the feature generically:

> Hindsight tags serve both retrieval/provenance and observation scoping today. In multi-source banks, those roles often differ. High-cardinality or provenance tags such as source, channel, session, harness, or document identifiers are useful on facts but can produce fragmented or exponentially large observation scope sets. A bank-level tag-key whitelist lets the bank define which semantic tag dimensions may participate in observations while preserving all fact tags for recall and provenance.

Emphasize:

```text
one bank
many ingestion clients
one observation ontology
```

The feature is not specific to coding agents.

It is especially useful with:

```text
all_combinations
```

because it bounds the dimensionality before combination expansion.

---

# Non-Goals

Do not include:

```text
new observation strategies
client-specific whitelists
automatic historical migration
observation deletion/rebuild tooling
tag inference
automatic topic classification
Slack/ticket integrations
Knowledge Page redesign
Mental Model redesign
RBAC/authentication
```

Keep this PR focused on bank-level observation-dimension policy.

---

# Suggested Commit Structure

Prefer small reviewable commits such as:

```text
feat(config): add observation scope tag-key whitelist

feat(consolidation): enforce bank observation tag policy

feat(control-plane): expose observation tag-key whitelist

test: cover bank observation scope whitelist

docs: document bank-level observation dimensions

refactor(coding-agents): remove experimental client whitelist
```

Adapt to actual repository architecture.

Do not create artificial commits merely to match this list.

---

# Definition of Done

The feature is complete when:

1. A bank can configure `observation_scope_tag_key_whitelist`.
2. The field is optional and unset preserves exact legacy behavior.
3. Stored fact tags are never removed by the whitelist.
4. `combined` uses only eligible tags.
5. `per_tag` uses only eligible tags.
6. `all_combinations` uses only eligible tags.
7. `shared` remains unchanged.
8. No eligible tags resolves to `[[]]`.
9. An explicitly empty whitelist resolves preset modes to `[[]]`.
10. Multiple values belonging to a whitelisted key remain eligible.
11. Explicit custom scopes using prohibited keys are rejected.
12. Manual observation creation/consolidation cannot bypass the bank policy.
13. Different banks can have different whitelists.
14. The field is exposed through normal bank configuration APIs/clients.
15. Bank templates/manifests support it where applicable.
16. Control Plane support is added if bank config is normally editable there.
17. Experimental client-side whitelist/tag-key scope features are removed.
18. Coding-agent `observationScopes` continues working without owning the whitelist.
19. Existing historical observations are not automatically changed.
20. Tests and documentation are complete.
21. The resulting design is generic and suitable for upstream submission.

---

# Primary Invariant

The bank decides which tag dimensions may become beliefs.

```text
FACT
──────────────────────────
scope:work
project:project-a
topic:authentication
source:chat
channel:engineering
harness:codex

all remain stored

             ↓

BANK POLICY
──────────────────────────
observation_scope_tag_key_whitelist

scope
project
topic

             ↓

ELIGIBLE OBSERVATION TAGS
──────────────────────────
scope:work
project:project-a
topic:authentication

             ↓

RETAIN STRATEGY
──────────────────────────
all_combinations

             ↓

OBSERVATIONS
──────────────────────────
only semantic bank-approved
dimensions participate
```

Ingestion clients provide facts and provenance.

The bank owns the observation ontology.
