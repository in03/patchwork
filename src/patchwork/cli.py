import os

import inquirer
import typer
from pydavinci import davinci
from rich import print
from rich.panel import Panel
from rich.prompt import Confirm

from patchwork.app import MasterFile, track_render
from patchwork.constants import STANDARD_RENDER_PRESETS
from patchwork.settings.manager import settings
from pyfiglet import Figlet

resolve = davinci.Resolve()
typer_app = typer.Typer()

figlet = Figlet(font="rectangles")
print(f"[cyan]{figlet.renderText('patchwork')}")

# CLI HANDLERS AND PROMPTS


def okay_to_write_sidecar(sidecar_output_path: str) -> bool:

    if os.path.exists(sidecar_output_path):
        if not Confirm.ask(
            "Looks like a sidecar file already exists with that name.\n"
            "It's linked render file is missing, "
            "so it's likely an orphan.\n"
            "Overwrite?"
        ):
            return False
    return True


def choose_render_preset():

    # Remove generic presets?
    rp = resolve.project.render_presets
    if not settings.render.allow_generic_render_presets:
        rp = [x for x in rp if x not in STANDARD_RENDER_PRESETS]

    # Prompt for chosen preset
    if choice := inquirer.prompt([
        inquirer.List(
            'render_preset',
            message="Choose a render preset",
            choices=rp,
        )
    ]):
        return choice
    exit()


def choose_render_mode():

    questions = [
        inquirer.List(
            'render_mode',
            message="Ready to render?",
            choices=["Local", "Network Render"],
        )
    ]
    answer = inquirer.prompt(questions)
    if not answer:
        exit()

    if answer == "Network Render":
        print(
            "[cyan]"
            "Cool! Select the network render machine, "
            "then start the render in Resolve."
        )

    else:
        print("[green]Starting render!")

    return answer["render_mode"]


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

    print()

    # Is resolve busy?
    if resolve.project.is_rendering():
        if Confirm.ask(
            "\nLooks like Resolve is busy rendering!\n"
            "You'll have to wait to queue a Patchwork job.\n"
            "Check again?"
        ):
            new()
        exit()

    # Are we happy?
    if not Confirm.ask(
        "\nAre you happy with the set render range?\n"
        "Have you set necessary in and outs?",
    ):
        exit()

    # Remove generic presets?
    rp = resolve.project.render_presets
    if not settings.render.allow_generic_render_presets:
        rp = [x for x in rp if x not in STANDARD_RENDER_PRESETS]

    # Prompt for chosen preset
    choice = inquirer.prompt([
        inquirer.List(
            'render_preset',
            message="Choose a render preset",
            choices=rp,
        )
    ])
    if not choice:
        exit()

    render_preset = choice["render_preset"]

    # Init masterfile
    masterfile = MasterFile(
        render_preset=render_preset,
        render_directory=settings.app.render_directory,
    )

    # Write sidecar?
    if not okay_to_write_sidecar(masterfile.sidecar_output_path):
        exit()

    # Write sidecar.
    masterfile.write_sidecar(overwrite=True)

    # Render
    render_mode = choose_render_mode()
    job_id = masterfile.start_render(render_mode)
    track_render(job_id)


@typer_app.command()
def patch():
    """Patch a master file with marked changes"""
    ...


def main():
    typer_app()


if __name__ == "__main__":
    main()
