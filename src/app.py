import logging
from pydavinci import davinci
from pydavinci.wrappers.marker import Marker
from timecode import Timecode
from rich.logging import RichHandler
import webbrowser
import json
import os
from deepdiff import DeepDiff

import dearpygui.dearpygui as dpg

logging.basicConfig(
    level="NOTSET",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

resolve = davinci.Resolve()
dpg.create_context()
dpg.set_global_font_scale(1.5)


class DialogBox():
    def __init__(self):
        
        with dpg.window(label="Dialog", modal=True, show=False, tag="dialog_box", no_title_bar=True, autosize=True, pos=[150, 225]):
            dpg.add_text("Dialog text goes here", tag="dialog_text", wrap=500)
            dpg.add_separator()
            with dpg.group(horizontal=True, tag="dialog_buttons"):
                dpg.add_button(label="Ok", callback=lambda: dpg.configure_item("dialog_box", show=False))
                
                
    def prompt(self, message:str):
        dpg.configure_item("dialog_box", show=True, label="dialog")
        dpg.set_value("dialog_text", message)

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


dialog_box = DialogBox()
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

def frames_to_playhead() -> int:   
    timeline = resolve.active_timeline
    frame_rate = resolve.active_timeline.settings.frame_rate
    tc = Timecode(framerate=frame_rate, start_timecode=timeline.timecode)
    print(f"Timecode: {timeline.timecode} Frames: {tc.frames} Framerate: {frame_rate}")
    assert tc.frames is not None
    return tc.frames

def toggle_always_on_top():
    
    dpg.add_bool_value(label="on_top", default_value=False)
    if dpg.get_value("on_top"):
        dpg.set_viewport_always_top(True)
    else:
        dpg.set_viewport_always_top(False)



# Commands
def create_marker():
    
    if not resolve.active_timeline.markers.add(
        frames_to_playhead(), 
        "Purple", 
        duration=2, 
        name=f"Change - {get_next_free_marker_num()}", 
        customdata="patchwork_marker"
    ):
    
        dialog_box.prompt(
            f"Couldn't create a marker at {resolve.active_timeline.timecode}"
            " Please make sure there isn't already a marker there."
        )

def clear_markers():
    """
    Delete all patchwork markers
    """
    timeline = resolve.active_timeline
    markers = timeline.markers.find_all("patchwork_marker")
    
    if markers:
        
        [x.delete() for x in markers]
        
def commit_changes():
    project = resolve.project
    timeline = resolve.active_timeline
    markers = timeline.markers.find_all("patchwork_marker")
    
    if not markers:
        dialog_box.prompt(
            "No changes have been marked in the timeline.\n"
            "Please mark some changes first",
        )
        return
    
    invalid_markers = [x for x in markers if x.duration < 1]
    if invalid_markers:
        dialog_box.prompt(
            "Markers cannot be shorter than 1 second.\n"
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
            dpg.add_menu_item(label="Always on top", check=True, callback=toggle_always_on_top)
            dpg.add_menu_item(label="Preferences")
            
        with dpg.menu(label="Help"):
            dpg.add_menu_item(label="About")
            dpg.add_menu_item(label="Docs", callback=open_documentation)
            
    dpg.add_separator()
    dpg.add_spacer(height=20) 
        
    # MASTER FILE
    with dpg.group(label="master_group", horizontal=True):
        
        with dpg.tab_bar(tag="tab_bar"):
            
            # CHANGES PAGE
            with dpg.tab(label="Changes"):
                
                dpg.add_spacer(height=20) 
                
                with dpg.group(tag="action_group", horizontal=True):
                            
                    # ADD BUTTON
                    dpg.add_button(label="Add", tag="Add", callback=create_marker)
                    with dpg.tooltip("Add"):
                        dpg.add_text("Mark changes on the active timeline\nto patch the master file with")
                                
                    # COMMIT BUTTON
                    dpg.add_button(label="Commit", tag="Commit", callback=commit_changes)
                    with dpg.tooltip("Commit"):
                        dpg.add_text("Commit changes and \ncreate render jobs")
                        
                    dpg.add_spacer(height=20) 
                        
                    # PUSH BUTTON
                    dpg.add_button(label="Push", tag="Push", callback=push_changes)
                    with dpg.tooltip("Push"):
                        dpg.add_text("Render and merge changes")
                            
                    dpg.add_spacer(height=20) 
                
                # CLEAR BUTTON
                dpg.add_button(label="Clear Changes", tag="clear_changes", callback=clear_markers)
                with dpg.tooltip("clear_changes"):
                    dpg.add_text("Clear all of Patchwork's ranged-markers\nfrom the active timeline")
                    
                dpg.add_spacer(height=20) 
                
            # SOURCE PAGE
            with dpg.tab(label="Source"):
                
                dpg.add_spacer(height=20)
                dpg.add_text("Track existing")
                dpg.add_text("Currently untracked", tag="master_status", color=[255, 100, 100], wrap=400)
                with dpg.tooltip("master_status"):
                    dpg.add_text(f"On the source page, select a patchwork file to track\nor render a new master file", tag="master_status_tooltip")
                with dpg.group(tag="file_selector", horizontal=True):
                    dpg.add_button(label="Browse", tag="link_browse_button", callback=lambda: dpg.show_item("track_file_dialog"))
                    dpg.add_input_text(default_value="", tag="track_file_input")
                dpg.add_button(label="Link", tag="link_patchfile", callback=lambda: dpg.show_item("track_file_dialog"), show=False)
                
                dpg.add_spacer(height=20)
                dpg.add_text("Render a new master file")
                dpg.add_button(label="Browse", tag="render_browse_button", callback=lambda: dpg.show_item("render_file_dialog"))
                dpg.add_spacer(height=20) 
                
    dpg.add_separator()
    dpg.add_spacer(height=20) 
  
dpg.create_viewport(title='Patchwork 0.1.0', width=800, height=540)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()