
import copy
from datetime import datetime, timedelta
import logging
from pathlib import Path
from pydavinci import davinci
from pydavinci.wrappers.marker import Marker
from timecode import Timecode
from rich.logging import RichHandler
import webbrowser
import json
import os
from deepdiff import DeepDiff

import dearpygui.dearpygui as dpg

# Logging
logging.basicConfig(
    level="NOTSET",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

# GLOBAL VARS

app_file_path = Path(__file__)
src_folder = app_file_path.parent.absolute()
root_folder = src_folder.parent.absolute()

# Flags
start_timecode_check_dismissed = False

# Counters
in_3_sec = datetime.now() + timedelta(seconds=3)
in_half_sec = datetime.now() + timedelta(seconds=0.5)


# DearPyGUI Init
dpg.create_context()
dpg.set_global_font_scale(1.5)

def save_init():
    dpg.save_init_file("dpg.ini")

width, height, channels, data = dpg.load_image(os.path.join(src_folder, "logo.png"))
with dpg.texture_registry(show=False):
    dpg.add_static_texture(width=width, height=height, default_value=data, tag="texture_tag")
    
import routines
from widgets import dialog_box

# RESOLVE INIT
resolve = davinci.Resolve()
resolve.active_timeline.custom_settings(True)

# RENDER PRESET
def choose_render_preset_callback():
    
    dpg.configure_item("preset_picker", show=False)
    chosen_render_preset = dpg.get_value("preset_radio")
    print(f"Chosen render preset {chosen_render_preset}")
     
def choose_render_preset():

    with dpg.window(label="Render Presets", tag="preset_picker", modal=True):
        dpg.add_radio_button(resolve.project.render_presets, tag="preset_radio")
        dpg.add_button(label="Confirm", callback=choose_render_preset_callback)
            
def load_render_preset() -> bool:
    
    if not dpg.get_value("preset_radio"):
        dialog_box.prompt("No render preset chosen. Please choose one before loading")
        return False
        
    if not resolve.project.load_render_preset(dpg.get_value("preset_radio")):
        dialog_box.prompt("Couldn't load render preset! Please ensure it exists.")
        return False
    
    return True

class PatchFile():
    
    def __init__(self):
        
        self.resolve = davinci.Resolve()
        self.patchfile = None
        
        project_settings = self.resolve.project.get_setting()
        timeline_settings = self.resolve.active_timeline.get_setting()
        
        self.current_settings = {
            "project_settings":project_settings, 
            "timeline_settings":timeline_settings
        }
        
    def load(self, patchfile_path):
        with open(patchfile_path) as patchfile:
            self.patchfile = json.loads(patchfile.read())
        
        settings_diff = DeepDiff(self.current_settings, self.patchfile)
        if settings_diff:
            
            print(settings_diff)
            dialog_box.prompt(f"Looks like settings have changed!\n{settings_diff}")
            
    def new(self, patchfile_path):
            
        project = self.resolve.project
        timeline = self.resolve.active_timeline
        project_settings = project.get_setting()
        timeline_settings = timeline.get_setting()
        render_settings = project.current_render_format_and_codec        
        
        data = {
            "project_settings":project_settings,
            "timeline_settings":timeline_settings,
            "render_settings":render_settings,
        }
        
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
           
    def callback(self, sender:str, app_data:dict):
        print('OK was clicked.')
        print("Sender: ", sender)
        print("App Data: ", app_data)
        
        if not app_data["selections"]:
            dialog_box.prompt("No selection was made!")
            return
        
        chosen_filepath = app_data['file_path_name']
        chosen_file = os.path.basename(chosen_filepath)
        chosen_filename = os.path.splitext(chosen_file)[0]
        
        dpg.configure_item("master_status", color=[100, 255, 100])
        dpg.set_value("master_status", f"Tracking")
        dpg.set_value("master_status_tooltip", f"Tracking master file:\n{chosen_filepath}")
        dpg.set_value("track_file_input", chosen_filepath)
        
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
            callback=self.callback, 
            cancel_callback=self.cancel_callback, 
            modal=True,
            width=600,
            height=400,
            tag="render_file_dialog",
        ):
        
            dpg.add_file_extension(".patch", color=(255, 255, 0, 255))
            dpg.add_file_extension(".*")
           
    def callback(self, sender:str, app_data:dict):
        print('OK was clicked.')
        print("Sender: ", sender)
        print("App Data: ", app_data)
        
        chosen_dirpath = app_data['file_path_name']
        determined_filename = f"{resolve.project.name} - {resolve.active_timeline.name}"
        full_output_path = f"{chosen_dirpath}{os.sep}{determined_filename}"
        chosen_render_preset = choose_render_preset()
        print(f"Chosen render preset: {chosen_render_preset}")

        
        patchfile = PatchFile()
        patchfile.new(full_output_path)

        dpg.configure_item("master_status", color=[255, 150, 0])
        dpg.set_value("master_status", f"Rendering \"{determined_filename}\"")
        dpg.set_value("master_status_tooltip", f"Rendering master file to path:\n'{full_output_path}'")
        dpg.set_value("master_status_tooltip", f"Rendering master file to path:\n'{full_output_path}'")

    def cancel_callback(self, sender, app_data):
        print('Cancel was clicked.')
        print("Sender: ", sender)
        print("App Data: ", app_data)

