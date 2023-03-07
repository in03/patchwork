import json
import os
import time
from tkinter import filedialog, messagebox

import ffmpeg
import inquirer
import toml
from pydavinci import davinci
from pydavinci.wrappers.marker import Marker
from rich import print
from rich.progress import Progress
from rich.prompt import Confirm

from patchwork import CONFIG_FILE, helpers
from patchwork.constants import STANDARD_RENDER_PRESETS

settings = toml.load(CONFIG_FILE)


resolve = davinci.Resolve()


def prompt_render_preset():

    all_presets = resolve.project.render_presets
    # print(all_presets)

    custom_presets = [
        x for x in all_presets if x not in STANDARD_RENDER_PRESETS
    ]
    custom_presets = sorted(custom_presets)

    questions = [
        inquirer.List(
            'render_preset',
            message="Choose a render preset",
            choices=custom_presets,
        )
    ]

    choice = inquirer.prompt(questions)
    if not choice:
        exit()

    return choice["render_preset"]


def get_project_settings():
    """Get relevant settings for sidecar gen"""

    forbidden_prefixes = [
        "_",
        "timeline",
        "audioCapture",
        "colorVersion",
        "perf",
        "videoCapture",
        "videoDeck",
        "videoMonitor",
        "videoPlayout",

    ]

    resolve.active_timeline.custom_settings(True)

    relevant_project_settings = helpers.blacklist_filter_dict(
        resolve.project.get_setting(),
        forbidden_prefixes
    )

    relevant_timeline_settings = helpers.blacklist_filter_dict(
        resolve.active_timeline.get_setting(),  # type: ignore
        ["_", "videoMonitor"]
    )

    return {
        "project_settings": relevant_project_settings,
        "timeline_settings": relevant_timeline_settings,
    }


def write_sidecar(output_file: str, sidecar_data: dict):

    sidecar_file_path = os.path.join(
        os.path.dirname(output_file),
        os.path.splitext(output_file)[0] + ".patch"
    )

    # Check if sidecar file exists
    if os.path.exists(sidecar_file_path):
        if not Confirm.ask(
            "Looks like a sidecar file already exists with that name.\n"
            "It's linked render file is missing, so it's likely an orphan.\n"
            "Overwrite?"
        ):
            print("User cancelled")
            exit()

        os.remove(sidecar_file_path)

    with open(sidecar_file_path, "x") as sidecar_file:
        json.dump(
            sidecar_data,
            sidecar_file,
            indent=1,
        )


def prompt_render():

    job_id = resolve.project.add_renderjob()

    questions = [
        inquirer.List(
            'render_start_style',
            message="Ready to render?\n"
                    "Select manual if you want to "
                    "set network render machines\n"
                    "and start the render yourself",
            choices=["Start", "Manual"],
        )
    ]
    answer = inquirer.prompt(questions)
    if not answer:
        exit()

    render_start_style = answer["render_start_style"]
    if render_start_style == "Start":
        resolve.project.render([job_id])

    return job_id


def track_render(job_id: str):

    # Pending render start
    with Progress(transient=True) as progress:
        ready_task_id = progress.add_task("[red]Waiting...", total=None)

        while True:

            if resolve.project.render_status(job_id)["JobStatus"] != "Ready":
                break

            progress.update(ready_task_id)

    # Tracking render progress
    with Progress(transient=True) as progress:
        render_task_id = progress.add_task("[red]Rendering...", total=100)

        while True:

            # Annoyingly assignment seems to cache render_status...
            if resolve.project.render_status(job_id)["JobStatus"] in [
                    "Complete",
                    "Cancelled",
                    "Failed",
            ]:
                break
            # else:
            #     print(resolve.project.render_status(job_id)["JobStatus"])

            percent_complete = float(resolve.project.render_status(job_id)["CompletionPercentage"])

            time.sleep(0.5)  # Be kind to the Resolve API
            progress.update(
                render_task_id,
                completed=percent_complete,
            )
    return


