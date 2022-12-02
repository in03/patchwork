from timecode import Timecode
from dearpygui import dearpygui as dpg
from pydavinci.wrappers.marker import MarkerCollection, Marker
from pydavinci import davinci
from pydavinci.exceptions import TimelineNotFound
from widgets import dialog_box
import trio
import logging

logger = logging.getLogger(__name__)
logger.setLevel(dpg.get_value("loglevel"))

def __compare_state():
    
    current_project = dpg.get_value("current_project")
    last_project = dpg.get_value("last_project")
    logger.debug(f"Last project: {last_project}, Current project: {current_project}")
    
    if current_project == last_project:
        dpg.set_value("project_has_changed", False)
    else:
        dpg.set_value("project_has_changed", True)
        dpg.set_value("environment_has_changed", True)
        logger.debug("PROJECT Environment has changed!")
        
    current_timeline = dpg.get_value("current_timeline")
    last_timeline = dpg.get_value("last_timeline")
    logger.debug(f"Last timeline: {last_timeline}, Current timeline: {current_timeline}")
    
    if current_timeline == last_timeline:
        dpg.set_value("timeline_has_changed", False)
    else:
        dpg.set_value("timeline_has_changed", True)
        dpg.set_value("environment_has_changed", True)
        logger.debug("TIMELINE Environment has changed!")
        
    dpg.set_value("last_project", current_project)
    dpg.set_value("last_timeline", current_timeline)
        
def __refresh_state():
    
    if not dpg.does_item_exist("state_registry"):
        logger.debug("[magenta]Creating new state registry")
        
        with dpg.value_registry(tag="state_registry"):
            
            dpg.add_string_value(tag="current_project", default_value="")
            dpg.add_string_value(tag="current_timeline", default_value="")
            dpg.add_string_value(tag="last_project", default_value="")
            dpg.add_string_value(tag="last_timeline", default_value="")
            dpg.add_bool_value(tag="project_has_changed", default_value=False)
            dpg.add_bool_value(tag="timeline_has_changed", default_value=False)
            dpg.add_bool_value(tag="resolve_is_open", default_value=False)
            dpg.add_bool_value(tag="project_is_open", default_value=False)
            dpg.add_bool_value(tag="timeline_is_open", default_value=False)
            dpg.add_bool_value(tag="environment_has_changed", default_value=False)

    try:
        
        resolve = davinci.Resolve()
        
    except TypeError as e:
        
        logger.warning(f"[yellow]Resolve is not open\n{e}")
        dpg.set_value("resolve_is_open", False)
        dpg.set_value("project_is_open", False)
        dpg.set_value("timeline_is_open", False)
        return
        
    except TimelineNotFound as e:
        
        logger.warning(f"[yellow]No timeline is open\n{e}")
        dpg.set_value("resolve_is_open", True)
        dpg.set_value("project_is_open", True)
        dpg.set_value("timeline_is_open", False)
        return
    
    else:
    
        project_name = str(resolve.project.name)
        timeline_name = str(resolve.active_timeline.name)
        dpg.set_value("current_project", project_name)
        dpg.set_value("last_project", project_name)
        dpg.set_value("current_timeline",timeline_name)
        dpg.set_value("last_timeline", timeline_name)
        
        dpg.set_value("resolve_is_open", True)
        dpg.set_value("project_is_open", True)
        dpg.set_value("timeline_is_open", True)

def get_environment_state():
    __refresh_state()
    __compare_state()

class Timer:
    # keeps track of DPG time since last render
    # note: frame rate speeds up by a factor of 4 to 5
    # when manipulating the viewport

    def __init__(self, interval):
        self.total_time = dpg.get_total_time()
        self.last_total_time = dpg.get_total_time()
        self.interval = interval

    @property
    def has_passed(self):
        self.total_time = dpg.get_total_time()
        delta_time = dpg.get_total_time() - self.last_total_time
        if delta_time > self.interval:
            self.last_total_time = self.total_time
            return True
        return False

async def get_markers_at_playhead(current_markers:MarkerCollection, current_frame:int) -> list[Marker]:
    
    logger.debug("[magenta]Checking for marker at playhead")
    
    playhead_markers = []
    if current_frame:
    
        playhead_markers = [x for x in current_markers if current_frame >= x.frameid and current_frame < (x.frameid + x.duration)]
        
    await trio.sleep(0)
    return playhead_markers 

async def refresh_add_status(current_markers:MarkerCollection, current_timecode:str, current_frame:int):
    
    logger.debug("[magenta]Refreshing 'Add' status")
    playhead_markers = await get_markers_at_playhead(current_markers, current_frame)
    if playhead_markers:
                
        # If any patchwork markers overlap
        if len(playhead_markers) > 1:
            if [x.customdata == "patchwork_marker" for x in playhead_markers]:
                dpg.set_value("current_timecode_display", f"Multiple overlapping markers, unsupported!")
                dpg.configure_item("current_timecode_display", color=[250, 0, 0])  
        
        # If not a patchwork marker
        elif len(playhead_markers) == 1:
            if not playhead_markers[0].customdata == "patchwork_marker":
                dpg.set_value("current_timecode_display", f"Not a patchwork marker")
                dpg.configure_item("current_timecode_display", color=[250, 150, 50])  
            
            else:
                dpg.set_value("current_timecode_display", f"On marker: '{playhead_markers[0].name}'")
                dpg.configure_item("current_timecode_display", color=[0, 255, 0])
    else:
        dpg.set_value("current_timecode_display", f"{current_timecode} | {current_frame}")
        dpg.configure_item("current_timecode_display", color=[50, 150, 255])
            
    await trio.sleep(0)

async def check_timecode_starts_at_zero(current_frame_rate:float, current_timecode:str):
    
    """
    Check that the Resolve timeline timecode starts at 00:00:00
    
    If it doesn't weird things happen with the markers (Resolve's fault).
    Prompt the user once per session. Unfortunately, running this once outside of the
    render loop doesn't seem to work. So we set a flag, but run it each time. 

    Args:
        current_timecode (str): The current timecode at playhead position
        frame_rate (float): The timeline framerate
        start_timecode_check_dismissed (bool): The flag to check for dialog box dismissal
    """
    
    logger.debug("[magenta]Check timecode starts at zero")
    
    dismissed = dpg.get_value("zero_timecode_warning_dismissed")
    if dismissed is None:
        with dpg.value_registry():
            dpg.add_bool_value(tag="zero_timecode_warning_dismissed", default_value=False)
        
    if not dismissed:  
        
        if Timecode(current_frame_rate, current_timecode).hrs >= 1:  
            dialog_box.prompt(
                "Hey! Does your timeline timecode start at 01:00:00? If so, please set it to 00:00:00. "
                "Resolve's API has a glitch that causes markers to appear an hour later on the timeline. "
                "If not, nevermind."
            )
            dpg.set_value("zero_timecode_warning_dismissed", True)
            
    await trio.sleep(0)