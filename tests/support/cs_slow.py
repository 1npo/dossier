"""Marker tables shared by the C# adapter and Semgrep slow tests."""

IO = {"io-args": "cli-args", "io-config": "config-file", "io-connstr": "config-file", "io-dapper": "db-access", "io-db": "db-access", "io-db-connect": "db-connect",
      "io-db-save": "db-access", "io-env": "env-var", "io-error": "error-response", "io-exit": "exit-code", "io-file-read": "file-read", "io-file-write": "file-write",
      "io-header": "request-header", "io-log": "log", "io-log2": "log", "io-outbound": "outbound-call", "io-outbound-add": "outbound-call", "io-produce": "message-produce",
      "io-stdin": "stdin", "io-stdout": "stdout", "fail-catch": "catch-all", "fail-handler": "catch-all", "fail-retry": "retry", "fail-tx": "transaction",
      "cc-lock": "lock", "cc-async": "async"}

BLIND = {"bs-di": "di-registration", "bs-scan": "di-scan", "bs-convention": "route-convention", "bs-convention-class": "route-convention", "bs-filter": "mvc-filter",
         "bs-filter-class": "mvc-filter", "bs-group": "route-mount", "bs-route": "string-route", "bs-conventional": "conventional-route",
         "bs-mediator-send": "mediator-handler", "bs-handler": "mediator-handler", "bs-resolve": "di-resolution", "bs-reflect": "reflection",
         "bs-flag": "feature-flag", "bs-generator": "source-generator", "bs-partial": "partial-class"}
