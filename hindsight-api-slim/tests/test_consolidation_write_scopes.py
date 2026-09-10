"""Unit tests for ``_resolve_write_scopes`` / ``_resolve_obs_tags_list``.

These helpers drive the per-scope lock acquisition in the parallel consolidation
dispatcher. The lock-based safety story only works if the helpers report the
*exact* set of observation scopes a memory will write to — over-reporting is
safe (extra locks slow things down but don't lose data) but under-reporting
allows a concurrent group to race on the same observation row. So we pin the
mapping for every observation_scopes mode the dispatcher recognises.
"""

import json

import pytest

from hindsight_api.engine.consolidation.consolidator import (
    _consolidation_batch_key,
    _resolve_obs_tags_list,
    _resolve_write_scopes,
    _scope_sort_key,
)
from hindsight_api.engine.retain.types import (
    ExtractedFact,
    ObservationScopesParam,
    PersistedObservationScopes,
    ProcessedFact,
    persist_observation_scopes,
)

# ---------------------------------------------------------------------------
# _resolve_write_scopes — frozenset output is what the lock dict keys on
# ---------------------------------------------------------------------------


# Production observation_scopes values come from a JSONB column. asyncpg
# returns JSONB without a codec, so the value is a JSON-encoded *string*. These
# parametrised cases cover both shapes: the raw Python form (None / list / dict
# — used in tests that build the memory dict directly) and the JSON-encoded
# string form (used in tests that mirror what asyncpg surfaces from the DB).


def _as_json_string(value):
    """Encode an observation_scopes value the way asyncpg presents it from JSONB."""
    return json.dumps(value)


class TestResolveWriteScopesCombined:
    @pytest.mark.parametrize("scopes_value", [None, _as_json_string("combined")])
    def test_default_uses_full_tag_set(self, scopes_value):
        memory = {"tags": ["alice", "session"], "observation_scopes": scopes_value}
        assert _resolve_write_scopes(memory) == [frozenset({"alice", "session"})]

    def test_empty_tags_collapses_to_untagged_scope(self):
        memory = {"tags": [], "observation_scopes": None}
        assert _resolve_write_scopes(memory) == [frozenset()]

    def test_missing_tags_collapses_to_untagged_scope(self):
        memory = {"observation_scopes": None}
        assert _resolve_write_scopes(memory) == [frozenset()]


class TestResolveWriteScopesPerTag:
    def test_emits_one_scope_per_tag(self):
        memory = {"tags": ["alice", "session", "thread"], "observation_scopes": _as_json_string("per_tag")}
        scopes = _resolve_write_scopes(memory)
        assert set(scopes) == {frozenset({"alice"}), frozenset({"session"}), frozenset({"thread"})}
        assert len(scopes) == 3  # no dedupe surprises

    def test_empty_tags_collapses_to_untagged_scope(self):
        memory = {"tags": [], "observation_scopes": _as_json_string("per_tag")}
        assert _resolve_write_scopes(memory) == [frozenset()]


class TestResolveWriteScopesAllCombinations:
    def test_two_tags_yields_three_scopes(self):
        memory = {"tags": ["alice", "session"], "observation_scopes": _as_json_string("all_combinations")}
        scopes = set(_resolve_write_scopes(memory))
        assert scopes == {
            frozenset({"alice"}),
            frozenset({"session"}),
            frozenset({"alice", "session"}),
        }

    def test_three_tags_yields_seven_scopes(self):
        memory = {"tags": ["a", "b", "c"], "observation_scopes": _as_json_string("all_combinations")}
        scopes = set(_resolve_write_scopes(memory))
        # C(3,1) + C(3,2) + C(3,3) = 3 + 3 + 1 = 7
        assert scopes == {
            frozenset({"a"}),
            frozenset({"b"}),
            frozenset({"c"}),
            frozenset({"a", "b"}),
            frozenset({"a", "c"}),
            frozenset({"b", "c"}),
            frozenset({"a", "b", "c"}),
        }

    def test_empty_tags_collapses_to_untagged_scope(self):
        memory = {"tags": [], "observation_scopes": _as_json_string("all_combinations")}
        assert _resolve_write_scopes(memory) == [frozenset()]


