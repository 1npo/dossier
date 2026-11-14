import pytest

from dossier.facts import gather


@pytest.fixture(autouse=True)
def opt_out():
    gather.include_test_reports(False)
    yield
    gather.include_test_reports(False)


@pytest.mark.parametrize("path", [
    ".coverage", ".coverage.host.123", "coverage.xml", "ci/Coverage.JSON", "coverage-final.json", "lcov.info", "a/b.lcov",
    "cobertura-coverage.xml", "jacoco.xml", "clover.xml", ".coverage-report.xml", "out/unit-coverage-report.md", "junit.xml", "TEST-foo.xml",
    "nosetests.xml", "test-results.xml", "r/test-results-1.json", "a.trx", "pytest-report.html",
    "htmlcov/index.html", ".nyc_output/x.json", "TestResults/a.txt", "test-reports/a.txt", "allure-results/a.json", "playwright-report/a.html",
])
def test_a_coverage_or_test_result_file_is_a_test_report(path):
    assert gather.noise_reason(path) == "test-report"


@pytest.mark.parametrize("path", ["src/app.py", "docs/coverage-notes.md", "TESTS.md", "tests/test_x.py", "README.md"])
def test_other_files_are_not_test_reports(path):
    assert gather.noise_reason(path) != "test-report"


def test_the_opt_in_reads_them_again():
    gather.include_test_reports(True)

    assert gather.noise_reason("coverage.xml") is None


class TestSniff:
    def test_coverage_py_xml(self):
        assert gather.sniff_test_report("cov/out.xml", b'<?xml version="1.0" ?>\n<coverage version="7.4" timestamp="1">')

    def test_junit_xml(self):
        assert gather.sniff_test_report("out/r.xml", b'<?xml version="1.0"?>\n<testsuites name="x">')

    def test_a_markdown_coverage_table(self):
        assert gather.sniff_test_report("TESTS.md", b"# Tests\n\n| Name | Stmts | Miss | Cover |\n|---|---|---|---|\n")

    def test_prose_about_coverage_is_not_a_report(self):
        assert not gather.sniff_test_report("NOTES.md", b"We track coverage. Stmts and Miss and Cover are explained below.\n")

    def test_python_source_that_mentions_a_testsuite_is_not_a_report(self):
        assert not gather.sniff_test_report("a.py", b"x = '<testsuite>'")
