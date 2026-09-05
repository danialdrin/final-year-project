import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model: {settings.MEDIUM_ANALYSIS_MODEL_NAME}")
            self._model = SentenceTransformer(settings.MEDIUM_ANALYSIS_MODEL_NAME)
        return self._model

    def embed(self, text: str) -> np.ndarray:
        dim = int(self.model.get_embedding_dimension() or 384)
        if not text or not text.strip():
            return np.zeros(dim)
        return self.model.encode(text, convert_to_numpy=True)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.array([])
        return self.model.encode(texts, convert_to_numpy=True)

    @staticmethod
    def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

embedding_service = EmbeddingService()