track_patch_file = TrackPatchfile()
render_patch_file = RenderPatchFile()


# Helpers
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

    timeline = resolve.active_timeline
    framerate = resolve.active_timeline.settings.frame_rate
    min_duration = int(framerate) * 2
    tc = Timecode(framerate=framerate, start_timecode=timeline.timecode)
    print(f"Timecode: {timeline.timecode} Frames: {tc.frames} Framerate: {framerate}")
    assert tc.frames is not None
    
    if not resolve.active_timeline.markers.add(
        tc.frames - 1,
        "Purple", 
        duration=min_duration, 
        name=f"Change - {get_next_free_marker_num()}", 
        customdata="patchwork_marker"
    ):
        return False
    return True

def clear_markers():
    """
    Delete all patchwork markers
    """
    timeline = resolve.active_timeline
    markers = timeline.markers.find_all("patchwork_marker")
    
    if not markers:
        return False
    
    [x.delete() for x in markers]
    return True

# Commands
def add_change():
      
    if not create_marker():
        dialog_box.prompt("Looks like there's already a marker there!")
        return

def clear_changes():
    
    if not clear_markers():
        dialog_box.prompt("Oops, no changes to clear.")
        return

def commit_changes():
    
    project = resolve.project
    timeline = resolve.active_timeline
    framerate = timeline.settings.frame_rate
    min_duration = int(framerate) * 2
    markers = timeline.markers.find_all("patchwork_marker")
    
    if not markers:
        dialog_box.prompt(
            "No changes have been marked in the timeline.\n"
            "Please mark some changes first",
        )
        return
    invalid_markers = [x for x in markers if x.duration < min_duration]
    if invalid_markers:
        dialog_box.prompt(
            "Markers shouldn't be shorter than 2 seconds.\n"
            f"These markers are invalid:\n{invalid_markers}",
        )
        return
    
    job_ids = []
    for x in markers:
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
        

def push_changes():
    ...
        
