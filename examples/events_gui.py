# type: ignore
"""PySide6 GUI example to display FreeWili events in real-time."""

import sys
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from freewili import FreeWili
from freewili.framing import ResponseFrame
from freewili.types import AccelData, BatteryData, ButtonData, EventType, GPIOData, IRData


class EventSignals(QObject):
    """Signals for thread-safe GUI updates."""

    accel_updated = Signal(AccelData)
    button_updated = Signal(ButtonData)
    ir_updated = Signal(IRData)
    battery_updated = Signal(BatteryData)
    gpio_updated = Signal(GPIOData)
    raw_event = Signal(str)


class FreeWiliEventsGUI(QMainWindow):
    """Main window for FreeWili events display."""

    def __init__(self):
        super().__init__()
        self.freewili = None
        self.event_timer = QTimer()
        self.signals = EventSignals()

        # Connect signals
        self.signals.accel_updated.connect(self.update_accel_display)
        self.signals.button_updated.connect(self.update_button_display)
        self.signals.ir_updated.connect(self.update_ir_display)
        self.signals.battery_updated.connect(self.update_battery_display)
        self.signals.gpio_updated.connect(self.update_gpio_display)
        self.signals.raw_event.connect(self.update_raw_events)

        self.setup_ui()
        self.setup_freewili()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("FreeWili Events Monitor")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Control buttons
        control_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        control_layout.addWidget(self.connect_btn)

        # Event enable checkboxes
        self.accel_cb = QCheckBox("Accelerometer")
        self.button_cb = QCheckBox("Buttons")
        self.ir_cb = QCheckBox("IR")
        self.battery_cb = QCheckBox("Battery")
        self.gpio_cb = QCheckBox("GPIO")

        for cb in [self.accel_cb, self.button_cb, self.ir_cb, self.battery_cb, self.gpio_cb]:
            cb.stateChanged.connect(self.update_event_subscriptions)
            control_layout.addWidget(cb)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        # Data display areas
        data_layout = QHBoxLayout()

        # Left column - Sensor data
        left_layout = QVBoxLayout()

        # Accelerometer group
        self.accel_group = self.create_accel_group()
        left_layout.addWidget(self.accel_group)

        # Battery group
        self.battery_group = self.create_battery_group()
        left_layout.addWidget(self.battery_group)

        data_layout.addLayout(left_layout)

        # Right column - Digital inputs
        right_layout = QVBoxLayout()

        # Button group
        self.button_group = self.create_button_group()
        right_layout.addWidget(self.button_group)

        # IR group
        self.ir_group = self.create_ir_group()
        right_layout.addWidget(self.ir_group)

        # GPIO group
        self.gpio_group = self.create_gpio_group()
        right_layout.addWidget(self.gpio_group)

        # Raw events log
        self.raw_events_group = self.create_raw_events_group()
        right_layout.addWidget(self.raw_events_group)

        data_layout.addLayout(right_layout)
        main_layout.addLayout(data_layout)

    def create_accel_group(self):
        """Create accelerometer data display group."""
        group = QGroupBox("Accelerometer")
        layout = QGridLayout(group)

        # Labels and value displays
        self.accel_labels = {}
        fields = [
            ("G-Force:", "g"),
            ("X:", "x"),
            ("Y:", "y"),
            ("Z:", "z"),
            ("Temp °C:", "temp_c"),
            ("Temp °F:", "temp_f"),
        ]

        for i, (label_text, key) in enumerate(fields):
            label = QLabel(label_text)
            value_label = QLabel("--")
            value_label.setStyleSheet("font-weight: bold; color: blue;")

            layout.addWidget(label, i, 0)
            layout.addWidget(value_label, i, 1)

            self.accel_labels[key] = value_label

        return group

    def create_battery_group(self):
        """Create battery data display group."""
        group = QGroupBox("Battery")
        layout = QGridLayout(group)

        self.battery_labels = {}
        fields = [
            ("VBUS:", "vbus"),
            ("VSYS:", "vsys"),
            ("VBATT:", "vbatt"),
            ("ICHG:", "ichg"),
            ("Charging:", "charging"),
            ("Complete:", "charge_complete"),
        ]

        for i, (label_text, key) in enumerate(fields):
            label = QLabel(label_text)
            value_label = QLabel("--")
            value_label.setStyleSheet("font-weight: bold; color: green;")

            layout.addWidget(label, i, 0)
            layout.addWidget(value_label, i, 1)

            self.battery_labels[key] = value_label

        return group

    def create_button_group(self):
        """Create button state display group."""
        group = QGroupBox("Buttons")
        layout = QGridLayout(group)

        self.button_labels = {}
        buttons = [("Gray:", "gray"), ("Yellow:", "yellow"), ("Green:", "green"), ("Blue:", "blue"), ("Red:", "red")]

        for i, (label_text, key) in enumerate(buttons):
            label = QLabel(label_text)
            value_label = QLabel("Released")
            value_label.setStyleSheet("font-weight: bold;")

            layout.addWidget(label, i, 0)
            layout.addWidget(value_label, i, 1)

            self.button_labels[key] = value_label

        return group

    def create_ir_group(self):
        """Create IR data display group."""
        group = QGroupBox("IR Data")
        layout = QVBoxLayout(group)

        self.ir_value_label = QLabel("No data")
        self.ir_value_label.setStyleSheet("font-weight: bold; color: purple; font-family: monospace;")
        layout.addWidget(self.ir_value_label)

        return group

    def create_gpio_group(self):
        """Create GPIO state display group."""
        group = QGroupBox("GPIO States")
        layout = QGridLayout(group)

        self.gpio_labels = {}

        # Get GPIO mappings from types.py
        from freewili.types import GPIO_MAP

        # Create labels for each GPIO pin
        row = 0
        for _gpio_num, gpio_name in GPIO_MAP.items():
            # Show just the GPIO number and main function
            display_name = gpio_name.replace("/", " / ")

            label = QLabel(f"{display_name}:")
            value_label = QLabel("--")
            value_label.setStyleSheet("font-weight: bold; font-family: monospace;")

            layout.addWidget(label, row, 0)
            layout.addWidget(value_label, row, 1)

            self.gpio_labels[gpio_name] = value_label
            row += 1

        return group

    def create_raw_events_group(self):
        """Create raw events log group."""
        group = QGroupBox("Raw Events Log")
        layout = QVBoxLayout(group)

        self.raw_events_text = QTextEdit()
        # self.raw_events_text.setMaximumHeight(150)
        self.raw_events_text.setStyleSheet("font-family: monospace; font-size: 10px;")
        layout.addWidget(self.raw_events_text)

        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.raw_events_text.clear)
        layout.addWidget(clear_btn)

        return group

    def setup_freewili(self):
        """Set up FreeWili connection and event processing."""
        self.event_timer.timeout.connect(self.process_events)
        self.event_timer.setInterval(50)  # Process events every 50ms

    def event_handler(self, event_type: EventType, frame: ResponseFrame, data: Any) -> None:
        """Handle events from FreeWili (runs in background thread)."""
        # Convert the data to the appropriate type and emit signals for thread-safe GUI updates
        try:
            if event_type == EventType.Accel and isinstance(data, AccelData):
                self.signals.accel_updated.emit(data)
            elif event_type == EventType.Button and isinstance(data, ButtonData):
                self.signals.button_updated.emit(data)
            elif event_type == EventType.IR and isinstance(data, IRData):
                self.signals.ir_updated.emit(data)
            elif event_type == EventType.Battery and isinstance(data, BatteryData):
                self.signals.battery_updated.emit(data)
            elif event_type == EventType.GPIO and isinstance(data, GPIOData):
                self.signals.gpio_updated.emit(data)

            # Also log to raw events
            self.signals.raw_event.emit(f"{event_type.name}: {data}")

        except Exception as e:
            self.signals.raw_event.emit(f"Error processing {event_type.name}: {e}")

    def update_accel_display(self, data: AccelData):
        """Update accelerometer display."""
        self.accel_labels["g"].setText(f"{data.g:.2f}g")
        self.accel_labels["x"].setText(f"{data.x:.1f}")
        self.accel_labels["y"].setText(f"{data.y:.1f}")
        self.accel_labels["z"].setText(f"{data.z:.1f}")
        self.accel_labels["temp_c"].setText(f"{data.temp_c:.1f}°C")
        self.accel_labels["temp_f"].setText(f"{data.temp_f:.1f}°F")

    def update_button_display(self, data: ButtonData):
        """Update button display."""
        buttons = {"gray": data.gray, "yellow": data.yellow, "green": data.green, "blue": data.blue, "red": data.red}

        for key, pressed in buttons.items():
            label = self.button_labels[key]
            if pressed:
                label.setText("PRESSED")
                label.setStyleSheet("font-weight: bold; color: green;")
            else:
                label.setText("Released")
                label.setStyleSheet("font-weight: bold; color: red;")

    def update_ir_display(self, data: IRData):
        """Update IR display."""
        hex_value = data.value.hex().upper()
        self.ir_value_label.setText(f"0x{hex_value}" if hex_value else "No data")

    def update_battery_display(self, data: BatteryData):
        """Update battery display."""
        self.battery_labels["vbus"].setText(f"{data.vbus:.1f}mV")
        self.battery_labels["vsys"].setText(f"{data.vsys:.1f}mV")
        self.battery_labels["vbatt"].setText(f"{data.vbatt:.1f}mV")
        self.battery_labels["ichg"].setText(f"{data.ichg}mA")
        self.battery_labels["charging"].setText("YES" if data.charging else "NO")
        self.battery_labels["charge_complete"].setText("YES" if data.charge_complete else "NO")

    def update_gpio_display(self, data: GPIOData):
        """Update GPIO display."""
        for gpio_name, value in data.pin.items():
            if gpio_name in self.gpio_labels:
                label = self.gpio_labels[gpio_name]
                if value == 1:
                    label.setText("HIGH")
                    label.setStyleSheet("font-weight: bold; color: red; font-family: monospace;")
                else:
                    label.setText("LOW")
                    label.setStyleSheet("font-weight: bold; color: blue; font-family: monospace;")

    def update_raw_events(self, event_text: str):
        """Update raw events log."""
        self.raw_events_text.append(event_text)

        # Keep log size manageable
        if self.raw_events_text.document().blockCount() > 100:
            cursor = self.raw_events_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # Remove the newline

    def toggle_connection(self):
        """Connect or disconnect from FreeWili."""
        if self.freewili is None:
            try:
                result = FreeWili.find_first()
                if result.is_err():
                    self.signals.raw_event.emit(f"Error: {result.unwrap_err()}")
                    return

                self.freewili = result.unwrap()
                self.freewili.set_event_callback(self.event_handler)

                # Open connection
                open_result = self.freewili.open()
                if open_result.is_err():
                    self.signals.raw_event.emit(f"Error opening connection: {open_result.unwrap_err()}")
                    self.freewili = None
                    return

                self.connect_btn.setText("Disconnect")
                self.event_timer.start()
                self.signals.raw_event.emit("Connected to FreeWili")

                # Enable default events
                self.accel_cb.setChecked(True)
                self.button_cb.setChecked(True)
                self.ir_cb.setChecked(True)
                self.battery_cb.setChecked(True)
                self.gpio_cb.setChecked(True)

            except Exception as e:
                self.signals.raw_event.emit(f"Connection error: {e}")

        else:
            # Disconnect
            self.event_timer.stop()

            # Disable all events
            for cb in [self.accel_cb, self.button_cb, self.ir_cb, self.battery_cb, self.gpio_cb]:
                cb.setChecked(False)

            if hasattr(self.freewili, "close"):
                self.freewili.close()

            self.freewili = None
            self.connect_btn.setText("Connect")
            self.signals.raw_event.emit("Disconnected from FreeWili")

    def update_event_subscriptions(self):
        """Update event subscriptions based on checkboxes."""
        if self.freewili is None:
            return

        try:
            # Update accelerometer events
            if self.accel_cb.isChecked():
                result = self.freewili.enable_accel_events(True, 100)
                if result.is_err():
                    self.signals.raw_event.emit(f"Error enabling accel: {result.unwrap_err()}")
            else:
                result = self.freewili.enable_accel_events(False)
                if result.is_err():
                    self.signals.raw_event.emit(f"Error disabling accel: {result.unwrap_err()}")

            # Update button events (assuming these methods exist)
            if hasattr(self.freewili, "enable_button_events"):
                if self.button_cb.isChecked():
                    result = self.freewili.enable_button_events(True, 100)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error enabling buttons: {result.unwrap_err()}")
                else:
                    result = self.freewili.enable_button_events(False)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error disabling buttons: {result.unwrap_err()}")

            # Update IR events
            if hasattr(self.freewili, "enable_ir_events"):
                if self.ir_cb.isChecked():
                    result = self.freewili.enable_ir_events(True)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error enabling IR: {result.unwrap_err()}")
                else:
                    result = self.freewili.enable_ir_events(False)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error disabling IR: {result.unwrap_err()}")

            # Update battery events
            if hasattr(self.freewili, "enable_battery_events"):
                if self.battery_cb.isChecked():
                    result = self.freewili.enable_battery_events(True)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error enabling battery: {result.unwrap_err()}")
                else:
                    result = self.freewili.enable_battery_events(False)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error disabling battery: {result.unwrap_err()}")

            # Update GPIO events
            if hasattr(self.freewili, "enable_gpio_events"):
                if self.gpio_cb.isChecked():
                    result = self.freewili.enable_gpio_events(True)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error enabling GPIO: {result.unwrap_err()}")
                else:
                    result = self.freewili.enable_gpio_events(False)
                    if result.is_err():
                        self.signals.raw_event.emit(f"Error disabling GPIO: {result.unwrap_err()}")

        except Exception as e:
            self.signals.raw_event.emit(f"Error updating subscriptions: {e}")

    def process_events(self):
        """Process FreeWili events (called by timer)."""
        if self.freewili:
            try:
                self.freewili.process_events()
            except Exception as e:
                self.signals.raw_event.emit(f"Event processing error: {e}")

    def closeEvent(self, event):  # noqa: N802
        """Handle window close event."""
        if self.freewili:
            self.toggle_connection()  # Disconnect cleanly
        event.accept()


def main():
    """Main function to run the GUI application."""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("FreeWili Events Monitor")
    app.setApplicationVersion("1.0")

    # Create and show the main window
    window = FreeWiliEventsGUI()
    window.show()

    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
