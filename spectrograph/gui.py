from collections import deque
import math
import sys
import time
import numpy as np
import pyqtgraph as pg
import serial.tools.list_ports
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QFrame, QSplitter, QSlider, QLineEdit, QCheckBox, QLabel, QSpacerItem, QSizePolicy, QMessageBox, QFileDialog
from PyQt5.QtGui import QDoubleValidator, QTransform
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from .datamodel import SAMPLING_RATE, AccelerometerData, ThreadPortReadout, project_x, project_xyz, project_y, project_z

def plasma_colormap(amplitude):
    return pg.ColorMap(
        pos=amplitude * np.array([
            0.0,
            0.14285714285714285,
            0.2857142857142857,
            0.42857142857142855,
            0.5714285714285714,
            0.7142857142857142,
            0.8571428571428571,
            1.0
        ]),
        color=np.array([
            [13, 8, 135],
            [84, 2, 163],
            [139, 10, 165],
            [185, 50, 137],
            [219, 92, 104],
            [244, 136, 73],
            [254, 188, 43],
            [240, 249, 33],
        ]))

class DivisionLineWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

class SliderInputWidget(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, min_val, max_val, resolution, default):
        super().__init__()

        self.min_val = min_val
        self.max_val = max_val
        self.resolution = resolution
        self.tracking = 0

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int((max_val - min_val) / resolution))
        self.slider.valueChanged.connect(self._slider_value_changed)

        self.value_input = QLineEdit()
        self.value_input.setValidator(QDoubleValidator(min_val, max_val, self._decimals))
        self.value_input.textChanged.connect(self._input_value_changed)

        layout = QVBoxLayout()
        layout.addWidget(self.slider)
        layout.addWidget(self.value_input)

        self.setLayout(layout)
        self.set_value(default)

    def set_tracking(self, value):
        self.tracking = value

    def move_to_max(self):
        self.slider.setValue(self.slider.maximum())
        self._slider_value_changed(self.slider.maximum())

    def set_range(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val
        update_to_max = self.tracking and self.slider.value() == self.slider.maximum()
        self.slider.setRange(0, int((max_val - min_val) / self.resolution))
        if update_to_max:
            self.slider.setValue(self.slider.maximum())
            self._slider_value_changed(self.slider.maximum())

    @property
    def _decimals(self):
        return -int(round(math.log10(self.resolution)))

    def _slider_value_changed(self, value):
        # Update the input field based on the slider value
        real_value = round(self.min_val + (value * self.resolution), self._decimals)
        formatted_value = f"{real_value:.{self._decimals}f}"
        self.value_input.setText(str(formatted_value))
        self.valueChanged.emit(real_value)

    def _input_value_changed(self, text):
        # Update the slider value based on the input field
        real_value = float(text)
        slider_value = int((real_value - self.min_val) / self.resolution)
        self.slider.setValue(slider_value)
        self.valueChanged.emit(real_value)

    def set_value(self, value):
        value = round(value, self._decimals)
        self.value_input.setText( f"{value:.{self._decimals}f}")
        self._input_value_changed(value)

    def get_value(self):
        return float(self.value_input.text())

class DataVisualizationWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.spectrogram = None
        self.spectrogram_args = None
        self.spectrogram_time_offset = 0
        self.spectrogram_start_point = 0
        self.spectrogram_last_time = 0

        self.layout = QVBoxLayout(self)

        # Create a splitter for adjusting the height of graph and spectrogram
        self.splitter = QSplitter(Qt.Vertical)

        self.graph_widget = pg.PlotWidget()
        self.graph_widget.showGrid(x=True, y=True)
        self.spectrum_plot = self.graph_widget.plot([], [], pen=pg.mkPen('r', width=1.5))
        self.v_line = pg.InfiniteLine(angle=90, movable=False)
        self.h_line = pg.InfiniteLine(angle=0, movable=False)
        self.graph_widget.addItem(self.v_line, ignoreBounds=True)
        self.graph_widget.addItem(self.h_line, ignoreBounds=True)
        self.crosshair_update = pg.SignalProxy(self.graph_widget.scene().sigMouseMoved, rateLimit=60, slot=self.update_crosshair)


        self.spectrogram_widget = pg.PlotWidget()
        self.spectrogram_img = pg.ImageItem()
        self.spectrogram_widget.addItem(self.spectrogram_img)
        self.spectrogram_v_line = pg.InfiniteLine(angle=90, movable=False)
        self.spectrogram_v_line.setPen((255, 255, 255), width=2)
        self.spectrogram_widget.addItem(self.spectrogram_v_line)

        # Align their X-axis
        self.spectrogram_widget.setXLink(self.graph_widget)

        # Add widgets to the splitter
        self.splitter.addWidget(self.graph_widget)
        self.splitter.addWidget(self.spectrogram_widget)

        # Create a slider for navigating back in time
        self.time_slider = SliderInputWidget(0, 0, 0.001, 0)
        self.time_slider.set_tracking(True)

        self.layout.addWidget(self.splitter)
        self.layout.addWidget(self.time_slider)  # Add the slider to the layout
        self.setLayout(self.layout)

    def update_crosshair(self, evt):
        pos = evt[0]
        if self.graph_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.graph_widget.plotItem.vb.mapSceneToView(pos)
            self.graph_widget.setTitle("<span style='font-size: 12pt'>Frekvence=%0.0f Hz, <span style='color: red'>Amplituda=%0.3f g</span>" % (mouse_point.x(), mouse_point.y()))
            self.v_line.setPos(mouse_point.x())
            self.h_line.setPos(mouse_point.y())
            self.spectrogram_v_line.setPos(mouse_point.x())

    def update_spectrum(self, sample_window, min_freq, max_freq, y_range,
               spectrogram_length, sample_projection, datasource):
        TIME_EPSILON = 0.05

        last_full_time = datasource.get_length()
        datasource.pull_samples()
        self.time_slider.set_range(0, datasource.get_length())
        if np.abs(self.time_slider.get_value() - last_full_time) < TIME_EPSILON:
            self.time_slider.set_value(datasource.get_length())

        time_point = self.time_slider.get_value()

        x, y = datasource.get_fft(
            time_point - sample_window - TIME_EPSILON,
            time_point - TIME_EPSILON,
            min_freq, max_freq, sample_projection)
        self.graph_widget.setYRange(0, y_range)
        self.graph_widget.setXRange(min_freq, max_freq)
        self.spectrum_plot.setData(x, y)

    def update_spectrogram(self, sample_window, min_freq, max_freq, y_range,
            spectrogram_length, sample_projection, datasource):
        DIVISION_FACTOR = 10

        time_offset = self.time_slider.get_value() - datasource.get_length()

        args = (sample_window, min_freq, max_freq, spectrogram_length, sample_projection)
        if args != self.spectrogram_args or np.abs(time_offset - self.spectrogram_time_offset) > 0.01:
            self.spectrogram_args = args
            self.spectrogram_time_offset = time_offset

            _, y = datasource.get_fft(0, sample_window, min_freq, max_freq, sample_projection)
            self.expected_samples = len(y)
            self.spectrogram = deque([np.full((self.expected_samples,), 0)
                for _ in range(int(spectrogram_length / sample_window * DIVISION_FACTOR))
            ], maxlen = int(DIVISION_FACTOR * spectrogram_length / sample_window))
            self.spectrogram_last_time = datasource.get_length() + self.spectrogram_time_offset - spectrogram_length

        steps_made = 0
        while True:
            start = self.spectrogram_last_time + sample_window * (1 / DIVISION_FACTOR)
            end = start + sample_window
            if end >= datasource.get_length() + self.spectrogram_time_offset:
                break

            if start < 0 and end < 0:
                self.spectrogram.append(np.full((self.expected_samples,), 0))
            else:
                _, y = datasource.get_fft(start, end, min_freq, max_freq, sample_projection)
                self.spectrogram.append(y)
                steps_made += 1

            self.spectrogram_last_time = start

            # Do not make the GUI responsive
            if steps_made > 300:
                break

        line_count = len(self.spectrogram)

        img = self.spectrogram_img
        img.setLevels([0, y_range], update=False)
        img.setColorMap(plasma_colormap(y_range))
        img.setImage(
            np.transpose(self.spectrogram),
            autoLevels=False)

        img.setTransform(QTransform()
            .scale(1, spectrogram_length / line_count)
            .translate(0, -line_count)
            .scale((max_freq - min_freq) / self.expected_samples, 1)
            .translate(min_freq, 0)
            )

        self.spectrogram_widget.setYRange(-spectrogram_length, 0)

    def on_readout_start(self):
        self.time_slider.move_to_max()

class ControlPanelWidget(QWidget):
    params_updated = pyqtSignal()
    recording_start = pyqtSignal(str)
    recording_stop = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.com_ports_combo = QComboBox()

        # Create button groups with fixed spacing between them
        connection_widget_group = QVBoxLayout()
        self.start_button = QPushButton("Začít nahrávat")
        self.stop_button = QPushButton("Zastavit nahrávání")
        self.stop_button.setDisabled(True)
        connection_widget_group.addWidget(self.com_ports_combo)
        connection_widget_group.addWidget(self.start_button)
        connection_widget_group.addWidget(self.stop_button)

        file_button_group = QVBoxLayout()
        self.load_button = QPushButton("Načíst ze souboru")
        self.save_button = QPushButton("Uložit do souboru")
        file_button_group.addWidget(self.load_button)
        file_button_group.addWidget(self.save_button)

        # Create controls for window size and spacing
        parameter_input_group = QVBoxLayout()
        parameter_input_group.addWidget(QLabel("Velikost vzorkovacího okna (s)"))
        self.window_size_input = SliderInputWidget(0.1, 3, 0.1, 1)
        self.window_size_input.valueChanged.connect(self.params_updated.emit)
        parameter_input_group.addWidget(self.window_size_input)

        # Create controls for min and max frequency
        parameter_input_group.addWidget(QLabel("Minimální frekvence"))
        self.min_freq_input = SliderInputWidget(0, 2000, 1, 0)
        self.min_freq_input.valueChanged.connect(self.params_updated.emit)
        parameter_input_group.addWidget(self.min_freq_input)
        parameter_input_group.addWidget(QLabel("Maximální frekvence:"))
        self.max_freq_input = SliderInputWidget(0, 2000, 1, 2000)
        self.max_freq_input.valueChanged.connect(self.params_updated.emit)
        parameter_input_group.addWidget(self.max_freq_input)
        parameter_input_group.addWidget(QLabel("Rozsah (g):"))
        self.range_input = SliderInputWidget(0, 2, 0.01, 0.1)
        self.range_input.valueChanged.connect(self.params_updated.emit)
        parameter_input_group.addWidget(self.range_input)
        parameter_input_group.addWidget(QLabel("Délka spektrogramu (s):"))
        self.length_input = SliderInputWidget(0, 300, 1, 20)
        self.length_input.valueChanged.connect(self.params_updated.emit)
        parameter_input_group.addWidget(self.length_input)

        # Create sample projection
        self.sample_projection_combo = QComboBox()
        self.sample_projection_combo.addItem("Analýza X + Y + Z")
        self.sample_projection_combo.addItem("Analýza X")
        self.sample_projection_combo.addItem("Analýza Y")
        self.sample_projection_combo.addItem("Analýza Z")
        parameter_input_group.addWidget(self.sample_projection_combo)

        # Add widgets to the layout
        self.layout.addLayout(connection_widget_group)
        self.layout.addWidget(DivisionLineWidget())
        self.layout.addLayout(file_button_group)
        self.layout.addWidget(DivisionLineWidget())
        self.layout.addLayout(parameter_input_group)
        self.layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.layout.setSpacing(20)
        self.setLayout(self.layout)

        # Create a timer to periodically refresh the COM port list every 2 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.populate_com_ports)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds

        # Initial population of COM port dropdown
        self.populate_com_ports()

        # Connect button click handlers
        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)

    def populate_com_ports(self):
        com_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_ports_combo.clear()
        self.com_ports_combo.addItems(com_ports)

    def start_recording(self):
        idx = self.com_ports_combo.currentIndex()
        if idx == -1:
            message_box = QMessageBox()
            message_box.setIcon(QMessageBox.Critical)
            message_box.setWindowTitle("Chyba")
            message_box.setText("Nebyl vybrán port")
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.exec_()
            return

        port = self.com_ports_combo.itemText(idx)
        self.start_button.setDisabled(True)
        self.stop_button.setDisabled(False)
        self.com_ports_combo.setDisabled(True)
        self.recording_start.emit(port)

        self.load_button.setDisabled(True)
        self.save_button.setDisabled(True)


    def stop_recording(self):
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
        self.com_ports_combo.setDisabled(False)
        self.load_button.setDisabled(False)
        self.save_button.setDisabled(False)
        self.recording_stop.emit()

    def get_selected_projection(self):
        projection_functions = [
            project_xyz,
            project_x,
            project_y,
            project_z
        ]
        return projection_functions[self.sample_projection_combo.currentIndex()]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.data = AccelerometerData()
        self.readout = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout(self.central_widget)
        self.splitter = QSplitter(Qt.Horizontal)  # Horizontal splitter for columns
        self.data_visualization_widget = DataVisualizationWidget()
        self.control_panel_widget = ControlPanelWidget()

        # Add widgets to the splitter
        self.splitter.addWidget(self.data_visualization_widget)
        self.splitter.addWidget(self.control_panel_widget)

        self.layout.addWidget(self.splitter)  # Add the splitter to the main layout
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle("Spectrogram")

        self.refresh_widget_timer = QTimer(self)
        self.refresh_widget_timer.timeout.connect(lambda:
            self.data_visualization_widget.update_spectrum(
                self.control_panel_widget.window_size_input.get_value(),
                self.control_panel_widget.min_freq_input.get_value(),
                self.control_panel_widget.max_freq_input.get_value(),
                self.control_panel_widget.range_input.get_value(),
                self.control_panel_widget.length_input.get_value(),
                self.control_panel_widget.get_selected_projection(),
                self.data
            ))
        self.refresh_widget_timer.start(50)

        self.refresh_spectrograph_timer = QTimer(self)
        self.refresh_spectrograph_timer.timeout.connect(lambda:
            self.data_visualization_widget.update_spectrogram(
                self.control_panel_widget.window_size_input.get_value(),
                self.control_panel_widget.min_freq_input.get_value(),
                self.control_panel_widget.max_freq_input.get_value(),
                self.control_panel_widget.range_input.get_value(),
                self.control_panel_widget.length_input.get_value(),
                self.control_panel_widget.get_selected_projection(),
                self.data
            ))
        self.refresh_spectrograph_timer.start(50)

        self.control_panel_widget.recording_start.connect(self.on_readout_start)
        self.control_panel_widget.recording_stop.connect(self.on_readout_stop)
        self.control_panel_widget.load_button.clicked.connect(self.load_trace)
        self.control_panel_widget.save_button.clicked.connect(self.save_trace)

    def on_readout_start(self, port):
        self.readout = ThreadPortReadout(port, self.data.push_sample)
        self.readout.start()
        self.data_visualization_widget.on_readout_start()

    def on_readout_stop(self):
        if self.readout is not None:
            self.readout.stop()

    def closeEvent(self, event):
        if self.readout is not None:
            self.readout.stop()

    def load_trace(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly

        file_path, _ = QFileDialog.getOpenFileName(self,
            "Náčíst záznam", "", "Záznam spektra (*.npy);;All Files(*)", options = options)

        if file_path:
            try:
                data = np.load(file_path)
                self.data.set_data(data)
            except Exception as e:
                message_box = QMessageBox()
                message_box.setIcon(QMessageBox.Critical)
                message_box.setWindowTitle("Chyba")
                message_box.setText(f"Nepodařilo se načíst soubor: {e}")
                message_box.setStandardButtons(QMessageBox.Ok)
                message_box.exec_()

    def save_trace(self):
        options = QFileDialog.Options()

        file_path, _ = QFileDialog.getSaveFileName(self,
            "Uložit záznam", "", "Záznam spektra (*.npy);;All Files(*)", options = options)
        if file_path:
            if not file_path.endswith(".npy"):
                file_path = file_path + ".npy"
            try:
                np.save(file_path, self.data.as_np())
            except Exception as e:
                message_box = QMessageBox()
                message_box.setIcon(QMessageBox.Critical)
                message_box.setWindowTitle("Chyba")
                message_box.setText(f"Nepodařilo se načíst soubor: {e}")
                message_box.setStandardButtons(QMessageBox.Ok)
                message_box.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
