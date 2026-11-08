"""Load all isolated collaboration regression tests during root Python discovery."""
import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    folder = Path(__file__).resolve().parents[1] / "ai-collab" / "tests"
    for source in sorted(folder.glob("test_*.py")):
        spec = importlib.util.spec_from_file_location("ai_collab_v4_" + source.stem, source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tests.addTests(loader.loadTestsFromModule(module))
    return tests
