
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
from json import JSONDecodeError
import os
from deepdiff import DeepDiff
import trio
import dearpygui.dearpygui as dpg

from patchwork.config import default_configuration as defaults
from patchwork.config import defaults_filepath
from click import launch

# Logging
logging.basicConfig(
    level="NOTSET",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
logger = logging.getLogger("rich")
logger.setLevel("INFO")

# GLOBAL VARS
app_file_path = Path(__file__)
src_folder = app_file_path.parent.absolute()
root_folder = src_folder.parent.absolute()
config_file = os.path.join(root_folder, "config.json")
patchwork_file = None

# DEFAULTS
window_width = 600
window_height = 400

#############################################################################
# ALL DPG CALLS MUST BE MADE AFTER 'dpg.create_context()!
dpg.create_context()
#############################################################################


#############################################################################
############################## CALLBACKS ####################################
#############################################################################

def select_patchfile_callback(sender, _, app_data:dict):
    
    global patchfile_data
    global chosen_filepath
    
    logger.debug('[magenta]OK was clicked.')
    print("Sender: ", sender)
    print("App Data: ", app_data)
    
    if not app_data["selections"]:
        dialog_box.prompt("No selection was made!")
        return
    
    chosen_filepath = app_data['file_path_name']
    
    with open(chosen_filepath, "r") as patchfile:
        patchfile_data = json.load(patchfile)

    dpg.configure_item("render_preset", enabled=False)        
    dpg.configure_item("source_status", color=[100, 255, 100])
    dpg.set_value("source_status", f"Linked: '{os.path.basename(chosen_filepath).split('.patch')[0]}'")
    
def cancel_patchfile_callback(sender, _, app_data):
    print('Cancel was clicked.')
    print("Sender: ", sender)
    print("App Data: ", app_data)       

def select_render_dir_callback(sender:str, _, app_data:dict):
    
    print('OK was clicked.')
    print("Sender: ", sender)
    print("App Data: ", app_data)
    
    chosen_dirpath = app_data['file_path_name']
    determined_filename = f"{resolve.project.name} - {resolve.active_timeline.name}"
    
    global patchwork_file
    patchwork_file = f"{chosen_dirpath}{os.sep}{determined_filename}.patch"           
                                    
    dpg.configure_item("render_preset", enabled=True)
    dpg.configure_item("source_status", color=[255, 150, 0])
    dpg.set_value("source_status", f"Rendering \"{determined_filename}\"")
    
def cancel_render_dir_callback(sender, _, app_data):
    print('Cancel was clicked.')
    print("Sender: ", sender)
    print("App Data: ", app_data)

def app_exit_callback():
    
    global config_file
    logger.info("[magenta]Writing viewport config to file")
    with open(config_file, "w") as json_file:
        json_file.write(json.dumps(get_current_viewport_config()))

#############################################################################

# Helpers

def get_current_viewport_config() -> dict:
    return {
        "viewport": {
            "width": dpg.get_viewport_client_width(),
            "height": dpg.get_viewport_client_height(),
            "position": dpg.get_viewport_pos(),
        }
    }

def set_viewport_config() -> bool:
    
    logger.debug("[magenta]Loading viewport configuration")
    
    global config_file
    if not os.path.exists(config_file):
        logger.warning("[yellow]Config file does not exist")
        return False
        
    with open(config_file, "r") as json_file: 
        
        try:
            json_data = json_file.read()
            config_data = json.loads(json_data)
            
        except FileNotFoundError:
            logger.warning("[yellow]Config file does not exist")
            return False
        
        except JSONDecodeError:
            logger.warning("[red]Config file contains malformed JSON!")
            return False
        
        viewport_config = config_data.get("viewport")
        if not viewport_config:
            logger.warning("[yellow]Config file contained no viewport configuration")
            return False
    
    
    global window_width
    global window_height
    window_width = viewport_config['width'] 
    window_height = viewport_config['height']
    
    dpg.set_viewport_width(viewport_config['width'] )
    dpg.set_viewport_height(viewport_config["height"])
    dpg.set_viewport_pos(viewport_config["position"])
    
    return True

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
                return None
            
    if not resolve.active_timeline.markers.add(
        new_marker_start,

        "Purple", 
        duration=min_duration, 
        name=f"Change - {get_next_free_marker_num()}", 
        customdata="patchwork_marker"
    ):
        dialog_box.prompt("Sorry, Resolve says no. Maybe there's already a marker there?")
        return

def set_marker_note(note:str):
    timeline = resolve.active_timeline
    framerate = resolve.active_timeline.settings.frame_rate
    patchwork_markers = timeline.markers.find_all("patchwork_marker")
    
    print(note)
    
    tc = Timecode(framerate=framerate, start_timecode=timeline.timecode)
    
    assert patchwork_markers
    for marker in patchwork_markers:
        if tc.frames in range(marker.frameid, marker.frameid+marker.duration):
            logger.info(f"[cyan]Added note: '{note}'")
            marker.note = note
            return True
        
    logger.warning("[yellow]Couldn't set marker description.")
    return False
        
    
def clear_markers():
    """
    Delete all patchwork markers
    """
    
    global force_refresh
    
    patchwork_markers = resolve.active_timeline.markers.find_all("patchwork_marker")
    
    if not patchwork_markers:
        return False
    
    [x.delete() for x in patchwork_markers]
    return True


def menu_loglevel_callback(sender):
    
    # Uncheck all loglevel menu items
    loglevel_menu_items = {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }
    [dpg.set_value(x, False) for x in loglevel_menu_items]
    
    # Check chosen item
    dpg.set_value(sender, True)
    logger.setLevel(sender)

def open_defaults_configuration():
    
    logger.info(f"[cyan]Opening defaults config file: {defaults_filepath}")
    launch(defaults_filepath)

# Commands
def add_change():
    
    def change_note_callback():
        dpg.delete_item("change_note_popup")
        set_marker_note()
        

    global refresh_now
    create_marker()
    with dpg.window(tag="change_note_popup", autosize=True, modal=True):
        dpg.add_text("Add change note (optional)")
        dpg.add_input_text(tag="marker_note")
        dpg.add_button(label="Ok", callback=change_note_callback)

    refresh_now = True
    
def clear_changes():
    
    global refresh_now
    
    if not clear_markers():
        dialog_box.prompt("Oops, no changes to clear.")
        return
    
    refresh_now = True

def render_changes():
    
    logger.info("[magenta]Starting render routine")
    
    global patchwork_file
    assert patchwork_file
    
    project = resolve.project
    timeline = resolve.active_timeline
    markers = resolve.active_timeline.markers
    patchwork_markers = [x for x in markers if x.customdata == "patchwork_marker"]
    
    patch_data = patchfile.load(patchwork_file)
    print(patch_data)
    
    if not patch_data['project_name'] == project.name:
        dialog_box.prompt(
            "The active project doesn't match the linked patch file\n"
            "Please load the correct file or change project."
        )
        return
    
    if not patch_data['timeline_name'] == timeline.name:
        dialog_box.prompt(
            "The active timeline doesn't match the linked patch file\n"
            "Please load the correct file or change timeline."
        )
        return
        
    if not patch_data.get('render_preset'):
        dialog_box.prompt(
            "Render preset has not been defined within the patchfile!"
        )
        return
        
    # COMPARE
    current_settings = patchfile.get_current_settings()
    patchfile.compare(current_settings, patchwork_file)
    
    # Choose render preset
    chosen_render_preset = dpg.get_value("chosen_render_preset")
    if not chosen_render_preset:
        dialog_box.prompt("No render preset chosen.\nPlease choose one before continuing.")
    
    job_ids = []
    for x in patchwork_markers:
        resolve.project.load_render_preset(chosen_render_preset)
        project.set_render_settings(
            {
                "MarkIn": x.frameid,
                "MarkOut": x.frameid + x.duration,
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
    
    dpg.set_global_font_scale(1.2)
    dpg.configure_app(init_file=os.path.join(root_folder, "dpg.ini"))
    
    global window_width
    global window_height
    
    dpg.create_viewport(
        title='Patchwork 0.1.0', 
        width=window_width, 
        height=window_height, 
        min_width=window_width, 
        min_height=window_height,
        resizable=True,
    )
    dpg.set_viewport_always_top(True)
    dpg.setup_dearpygui()
    
    # TODO: Potentially make this async for faster start up?
    # Would need all of init to be async though...
    # Whilst awaiting viewport config json to load, set everything else up
    # Then once loaded, show the viewport?
    set_viewport_config()
    dpg.show_viewport()

    # These will silently crash dpg if instantiated earlier
    global routines
    global patchfile
    global dialog_box
    from patchwork import routines
    from patchwork import patchfile
    from patchwork.widgets import dialog_box
    

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
    global render_preset_chosen
    render_preset_chosen = False    

    # Timers
    global half_a_second
    global five_seconds
    half_a_second = routines.Timer(0.5)
    five_seconds = routines.Timer(5)

def setup_gui():
    
    # Configure disabled item theme
    with dpg.theme(tag="main_theme"):
        with dpg.theme_component(dpg.mvButton, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (122, 122, 122))
        with dpg.theme_component(dpg.mvCombo, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (122, 122, 122))
        dpg.bind_theme("main_theme")
        
    with dpg.window(label="main_window", tag="main_window", autosize=True):
        dpg.set_primary_window("main_window", True)

        # MENU BAR
        with dpg.menu_bar():

            with dpg.menu(label="Settings"):
                dpg.add_menu_item(label="Always on top", check=True, tag="menu_always_on_top", default_value=True, callback=toggle_always_on_top)
                dpg.add_menu_item(label="Configure defaults", callback=open_defaults_configuration)
                with dpg.menu(label="loglevel"):
                    dpg.add_menu_item(label="DEBUG", check=True, tag="DEBUG", default_value=False, callback=menu_loglevel_callback)
                    dpg.add_menu_item(label="INFO", check=True, tag="INFO", default_value=True, callback=menu_loglevel_callback)
                    dpg.add_menu_item(label="WARNING", check=True, tag="WARNING", default_value=False, callback=menu_loglevel_callback)
                    dpg.add_menu_item(label="ERROR", check=True, tag="ERROR", default_value=False, callback=menu_loglevel_callback)
                    dpg.add_menu_item(label="CRITICAL", check=True, tag="CRITICAL", default_value=False, callback=menu_loglevel_callback)
                
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About")
                dpg.add_menu_item(label="Docs", callback=open_documentation)
        
        # dpg.add_image("texture_tag") 
        # dpg.add_separator()
        
        
        ###############################################################
        ################# TRACK FILE DIALOG ###########################
        ###############################################################
        
        with dpg.file_dialog(
            directory_selector=False, 
            default_path=defaults['app']['starting_directory'],
            
            show=False, 
            callback=select_patchfile_callback, 
            cancel_callback=cancel_patchfile_callback, 
            modal=True,
            width=window_width - 50,
            height=window_height - 75,
            tag="track_file_dialog",
        ):

            dpg.add_file_extension(".patch", color=(255, 255, 0, 255))
            dpg.add_file_extension(".*")
         
        ###############################################################
        ################# RENDER FILE DIALOG ##########################
        ###############################################################
               
        with dpg.file_dialog(
            directory_selector=True, 
            default_path=defaults['app']['starting_directory'], 
            show=False, 
            callback=select_render_dir_callback, 
            cancel_callback=cancel_render_dir_callback, 
            modal=True,
            width=window_width - 50,
            height=window_height - 75,
            tag="render_file_dialog",
        ):
        
            dpg.add_file_extension(".patch", color=(255, 255, 0, 255))
            dpg.add_file_extension(".*")
        
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
                    dpg.add_combo(items=resolve.project.render_presets, default_value=defaults['render']['render_preset'], tag="render_preset", enabled=False)
    
                    
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

async def gui_render():
            
    dpg.render_dearpygui_frame()
    logger.debug(f"[magenta]{dpg.get_frame_count()}")
    
    global refresh_now
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

            global patchwork_file
            if patchwork_file:
                dpg.configure_item("add_button")
                
            if not patchwork_markers:
                dpg.configure_item("clear_changes_button")
                dpg.configure_item("render_button")
            else:
                dpg.configure_item("clear_changes_button")
                if patchwork_file:
                    dpg.configure_item("render_button")
                
                        
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

async def event_loop():
    
    # SETUP
    logger.debug("[magenta]Initialising...")
    init()
    setup_gui()
    logger.debug("[magenta]Ready!")
    
    # LOOP
    logger.debug("[magenta]Starting render cycle!")

    dpg.set_exit_callback(app_exit_callback)
    while dpg.is_dearpygui_running():
        async with trio.open_nursery() as nursery: 
            nursery.start_soon(gui_render)
    
    # EXIT
    logger.debug("[magenta]Exiting!")
    dpg.destroy_context()
    
def main():
    trio.run(event_loop)
    

if __name__ == "__main__":
    main()