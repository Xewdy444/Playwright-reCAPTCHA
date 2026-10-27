from unittest.mock import AsyncMock, MagicMock

import pytest

from playwright_recaptcha import recaptchav2

DEFAULT_URL = "https://api.capsolver.com/createTask"
OK_RESPONSE = {"errorId": 0, "solution": {"hasObject": True}}


def _sync_solver(monkeypatch, **kwargs):
    page = MagicMock()
    page.request.post.return_value.json.return_value = OK_RESPONSE
    solver = recaptchav2.SyncSolver(page, capsolver_api_key="key", **kwargs)
    monkeypatch.setattr(solver, "_get_task_object", lambda _: "vehicles")
    return solver, page


@pytest.mark.parametrize(
    ("argument", "env", "expected"),
    [
        (None, None, DEFAULT_URL),
        (None, "https://env.example/", "https://env.example/createTask"),
        (
            "https://arg.example",
            "https://env.example",
            "https://arg.example/createTask",
        ),
    ],
)
def test_sync_solver_capsolver_api_url(monkeypatch, argument, env, expected) -> None:
    """Test that the CapSolver base URL can be configured."""
    monkeypatch.delenv("CAPSOLVER_API_URL", raising=False)

    if env is not None:
        monkeypatch.setenv("CAPSOLVER_API_URL", env)

    solver, page = _sync_solver(monkeypatch, capsolver_api_url=argument)
    assert solver._get_capsolver_response(MagicMock(), b"image") == OK_RESPONSE
    assert page.request.post.call_args.args[0] == expected


@pytest.mark.asyncio
async def test_async_solver_capsolver_api_url(monkeypatch) -> None:
    """Test that the async solver posts to the configured CapSolver base URL."""
    monkeypatch.delenv("CAPSOLVER_API_URL", raising=False)

    page = MagicMock()
    response = MagicMock()
    response.json = AsyncMock(return_value=OK_RESPONSE)
    page.request.post = AsyncMock(return_value=response)
    page.on = MagicMock()

    solver = recaptchav2.AsyncSolver(
        page, capsolver_api_key="key", capsolver_api_url="https://api.solvecha.com"
    )
    monkeypatch.setattr(solver, "_get_task_object", AsyncMock(return_value="vehicles"))

    assert await solver._get_capsolver_response(MagicMock(), b"image") == OK_RESPONSE
    assert page.request.post.call_args.args[0] == "https://api.solvecha.com/createTask"
