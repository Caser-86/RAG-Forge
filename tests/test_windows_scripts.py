from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _script(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_windows_scripts_are_repo_relative_and_use_venv():
    start = _script("start.ps1")
    assert "$PSScriptRoot" in start
    assert ".venv" in start
    assert "Start-Process" in start
    assert "-WindowStyle Hidden" in start
    assert "-WorkingDirectory $RepoRoot" in start


def test_local_process_scripts_prefer_current_src_over_stale_installed_package():
    start = _script("start.ps1")
    browser = _script("verify_browser_e2e.ps1")

    for script in (start, browser):
        assert "PYTHONPATH" in script
        assert "Join-Path $RepoRoot \"src\"" in script


def test_windows_scripts_verify_process_identity_before_mutation():
    start = _script("start.ps1")
    status = _script("status.ps1")
    stop = _script("stop.ps1")
    for script in (start, status, stop):
        assert "project_path" in script
        assert "process_start_time" in script
        assert "Get-CimInstance Win32_Process" in script
    assert "Stop-Process" in stop
    assert "Ollama" in stop


def test_windows_scripts_keep_runtime_state_out_of_git():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/run/" in gitignore


def test_locked_install_script_selects_only_supported_windows_lock_profiles():
    script = _script("install_locked.ps1")
    assert "windows-vector-dev-py314-piptools.txt" in script
    assert "windows-local-py314-piptools.txt" in script
    assert "windows-collector-py314-piptools.txt" in script
    assert "pip check" in script
    assert "--no-deps ." in script
