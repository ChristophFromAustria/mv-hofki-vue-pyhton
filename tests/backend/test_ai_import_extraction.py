"""LLM client payload/response handling and the extraction schema."""

import json

import httpx
import pytest

from mv_hofki.services.ai_import.extraction import (
    EXTRACTION_SCHEMA,
    PageExtraction,
    build_prompt,
    extract_page,
    to_pixel_boxes,
)
from mv_hofki.services.ai_import.llm_client import (
    MAX_IMAGES_PER_REQUEST,
    LlmClient,
    LlmError,
)
from mv_hofki.services.ai_import.pages import PageImage

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0000000030001a6a0c5d10000000049454e44ae426082"
)

SAMPLE_EXTRACTION = {
    "page_kind": "mixed",
    "instruments": [
        {
            "inventory_nr": "12",
            "instrument_type": "Trompete Bb",
            "label": None,
            "manufacturer": "Yamaha",
            "model": None,
            "serial_nr": "YTR-4335 A",
            "construction_year": 2009,
            "acquisition_date": None,
            "acquisition_cost": "1.200 €",
            "distributor": None,
            "container": "Koffer",
            "particularities": None,
            "owner": None,
            "loan": {
                "musician_name": "Hofer Anna",
                "start_date": "14.03.2021",
                "end_date": None,
                "remarks": None,
            },
            "source_text": "12 Trompete Bb Yamaha YTR-4335 A 2009 Hofer Anna 14.03.21",
            "confidence": "high",
            "bbox_2d": [48, 167, 968, 211],
        }
    ],
    "photos": [
        {"caption": "Foto Nr. 12", "inventory_nr": "12", "bbox_2d": [65, 378, 452, 911]}
    ],
    "remarks": None,
}


def _completion(content: str, finish_reason: str = "stop") -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _client_with(handler) -> LlmClient:
    return LlmClient(
        base_url="http://llm.test/v1",
        model="test-model",
        timeout=5,
        transport=httpx.MockTransport(handler),
    )


def _page() -> PageImage:
    return PageImage(
        index=2, png=PNG_1PX, width=1240, height=900, source_name="inv.pdf"
    )


# --- schema -------------------------------------------------------------


def _walk(schema: dict):
    """Yield every object schema nested inside ``schema``."""
    if schema.get("type") == "object":
        yield schema
    for v in schema.get("properties", {}).values():
        yield from _walk(v)
    if "items" in schema:
        yield from _walk(schema["items"])
    for alt in schema.get("anyOf", []):
        yield from _walk(alt)


def test_schema_objects_require_every_property():
    # Guided decoding is most reliable when the model has no optional keys.
    objects = list(_walk(EXTRACTION_SCHEMA))
    assert len(objects) >= 4
    for obj in objects:
        assert set(obj["required"]) == set(obj["properties"]), obj["properties"].keys()
        assert obj["additionalProperties"] is False


def test_schema_matches_pydantic_model():
    instrument_props = EXTRACTION_SCHEMA["properties"]["instruments"]["items"][
        "properties"
    ]
    from mv_hofki.services.ai_import.extraction import ExtractedInstrument

    assert set(instrument_props) == set(ExtractedInstrument.model_fields)
    assert set(EXTRACTION_SCHEMA["properties"]) == set(PageExtraction.model_fields)


def test_sample_validates_against_pydantic():
    ex = PageExtraction.model_validate(SAMPLE_EXTRACTION)
    assert ex.instruments[0].loan.musician_name == "Hofer Anna"
    assert ex.photos[0].bbox_2d == [65, 378, 452, 911]


def test_boxes_are_scaled_from_normalised_to_pixels():
    ex = PageExtraction.model_validate(SAMPLE_EXTRACTION)
    px = to_pixel_boxes(ex, 1240, 900)
    assert px.photos[0].bbox_2d == [81, 340, 560, 820]
    assert px.instruments[0].bbox_2d == [60, 150, 1200, 190]
    # the input is untouched (raw output stays as the model gave it)
    assert ex.photos[0].bbox_2d == [65, 378, 452, 911]


def test_boxes_are_clamped_and_ordered():
    ex = PageExtraction.model_validate(
        {
            **SAMPLE_EXTRACTION,
            "photos": [
                {
                    "caption": None,
                    "inventory_nr": None,
                    "bbox_2d": [1200, 500, 900, -20],
                }
            ],
        }
    )
    px = to_pixel_boxes(ex, 1000, 1000)
    assert px.photos[0].bbox_2d == [900, 0, 1000, 500]


def test_prompt_mentions_page_size():
    prompt = build_prompt(1240, 900)
    assert "1240 px" in prompt and "900 px" in prompt


# --- client ---------------------------------------------------------------


async def test_extract_page_sends_image_schema_and_parses_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion(json.dumps(SAMPLE_EXTRACTION)))

    result = await extract_page(_client_with(handler), _page())

    assert seen["url"] == "http://llm.test/v1/chat/completions"
    body = seen["body"]
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == EXTRACTION_SCHEMA
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["messages"][0]["role"] == "system"
    user_content = body["messages"][1]["content"]
    assert user_content[0]["type"] == "image_url"
    assert user_content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert user_content[1]["type"] == "text"

    assert result.source_name == "inv.pdf"
    assert result.page_index == 2
    assert (result.width, result.height) == (1240, 900)
    assert result.extraction.page_kind == "mixed"
    assert result.extraction.instruments[0].serial_nr == "YTR-4335 A"
    # pixel coordinates for consumers, model coordinates preserved in raw
    assert result.extraction.photos[0].bbox_2d == [81, 340, 560, 820]
    assert result.raw["photos"][0]["bbox_2d"] == [65, 378, 452, 911]
    assert result.duration_seconds is not None
    assert result.usage["total_tokens"] == 15


async def test_http_error_raises_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(LlmError, match="HTTP 500"):
        await extract_page(_client_with(handler), _page())


async def test_connection_error_raises_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(LlmError, match="nicht erreichbar"):
        await extract_page(_client_with(handler), _page())


async def test_truncated_answer_raises_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_completion('{"page_kind": "other", "instr', "length")
        )

    with pytest.raises(LlmError, match="abgeschnitten"):
        await extract_page(_client_with(handler), _page())


async def test_invalid_json_raises_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion("Hier ist das JSON: {"))

    with pytest.raises(LlmError, match="kein gültiges JSON"):
        await extract_page(_client_with(handler), _page())


def test_too_many_images_rejected():
    client = _client_with(lambda r: httpx.Response(200))
    with pytest.raises(LlmError):
        client.build_payload(
            "p", [PNG_1PX] * (MAX_IMAGES_PER_REQUEST + 1), EXTRACTION_SCHEMA
        )


async def test_list_models():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://llm.test/v1/models"
        return httpx.Response(
            200, json={"data": [{"id": "qwen-vl"}, {"id": "qwen3.8-27b"}]}
        )

    assert await _client_with(handler).list_models() == ["qwen-vl", "qwen3.8-27b"]
