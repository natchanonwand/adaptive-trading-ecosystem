"""Interface only: no Parquet dependency, ingestion, downloading or implementation."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ImmutableArtifact:
    content_hash: str
    byte_length: int
    media_type: str = "application/vnd.apache.parquet"


class ImmutableParquetStore(Protocol):
    def put_if_absent(self, artifact: ImmutableArtifact, content: bytes) -> None: ...

    def read_verified(self, content_hash: str) -> bytes: ...
