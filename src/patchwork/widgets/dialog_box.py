from dearpygui import dearpygui as dpg
    
with dpg.window(label="Dialog", modal=True, show=False, tag="dialog_box", no_title_bar=True, autosize=True, pos=[150, 225]):
    dpg.add_text("Dialog text goes here", tag="dialog_text", wrap=500)
    dpg.add_separator()
    with dpg.group(horizontal=True, tag="dialog_buttons"):
        dpg.add_button(label="Ok", callback=lambda: dpg.configure_item("dialog_box", show=False))
                   
def prompt(message:str):
    if not dpg.is_item_shown("dialog_box"):
        dpg.configure_item("dialog_box", show=True, label="dialog")
        dpg.set_value("dialog_text", message)
    else:
        print("Dialog box is already in use!")