class TestResolveWriteScopesShared:
    def test_collapses_to_single_untagged_scope_regardless_of_tags(self):
        # "shared" ignores the memory's own tags and writes to one global scope,
        # so every memory deduplicates against the same observation.
        memory = {"tags": ["alice", "session"], "observation_scopes": _as_json_string("shared")}
        assert _resolve_write_scopes(memory) == [frozenset()]

    def test_empty_tags_also_untagged_scope(self):
        memory = {"tags": [], "observation_scopes": _as_json_string("shared")}
        assert _resolve_write_scopes(memory) == [frozenset()]

    def test_whitelist_with_no_matching_tags_uses_untagged_scope(self):
        memory = {
            "tags": ["source:chat"],
            "observation_scopes": PersistedObservationScopes(mode="combined", tag_key_whitelist=["project"]),
        }
        assert _resolve_write_scopes(memory) == [frozenset()]


class TestResolveWriteScopesExplicitList:
    def test_uses_declared_scopes_verbatim(self):
        memory = {
            "tags": ["alice", "session"],
            "observation_scopes": _as_json_string([["alice"], ["session"], ["alice", "session"]]),
        }
        scopes = set(_resolve_write_scopes(memory))
        assert scopes == {
            frozenset({"alice"}),
            frozenset({"session"}),
            frozenset({"alice", "session"}),
        }

    def test_ignores_memory_tags(self):
        # An explicit scope list overrides per-mode logic — even if the memory's
        # own tags don't match, the declared scopes are what gets written.
        memory = {"tags": ["alice"], "observation_scopes": _as_json_string([["unrelated_scope"]])}
        assert _resolve_write_scopes(memory) == [frozenset({"unrelated_scope"})]

    def test_with_empty_inner_scope(self):
        memory = {"tags": ["alice"], "observation_scopes": _as_json_string([[], ["alice"]])}
        scopes = set(_resolve_write_scopes(memory))
        assert scopes == {frozenset(), frozenset({"alice"})}


class TestResolveWriteScopesPrepackedValues:
    """When the caller hands a memory dict with already-parsed observation_scopes
    (e.g. a unit test fixture passing a Python value directly), the helper must
    not try to JSON-decode it again. The shape gate is ``isinstance(_, str)``,
    so non-string Python values flow through untouched."""

    def test_list_passed_directly(self):
        memory = {"tags": ["alice"], "observation_scopes": [["alice"], ["other"]]}
        assert set(_resolve_write_scopes(memory)) == {frozenset({"alice"}), frozenset({"other"})}

    def test_none_passed_directly(self):
        memory = {"tags": ["alice"], "observation_scopes": None}
        assert _resolve_write_scopes(memory) == [frozenset({"alice"})]


# ---------------------------------------------------------------------------
# _resolve_obs_tags_list — drives the multi-pass dispatch
# ---------------------------------------------------------------------------


