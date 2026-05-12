from pathlib import Path
import json

import typer
import yaml
from rich import print

app = typer.Typer(help="ForgeMoE-R1-Agent-Coder command line interface.")


@app.command()
def doctor(config: Path = typer.Option(Path("configs/aws/paths.yaml"))):
    """Validate local project configuration."""
    if not config.exists():
        raise typer.BadParameter(f"Missing config: {config}")

    data = yaml.safe_load(config.read_text())
    print("[bold green]ForgeAgentCoder doctor[/bold green]")
    print(json.dumps(data, indent=2))


@app.command()
def version():
    """Print package version."""
    print("forgeagentcoder 0.1.0")


if __name__ == "__main__":
    app()
