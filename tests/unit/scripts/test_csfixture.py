import re
import subprocess

import pytest

from conftest import CSFIX, key_line, line_of

MARKERS = """ci-test
ep-sample ep-main io-args io-stdin io-exit ep-cli cc-process
ep-program io-config io-env bs-di bs-scan ep-hosted-add io-outbound-add bs-convention bs-filter ep-min-get bs-group
ep-min-post bs-route bs-conventional ep-hub ep-grpc fail-handler io-log io-stdout not-route
ep-ctl-list ep-ctl-get ep-ctl-abs io-error io-header bs-mediator-send bs-resolve
io-outbound io-db io-db-save fail-tx fail-catch io-log2 fail-retry io-file-read io-file-write cc-lock cc-async state-static io-produce
ep-hosted bs-handler bs-filter-class bs-convention-class bs-reflect bs-generator bs-partial bs-flag ep-cron ep-queue
ep-func ep-func-timer ep-razor ep-blazor
model-order model-enum api-interface api-method api-ext api-internal dead-type api-nested api-protected api-hidden api-polyfill
api-partial-a api-partial-b scip-collide-a model-customer
model-ctx io-db-connect io-connstr model-migration bs-codegen not-entity model-dapper io-dapper scip-collide-b
test-skip test-mock test-fixture test-ignore ep-target""".split()


def all_files():
    return [p for p in CSFIX.rglob("*") if p.is_file()]


class TestCsFixture:
    @pytest.mark.parametrize("name", MARKERS)
    def test_marker_appears_exactly_once_in_the_fixture(self, name):
        pattern = re.compile(r"@" + re.escape(name) + r"(?![\w-])")

        count = sum(len(pattern.findall(p.read_text(encoding="utf-8"))) for p in all_files())

        assert count == 1

    def test_every_file_is_under_forty_lines(self):
        long = [str(p.relative_to(CSFIX)) for p in all_files() if len(p.read_text().splitlines()) >= 40]

        assert long == []

    def test_line_of_and_key_line_find_lines(self, cs_repo):
        assert cs_repo.line_of("src/Shop.Api/Program.cs", "ep-program") == 3
        assert cs_repo.key_line("src/Shop.Api/Properties/launchSettings.json", "ASPNETCORE_ENVIRONMENT") == \
            key_line(CSFIX, "src/Shop.Api/Properties/launchSettings.json", "ASPNETCORE_ENVIRONMENT")
        with pytest.raises(LookupError):
            cs_repo.line_of("src/Shop.Api/Program.cs", "nope")

    def test_fixture_commits_as_one_commit_on_main(self, cs_repo):
        log = subprocess.run(["git", "-C", cs_repo.path, "log", "--oneline"], capture_output=True, text=True).stdout.splitlines()

        assert len(log) == 1

    def test_every_tracked_file_made_it_into_the_commit(self, cs_repo):
        tracked = subprocess.run(["git", "-C", cs_repo.path, "ls-files"], capture_output=True, text=True).stdout.split()

        assert len(tracked) == len(all_files())

    def test_only_shop_core_has_a_lock_file(self, cs_repo):
        tracked = subprocess.run(["git", "-C", cs_repo.path, "ls-files"], capture_output=True, text=True).stdout.split()

        assert [p for p in tracked if p.endswith("packages.lock.json")] == ["src/Shop.Core/packages.lock.json"]