class TestResolveObsTagsList:
    """The list form is what the dispatcher passes as obs_tags_override on each
    pass; the frozenset form is what gets locked. They must agree on which
    scopes are touched."""

    def test_combined_returns_none(self):
        assert _resolve_obs_tags_list({"tags": ["a"], "observation_scopes": None}) is None
        assert _resolve_obs_tags_list({"tags": ["a"], "observation_scopes": json.dumps("combined")}) is None

    def test_per_tag_returns_one_list_per_tag(self):
        memory = {"tags": ["a", "b"], "observation_scopes": json.dumps("per_tag")}
        assert _resolve_obs_tags_list(memory) == [["a"], ["b"]]

    def test_all_combinations_returns_all_nonempty_subsets(self):
        memory = {"tags": ["a", "b"], "observation_scopes": json.dumps("all_combinations")}
        result = _resolve_obs_tags_list(memory)
        assert result is not None
        assert {tuple(sorted(r)) for r in result} == {("a",), ("b",), ("a", "b")}

    def test_per_tag_empty_tags_returns_none(self):
        # Falls back to the default single-pass behaviour; the dispatcher then
        # uses the memory's (empty) tag set, matching combined-mode behaviour.
        assert _resolve_obs_tags_list({"tags": [], "observation_scopes": json.dumps("per_tag")}) is None

    def test_explicit_list_passthrough(self):
        spec = [["a"], ["a", "b"]]
        memory = {"tags": ["a", "b"], "observation_scopes": json.dumps(spec)}
        assert _resolve_obs_tags_list(memory) == spec

    def test_shared_returns_single_empty_scope(self):
        # One pass over the empty (untagged) scope; the memory's own tags are
        # ignored so cross-tag memories consolidate into one observation.
        memory = {"tags": ["a", "b"], "observation_scopes": json.dumps("shared")}
        assert _resolve_obs_tags_list(memory) == [[]]

    @pytest.mark.parametrize("mode", ["combined", "per_tag", "all_combinations"])
    def test_whitelist_with_no_matching_tags_falls_back_to_shared(self, mode):
        memory = {
            "tags": ["source:chat", "harness:codex"],
            "observation_scopes": PersistedObservationScopes(mode=mode, tag_key_whitelist=["project"]),
        }
        assert _resolve_obs_tags_list(memory) == [[]]

    def test_empty_whitelist_falls_back_to_shared(self):
        memory = {
            "tags": ["project:foo"],
            "observation_scopes": PersistedObservationScopes(mode="combined", tag_key_whitelist=[]),
        }
        assert _resolve_obs_tags_list(memory) == [[]]

    def test_whitelist_keeps_complete_matching_tags_and_multiple_values(self):
        original_tags = ["project:foo", "source:chat", "project:bar", "user:gde"]
        memory = {
            "tags": original_tags,
            "observation_scopes": PersistedObservationScopes(mode="combined", tag_key_whitelist=["project", "user"]),
        }
        assert _resolve_obs_tags_list(memory) == [["project:foo", "project:bar", "user:gde"]]
        assert memory["tags"] == original_tags

    def test_whitelist_composes_with_per_tag_and_all_combinations(self):
        tags = ["project:foo", "user:gde", "source:chat"]
        per_tag = _resolve_obs_tags_list(
            {
                "tags": tags,
                "observation_scopes": PersistedObservationScopes(mode="per_tag", tag_key_whitelist=["project", "user"]),
            }
        )
        combinations_result = _resolve_obs_tags_list(
            {
                "tags": tags,
                "observation_scopes": PersistedObservationScopes(
                    mode="all_combinations", tag_key_whitelist=["project", "user"]
                ),
            }
        )
        assert per_tag == [["project:foo"], ["user:gde"]]
        assert combinations_result == [["project:foo"], ["user:gde"], ["project:foo", "user:gde"]]

    def test_whitelist_decodes_from_jsonb_string(self):
        memory = {
            "tags": ["project:foo", "source:chat"],
            "observation_scopes": json.dumps({"mode": "combined", "tag_key_whitelist": ["project"]}),
        }
        assert _resolve_obs_tags_list(memory) == [["project:foo"]]

    def test_whitelist_does_not_change_shared(self):
        memory = {
            "tags": ["project:foo"],
            "observation_scopes": PersistedObservationScopes(mode="shared", tag_key_whitelist=["project"]),
        }
        assert _resolve_obs_tags_list(memory) == [[]]


class TestObservationScopePersistence:
    def test_absent_parameter_preserves_legacy_value(self):
        assert persist_observation_scopes("combined", None) == "combined"

    def test_configured_parameter_uses_internal_envelope(self):
        persisted = persist_observation_scopes("combined", ObservationScopesParam(tag_key_whitelist=["project"]))
        assert persisted == PersistedObservationScopes(mode="combined", tag_key_whitelist=["project"])

    def test_explicit_scopes_and_parameter_are_rejected(self):
        with pytest.raises(ValueError, match="explicit observation_scopes"):
            persist_observation_scopes([["project:foo"]], ObservationScopesParam(tag_key_whitelist=["project"]))

    def test_processed_fact_persists_json_envelope_without_changing_fact_tags(self):
        tags = ["project:foo", "source:chat"]
        fact = ExtractedFact(
            fact_text="A project fact",
            fact_type="world",
            tags=tags,
            observation_scopes="combined",
            observation_scopes_param=ObservationScopesParam(tag_key_whitelist=["project"]),
        )

        processed = ProcessedFact.from_extracted_fact(fact, [0.1])

        assert processed is not None
        assert processed.observation_scopes == {
            "mode": "combined",
            "tag_key_whitelist": ["project"],
        }
        assert processed.tags == tags


# ---------------------------------------------------------------------------
# Agreement between obs_tags_list (dispatch) and write_scopes (locks)
# ---------------------------------------------------------------------------


