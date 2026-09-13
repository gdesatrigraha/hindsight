You are the lead coding agent and coordinator for this task.

The complete revised specification is:

`docs/gde-feature-observation-scope-whitelisting.md`

Read it completely before making changes.

The architecture has changed from the earlier design.

The tag-key whitelist is no longer a per-client/per-retain parameter such as:

```json
{
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

It must become a **bank-level configuration policy**.

The target concept is:

```text
bank config:
observation_scope_tag_key_whitelist

        +

retain request:
observation_scopes

        ↓

filter eligible observation tags
        ↓
apply existing observation strategy
```

Your job is to migrate the current fork implementation to this design, complete all affected server/config/client/UI/docs work, test it thoroughly, and run an independent review/fix loop until no substantive concerns remain.

## Role

Act as coordinator/supervisor.

Use subagents for bounded investigation and implementation tasks where practical.

Prefer cheaper/faster OpenAI coding subagents for:

- repository reconnaissance;
- locating bank-config paths;
- locating observation-scope expansion;
- implementing isolated model/schema changes;
- focused test writing;
- client plumbing;
- Control Plane UI changes;
- documentation;
- independent review.

The main agent remains responsible for:

- architecture;
- deciding exact integration points;
- resolving discrepancies between the specification and current source;
- coordinating overlapping edits;
- reviewing every delegated change;
- final test coverage;
- upstream suitability;
- the review/fix loop.

Do not hand the entire task to one subagent.

Do not allow multiple agents to concurrently modify the same implementation area without explicit ownership.

## Protect existing work

Before editing:

```text
inspect git status
inspect current branch
inspect current diff
identify previous experimental whitelist implementation
```

Do not discard existing user work.

Do not use destructive reset/checkout commands.

Some previous work may be reusable even though its API shape is obsolete.

## Phase 0 — Repository reconnaissance

Delegate read-only investigation first.

Have subagents identify exact current paths/symbols for:

```text
bank configuration model
bank config persistence
bank GET/PATCH/create APIs
bank client methods
bank templates/manifests
Control Plane bank config
observation scope expansion
combined
per_tag
all_combinations
shared
custom scopes
manual consolidate endpoint
retain pipeline
batch retain
fact tag persistence
coding-agent observationScopes config
experimental observationScopesParam/tag_keys work
OpenAPI/client generation
tests
documentation generators
```

Also determine whether observation scopes are concretized:

```text
at retain time
at consolidation time
or partly at both
```

This matters for where bank policy must be enforced.

Scouts must not edit code.

## Investigation checkpoint

Before implementation, report briefly:

- current bank config call path;
- current observation-scope expansion call path;
- where concrete scopes become associated with retained memories;
- all observation-creation paths that could bypass the policy;
- how explicit custom scopes work;
- how manual consolidation accepts scopes;
- where stored fact tags are finalized;
- which clients/config schemas need updating;
- whether Control Plane bank configuration is generated or handwritten;
- what experimental client-side whitelist code currently exists;
- exact code that can be reused;
- exact code that should be deleted;
- discrepancies between the specification and current source;
- proposed minimal patch boundaries.

Then continue automatically unless a material architectural incompatibility is discovered.

## Phase 1 — Bank configuration

Implement the bank-level field:

```text
observation_scope_tag_key_whitelist
```

with semantics from the specification.

Requirements:

```text
unset/null
    → legacy behavior

[]
    → no tagged observation dimensions permitted

non-empty list
    → only those tag keys may participate
```

Use existing bank configuration infrastructure.

Do not create a parallel settings store.

Ensure persistence/read/update behavior follows existing bank config conventions.

Add focused config tests first.

## Phase 2 — Observation policy implementation

Implement one central server/engine policy.

Preset strategies should conceptually perform:

```text
fact tags
    ↓
bank whitelist filtering
    ↓
eligible tags
    ↓
