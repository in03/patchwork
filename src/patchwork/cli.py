import typer
from patchwork import app
from rich import print
from rich.panel import Panel

typer_app = typer.Typer()


@typer_app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        print()
        print(Panel(
            "\n"
            "Patchwork patches render files with changes "
            "marked in your timeline to save you time.\n"
            "Run `patchwork new` to render a new master file "
            "with the current timeline,\n"
            "Or run `patchwork patch` to patch an existing "
            "master file with segments marked "
            "by ranged markers in the current timeline.",
            title="Welcome to Patchwork!",
            title_align="left",
            expand=False,
        ))


@typer_app.command()
def new():
    """Render a new master file of the current timeline"""
    app.render_master_file()


@typer_app.command()
def patch():
    """Patch a master file with marked changes"""
    ...


typer_app()
