# Hindsight Observation Scope Tag-Key Whitelist

## Objective

Add a generic, server-supported **tag-key whitelist for observation scope generation**.

The feature must allow callers to keep rich tags on retained facts for provenance and recall filtering while restricting which tag dimensions participate in observation consolidation.

This should compose with Hindsight's existing observation-scope strategies rather than introducing a new strategy.

Target configuration in `@vectorize-io/hindsight-coding-agents`:

```json
{
  "observationScopes": "combined",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

Future example:

```json
{
  "observationScopes": "all_combinations",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project", "user"]
  }
}
```

The implementation should be designed as a generic Hindsight feature suitable for an upstream PR.

---

# Background

A retained memory may have tags such as:

```text
project:example
user:gde
harness:codex
source:chat
knowledge:decision
```

All of these tags are useful on the underlying facts.

For example:

- `project:*` identifies the repository/project.
- `user:*` may identify the contributing user.
- `harness:*` records which coding agent wrote the memory.
- `source:*` records the source type.
- `knowledge:*` records extracted knowledge classification.

However, not every tag should necessarily create an observation boundary.

Currently, existing strategies operate over the retained item's entire tag set.

For example:

```json
{
  "observation_scopes": "combined"
}
```

with:

```text
project:example
harness:codex
source:chat
```

produces conceptually:

```json
[
  ["project:example", "harness:codex", "source:chat"]
]
```

This fragments observations based on provenance.

The desired behavior is to preserve all fact tags while allowing observation scope generation to consider only selected tag keys.

---

# Core Design

Observation scope generation should conceptually become a two-stage process:

```text
original fact tags
       ↓
optional tag-key whitelist
       ↓
eligible observation tags
       ↓
existing observation scope strategy
       ↓
concrete observation scopes
```

The two concerns must remain orthogonal:

```text
observationScopes
    = HOW eligible tags become scopes

observationScopesParam.tagKeyWhitelist
    = WHICH tag dimensions are eligible
