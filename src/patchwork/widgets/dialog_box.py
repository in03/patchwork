from dearpygui import dearpygui as dpg
import logging

logger = logging.getLogger("rich")

def dialog_selection_callback(sender, unused, user_data) -> bool:
    if user_data[1]:
        logger.debug("[magenta]User chose OK")
        dpg.delete_item(user_data[0])
        return True
    else:
        logger.debug("[magenta]User chose Cancel")
        dpg.delete_item(user_data[0])
        return False
                   
def prompt(
        message:str, 
        title:str="Dialog", 
        show_ok:bool=True, 
        show_cancel:bool=False, 
        ok_text:str="Ok", 
        cancel_text:str="Cancel", 
        width:int|None=None, 
        height:int|None=None, 
        pos:list[int]|None=None, 
        wrap:int=400, 
        **kwargs
    ) -> bool|None:
    
    if dpg.does_item_exist("dialog"):
        dpg.delete_item("dialog")

    viewport_width = dpg.get_viewport_client_width()
    viewport_height = dpg.get_viewport_client_height()
    
    if not width:
        width =  viewport_width - 21
    
    if not height:
        height = viewport_height - 50  
    
    if not pos:
        pos = pos=[viewport_width // 2 - wrap // 2, viewport_height // 2 - height // 2]
    
    with dpg.window(label=title, modal=True, no_title_bar=True, tag="dialog", width=width, height=height, pos=pos, **kwargs):
        dpg.add_text(message, wrap=wrap)
        dpg.add_separator()
        with dpg.group(horizontal=True, tag="dialog_buttons"):
            
            if show_ok:      
                dpg.add_button(label=ok_text, user_data=("dialog", True), callback = dialog_selection_callback)
            if show_cancel:
                dpg.add_button(label=cancel_text, user_data=("dialog", False), callback = dialog_selection_callback)
                
        