def open_documentation():
    webbrowser.open_new_tab("https://github.com/in03/patchwork")

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
    
    dpg.add_image("texture_tag") 
        
    dpg.add_separator()
    dpg.add_spacer(height=20) 
    
                    
    dpg.add_text("Currently untracked", tag="master_status", color=[255, 100, 100], wrap=500)
    with dpg.tooltip("master_status"):
        dpg.add_text(f"On the source page, select a patchwork file to track\nor render a new master file", tag="master_status_tooltip")
        
    dpg.add_separator()
    dpg.add_spacer(height=20) 
        
    # MASTER FILE
    with dpg.group(label="master_group", horizontal=True):
        
        with dpg.tab_bar(tag="tab_bar"):
            
            # CHANGES PAGE
            with dpg.tab(label="Changes"):
                dpg.add_spacer(height=20) 
            
                dpg.add_text("Mark changes on the active timeline to patch the master file with", wrap=500)
                dpg.add_spacer(height=20) 
                

                with dpg.group(tag="add_group", horizontal=True):
                    
                    # ADD BUTTON
                    dpg.add_button(label="Add", tag="Add", callback=add_change)
                    
                    # CLEAR BUTTON
                    dpg.add_button(label="Clear Changes", tag="clear_changes", callback=clear_changes)
                    with dpg.tooltip("clear_changes"):
                        dpg.add_text("Clear all of Patchwork's ranged-markers\nfrom the active timeline")
                        
                dpg.add_text("N/A", tag="current_timecode_display", color=[255, 150, 0])
                        
                dpg.add_separator()
                dpg.add_spacer(height=20)
                            
                # COMMIT BUTTON
                dpg.add_text("Commit changes and create render jobs", wrap=500)
                with dpg.group(tag="commit_group"):
                    dpg.add_text("No changes to commit", tag="commit_status", color=[255, 100, 100], wrap=500)
                    dpg.add_button(label="Commit", tag="Commit", callback=commit_changes)
                    
                dpg.add_separator()
                dpg.add_spacer(height=20) 
                    
                # PUSH BUTTON
                dpg.add_button(label="Push", tag="Push", callback=push_changes)
                with dpg.tooltip("Push"):
                    dpg.add_text("Render and merge changes")
                        
                dpg.add_separator()
                dpg.add_spacer(height=20) 
            
                    
                dpg.add_spacer(height=20) 
                
            # SOURCE PAGE
            with dpg.tab(label="Source"):
                
                dpg.add_spacer(height=20)
                dpg.add_text("Track existing sidecar file")
                    
                with dpg.group(tag="file_selector", horizontal=True):
                    dpg.add_button(label="Browse", tag="link_browse_button", callback=lambda: dpg.show_item("track_file_dialog"))
                    dpg.add_input_text(default_value="", tag="track_file_input")
                dpg.add_button(label="Link", tag="link_patchfile", callback=lambda: dpg.show_item("track_file_dialog"), show=False)
                
                dpg.add_spacer(height=20)
                dpg.add_text("Render new master and regenerate sidecar file")
                with dpg.group(tag="render_buttons", horizontal=True):
                    dpg.add_button(label="Browse", tag="render_browse_button", callback=lambda: dpg.show_item("render_file_dialog"))
                    dpg.add_button(label="Choose render preset", tag="choose_render_preset_button", callback=lambda: choose_render_preset())
                    dpg.add_button(label="Render", tag="render_start_button", callback=lambda: dialog_box.prompt("TODO: Render!"))
                dpg.add_spacer(height=20) 
                
    dpg.add_separator()
    dpg.add_spacer(height=20) 
  
dpg.create_viewport(title='Patchwork 0.1.0', width=800, height=540)
dpg.configure_app(init_file=os.path.join(root_folder, "dpg.ini"))
dpg.set_viewport_always_top(True)
dpg.setup_dearpygui()
dpg.show_viewport()

while dpg.is_dearpygui_running():
        
    # REACTIVE VARIABLES
    markers = copy.copy(resolve.active_timeline.markers)
    frame_rate = copy.copy(resolve.active_timeline.settings.frame_rate)
    current_timecode = copy.copy(resolve.active_timeline.timecode)
    
    # SIMPLE
    resolve.active_timeline.custom_settings(True)

    
    # TODO: Check Resolve is open, lock up whole interface with warning otherwise
    # No option to dismiss dialog box. Automatically dismiss box when Resolve is opened
    
    # TODO: Check timeline is open, lock up whole interface with warning otherwise
    # No option to dismiss dialog box. Automatically dismiss box when timeline is opened
    
    # TODO: Check timeline is same as tracked timeline, disable changes page
    # On each timeline change, ensure custom settings are enabled. Make it so.
        
    routines.check_timecode_starts_at_zero(current_timecode, frame_rate)
    routines.refresh_add_status(markers, current_timecode, frame_rate)
    routines.refresh_commit_status(markers)
        
    dpg.render_dearpygui_frame()

# TODO: Fix save init file
dpg.save_init_file(os.path.join(root_folder, "dpg.ini"))
dpg.destroy_context()