"""One module per group of CLI commands.

May import (besides itself and the standard library): anything in the package.

  basics      The small commands: `version`, `home`, `portfolio`, `doctor` and `clean`. They read the config and the tool table and, for `clean`, remove one repository's working area.
  candidates  `candidates`: list the tool findings a report must keep, merge or dismiss. Read only.
  check       `check`: audit a written page, and the browser check it may run. Reads the HTML and the build log; never rewrites the page.
  decisions   `correct` and `confirm`: record the user's corrections and their decisions on open items in the decisions file. Never edits a report.
  prepare     `prepare`: check the tools, make a clean copy, measure the repository, and write facts, the reading plan and the update plan. Never writes the reports or the HTML.
  render      `render`: validate the reports and write the HTML page, the summary and the build log. Runs the browser check line from `check` for the build record.
  verify      `verify-sample` and `verify-record`: pick cited claims for the independent check and record its verdicts in the build log.
"""

__all__ = ["basics", "candidates", "check", "decisions", "prepare", "render", "verify"]
