from __future__ import annotations

import os
import re
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


MODEL_ID = "zilliz/semantic-highlight-bilingual-v1"


@dataclass(frozen=True)
class SelectionItem:
    id: str | None
    question: str
    threshold: float


def sentence_spans(text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    normalized = text.replace("\n", " ")
    for match in re.finditer(r"[^.!?。！？]+[.!?。！？]?", normalized):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        leading = len(match.group(0)) - len(match.group(0).lstrip())
        trailing = len(match.group(0).rstrip())
        spans.append(
            {
                "index": len(spans),
                "text": sentence,
                "start": match.start() + leading,
                "end": match.start() + trailing,
            }
        )
    return spans


@lru_cache(maxsize=1)
def load_zilliz_model(model_id: str = MODEL_ID):
    import torch

    project_transformers_path = os.environ.get("PROJECT_TRANSFORMERS_PATH")
    if project_transformers_path and project_transformers_path not in sys.path:
        sys.path.insert(0, project_transformers_path)
    from transformers import AutoModel

    patch_xlm_roberta_tokenizer()
    patch_transformers_tied_weights()
    model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
    model.eval()
    if os.environ.get("LOCAL_AI_TOOLS_ZILLIZ_QUANTIZE_CPU", "1") != "0" and not torch.cuda.is_available():
        model = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
        model.eval()
    return model


def patch_xlm_roberta_tokenizer() -> None:
    try:
        from transformers import XLMRobertaTokenizer
    except Exception:
        return
    if hasattr(XLMRobertaTokenizer, "build_inputs_with_special_tokens"):
        has_build_inputs = True
    else:
        has_build_inputs = False

    def build_inputs_with_special_tokens(self, token_ids_0, token_ids_1=None):
        cls = self.cls_token_id if self.cls_token_id is not None else 0
        sep = self.sep_token_id if self.sep_token_id is not None else 2
        if token_ids_1 is None:
            return [cls, *token_ids_0, sep]
        return [cls, *token_ids_0, sep, sep, *token_ids_1, sep]

    def create_token_type_ids_from_sequences(self, token_ids_0, token_ids_1=None):
        return [0] * len(build_inputs_with_special_tokens(self, token_ids_0, token_ids_1))

    if not has_build_inputs:
        XLMRobertaTokenizer.build_inputs_with_special_tokens = build_inputs_with_special_tokens
    XLMRobertaTokenizer.create_token_type_ids_from_sequences = create_token_type_ids_from_sequences


def patch_transformers_tied_weights() -> None:
    try:
        from transformers.modeling_utils import PreTrainedModel
    except Exception:
        return
    if hasattr(PreTrainedModel, "all_tied_weights_keys"):
        return

    def get_all_tied_weights_keys(self):
        value = getattr(self, "_all_tied_weights_keys", None) or getattr(self, "_tied_weights_keys", None) or {}
        if isinstance(value, dict):
            return value
        return {key: [] for key in value}

    def set_all_tied_weights_keys(self, value):
        self._all_tied_weights_keys = value if isinstance(value, dict) else {key: [] for key in value}

    PreTrainedModel.all_tied_weights_keys = property(get_all_tied_weights_keys, set_all_tied_weights_keys)


class ZillizSelector:
    def __init__(self, model_id: str = MODEL_ID) -> None:
        self.model_id = model_id
        self.model = load_zilliz_model(model_id)
        self.batch_size = int(os.environ.get("LOCAL_AI_TOOLS_ZILLIZ_BATCH_SIZE", "32"))

    def select(self, text: str, items: list[SelectionItem], language: str = "auto", include_all_scores: bool = False) -> dict[str, Any]:
        try:
            import torch

            inference = torch.inference_mode()
        except Exception:
            inference = nullcontext()

        sentences = sentence_spans(text)
        if not sentences or not items:
            return {"model": self.model_id, "language": language, "sentence_count": len(sentences), "results": []}

        questions = [item.question for item in items]
        contexts = [text] * len(items)
        threshold = min(item.threshold for item in items)
        with inference:
            output = self.model.process(
                question=questions,
                context=contexts,
                threshold=threshold,
                language=None if language == "auto" else language,
                return_sentence_metrics=True,
                show_progress=False,
                show_inference_progress=False,
                batch_size=self.batch_size,
            )

        probability_rows = output.get("sentence_probabilities", [])
        results = []
        for item_index, item in enumerate(items):
            probabilities = probability_rows[item_index] if item_index < len(probability_rows) else []
            selections = []
            scores = []
            for sentence, raw_score in zip(sentences, probabilities):
                score = float(raw_score)
                scored = {**sentence, "score": score}
                if include_all_scores:
                    scores.append(scored)
                if score >= item.threshold:
                    selections.append(scored)
            row = {
                "id": item.id,
                "question": item.question,
                "threshold": item.threshold,
                "selections": selections,
            }
            if include_all_scores:
                row["scores"] = scores
            results.append(row)

        return {
            "model": self.model_id,
            "language": language,
            "sentence_count": len(sentences),
            "results": results,
        }


def selection_items(raw_items: list[dict[str, Any]]) -> list[SelectionItem]:
    return [
        SelectionItem(
            id=item.get("id"),
            question=str(item["question"]).strip(),
            threshold=float(item.get("threshold", 0.5)),
        )
        for item in raw_items
        if str(item.get("question", "")).strip()
    ]
