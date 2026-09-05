import re
import logging
import numpy as np
import textstat
from typing import Dict, Any, List
from app.services.embedding_service import embedding_service
from app.models.resource import MediumAnalysisScores

logger = logging.getLogger(__name__)

EXAMPLE_PATTERNS = [
    r"for example", r"for instance", r"let's say", r"imagine",
    r"consider this", r"such as", r"e\.g\.", r"code example", r"sample"
]

STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
    "is", "are", "was", "were", "and", "or", "but", "this", "that",
    "it", "you", "we", "i", "how", "what", "why", "when", "where"
}

class MediumAnalysisService:
    def compute_scores(
        self,
        query: str,
        title: str,
        description: str,
        transcript_text: str,
        segments: List[Dict[str, Any]],
        transcript_available: bool = True
    ) -> MediumAnalysisScores:
        """
        Computes 7 scoring factors entirely on local CPU without an LLM API call.
        """
        content_text = transcript_text if (transcript_available and transcript_text) else f"{title} {description}"
        if not content_text.strip():
            return MediumAnalysisScores(
                relevance=0.0, topic_coverage=0.0, depth=0.0, examples=0.0,
                clarity=0.0, structure=0.0, redundancy=0.0, overall=0.0,
                transcript_available=False
            )

        # Embed query and content
        query_vec = embedding_service.embed(query)
        content_vec = embedding_service.embed(content_text)

        # 1. Relevance
        relevance_raw = embedding_service.cosine_sim(query_vec, content_vec)
        relevance = float(np.clip((relevance_raw + 1) / 2.0, 0.0, 1.0))

        # 2. Topic Coverage
        subtopics = [w.strip() for w in query.split() if len(w.strip()) > 2 and w.lower() not in STOPWORDS]
        if not subtopics:
            subtopics = [query]
        
        if segments:
            seg_texts = [s.get("text", "") for s in segments if s.get("text", "").strip()]
            if seg_texts:
                seg_vecs = embedding_service.embed_batch(seg_texts)
                subtopic_scores = []
                for sub in subtopics:
                    sub_vec = embedding_service.embed(sub)
                    sims = [embedding_service.cosine_sim(sub_vec, sv) for sv in seg_vecs]
                    subtopic_scores.append(max(sims) if sims else 0.0)
                topic_coverage = float(np.clip(np.mean(subtopic_scores), 0.0, 1.0))
            else:
                topic_coverage = relevance
        else:
            topic_coverage = relevance

        # 3. Depth (Vocabulary richness + drift)
        words = [w.lower() for w in re.findall(r"\b\w+\b", content_text) if w.lower() not in STOPWORDS]
        vocab_richness = len(set(words)) / max(len(words), 1) if words else 0.0
        
        if segments and len(segments) > 2:
            seg_vecs = embedding_service.embed_batch([s["text"] for s in segments if s.get("text")])
            if len(seg_vecs) > 1:
                drifts = [1.0 - embedding_service.cosine_sim(seg_vecs[i], seg_vecs[i+1]) for i in range(len(seg_vecs)-1)]
                avg_drift = float(np.mean(drifts))
            else:
                avg_drift = 0.5
        else:
            avg_drift = 0.5
        depth = float(np.clip(vocab_richness * 0.5 + avg_drift * 0.5, 0.0, 1.0))

        # 4. Examples
        example_matches = 0
        for pat in EXAMPLE_PATTERNS:
            example_matches += len(re.findall(pat, content_text, re.IGNORECASE))
        example_density = example_matches / max(len(content_text.split()) / 100.0, 1.0)
        examples = float(np.clip(example_density / 3.0, 0.0, 1.0))

        # 5. Clarity (Flesch Reading Ease)
        try:
            flesch_fn = getattr(textstat, "flesch_reading_ease")
            reading_ease = float(flesch_fn(content_text))
            clarity = float(np.clip(reading_ease / 100.0, 0.0, 1.0))
        except Exception:
            clarity = 0.5

        # 6. Structure
        has_chapters = 1.0 if (re.search(r"\d{1,2}:\d{2}", description) or "0:" in content_text) else 0.5
        sentences = [s.strip() for s in re.split(r"[.!?]", content_text) if s.strip()]
        if sentences:
            sentence_lens = [len(s.split()) for s in sentences]
            std_dev = float(np.std(sentence_lens)) if len(sentence_lens) > 1 else 5.0
            pacing_score = float(np.clip(1.0 - (std_dev / 25.0), 0.0, 1.0))
        else:
            pacing_score = 0.5
        structure = float(np.clip(has_chapters * 0.5 + pacing_score * 0.5, 0.0, 1.0))

        # 7. Redundancy (inverted: lower pairwise similarity = lower redundancy = higher score)
        if segments and len(segments) > 2:
            seg_vecs = embedding_service.embed_batch([s["text"] for s in segments if s.get("text")])
            if len(seg_vecs) > 1:
                similarities = []
                for i in range(min(len(seg_vecs), 10)):
                    for j in range(i+1, min(len(seg_vecs), 10)):
                        similarities.append(embedding_service.cosine_sim(seg_vecs[i], seg_vecs[j]))
                avg_similarity = float(np.mean(similarities)) if similarities else 0.5
                redundancy_score = float(np.clip(1.0 - avg_similarity, 0.0, 1.0))
            else:
                redundancy_score = 0.5
        else:
            redundancy_score = 0.5

        # If transcript not available, penalize scores slightly
        if not transcript_available:
            relevance *= 0.8
            topic_coverage *= 0.7
            depth *= 0.6
            examples *= 0.5
            structure *= 0.5

        # Compute weighted overall score (0.0 to 100.0)
        weights = {
            "relevance": 0.25,
            "topic_coverage": 0.20,
            "depth": 0.15,
            "examples": 0.10,
            "clarity": 0.10,
            "structure": 0.10,
            "redundancy": 0.10
        }
        overall = (
            relevance * weights["relevance"] +
            topic_coverage * weights["topic_coverage"] +
            depth * weights["depth"] +
            examples * weights["examples"] +
            clarity * weights["clarity"] +
            structure * weights["structure"] +
            redundancy_score * weights["redundancy"]
        ) * 100.0

        return MediumAnalysisScores(
            relevance=round(relevance, 3),
            topic_coverage=round(topic_coverage, 3),
            depth=round(depth, 3),
            examples=round(examples, 3),
            clarity=round(clarity, 3),
            structure=round(structure, 3),
            redundancy=round(redundancy_score, 3),
            overall=round(overall, 1),
            transcript_available=transcript_available
        )

medium_analysis_service = MediumAnalysisService()
