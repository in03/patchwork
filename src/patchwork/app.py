
import copy
import logging
from pathlib import Path
from pydavinci import davinci
from pydavinci.wrappers.marker import Marker, MarkerCollection
from pydavinci.wrappers.timeline import Timeline
from timecode import Timecode
from rich.logging import RichHandler
import webbrowser
import json
import os
from deepdiff import DeepDiff
import trio
import dearpygui.dearpygui as dpg

# Logging
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
logger = logging.getLogger(__name__)

# GLOBAL VARS
app_file_path = Path(__file__)
src_folder = app_file_path.parent.absolute()
root_folder = src_folder.parent.absolute()

#############################################################################
# ALL DPG CALLS MUST BE MADE AFTER 'dpg.create_context()!
dpg.create_context()
#############################################################################

# LOGLEVEL VALUE
with dpg.value_registry():
    dpg.add_string_value(tag="loglevel", default_value="INFO")
# logger.setLevel(dpg.get_value("loglevel"))

dpg.set_global_font_scale(1.5)
dpg.create_viewport(title='Patchwork 0.1.0', width=800, height=540)
dpg.configure_app(init_file=os.path.join(root_folder, "dpg.ini"))
dpg.set_viewport_always_top(True)
dpg.setup_dearpygui()
dpg.show_viewport()

def save_init():
    dpg.save_init_file("dpg.ini")
    
# RENDER PRESET
def choose_render_preset_callback():
    
    dpg.configure_item("preset_picker", show=False)
    chosen_render_preset = dpg.get_value("preset_combo")
    print(f"Chosen render preset {chosen_render_preset}")
    dpg.delete_item("preset_picker")
     
def choose_render_preset():

    with dpg.window(label="Render Presets", tag="preset_picker", modal=True, autosize=True):
        dpg.add_combo(resolve.project.render_presets, tag="preset_combo", default_value="-- Choose Render Preset --")
        dpg.add_button(label="Confirm", callback=choose_render_preset_callback)
            
def load_render_preset() -> bool:
    
    if not dpg.get_value("preset_combo"):
        dialog_box.prompt("No render preset chosen. Please choose one before loading")
        return False
        
    if not resolve.project.load_render_preset(dpg.get_value("preset_radio")):
        dialog_box.prompt("Couldn't load render preset! Please ensure it exists.")
        return False
    
    return True

class PatchFile():
    
    def __init__(self, patchfile:str):
        
        self.resolve = davinci.Resolve()
        self.patchfile = patchfile
        self.patchfile_data = {}
        self.current_settings = self.get_current_settings()
        
    def get_current_settings(self) -> dict:
        
        project = self.resolve.project
        timeline = self.resolve.active_timeline
        project_settings = project.get_setting()
        timeline_settings = timeline.get_setting()
        render_settings = project.current_render_format_and_codec  
        
        data = {
            "project_name": project.name,
            "timeline_name": timeline.name,
            "settings": {
                "project_settings":project_settings,
                "timeline_settings":timeline_settings,
                "render_settings":render_settings,
            }
        }
        return data
    
    def get_changes_data(self) -> dict:
        
        timeline = self.resolve.active_timeline
        changes = [x for x in timeline.markers if x.customdata == "patchwork_marker"]
        
        data = {
            "changes": changes,
        }
        return data
    
    def compare(self):

        if self.current_settings["project_name"] != self.patchfile_data["project_name"]:
            dialog_box.prompt(
                f"Looks like the tracked file is for a different project: '{self.patchfile_data['project_name']}'\n"
                "Please load the correct patchfile for this project, or create a new one."
            )
            return
        
        if self.current_settings["timeline_name"] != self.patchfile_data["timeline_name"]:
            dialog_box.prompt(
                f"Looks like the tracked file is for a different timeline: '{self.patchfile_data['timeline_name']}'\n"
                "Please load the correct patchfile for this timeline, or create a new one."
            )
            return
        
        settings_diff = DeepDiff(self.current_settings["settings"], self.patchfile_data["settings"])
        if settings_diff:
            
            print(settings_diff)
            dialog_box.prompt(
                "Looks like project settings have been altered since the master file was rendered!\n"
                "You will need to render a master file again, since consistent results cannot be guaranteed with different settings\n"
                f"{settings_diff}"
            )
            return
    
    def load(self):
        
        with open(self.patchfile) as patchfile:
            self.patchfile_data = json.loads(patchfile.read())
            return self.patchfile_data
     
    def update(self, writable):
        
        if not self.patchfile:
            logger.error("[red]No patchfile chosen")
            return None
        
        existing_data = self.load()
        with open(self.patchfile, "w") as json_file:
            if existing_data:
                writable.update(existing_data)
            return json.dump(writable, json_file)
            
    def new(self, patchfile_path):
            
        data = self.get_current_settings()
        
        try:
            with open(patchfile_path + ".patch", "w") as patchfile:
                patchfile.write(json.dumps(data, sort_keys=True))
        except PermissionError:
            dialog_box.prompt("You don't have write permissions to this folder. Try another one.")
       
