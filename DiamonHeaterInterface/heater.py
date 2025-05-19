import dearpygui.dearpygui as dpg
from dearpygui_ext.logger import mvLogger
import config as cfg
from pycomm import Comm, MSG
import os
import time

comm = Comm(baud_rate=115200)
temperature   = [] # Temperature data points
setpoint      = [] # Setpoint data points
time_temp     = [] # Timestamps for temperature data points
time_setpoint = [] # Timestamps for setpoint data points

# Scan available serial ports and update scroll box
def scanPorts():
    ports = comm.available_ports()

    dpg.delete_item("Ports list", children_only=True)
    for port, desc, hwid in sorted(ports):
        dpg.add_text("{}: {} [{}]".format(port, desc, hwid), parent="Ports list")

# Connect button callback
def connect():
    port = dpg.get_value("Port select")
    try:
        comm.connect(port)
    except:
        print("fail")
    else:
        dpg.configure_item("Connect Button", label="Disconnect")
        dpg.configure_item("Connect Button", callback=disconnect)
        dpg.configure_item("Slider Group", enabled=True)
        # Set default PID values
        comm.add_variable_token(dpg.get_value("slider_P"), MSG.PID_P)
        comm.add_variable_token(dpg.get_value("slider_I"), MSG.PID_I)
        comm.add_variable_token(dpg.get_value("slider_D"), MSG.PID_D)
        comm.transmit()

# Disconnect button callback
def disconnect():
    comm.disconnect()
    dpg.configure_item("Connect Button", label="Connect")
    dpg.configure_item("Connect Button", callback=connect)
    dpg.configure_item("Slider Group", enabled=False)

# clear plot button callback
def clear_plot():
    temperature.clear()
    setpoint.clear()
    time_temp.clear()
    time_setpoint.clear()
    update_Plot()

# Slider callbacks: Send new PID gains to heater
def set_P():
    p = dpg.get_value("slider_P")
    comm.add_variable_token(p, MSG.PID_P)
    comm.transmit()
def set_I():
    i = dpg.get_value("slider_I")
    comm.add_variable_token(i, MSG.PID_I)
    comm.transmit()
def set_D():
    d = dpg.get_value("slider_D")
    comm.add_variable_token(d, MSG.PID_D)
    comm.transmit()

def setActiveIndicator(isOn):
    if isOn: dpg.configure_item("Indicator Active", texture_tag = "GreenIndicator")
    else:    dpg.configure_item("Indicator Active", texture_tag = "GreenIndicatorOff")
def setFaultIndicator(isOn):
    if isOn: dpg.configure_item("Indicator Fault", texture_tag = "RedIndicator")
    else:    dpg.configure_item("Indicator Fault", texture_tag = "RedIndicatorOff")
def setOCIndicator(isOn):
    if isOn: dpg.configure_item("Indicator OC", texture_tag = "RedIndicator")
    else:    dpg.configure_item("Indicator OC", texture_tag = "RedIndicatorOff")
def setOTIndicator(isOn):
    if isOn: dpg.configure_item("Indicator OT", texture_tag = "RedIndicator")
    else:    dpg.configure_item("Indicator OT", texture_tag = "RedIndicatorOff")

# Handle UI scaling when viewport is resized   
def on_viewport_resize(sender, app_data):
    width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()

    # Example split: left 25%, right 75% (stacked vertically)
    left_width = int(width * 0.25)
    right_width = width - left_width
    top_height = int(height * 0.2)
    bottom_height = height - top_height

    # Reposition and resize windows
    dpg.configure_item("Settings Window", pos=(0, 0), width=left_width, height=height)
    dpg.configure_item("Temperature Window", pos=(left_width, 0), width=right_width, height=top_height)
    dpg.configure_item("Plot Window", pos=(left_width, top_height), width=right_width, height=bottom_height)

# Pushes new temperature to the screen
def update_Plot():
    dpg.set_value("Setpoint Series", [time_setpoint, setpoint])
    dpg.set_value("Temperature Series", [time_temp, temperature])
    if(dpg.get_value("Checkbox Autoscale")):
        dpg.fit_axis_data("x_axis")
        dpg.fit_axis_data("y_axis")

# Called continuously in the render loop
def handle_Serial():
    if not comm.msg_available:
        return
    
    if not comm.ser.is_open:
        return
    
    # Read all incoming messages until MSG_END
    while True:
        msg = comm.get_next_msg()
        if msg.msg == MSG.MSG_END:
            break
        if msg.msg == MSG.T_ACTUAL:
            temperature.append(comm.get_payload(float))
            time_temp.append(time.time() + 7200) # Munich two hours ahead of UTC
            update_Plot()
            dpg.configure_item("current_temp_text", default_value=f"{temperature[-1]:.1f}")

        elif msg.msg == MSG.STATUS:
            status = comm.get_payload(int)
            setActiveIndicator(status & 0b1)
            setOTIndicator(status & 0b10)
            setOCIndicator(status & 0b100)
            setFaultIndicator(status & 0b1000)

