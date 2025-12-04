import numpy as np

WorkspaceId = str


class InMemoryStore:
    def __init__(self):
        self._data: dict[WorkspaceId, list[dict]] = {}

    def add(self, workspace_id: str, chunks: list[dict], embeddings: np.ndarray) -> None:
        """Store each chunk plus its vector for the given workspace."""
        records = self._data.setdefault(workspace_id, [])
        for chunk, vector in zip(chunks, embeddings):
            records.append(
                {
                    "content": chunk["content"],
                    "source": chunk.get("source"),
                    "embedding": vector.tolist(),
                }
            )

    def get_workspace(self, workspace_id: str) -> list[dict]:
        """Return all stored chunk records for the workspace."""
        return list(self._data.get(workspace_id, []))


store = InMemoryStore()