existing scope expansion
```

Do NOT rewrite the existing algorithms for:

```text
combined
per_tag
all_combinations
shared
```

Reuse them.

If a configured whitelist leaves zero eligible tags, preset strategies must resolve to:

```json
[
  []
]
```

Never use an empty outer list as the shared fallback.

The original fact tags must remain untouched.

Add focused unit tests before moving on.

## Phase 3 — Explicit custom scopes

Because this is bank policy, custom scopes must not bypass it.

When a whitelist exists:

```text
custom scope contains only permitted keys
    → accept

custom scope contains prohibited key
    → reject clearly

shared empty inner scope []
    → always allowed
```

Do not silently filter a custom explicit scope.

Implement validation in the narrowest common server layer.

Test it independently.

## Phase 4 — Other observation-creation paths

Inspect manual consolidation and any other APIs that can create observations.

The bank whitelist must not be enforceable through Retain while bypassable through:

```text
manual consolidate
administrative consolidation
another engine method
```

Maintain this invariant:

> No newly created tagged observation scope may use a tag key prohibited by the bank.

Centralize enforcement.

Do not duplicate slightly different whitelist implementations.

## Phase 5 — Bank API/client plumbing

Expose the new field through every normal bank configuration surface required by current architecture.

Investigate and update as appropriate:

```text
OpenAPI schema
Python client
TypeScript client
CLI
bank create/update methods
bank templates/manifests
generated clients
```

Use official generators when files are generated.

Do not manually edit generated output when a repository generator exists.

## Phase 6 — Control Plane

If the existing Control Plane edits bank configuration, add this field there.

Keep UI small and consistent with existing settings.

The UI should make clear:

```text
Observation Scope Tag-Key Whitelist

Limits which tag keys may participate in tagged observations.
Fact tags themselves are preserved.
```

Support the distinction between:

```text
unset
```

and:

```text
[]
```

if the existing configuration UX/model can represent it.

Do not build a new settings framework.

## Phase 7 — Remove superseded client-side feature

Find and remove the fork's experimental:

```text
observationScopesParam.tagKeyWhitelist
```

and/or:

```text
tag_key
tag_keys
```

observation modes.

The coding-agent integration should return to using ordinary:

```json
{
  "observationScopes": "all_combinations"
}
```

or another existing strategy.

It must not independently filter tag keys.

Do not leave two competing whitelist mechanisms.

Preserve useful tests/helpers only if they now test generic server behavior.

## Phase 8 — Coding-agent regression coverage

Verify:

- existing `observationScopes` still works;
- `shared` default behavior remains unchanged unless user config changes it;
- `per_source` remains unchanged;
- `manageBankConfig` does not overwrite a user-configured whitelist;
- coding-agent fact provenance tags remain intact;
- no obsolete `observationScopesParam` documentation/config remains.

The coding-agent does not need to know the whitelist value.

## Required behavioral tests

At minimum cover:

```text
no whitelist + combined
no whitelist + per_tag
no whitelist + all_combinations
no whitelist + shared
no whitelist + custom scopes
```

All must match legacy behavior exactly.

Then test:

```text
whitelist + combined
whitelist + per_tag
whitelist + all_combinations
whitelist + shared
no matching tags
explicit empty whitelist
multiple values for one whitelisted key
stored fact tags remain unchanged
allowed custom scope
rejected custom scope
different banks with different whitelists
manual consolidation cannot bypass policy
```

Add config persistence/update tests.

Add client serialization tests if applicable.

Add UI tests following existing repository conventions.

## Critical regression invariant

Given:

```text
fact tags:

project:project-a
topic:authentication
source:chat
harness:codex
```

and bank config:

```text
observation_scope_tag_key_whitelist:

