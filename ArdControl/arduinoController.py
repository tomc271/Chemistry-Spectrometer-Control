import threading
import serial
import logging
import time
import csv
import os

class ArduinoController:
    def __init__(self, port, verbose, mode):
        self.port = port    # Port number to connect to arduino
        self.baudrate = 9600    # Baudrate for serial connection
        self.verbose = verbose  # Verbose mode
        self.mode = mode    # Mode of operation (0 = manual, 1 = sequence, 2 = TTL)
        self.arduino = None # Container for arduino object
        self.valve_states = []  # Container for valve states
        self.pressure_values = []   # Container for pressure values
        self.readings = []  # Container for pressure readings
        self.serial_connected = False   # Flag to indicate serial connection
        self.shutdown_flag = False  # Flag to indicate server shutdown
        self.save_pressure = False  # Flag to indicate saving pressure data
        self.new_reading = False  # Flag to indicate new pressure reading
        self.sequence_loaded = False    # Flag to indicate sequence loaded
        self.last_heartbeat_time = time.time()
        self.heartbeat_time = 5  # Time in seconds between heartbeats
        self.auto_control = False
        self.pressure_data_filepath = ""
        self.commands_dict = {
            "HEARTBEAT": 'y',  # Heartbeat response
            "DECODE_SEQUENCE": 'i',  # Decode a sequence input
            "EXECUTE_SEQUENCE": 'R',  # Execute the current loaded sequence
            "ENABLE_PRESSURE_LOG": 'K',  # Enable pressure logging
            "DISABLE_PRESSURE_LOG": 'k',  # Disable pressure logging
            "SWITCH_TO_MANUAL": 'm',  # Switch to manual control (TN = 0)
            "SWITCH_TO_AUTO_CONTROL": 'M',  # Switch to spec'r control (TN = 1)
            "ENABLE_TTL_CONTROL": 'T',  # Enable TTL control
            "DISABLE_TTL_CONTROL": 't',  # Disable TTL control
            "TURN_ON_SHORT_VALVE": 'Z',  # Turn on short valve
            "TURN_OFF_SHORT_VALVE": 'z',  # Turn off short valve
            "TURN_ON_INPUT_VALVE": 'C',  # Turn on input valve
            "TURN_OFF_INPUT_VALVE": 'c',  # Turn off input valve
            "TURN_ON_OUTPUT_VALVE": 'V',  # Turn on output valve
            "TURN_OFF_OUTPUT_VALVE": 'v',  # Turn off output valve
            "TURN_ON_NN_VALVE": 'X',  # Turn on NN valve
            "TURN_OFF_NN_VALVE": 'x',  # Turn off NN valve
            "TURN_ON_OPH_VALVE": 'H',  # Turn on OPH valve
            "TURN_OFF_OPH_VALVE": 'h',  # Turn off OPH valve
            "RESET": 's'    # Reset the Arduino
        }

        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        if mode == 0:
            self.auto_control = False
        elif mode == 1:
            self.auto_control = True
            logging.info("Magritek mode enabled")
        elif mode == 2:
            self.auto_control = True
            logging.info("TTL mode enabled")
        else:
            logging.error("Invalid mode, defaulting to manual mode")
            self.mode = 0
            self.auto_control = False

    def start(self):
        self.connect_arduino()
        if self.serial_connected:
            self.start_heartbeat()
            self.start_reading()

    def connect_arduino(self):
        try:
            self.arduino = serial.Serial(f"COM{self.port}", self.baudrate)
            logging.info(f"Connected to Arduino on port {self.port}")
            self.serial_connected = True
        except serial.SerialException as e:
            logging.error(f"Failed to connect to Arduino on port {self.port}: {e}")
            self.serial_connected = False

    def start_heartbeat(self):
        self.heartbeat_thread = threading.Thread(target=self.send_heartbeat)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

    def send_heartbeat(self):
        while not self.shutdown_flag and self.arduino != None:
            try:
                if self.serial_connected:
                    self.arduino.write(self.commands_dict["HEARTBEAT"].encode())
                    logging.info("Sent HEARTBEAT")
                    # self.last_heartbeat_time = time.time()
                time.sleep(4.5)  # Send heartbeat every 4.5 seconds
            except serial.SerialException as e:
                logging.error(f"Failed to send heartbeat: {e}")
                self.serial_connected = False

    def start_reading(self):
        self.reading_thread = threading.Thread(target=self.read_responses)
        self.reading_thread.daemon = True
        self.reading_thread.start()

    def read_responses(self):
        while not self.shutdown_flag and self.arduino != None:
            try:
                if self.serial_connected and self.arduino.in_waiting > 0:
                    response = self.arduino.readline().decode('utf-8').strip()
                    logging.info(f"Received: {response}")
                    self.process_response(response)
            except serial.SerialException as e:
                logging.error(f"Failed to read from Arduino: {e}")
                self.serial_connected = False
            if self.last_heartbeat_time + self.heartbeat_time < time.time():
                logging.error(
                    "No heartbeat received from Arduino. Stopping server.")
                self.stop()

    def process_response(self, response):
        # Process the response from Arduino
        if response == "HEARTBEAT_ACK":
            self.last_heartbeat_time = time.time()  # Update heartbeat time
            logging.info("Received HEARTBEAT_ACK")
        # Pressure reading - "P <pressure1> ... <valveState1> ... C"
        # Pressure values are in mbar, valve states are 0 or 1
        # P 1013 1014 1015 1 1 1 1 1 1 0 1 C
        elif response.startswith("P "):
            self.pressure_values = response.split(" ")[1:4] # Currently only 3 pressure values
            logging.info(f"Pressure reading: {self.pressure_values}")
            self.valve_states = response.split(" ")[4:-1]   # Currently only 8 valve states
            logging.info(f"Valve states: {self.valve_states}")
            # Set flag to indicate new reading available
            self.readings.append([*self.pressure_values, *self.valve_states])
            if len(self.readings) > 10:
                # Remove the oldest reading
                self.readings.pop(0)
            self.new_reading = True
        elif response.startswith("SEQ: "):  # Sequence loaded - "SEQ: <sequence>"
            if response.endswith("False"):
                self.sequence_loaded = False
                logging.info(f"Sequence loaded: {response.replace('SEQ: ', '')}")
            else:
                self.sequence_loaded = True
                logging.info(f"Sequence loaded: {response.replace('SEQ: ', '')}")
        elif response.startswith("LOG: "):  # Log message - "LOG <message>"
            log_message = response.replace("LOG: ", "")
            logging.info(f"Arduino: {log_message}")
        else:
            logging.warning(f"Unknown response: {response}")

    def stop(self):
        
        if self.arduino != None:
            self.send_command("RESET")
            self.arduino.close()
            self.arduino = None
        logging.info("Server stopped.")

        self.shutdown_flag = True

        # Join the reading thread to ensure it has finished
        if hasattr(self, 'reading_thread') and self.reading_thread.is_alive():
            self.reading_thread.join()

        # Join the heartbeat thread to ensure it has finished
        if hasattr(self, 'heartbeat_thread') and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join()

        # Join the pressure data thread to ensure it has finished
        if hasattr(self, 'pressure_data_thread') and self.pressure_data_thread.is_alive():
            self.pressure_data_thread.join()

    def save_pressure_data(self, save, filename):
        if save:
            if filename == "":  # If no filename specified, save in NMR Results folder with timestamp
                if not os.path.exists("C:\\NMR Results"):
                    os.makedirs("C:\\NMR Results")
                filename = os.path.join("C:\\NMR Results", f"pressure_data_{time.strftime('%Y%m%d-%H%M%S')}.csv")
            elif not filename.endswith(".csv"): # If filename doesn't end in .csv, add it
                filename = filename + ".csv"
            if os.path.dirname(filename) == "":  # If no location specified, save in NMR Results folder
                filename = os.path.join("C:\\NMR Results", filename)
            if not os.path.exists(os.path.dirname(filename)): # If location doesn't exist, create it
                os.makedirs(os.path.dirname(filename))
            self.pressure_data_filepath = filename
            self.save_pressure = True
            if not self.pressure_data_thread or not self.pressure_data_thread.is_alive():
                self.pressure_data_thread = threading.Thread(
                    target=self.read_pressure_data)
                self.pressure_data_thread.start()
            else:
                logging.error("Pressure data thread already running")
        else:
            self.save_pressure = False
            if self.pressure_data_thread and self.pressure_data_thread.is_alive():
                self.pressure_data_thread.join()

    def read_pressure_data(self):
        # Check if the file exists
        file_exists = os.path.isfile(self.pressure_data_filepath)

        if not file_exists:
            with open(self.pressure_data_filepath, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Time", "Pressure1", "Pressure2", "Pressure3", "ValveState1", "ValveState2",
                                "ValveState3", "ValveState4", "ValveState5", "ValveState6", "ValveState7", "ValveState8"])

        while self.save_pressure:
            if self.new_reading:
                with open(self.pressure_data_filepath, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(
                        [time.time(), *self.pressure_values, *self.valve_states])
                self.new_reading = False
            time.sleep(0.1)

    def get_pressure_values(self):
        return self.pressure_values

    def get_valve_states(self):
        return self.valve_states

    def send_command(self, command):
        if command in self.commands_dict:
            command = self.commands_dict[command]
        
        if self.serial_connected and self.arduino != None:
            if command in self.commands_dict.values():
                try:
                    self.arduino.write(command.encode())
                    logging.info(f"Sent command: {command}")
                except serial.SerialException as e:
                    logging.error(f"Failed to send command: {e}")
                    self.serial_connected = False
            else:
                logging.error("Invalid command - not a recognised command")
        else:
            logging.error("Cannot send command - not connected to Arduino")

    def get_auto_control(self):
        return self.auto_control
    
    def get_sequence_loaded(self):
        return self.sequence_loaded
    
    def get_recent_readings(self):
        return self.readings
    
    # Sequence e.g. b100n200d300b300 -- current max 9 "steps" in sequence
    def send_sequence(self, sequence):
        if not self.get_auto_control():
            logging.error("Cannot send sequence in manual mode")
            return
        if self.mode == 2:
            logging.error("Cannot send sequence in TTL mode")
            return
        if self.serial_connected and self.arduino != None:
            try:
                self.arduino.write(b'i')
                self.arduino.write(sequence.encode())
                self.arduino.write(b'\n')
                logging.info(f"Sent sequence: {sequence}")
            except serial.SerialException as e:
                logging.error(f"Failed to send sequence: {e}")
                self.serial_connected = False