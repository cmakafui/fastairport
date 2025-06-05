from typer.testing import CliRunner

from fastairport.cli.main import app
from fastairport import FastAirport


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "FastAirport" in result.stdout


def test_cli_serve_invokes_start(tmp_path, monkeypatch):
    file = tmp_path / "srv.py"
    file.write_text(
        "from fastairport import FastAirport\nairport = FastAirport('Demo')\n"
    )

    called = {}

    def fake_start(self, host: str = "0.0.0.0", port: int = 8815):
        called["host"] = host
        called["port"] = port

    monkeypatch.setattr(FastAirport, "start", fake_start)

    runner = CliRunner()
    result = runner.invoke(app, ["serve", str(file), "--host", "127.0.0.1", "--port", "9999"])

    assert result.exit_code == 0
    assert called == {"host": "127.0.0.1", "port": 9999}

