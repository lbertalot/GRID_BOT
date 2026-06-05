"""TrustedHost: Alertmanager y otros clientes Docker deben poder usar Host=api."""

from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.main import app


def test_trusted_hosts_always_include_compose_service_names() -> None:
    for middleware in app.user_middleware:
        if middleware.cls is not TrustedHostMiddleware:
            continue
        hosts = middleware.options["allowed_hosts"]
        for required in ("api", "api_dev", "gridbot_api", "gridbot_api_dev"):
            assert required in hosts, f"falta {required} en allowed_hosts={hosts!r}"
        assert "testserver" in hosts or "localhost" in hosts
        return
    raise AssertionError("TrustedHostMiddleware no está registrado")