# File Dialog
class TrackPatchfile():
    def __init__(self):
        
        with dpg.file_dialog(
            directory_selector=False, 
            default_path="Z:\\@Finished Renders", 
            show=False, 
            callback=self.callback, 
            cancel_callback=self.cancel_callback, 
            modal=True,
            width=600,
            height=400,
            tag="track_file_dialog",
        ):
        
            dpg.add_file_extension(".patch", color=(255, 255, 0, 255))
            dpg.add_file_extension(".*")
        
        self.chosen_file = ""
        self.chosen_filename = ""
        self.chosen_filepath = ""
           
    def callback(self, sender:str, app_data:dict):
        print('OK was clicked.')
        print("Sender: ", sender)
        print("App Data: ", app_data)
        
        if not app_data["selections"]:
            dialog_box.prompt("No selection was made!")
            return
        
        self.chosen_filepath = app_data['file_path_name']
        self.chosen_file = os.path.basename(self.chosen_filepath)
        self.chosen_filename = os.path.splitext(self.chosen_file)[0]
        
        dpg.configure_item("source_status", color=[100, 255, 100])
        dpg.set_value("source_status", f"Linked")
        dpg.set_value("track_file_input", self.chosen_filepath)
        
    def cancel_callback(self, sender, app_data):
        print('Cancel was clicked.')
        print("Sender: ", sender)
        print("App Data: ", app_data)       


# File Dialog
class RenderPatchFile():
    def __init__(self):
        
        with dpg.file_dialog(
            directory_selector=True, 
            default_path="Z:\\@Finished Renders", 
            show=False, 
            callback=self.picked_dir_callback, 
            cancel_callback=self.picked_dir_cancel_callback, 
            modal=True,
            width=600,
            height=400,
            tag="render_file_dialog",
        ):
        
            dpg.add_file_extension(".patch", color=(255, 255, 0, 255))
            dpg.add_file_extension(".*")
           
    def picked_dir_callback(self, sender:str, app_data:dict):
        print('OK was clicked.')
        print("Sender: ", sender)
        print("App Data: ", app_data)
        
        chosen_dirpath = app_data['file_path_name']
        determined_filename = f"{resolve.project.name} - {resolve.active_timeline.name}"
        full_output_path = f"{chosen_dirpath}{os.sep}{determined_filename}"
        chosen_render_preset = choose_render_preset()
        print(f"Chosen render preset: {chosen_render_preset}")
        
        dpg.configure_item("choose_render_preset_button", enabled=True)
        
        # patchfile = PatchFile()
        # patchfile.new(full_output_path)

        dpg.configure_item("source_status", color=[255, 150, 0])
        dpg.set_value("source_status", f"Rendering \"{determined_filename}\"")

    def picked_dir_cancel_callback(self, sender, app_data):
        print('Cancel was clicked.')
        print("Sender: ", sender)
        print("App Data: ", app_data)

track_patch_file = TrackPatchfile()
render_patch_file = RenderPatchFile()

# Helpers
def should_refresh_now():
    global force_refresh
    if force_refresh:
        force_refresh = False
        return True

def get_next_free_marker_num():
    """Get the next marker number in the series"""
    
    def get_marker_num(marker: Marker) -> int:
        """
        Parses ordinal number from marker name
        
        Returns zero if none
        """
        try:
            return int(marker.name[-1])
        except TypeError:
            return 0
    
    timeline = resolve.active_timeline
    markers = timeline.markers.find_all("patchwork_marker")
    
    if not markers:
        return 1
    
    last_num = int(sorted([get_marker_num(x) for x in markers])[-1])
    next_num = last_num + 1
    return str(next_num)

def toggle_always_on_top():
    
    if dpg.get_value("menu_always_on_top"):
        dpg.set_viewport_always_top(True)
    else:
        dpg.set_viewport_always_top(False)

