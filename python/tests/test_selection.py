from local_ai_tools.selection import SelectionItem, ZillizSelector, patch_transformers_tied_weights, patch_xlm_roberta_tokenizer, sentence_spans


def test_sentence_spans_indexes_and_offsets():
    text = "First sentence. Second line!\nThird?"
    assert sentence_spans(text) == [
        {"index": 0, "text": "First sentence.", "start": 0, "end": 15},
        {"index": 1, "text": "Second line!", "start": 16, "end": 28},
        {"index": 2, "text": "Third?", "start": 29, "end": 35},
    ]


def test_selector_filters_scores_with_fake_model():
    class Model:
        def process(self, **_kwargs):
            return {"sentence_probabilities": [[0.2, 0.8], [0.9, 0.1]]}

    selector = object.__new__(ZillizSelector)
    selector.model_id = "fake"
    selector.model = Model()
    selector.batch_size = 32
    result = selector.select(
        "Alpha failed. Beta passed.",
        [
            SelectionItem(id="failed", question="What failed?", threshold=0.5),
            SelectionItem(id="passed", question="What passed?", threshold=0.5),
        ],
        "auto",
        False,
    )
    assert result["sentence_count"] == 2
    assert result["results"][0]["selections"][0]["text"] == "Beta passed."
    assert result["results"][1]["selections"][0]["text"] == "Alpha failed."


def test_xlm_roberta_patch_adds_special_token_builder(monkeypatch):
    class Tokenizer:
        cls_token_id = 0
        sep_token_id = 2

    import types

    module = types.SimpleNamespace(XLMRobertaTokenizer=Tokenizer)
    monkeypatch.setitem(__import__("sys").modules, "transformers", module)
    patch_xlm_roberta_tokenizer()
    assert Tokenizer().build_inputs_with_special_tokens([10], [20]) == [0, 10, 2, 2, 20, 2]
    assert Tokenizer().create_token_type_ids_from_sequences([10], [20]) == [0, 0, 0, 0, 0, 0]


def test_tied_weights_patch_adds_fallback_property(monkeypatch):
    class PreTrainedModel:
        pass

    import types

    module = types.SimpleNamespace(PreTrainedModel=PreTrainedModel)
    monkeypatch.setitem(__import__("sys").modules, "transformers.modeling_utils", module)
    patch_transformers_tied_weights()
    model = PreTrainedModel()
    model._tied_weights_keys = ["a"]
    assert model.all_tied_weights_keys == {"a": []}
    model.all_tied_weights_keys = ["b"]
    assert model.all_tied_weights_keys == {"b": []}
