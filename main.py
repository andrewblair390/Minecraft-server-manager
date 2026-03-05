import sys
import os
import subprocess
import threading
import shutil
import html
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit,
    QLineEdit, QLabel, QPushButton, QCheckBox
)
from PySide6.QtCore import Signal, QObject

# -------------------------------
# Server Manager
# -------------------------------
class ServerManager(QObject):
    log_signal = Signal(str)
    status_signal = Signal(str)

    def __init__(self, jar_name="server.jar"):
        super().__init__()
        self.process = None
        self.jar_name = jar_name
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.current_status = "OFFLINE"

    def start_server(self):
        # Check Java
        if shutil.which("java") is None:
            self.log_signal.emit("ERROR: Java not found. Install Java 17+ and add to PATH.")
            self.status_signal.emit("OFFLINE")
            return

        # Check jar file
        jar_path = os.path.join(self.base_dir, self.jar_name)
        if not os.path.isfile(jar_path):
            self.log_signal.emit(f"ERROR: {self.jar_name} not found in {self.base_dir}")
            self.status_signal.emit("OFFLINE")
            return

        self.log_signal.emit("Starting server...")
        self.status_signal.emit("STARTING")
        self.current_status = "STARTING"

        try:
            self.process = subprocess.Popen(
                ["java", "-jar", self.jar_name, "nogui"],
                cwd=self.base_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except FileNotFoundError:
            self.log_signal.emit("ERROR: Could not launch Java process!")
            self.status_signal.emit("OFFLINE")
            self.current_status = "OFFLINE"
            return

        # Start background threads
        threading.Thread(target=self.read_output, daemon=True).start()
        threading.Thread(target=self.monitor_process, daemon=True).start()

    def stop_server(self):
        if self.process and self.process.poll() is None:
            self.send_command("stop")

    def read_output(self):
        for line in self.process.stdout:
            text = line.rstrip()
            self.log_signal.emit(text)

            # Detect server fully started
            if "Done (" in text and ")! For help" in text:
                self.status_signal.emit("RUNNING")
                self.current_status = "RUNNING"

    def monitor_process(self):
        self.process.wait()
        self.status_signal.emit("OFFLINE")
        self.current_status = "OFFLINE"
        self.log_signal.emit("Server process has stopped.")

    def send_command(self, cmd):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
            except Exception as e:
                self.log_signal.emit(f"ERROR sending command: {e}")

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def is_ready(self):
        return self.current_status == "RUNNING"

# -------------------------------
# GUI
# -------------------------------
class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft Server Manager")
        self.resize(800, 600)

        # -------------------------------
        # Layout
        # -------------------------------
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # -------------------------------
        # Server Manager
        # -------------------------------
        self.server = ServerManager()
        self.server.log_signal.connect(self.append_log)
        self.server.status_signal.connect(self.update_status)

        # -------------------------------
        # Server status label
        # -------------------------------
        self.status_label = QLabel("Server: OFFLINE")
        self.layout.addWidget(self.status_label)

        # -------------------------------
        # Console
        # -------------------------------
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.layout.addWidget(self.console)

        # -------------------------------
        # Command input
        # -------------------------------
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter command and press Enter")
        self.input.returnPressed.connect(self.send_command)
        self.layout.addWidget(self.input)

        # -------------------------------
        # Start/Stop button
        # -------------------------------
        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.toggle_server)
        self.layout.addWidget(self.start_button)

        # -------------------------------
        # Auto-restart checkbox
        # -------------------------------
        self.auto_restart_checkbox = QCheckBox("Auto-restart if server stops")
        self.layout.addWidget(self.auto_restart_checkbox)

    # -------------------------------
    # Start / Stop logic
    # -------------------------------
    def toggle_server(self):
        if self.server.is_ready() or self.server.is_running():
            self.server.stop_server()
        else:
            self.server.start_server()

    # -------------------------------
    # Append log with color support
    # -------------------------------
    def append_log(self, text):
        color = "white"
        if "[INFO]" in text:
            color = "blue"
        elif "[WARN]" in text:
            color = "orange"
        elif "[ERROR]" in text or "ERROR" in text:
            color = "red"
        elif "Done (" in text and ")! For help" in text:
            color = "green"
        elif "joined the game" in text:
            color = "purple"
        elif "left the game" in text:
            color = "gray"

        safe_text = html.escape(text)
        self.console.append(f'<span style="color:{color}">{safe_text}</span>')
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    # -------------------------------
    # Update server status & button text
    # -------------------------------
    def update_status(self, status):
        self.server.current_status = status
        color = {"OFFLINE": "red", "STARTING": "orange", "RUNNING": "green"}.get(status, "black")
        self.status_label.setText(f"Server: {status}")
        self.status_label.setStyleSheet(f"color: {color}")

        # Update start/stop button dynamically
        if status == "RUNNING":
            self.start_button.setText("Stop Server")
        else:
            self.start_button.setText("Start Server")

        # Auto-restart if checked
        if status == "OFFLINE" and self.auto_restart_checkbox.isChecked():
            self.append_log("Auto-restart enabled: starting server...")
            self.server.start_server()

    # -------------------------------
    # Send command from input
    # -------------------------------
    def send_command(self):
        cmd = self.input.text().strip()
        if cmd:
            self.server.send_command(cmd)
            self.input.clear()

# -------------------------------
# Entry point
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
