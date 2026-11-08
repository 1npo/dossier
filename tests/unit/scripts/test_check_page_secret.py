import re

import pytest

pytest.importorskip("playwright")
import check_page  # noqa: E402


class TestSecretPath:
    """The browser check must flag the same files the page refuses to open (`gather.SENSITIVE_FILE`)."""

    @pytest.mark.parametrize("path", ["apps/web/.env.example", "apps/web/.env.example-e2e", ".env.sample", "a/.env.template", ".env.dist"])
    def test_env_templates_are_not_secret(self, path):
        assert not re.search(check_page.SECRET_PATH, path)

    @pytest.mark.parametrize("path", [".env", "apps/web/.env.local", ".env.production", "keys/id_rsa", "certs/server.pem"])
    def test_real_secret_files_are_secret(self, path):
        assert re.search(check_page.SECRET_PATH, path)
