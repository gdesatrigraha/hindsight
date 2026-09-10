You are the lead coding agent and coordinator for this implementation.

The complete specification is in:

`docs/gde-feature-observation-scope-whitelisting.md`

Read that document completely before making changes.

Your responsibility is to deliver the finished implementation, tests, documentation, and review fixes in this session.

## Role

Act primarily as the **coordinator/supervisor**, not as the agent that personally performs every mechanical task.

Use subagents aggressively where the work can be cleanly bounded.

Prefer cheaper/faster OpenAI coding models for:

- repository reconnaissance;
- locating implementation paths;
- isolated server changes;
- SDK/client plumbing;
- coding-agent configuration changes;
- test additions;
- documentation updates;
- focused code review;
- running/debugging targeted tests.

Keep these responsibilities with the main coordinator:

- architecture and API decisions;
- interpreting the specification;
- resolving discrepancies between spec and current upstream;
- deciding how server/client boundaries should work;
- coordinating changes that touch overlapping areas;
- integrating subagent results;
- final diff review;
- deciding whether reviewer concerns are valid;
- ensuring the implementation remains suitable for upstream submission.

Do not delegate the entire task to one subagent.

Do not allow multiple subagents to edit the same files concurrently unless you explicitly coordinate ownership.

## Source of truth

The primary source of truth is:

`docs/gde-feature-observation-scope-whitelisting.md`

Current repository code is the source of truth for implementation details.

If the document assumes an API, filename, symbol, generated-client workflow, or behavior that differs from the current repository, investigate the discrepancy and choose the smallest implementation that preserves the intended architecture.

Do not blindly implement stale assumptions from the document.

## Important architectural intent

The feature is NOT a new observation scope strategy.

The desired model is:

```text
fact tags
    ↓
optional tag-key whitelist
    ↓
eligible observation tags
    ↓
existing observationScopes strategy
    ↓
concrete observation scopes
```

For example:

```json
{
  "observationScopes": "all_combinations",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project", "user"]
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

only:

```text
project:example
user:gde
```

participate in observation scope generation.

The original stored fact must retain all original tags.

When a configured whitelist leaves zero eligible tags, the result must intentionally behave as `shared`, i.e. the concrete observation scope must be `[[]]`, not `[]`.

Existing behavior with no `observationScopesParam` must remain unchanged.

## Phase 0 — Repository investigation

Before editing code, delegate repository reconnaissance to one or more read-only subagents.

Have them independently inspect relevant areas such as:

- Retain API request schemas;
- observation scope expansion;
- `combined`;
- `per_tag`;
- `all_combinations`;
- `shared`;
- explicit custom scopes;
- server-side consolidation behavior;
- Python/TypeScript/other SDK clients;
- generated OpenAPI/client workflows;
- generic MCP retain interface;
- coding-agent configuration parsing;
- coding-agent retain request construction;
- the existing `per_source` special case;
- tests;
- documentation generation;
- the fork's previous experimental `tag_keys` implementation.

Ask scouts to return exact:

- file paths;
- symbols/functions/classes;
- call paths;
- relevant tests;
- generated-vs-handwritten boundaries;
- discrepancies with the specification.

Scouts should not edit files.

Review their findings yourself before implementation.

## Investigation checkpoint

After reconnaissance, provide me a concise checkpoint containing:

- current Retain → observation-scope expansion call path;
- where the whitelist should be inserted;
- API/schema changes required;
- which SDK/client layers need changes;
- how coding-agents currently forwards observation settings;
- what must be removed from the experimental `tag_keys` implementation;
- whether `per_source` requires special handling;
- whether explicit custom scopes should reject `observationScopesParam`;
- any discrepancy with the specification;
- whether any proposed change appears unnecessarily broad.

Then proceed with implementation without waiting for approval unless you discover a material architectural incompatibility.

## Phase 1 — Server implementation

Delegate the focused server work to an implementation subagent if practical.

Implement the generic server-side equivalent of:

```json
{
  "observation_scopes": "combined",
  "observation_scopes_param": {
    "tag_key_whitelist": ["project"]
  }
}
```

Requirements:

- filter only the tags used as input to observation-scope generation;
- never mutate stored fact tags;
- reuse existing strategy expansion;
- no whitelist means exact legacy behavior;
- explicitly empty whitelist means no eligible tags → shared `[[]]`;
- zero matches means shared `[[]]`;
- `shared` remains shared;
- multiple matching tags for one key remain eligible;
- explicit custom scope lists must not be silently rewritten.

Prefer rejecting an ambiguous combination of explicit custom scopes plus whitelist parameters rather than unexpectedly modifying explicit scopes.

Add focused server tests before proceeding.

The main coordinator must review this implementation before accepting it.

## Phase 2 — API and SDK/client plumbing

Delegate client/schema plumbing by bounded ownership where practical.

Expose the parameter through all relevant first-party surfaces identified during investigation.

Follow repository conventions and generators.

Do not manually modify generated output when an official generator exists.

Ensure naming is idiomatic:

```text
HTTP/server:
observation_scopes_param.tag_key_whitelist

