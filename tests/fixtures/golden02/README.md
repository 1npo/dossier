# Report 02 screenshot baselines

Screenshots of report 02's three cards (`facts-git`, `facts-contributors`, `facts-dependencies`) at 1500 x 1000 px in the light and
dark themes, made by the skill as it was before the tier work (commit `fc916d6`), from the frozen fixture `tests/fixtures/encamp-m0`.
`tests/tools/golden02.py` compares a page with them; `tests/integration/scripts/test_golden02_slow.py` runs that for the page the
current code renders (`DOSSIER_SLOW=1`).

The PNG files are git-ignored (like the fixture, which is also local). They depend on the fonts installed on the machine, so make them
on the machine that runs the test. To make them again, from the repository root:

```bash
SCR=$(mktemp -d)
SKILL=configs/user/claude/.claude/skills/dossier
git worktree add --detach $SCR/wt-pre fc916d6
mkdir -p $SCR/pre/home && cp -r $SKILL/tests/fixtures/encamp-m0 $SCR/pre/home/encamp
chmod -R u+w $SCR/pre/home/encamp && rm -f $SCR/pre/home/encamp/dossier-encamp.html
(cd $SCR/wt-pre/$SKILL && DOSSIER_HOME=$SCR/pre/home DOSSIER_CONFIG=$SCR/pre/cfg.json DOSSIER_CACHE=$SCR/pre/cache \
   uv run --with pygments python scripts/dossier.py render "$OLDPWD" --allow-errors)
uv run $SKILL/tests/tools/golden02.py --write-baseline $SCR/pre/home/encamp/dossier-encamp.html $SKILL/tests/fixtures/golden02
git worktree remove --force $SCR/wt-pre
```

The fixture is in the pre-M0 layout already, so the old skill needs no `migrate`.
