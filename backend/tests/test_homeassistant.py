import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.utils.homeassistant import DoorUnavailable, open_door


@pytest.fixture
def ha(monkeypatch):
    monkeypatch.setattr(settings, "ha_url", "https://ha.example.test")
    monkeypatch.setattr(settings, "ha_token", "test-token")
    monkeypatch.setattr(settings, "ha_door_scripts", {"room-public-id": "script.open_door"})


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr("app.utils.homeassistant.httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


async def test_calls_only_configured_script_with_backend_token(ha, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://ha.example.test/api/services/script/open_door"
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.content == b"{}"
        return httpx.Response(200, json=[])

    transport(monkeypatch, handler)
    await open_door("room-public-id")
    assert len(calls) == 1


async def test_unmapped_room_never_calls_homeassistant(ha, monkeypatch):
    def handler(request):
        pytest.fail("Unmapped rooms must not trigger a door")

    transport(monkeypatch, handler)
    with pytest.raises(DoorUnavailable):
        await open_door("another-room")


@pytest.mark.parametrize("status", [302, 401, 404, 500])
async def test_failure_or_redirect_is_not_success(ha, monkeypatch, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://elsewhere.test"})

    transport(monkeypatch, handler)
    with pytest.raises(DoorUnavailable):
        await open_door("room-public-id")
    assert len(calls) == 1


async def test_timeout_does_not_retry_opening(ha, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)

    transport(monkeypatch, handler)
    with pytest.raises(DoorUnavailable):
        await open_door("room-public-id")
    assert len(calls) == 1


async def test_missing_token_is_not_a_fake_success(ha, monkeypatch):
    monkeypatch.setattr(settings, "ha_token", "")
    with pytest.raises(DoorUnavailable):
        await open_door("room-public-id")


def test_script_mapping_rejects_arbitrary_service_paths():
    with pytest.raises(ValidationError):
        Settings(ha_door_scripts={"room": "../something"})
