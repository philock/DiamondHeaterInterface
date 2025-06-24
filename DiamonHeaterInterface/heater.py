import dearpygui.dearpygui as dpg
from logger import mvLogger
import config as cfg
from pycomm import Comm, MSG
import os
import time

#log = mvLogger()

comm = Comm(baud_rate=115200)
temperature   = [] # Temperature data points
setpoint      = [] # Setpoint data points
time_temp     = [] # Timestamps for temperature data points
time_setpoint = [] # Timestamps for setpoint data points

status_prev = 0

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
        log.log_error("Failed to establish connection!")
    else:
        # Set default PID values
        comm.add_variable_token(dpg.get_value("slider_P"), MSG.PID_P)
        comm.add_variable_token(dpg.get_value("slider_I"), MSG.PID_I)
        comm.add_variable_token(dpg.get_value("slider_D"), MSG.PID_D)

        # Transmit PID values. Even if connection to the selected port was sucessful, it might not be the Teensy microcontroller and the write will fail
        try:
            comm.transmit() 
        except: 
            log.log_error("Failed to establish connection!")
        else:
            dpg.configure_item("Connect Button", label="Disconnect")
            dpg.configure_item("Connect Button", callback=disconnect)
            dpg.configure_item("Slider Group", enabled=True)
            dpg.configure_item("Temperature Group", enabled=True)
            log.log_info("Successfully connected")

# Disconnect button callback
def disconnect():
    comm.disconnect()
    dpg.configure_item("Connect Button", label="Connect")
    dpg.configure_item("Connect Button", callback=connect)
    dpg.configure_item("Slider Group", enabled=False)
    dpg.configure_item("Temperature Group", enabled=False)
    log.log_info("Disconnected")

# Callback to set a new temperature setpoint
def new_setpoint(sender, app_data):
    comm.add_variable_token(app_data, MSG.T_SETPOINT)
    comm.transmit()
    setpoint.append(app_data)
    time_setpoint.append(time.time() + 7200)

# Start temperature controller
def start_button():
    comm.add_flag_token(MSG.START)
    comm.transmit()
    print("Start")

# Stop temperature controller
def stop_button():
    comm.add_flag_token(MSG.STOP)
    comm.transmit()
    print("Stop")

# Reset error states of temperature controller
def reset_button():
    comm.add_flag_token(MSG.RESET)
    comm.transmit()

    # Set Start/Stop button back to start
    dpg.configure_item("start stop button", label="Start")
    dpg.configure_item("start stop button", callback=start_button)

    log.log_info("System reset")

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
    print(p)
    comm.add_variable_token(p, MSG.PID_P)
    comm.transmit()
    log.log_info("Set proportional gain")
def set_I():
    i = dpg.get_value("slider_I")
    print(i)
    comm.add_variable_token(i, MSG.PID_I)
    comm.transmit()
    log.log_info("Set integral gain")
def set_D():
    d = dpg.get_value("slider_D")
    print(d)
    comm.add_variable_token(d, MSG.PID_D)
    comm.transmit()
    log.log_info("Set differential gain")

# Set state indicators from binary state-word
def setIndicators(status):
    global status_prev

    # Only update when status changed
    if status == status_prev: return

    # XOR, one whereever there was a status change
    changes = status ^ status_prev 

    # Save status
    status_prev = status

    if(changes & 0b1):
        if (status & 0b1): dpg.configure_item("Indicator Active", texture_tag = "GreenIndicator")
        else:              dpg.configure_item("Indicator Active", texture_tag = "GreenIndicatorOff")

    if(changes & 0b10):
        if (status & 0b10): 
            dpg.configure_item("Indicator OT", texture_tag = "RedIndicator")
            log.log_error("Over-Temperature!")
        else:               
            dpg.configure_item("Indicator OT", texture_tag = "RedIndicatorOff")

    if(changes & 0b100):
        if (status & 0b100): 
            dpg.configure_item("Indicator OC", texture_tag = "RedIndicator")
            log.log_error("Over-Current!")
        else:                
            dpg.configure_item("Indicator OC", texture_tag = "RedIndicatorOff")

    if(changes & 0b1000):
        if (status & 0b1000): 
            dpg.configure_item("Indicator Fault", texture_tag = "RedIndicator")
            log.log_error("System Fault!")
        else:                 
            dpg.configure_item("Indicator Fault", texture_tag = "RedIndicatorOff")

    if(status & 0b1110): # One of the fault indicators is on
        dpg.configure_item("start stop button", label="Start")
        dpg.configure_item("start stop button", callback=start_button)