def run():
    dpg.create_context()
    dpg.create_viewport(title='Diamond Heater Control', width=cfg.window_width, height=cfg.window_height)

    # Load fonts
    with dpg.font_registry():
        font_path = os.path.join(os.path.dirname(__file__), "Fonts", "fonts-DSEG_v046", "DSEG7-Classic", "DSEG7Classic-Regular.ttf")
        font_7seg = dpg.add_font(font_path, 30)
        font_path = os.path.join(os.path.dirname(__file__), "Fonts", "arial", "arial.ttf")
        font_arial = dpg.add_font(font_path, 20)

    # Load icons
    with dpg.texture_registry(show=False):
        for icon in ["RedIndicator.png", "RedIndicatorOff.png", "GreenIndicator.png", "GreenIndicatorOff.png"]:
            width, height, channels, data = dpg.load_image(os.path.join(os.path.dirname(__file__), "Icons", icon))
            dpg.add_static_texture(width=width, height=height, default_value=data, tag=icon.replace(".png",""))

    # Settings window
    with dpg.window(tag="Settings Window", no_title_bar=True, no_resize=True, no_move=True, no_close=True):
        dpg.add_separator(label="Connection")

        # Scan for available serial ports and list them in a scrollable box
        dpg.add_button(tag = "Scan Button", label="Scan Ports", callback=scanPorts)
        with dpg.child_window(tag="Ports list", autosize_x=True, auto_resize_y=True, menubar=True):
            with dpg.menu_bar():
                dpg.add_menu(label="Available Ports")

        # Dropdown menu to select serial port and button to connect
        with dpg.group(horizontal=True):
            port_selection = ("COM0", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "COM10")
            dpg.add_combo(port_selection, tag="Port select", default_value="COM0", width=100)
            dpg.add_button(tag = "Connect Button", label="Connect", callback=connect)

        # Sliders to change PID loop gains
        dpg.add_separator(label="PID Settings")
        dpg.add_text("PID control loop gains")
        with dpg.group(tag="Slider Group", enabled=False):
            dpg.add_slider_float(tag="slider_P", max_value=cfg.P_max, default_value=cfg.P_default, format="Kp = %.1f", callback=set_P)
            dpg.add_slider_float(tag="slider_I", max_value=cfg.I_max, default_value=cfg.I_default, format="Ki = %.1f", callback=set_I)
            dpg.add_slider_float(tag="slider_D", max_value=cfg.D_max, default_value=cfg.D_default, format="Kd = %.1f", callback=set_D)
        
        # Logger box for status messages
        dpg.add_separator(label="Log")
        log = mvLogger(parent="Settings Window")
        log.log("log")
        #log.log_debug("log debug")
        #log.log_info("log info")
        log.log_warning("log warning")
        log.log_error("log error")
        #log.log_critical("log critical")
            
    # Temperature window at top of viewport
    with dpg.window(tag="Temperature Window", no_title_bar=True, no_resize=True, no_move=True, no_close=True):
        with dpg.group(horizontal=True, xoffset=220):
            # Status indicator lights
            with dpg.group(tag="status_light_group", horizontal=False, ):
                for status_name, tag_name in zip(["System Fault", "Over-Current", "Over-Temp"], ["Indicator Fault", "Indicator OC", "Indicator OT"]):
                    with dpg.group(horizontal=True):
                        dpg.add_image("RedIndicatorOff",tag=tag_name, width=20, height=20)
                        dpg.add_text(status_name)
                with dpg.group(horizontal=True):
                    dpg.add_image("GreenIndicatorOff", tag="Indicator Active",width=20, height=20)
                    dpg.add_text("Active")

            # Temperature setpoint input box
            with dpg.group(horizontal=False):
                dpg.add_text("Setpoint Temperature", tag="text_temp_setpoint")
                dpg.add_input_float(tag="setpoint_input", default_value=0.0, format="%.1f", width=200, step=0, step_fast=0)
                dpg.bind_item_font("text_temp_setpoint", font_arial)
                dpg.bind_item_font("setpoint_input", font_7seg)

            # Actual Temperature display
            with dpg.group(horizontal=False):
                current_temp = 0.0
                dpg.add_text("Actual Temperature", tag="text_temp_actual")
                dpg.add_text(f"{current_temp:.1f}", tag="current_temp_text")
                dpg.bind_item_font("text_temp_actual", font_arial)
                dpg.bind_item_font("current_temp_text", font_7seg)

    # Plot window
    with dpg.window(tag="Plot Window", no_title_bar=True, no_resize=True, no_move=True, no_close=True):
        # create plot
        with dpg.plot(label="Line Series", height=-1, width=-1):
            # optionally create legend
            dpg.add_plot_legend()

            # REQUIRED: create x and y axes
            dpg.add_plot_axis(dpg.mvXAxis, label="Time", tag="x_axis", scale=dpg.mvPlotScale_Time)
            dpg.add_plot_axis(dpg.mvYAxis, label="T (°C)", tag="y_axis")

            # series belong to a y axis
            dpg.add_line_series(time_setpoint, setpoint, label="Setpoint", tag="Setpoint Series", parent="y_axis")
            dpg.add_line_series(time_temp, temperature, label="Temperature", tag="Temperature Series", parent="y_axis")

        # Menu bar 
        with dpg.menu_bar():
            with dpg.menu(label="Plot Settings"):
                dpg.add_checkbox(label="Autoscale Axis", tag="Checkbox Autoscale", default_value=True)
                dpg.add_button(label="Clear Plot", callback=clear_plot)

    # Callback for Window resizing
    dpg.set_viewport_resize_callback(on_viewport_resize)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    #dpg.start_dearpygui() # Only necessary when main render loop is not accessed

    # Main loop
    while dpg.is_dearpygui_running():
        handle_Serial()
        dpg.render_dearpygui_frame()

    dpg.destroy_context()