from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_build_uses_python311_lock_and_non_editable_install():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "requirements/docker-py311-piptools.txt" in dockerfile
    assert "pip install" in dockerfile and "-r /tmp/requirements.txt" in dockerfile
    assert "pip wheel --no-deps" in dockerfile
    assert "-e \".[local,vector]\"" not in dockerfile
    assert "USER ragforge" in dockerfile


def test_ci_checks_tests_lint_wheel_and_dependency_audit():
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    content = workflow.read_text(encoding="utf-8")

    for required in (
        "windows-vector-dev-py314-piptools.txt",
        "pytest",
        "ruff check",
        "coverage run",
        "python -m build --wheel",
        "pip-audit",
    ):
        assert required in content
