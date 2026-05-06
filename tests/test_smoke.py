import subprocess
import sys
import pytest

def test_cli_help_smoke():
    """Verify that the CLI can at least import and show help without crashing."""
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Available commands" in result.stdout

def test_imports_smoke():
    """Ensure all core modules can be imported without NameErrors or ImportErrors."""
    import src.main
    import src.collector
    import src.evaluator
    import src.review_tui
    import src.pipeline
    import src.llm_client
    import src.database
    import src.config_loader
