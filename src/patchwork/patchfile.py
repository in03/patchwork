
from pydavinci import davinci
from dearpygui import dearpygui as dpg
from patchwork.widgets import dialog_box
from deepdiff import DeepDiff
import json
from json import JSONDecodeError


import logging

logger = logging.getLogger("rich")

resolve = davinci.Resolve()

def safe_dump(obj, **kwargs):
  default = lambda o: f"<<non-serializable: {type(o).__qualname__}>>"
  return json.dumps(obj, default=default, **kwargs)

def get_changes_data()-> dict:
    
    timeline = resolve.active_timeline
    return [x.__dict__ for x in timeline.markers if x.customdata == "patchwork_marker"][0]['_data']
    
# MANIPULATE PATCHWORK FILE
def get_current_settings() -> dict:
    
    project = resolve.project
    timeline = resolve.active_timeline
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
        },
        "changes": get_changes_data(),
        "render_preset": dpg.get_value("chosen_render_preset"),
    }
    return data

def compare(current_settings:dict, patchwork_file:str):
    
    patchwork_file_data = load(patchwork_file)

    if current_settings["project_name"] != patchwork_file_data["project_name"]:
        dialog_box.prompt(
            f"Looks like the tracked file is for a different project: '{patchwork_file_data['project_name']}'\n"
            "Please load the correct patchwork_file for this project, or create a new one."
        )
        return
    
    if current_settings["timeline_name"] != patchwork_file_data["timeline_name"]:
        dialog_box.prompt(
            f"Looks like the tracked file is for a different timeline: '{patchwork_file_data['timeline_name']}'\n"
            "Please load the correct patchwork_file for this timeline, or create a new one."
        )
        return
    
    settings_diff = DeepDiff(current_settings["settings"], patchwork_file_data["settings"])
    if settings_diff:
        
        print(settings_diff)
        dialog_box.prompt(
            "Looks like project settings have been altered since the master file was rendered!\n"
            "You will need to render a master file again, since consistent results cannot be guaranteed with different settings\n"
            f"{settings_diff}"
        )
        return
    
def load(patchwork_file):
    
    patchwork_file_data = {}
    with open(patchwork_file) as patchwork_file:
        patchwork_file_data = json.loads(patchwork_file.read())
        
    return patchwork_file_data
    
def update(patchwork_file, writable):
    
    if not patchwork_file:
        logger.error("[red]No patchwork_file chosen")
        return None
    
    existing_data = load(patchwork_file)
    with open(patchwork_file, "w") as json_file:
        if existing_data:
            writable.update(existing_data)
        return json.dump(writable, json_file)
        
def new(patchwork_file_path):
    
    data = get_current_settings()
    
    try:
        with open(patchwork_file_path, "w") as patchwork_file:
            patchwork_file.write(safe_dump(data, sort_keys=True))
    except PermissionError:
        dialog_box.prompt("You don't have write permissions to this folder. Try another one.")
