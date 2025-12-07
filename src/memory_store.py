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

    def list_workspaces(self) -> list[dict]:
        """Return a summary of workspace IDs and their stored record counts."""
        return [
            {"workspace_id": workspace_id, "records": len(records)}
            for workspace_id, records in self._data.items()
        ]

    def top_k_similar(
        self,
        workspace_id: str,
        query_embedding: list[float],
        k: int = 3,
    ) -> list[dict]:
        """Return up to k stored records closest to the query vector."""
        records = self.get_workspace(workspace_id)
        if not records:
            return []

        query_vector = np.array(query_embedding, dtype=float)
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []

        scored = []
        for record in records:
            vector = np.array(record["embedding"], dtype=float)
            denom = query_norm * np.linalg.norm(vector)
            if denom == 0:
                continue
            score = float(np.dot(query_vector, vector) / denom)
            scored.append(
                {
                    "content": record["content"],
                    "source": record.get("source"),
                    "score": score,
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:k]


store = InMemoryStore()