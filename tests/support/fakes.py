"""Fakes that more than one test module uses."""


class FakeSemgrep:
    def __init__(self, results=None, error=None):
        self.results, self.error, self.calls = results or [], error, []

    def scan(self, config, paths=None, timeout=30):
        self.calls.append((config, paths))
        if self.error:
            raise self.error
        return self.results
