from DiamonHeaterInterface.pycomm import Comm, MSG
import time
import serial.tools.list_ports

ports = serial.tools.list_ports.comports()
for port, desc, hwid in sorted(ports):
        print("{}: {} [{}]".format(port, desc, hwid))

# Initialize communication with COM port
comm = Comm(port="COM5", baud_rate=115200)
#time.sleep(0.5)

while True:
    # Add messages to the buffer
    print("Sending...")

    #comm = Comm(port="COM5", baud_rate=115200)

    comm.add_flag_token(MSG.RESET)
    """ comm.add_variable_token(25.5, MSG.T_SETPOINT)
    comm.add_variable_token(0.75, MSG.PID_P) """
    #comm.ser.write(b'hello')
    comm.transmit()

    print("Transmitted!")

    #comm.close()
    time.sleep(1)

    while not comm.msg_available:
        time.sleep(0.01)

    
    # Receive messages
    while True:
        msg = comm.get_next_msg()
        if msg.msg == MSG.MSG_END:
            break
            
        if msg.msg == MSG.T_ACTUAL:
            temperature = comm.get_payload(float)
            print(f"Current temperature: {temperature}°C")
        elif msg.msg == MSG.CURRENT:
            current = comm.get_payload(float)
            print(f"Current value: {current}A")
        
# Close the connection when done
comm.close()