class TestDispatchLockAgreement:
    """Whatever scopes the dispatcher visits via _resolve_obs_tags_list, the
    lock layer must have a lock for. Under-locking is the race we set out to
    fix, so this is the load-bearing invariant."""

    @pytest.mark.parametrize(
        "memory",
        [
            # JSON-encoded shape (what asyncpg surfaces from JSONB without a codec).
            {"tags": ["a", "b"], "observation_scopes": None},
            {"tags": ["a", "b", "c"], "observation_scopes": json.dumps("combined")},
            {"tags": ["a", "b"], "observation_scopes": json.dumps("per_tag")},
            {"tags": ["a", "b", "c"], "observation_scopes": json.dumps("all_combinations")},
            {"tags": ["a", "b"], "observation_scopes": json.dumps("shared")},
            {"tags": ["a", "b"], "observation_scopes": json.dumps([["a"], ["b"], ["a", "b"]])},
            {"tags": ["a"], "observation_scopes": json.dumps([["a"], ["x"]])},
            {
                "tags": ["project:a", "source:chat"],
                "observation_scopes": {"mode": "combined", "tag_key_whitelist": ["project"]},
            },
            {
                "tags": ["project:a", "source:chat"],
                "observation_scopes": {"mode": "per_tag", "tag_key_whitelist": ["project"]},
            },
            {
                "tags": ["project:a", "source:chat"],
                "observation_scopes": {"mode": "all_combinations", "tag_key_whitelist": ["project"]},
            },
            {
                "tags": ["source:chat"],
                "observation_scopes": {"mode": "combined", "tag_key_whitelist": []},
            },
            # Pre-parsed Python shape (defensive — covers callers that hand the
            # helper a memory dict with a non-string value).
            {"tags": ["a", "b"], "observation_scopes": [["a"], ["b"], ["a", "b"]]},
        ],
    )
    def test_every_dispatched_scope_has_a_lock(self, memory):
        dispatched = _resolve_obs_tags_list(memory)
        write_scopes = set(_resolve_write_scopes(memory))

        if dispatched is None:
            # Combined-mode single pass: memory's own tags are the write scope.
            expected = {frozenset(memory.get("tags") or [])}
        else:
            expected = {frozenset(s) for s in dispatched}

        missing = expected - write_scopes
        assert not missing, (
            f"dispatcher will write to scopes {missing} but no lock will be acquired "
            f"for them (memory={memory!r}, write_scopes={write_scopes!r})"
        )


class TestConsolidationBatchKey:
    def test_same_fact_tags_with_different_scope_plans_are_separate_batches(self):
        """A batch cannot use its first row's observation plan for unlike rows."""
        tags = ["project:foo", "source:chat"]
        memories = [
            {"tags": tags, "observation_scopes": "combined"},
            {
                "tags": tags,
                "observation_scopes": PersistedObservationScopes(
                    mode="combined",
                    tag_key_whitelist=["project"],
                ),
            },
            {"tags": tags, "observation_scopes": "per_tag"},
            {"tags": tags, "observation_scopes": [["source:chat"]]},
        ]

        grouped: dict[object, list[dict]] = {}
        for memory in memories:
            grouped.setdefault(_consolidation_batch_key(memory), []).append(memory)

        assert len(grouped) == len(memories)
        assert all(len(group) == 1 for group in grouped.values())

    def test_equivalent_rows_still_share_a_batch_key(self):
        first = {
            "tags": ["project:foo", "source:chat"],
            "observation_scopes": PersistedObservationScopes(
                mode="per_tag",
                tag_key_whitelist=["project"],
            ),
        }
        second = {
            "tags": ["project:foo", "source:chat"],
            "observation_scopes": PersistedObservationScopes(
                mode="per_tag",
                tag_key_whitelist=["project"],
            ),
        }

        assert _consolidation_batch_key(first) == _consolidation_batch_key(second)


# ---------------------------------------------------------------------------
# _scope_sort_key — deadlock-freedom rests on a total order over frozensets
# ---------------------------------------------------------------------------


class TestScopeSortKey:
    def test_is_total_order(self):
        """Every distinct scope must have a distinct sort key so concurrent
        groups acquire shared locks in the same order."""
        scopes = [
            frozenset(),
            frozenset({"a"}),
            frozenset({"b"}),
            frozenset({"a", "b"}),
            frozenset({"a", "b", "c"}),
        ]
        keys = [_scope_sort_key(s) for s in scopes]
        assert len(set(keys)) == len(scopes), "two distinct scopes share a sort key"

    def test_order_is_stable_across_set_construction(self):
        """frozenset hash order is non-deterministic across runs, but the sort
        key should not be — otherwise two groups could try to acquire shared
        locks in opposite orders."""
        scope_a = frozenset(["x", "y", "z"])
        scope_b = frozenset({"z", "y", "x"})  # built differently, same set
        assert _scope_sort_key(scope_a) == _scope_sort_key(scope_b)
