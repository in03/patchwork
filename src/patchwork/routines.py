from timecode import Timecode
from dearpygui import dearpygui as dpg
from pydavinci.wrappers.marker import MarkerCollection, Marker
from widgets import dialog_box
import trio
import logging

logger = logging.getLogger(__name__)
logger.setLevel(dpg.get_value("loglevel"))


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

async def get_marker_at_playhead(current_markers:MarkerCollection, current_frame:int) -> Marker|None:
    
    logger.debug("[magenta]Checking for marker at playhead")
    
    marker_at_playhead = None
    if current_frame:
    
        playhead_markers = [x for x in current_markers if current_frame >= x.frameid and current_frame < (x.frameid + x.duration)]
        
        if len(playhead_markers) > 1:
            raise ValueError(f"Multiple overlapping Patchwork markers are disallowed!\n{[str(x) for x in playhead_markers]}")
        
        if len(playhead_markers) == 1:
            marker_at_playhead = playhead_markers[0]
        
    await trio.sleep(0)
    return marker_at_playhead 

async def refresh_add_status(current_markers:MarkerCollection, current_timecode:str, current_frame:int):
    
    logger.debug("[magenta]Refreshing 'Add' status")
            
    marker_at_playhead = await get_marker_at_playhead(current_markers, current_frame)
    if marker_at_playhead:
        
        #TODO: Set flag to allow prompting "overwrite"
        
        if not marker_at_playhead.customdata == "patchwork_marker":
            
            dpg.set_value("current_timecode_display", f"On unsupported marker")
            dpg.configure_item("current_timecode_display", color=[250, 0, 0])  
            
        else:
            dpg.set_value("current_timecode_display", f"On marker: '{marker_at_playhead.name}'")
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

async def refresh_commit_status(current_markers:MarkerCollection):
    
    logger.debug("[magenta]Refreshing 'Commit' status")
    
    committed_changes = []
    uncommitted_changes = []
    invalid_changes = []

    for x in current_markers:
        if x.customdata != "patchwork_marker":
            continue
        if x.color == "Green":
            committed_changes.append(x)
        elif x.color == "Purple":
            uncommitted_changes.append(x)
        else:
            invalid_changes.append(x)

    assert not invalid_changes 
            
    if committed_changes and not uncommitted_changes:
        dpg.configure_item("commit_status", color=[0, 255, 0]) 
        dpg.set_value("commit_status", f"All changes committed")
        
    elif uncommitted_changes and not committed_changes:
        dpg.configure_item("commit_status", color=[255, 150, 0]) 
        dpg.set_value("commit_status", f"{len(uncommitted_changes)} uncommitted")

    elif uncommitted_changes:
        dpg.configure_item("commit_status", color=[255, 150, 0]) 
        dpg.set_value(
            "commit_status", 
            f"{len(uncommitted_changes)} uncommitted | "
            f"{len(committed_changes)} committed"
        )

    elif not committed_changes and not uncommitted_changes:
        dpg.configure_item("commit_status", color=[50, 150, 255])
        dpg.set_value("commit_status", "No changes")
        
    else:
        dpg.configure_item("commit_status", color=[255, 150, 0])
        dpg.set_value("commit_status", "N/A")
            
    await trio.sleep(0)