def create_marker():
    
    global markers
    global force_refresh
    
    timeline = resolve.active_timeline
    framerate = resolve.active_timeline.settings.frame_rate
    patchwork_markers:list[Marker]|None = timeline.markers.find_all("patchwork_marker")
    
    min_duration = int(framerate) * 2
    tc = Timecode(framerate=framerate, start_timecode=timeline.timecode)
    print(f"Timecode: {timeline.timecode} Frames: {tc.frames} Framerate: {framerate}")

    assert tc.frames is not None
    new_marker_frame_id = tc.frames -1
    

    new_marker_start = tc.frames -1
    new_marker_end = new_marker_start + min_duration
    
    # Check if any patchwork markers overlap
    if patchwork_markers:
        for x in patchwork_markers:
            
            existing_marker_start = x.frameid
            existing_marker_end = x.frameid + x.duration
            
            logger.debug(f"[magenta]Attempt marker @ {new_marker_start} -> {new_marker_end}")
            
            # Check overlap between new marker and existing marker ranges
            nm_range = range(new_marker_start, new_marker_end)
            em_range = range(existing_marker_start, existing_marker_end)
            overlap = bool(range(max(nm_range[0], em_range[0]), min(nm_range[-1], em_range[-1])+1))
            
            if overlap:
                dialog_box.prompt(
                    "Whoops, sorry. Changes can't overlap!\n"
                    f"A change added here would overlap with '{x.name}'"
                )
                return
    
    if not resolve.active_timeline.markers.add(
        new_marker_start,

        "Purple", 
        duration=min_duration, 
        name=f"Change - {get_next_free_marker_num()}", 
        customdata="patchwork_marker"
    ):
        dialog_box.prompt("Sorry, Resolve says no. Maybe there's already a marker there?")
        return

def clear_markers():
    """
    Delete all patchwork markers
    """
    
    global markers
    global force_refresh
    
    if not markers:
        return False
    
    [x.delete() for x in markers if x.customdata == "patchwork_marker"]
    force_refresh = True
    markers = copy.copy(resolve.active_timeline.markers)
    return True

# Commands
def add_change():

    global refresh_now
    create_marker()

    refresh_now = True
    
def clear_changes():
    
    global refresh_now
    
    if not clear_markers():
        dialog_box.prompt("Oops, no changes to clear.")
        return
    
    refresh_now = True

def render_changes():
    
    project = resolve.project
    timeline = resolve.active_timeline
    
    job_ids = []
    for x in committed_markers:
        if not load_render_preset():
            return
        project.set_render_settings(
            {
                "MarkIn": x.frameid,
                "MarkOut": x.frameid + x.duration * timeline.settings.frame_rate,
                "CustomName": f"{project.name} {timeline.name} {x.name}"
            }
        )
        job_id = project.add_renderjob()
        job_ids.append(job_id)
        print(job_ids)
        
def open_documentation():
    webbrowser.open_new_tab("https://github.com/in03/patchwork")

def init():
    
    print("Running")
    # DearPyGUI Init
    # Post context init imports
    # These will silently crash dpg if instantiated earlier
    global routines
    import routines
    global dialog_box
    from widgets import dialog_box

    # # Load logo image
    # width, height, channels, data = dpg.load_image(os.path.join(src_folder, "logo.png"))
    # with dpg.texture_registry(show=False):
    #     dpg.add_static_texture(width=width, height=height, default_value=data, tag="texture_tag")

    # Resolve init
    global resolve
    resolve = davinci.Resolve()
    
    global project
    project = resolve.project
    
    global timeline
    timeline = resolve.active_timeline
    resolve.active_timeline.custom_settings(True)

    global force_refresh
    force_refresh = False
    
    global markers
    markers = resolve.active_timeline.markers   

    global current_frame_rate
    current_frame_rate = copy.copy(resolve.active_timeline.settings.frame_rate)

    global current_timecode
    current_timecode = copy.copy(resolve.active_timeline.timecode)
    
    global refresh_now
    refresh_now = False
    
    # Item enabled flags
    
    global committed_markers
    committed_markers = []
    
    global new_changes_exist
    new_changes_exist = False
    
    global render_preset_chosen
    render_preset_chosen = False    

    # Timers
    global half_a_second
    half_a_second = routines.Timer(0.5)