# Handle UI scaling when viewport is resized   
def on_viewport_resize(sender, app_data):
    width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()

    # Example split: left 25%, right 75% (stacked vertically)
    left_width = int(width * 0.25)
    right_width = width - left_width
    top_height = int(cfg.top_temperature_window_height)
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
        #dpg.fit_axis_data("y_axis") # y-axis fits to data automatically using auto_fit=True
        # Add some padding to the y-axis so that no plot line is at the limits of the plot
        """ y_min, y_max = dpg.get_axis_limits("y_axis")
        dpg.set_axis_limits("y_axis", y_min - 5, y_max + 5) """

# Handle acknowledgements sent back from controller
def handleAckNack(ack):
    msg = comm.get_next_msg()

    if ack: # Acknowledgements
        if msg.msg == MSG.START:
            dpg.configure_item("start stop button", label="Stop")
            dpg.configure_item("start stop button", callback=stop_button)
            log.log_info("System started")
        elif msg.msg == MSG.STOP:
            dpg.configure_item("start stop button", label="Start")
            dpg.configure_item("start stop button", callback=start_button)
            log.log_info("System stopped")
        elif msg.msg == MSG.T_SETPOINT:
            log.log_info("New setpoint")

    else: # Not Acknowledgements
        if msg.msg == MSG.START:
            log.log_error("Failed to start system!")
        elif msg.msg == MSG.STOP:
            log.log_error("Failed to stop system!")
        elif msg.msg == MSG.T_SETPOINT:
            log.log_info("Failed to set new setpoint!")

# Called continuously in the render loop
def handle_Serial():
    if not comm.ser.is_open:
        return
    
    if not comm.msg_available():
        return

    # Read all incoming messages until MSG_END
    while True:
        msg = comm.get_next_msg()
        #if msg.msg != MSG.MSG_END: print(msg.msg)

        if msg.msg == MSG.MSG_END:
            break  

        elif msg.msg == MSG.T_ACTUAL:
            # Update plot datapoints
            temperature.append(comm.get_payload(float))
            setpoint.append(dpg.get_value("setpoint_input"))
            t = time.time() + 7200 # Munich is two hours ahead of UTC (7200 seconds)
            time_setpoint.append(t)
            time_temp.append(t) 
        
            # Update UI elements
            update_Plot()
            dpg.configure_item("actual_temp_value", default_value=f"{temperature[-1]:.1f}")

        elif msg.msg == MSG.CURRENT:
            I = comm.get_payload(float)
            dpg.configure_item("current_value", default_value=f"{I:.2f}")

        elif msg.msg == MSG.STATUS:
            status = comm.get_payload(int)
            setIndicators(status)

        elif msg.msg == MSG.ACK:
            handleAckNack(True)

        elif msg.msg == MSG.NACK:
            handleAckNack(False)

        # Reset button on PCB was pressed
        elif msg.msg == MSG.RESET:
            dpg.configure_item("start stop button", label="Start")
            dpg.configure_item("start stop button", callback=start_button)
            log.log_info("Reset button pressed")

        elif msg.msg == MSG.ERROR_MSG:
            err_msg = comm.get_payload(str)
            log.log_debug(err_msg)

    # Acknowledge reception and feed the watchdog. If the controller does not receive this Ack over five seconds, it resets
    comm.add_flag_token(MSG.ACK) 
    comm.transmit()
    #print("Feed watchdog")

