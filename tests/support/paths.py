"""Where things are, for tests: the skill folder, the fixture repositories and the two launchers."""
from dossier import resources

SKILL_ROOT = resources.skill_root()
FIXTURES = SKILL_ROOT / "tests" / "fixtures"
LAUNCHER = SKILL_ROOT / "scripts" / "dossier.py"
CHECK_PAGE = SKILL_ROOT / "scripts" / "check_page.py"
