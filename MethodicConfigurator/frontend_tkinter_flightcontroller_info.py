#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

#from logging import debug as logging_debug
from logging import info as logging_info

import tkinter as tk

from MethodicConfigurator.backend_flightcontroller import FlightController
#from MethodicConfigurator.backend_flightcontroller_info import BackendFlightcontrollerInfo

#from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import ProgressWindow
from MethodicConfigurator.frontend_tkinter_base import BaseWindow

from MethodicConfigurator.version import VERSION


class FlightControllerInfoWindow(BaseWindow):  # pylint: disable=too-few-public-methods
    """
    Display flight controller hardware, firmware and parameter information
    """
    def __init__(self, flight_controller: FlightController):
        super().__init__()
        self.root.title("ArduPilot methodic configurator " + VERSION + " - Flight Controller Info")
        self.root.geometry("500x350")  # Adjust the window size as needed
        self.flight_controller = flight_controller

        # Create a frame to hold all the labels and text fields
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(padx=20, pady=20)

        # Dictionary mapping attribute names to their descriptions
        attribute_descriptions = {
            "Vendor": "vendor",
            "Product": "product",
            "Hardware Version": "board_version",
            "Autopilot Type": "autopilot",
            "ArduPilot FW Type": "vehicle_type",
            "MAV Type": "mav_type",
            "Firmware Version": "flight_sw_version_and_type",
            "Git Hash": "flight_custom_version",
            "OS Git Hash": "os_custom_version",
            "Capabilities": "capabilities",
            "System ID": "system_id",
            "Component ID": "component_id"
        }

        # Dynamically create labels and text fields for each attribute
        for row_nr, (description, attr_name) in enumerate(attribute_descriptions.items()):
            label = tk.Label(self.info_frame, text=f"{description}:")
            label.grid(row=row_nr, column=0, sticky="w")

            text_field = tk.Entry(self.info_frame, width=60)
            text_field.grid(row=row_nr, column=1, sticky="w")

            # Check if the attribute exists and has a non-empty value before inserting
            attr_value = getattr(flight_controller.info, attr_name, "")
            if attr_value:
                if isinstance(attr_value, dict):
                    text_field.insert(tk.END, (", ").join(attr_value.keys()))
                else:
                    text_field.insert(tk.END, attr_value)
            else:
                text_field.insert(tk.END, "N/A")  # Insert "Not Available" if the attribute is missing or empty
            text_field.configure(state="readonly")

        logging_info("Firmware Version: %s", flight_controller.info.flight_sw_version_and_type)
        logging_info(f"Firmware first 8 hex bytes of the FC git hash: {flight_controller.info.flight_custom_version}")
        logging_info(f"Firmware first 8 hex bytes of the ChibiOS git hash: {flight_controller.info.os_custom_version}")
        logging_info(f"Flight Controller HW / board version: {flight_controller.info.board_version}")
        logging_info(f"Flight Controller USB vendor ID: {flight_controller.info.vendor}")
        logging_info(f"Flight Controller USB product ID: {flight_controller.info.product}")

        self.root.after(50, self.download_flight_controller_parameters()) # 50 milliseconds
        self.root.mainloop()

    def download_flight_controller_parameters(self):
        param_download_progress_window = ProgressWindow(self.root, "Downloading FC parameters",
                                                        "Downloaded {} of {} parameters")
        self.flight_controller.fc_parameters = self.flight_controller.download_params(
            param_download_progress_window.update_progress_bar)
        param_download_progress_window.destroy()  # for the case that '--device test' and there is no real FC connected
        self.root.destroy()
