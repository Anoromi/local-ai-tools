from __future__ import annotations

import os
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


MODEL_ID = "tasksource/ModernBERT-base-nli"
DEFAULT_HYPOTHESIS_TEMPLATE = "This sentence indicates {}."


@dataclass(frozen=True)
class ClassificationSentence:
    id: str | None
    text: str


@dataclass(frozen=True)
class ClassificationLabel:
    id: str
    label: str
    threshold: float | None = None


def _prepare_transformers_path() -> None:
    project_transformers_path = os.environ.get("PROJECT_TRANSFORMERS_PATH")
    if project_transformers_path and project_transformers_path not in sys.path:
        sys.path.insert(0, project_transformers_path)


@lru_cache(maxsize=1)
def load_modernbert_pipeline(model_id: str = MODEL_ID):
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("ModernBERT classification requires ROCm/CUDA; CPU fallback is disabled")
    _prepare_transformers_path()
    from transformers import pipeline

    return pipeline("zero-shot-classification", model=model_id, device=0)


class ModernBertClassifier:
    def __init__(self, model_id: str = MODEL_ID) -> None:
        self.model_id = model_id
        self.classifier = load_modernbert_pipeline(model_id)
        self.batch_size = int(os.environ.get("LOCAL_AI_TOOLS_MODERNBERT_BATCH_SIZE", "32"))

    def classify(
        self,
        sentences: list[ClassificationSentence],
        labels: list[ClassificationLabel],
        threshold: float = 0.5,
        hypothesis_template: str = DEFAULT_HYPOTHESIS_TEMPLATE,
        include_all_scores: bool = False,
    ) -> dict[str, Any]:
        if not sentences or not labels:
            return {
                "model": self.model_id,
                "sentence_count": len(sentences),
                "label_count": len(labels),
                "hypothesis_template": hypothesis_template,
                "results": [],
            }

        try:
            import torch

            inference = torch.inference_mode()
        except Exception:
            inference = nullcontext()

        sentence_texts = [sentence.text for sentence in sentences]
        label_texts = [label.label for label in labels]
        with inference:
            outputs = self.classifier(
                sentence_texts,
                candidate_labels=label_texts,
                multi_label=True,
                hypothesis_template=hypothesis_template,
                truncation=True,
                batch_size=self.batch_size,
            )
        if isinstance(outputs, dict):
            outputs = [outputs]

        results: list[dict[str, Any]] = []
        threshold_by_id = {label.id: label.threshold if label.threshold is not None else threshold for label in labels}
        for sentence, output in zip(sentences, outputs):
            score_by_label = {str(label): float(score) for label, score in zip(output.get("labels", []), output.get("scores", []))}
            scored = [
                {
                    "id": label.id,
                    "label": label.label,
                    "score": score_by_label.get(label.label, 0.0),
                }
                for label in labels
            ]
            scored.sort(key=lambda item: item["score"], reverse=True)
            matches = [item for item in scored if item["score"] >= threshold_by_id[item["id"]]]
            row: dict[str, Any] = {
                "id": sentence.id,
                "text": sentence.text,
                "matches": matches,
                "top_label": scored[0]["id"] if scored else None,
                "top_score": scored[0]["score"] if scored else None,
            }
            if include_all_scores:
                row["all_scores"] = scored
            results.append(row)

        return {
            "model": self.model_id,
            "sentence_count": len(sentences),
            "label_count": len(labels),
            "hypothesis_template": hypothesis_template,
            "results": results,
        }


def classification_sentences(raw_sentences: list[Any]) -> list[ClassificationSentence]:
    sentences: list[ClassificationSentence] = []
    for item in raw_sentences:
        if isinstance(item, str):
            text = item.strip()
            if text:
                sentences.append(ClassificationSentence(id=None, text=text))
            continue
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            if text:
                item_id = item.get("id")
                sentences.append(ClassificationSentence(id=item_id if isinstance(item_id, str) else None, text=text))
    return sentences


def classification_labels(raw_labels: list[Any]) -> list[ClassificationLabel]:
    labels: list[ClassificationLabel] = []
    for item in raw_labels:
        if isinstance(item, str):
            label = item.strip()
            if label:
                labels.append(ClassificationLabel(id=label, label=label))
            continue
        if isinstance(item, dict):
            label = str(item.get("label", "")).strip()
            if label:
                item_id = item.get("id")
                labels.append(
                    ClassificationLabel(
                        id=item_id.strip() if isinstance(item_id, str) and item_id.strip() else label,
                        label=label,
                        threshold=None if item.get("threshold") is None else float(item["threshold"]),
                    )
                )
    return labels
