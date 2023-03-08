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

resolve = davinci.Resolve()


def track_render(job_id: str):

    # Pending render start
    with Progress(transient=True) as progress:
        ready_task_id = progress.add_task("[red]Waiting...", total=None)

        while True:
            try:
                rs = resolve.project.render_status(job_id)["JobStatus"]
                if rs != "Ready":
                    break
            except TypeError:
                print("[red]Job cancelled.")
                exit()

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

            percent_complete = float(
                resolve.project.render_status(job_id)["CompletionPercentage"]
            )

            time.sleep(0.5)  # Be kind to the Resolve API
            progress.update(
                render_task_id,
                completed=percent_complete,
            )
    return


class MasterFile():

    def __init__(
        self,
        render_directory: str,
        render_preset: str,
    ):

        self.job_id: str | None = None
        self.project_name = resolve.project.name
        self.timeline_name = resolve.active_timeline.name

        self.render_preset = render_preset
        self.render_directory = render_directory
        self.__set_render_preset()

        self.master_output_path = self.__get_output_file()
        self.sidecar_output_path = os.path.join(
            os.path.dirname(self.master_output_path),
            os.path.splitext(self.master_output_path)[0] + ".patch"
        )

        self.render_settings = self.__set_render_settings()
        self.resolve_settings = self.__get_resolve_settings()
        self.sidecar_data = {
            "render_preset": self.render_preset,
            **self.render_settings,
            **self.resolve_settings,
        }

    def __set_render_preset(self):
        if not resolve.project.load_render_preset(self.render_preset):
            raise ValueError(f"Invalid render preset! '{self.render_preset}'")

    def __get_output_file(self):

        file_ext = resolve.project.current_render_format_and_codec['format']

        # Get correct output name
        output_dir = os.path.normpath(settings.app.render_directory)
        output_name = f"{self.project_name} - {self.timeline_name}"

        return helpers.next_path(
            os.path.join(output_dir, f"{output_name}_%s.{file_ext}")
        )

    def __set_render_settings(self):
        self.render_settings = {
            "TargetDir": settings.app.render_directory,
            "CustomName": os.path.splitext(
                os.path.basename(self.master_output_path)
            )[0],
        }
        resolve.project.set_render_settings(self.render_settings)
        return self.render_settings

    def __get_resolve_settings(self) -> dict:
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

    def write_sidecar(self, overwrite: bool = False):

        if overwrite:
            if os.path.exists(self.sidecar_output_path):
                os.remove(self.sidecar_output_path)

        with open(self.sidecar_output_path, "x") as sidecar_file:
            json.dump(
                self.sidecar_data,
                sidecar_file,
                indent=1,
            )

    def start_render(self, mode: Literal["Local", "Network Render"]):
        """
        Start rendering the master file

        Args:
            mode (Literal["Start", "Manual"]): Allow the user
            to configure network rendering if desirable

        Returns:
            job_id: The Resolve render job id.
            Can be used for tracking status.
        """

        self.job_id = resolve.project.add_renderjob()

        if mode == "Local":
            resolve.project.render([self.job_id], interactive=True)

        elif mode != "Network Render":
            ValueError(f"Invalid mode passed: {mode}")

        return self.job_id


class PatchThat():

    def get_markers(self):

        markers = resolve.active_timeline.markers
        patchwork_markers = [x for x in markers if x.color == "Cream"]
        if not patchwork_markers:
            retry = messagebox.askretrycancel(
                "No markers on timeline!",
                "There are no markers on the timeline.\n"
                "Can't splice without marked ranges!"
            )
            if retry:
                self.get_markers()
            return []
        return patchwork_markers

    def get_master_file(self):

        supported_files = (
            ("MP4", "MPEG-4"),
            ("AVI", "Advanced Video Interchange"),
            ("MOV", "Quicktime Movie File"),
            ("MXF", "Material Exchange Format"),
        )

        master_file = filedialog.askopenfilename(
            initialdir=settings.app.render_directory,
            filetypes=supported_files,
            title="Link to master video file",
        )
        return master_file

    def get_resolve_settings(self):

        # TODO: More robust verification!
        # Specifically file type, codec, etc
        return {
            "timeline_settings": resolve.active_timeline.settings,
            "project_settings": resolve.project.settings,
        }

    def write_sidecar_file(self, sidecar_file_path: str):

        assert not os.path.exists(sidecar_file_path)
        with open("x", sidecar_file_path) as sidecar_file:
            sidecar_file.write(self.get_resolve_settings())

        return

    def verify_sidecar_file(self, master_file: str):

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
        if sidecar_file_data != json.dumps(self.get_resolve_settings()):
            dismissed = messagebox.askquestion(
                "Mismatched sidecar data",
                "Sidecar data does not match the current timeline! "
                "If you ABSOLUTELY want to continue, delete the sidecar file, "
                "and follow prompts."
            )
            if dismissed:
                return False

    def render_patches(self, markers: list[Marker]) -> list[str]:

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

    def slice_master(self, master_file: str, markers: list[Marker]):
        """
        Need to slice the master file at each new segment intersection.
        We leave the sections to be overwritten out of concatenation
        and subsistute with the new renders
        """
        master_filepath_minus_ext, master_ext = os.path.splitext(master_file)
        # timeline_framerate = resolve.active_timeline.settings.frame_rate
        master_segments = []

        for i, marker in enumerate(markers):

            master_segments.append(
                f"{master_filepath_minus_ext}_{i}{master_ext}"
            )

            (ffmpeg
                .input(master_file)
                .trim(
                    start_frame=marker.frameid,
                    end_frame=marker.frameid + marker.duration
                )
                .output(
                    "-avoid_negative_ts",
                    f"{master_filepath_minus_ext}_{i}{master_ext}",
                )
            )

    def patch(self):

        print(f"Current timeline: '{resolve.active_timeline.name}'")

        markers = self.get_markers()
        print(markers)
        if not markers:
            exit()

        master_file = self.get_master_file()
        print(master_file)
        if not self.verify_sidecar_file(master_file):
            print("Verified")
            exit()

        # unchanged_segments = slice_master(master_file, markers)

        self.render_patches(markers)
