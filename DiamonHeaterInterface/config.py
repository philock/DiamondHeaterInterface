# GUI layout
aspect_ratio = 16/10
window_width = 1200
window_height = round(window_width/aspect_ratio)
top_temperature_window_height = 105

# Plot downsampling. After N_points_max datapoints, the plot gets downsampled by factor of two.
N_points_max = 30000

# Temperature settings
T_max = 200.0
T_min = 0

# PID settings
P_max = 0.2
I_max = 0.05
D_max = 0.05

# PID default values
P_default = 0.045
I_default = 0.01
D_default = 0.0