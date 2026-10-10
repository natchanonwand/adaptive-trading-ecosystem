"""Pinned lineage plus descendant-work contract; generated evidence stays byte exact."""

import subprocess
from pathlib import Path

LINEAGE: tuple[tuple[str, str], ...] = (
    ("phase5a-v0.1.0", "ec87ad23a1bbb805f033af59cf2e9991af755191"),  # pragma: allowlist secret
    ("phase5a-v0.1.1", "e83c41b3d41704c276f98b0912439d13400eb490"),  # pragma: allowlist secret
    (
        "phase5b-tooling-v0.1.0",
        "3a35373a7d022fe61a7289a18c33243a8f8fb178",  # pragma: allowlist secret
    ),  # pragma: allowlist secret
    (
        "phase5b-tooling-v0.1.1",
        "a76d896ac031c85951b300d6fa946b93f084ab70",  # pragma: allowlist secret
    ),  # pragma: allowlist secret
)
TAG_OBJECTS: tuple[str, ...] = (
    "16b4fc3be5ffbaf96f5e7c5e5c77dd5d6ed3a9c0",  # pragma: allowlist secret
    "955cc487710df8773519e791d699b93c4f225012",  # pragma: allowlist secret
    "1d1d57b1dbba78d5a3de2aabe50e9b56e4cfb245",  # pragma: allowlist secret
    "41ea0316671c646c7d903da531008a0cb44d63bd",  # pragma: allowlist secret
)

LINEAGE += (
    (
        "phase5b-tooling-v0.1.2",
        "27f4e0db60238f9467bc88de80abefa055aef2ae",  # pragma: allowlist secret
    ),  # pragma: allowlist secret
    (
        "phase5b-tooling-v0.1.3",
        "27f4e0db60238f9467bc88de80abefa055aef2ae",  # pragma: allowlist secret
    ),  # pragma: allowlist secret
    (
        "phase5b-tooling-v0.1.4",
        "3ad73e72821026da91254100f065f37a390b015e",  # pragma: allowlist secret
    ),  # pragma: allowlist secret
)
TAG_OBJECTS += (
    "335fa7d93d88de7e677cdfc6cbf84861a3259725",  # pragma: allowlist secret
    "e32907e54cb454149c301a61aa45a7d9abfd1cde",  # pragma: allowlist secret
    "831ef592492ff4e37199b3724165b0c3c532dde1",  # pragma: allowlist secret
)


LINEAGE += (
    (
        "phase5b-tooling-v0.1.5",
        "bd5780b59068f6dd81d2bb55cc748dbf978658e8",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("492b7eb6aeef47a8fb14ba4de579f35c84ee7f9f",)  # pragma: allowlist secret


LINEAGE += (
    (
        "phase5b-tooling-v0.1.6",
        "38e022b8dd70d245500ecfa8ea332a99061f1bd2",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("a155679747624336f0bbdda39acafa9dafd3097d",)  # pragma: allowlist secret


LINEAGE += (
    (
        "phase5b-tooling-v0.1.7",
        "3f88a030d7f6b67d47f7a3fea01b490a8ca0bde5",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("10a4f107b09d24b654e9832922ba9edc5cff0564",)  # pragma: allowlist secret


LINEAGE += (
    (
        "phase5b-tooling-v0.1.8",
        "55071a4f8be825f5aef9d920d3182ef241f2b158",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("ee92d9a1c9f415f9477f36c965e08bf7a6924a7b",)  # pragma: allowlist secret


LINEAGE += (
    (
        "phase5b-tooling-v0.1.9",
        "6b9567a9ad76f27e63f98aeeae98350bcc1700fd",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("b3e259e9e6c71606e4ef53b80ac8832edf7b5d3c",)  # pragma: allowlist secret

LINEAGE += (
    (
        "phase5b-tooling-v0.1.10",
        "46f2c3d09beabae8a9d44c5ec7d3e1dbe5e899ed",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("9261b6f479bc8ef007477c18dbaa10832b66c91f",)  # pragma: allowlist secret

LINEAGE += (
    (
        "phase5b-tooling-v0.1.11",
        "c78a7ed46f0c846d9aeffa345b8c08451ce028ac",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("b4b37d9b6a5be1ada3ec48935d7b0113812e3c2d",)  # pragma: allowlist secret


LINEAGE += (
    (
        "phase5b-tooling-v0.1.12",
        "657f0236d5b3e88db36848efb279b06047d09eb8",  # pragma: allowlist secret
    ),
)
TAG_OBJECTS += ("82ec14370abf9f50b5e0cc27079ce7ac721d01a7",)  # pragma: allowlist secret


def verify_checkpoint(
    root: Path,
    immediate: str = "phase5b-tooling-v0.1.12",
    lineage: tuple[tuple[str, str], ...] = LINEAGE,
) -> str:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    if immediate != lineage[-1][0]:
        raise ValueError("WRONG_IMMEDIATE_CHECKPOINT")
    previous = None
    if lineage == LINEAGE:
        for (tag, _), tag_object in zip(lineage, TAG_OBJECTS, strict=True):
            if git("rev-parse", tag) != tag_object:
                raise ValueError("FROZEN_TAG_OBJECT_CHANGED: " + tag)
    for tag, expected in lineage:
        if git("rev-parse", tag + "^{commit}") != expected:
            raise ValueError("FROZEN_TAG_CHANGED: " + tag)
        if previous:
            git("merge-base", "--is-ancestor", previous, expected)
        previous = expected
    checkpoint = lineage[-1][1]
    for ref in ("HEAD", "origin/main"):
        git("merge-base", "--is-ancestor", checkpoint, ref)
    return checkpoint
