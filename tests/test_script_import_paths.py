from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_scripts_prefer_the_current_src_tree():
    for name in ("benchmark_runtime.py", "check_environment.py"):
        content = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "ROOT = Path(__file__).resolve().parent.parent" in content
        assert 'sys.path.insert(0, str(ROOT / "src"))' in content
