"""Bank policy helpers for observation scope tag dimensions."""

from __future__ import annotations


def observation_scope_tag_key(tag: str) -> str:
    """Return the key portion of a tag, preserving bare-tag legacy semantics."""
    return tag.split(":", 1)[0]


def filter_observation_scope_tags(tags: list[str], whitelist: list[str] | None) -> list[str]:
    """Filter only the tags used for observation routing, never source fact tags."""
    if whitelist is None:
        return tags
    allowed = set(whitelist)
    return [tag for tag in tags if observation_scope_tag_key(tag) in allowed]


def validate_observation_scopes(scopes: list[list[str]], whitelist: list[str] | None) -> None:
    """Reject explicit scopes containing tag keys prohibited by bank policy."""
    if whitelist is None:
        return
    allowed = set(whitelist)
    prohibited = sorted(
        {
            observation_scope_tag_key(tag)
            for scope in scopes
            for tag in scope
            if observation_scope_tag_key(tag) not in allowed
        }
    )
    if prohibited:
        raise ValueError(
            "Observation scope contains tag keys not permitted by the bank's "
            f"observation_scope_tag_key_whitelist: {prohibited}"
        )
