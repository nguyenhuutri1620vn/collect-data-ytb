"""FR-4.2 grouping (D25: no Places). Pure function, no I/O.

Mentions join a place only when they share `legacy_district` and their normalized names are at
least `threshold` similar to the group's first mention. Mentions without a district never join
anything: "không chắc thì không gộp".
"""

from collections.abc import Sequence

from app.core.similarity import name_overlap


def group_mentions(
    mentions: Sequence[tuple[str, str | None]], *, threshold: float
) -> list[list[int]]:
    """mentions: (name_raw, legacy_district) per mention. Returns groups of input indices."""
    groups: list[list[int]] = []
    for i, (name, district) in enumerate(mentions):
        if district is None:
            groups.append([i])
            continue
        for group in groups:
            rep_name, rep_district = mentions[group[0]]
            if rep_district == district and name_overlap(name, rep_name) >= threshold:
                group.append(i)
                break
        else:
            groups.append([i])
    return groups