def setup_gui():
    
    with dpg.theme(tag="main_theme"):
        with dpg.theme_component(dpg.mvButton, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (122, 122, 122))
            # dpg.mvThemeCol_ButtonHovered
        
        dpg.bind_theme("main_theme")

    
    with dpg.window(tag="primary_window", autosize=True):
        dpg.set_primary_window("primary_window", True)

        # MENU BAR
        with dpg.menu_bar():

            with dpg.menu(label="Settings"):
                dpg.add_menu_item(label="Always on top", check=True, tag="menu_always_on_top", default_value=True, callback=toggle_always_on_top)
                dpg.add_menu_item(label="Preferences")
                
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About")
                dpg.add_menu_item(label="Docs", callback=open_documentation)
        
        # dpg.add_image("texture_tag") 
        # dpg.add_separator()
        
        dpg.add_spacer(height=20)
        dpg.add_text("Link or create a new patchwork file", tag="master_status", color=[250, 150, 50], wrap=500)
            
        dpg.add_separator()
        dpg.add_spacer(height=20) 
            
        # MASTER FILE
        with dpg.group(label="master_group", horizontal=True):
            
            with dpg.tab_bar(tag="tab_bar"):
                
                # CHANGES PAGE
                with dpg.tab(label="Changes"):
                    
                    dpg.add_spacer(height=20) 
                    dpg.add_text("N/A", tag="current_timecode_display", color=[255, 150, 0])
                    dpg.add_spacer(height=20) 
                    
                    dpg.add_separator()
                    with dpg.group(horizontal=True):
                        
                        dpg.add_button(label="Add", tag="add_button", callback=add_change)
                        dpg.add_button(label="Clear All", tag="clear_changes_button", callback=clear_changes)
                        dpg.add_button(label="Render", tag="render_button", callback=render_changes)
                        
                    dpg.add_separator()
                
                # SOURCE PAGE
                with dpg.tab(label="Source"):
                    
                    dpg.add_spacer(height=20) 
                    dpg.add_text("Not currently tracking", tag="source_status", color=[255, 150, 0])
                    dpg.add_spacer(height=20) 

                    dpg.add_separator()
                    with dpg.group(tag="source_buttons", horizontal=True):
                        dpg.add_button(label="Link", tag="link_browse_button", callback=lambda: dpg.show_item("track_file_dialog"))
                        dpg.add_button(label="New", tag="render_browse_button", callback=lambda: dpg.show_item("render_file_dialog"))
                    dpg.add_separator()
                        
                    
async def resolve_is_ready():
    routines.get_environment_state()
    
    if dpg.get_value("resolve_is_open") == False:
        dialog_box.prompt("Resolve is not running! Waiting...", no_close=True)
        await trio.sleep(0)
        return False

    if dpg.get_value("project_is_open") == False:
        dialog_box.prompt("No project is open! Waiting...", no_close=True)
        await trio.sleep(0)
        return False
            
    if dpg.get_value("timeline_is_open") == False:
        dialog_box.prompt("No timeline is open! Waiting...", no_close=True)
        await trio.sleep(0)
        return False
        
    await trio.sleep(0)
    return True

async def render():
    
    global refresh_now
        
    dpg.render_dearpygui_frame()
    logger.debug(f"[magenta]{dpg.get_frame_count()}")
    
    if half_a_second.has_passed or refresh_now:
        refresh_now = False
        
        if resolve_is_ready:
            
            # RUN ONLY IF PROJECT OR TIMELINE HAS CHANGED
            if dpg.get_value("environment_has_changed"):
        
                global current_frame_rate
                current_frame_rate = copy.copy(resolve.active_timeline.settings.frame_rate)
                
                # SIMPLE
                logger.debug("[magenta]Ensure custom timeline settings enabled")
                resolve.active_timeline.custom_settings(True)
                
            # Direct API results only!!! Calculations should be performed as a routine with caching
            # Copy to prevent each chained function from calling the API
            global current_markers
            current_markers = copy.copy(resolve.active_timeline.markers)
            patchwork_markers = ([x for x in current_markers if x.customdata == "patchwork_marker"])

            if not patchwork_markers:
                dpg.configure_item("clear_changes_button", enabled=False)
                dpg.configure_item("render_button", enabled=False)
            else:
                dpg.configure_item("clear_changes_button", enabled=True)
                dpg.configure_item("render_button", enabled=True)
                        
            global current_timecode
            current_timecode = copy.copy(resolve.active_timeline.timecode)
            
            # Weird single frame offset
            global current_frame
            current_frame = Timecode(current_frame_rate, current_timecode).frames
            if current_frame:
                current_frame -=1 
            else:
                current_frame = -1
        
            # ROUTINES SHOULD ALL BE ASYNC
            logger.debug("[magenta]Running complex routines")
            await routines.check_timecode_starts_at_zero(current_frame_rate, current_timecode)
            await routines.refresh_add_status(current_markers, current_timecode, current_frame)
            
    await trio.sleep(0)

async def main():
    
    # SETUP
    logger.debug("[magenta]Initialising...")
    init()
    setup_gui()
    logger.debug("[magenta]Ready!")
    
    # LOOP
    logger.debug("[magenta]Starting render cycle!")
    while dpg.is_dearpygui_running():
        async with trio.open_nursery() as nursery: 
            nursery.start_soon(render)
    
    # EXIT
    logger.debug("[magenta]Exiting!")
    dpg.save_init_file(os.path.join(root_folder, "dpg.ini"))
    dpg.destroy_context()

if __name__ == "__main__":
    trio.run(main)