def render_master_file():

    # Check if rendering
    if resolve.project.is_rendering():
        if Confirm.ask(
            "Looks like Resolve is busy rendering!\n"
            "You'll have to wait to queue a Patchwork job.\n"
            "Check again?"
        ):
            render_master_file()
        exit()

    # Confirm render range
    if not Confirm.ask(
        "Are you happy with the set render range? "
        "Have you set necessary in and outs?",
    ):
        print("Cool! Set them and try again when you're done.")
        exit()

    # Get chosen render preset
    chosen_render_preset = prompt_render_preset()
    resolve.project.set_preset(chosen_render_preset)

    # Get delivery format
    format_and_codec = resolve.project.current_render_format_and_codec
    file_extension = format_and_codec['format']

    # Get correct output name
    output_dir = os.path.normpath(settings["app"]["render_directory"])
    output_name = f"{resolve.project.name} - {resolve.active_timeline.name}"
    output_file = helpers.next_path(
        os.path.join(output_dir, f"{output_name}_%s.{file_extension}")
    )

    # Set correct filename and path
    render_settings = {
        "TargetDir": settings["app"]["render_directory"],
        "CustomName": output_file,
    }
    resolve.project.set_render_settings(render_settings)

    # Write sidecar data
    sidecar_data = {}
    sidecar_data.update(**get_project_settings())
    sidecar_data.update(**render_settings)
    write_sidecar(output_file, sidecar_data)

    # Render
    job_id = prompt_render()
    track_render(job_id)


def get_markers():

    markers = resolve.active_timeline.markers
    patchwork_markers = [x for x in markers if x.color == "Cream"]
    if not patchwork_markers:
        retry = messagebox.askretrycancel(
            "No markers on timeline!",
            "There are no markers on the timeline.\n"
            "Can't splice without marked ranges!"
        )
        if retry:
            get_markers()
        return []
    return patchwork_markers


def get_master_file():

    supported_files = (
        ("MP4", "MPEG-4"),
        ("AVI", "Advanced Video Interchange"),
        ("MOV", "Quicktime Movie File"),
        ("MXF", "Material Exchange Format"),
    )

    master_file = filedialog.askopenfilename(
        initialdir=settings["app"]["starting_dir"],
        filetypes=supported_files,
        title="Link to master video file",
    )
    return master_file


def get_resolve_settings():

    # TODO: More robust verification!
    # Specifically file type, codec, etc
    return {
        "timeline_settings": resolve.active_timeline.settings,
        "project_settings": resolve.project.settings,
    }


def write_sidecar_file(sidecar_file_path: str):

    assert not os.path.exists(sidecar_file_path)
    with open("x", sidecar_file_path) as sidecar_file:
        sidecar_file.write(get_resolve_settings())

    return


def verify_sidecar_file(master_file: str):

    sidecar_file_path = os.path.splitext(master_file)[0] + ".patch"

    if not os.path.exists(sidecar_file_path):
        continue_ = messagebox.askyesno(
            "Missing sidecar!",
            "Sidecar file does not exist! "
            "Master integrity questionable. "
            "Continue anyway?"
        )
        if continue_:
            return True
        return False

    sidecar_file_data = json.loads(sidecar_file_path)
    if sidecar_file_data != json.dumps(get_resolve_settings()):
        dismissed = messagebox.askquestion(
            "Mismatched sidecar data",
            "Sidecar data does not match the current timeline! "
            "If you ABSOLUTELY want to continue, delete the sidecar file, "
            "and follow prompts."
        )
        if dismissed:
            return False


def render_patches(markers: list[Marker]) -> list[str]:

    if resolve.project.is_rendering():
        messagebox.askretrycancel(
            "Rendering already in progress!", 
            "Resolve is currently rendering"
            "Finish current renders first!"
        )

    job_ids = []

    for marker in markers:
        resolve.project.set_render_settings(
            {
                "MarkIn": marker.frameid,
                "MarkOut": marker.frameid + marker.duration
            }
        )

        print(marker.name)
        resolve.project.current_render_format_and_codec
        job_id = resolve.project.add_renderjob()
        job_ids.append(job_id)
        resolve.project.render(job_ids)

    return job_ids


def slice_master(master_file: str, markers: list[Marker]):
    """
    Need to slice the master file at each new segment intersection.
    We leave the sections to be overwritten out of concatenation
    and subsistute with the new renders
    """
    master_filepath_minus_ext, master_ext = os.path.splitext(master_file)
    timeline_framerate = resolve.active_timeline.settings.frame_rate
    master_segments = []

    for i, marker in enumerate(markers):

        master_segments.append(f"{master_filepath_minus_ext}_{i}{master_ext}")

        (ffmpeg
            .input(master_file)
            .trim(start_frame=marker.frameid, end_frame=marker.frameid + marker.duration)
            .output("-avoid_negative_ts", f"{master_filepath_minus_ext}_{i}{master_ext}")
        )


def patch():

    print(f"Current timeline: '{resolve.active_timeline.name}'")

    markers = get_markers()
    print(markers)
    if not markers:
        exit()

    master_file = get_master_file()
    print(master_file)
    if not verify_sidecar_file(master_file):
        print("Verified")
        exit()
        
    unchanged_segments = slice_master(master_file, markers)

    render_patches(markers)