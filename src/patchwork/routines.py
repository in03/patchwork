from timecode import Timecode
from dearpygui import dearpygui as dpg
from pydavinci.wrappers.marker import MarkerCollection
from widgets import dialog_box

import trio

def refresh_add_status(markers:MarkerCollection, current_timecode:str, frame_rate:float, refresh_rate:float=0.5):
    
    # await trio.sleep(refresh_rate)

    current_frame = Timecode(frame_rate, current_timecode).frames
    current_marker = None
    
    if current_frame:
        
        current_frame -=1 # Single frame offset for some reason
        current_marker = [x for x in markers if current_frame >= x.frameid and current_frame < (x.frameid + x.duration)]
    
    if current_marker:
        
        assert len(current_marker) == 1
        current_marker = current_marker[0]
        
        #TODO: Set flag to allow prompting "overwrite"
        
        if not current_marker.customdata == "patchwork_marker":
            
            dpg.set_value("current_timecode_display", f"On unsupported marker")
            dpg.configure_item("current_timecode_display", color=[250, 0, 0])  
            
        else:
            dpg.set_value("current_timecode_display", f"On marker: '{current_marker.name}'")
            dpg.configure_item("current_timecode_display", color=[0, 255, 0])
        
    else:
        dpg.set_value("current_timecode_display", f"{current_timecode} | {current_frame}")
        dpg.configure_item("current_timecode_display", color=[50, 150, 255])

def check_timecode_starts_at_zero(current_timecode:str, frame_rate:float, refresh_rate:float=0.5):
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
    
    # await trio.sleep(refresh_rate)
    
    dismissed = dpg.get_value("zero_timecode_warning_dismissed")
    if dismissed is None:
        with dpg.value_registry():
            dpg.add_bool_value(tag="zero_timecode_warning_dismissed", default_value=False)
        
    if not dismissed:  
        
        if Timecode(frame_rate, current_timecode).hrs >= 1:  
            dialog_box.prompt(
                "Hey! Does your timeline timecode start at 01:00:00? If so, please set it to 00:00:00. "
                "Resolve's API has a glitch that causes markers to appear an hour later on the timeline. "
                "If not, nevermind."
            )
            dpg.set_value("zero_timecode_warning_dismissed", True)

def refresh_commit_status(markers:MarkerCollection, refresh_rate:float=0.5):
    
    committed_changes = []
    uncommitted_changes = []
    invalid_changes = []

    for x in markers:
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