"""TrustedHost: Alertmanager y otros clientes Docker deben poder usar Host=api."""

from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.main import app


def _middleware_kwargs(middleware) -> dict:
    """Starlette>=1.x: kwargs; versiones previas: options."""
    kwargs = getattr(middleware, "kwargs", None)
    if kwargs is not None:
        return kwargs
    options = getattr(middleware, "options", None)
    if options is not None:
        return options
    raise AssertionError(f"Middleware sin kwargs/options: {middleware!r}")


def test_trusted_hosts_always_include_compose_service_names() -> None:
    for middleware in app.user_middleware:
        if middleware.cls is not TrustedHostMiddleware:
            continue
        hosts = _middleware_kwargs(middleware)["allowed_hosts"]
        for required in ("api", "api_dev", "gridbot_api", "gridbot_api_dev"):
            assert required in hosts, f"falta {required} en allowed_hosts={hosts!r}"
        assert "testserver" in hosts or "localhost" in hosts
        return
    raise AssertionError("TrustedHostMiddleware no está registrado")