# Main function
def run():
    dpg.create_context()
    dpg.create_viewport(title='Diamond Heater Control', width=cfg.window_width, height=cfg.window_height)
    dpg.set_viewport_large_icon(os.path.join(os.path.dirname(__file__), "Icons", "icon.ico"))
    dpg.set_viewport_small_icon(os.path.join(os.path.dirname(__file__), "Icons", "icon.ico"))

    # Load fonts
    with dpg.font_registry():
        font_path = os.path.join(os.path.dirname(__file__), "Fonts", "fonts-DSEG_v046", "DSEG7-Classic", "DSEG7Classic-Regular.ttf")
        font_7seg = dpg.add_font(font_path, 35)
        font_path = os.path.join(os.path.dirname(__file__), "Fonts", "arial", "arial.ttf")
        font_arial = dpg.add_font(font_path, 20)
        font_arial_big = dpg.add_font(font_path, 40)

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
            dpg.add_combo(port_selection, tag="Port select", default_value="COM5", width=100)
            dpg.add_button(tag = "Connect Button", label="Connect", callback=connect)

        # Sliders to change PID loop gains. Handlers to only transmit after slider is released.
        dpg.add_separator(label="PID Settings")
        dpg.add_text("PID control loop gains")
        with dpg.item_handler_registry(tag="release handler P") as handler:
            dpg.add_item_deactivated_after_edit_handler(callback=set_P)
        with dpg.item_handler_registry(tag="release handler I") as handler:
            dpg.add_item_deactivated_after_edit_handler(callback=set_I)
        with dpg.item_handler_registry(tag="release handler D") as handler:
            dpg.add_item_deactivated_after_edit_handler(callback=set_D)
        with dpg.group(tag="Slider Group", enabled=False):
            dpg.add_slider_float(tag="slider_P", max_value=cfg.P_max, default_value=cfg.P_default, format="Kp = %.5f")#, callback=set_P)
            dpg.add_slider_float(tag="slider_I", max_value=cfg.I_max, default_value=cfg.I_default, format="Ki = %.5f")#, callback=set_I)
            dpg.add_slider_float(tag="slider_D", max_value=cfg.D_max,min_value=-cfg.D_max, default_value=cfg.D_default, format="Kd = %.5f")#, callback=set_D)
        dpg.bind_item_handler_registry("slider_P", "release handler P")
        dpg.bind_item_handler_registry("slider_I", "release handler I")
        dpg.bind_item_handler_registry("slider_D", "release handler D")
        
        # Logger box for status messages
        dpg.add_separator(label="Log")
        global log
        log = mvLogger(parent="Settings Window")
            
    # Temperature window at top of viewport
    with dpg.window(tag="Temperature Window", no_title_bar=True, no_resize=True, no_move=True, no_close=True):
        with dpg.group(tag="Temperature Group", horizontal=True, horizontal_spacing=40, enabled=False):
            # Status indicator lights
            with dpg.group(tag="status_light_group", horizontal=False, ):
                for status_name, tag_name in zip(["System Fault", "Over-Current", "Over-Temperature"], ["Indicator Fault", "Indicator OC", "Indicator OT"]):
                    with dpg.group(horizontal=True):
                        dpg.add_image("RedIndicatorOff",tag=tag_name, width=18, height=18)
                        dpg.add_text(status_name)
                with dpg.group(horizontal=True):
                    dpg.add_image("GreenIndicatorOff", tag="Indicator Active",width=18, height=18)
                    dpg.add_text("Active")

            # Start/Stop and Reset button
            with dpg.group(tag="System Controls Group", horizontal=False):
                dpg.add_button(tag="start stop button", label="Start",width=100, height=40, callback=start_button)
                dpg.add_button(tag="reset button", label="Reset",width=100, height=40, callback=reset_button)
                dpg.bind_item_font("start stop button", font_arial)
                dpg.bind_item_font("reset button", font_arial)


            # Temperature setpoint input box
            with dpg.group(horizontal=False):
                dpg.add_text("Setpoint", tag="text_temp_setpoint")
                dpg.bind_item_font("text_temp_setpoint", font_arial)
                with dpg.group(horizontal=True):
                    dpg.add_input_float(tag="setpoint_input", default_value=0.0,min_value=cfg.T_min,max_value=cfg.T_max, format="%.1f", width=120, step=0, step_fast=0, callback=new_setpoint, on_enter=True)
                    dpg.add_text("°C", tag="Celcius_setpoint")
                    dpg.bind_item_font("setpoint_input", font_7seg)
                    dpg.bind_item_font("Celcius_setpoint", font_arial_big)

            # Actual Temperature display
            with dpg.group(horizontal=False):
                current_temp = 0.0
                dpg.add_text("Temperature", tag="actual_temp_label")
                dpg.bind_item_font("actual_temp_label", font_arial)
                with dpg.group(horizontal=True):
                    dpg.add_text(f"{current_temp:.1f}", tag="actual_temp_value")
                    dpg.add_text("°C", tag="Celcius_actual")
                    dpg.bind_item_font("actual_temp_value", font_7seg)
                    dpg.bind_item_font("Celcius_actual", font_arial_big)

            # Actual Current display
            with dpg.group(horizontal=False):
                current = 0.0
                dpg.add_text("Current", tag="current_label")
                dpg.bind_item_font("current_label", font_arial)
                with dpg.group(horizontal=True):
                    dpg.add_text(f"{current:.2f}", tag="current_value")
                    dpg.add_text("A", tag="Amps")
                    dpg.bind_item_font("current_value", font_7seg)
                    dpg.bind_item_font("Amps", font_arial_big)

    # Plot window
    with dpg.window(tag="Plot Window", no_title_bar=True, no_resize=True, no_move=True, no_close=True):
        # create plot
        with dpg.plot(label="Line Series", height=-1, width=-1):
            # optionally create legend
            dpg.add_plot_legend()

            # REQUIRED: create x and y axes
            dpg.add_plot_axis(dpg.mvXAxis, label="Time", tag="x_axis", scale=dpg.mvPlotScale_Time)
            dpg.add_plot_axis(dpg.mvYAxis, label="T (°C)", tag="y_axis", auto_fit=True)

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
    #dpg.set_exit_callback(on_window_close)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    #dpg.start_dearpygui() # Only necessary when main render loop is not accessed

    # Main loop
    while dpg.is_dearpygui_running():
        handle_Serial()
        dpg.render_dearpygui_frame()

    comm.close()
    dpg.destroy_context()