project
topic
```

stored facts must still contain:

```text
project:project-a
topic:authentication
source:chat
harness:codex
```

while:

```text
all_combinations
```

must consider only:

```text
project:project-a
topic:authentication
```

Do not accept an implementation that achieves scope filtering by deleting or rewriting fact tags.

## Historical behavior

Do not migrate existing observations.

Do not delete old scopes.

Do not automatically reconsolidate.

Do not rewrite existing memories when the bank config changes.

Document that the policy applies to future observation-scope generation.

Historical migration remains separate work.

## Documentation

Update generic Hindsight documentation first.

Explain:

```text
fact tags
→ bank whitelist
→ observation strategy
→ observation scopes
```

Use examples involving multiple generic ingestion sources.

Show why a memory may keep:

```text
source:chat
channel:engineering
```

for provenance while excluding those dimensions from `all_combinations`.

Document:

```text
unset whitelist
empty whitelist
no matching tags
shared behavior
custom scope validation
historical observations
```

Then update coding-agent docs to remove the obsolete client-side whitelist mechanism.

## Upstream scope discipline

Keep the patch focused on:

```text
bank config
observation policy
config/client plumbing
Control Plane integration if appropriate
tests
docs
removal of experimental fork code
```

Do not bundle:

```text
Slack ingestion
ticket ingestion
topic extraction
auth/RBAC
Knowledge Page redesign
Mental Model redesign
historical migration
new observation modes
```

## Mandatory review/fix loop

After implementation, tests, docs, and generated artifacts are complete, delegate a full review to a fresh subagent that did not author most of the implementation.

The reviewer must inspect the entire diff against:

`docs/gde-feature-observation-scope-whitelisting.md`

Ask it specifically to look for:

```text
legacy behavior regressions
fact tag mutation
incorrect [] versus [[]] behavior
bank-policy bypass through custom scopes
bank-policy bypass through manual consolidation
incorrect null vs empty-list behavior
inconsistent config serialization
different clients interpreting the field differently
coding-agent experimental code left behind
per_source regression
shared regression
all_combinations regression
generated-file mistakes
UI semantics inconsistent with API
historical observations accidentally migrated
unnecessary refactoring
anything likely to trigger upstream maintainer pushback
```

Require actionable findings with file/symbol references.

Then perform:

```text
review
   ↓
concerns?
   ├─ yes
   │    ↓
   │  fix
   │    ↓
   │  targeted tests
   │    ↓
   │  broader tests
   │    ↓
   │  fresh review
   │
   └─ no
        ↓
     final validation
```

Repeat until a fresh reviewer reports **no remaining substantive concerns**.

Do not stop after one review pass.

If a reviewer concern appears invalid, investigate and verify it rather than dismissing it reflexively.

## Final validation

After the review loop is clean:

- reread the complete specification;
- inspect the entire git diff yourself;
- run focused server tests;
- run broader affected API/engine tests;
- run coding-agent tests;
- run client/schema generation checks;
- run Control Plane tests/build if changed;
- run linters/typechecks required by affected packages;
- verify generated files are current;
- inspect git status;
- remove debugging artifacts;
- ensure no unrelated files changed.

## Git discipline

Do not discard existing user work.

Keep the patch rebase-friendly.

Avoid broad formatting/refactoring.

If committing is permitted, prefer logical commits approximately like:

```text
feat(config): add observation scope tag-key whitelist

feat(consolidation): enforce bank observation tag policy

feat(control-plane): expose observation tag whitelist

refactor(coding-agents): remove experimental client whitelist

test: cover bank observation scope policy

docs: document bank observation dimensions
```

Adapt to actual repository conventions.

Do not create broken intermediate commits.

## Completion report

When finished, report:

1. architecture implemented;
2. bank config field and exact semantics;
3. server files changed;
4. observation-generation enforcement point;
5. custom-scope enforcement behavior;
6. manual-consolidation enforcement behavior;
7. clients/config surfaces updated;
8. Control Plane changes;
9. experimental client-side code removed;
10. coding-agent regression status;
11. null/unset versus empty-list semantics;
12. no-match fallback behavior;
13. historical observation behavior;
14. tests/builds/typechecks run and results;
15. review/fix iterations and concerns fixed;
16. remaining limitations;
17. whether the patch is suitable for an upstream PR.

Do not stop at planning.

Carry the task through investigation, implementation, testing, documentation, repeated independent review, fixes, and final validation.