```

Do not introduce a new `tag_keys` observation scope mode.

---

# Public Configuration

## Coding-Agent JSON

Support:

```json
{
  "observationScopes": "<existing mode>",
  "observationScopesParam": {
    "tagKeyWhitelist": ["tagKey1", "tagKey2"]
  }
}
```

Example:

```json
{
  "observationScopes": "combined",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

Future team-oriented example:

```json
{
  "observationScopes": "all_combinations",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project", "user"]
  }
}
```

`observationScopesParam` must be optional.

When absent, behavior must remain exactly as it is upstream today.

---

# Server API

Expose the equivalent concept in the Retain API.

Follow existing API naming conventions.

Conceptually:

```json
{
  "tags": [
    "project:example",
    "user:gde",
    "harness:codex",
    "source:chat"
  ],

  "observation_scopes": "all_combinations",

  "observation_scopes_param": {
    "tag_key_whitelist": [
      "project",
      "user"
    ]
  }
}
```

Exact Python/Pydantic naming should follow current repository conventions.

Client SDKs should expose idiomatic names for their languages.

For example, TypeScript/coding-agent configuration:

```text
observationScopesParam.tagKeyWhitelist
```

while the JSON HTTP API may use:

```text
observation_scopes_param.tag_key_whitelist
```

Do not invent inconsistent casing merely to match this specification; follow existing server/API conventions.

---

# Supported Observation Scope Strategies

The whitelist must compose with:

```text
combined
per_tag
all_combinations
shared
```

Do not create replacement algorithms for these modes.

Filter the tags first, then invoke the existing strategy implementation.

---

# `combined`

Given:

```text
tags:

project:example
user:gde
harness:codex
source:chat
```

and:

```json
{
  "observation_scopes": "combined",
  "observation_scopes_param": {
    "tag_key_whitelist": ["project", "user"]
  }
}
```

eligible tags become:

```text
project:example
user:gde
```

and the generated scope is:

```json
[
  ["project:example", "user:gde"]
]
```

---

# `per_tag`

Using the same retained tags and whitelist:

```json
{
  "observation_scopes": "per_tag",
  "observation_scopes_param": {
    "tag_key_whitelist": ["project", "user"]
  }
}
```

the result must be:

```json
[
  ["project:example"],
  ["user:gde"]
]
```

`harness:*` and `source:*` remain on the facts but do not participate in observations.

---

# `all_combinations`

Using:

```json
{
  "observation_scopes": "all_combinations",
  "observation_scopes_param": {
    "tag_key_whitelist": ["project", "user"]
  }
}
```

the result is:

```json
[
  ["project:example"],
  ["user:gde"],
  ["project:example", "user:gde"]
]
```

Existing combination-generation behavior should be reused after filtering.

Do not implement a second combinations algorithm unless current architecture requires it.

---

# `shared`

`shared` always represents the global/untagged observation scope:

```json
[
  []
]
```

A tag-key whitelist does not change that meaning.

For example:

```json
{
  "observation_scopes": "shared",
  "observation_scopes_param": {
    "tag_key_whitelist": ["project"]
  }
}
```

still produces:

```json
[
  []
]
```

It is acceptable either to ignore `tagKeyWhitelist` for `shared` or treat it as a no-op during normalization.

Do not change the existing meaning of `shared`.

---

# Empty Result / Fallback Semantics

This behavior is important and must be explicitly implemented and tested.

Suppose:

```text
tags:

source:chat
harness:codex
```

and:

```json
{
  "observation_scopes": "combined",
  "observation_scopes_param": {
    "tag_key_whitelist": ["project"]
  }
}
```

No retained tag matches the whitelist.

The effective observation tag set is therefore empty.

The required default behavior is:

```text
fallback to shared
```

which means:

```json
[
  []
]
```

Do NOT pass:

```json
[]
```

The empty outer list and the shared scope are not equivalent in the current Hindsight implementation.

The intended semantics are:

```text
whitelist exists
        ↓
filter tags
        ↓
zero eligible tags
        ↓
explicit shared scope
        ↓
[[]]
```

This behavior applies consistently to:

```text
combined
per_tag
all_combinations
```

when a whitelist is configured and no tags survive filtering.

---

# Empty Whitelist

Treat:

```json
{
  "tag_key_whitelist": []
}
```

as a valid whitelist that permits no tag keys.

Therefore:

```text
eligible tags = []
```

and the result for non-`shared` preset modes is:

```json
[
  []
]
```

Do not interpret an explicitly empty whitelist as equivalent to the parameter being absent.

These must differ:

```text
parameter absent
    → existing behavior using all tags

tag_key_whitelist: []
    → no tags eligible
    → shared observation scope
```

---

# Tag-Key Matching

A whitelist entry refers to a tag **key**, not a complete tag.

Example:

```text
tag:
project:example

key:
project

value:
example
```

With:

```json
{
  "tag_key_whitelist": ["project"]
}
```

the complete original tag:

```text
project:example
```

is retained as the eligible observation tag.

Do not transform it into just:

```text
project
```

The whitelist selects tags; it does not rewrite their values.

---

# Tag Parsing

Inspect the repository for an existing tag parsing/key utility and reuse it if present.

Avoid introducing a competing interpretation of tags.

If no existing implementation exists, the expected conceptual behavior is:

```text
project:example
→ key "project"

user:gde
→ key "user"
```

Use the portion before the first `:` as the key.

For unusual/bare tags without `:`, preserve existing Hindsight semantics.

If a special decision is required for bare tags, document and test it.

Do not make assumptions before inspecting current tag utilities.

---

# Multiple Values for the Same Key

A retained memory may theoretically contain:

```text
project:foo
project:bar
user:gde
```

with:

```json
{
  "tag_key_whitelist": ["project", "user"]
}
```

Both matching `project:*` tags should remain eligible.

The whitelist filters **keys**, not cardinality.

Therefore eligible tags should conceptually be:

```text
project:foo
project:bar
user:gde
```

and the selected observation strategy determines what happens next.

For `combined`:

```json
[
  ["project:foo", "project:bar", "user:gde"]
]
```

For `per_tag`:

```json
[
  ["project:foo"],
  ["project:bar"],
  ["user:gde"]
]
```

For `all_combinations`, reuse normal combination semantics.

Do not silently select one value.

---

# Ordering and Determinism

Preserve existing observation-scope tag ordering semantics wherever possible.

Do not introduce unstable ordering based on hash maps/sets.

Tests should compare deterministic normalized output.

If the current scope implementation already sorts/canonicalizes tags, continue using that behavior.

---

# Custom Explicit Observation Scopes

Hindsight also supports explicit custom scopes such as:

```json
{
  "observation_scopes": [
    ["project:example"],
    ["user:gde"],
    ["project:example", "user:gde"]
  ]
}
```

These scopes are already explicit instructions.

The whitelist must NOT alter them.

For example, do not transform:

```json
[
  ["project:example", "harness:codex"]
]
```

because of:

```json
{
  "tag_key_whitelist": ["project"]
}
```

The caller explicitly requested that scope.

Preferred validation behavior:

```text
explicit custom scope list
+
observation_scopes_param.tag_key_whitelist
→ reject as an invalid/ambiguous combination
```

If repository compatibility conventions make rejection undesirable, document an alternative clearly.

Do not silently filter explicitly supplied scopes.

---

# Backward Compatibility

This feature must be completely additive.

Existing calls such as:

```json
{
  "observation_scopes": "combined"
}
```

must behave exactly as before.

Likewise:

```json
{
  "observation_scopes": "per_tag"
}
```

```json
{
  "observation_scopes": "all_combinations"
}
```

```json
{
  "observation_scopes": "shared"
}
```

and existing explicit custom lists.

The absence of:

```text
observation_scopes_param
```

must mean:

```text
use existing behavior
```

Do not change the server's default observation mode.

Do not change existing clients' defaults.

---

# Coding-Agent Integration

Replace the custom client-side `tag_keys` observation mode developed in this fork.

The coding-agent integration should instead rely on the generic server feature.

Target configuration:

```json
{
  "observationScopes": "combined",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

For the user's current shared-bank setup:

```json
{
  "serverMode": "self-hosted",
  "apiUrl": "http://hindsight.bionicbox.net:18888",
  "bankId": "gde.satrigraha",

  "retainTags": [
    "project:{gitProject}"
  ],

  "retainMetadata": {
    "repo": "{gitProject}"
  },

  "observationScopes": "combined",

  "observationScopesParam": {
    "tagKeyWhitelist": [
      "project"
    ]
  },

  "autoSeed": false,
  "autoReflect": false,
  "autoUpdate": false
}
```

A retained coding-agent document may still have:

```text
project:example
source:chat
harness:codex
knowledge:decision
```

Its source facts retain all four tags.

The server receives the whitelist:

```text
project
```

and generates:

```json
[
  ["project:example"]
]
```

for observations.

---

# Future Team Configuration

The feature should support a future configuration such as:

```json
{
  "observationScopes": "all_combinations",
  "observationScopesParam": {
    "tagKeyWhitelist": [
      "project",
      "user"
    ]
  }
}
```

Given:

```text
project:example
user:gde
harness:codex
source:chat
```

the generated scopes should be:

```json
[
  ["project:example"],
  ["user:gde"],
  ["project:example", "user:gde"]
]
```

For another teammate:

```text
project:example
user:alice
```

the server creates:

```json
[
  ["project:example"],
  ["user:alice"],
  ["project:example", "user:alice"]
]
```

This means both users contribute to:

```text
project:example
```

while retaining separate user and project+user observations.

This behavior is intentional.

---

# Coding-Agent `per_source`

The coding-agent integration currently has a special client-side:

```text
per_source
```

mode.

This is not a normal server observation-scope preset.

Do not accidentally alter its existing semantics while implementing this feature.

Investigate how `per_source` currently produces explicit per-document scopes.

For the initial implementation, `observationScopesParam.tagKeyWhitelist` does not need to compose with `per_source`.

Preferred behavior is to reject or clearly validate an unsupported combination rather than silently ignoring the parameter.

Example unsupported configuration:

```json
{
  "observationScopes": "per_source",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

If there is an obvious, backward-compatible way to support it cleanly, report the design before expanding scope.

Do not let this block the generic server feature.

---

# Server Implementation Strategy

Do not rewrite the existing observation-scope expansion machinery.

Find the current code responsible for converting:

```text
combined
per_tag
all_combinations
shared
```

into concrete scopes.

Conceptually change:

```python
scopes = expand_observation_scopes(
    mode=observation_scopes,
    tags=tags,
)
```

into:

```python
eligible_tags = tags

if observation_scopes_param.tag_key_whitelist is not None:
    eligible_tags = filter_tags_by_key(
        tags,
        observation_scopes_param.tag_key_whitelist,
    )

if whitelist_was_configured and len(eligible_tags) == 0:
    scopes = [[]]
else:
    scopes = expand_observation_scopes(
        mode=observation_scopes,
        tags=eligible_tags,
    )
```

This is conceptual pseudocode only.

Inspect current implementation and integrate at the narrowest appropriate layer.

Important:

```text
facts keep original tags
```

Only the tags supplied to the observation-scope expansion logic are filtered.

Do NOT modify the fact's stored tag list.

---

# API Schema

Add a typed parameter object rather than a loose dictionary.

Conceptually:

```python
class ObservationScopesParam(...):
    tag_key_whitelist: list[str] | None = None
```

Use the repository's actual schema framework and naming conventions.

This object should be extensible for future strategy parameters without changing the top-level Retain API shape.

That extensibility is one reason for using:

```text
observationScopesParam
```

rather than adding:

```text
observationScopeTagKeys
```

as another unrelated top-level property.

Do not add speculative parameters now.

Only implement:

```text
tagKeyWhitelist
```

in the initial feature.

---

# SDK Support

Identify every first-party SDK/client that exposes Retain API observation scope options.

Update the relevant request types/models to expose the new parameter.

At minimum inspect:

- Python client;
- TypeScript/JavaScript clients;
- coding-agent integration client;
- generated OpenAPI clients if applicable;
- MCP retain tool schema if it exposes observation-scope configuration.

Follow the repository's code-generation workflow where clients are generated.

Do not manually edit generated files if upstream provides a generator.

---

# MCP Consideration

Inspect whether Hindsight's generic MCP `retain` tool exposes:

```text
observation_scopes
```

directly.

If so, expose the new parameter consistently if the MCP schema represents the underlying Retain API.

Do not add coding-agent-specific concepts to the generic MCP server.

---

# Documentation

Update the Retain API documentation.

Explain the processing order:

```text
tags
→ tagKeyWhitelist
→ observationScopes strategy
→ concrete scopes
```

Include examples for:

```text
combined
per_tag
all_combinations
```

Explain clearly that the original fact tags remain unchanged.

Document the empty-result behavior:

> If `tagKeyWhitelist` is configured and no retained tags match the whitelist, observation consolidation falls back to the shared/untagged scope.

Explicitly distinguish:

```text
[[]]
```

from:

```text
[]
```

Update coding-agent documentation with the shared multi-repository use case.

Example:

```json
{
  "bankId": "shared-engineering-bank",

  "retainTags": [
    "project:{gitProject}"
  ],

  "observationScopes": "combined",

  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

Explain that provenance tags such as:

```text
source:*
harness:*
knowledge:*
```

remain available for Recall but no longer fragment observations.

---

# Tests — Server

Add focused unit tests around scope expansion/filtering.

## No whitelist

Verify all existing behavior remains unchanged.

### Combined

```text
tags:
project:foo
source:chat

→

[["project:foo", "source:chat"]]
```

### Per-tag

```text
→

[
  ["project:foo"],
  ["source:chat"]
]
```

### All combinations

Verify current output exactly.

### Shared

```text
→

[[]]
```

---

# Tests — Whitelisted Combined

Input:

```text
tags:
project:foo
user:gde
source:chat
harness:codex
```

Whitelist:

```text
project
```

Expected:

```json
[
  ["project:foo"]
]
```

Whitelist:

```text
project
user
```

Expected:

```json
[
  ["project:foo", "user:gde"]
]
```

---

# Tests — Whitelisted `per_tag`

Whitelist:

```text
project
user
```

Expected:

```json
[
  ["project:foo"],
  ["user:gde"]
]
```

No `source:*` or `harness:*` scopes should be generated.

---

# Tests — Whitelisted `all_combinations`

Whitelist:

```text
project
user
```

Expected:

```json
[
  ["project:foo"],
  ["user:gde"],
  ["project:foo", "user:gde"]
]
```

Use the repository's canonical ordering.

---

# Tests — No Matching Tags

Input:

```text
source:chat
harness:codex
```

Whitelist:

```text
project
user
```

For:

```text
combined
per_tag
all_combinations
```

expected result:

```json
[
  []
]
```

Explicitly verify the implementation does NOT produce:

```json
[]
```

---

# Tests — Empty Whitelist

Input:

```text
project:foo
source:chat
```

Whitelist:

```json
[]
```

Expected:

```json
[
  []
]
```

---

# Tests — Stored Fact Tags

Verify whitelist filtering does not mutate stored fact tags.

Given:

```text
project:foo
source:chat
harness:codex
```

with whitelist:

```text
project
```

the extracted/stored facts must still carry:

```text
project:foo
source:chat
harness:codex
```

Only observation scopes are restricted.

This is a critical invariant.

---

# Tests — Duplicate / Multiple Key Values

Input:

```text
project:foo
project:bar
user:gde
source:chat
```

Whitelist:

```text
project
user
```

Verify all matching tags survive filtering and normal strategy semantics apply.

Do not silently select one `project:*`.

---

# Tests — Custom Explicit Scopes

Verify existing explicit lists remain unchanged.

If parameters combined with explicit custom scopes are rejected, add a validation test confirming the error.

---

# Coding-Agent Tests

Add tests confirming:

```json
{
  "observationScopes": "combined",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

is:

1. parsed correctly;
2. merged correctly through config layering;
3. passed to the Retain API;
4. compatible with `{gitProject}`;
5. independent of provenance tags.

Given:

```text
project:example
harness:claude-code
source:chat
```

verify the coding agent no longer needs to calculate custom project scope lists itself.

The server owns the filtering semantics.

---

# Config Layering

The coding-agent config currently supports layering such as:

```text
defaults
environment
top-level config
harness override
bank override
```

Ensure `observationScopesParam` follows the repository's existing object/map merge conventions.

Do not accidentally replace unrelated nested properties if future parameters are added.

If map-valued settings are file-only under the existing config system, `observationScopesParam` may initially remain file-only.

Do not invent awkward environment-variable serialization merely to support this feature.

Document the limitation if applicable.

---

# Migration from the Fork's Existing `tag_keys`

The current fork may already contain the earlier client-side implementation:

```json
{
  "observationScopes": {
    "mode": "tag_keys",
    "tagKeys": ["project"],
    "fallback": "shared"
  }
}
```

Replace that experimental API before upstream submission.

The new form is:

```json
{
  "observationScopes": "combined",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

Remove code that precomputes custom scope lists specifically for `tag_keys`.

Do not retain two competing ways to accomplish the same behavior unless backward compatibility with an already-released fork version is required.

This fork feature has not been released upstream, so prefer the cleaner final design.

---

# Historical Observations

This feature affects observation scope generation for new Retain operations.

It must not automatically rewrite previously consolidated observations.

Do not trigger a full-bank migration when configuration changes.

Existing observations created under:

```text
combined
```

remain in their historical scopes until an explicit migration/rebuild is performed.

Historical migration is a separate concern.

Document this.

---

# Performance

The whitelist itself should be inexpensive.

Filtering should be approximately linear in the number of retained tags.

Do not introduce additional LLM calls.

For `all_combinations`, complexity remains governed by the number of eligible tags.

The whitelist may significantly reduce combination count.

Example:

```text
original tags = 6
all_combinations = 63 scopes

whitelisted eligible tags = 2
all_combinations = 3 scopes
```

This is a desirable side effect.

Do not modify existing safeguards around excessive scope counts if such safeguards already exist.

---

# Upstream-Friendly Scope

Keep the first PR focused.

Required:

```text
server Retain API
scope generation
API schema
relevant SDK/client plumbing
coding-agent config
tests
documentation
```

Do not bundle:

- project Knowledge Page provisioning;
- Mental Model provisioning;
- historical observation migration;
- shared-bank export/import tooling;
- unrelated coding-agent refactors;
- new observation strategies.

Those should remain separate commits/PRs.

---

# Investigation Before Implementation

Before editing code, inspect current upstream/fork state.

Locate:

```text
Retain request API schema
observation_scopes model/type
scope expansion function
combined implementation
per_tag implementation
all_combinations implementation
shared implementation
Python client Retain options
other first-party client Retain options
MCP retain schema
coding-agent RawConfig / resolved config
coding-agent retain request builder
per_source implementation
related tests
generated API/client workflows
documentation generation workflows
```

Also inspect the current fork diff to identify the experimental `tag_keys` work that should be replaced.

Do not assume file paths from previous discussions are still current.

---

# Initial Investigation Report

Before implementation, report briefly:

1. server files/symbols responsible for observation-scope expansion;
2. where Retain API schemas are defined;
3. whether clients are generated or manually maintained;
4. which SDKs require updates;
5. coding-agent config path and retain call path;
6. how the experimental `tag_keys` implementation currently works;
7. how `per_source` should remain isolated from this change;
8. any discrepancy between this specification and current code;
9. proposed minimal patch boundaries.

Then proceed without waiting unless a material incompatibility is discovered.

---

# Suggested Implementation Order

## Phase 1 — Server core

Implement:

```text
observation_scopes_param.tag_key_whitelist
```

and filtering before existing strategy expansion.

Add exhaustive server tests.

Do not touch coding-agent behavior until the server implementation is passing.

## Phase 2 — API / clients

Expose the new parameter through appropriate server schema and first-party clients.

Run generated-client workflows where applicable.

## Phase 3 — Coding-agent integration

Remove the experimental `tag_keys` mode.

Add:

```text
observationScopesParam.tagKeyWhitelist
```

and forward it to Retain.

Add config-layering and integration tests.

## Phase 4 — Documentation

Update generic Hindsight API documentation first.

Then update coding-agent documentation.

Run any documentation/skill generators required by the repository.

## Phase 5 — Full review

Run focused tests first, then broader relevant suites.

Review the complete diff specifically for backward compatibility.

---

# Suggested Commit Structure

Prefer small reviewable commits such as:

```text
feat(api): add observation scope tag-key whitelist

feat(clients): expose observation scope parameters

feat(coding-agents): support observation scope parameters

test: cover observation scope tag-key filtering

docs: document observation scope tag-key whitelist
```

Exact commit grouping can follow repository conventions.

Avoid unrelated cleanup.

---

# Definition of Done

The feature is complete when:

1. The Retain API accepts an optional observation-scope parameter object.
2. The object supports `tagKeyWhitelist` / `tag_key_whitelist`.
3. Original fact tags remain untouched.
4. `combined` operates only on whitelisted tag keys when configured.
5. `per_tag` operates only on whitelisted tag keys when configured.
6. `all_combinations` operates only on whitelisted tag keys when configured.
7. `shared` retains its existing `[[]]` semantics.
8. If the whitelist leaves zero eligible tags, the result is explicitly `[[]]`.
9. An empty whitelist also produces shared scope.
10. No whitelist preserves exact current behavior.
11. Explicit custom scope lists remain literal and are not silently filtered.
12. Multiple matching values for one tag key are preserved.
13. Relevant first-party clients expose the parameter.
14. Coding-agent configuration supports:

```json
{
  "observationScopes": "combined",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

15. The experimental `tag_keys` mode is removed from the fork.
16. Existing `per_source` behavior remains unchanged.
17. Existing observations are not automatically migrated.
18. Unit/integration tests pass.
19. Documentation is updated.
20. The resulting patch is small and generic enough to reasonably submit upstream.

---

# Primary Design Principle

The feature should enforce this separation:

```text
FACT TAGS
─────────────────────────────
project:example
user:gde
source:chat
harness:codex
knowledge:decision

All remain stored and usable
for recall/provenance.

              ↓

OBSERVATION TAG FILTER
─────────────────────────────
tagKeyWhitelist:
  project
  user

              ↓

ELIGIBLE TAGS
─────────────────────────────
project:example
user:gde

              ↓

EXISTING STRATEGY
─────────────────────────────
combined
per_tag
all_combinations
shared

              ↓

OBSERVATION SCOPES
─────────────────────────────
Only desired semantic
dimensions influence beliefs.
```

The whitelist is not itself an observation strategy.

It is a parameter controlling the input tag set used by existing observation strategies.
