#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

from argparse import ArgumentParser

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
# from logging import debug as logging_debug
#from logging import info as logging_info
from logging import error as logging_error

import tkinter as tk
from tkinter import ttk

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.backend_filesystem import LocalFilesystem

from MethodicConfigurator.backend_filesystem_vehicle_components import VehicleComponents

from MethodicConfigurator.battery_cell_voltages import BatteryCell

from MethodicConfigurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase

#from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import show_error_message

from MethodicConfigurator.version import VERSION


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='A GUI for editing JSON files that contain vehicle component configurations. '
                            'Not to be used directly, but through the main ArduPilot methodic configurator script.')
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ComponentEditorWindow.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


class VoltageTooLowError(Exception):
    """Raised when the voltage is below the minimum limit."""


class VoltageTooHighError(Exception):
    """Raised when the voltage is above the maximum limit."""

class ComponentEditorWindow(ComponentEditorWindowBase):
    """
    This class validates the user input and handles user interactions
    for editing component configurations in the ArduPilot Methodic Configurator.
    """
    def __init__(self, version, local_filesystem: LocalFilesystem=None):
        self.serial_ports = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
        self.can_ports = ["CAN1", "CAN2"]
        self.i2c_ports = ["I2C1", "I2C2", "I2C3", "I2C4"]
        ComponentEditorWindowBase.__init__(self, version, local_filesystem)

    def update_json_data(self):  # pylint: disable=too-many-branches, too-many-statements
        super().update_json_data()
        # To update old JSON files that do not have these new fields
        if 'Components' not in self.data:
            self.data['Components'] = {}
        if 'Battery' not in self.data['Components']:
            self.data['Components']['Battery'] = {}
        if 'Specifications' not in self.data['Components']['Battery']:
            self.data['Components']['Battery']['Specifications'] = {}
        if 'Chemistry' not in self.data['Components']['Battery']['Specifications']:
            self.data['Components']['Battery']['Specifications']['Chemistry'] = "Lipo"
        if 'Capacity mAh' not in self.data['Components']['Battery']['Specifications']:
            self.data['Components']['Battery']['Specifications']['Capacity mAh'] = 0

        # To update old JSON files that do not have these new fields
        if 'Frame' not in self.data['Components']:
            self.data['Components']['Frame'] = {}
        if 'Specifications' not in self.data['Components']['Frame']:
            self.data['Components']['Frame']['Specifications'] = {}
        if 'TOW min Kg' not in self.data['Components']['Frame']['Specifications']:
            self.data['Components']['Frame']['Specifications']['TOW min Kg'] = 1
        if 'TOW max Kg' not in self.data['Components']['Frame']['Specifications']:
            self.data['Components']['Frame']['Specifications']['TOW max Kg'] = 1

        # Older versions used receiver instead of Receiver, rename it for consistency with other fields
        if 'GNSS receiver' in self.data['Components']:
            self.data['Components']['GNSS Receiver'] = self.data['Components'].pop('GNSS receiver')

        self.data['Program version'] = VERSION

    def set_vehicle_type_and_version(self, vehicle_type: str, version: str):
        self._set_component_value_and_update_ui(('Flight Controller', 'Firmware', 'Type'), vehicle_type)
        if version:
            self._set_component_value_and_update_ui(('Flight Controller', 'Firmware', 'Version'), version)

    def set_fc_manufacturer(self, manufacturer: str):
        if manufacturer and manufacturer!= "Unknown" and manufacturer!= "ArduPilot":
            self._set_component_value_and_update_ui(('Flight Controller', 'Product', 'Manufacturer'), manufacturer)

    def set_fc_model(self, model: str):
        if model and model!= "Unknown" and model!= "MAVLink":
            self._set_component_value_and_update_ui(('Flight Controller', 'Product', 'Model'), model)

    @staticmethod
    def reverse_key_search(doc: dict, param_name: str, values: list, fallbacks: list) -> list:
        retv = [int(key) for key, value in doc[param_name]["values"].items() if value in values]
        if retv:
            return retv
        logging_error("No values found for %s in the metadata", param_name)
        return fallbacks

    def set_values_from_fc_parameters(self, fc_parameters: dict, doc: dict):
        self.set_protocol_and_connection_from_fc_parameters(fc_parameters, doc)
        self.set_motor_poles_from_fc_parameters(fc_parameters, doc)

    def set_protocol_and_connection_from_fc_parameters(self, fc_parameters: dict, doc: dict):
        rc_receiver_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL", ["RCIN"], [23])
        telemetry_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL",
                                                      ["MAVLink1", "MAVLink2", "MAVLink High Latency"], [1, 2, 43])
        gnss_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL", ["GPS"], [5])
        esc_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL",
                                                ["ESC Telemetry", "FETtecOneWire", "Torqeedo", "CoDevESC"],
                                                [16, 38, 39, 41])
        for serial in self.serial_ports:
            if serial + "_PROTOCOL" in fc_parameters:
                serial_protocol = fc_parameters[serial + "_PROTOCOL"]
                try:
                    serial_protocol = int(serial_protocol)
                except ValueError:
                    logging_error("Invalid non-integer value for %s_PROTOCOL %f", serial, serial_protocol)
                    serial_protocol = 0
                if serial_protocol in rc_receiver_protocols:
                    self.data['Components']['RC Receiver']['FC Connection']['Type'] = serial
                    #self.data['Components']['RC Receiver']['FC Connection']['Protocol'] = \
                    # doc['RC_PROTOCOLS']['values'][fc_parameters['RC_PROTOCOLS']] this is a Bitmask and not a value
                elif serial_protocol in telemetry_protocols:
                    self.data['Components']['Telemetry']['FC Connection']['Type'] = serial
                    self.data['Components']['Telemetry']['FC Connection']['Protocol'] = \
                        doc[serial + "_PROTOCOL"]['values'][str(serial_protocol)]
                elif serial_protocol in gnss_protocols:
                    self.data['Components']['GNSS Receiver']['FC Connection']['Type'] = serial
                    gps_type = fc_parameters['GPS_TYPE'] if "GPS_TYPE" in fc_parameters else 0
                    try:
                        gps_type = int(gps_type)
                    except ValueError:
                        logging_error("Invalid non-integer value for GPS_TYPE %f", gps_type)
                        gps_type = 0
                    self.data['Components']['GNSS Receiver']['FC Connection']['Protocol'] = \
                        doc['GPS_TYPE']['values'][str(gps_type)]
                elif serial_protocol in esc_protocols:
                    self.data['Components']['ESC']['FC Connection']['Type'] = serial
                    mot_pwm_type = fc_parameters['MOT_PWM_TYPE'] if "MOT_PWM_TYPE" in fc_parameters else 0
                    try:
                        mot_pwm_type = int(mot_pwm_type)
                    except ValueError:
                        logging_error("Invalid non-integer value for MOT_PWM_TYPE %f", mot_pwm_type)
                        mot_pwm_type = 0
                    self.data['Components']['ESC']['FC Connection']['Protocol'] = \
                        doc['MOT_PWM_TYPE']['values'][str(mot_pwm_type)]
        if "BATT_MONITOR" in fc_parameters and "BATT_MONITOR" in doc:
            batt_monitor = int(fc_parameters["BATT_MONITOR"])
            analog = [int(key) for key, value in doc["BATT_MONITOR"]["values"].items() \
                      if value in ['Analog Voltage Only', 'Analog Voltage and Current']]
            if batt_monitor in analog:
                self.data['Components']['Battery Monitor']['FC Connection']['Type'] = "Analog"
            self.data['Components']['Battery Monitor']['FC Connection']['Protocol'] = \
                doc['BATT_MONITOR']['values'][str(batt_monitor)]

    def set_motor_poles_from_fc_parameters(self, fc_parameters: dict, doc: dict):
        dshot_protocols = self.reverse_key_search(doc, "MOT_PWM_TYPE",
                                                  ["OneShot", "OneShot125", "DShot150", "DShot300", "DShot600", "DShot1200"],
                                                  [1, 2, 4, 5, 6, 7])
        if "MOT_PWM_TYPE" in fc_parameters and fc_parameters["MOT_PWM_TYPE"] in dshot_protocols:
            if "SERVO_BLH_POLES" in fc_parameters:
                self.data['Components']['Motors']['Specifications']['Poles'] = fc_parameters["SERVO_BLH_POLES"]
        else:
            if "SERVO_FTW_MASK" in fc_parameters and fc_parameters["SERVO_FTW_MASK"] and "SERVO_FTW_POLES" in fc_parameters:
                self.data['Components']['Motors']['Specifications']['Poles'] = fc_parameters["SERVO_FTW_POLES"]

    def add_entry_or_combobox(self, value, entry_frame, path):

        # Default values for comboboxes in case the apm.pdef.xml metadata is not available
        fallbacks = {
            'RC_PROTOCOLS': ["All", "PPM", "IBUS", "SBUS", "SBUS_NI", "DSM", "SUMD", "SRXL", "SRXL2",
                             "CRSF", "ST24", "FPORT", "FPORT2", "FastSBUS", "DroneCAN", "Ghost", "MAVRadio"],
            'BATT_MONITOR': ['Analog Voltage Only', 'Analog Voltage and Current', 'Solo', 'Bebop', 'SMBus-Generic',
                             'DroneCAN-BatteryInfo', 'ESC', 'Sum Of Selected Monitors', 'FuelFlow', 'FuelLevelPWM',
                             'SMBUS-SUI3', 'SMBUS-SUI6', 'NeoDesign', 'SMBus-Maxell', 'Generator-Elec', 'Generator-Fuel',
                             'Rotoye', 'MPPT', 'INA2XX', 'LTC2946', 'Torqeedo', 'FuelLevelAnalog',
                             'Synthetic Current and Analog Voltage', 'INA239_SPI', 'EFI', 'AD7091R5', 'Scripting'],
            'MOT_PWM_TYPE': ['Normal', 'OneShot', 'OneShot125', 'Brushed', 'DShot150', 'DShot300', 'DShot600',
                             'DShot1200', 'PWMRange', 'PWMAngle'],
            'GPS_TYPE': ['Auto', 'uBlox', 'NMEA', 'SiRF', 'HIL', 'SwiftNav', 'DroneCAN', 'SBF', 'GSOF', 'ERB',
                         'MAV', 'NOVA', 'HemisphereNMEA', 'uBlox-MovingBaseline-Base', 'uBlox-MovingBaseline-Rover',
                         'MSP', 'AllyStar', 'ExternalAHRS', 'Unicore', 'DroneCAN-MovingBaseline-Base',
                         'DroneCAN-MovingBaseline-Rover', 'UnicoreNMEA', 'UnicoreMovingBaselineNMEA', 'SBF-DualAntenna'],
        }
        def get_combobox_values(param_name: str) -> list:
            param_metadata = self.local_filesystem.doc_dict
            if param_name in param_metadata:
                if "values" in param_metadata[param_name] and param_metadata[param_name]["values"]:
                    return list(param_metadata[param_name]["values"].values())
                if "Bitmask" in param_metadata[param_name] and param_metadata[param_name]["Bitmask"]:
                    return list(param_metadata[param_name]["Bitmask"].values())
                logging_error("No values found for %s in the metadata", param_name)
            if param_name in fallbacks:
                return fallbacks[param_name]
            logging_error("No fallback values found for %s", param_name)
            return []

        combobox_config = {
            ('Flight Controller', 'Firmware', 'Type'): {
                "values": VehicleComponents.supported_vehicles(),
            },
            ('RC Receiver', 'FC Connection', 'Type'): {
                "values": ["RCin/SBUS"] + self.serial_ports + self.can_ports,
            },
            ('RC Receiver', 'FC Connection', 'Protocol'): {
                "values": get_combobox_values('RC_PROTOCOLS'),
            },
            ('Telemetry', 'FC Connection', 'Type'): {
                "values": self.serial_ports + self.can_ports,
            },
            ('Telemetry', 'FC Connection', 'Protocol'): {
                "values": ["MAVLink1", "MAVLink2", "MAVLink High Latency"],
            },
            ('Battery Monitor', 'FC Connection', 'Type'): {
                "values": ['Analog'] + self.i2c_ports + self.serial_ports + self.can_ports,
            },
            ('Battery Monitor', 'FC Connection', 'Protocol'): {
                "values": get_combobox_values('BATT_MONITOR'),
            },
            ('ESC', 'FC Connection', 'Type'): {
                "values": ['Main Out', 'AIO'] + self.serial_ports + self.can_ports,
            },
            ('ESC', 'FC Connection', 'Protocol'): {
                "values": get_combobox_values('MOT_PWM_TYPE')# + ['FETtecOneWire', 'Torqeedo', 'CoDevESC'],
            },
            ('GNSS Receiver', 'FC Connection', 'Type'): {
                "values": self.serial_ports + self.can_ports,
            },
            ('GNSS Receiver', 'FC Connection', 'Protocol'): {
                "values": get_combobox_values('GPS_TYPE'),
            },
            ('Battery', 'Specifications', 'Chemistry'): {
                "values": BatteryCell.chemistries(),
            },
        }
        config = combobox_config.get(path)
        if config:
            cb = ttk.Combobox(entry_frame, values=config["values"])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.bind("<KeyRelease>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb

        entry = ttk.Entry(entry_frame)
        validate_function = self.get_validate_function(entry, path)
        if validate_function:
            entry.bind("<FocusOut>", validate_function)
            entry.bind("<KeyRelease>", validate_function)
        entry.insert(0, str(value))
        return entry

    def get_validate_function(self, entry, path):
        validate_functions = {
            ('Frame', 'Specifications', 'TOW min Kg'): lambda event, entry=entry, path=path:
                self.validate_entry_limits(event, entry, float, (0.01, 600), "Takeoff Weight", path),

            ('Frame', 'Specifications', 'TOW max Kg'): lambda event, entry=entry, path=path:
                self.validate_entry_limits(event, entry, float, (0.01, 600), "Takeoff Weight", path),

            ('Battery', 'Specifications', 'Volt per cell max'): lambda event, entry=entry, path=path:
                self.validate_cell_voltage(event, entry, path),

            ('Battery', 'Specifications', 'Volt per cell low'): lambda event, entry=entry, path=path:
                self.validate_cell_voltage(event, entry, path),

            ('Battery', 'Specifications', 'Volt per cell crit'): lambda event, entry=entry, path=path:
                self.validate_cell_voltage(event, entry, path),

            ('Battery', 'Specifications', 'Number of cells'): lambda event, entry=entry, path=path:
                self.validate_entry_limits(event, entry, int, (1, 50), "Nr of cells", path),

            ('Battery', 'Specifications', 'Capacity mAh'): lambda event, entry=entry, path=path:
                self.validate_entry_limits(event, entry, int, (100, 1000000), "mAh capacity", path),

            ('Motors', 'Specifications', 'Poles'): lambda event, entry=entry, path=path:
                self.validate_entry_limits(event, entry, int, (3, 50), "Motor Poles", path),

            ('Propellers', 'Specifications', 'Diameter_inches'): lambda event, entry=entry, path=path:
                self.validate_entry_limits(event, entry, float, (0.3, 400), "Propeller Diameter", path),

        }
        return validate_functions.get(path, None)

    def validate_combobox(self, event, path) -> bool:
        """
        Validates the value of a combobox.
        """
        combobox = event.widget # Get the combobox widget that triggered the event
        value = combobox.get() # Get the current value of the combobox
        allowed_values = combobox.cget("values") # Get the list of allowed values

        if value not in allowed_values:
            if event.type == "10": # FocusOut events
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                   f"Allowed values are: {', '.join(allowed_values)}")
            combobox.configure(style="comb_input_invalid.TCombobox")
            return False
        combobox.configure(style="comb_input_valid.TCombobox")
        return True

    def validate_entry_limits(self, event, entry, data_type, limits, name, path):  # pylint: disable=too-many-arguments
        is_focusout_event = event and event.type == "10"
        try:
            value = entry.get()  # make sure value is defined to prevent exception in the except block
            value = data_type(value)
            if value < limits[0] or value > limits[1]:
                entry.configure(style="entry_input_invalid.TEntry")
                raise ValueError(f"{name} must be a {data_type.__name__} between {limits[0]} and {limits[1]}")
        except ValueError as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n{e}")
            return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def validate_cell_voltage(self, event, entry, path):  # pylint: disable=too-many-branches
        """
        Validates the value of a battery cell voltage entry.
        """
        chemistry_path = ('Battery', 'Specifications', 'Chemistry')
        if chemistry_path not in self.entry_widgets:
            show_error_message("Error", "Battery Chemistry not set. Will default to Lipo.")
            chemistry = "Lipo"
        else:
            chemistry = self.entry_widgets[chemistry_path].get()
        value = entry.get()
        is_focusout_event = event and event.type == "10"
        try:
            voltage = float(value)
            if voltage < BatteryCell.limit_min_voltage(chemistry):
                if is_focusout_event:
                    entry.delete(0, tk.END)
                    entry.insert(0, BatteryCell.limit_min_voltage(chemistry))
                raise VoltageTooLowError(f"is below the {chemistry} minimum limit of "
                                         f"{BatteryCell.limit_min_voltage(chemistry)}")
            if voltage > BatteryCell.limit_max_voltage(chemistry):
                if is_focusout_event:
                    entry.delete(0, tk.END)
                    entry.insert(0, BatteryCell.limit_max_voltage(chemistry))
                raise VoltageTooHighError(f"is above the {chemistry} maximum limit of "
                                          f"{BatteryCell.limit_max_voltage(chemistry)}")
        except (VoltageTooLowError, VoltageTooHighError) as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                   f"{e}")
            else:
                entry.configure(style="entry_input_invalid.TEntry")
                return False
        except ValueError as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                f"{e}\nWill be set to the recommended value.")
                entry.delete(0, tk.END)
                if path[-1] == "Volt per cell max":
                    entry.insert(0, str(BatteryCell.recommended_max_voltage(chemistry)))
                elif path[-1] == "Volt per cell low":
                    entry.insert(0, str(BatteryCell.recommended_low_voltage(chemistry)))
                elif path[-1] == "Volt per cell crit":
                    entry.insert(0, str(BatteryCell.recommended_crit_voltage(chemistry)))
                else:
                    entry.insert(0, "3.8")
            else:
                entry.configure(style="entry_input_invalid.TEntry")
                return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def save_data(self):
        if self.validate_data():
            ComponentEditorWindowBase.save_data(self)

    def validate_data(self):  # pylint: disable=too-many-branches
        invalid_values = False
        duplicated_connections = False
        fc_serial_connection = {}

        for path, entry in self.entry_widgets.items():
            value = entry.get()

            if isinstance(entry, ttk.Combobox):
                if value not in entry.cget("values"):
                    show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                    f"Allowed values are: {', '.join(entry.cget('values'))}")
                    entry.configure(style="comb_input_invalid.TCombobox")
                    invalid_values = True
                    continue
                if 'FC Connection' in path and 'Type' in path:
                    if value in fc_serial_connection and value not in ["CAN1", "CAN2", "I2C1", "I2C2", "I2C3", "I2C4"]:
                        if path[0] in ['Telemetry', 'RC Receiver'] and \
                           fc_serial_connection[value] in ['Telemetry', 'RC Receiver']:
                            entry.configure(style="comb_input_valid.TCombobox")
                            continue  # Allow telemetry and RC Receiver connections using the same SERIAL port
                        show_error_message("Error", f"Duplicate FC connection type '{value}' for {'>'.join(list(path))}")
                        entry.configure(style="comb_input_invalid.TCombobox")
                        duplicated_connections = True
                        continue
                    fc_serial_connection[value] = path[0]
                entry.configure(style="comb_input_valid.TCombobox")

            validate_function = self.get_validate_function(entry, path)
            if validate_function:
                mock_focus_out_event = type('', (), {'type': '10'})()
                if not validate_function(mock_focus_out_event):
                    invalid_values = True
            if path in [('Battery', 'Specifications', 'Volt per cell max'), ('Battery', 'Specifications', 'Volt per cell low'),
                        ('Battery', 'Specifications', 'Volt per cell crit')]:
                if not self.validate_cell_voltage(None, entry, path):
                    invalid_values = True
            if path == ('Battery', 'Specifications', 'Volt per cell low'):
                if value >= self.entry_widgets[('Battery', 'Specifications', 'Volt per cell max')].get():
                    show_error_message("Error", "Battery Cell Low voltage must be lower than max voltage")
                    entry.configure(style="entry_input_invalid.TEntry")
                    invalid_values = True
            if path == ('Battery', 'Specifications', 'Volt per cell crit'):
                if value >= self.entry_widgets[('Battery', 'Specifications', 'Volt per cell low')].get():
                    show_error_message("Error", "Battery Cell Crit voltage must be lower than low voltage")
                    entry.configure(style="entry_input_invalid.TEntry")
                    invalid_values = True

        return not (invalid_values or duplicated_connections)


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type, None, args.allow_editing_template_files)
    app = ComponentEditorWindow(VERSION, filesystem)
    app.root.mainloop()
