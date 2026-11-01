# Semgrep rules

Semgrep rules shipped with dossier live here, one folder per scope (`all/`, `python/`, `js/`, `csharp/`). Rule files are YAML and end in `.yml`. Rule ids are `dossier.<scope>.<category>.<name>`, and `metadata.category` names the `io_candidates` category the rule feeds. Version 0.6.0 ships no rules; the Python set arrives with the Python adapter.
