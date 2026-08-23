import os
from typing import List, Optional, Tuple

import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer


class LanceDBStore:
    """Vector memory store backed by LanceDB for dense embeddings and semantic deduplication."""

    def __init__(
        self,
        db_path: str = "storage/lancedb",
        table_name: str = "challenges_vector",
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.db_path = db_path
        self.table_name = table_name
        self.model_name = model_name
        self._model = None

        os.makedirs(db_path, exist_ok=True)
        self.db = lancedb.connect(db_path)
        self.table = self._init_table()

    @property
    def model(self) -> SentenceTransformer:
        """Lazy loader for SentenceTransformer model to optimize import and init times."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _get_table_names(self) -> List[str]:
        if hasattr(self.db, "list_tables"):
            resp = self.db.list_tables()
            if hasattr(resp, "tables"):
                return resp.tables
            return list(resp)
        return self.db.table_names()

    def _init_table(self):
        """Initializes or opens the LanceDB vector table with a 384-dimensional embedding schema."""
        schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 384)),
                pa.field("source_url", pa.string()),
                pa.field("text", pa.string()),
            ]
        )

        table_names = self._get_table_names()
        if self.table_name in table_names:
            return self.db.open_table(self.table_name)
        else:
            return self.db.create_table(self.table_name, schema=schema)

    def embed_text(self, text: str) -> List[float]:
        """Generates normalized 384-dimensional dense vector embeddings for input text."""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def is_duplicate(self, vector: List[float], threshold: float = 0.15) -> Tuple[bool, Optional[str], float]:
        """
        Performs cosine distance search against stored vectors.
        Returns (is_duplicate: bool, matching_record_id: Optional[str], distance: float).
        Cosine distance < threshold (default 0.15) indicates near-identical semantics.
        """
        if self.count() == 0:
            return False, None, 1.0

        results = self.table.search(vector).metric("cosine").limit(1).to_list()
        if not results:
            return False, None, 1.0

        top_match = results[0]
        # In LanceDB cosine metric, _distance is cosine distance (1 - cosine_similarity)
        distance = float(top_match.get("_distance", 1.0))

        if distance < threshold:
            return True, top_match.get("id"), distance

        return False, None, distance

    def add_record(self, record_id: str, vector: List[float], source_url: str, text: str = "") -> None:
        """Persists a vector embedding and source attribution into the LanceDB table."""
        data = [
            {
                "id": record_id,
                "vector": vector,
                "source_url": source_url,
                "text": text,
            }
        ]
        self.table.add(data)

    def count(self) -> int:
        """Returns total vector count in the table."""
        try:
            if self.table_name not in self._get_table_names():
                return 0
            return len(self.table)
        except Exception:
            return 0