coding-agent JSON:
observationScopesParam.tagKeyWhitelist
```

Do not add speculative parameters.

## Phase 3 — Coding-agent integration

Remove the earlier experimental client-side `tag_keys` mode unless repository history indicates it has become a compatibility requirement.

The desired coding-agent configuration is:

```json
{
  "observationScopes": "combined",
  "observationScopesParam": {
    "tagKeyWhitelist": ["project"]
  }
}
```

The coding-agent integration should forward the parameter to Hindsight rather than calculating project-specific concrete scopes itself.

Preserve existing observation scope modes.

Preserve `per_source` behavior.

If `per_source` + `observationScopesParam` has no clean semantics, validate/reject that combination rather than silently doing something surprising.

## Phase 4 — Tests

Delegate test expansion where useful, but the coordinator owns final coverage.

At minimum verify:

- no whitelist preserves existing `combined`;
- no whitelist preserves existing `per_tag`;
- no whitelist preserves existing `all_combinations`;
- no whitelist preserves `shared`;
- whitelist + `combined`;
- whitelist + `per_tag`;
- whitelist + `all_combinations`;
- zero matching tags → `[[]]`;
- explicitly empty whitelist → `[[]]`;
- fact tags remain unchanged;
- multiple values for a whitelisted key;
- deterministic ordering/canonicalization;
- explicit custom-scope behavior;
- coding-agent config parsing;
- coding-agent config layering;
- coding-agent forwarding;
- existing `per_source` tests remain passing;
- relevant SDK serialization/deserialization.

Run narrow tests during development, then broader relevant suites.

Do not accept compilation alone as sufficient verification.

## Phase 5 — Documentation

Delegate documentation updates after behavior is stable.

Update the generic API documentation first, then coding-agent documentation.

The docs must clearly explain:

```text
tags
→ tagKeyWhitelist
→ observationScopes
→ generated scopes
```

Include examples for:

- `combined`;
- `per_tag`;
- `all_combinations`;
- zero matching tags;
- preservation of fact/provenance tags.

Explain why this exists:

Fact tags may represent both:

```text
retrieval/provenance dimensions
```

and:

```text
observation/belief dimensions
```

but those are not always the same set.

Do not frame the feature as a coding-agent-only capability.

## Scope discipline

Keep this suitable for upstream submission.

Do NOT bundle:

- per-project Knowledge Page provisioning;
- Mental Model provisioning;
- historical observation migration;
- export/import migration tooling;
- unrelated refactors;
- new observation strategies;
- generalized tag-query infrastructure unrelated to observation scopes.

If cleanup is tempting but unrelated, leave it out.

## Subagent result handling

Never trust a subagent result purely because it claims success.

For each delegated implementation:

1. inspect the diff yourself;
2. verify it matches the specification;
3. check for unintended neighboring changes;
4. run or independently confirm its tests;
5. amend/fix the work if necessary.

Subagents are workers and reviewers; the main agent remains accountable for the final repository state.

## Mandatory review/fix loop

After implementation, tests, and documentation are complete, start a formal review loop.

Delegate the review to a fresh subagent that did NOT author the majority of the implementation.

Ask the reviewer to inspect the entire diff against:

`docs/gde-feature-observation-scope-whitelisting.md`

The reviewer should actively search for:

- semantic regressions;
- incorrect fallback behavior;
- accidental `[]` instead of `[[]]`;
- fact-tag mutation;
- filtering explicit custom scopes;
- backwards incompatibility;
- incorrect `shared` behavior;
- invalid assumptions about tag parsing;
- duplicate implementations of scope-generation logic;
- unnecessary server/client coupling;
- SDK/schema inconsistencies;
- incomplete serialization;
- missing tests;
- generated-file mistakes;
- coding-agent regressions;
- `per_source` regressions;
- documentation that disagrees with implementation;
- unnecessarily large diff;
- anything likely to trigger upstream maintainer pushback.

The reviewer must produce specific actionable concerns, preferably with file/symbol references.

Then:

```text
review
  ↓
concerns found?
  ├─ yes → fix concerns
  │          ↓
  │       rerun relevant tests
  │          ↓
  │       fresh review
  │
  └─ no → final validation
```

Repeat this **review → fix → test → review** cycle until the reviewer reports no remaining substantive concerns.

Use fresh reviewer context/subagents when practical so earlier assumptions do not bias later reviews.

Do not stop merely because one review pass completed.

Do not dismiss reviewer concerns without examining them. If you believe a concern is invalid, verify why and document the reasoning internally before continuing.

## Final validation

After the reviewer reports no remaining substantive concerns:

1. reread the specification;
2. inspect the entire git diff;
3. run the broadest relevant tests practical for this repository;
4. run linters/typechecks/build steps required by affected packages;
5. verify generated files are current;
6. inspect `git status`;
7. ensure no unrelated files were changed;
8. ensure no temporary debugging artifacts remain.

Check specifically that:

```text
original fact tags
    remain unchanged

observationScopesParam.tagKeyWhitelist
    filters only observation-scope input tags

existing observationScopes strategy
    remains responsible for scope generation
```

## Git discipline

Do not discard existing user changes.

Do not use destructive reset/checkout commands against user work.

Keep changes rebase-friendly.

Prefer logically separated commits if committing is permitted, approximately:

```text
feat(api): add observation scope tag-key whitelist

feat(clients): expose observation scope parameters

feat(coding-agents): support observation scope parameters

test: cover observation scope tag filtering

docs: document observation scope tag whitelist
```

Adapt to repository conventions.

Do not commit broken intermediate states.

## Completion criteria

Do not declare completion until:

- implementation is complete;
- tests pass;
- docs are updated;
- generated artifacts are current;
- the full diff has been reviewed;
- all substantive review concerns have been fixed;
- a final reviewer pass reports no remaining substantive concerns.

## Final report

When finished, report concisely:

1. architecture implemented;
2. server files changed;
3. SDK/client files changed;
4. coding-agent changes;
5. final configuration syntax;
6. exact empty/no-match whitelist behavior;
7. explicit custom-scope behavior;
8. `per_source` interaction;
9. backward-compatibility status;
10. tests/typechecks/builds run and results;
11. documentation updated;
12. review/fix iterations performed and issues found/fixed;
13. any remaining limitations;
14. whether the final patch appears suitable for an upstream PR.

Do not stop at planning or investigation. Carry the task through implementation, validation, review/fix iterations, and final completion.
