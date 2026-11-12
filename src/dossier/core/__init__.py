"""Leaf utilities with no domain knowledge: config file, build log, graph helpers, card schema loader, SCIP reader.

May import (besides itself and the standard library): resources.

  buildlog   build.json: the crash-safe record of what each step of a build did. Standard library only.
  config     The dossier home config: one JSON file, owned by this module.
  graphs     Small graph helpers for the import graph: cycles, ranking, communities and grouping. Standard library only.
  schema     Card schema: load src/dossier/data/schemas/cards/*.json, lint them, and check a report against its schema (V6).
  scip_read  A standard-library reader for the SCIP index file (protobuf wire format) written by scip-python.
"""

__all__ = ["buildlog", "config", "graphs", "schema", "scip_read"]
