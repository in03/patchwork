from dearpygui import dearpygui as dpg
import logging

logger = logging.getLogger(__name__)
# logger.setLevel(dpg.get_value("loglevel"))

def dialog_selection_callback(sender, unused, user_data) -> bool:
    if user_data[1]:
        logger.info("User chose OK")
        dpg.delete_item(user_data[0])
        return True
    else:
        logger.info("User chose Cancel")
        dpg.delete_item(user_data[0])
        return False
                   
def prompt(message:str, title:str="Dialog", show_ok:bool=True, show_cancel:bool=False, wrap:int=400, **kwargs) -> bool|None:
    
    if dpg.does_item_exist("dialog"):
        dpg.delete_item("dialog")
    
    with dpg.mutex():
        
        viewport_width = dpg.get_viewport_client_width()
        viewport_height = dpg.get_viewport_client_height()
        
        with dpg.window(label=title, modal=True, no_title_bar=True, tag="dialog", **kwargs) as dialog_window:
            dpg.add_text(message, wrap=wrap)
            dpg.add_separator()
            with dpg.group(horizontal=True, tag="dialog_buttons"):
                
                if show_ok:      
                    dpg.add_button(label="Ok", user_data=("dialog", True), callback = dialog_selection_callback)
                if show_cancel:
                    dpg.add_button(label="Cancel", user_data=("dialog", False), callback = dialog_selection_callback)
                
    dpg.split_frame()
    
    width = dpg.get_item_width("dialog")
    height = dpg.get_item_height("dialog")
    
    if width and height:
        dpg.set_item_pos("dialog", [viewport_width // 2 - width // 2, viewport_height // 2 - height // 2])