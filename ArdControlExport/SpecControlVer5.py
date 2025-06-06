import matplotlib.pyplot as plt
import json
import csv
import random
import threading
import time
import matplotlib
import logging
import sys
from PyQt6 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from motorController import MotorController
from arduinoController import ArduinoController
from pathlib import Path
import os
os.environ['MPLCONFIGDIR'] = str(Path.home())+"/.matplotlib/"
matplotlib.use('QtAgg')


class Ui_MainWindow(object):
    # creates the GUI for the main window
    def setupUi(self, MainWindow):

        # Initialise variables

        # how frequently the valve states are checked (ms)
        self.valveCheckInterval = 100

        # List of valve settings for each step type
        self.valve_settings = {
            'd': [0, 0, 0, 0, 0, 2, 2, 2],
            'n': [1, 1, 1, 1, 1, 2, 2, 2],
            'e': [0, 0, 0, 0, 0, 2, 2, 2],
            'b': [2, 1, 1, 1, 0, 2, 2, 2],
            's': [2, 2, 2, 0, 0, 2, 2, 2],
            'h': [2, 0, 0, 0, 0, 2, 2, 2]
        }
        # list of programmed step types + recognisable name for the GUI
        self.step_types = {
            'd': 'Depressurise',
            'n': 'Nitrogen',
            'e': 'Evacuate',
            'b': 'Bubble',
            's': 'Sleep',
            'h': 'Hold Bubble'
        }

        # List of valve settings for each macro
        self.macro_settings = {
            "1": {
                "Label": "Macro 1",
                "Valves": [1, 1, 1, 1, 1, 2, 2, 2],
                "Timer": 1.0
            },
            "2": {
                "Label": "Macro 2",
                "Valves": [0, 0, 0, 0, 0, 2, 2, 2],
                "Timer": 1.0
            },
            "3": {
                "Label": "Macro 3",
                "Valves": [1, 1, 1, 1, 1, 2, 2, 2],
                "Timer": 1.0
            },
            "4": {
                "Label": "Macro 4",
                "Valves": [0, 0, 0, 0, 0, 2, 2, 2],
                "Timer": 1.0
            }
        }

        self.motor_macro_settings = {
            "1": {
                "Label": "Motor Macro 1",
                "Position": 0
            },
            "2": {
                "Label": "Motor Macro 2",
                "Position": 0
            },
            "3": {
                "Label": "Motor Macro 3",
                "Position": 0
            },
            "4": {
                "Label": "Motor Macro 4",
                "Position": 0
            }
        }

        # Initialise the prev valve states
        self.previous_valve_states = [0, 0, 0, 0, 0, 2, 2, 2]

        self.macro_editor = ValveMacroEditor(self)
        self.macro_editor.load_data()
        self.macro_settings = self.macro_editor.get_macro_data_dict()

        self.motor_macro_editor = MotorMacroEditor(self)
        self.motor_macro_editor.load_data()
        self.motor_macro_settings = self.motor_macro_editor.get_macro_data_dict()

        self.motor_connected = False

        self.vent_flag = False

        # Show debug logs
        self.verbosity = False

        # Bool to track arduino connection
        self.ardConnected = False

        # Variable to track valve arduino running mode
        self.selectedMode = None

        # Bool to track pressure reading saving
        self.saving = False

        # Default save path
        self.default_save_path = os.path.join("C:\\", "ssbubble")

        # Array for storing sequence steps
        self.steps = []

        # Watchdog gets activated when valve arduino is connected and updates the connection status
        self.watchdog = None

        # Array for keeping track of valve states
        self.valveStates = [0, 0, 0, 0, 0, 0, 0, 0]

        # QTimer for updating the sequence step and time display
        self.stepTimer = QtCore.QTimer()
        self.stepTimer.setSingleShot(False)
        self.stepTimer.timeout.connect(self.update_step)

        self.bubbleTimer = QtCore.QTimer()
        self.bubbleTimer.setSingleShot(True)
        self.bubbleTimer.timeout.connect(self.bubble_timeout)

        # Bool that avoids "Step complete" message on sequence init
        self.seq_new = True

        # Ensure the prospa file is removed - prospa must be activated once gui already open
        # self.delete_sequence_file()

        """Create UI Widgets"""
        # Create the main window
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1050, 680)
        MainWindow.setFixedSize(1050, 680)

        # Create the central widget
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # Create the layout widgets
        self.verticalLayoutWidget = QtWidgets.QWidget(
            parent=self.centralwidget)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 10, 181, 291))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")

        # Create the layout
        self.ardConnectLayout = QtWidgets.QVBoxLayout(
            self.verticalLayoutWidget)
        self.ardConnectLayout.setContentsMargins(0, 0, 0, 0)
        self.ardConnectLayout.setObjectName("ardConnectLayout")

        # Create the COM port label
        self.ardCOMPortLabel = QtWidgets.QLabel(
            parent=self.verticalLayoutWidget)
        self.ardCOMPortLabel.setEnabled(True)
        font = QtGui.QFont()
        font.setPointSize(15)
        self.ardCOMPortLabel.setFont(font)
        self.ardCOMPortLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.ardCOMPortLabel.setObjectName("ardCOMPortLabel")
        self.ardConnectLayout.addWidget(self.ardCOMPortLabel)

        # Create the COM port spin box
        self.ardCOMPortSpinBox = QtWidgets.QSpinBox(
            parent=self.verticalLayoutWidget)
        self.ardCOMPortSpinBox.setMinimumSize(QtCore.QSize(0, 24))
        font = QtGui.QFont()
        font.setPointSize(11)
        self.ardCOMPortSpinBox.setFont(font)
        self.ardCOMPortSpinBox.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTrailing | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.ardCOMPortSpinBox.setObjectName("ardCOMPortSpinBox")
        self.ardConnectLayout.addWidget(self.ardCOMPortSpinBox)
        self.ardCOMPortSpinBox.setMaximum(255)
        self.ardCOMPortSpinBox.setMinimum(0)
        self.ardCOMPortSpinBox.setValue(7)

        # Create the warning label
        self.ardWarningLabel = QtWidgets.QLabel(
            parent=self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.ardWarningLabel.setFont(font)
        self.ardWarningLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.ardWarningLabel.setObjectName("ardWarningLabel")
        self.ardConnectLayout.addWidget(self.ardWarningLabel)

        # Create the radio buttons
        self.autoConnectRadioButton = QtWidgets.QRadioButton(
            parent=self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.autoConnectRadioButton.setFont(font)
        self.autoConnectRadioButton.setObjectName("autoConnectRadioButton")
        self.ardConnectLayout.addWidget(
            self.autoConnectRadioButton, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.TTLRadioButton = QtWidgets.QRadioButton(
            parent=self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.TTLRadioButton.setFont(font)
        self.TTLRadioButton.setObjectName("TTLRadioButton")
        self.ardConnectLayout.addWidget(
            self.TTLRadioButton, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.manualRadioButton = QtWidgets.QRadioButton(
            parent=self.verticalLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.manualRadioButton.setFont(font)
        self.manualRadioButton.setObjectName("manualRadioButton")
        self.ardConnectLayout.addWidget(
            self.manualRadioButton, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        # Create the button group, this should make radio buttons exclusive
        self.ardConnectButtonGroup = QtWidgets.QButtonGroup(MainWindow)
        self.ardConnectButtonGroup.addButton(self.autoConnectRadioButton)
        self.ardConnectButtonGroup.addButton(self.TTLRadioButton)
        self.ardConnectButtonGroup.addButton(self.manualRadioButton)

        # Create the connect button
        self.ardConnectButton = QtWidgets.QPushButton(
            parent=self.verticalLayoutWidget)
        self.ardConnectButton.setMinimumSize(QtCore.QSize(0, 70))
        font = QtGui.QFont()
        font.setPointSize(18)
        self.ardConnectButton.setFont(font)
        self.ardConnectButton.setObjectName("ardConnectButton")
        self.ardConnectLayout.addWidget(self.ardConnectButton)

        # Create the feedback text box
        self.textBrowser = QtWidgets.QTextBrowser(parent=self.centralwidget)
        self.textBrowser.setGeometry(QtCore.QRect(200, 10, 321, 291))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.textBrowser.setFont(font)
        self.textBrowser.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.textBrowser.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.textBrowser.setObjectName("textBrowser")

        # Create a dividing line
        self.line = QtWidgets.QFrame(parent=self.centralwidget)
        self.line.setGeometry(QtCore.QRect(10, 300, 1000, 20))
        self.line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.line.setObjectName("line")

        # Create the valve layout
        self.gridLayoutWidget = QtWidgets.QWidget(parent=self.centralwidget)
        self.gridLayoutWidget.setGeometry(QtCore.QRect(10, 320, 96, 294))
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.valveLayout = QtWidgets.QGridLayout(self.gridLayoutWidget)
        self.valveLayout.setContentsMargins(0, 0, 0, 0)
        self.valveLayout.setObjectName("valveLayout")

        # Create the valve buttons
        self.Valve2Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve2Button.setMinimumSize(QtCore.QSize(0, 30))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.Valve2Button.setFont(font)
        self.Valve2Button.setObjectName("Valve2Button")
        self.valveLayout.addWidget(self.Valve2Button, 3, 0, 1, 1)
        '''
        self.Valve7Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve7Button.setMinimumSize(QtCore.QSize(0, 50))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.Valve7Button.setFont(font)
        self.Valve7Button.setObjectName("Valve7Button")
        self.valveLayout.addWidget(self.Valve7Button, 5, 0, 1, 1)

        self.Valve6Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve6Button.setMinimumSize(QtCore.QSize(0, 50))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.Valve6Button.setFont(font)
        self.Valve6Button.setObjectName("Valve6Button")
        self.valveLayout.addWidget(self.Valve6Button, 4, 1, 1, 1)
        '''
        self.Valve1Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve1Button.setMinimumSize(QtCore.QSize(0, 30))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.Valve1Button.setFont(font)
        self.Valve1Button.setObjectName("Valve1Button")
        self.valveLayout.addWidget(self.Valve1Button, 2, 0, 1, 1)
        self.Valve4Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve4Button.setMinimumSize(QtCore.QSize(0, 30))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.Valve4Button.setFont(font)
        self.Valve4Button.setObjectName("Valve4Button")
        self.valveLayout.addWidget(self.Valve4Button, 5, 0, 1, 1)
        self.Valve3Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve3Button.setMinimumSize(QtCore.QSize(0, 30))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.Valve3Button.setFont(font)
        self.Valve3Button.setObjectName("Valve3Button")
        self.valveLayout.addWidget(self.Valve3Button, 4, 0, 1, 1)
        '''
        self.Valve8Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve8Button.setMinimumSize(QtCore.QSize(0, 50))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.Valve8Button.setFont(font)
        self.Valve8Button.setObjectName("Valve8Button")
        self.valveLayout.addWidget(self.Valve8Button, 5, 1, 1, 1)
        '''
        self.Valve5Button = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.Valve5Button.setMinimumSize(QtCore.QSize(0, 30))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.Valve5Button.setFont(font)
        self.Valve5Button.setObjectName("Valve5Button")
        self.valveLayout.addWidget(self.Valve5Button, 6, 0, 1, 1)
        self.Valve1Button.setCheckable(True)
        self.Valve2Button.setCheckable(True)
        self.Valve3Button.setCheckable(True)
        self.Valve4Button.setCheckable(True)
        self.Valve5Button.setCheckable(True)
        # self.Valve6Button.setCheckable(True)
        # self.Valve7Button.setCheckable(True)
        # self.Valve8Button.setCheckable(True)

        # Create the valve label and checkbox
        self.ValveLabel = QtWidgets.QLabel(parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(12)
        self.ValveLabel.setFont(font)
        self.ValveLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.ValveLabel.setObjectName("ValveLabel")
        self.valveLayout.addWidget(self.ValveLabel, 0, 0, 1, 1)

        self.devValveCheckbox = QtWidgets.QCheckBox(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.devValveCheckbox.setFont(font)
        self.devValveCheckbox.setTristate(False)
        self.devValveCheckbox.setObjectName("devValveCheckbox")
        self.devValveCheckbox.setChecked(False)
        self.devValveCheckbox.setText("Enable\nControls")
        self.valveLayout.addWidget(
            self.devValveCheckbox, 1, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.showValvesCheckbox = QtWidgets.QCheckBox(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.showValvesCheckbox.setFont(font)
        self.showValvesCheckbox.setTristate(False)
        self.showValvesCheckbox.setObjectName("showValvesCheckbox")
        self.valveLayout.addWidget(
            self.showValvesCheckbox, 7, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.resetButton = QtWidgets.QPushButton(parent=self.gridLayoutWidget)
        self.resetButton.setMinimumSize(QtCore.QSize(0, 30))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.resetButton.setFont(font)
        self.resetButton.setObjectName("resetButton")
        self.valveLayout.addWidget(self.resetButton, 8, 0, 1, 1)

        self.currentStepTypeLabel = QtWidgets.QLabel(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.currentStepTypeLabel.setFont(font)
        self.currentStepTypeLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.currentStepTypeLabel.setObjectName("currentStepLabel")
        self.valveLayout.addWidget(self.currentStepTypeLabel, 1, 0, 1, 1)

        self.currentStepTypeEdit = QtWidgets.QLineEdit(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.currentStepTypeEdit.setFont(font)
        self.currentStepTypeEdit.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.currentStepTypeEdit.setObjectName("currentStepTypeEdit")
        self.currentStepTypeEdit.setReadOnly(True)
        self.currentStepTypeEdit.setMaximumWidth(100)
        self.valveLayout.addWidget(self.currentStepTypeEdit, 2, 0, 1, 1)

        self.currentStepTimeLabel = QtWidgets.QLabel(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.currentStepTimeLabel.setFont(font)
        self.currentStepTimeLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.currentStepTimeLabel.setObjectName("currentStepTimeLabel")
        self.valveLayout.addWidget(self.currentStepTimeLabel, 3, 0, 1, 1)

        self.currentStepTimeEdit = QtWidgets.QLineEdit(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.currentStepTimeEdit.setFont(font)
        self.currentStepTimeEdit.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.currentStepTimeEdit.setObjectName("currentStepTimeEdit")
        self.currentStepTimeEdit.setReadOnly(True)
        self.currentStepTimeEdit.setMaximumWidth(100)
        self.valveLayout.addWidget(self.currentStepTimeEdit, 4, 0, 1, 1)

        self.stepsRemainingLabel = QtWidgets.QLabel(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.stepsRemainingLabel.setFont(font)
        self.stepsRemainingLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.stepsRemainingLabel.setObjectName("stepsRemainingLabel")
        self.valveLayout.addWidget(self.stepsRemainingLabel, 5, 0, 1, 1)

        self.stepsTimeRemainingLabel = QtWidgets.QLabel(
            parent=self.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.stepsTimeRemainingLabel.setFont(font)
        self.stepsTimeRemainingLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.stepsTimeRemainingLabel.setObjectName("stepsTimeRemainingLabel")
        self.valveLayout.addWidget(self.stepsTimeRemainingLabel, 6, 0, 1, 1)

        # self.stepsRemainingLabel.hide()
        # self.stepsTimeRemainingLabel.hide()
        # self.currentStepTypeLabel.hide()
        # self.currentStepTypeEdit.hide()
        # self.currentStepTimeLabel.hide()
        # self.currentStepTimeEdit.hide()

        self.Valve1Button.hide()
        self.Valve2Button.hide()
        self.Valve3Button.hide()
        self.Valve4Button.hide()
        self.Valve5Button.hide()
        self.devValveCheckbox.hide()

        # Create the motor layout
        self.verticalLayoutWidget_2 = QtWidgets.QWidget(
            parent=self.centralwidget)
        self.verticalLayoutWidget_2.setGeometry(
            QtCore.QRect(530, 10, 201, 291))
        self.verticalLayoutWidget_2.setObjectName("verticalLayoutWidget_2")
        self.motorConnectLayout = QtWidgets.QVBoxLayout(
            self.verticalLayoutWidget_2)
        self.motorConnectLayout.setContentsMargins(0, 0, 0, 0)
        self.motorConnectLayout.setObjectName("motorConnectLayout")

        # Create the motor COM port label
        self.motorCOMPortLabel = QtWidgets.QLabel(
            parent=self.verticalLayoutWidget_2)
        self.motorCOMPortLabel.setEnabled(True)
        font = QtGui.QFont()
        font.setPointSize(15)
        self.motorCOMPortLabel.setFont(font)
        self.motorCOMPortLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.motorCOMPortLabel.setObjectName("motorCOMPortLabel")
        self.motorConnectLayout.addWidget(self.motorCOMPortLabel)

        # Create the motor COM port spin box
        self.motorCOMPortSpinBox = QtWidgets.QSpinBox(
            parent=self.verticalLayoutWidget_2)
        self.motorCOMPortSpinBox.setMinimumSize(QtCore.QSize(0, 24))
        font = QtGui.QFont()
        font.setPointSize(11)
        self.motorCOMPortSpinBox.setFont(font)
        self.motorCOMPortSpinBox.setValue(9)
        self.motorCOMPortSpinBox.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTrailing | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.motorCOMPortSpinBox.setObjectName("motorCOMPortSpinBox")
        self.motorConnectLayout.addWidget(self.motorCOMPortSpinBox)

        # Create the motor warning label
        self.motorWarningLabel = QtWidgets.QLabel(
            parent=self.verticalLayoutWidget_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorWarningLabel.setFont(font)
        self.motorWarningLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter)
        self.motorWarningLabel.setObjectName("motorWarningLabel")
        self.motorConnectLayout.addWidget(self.motorWarningLabel)

        # Create the motor buttons
        self.motorConnectButton = QtWidgets.QPushButton(
            parent=self.verticalLayoutWidget_2)
        self.motorConnectButton.setMinimumSize(QtCore.QSize(0, 35))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.motorConnectButton.setFont(font)
        self.motorConnectButton.setObjectName("motorConnectButton")
        self.motorConnectLayout.addWidget(self.motorConnectButton)
        self.motorCalibrateButton = QtWidgets.QPushButton(
            parent=self.verticalLayoutWidget_2)
        self.motorCalibrateButton.setMinimumSize(QtCore.QSize(0, 35))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.motorCalibrateButton.setFont(font)
        self.motorCalibrateButton.setObjectName("motorCalibrateButton")
        self.motorConnectLayout.addWidget(self.motorCalibrateButton)
        self.motorStopButton = QtWidgets.QPushButton(
            parent=self.verticalLayoutWidget_2)
        self.motorStopButton.setMinimumSize(QtCore.QSize(0, 90))
        font = QtGui.QFont()
        font.setPointSize(20)
        self.motorStopButton.setFont(font)
        self.motorStopButton.setObjectName("motorStopButton")
        self.motorConnectLayout.addWidget(self.motorStopButton)

        # Create the monitor layout
        self.gridLayoutWidget_2 = QtWidgets.QWidget(parent=self.centralwidget)
        self.gridLayoutWidget_2.setGeometry(QtCore.QRect(760, 320, 261, 291))
        self.gridLayoutWidget_2.setObjectName("gridLayoutWidget_2")
        self.monitorLayout = QtWidgets.QGridLayout(self.gridLayoutWidget_2)
        self.monitorLayout.setContentsMargins(0, 0, 0, 0)
        self.monitorLayout.setObjectName("monitorLayout")

        '''
        # Create the pressure monitor button
        self.pressureMonitorButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.pressureMonitorButton.setMinimumSize(QtCore.QSize(0, 50))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.pressureMonitorButton.setFont(font)
        self.pressureMonitorButton.setObjectName("pressureMonitorButton")
        self.monitorLayout.addWidget(self.pressureMonitorButton, 0, 0, 1, 2)
        '''

        self.quickVentButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.quickVentButton.setMinimumSize(QtCore.QSize(0, 25))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.quickVentButton.setFont(font)
        self.quickVentButton.setObjectName("quickVentButton")
        self.quickVentButton.setCheckable(True)
        self.monitorLayout.addWidget(self.quickVentButton, 9, 0, 1, 1)

        self.slowVentButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.slowVentButton.setMinimumSize(QtCore.QSize(0, 25))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.slowVentButton.setFont(font)
        self.slowVentButton.setObjectName("slowVentButton")
        self.slowVentButton.setCheckable(True)
        self.monitorLayout.addWidget(self.slowVentButton, 9, 1, 1, 1)

        self.buildPressureButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.buildPressureButton.setMinimumSize(QtCore.QSize(0, 25))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.buildPressureButton.setFont(font)
        self.buildPressureButton.setObjectName("buildPressureButton")
        self.buildPressureButton.setCheckable(True)
        self.monitorLayout.addWidget(self.buildPressureButton, 6, 1, 1, 1)

        self.switchGasButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.switchGasButton.setMinimumSize(QtCore.QSize(0, 25))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.switchGasButton.setFont(font)
        self.switchGasButton.setObjectName("switchGasButton")
        self.switchGasButton.setCheckable(True)
        self.monitorLayout.addWidget(self.switchGasButton, 6, 0, 1, 1)

        self.valveMacro1Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.valveMacro1Button.setMinimumSize(QtCore.QSize(0, 25))
        self.valveMacro1Button.setMaximumWidth(125)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.valveMacro1Button.setFont(font)
        self.valveMacro1Button.setObjectName("valveMacro1Button")
        # self.valveMacro1Button.setCheckable(True)
        self.monitorLayout.addWidget(self.valveMacro1Button, 7, 0, 1, 1)

        self.valveMacro2Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.valveMacro2Button.setMinimumSize(QtCore.QSize(0, 25))
        self.valveMacro2Button.setMaximumWidth(125)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.valveMacro2Button.setFont(font)
        self.valveMacro2Button.setObjectName("valveMacro2Button")
        # self.valveMacro2Button.setCheckable(True)
        self.monitorLayout.addWidget(self.valveMacro2Button, 7, 1, 1, 1)

        self.valveMacro3Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.valveMacro3Button.setMinimumSize(QtCore.QSize(0, 25))
        self.valveMacro3Button.setMaximumWidth(125)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.valveMacro3Button.setFont(font)
        self.valveMacro3Button.setObjectName("valveMacro3Button")
        # self.valveMacro3Button.setCheckable(True)
        self.monitorLayout.addWidget(self.valveMacro3Button, 8, 0, 1, 1)

        self.valveMacro4Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.valveMacro4Button.setMinimumSize(QtCore.QSize(0, 25))
        self.valveMacro4Button.setMaximumWidth(125)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.valveMacro4Button.setFont(font)
        self.valveMacro4Button.setObjectName("valveMacro4Button")
        # self.valveMacro4Button.setCheckable(True)
        self.monitorLayout.addWidget(self.valveMacro4Button, 8, 1, 1, 1)

        # Create the pressure radio buttons
        self.pressure4RadioButton = QtWidgets.QRadioButton(
            parent=self.gridLayoutWidget_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pressure4RadioButton.setFont(font)
        self.pressure4RadioButton.setObjectName("pressure4RadioButton")
        self.pressure4RadioButton.setAutoExclusive(False)
        self.pressure4RadioButton.setChecked(True)
        self.monitorLayout.addWidget(
            self.pressure4RadioButton, 1, 1, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.pressure2RadioButton = QtWidgets.QRadioButton(
            parent=self.gridLayoutWidget_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pressure2RadioButton.setFont(font)
        self.pressure2RadioButton.setObjectName("pressure2RadioButton")
        self.pressure2RadioButton.setAutoExclusive(False)
        self.pressure2RadioButton.setChecked(True)
        self.monitorLayout.addWidget(
            self.pressure2RadioButton, 0, 1, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.pressure1RadioButton = QtWidgets.QRadioButton(
            parent=self.gridLayoutWidget_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pressure1RadioButton.setFont(font)
        self.pressure1RadioButton.setObjectName("pressure1RadioButton")
        self.pressure1RadioButton.setAutoExclusive(False)
        self.pressure1RadioButton.setChecked(True)
        self.monitorLayout.addWidget(
            self.pressure1RadioButton, 0, 0, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.pressure3RadioButton = QtWidgets.QRadioButton(
            parent=self.gridLayoutWidget_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pressure3RadioButton.setFont(font)
        self.pressure3RadioButton.setObjectName("pressure3RadioButton")
        self.pressure3RadioButton.setAutoExclusive(False)
        self.pressure3RadioButton.setChecked(True)
        self.monitorLayout.addWidget(
            self.pressure3RadioButton, 1, 0, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Create the save path buttons
        self.selectSavePathButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.selectSavePathButton.setMinimumSize(QtCore.QSize(0, 25))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.selectSavePathButton.setFont(font)
        self.selectSavePathButton.setObjectName("selectSavePathButton")
        self.monitorLayout.addWidget(self.selectSavePathButton, 2, 0, 1, 1)
        self.savePathEdit = QtWidgets.QLineEdit(parent=self.gridLayoutWidget_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.savePathEdit.setFont(font)
        self.savePathEdit.setObjectName("savePathEdit")
        self.monitorLayout.addWidget(self.savePathEdit, 3, 0, 1, 2)
        self.beginSaveButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.beginSaveButton.setMinimumSize(QtCore.QSize(0, 25))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.beginSaveButton.setFont(font)
        self.beginSaveButton.setObjectName("beginSaveButton")
        self.beginSaveButton.setCheckable(True)
        self.monitorLayout.addWidget(self.beginSaveButton, 2, 1, 1, 1)

        # Create the bubble time widgets
        self.bubbleTimeLabel = QtWidgets.QLabel(parent=self.gridLayoutWidget_2)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.bubbleTimeLabel.setFont(font)
        self.bubbleTimeLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight |
                                          QtCore.Qt.AlignmentFlag.AlignTrailing | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.bubbleTimeLabel.setObjectName("bubbleTimeLabel")
        self.monitorLayout.addWidget(self.bubbleTimeLabel, 4, 0, 1, 1)
        self.quickBubbleButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_2)
        self.quickBubbleButton.setMinimumSize(QtCore.QSize(0, 25))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.quickBubbleButton.setFont(font)
        self.quickBubbleButton.setCheckable(True)
        self.quickBubbleButton.setObjectName("quickBubbleButton")
        self.monitorLayout.addWidget(self.quickBubbleButton, 5, 0, 1, 2)

        self.bubbleTimeDoubleSpinBox = QtWidgets.QDoubleSpinBox(
            parent=self.gridLayoutWidget_2)
        self.bubbleTimeDoubleSpinBox.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTrailing | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.bubbleTimeDoubleSpinBox.setObjectName("bubbleTimeDoubleSpinBox")
        self.bubbleTimeDoubleSpinBox.setMinimum(0.0)
        self.bubbleTimeDoubleSpinBox.setValue(5.00)
        self.monitorLayout.addWidget(self.bubbleTimeDoubleSpinBox, 4, 1, 1, 1)

        # Create the motor position layout
        self.gridLayoutWidget_3 = QtWidgets.QWidget(parent=self.centralwidget)
        self.gridLayoutWidget_3.setGeometry(QtCore.QRect(740, 10, 281, 121))
        self.gridLayoutWidget_3.setObjectName("gridLayoutWidget_3")
        self.motorPosLayout = QtWidgets.QGridLayout(self.gridLayoutWidget_3)
        self.motorPosLayout.setContentsMargins(0, 0, 0, 0)
        self.motorPosLayout.setObjectName("motorPosLayout")

        # Create the motor position widgets
        self.curMotorPosLabel = QtWidgets.QLabel(
            parent=self.gridLayoutWidget_3)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.curMotorPosLabel.setFont(font)
        self.curMotorPosLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTrailing | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.curMotorPosLabel.setObjectName("curMotorPosLabel")
        self.motorPosLayout.addWidget(self.curMotorPosLabel, 0, 0, 1, 1)

        self.targetMotorPosEdit = QtWidgets.QLineEdit(
            parent=self.gridLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.targetMotorPosEdit.sizePolicy().hasHeightForWidth())
        self.targetMotorPosEdit.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.targetMotorPosEdit.setFont(font)
        self.targetMotorPosEdit.setObjectName("targetMotorPosEdit")
        self.motorPosLayout.addWidget(self.targetMotorPosEdit, 1, 1, 1, 1)

        self.curMotorPosEdit = QtWidgets.QLineEdit(
            parent=self.gridLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.curMotorPosEdit.sizePolicy().hasHeightForWidth())
        self.curMotorPosEdit.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.curMotorPosEdit.setReadOnly(True)
        self.curMotorPosEdit.setFont(font)
        self.curMotorPosEdit.setObjectName("curMotorPosEdit")
        self.motorPosLayout.addWidget(self.curMotorPosEdit, 0, 1, 1, 1)

        self.targetMotorPosLabel = QtWidgets.QLabel(
            parent=self.gridLayoutWidget_3)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.targetMotorPosLabel.setFont(font)
        self.targetMotorPosLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTrailing | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.targetMotorPosLabel.setObjectName("targetMotorPosLabel")
        self.motorPosLayout.addWidget(self.targetMotorPosLabel, 1, 0, 1, 1)

        self.motorMoveToTargetButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_3)
        self.motorMoveToTargetButton.setMinimumSize(QtCore.QSize(0, 40))
        font = QtGui.QFont()
        font.setPointSize(11)
        self.motorMoveToTargetButton.setFont(font)
        self.motorMoveToTargetButton.setObjectName("motorMoveToTargetButton")
        self.motorPosLayout.addWidget(self.motorMoveToTargetButton, 2, 0, 1, 2)

        # Create the motor macro layout
        self.gridLayoutWidget_4 = QtWidgets.QWidget(parent=self.centralwidget)
        self.gridLayoutWidget_4.setGeometry(QtCore.QRect(740, 130, 281, 171))
        self.gridLayoutWidget_4.setObjectName("gridLayoutWidget_4")
        self.motorMacroLayout = QtWidgets.QGridLayout(self.gridLayoutWidget_4)
        self.motorMacroLayout.setContentsMargins(0, 0, 0, 0)
        self.motorMacroLayout.setObjectName("motorMacroLayout")

        # Create the motor macro buttons
        self.motorMacro4Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorMacro4Button.setMinimumSize(QtCore.QSize(0, 35))
        self.motorMacro4Button.setMaximumWidth(135)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorMacro4Button.setFont(font)
        self.motorMacro4Button.setObjectName("motorMacro4Button")
        self.motorMacroLayout.addWidget(self.motorMacro4Button, 2, 1, 1, 1)
        self.motorMacro3Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorMacro3Button.setMinimumSize(QtCore.QSize(0, 35))
        self.motorMacro3Button.setMaximumWidth(135)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorMacro3Button.setFont(font)
        self.motorMacro3Button.setObjectName("motorMacro3Button")
        self.motorMacroLayout.addWidget(self.motorMacro3Button, 2, 0, 1, 1)
        self.motorAscentButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorAscentButton.setMinimumSize(QtCore.QSize(0, 35))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorAscentButton.setFont(font)
        self.motorAscentButton.setObjectName("motorAscentButton")
        self.motorMacroLayout.addWidget(self.motorAscentButton, 0, 1, 1, 1)
        self.motorMacro1Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorMacro1Button.setMinimumSize(QtCore.QSize(0, 35))
        self.motorMacro1Button.setMaximumWidth(135)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorMacro1Button.setFont(font)
        self.motorMacro1Button.setObjectName("motorMacro1Button")
        self.motorMacroLayout.addWidget(self.motorMacro1Button, 1, 0, 1, 1)
        self.motorMacro2Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorMacro2Button.setMinimumSize(QtCore.QSize(0, 35))
        self.motorMacro2Button.setMaximumWidth(135)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorMacro2Button.setFont(font)
        self.motorMacro2Button.setObjectName("motorMacro2Button")
        self.motorMacroLayout.addWidget(self.motorMacro2Button, 1, 1, 1, 1)
        self.motorToTopButton = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorToTopButton.setMinimumSize(QtCore.QSize(0, 35))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorToTopButton.setFont(font)
        self.motorToTopButton.setObjectName("motorToTopButton")
        self.motorMacroLayout.addWidget(self.motorToTopButton, 0, 0, 1, 1)
        self.motorMacro5Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorMacro5Button.setMinimumSize(QtCore.QSize(0, 35))
        self.motorMacro5Button.setMaximumWidth(135)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorMacro5Button.setFont(font)
        self.motorMacro5Button.setObjectName("motorMacro5Button")
        self.motorMacroLayout.addWidget(self.motorMacro5Button, 3, 0, 1, 1)
        self.motorMacro6Button = QtWidgets.QPushButton(
            parent=self.gridLayoutWidget_4)
        self.motorMacro6Button.setMinimumSize(QtCore.QSize(0, 35))
        self.motorMacro6Button.setMaximumWidth(135)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.motorMacro6Button.setFont(font)
        self.motorMacro6Button.setObjectName("motorMacro6Button")
        self.motorMacroLayout.addWidget(self.motorMacro6Button, 3, 1, 1, 1)

        # Set the central widget
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.menuBar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menuBar.setGeometry(QtCore.QRect(0, 0, 1029, 21))
        self.menuBar.setObjectName("menuBar")
        self.motorMacroMenu = QtWidgets.QMenu(parent=self.menuBar)
        self.motorMacroMenu.setObjectName("motorMacroMenu")
        MainWindow.setMenuBar(self.menuBar)
        self.editMotorMacroAction = QtGui.QAction(parent=MainWindow)
        self.editMotorMacroAction.setObjectName("editMotorMacroAction")
        self.motorMacroMenu.addAction(self.editMotorMacroAction)
        self.editValveMacroAction = QtGui.QAction(parent=MainWindow)
        self.editValveMacroAction.setObjectName("editValveMacroAction")
        self.motorMacroMenu.addAction(self.editValveMacroAction)
        self.menuBar.addAction(self.motorMacroMenu.menuAction())

        # Create the graph widgets container
        self.graphContainer = QtWidgets.QWidget(self.centralwidget)
        self.graphContainer.setGeometry(QtCore.QRect(119, 323, 625, 299))
        self.graphContainer.setObjectName("graphContainer")
        self.graphContainer.setStyleSheet(
            "border: 2px Solid LightGray;")  # Add border

        # Create the graph widgets
        self.figure = Figure()
        self.sc = RealTimePlot(self)
        self.graphWidget = QtWidgets.QWidget(
            parent=self.centralwidget)
        self.graphWidget.setGeometry(QtCore.QRect(121, 325, 621, 294))
        self.graphWidget.setObjectName("graphWidget")
        self.graphLayout = QtWidgets.QVBoxLayout(self.graphWidget)
        self.graphLayout.setContentsMargins(0, 0, 0, 0)
        self.graphLayout.setObjectName("graphLayout")
        self.graphLayout.addWidget(self.sc)

        # Create the toolbar and add it to the layout
        self.toolbar = NavigationToolbar(self.sc, self)
        self.graphLayout.addWidget(self.toolbar)

        # Connect the buttons to their slots
        # QtCore.QMetaObject.connectSlotsByName(MainWindow)
        self.ardConnectButton.clicked.connect(self.on_ardConnectButton_clicked)
        self.manualRadioButton.clicked.connect(
            self.on_manualRadioButton_clicked)
        self.TTLRadioButton.clicked.connect(self.on_TTLRadioButton_clicked)
        self.autoConnectRadioButton.clicked.connect(
            self.on_autoConnectRadioButton_clicked)
        self.Valve1Button.clicked.connect(self.on_Valve1Button_clicked)
        self.Valve2Button.clicked.connect(self.on_Valve2Button_clicked)
        self.Valve3Button.clicked.connect(self.on_Valve3Button_clicked)
        self.Valve4Button.clicked.connect(self.on_Valve4Button_clicked)
        self.Valve5Button.clicked.connect(self.on_Valve5Button_clicked)
        # self.Valve6Button.clicked.connect(self.on_Valve6Button_clicked)
        # self.Valve7Button.clicked.connect(self.on_Valve7Button_clicked)
        # self.Valve8Button.clicked.connect(self.on_Valve8Button_clicked)
        # self.pressureMonitorButton.clicked.connect(self.on_pressureMonitorButton_clicked)
        self.pressure1RadioButton.clicked.connect(
            self.on_pressure1RadioButton_clicked)
        self.pressure2RadioButton.clicked.connect(
            self.on_pressure2RadioButton_clicked)
        self.pressure3RadioButton.clicked.connect(
            self.on_pressure3RadioButton_clicked)
        self.pressure4RadioButton.clicked.connect(
            self.on_pressure4RadioButton_clicked)
        self.selectSavePathButton.clicked.connect(
            self.on_selectSavePathButton_clicked)
        self.resetButton.clicked.connect(self.on_resetButton_clicked)
        self.beginSaveButton.clicked.connect(self.on_beginSaveButton_clicked)
        self.quickVentButton.clicked.connect(self.on_quickVentButton_clicked)
        self.slowVentButton.clicked.connect(self.on_slowVentButton_clicked)
        self.buildPressureButton.clicked.connect(
            self.on_buildPressureButton_clicked)
        self.switchGasButton.clicked.connect(self.on_switchGasButton_clicked)
        self.quickBubbleButton.clicked.connect(
            self.on_quickBubbleButton_clicked)
        self.valveMacro1Button.clicked.connect(
            self.on_valveMacro1Button_clicked)
        self.valveMacro2Button.clicked.connect(
            self.on_valveMacro2Button_clicked)
        self.valveMacro3Button.clicked.connect(
            self.on_valveMacro3Button_clicked)
        self.valveMacro4Button.clicked.connect(
            self.on_valveMacro4Button_clicked)
        self.motorMacro1Button.clicked.connect(
            self.on_motorMacro1Button_clicked)
        self.motorMacro2Button.clicked.connect(
            self.on_motorMacro2Button_clicked)
        self.motorMacro3Button.clicked.connect(
            self.on_motorMacro3Button_clicked)
        self.motorMacro4Button.clicked.connect(
            self.on_motorMacro4Button_clicked)
        self.motorMacro5Button.clicked.connect(
            self.on_motorMacro5Button_clicked)
        self.motorMacro6Button.clicked.connect(
            self.on_motorMacro6Button_clicked)
        self.motorConnectButton.clicked.connect(
            self.on_motorConnectButton_clicked)
        self.motorCalibrateButton.clicked.connect(
            self.on_motorCalibrateButton_clicked)
        self.motorStopButton.clicked.connect(self.on_motorStopButton_clicked)
        self.motorAscentButton.clicked.connect(
            self.on_motorAscentButton_clicked)
        self.motorToTopButton.clicked.connect(self.on_motorToTopButton_clicked)
        self.motorMoveToTargetButton.clicked.connect(
            self.on_motorMoveToTargetButton_clicked)
        self.devValveCheckbox.clicked.connect(self.on_devValveCheckbox_clicked)

        # Connect menu actions to their slots
        self.editMotorMacroAction.triggered.connect(self.edit_motor_macro)
        self.editValveMacroAction.triggered.connect(self.edit_valve_macro)

        self.retranslateUi(MainWindow)
        self.update_controls()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Spectrometer GUI"))
        self.ardCOMPortLabel.setText(
            _translate("MainWindow", "Arduino COM Port"))
        self.ardWarningLabel.setText(_translate("MainWindow", ""))
        self.ardWarningLabel.setStyleSheet("color: red")
        self.autoConnectRadioButton.setText(
            _translate("MainWindow", "Automatic Mode"))
        self.TTLRadioButton.setText(_translate("MainWindow", "TTL Mode"))
        self.manualRadioButton.setText(_translate("MainWindow", "Manual Mode"))
        self.ardConnectButton.setText(_translate("MainWindow", "Connect"))
        self.Valve2Button.setText(_translate("MainWindow", "Inlet"))
        # self.Valve7Button.setText(_translate("MainWindow", "V7"))
        # self.Valve6Button.setText(_translate("MainWindow", "V6"))
        self.Valve1Button.setText(_translate("MainWindow", "Switch"))
        self.Valve4Button.setText(_translate("MainWindow", "Vent"))
        self.Valve3Button.setText(_translate("MainWindow", "Outlet"))
        # self.Valve8Button.setText(_translate("MainWindow", "V8"))
        self.Valve5Button.setText(_translate("MainWindow", "Short"))
        self.ValveLabel.setText(_translate("MainWindow", "Valves"))
        self.showValvesCheckbox.setText(
            _translate("MainWindow", "Graph\nValves"))
        self.motorCOMPortLabel.setText(
            _translate("MainWindow", "Motor COM Port"))
        self.motorWarningLabel.setText(_translate("MainWindow", ""))
        self.motorWarningLabel.setStyleSheet("color: red")
        self.motorConnectButton.setText(
            _translate("MainWindow", "Connect Motor"))
        self.motorCalibrateButton.setText(
            _translate("MainWindow", "Calibrate Motor"))
        self.motorStopButton.setText(_translate("MainWindow", "Stop Motor"))
        # self.pressureMonitorButton.setText(_translate("MainWindow", "Begin Pressure Monitor"))
        self.quickVentButton.setText(_translate("MainWindow", "Quick Vent"))
        self.slowVentButton.setText(_translate("MainWindow", "Slow Vent"))
        self.pressure4RadioButton.setText(
            _translate("MainWindow", "Pressure 4"))
        self.pressure2RadioButton.setText(
            _translate("MainWindow", "Pressure 2"))
        self.pressure1RadioButton.setText(
            _translate("MainWindow", "Pressure 1"))
        self.pressure3RadioButton.setText(
            _translate("MainWindow", "Pressure 3"))
        self.selectSavePathButton.setText(
            _translate("MainWindow", "Select Path.."))
        self.beginSaveButton.setText(_translate("MainWindow", "Begin Saving"))
        self.bubbleTimeLabel.setText(
            _translate("MainWindow", "Bubble Time (s)"))
        self.quickBubbleButton.setText(
            _translate("MainWindow", "Quick Bubble"))
        self.curMotorPosLabel.setText(_translate(
            "MainWindow", "Current Motor Pos (mm)"))
        self.targetMotorPosLabel.setText(
            _translate("MainWindow", "Target Motor Pos (mm)"))
        self.motorMoveToTargetButton.setText(
            _translate("MainWindow", "Move to Target Position"))
        self.motorMacro4Button.setText(
            _translate("MainWindow", "Motor Macro 4"))
        self.motorMacro3Button.setText(
            _translate("MainWindow", "Motor Macro 3"))
        self.motorAscentButton.setText(_translate("MainWindow", "Slow Ascent"))
        self.motorMacro1Button.setText(
            _translate("MainWindow", "Motor Macro 1"))
        self.motorMacro2Button.setText(
            _translate("MainWindow", "Motor Macro 2"))
        self.motorToTopButton.setText(
            _translate("MainWindow", "Return to Top"))
        self.motorMacro5Button.setText(
            _translate("MainWindow", "Motor Macro 5"))
        self.motorMacro6Button.setText(
            _translate("MainWindow", "Motor Macro 6"))
        self.motorMacroMenu.setTitle(
            _translate("MainWindow", "Edit Macros"))
        self.editMotorMacroAction.setText(
            _translate("MainWindow", "Edit Motor Macros"))
        self.editValveMacroAction.setText(_translate(
            "MainWindow", "Edit Valve Macros"))
        self.savePathEdit.setText(_translate("MainWindow", "C:\\ssbubble"))
        self.resetButton.setText(_translate("MainWindow", "Reset"))
        self.buildPressureButton.setText(
            _translate("MainWindow", "Build Pressure"))
        self.switchGasButton.setText(_translate("MainWindow", "Switch Gas"))
        self.valveMacro1Button.setText(
            _translate("MainWindow", "Valve Macro 1"))
        self.valveMacro2Button.setText(
            _translate("MainWindow", "Valve Macro 2"))
        self.valveMacro3Button.setText(
            _translate("MainWindow", "Valve Macro 3"))
        self.valveMacro4Button.setText(
            _translate("MainWindow", "Valve Macro 4"))
        self.currentStepTypeLabel.setText(
            _translate("MainWindow", "Cur. Step Type"))
        self.currentStepTimeLabel.setText(
            _translate("MainWindow", "Cur. Step Time"))
        self.stepsRemainingLabel.setText(
            _translate("MainWindow", "Steps: "))
        self.stepsTimeRemainingLabel.setText(
            _translate("MainWindow", "Time: "))

        # Update the main window's buttons with the new labels
        for i in range(4):
            getattr(self, f'valveMacro{
                    i+1}Button').setText(self.macro_settings[str(i+1)]['Label'])

        for i in range(6):
            getattr(self, f'motorMacro{
                    i+1}Button').setText(self.motor_macro_settings[str(i+1)]['Label'])

    def disconnect_ard(self):
        try:
            self.arduino_worker.command_signal.emit("RESET")
            self.arduino_worker.stop_timer()
        except Exception:
            pass
        if self.watchdog != None:
            self.watchdog.stop()
        self.ardConnected = False
        self.valveStates = [0, 0, 0, 0, 0, 0, 0, 0]
        self.update_valve_button_states()
        self.ardWarningLabel.setText("Connection closed")
        self.ardWarningLabel.setStyleSheet("color: red")
        self.UIUpdateArdConnection()

    def on_ardConnectButton_clicked(self):
        """Handle Arduino connection/disconnection."""
        if self.ardConnected:
            # If Arduino is already connected, stop the worker and disconnect
            self.disconnect_ard()

        # If no mode is selected, display a warning
        elif self.selectedMode == None:
            self.ardWarningLabel.setText("Please select a mode")
            self.ardWarningLabel.setStyleSheet("color: red")
            self.ardConnected = False
            self.UIUpdateArdConnection()
        else:
            # Create the worker and start the Arduino communication
            port = self.ardCOMPortSpinBox.value()
            self.arduino_worker = ArduinoWorker(
                self, port=port, mode=self.selectedMode, verbose=self.verbosity)

            self.arduino_worker.start()

            self.connect_arduino_signals()    # Connect the worker signals to appropriate slots

            # Create an event loop
            loop = QtCore.QEventLoop()

            # Define a function to check connection status
            def check_connection():
                if self.arduino_worker.isConnected():
                    loop.quit()  # Exit event loop if connected

            # Set up a timer to periodically check connection
            connection_timer = QtCore.QTimer()
            connection_timer.timeout.connect(check_connection)
            connection_timer.start(100)  # Check every 100 ms

            # Set a timeout to exit the event loop after the specified time
            QtCore.QTimer.singleShot(5000, loop.quit)  # Timeout after 5000 ms

            # Start the event loop
            loop.exec()

            # Stop the connection timer
            connection_timer.stop()

            # Update the UI based on the connection status
            if self.arduino_worker.isConnected():
                self.ardConnected = True
                # Start the watchdog timer that updates arduino connection status
                self.setup_arduino_watchdog()
                # Start the arduino time that read pressure readings every 500ms
                self.arduino_worker.start_timer()
            else:
                self.ardConnected = False
                self.arduino_worker.stop()
                self.ardWarningLabel.setText("Connection failed")
                self.ardWarningLabel.setStyleSheet("color: red")
            self.UIUpdateArdConnection()

            time.sleep(1)

            # If in manual mode, make sure buttons reflect actual valve states
            if self.selectedMode == 0:
                self.arduino_worker.command_signal.emit(
                    "TTLDISABLE")  # ensure tTL mode disabled
                self.update_valve_states()
                self.update_valve_button_states()

            # If in automatic mode, begin sequence processing
            if self.selectedMode == 1:
                self.arduino_worker.command_signal.emit(
                    "TTLDISABLE")  # ensure tTL mode disabled
                # begin sequence loading
                self.find_file()

    def update_valve_button_states(self):
        special_cases = {
            0: self.switchGasButton,
            1: self.buildPressureButton
        }

        for i in range(5):
            button = getattr(self, f'Valve{i+1}Button')
            button.setChecked(self.valveStates[i] == 1)
            if i in special_cases:
                special_cases[i].setChecked(self.valveStates[i] == 1)

    """Recurring function that updates the current step and valve states as well as the time labels."""

    def update_step(self):
        # Check the connection
        if self.ardConnected:
            if not self.motor_flag or (self.motor_worker.motor.serial_connected and self.motor_worker.calibrated):
                # Get the current time
                current_time = time.perf_counter()

                # Initialize last_update_time if it doesn't exist
                if not hasattr(self, 'last_update_time'):
                    self.last_update_time = current_time

                # Calculate elapsed time in milliseconds
                # Convert to milliseconds
                elapsed_time = (current_time - self.last_update_time) * 1000

                # Update last_update_time
                self.last_update_time = current_time

                # Increment time trackers by elapsed time
                self.sequence_running_time += elapsed_time
                self.step_running_time += elapsed_time

                # Update the time labels
                self.currentStepTimeEdit.setText(
                    f"{(self.current_step_time - self.step_running_time) / 1000:.2f}")
                self.stepsTimeRemainingLabel.setText(
                    f"Time: {(self.total_sequence_time - self.sequence_running_time) / 1000:.2f}")

                # Check if the current step is complete
                if self.step_running_time >= self.current_step_time:
                    # Check if sequence has been initialized
                    if self.seq_new == True:
                        self.seq_new = False
                    # If not, step is complete
                    else:
                        logging.info("Step complete")

                    # Reset the step timer
                    self.step_running_time = 0

                    # Check if there are more steps
                    if len(self.steps) == 0:
                        # If not, sequence is complete
                        self.ardWarningLabel.setText("Sequence complete")
                        self.ardWarningLabel.setStyleSheet("color: green")
                        self.currentStepTypeEdit.setText("")
                        self.stepsRemainingLabel.setText("Steps: 0")
                        self.stepsTimeRemainingLabel.setText("Time: 0.00")
                        self.currentStepTimeEdit.setText("0.00")

                        # Stop the timer to prevent this function from recurring
                        self.stepTimer.stop()

                        # Stop saving at the end of the sequence
                        if self.saving:
                            self.on_beginSaveButton_clicked()

                        # Reset sequence init flag
                        self.seq_new = True
                        return
                    else:
                        # Get the next step
                        self.current_step = self.steps.pop(0)
                        # Get the key values
                        self.current_step_time = self.current_step.time_length
                        self.current_step_type = self.current_step.step_type
                        # Update the labels
                        self.currentStepTypeEdit.setText(
                            self.step_types[self.current_step_type])

                        self.stepsRemainingLabel.setText(
                            f"Steps: {len(self.steps) + 1}")

                        # Update the valves with new step state
                        self.arduino_worker.set_valve_signal.emit(
                            self.valve_settings[self.current_step_type])

                        # Update the motor position if motor_flag is True
                        if self.motor_flag and self.current_step.motor_position >= 0:
                            self.motor_worker.command_signal.emit(
                                self.current_step.motor_position)

                        # Log the step type and time
                        logging.info(f"Step {self.step_types[self.current_step_type]} for {
                            self.current_step_time} ms")
            else:
                # If motor is not ready, stop the timer and reset all labels
                logging.error("Motor not connected and calibrated")
                self.ardWarningLabel.setText("Motor not ready")
                self.ardWarningLabel.setStyleSheet("color: red")
                self.stepTimer.stop()
                self.currentStepTypeEdit.setText("")
                self.stepsRemainingLabel.setText("Steps: 0")
                self.currentStepTimeEdit.setText("0.00")
                self.stepsTimeRemainingLabel.setText("Time: 0.00")
        else:
            # If arduino is not connected, stop the timer and reset all labels
            logging.error("Arduino not connected")
            self.ardWarningLabel.setText("Arduino not connected")
            self.ardWarningLabel.setStyleSheet("color: red")
            self.stepTimer.stop()
            self.currentStepTypeEdit.setText("")
            self.stepsRemainingLabel.setText("Steps: 0")
            self.currentStepTimeEdit.setText("0.00")
            self.stepsTimeRemainingLabel.setText("Time: 0.00")

            # Stop saving if it was started
            if self.saving:
                self.on_beginSaveButton_clicked()

            # Reset sequence init flag
            self.seq_new = True
            return

        # Recur the function every 10ms until sequence is over
        self.stepTimer.start(10)

    def calculate_sequence_time(self):
        """Calculate the total time of the sequence."""
        self.sequence_running_time = -10/1000
        self.step_running_time = -10/1000
        self.total_sequence_time = 0
        self.current_step_time = 0
        for step in self.steps:
            self.total_sequence_time += step.time_length
        logging.info(f"Sequence length is {self.total_sequence_time} ms")

    @QtCore.pyqtSlot()
    def find_file(self):
        self.file_timer = QtCore.QTimer()
        self.file_timer.timeout.connect(self.find_file)
        if os.path.exists(r"C:\ssbubble\sequence.txt"):
            logging.info("Sequence file found")
            if (self.load_sequence()):
                logging.info("Sequence loaded successfully")
                logging.info("Starting sequence")
                # Calculate time to show on the labels
                self.calculate_sequence_time()
                self.currentStepTypeEdit.setText(
                    self.step_types[self.steps[0].step_type])
                # logging.info(f"Step {self.steps[0].step_type} for {self.steps[0].time_length} ms")

                # Tell prospa that sequence was loaded successfully and is now running
                self.write_to_prospa(True)
                self.delete_sequence_file()

                # Update valve states for current step and start recurring timer
                self.update_step()

                # Update the UI
                self.UIUpdateArdConnection()
                self.ardWarningLabel.setText("Sequence running")
            else:
                self.write_to_prospa(False)
                self.delete_sequence_file()

                self.disconnect_ard()

                # Update the UI
                self.ardWarningLabel.setText(
                    "Error loading sequence file")
                self.ardWarningLabel.setStyleSheet("color: red")
                logging.error("Error loading sequence file")

                # Stop the arduino worker
                self.ardConnected = False
                self.arduino_worker.stop()
                self.UIUpdateArdConnection()

            self.file_timer.stop()
        else:
            if self.ardConnected:
                logging.info("Sequence file not found, checking again...")
                self.file_timer.singleShot(500, self.find_file)

    def load_sequence(self):
        """Load a sequence from a file."""

        try:
            # Get the file path
            self.steps = []  # initialise steps
            with open(r"C:\ssbubble\sequence.txt", "r") as f:
                # sequence format is a long string e.g. d100e200f400
                raw_sequence = f.readlines()

                # Check if the sequence file is empty
                if not raw_sequence:
                    logging.error("Sequence file is empty")
                    return False

                # Get the save path from the second line of the sequence file
                seq_save_path = raw_sequence[1].strip()
                sequence_string = raw_sequence[0].strip()
                i = 0

                # Check for capital 'M' in the sequence string
                self.motor_flag = False
                if 'M' in sequence_string:
                    self.motor_flag = True
                    sequence_string = sequence_string.replace(
                        'M', '')  # Remove 'M' from the sequence string

                if self.motor_flag:
                    try:
                        if not self.motor_worker.motor.serial_connected or not self.motor_worker.calibrated:
                            logging.error(
                                "Sequence requires motor, but motor is not ready")
                            return False
                    except Exception as e:
                        # logging.error(f"Error checking motor status: {e}")
                        logging.error(
                            "Sequence requires motor, but motor is not ready")
                        return False

                # Parse the sequence string
                while i < len(sequence_string):
                    # Check for valid step types based on dictionaries in the class (at the top of the file)
                    if sequence_string[i] in self.step_types.keys():
                        step_type = sequence_string[i]
                    else:
                        logging.error("Invalid step type in sequence file")
                        return False

                    # Get the time length of the step
                    i += 1
                    time_length = ""
                    while i < len(sequence_string) and sequence_string[i].isdigit():
                        time_length += sequence_string[i]
                        i += 1
                    try:
                        time_length = int(time_length)
                    except ValueError:
                        logging.error("Invalid time length in sequence file")
                        return False
                    if time_length <= 0:
                        logging.error("Invalid time length in sequence file")
                        return False

                    # Get motor position if motor_flag is True
                    motor_position = 0
                    if self.motor_flag and i < len(sequence_string) and sequence_string[i] == 'm':
                        i += 1
                        motor_position_str = ""
                        # Check for negative sign
                        if i < len(sequence_string) and sequence_string[i] == '-':
                            motor_position_str += sequence_string[i]
                            i += 1
                        # Collect digits
                        while i < len(sequence_string) and sequence_string[i].isdigit():
                            motor_position_str += sequence_string[i]
                            i += 1
                        try:
                            motor_position = int(motor_position_str)
                        except ValueError:
                            logging.error(
                                "Invalid motor position in sequence file")
                            return False

                    # Create a step object and add it to the list
                    step = Step(step_type, time_length, motor_position)
                    # logging.info("Step loaded: " + str(step.step_type) + " " + str(step.time_length))
                    self.steps.append(step)

                # Automatically start saving at sequence start
                if self.saving == False:
                    # Get the save path from the sequence file
                    if len(seq_save_path) > 1:    # Look for save path in second line of seqeunce file
                        if seq_save_path.endswith('.csv'):
                            self.savePathEdit.setText(seq_save_path)
                        else:   # Add timestamped csv to the file path if no file specified
                            self.savePathEdit.setText(os.path.join(
                                seq_save_path, f"pressure_data_{time.strftime('%m%d-%H%M')}.csv").replace("/", "\\"))
                    else:
                        # If no save path is specified, use the default path
                        self.savePathEdit.setText(
                            os.path.join(self.default_save_path, f"pressure_data_{time.strftime('%m%d-%H%M')}.csv").replace("/", "\\"))

                    # Simulate save button click
                    self.on_beginSaveButton_clicked()

            return True

        except FileNotFoundError:
            logging.error("Sequence file not found")
            return False

        except IOError as e:
            logging.error(f"Error reading sequence file: {e}")
            return False

    def write_to_prospa(self, start):
        """Write the file to Prospa."""
        if start:
            with open(r"C:\ssbubble\prospa.txt", "w") as f:
                f.write("1")    # Signal success
        else:
            with open(r"C:\ssbubble\prospa.txt", "w") as f:
                f.write("0")    # Signal failure

    def delete_sequence_file(self):
        """Delete the sequence file that Prospa makes."""
        try:
            os.remove(r"C:\ssbubble\sequence.txt")
            pass
        except FileNotFoundError:
            pass

    def on_autoConnectRadioButton_clicked(self):
        self.selectedMode = 1

    def on_TTLRadioButton_clicked(self):
        self.selectedMode = 2

    def on_manualRadioButton_clicked(self):
        self.selectedMode = 0

    """Update valve arduino controls."""

    def UIUpdateArdConnection(self):
        self.ardConnectButton.setEnabled(True)  # Re-enable the button
        if self.ardConnected == False:
            self.ardConnectButton.setText("Connect")
            self.ardCOMPortSpinBox.setEnabled(True)
            self.autoConnectRadioButton.setEnabled(True)
            self.TTLRadioButton.setEnabled(True)
            self.manualRadioButton.setEnabled(True)
        else:
            self.ardConnectButton.setText("Disconnect")
            self.ardCOMPortSpinBox.setEnabled(False)
            self.autoConnectRadioButton.setEnabled(False)
            self.TTLRadioButton.setEnabled(False)
            self.manualRadioButton.setEnabled(False)
            self.ardWarningLabel.setText("Connected")
            self.ardWarningLabel.setStyleSheet("color: green")
        self.update_controls()

    """Update the valve states with a thread safe call."""

    def update_valve_states(self):
        # Event loop ensures that state is updated before continuing
        loop = QtCore.QEventLoop()
        self.arduino_worker.valve_states_updated.connect(loop.quit)
        QtCore.QMetaObject.invokeMethod(
            self.arduino_worker, "get_valve_states", QtCore.Qt.ConnectionType.QueuedConnection)
        loop.exec()

    """Toggle valve 1"""

    def on_Valve1Button_clicked(self):
        # logging.debug("Valve 1 button clicked")
        # Update the valve states
        self.update_valve_states()
        # Check if the arduino is connected
        if self.ardConnected:
            if int(self.valveStates[0]) == 0:
                # Only change specified valve
                self.arduino_worker.set_valve_signal.emit(
                    [1, 2, 2, 2, 2, 2, 2, 2])
                logging.info("Turning on valve 1")
                self.Valve1Button.setChecked(True)
            else:
                self.arduino_worker.set_valve_signal.emit(
                    [0, 2, 2, 2, 2, 2, 2, 2])
                logging.info("Turning off valve 1")
                self.Valve1Button.setChecked(False)

    def on_Valve2Button_clicked(self):
        # logging.info("Valve 2 button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if int(self.valveStates[1]) == 0:
                logging.info("Turning on valve 2")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 1, 2, 2, 2, 2, 2, 2])
                self.Valve2Button.setChecked(True)
            else:
                logging.info("Turning off valve 2")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 0, 2, 2, 2, 2, 2, 2])
                self.Valve2Button.setChecked(False)

    def on_Valve3Button_clicked(self):
        # logging.info("Valve 3 button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if int(self.valveStates[2]) == 0:
                logging.info("Turning on valve 3")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 1, 2, 2, 2, 2, 2])
                self.Valve3Button.setChecked(True)
            else:
                logging.info("Turning off valve 3")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 0, 2, 2, 2, 2, 2])
                self.Valve3Button.setChecked(False)

    def on_Valve4Button_clicked(self):
        # logging.info("Valve 4 button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if int(self.valveStates[3]) == 0:
                logging.info("Turning on valve 4")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 2, 1, 2, 2, 2, 2])
                self.Valve4Button.setChecked(True)
            else:
                logging.info("Turning off valve 4")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 2, 0, 2, 2, 2, 2])
                self.Valve4Button.setChecked(False)

    def on_Valve5Button_clicked(self):
        # logging.info("Valve 5 button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if int(self.valveStates[4]) == 0:
                logging.info("Turning on valve 5")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 2, 2, 1, 2, 2, 2])
                self.Valve5Button.setChecked(True)
            else:
                logging.info("Turning off valve 5")
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 2, 2, 0, 2, 2, 2])
                self.Valve5Button.setChecked(False)

    def on_devValveCheckbox_clicked(self):
        self.update_controls()

    '''
    def on_Valve6Button_clicked(self):
        logging.info("Valve 6 button clicked")
        self.Valve6Button.setChecked(False)
        logging.info("Valve 6 not implemented")

    def on_Valve7Button_clicked(self):
        logging.info("Valve 7 button clicked")
        self.Valve7Button.setChecked(False)
        logging.info("Valve 7 not implemented")

    def on_Valve8Button_clicked(self):
        logging.info("Valve 8 button clicked")
        self.Valve8Button.setChecked(False)
        logging.info("Valve 8 not implemented")
    '''
    """
    def on_pressureMonitorButton_clicked(self):
        logging.info("Pressure monitor button clicked")
        if self.ardConnected:
            if self.monitoring:
                self.monitoring = False
                self.pressureMonitorButton.setText("Begin Pressure Monitor")
                self.controller.send_command(
                    "DISABLE_PRESSURE_LOG") # type: ignore
            else:
                self.monitoring = True
                self.pressureMonitorButton.setText("Stop Pressure Monitor")
                self.controller.send_command(
                    "ENABLE_PRESSURE_LOG") # type: ignore
        else:
            if self.monitoring:
                self.monitoring = False
                self.pressureMonitorButton.setText("Begin Pressure Monitor")
    """

    def on_pressure1RadioButton_clicked(self):
        pass

    def on_pressure2RadioButton_clicked(self):
        pass

    def on_pressure3RadioButton_clicked(self):
        pass

    def on_pressure4RadioButton_clicked(self):
        pass

    """Opens a file dialog to select the save path."""

    def on_selectSavePathButton_clicked(self):
        """
        logging.info("Select save path button clicked")
        self.save_path = QtWidgets.QFileDialog.getExistingDirectory(
            directory=self.savePathEdit.text())
        self.savePathEdit.setText(os.path.join(
            self.save_path, f"pressure_data_{time.strftime('%m%d-%H%M')}.csv").replace("/", "\\"))
        """
        self.save_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.savePathEdit,
            "Select CSV File",
            self.savePathEdit.text(),
            "CSV Files (*.csv)"
        )

        if self.save_path:
            # Optionally update the text field with the selected path
            self.savePathEdit.setText(self.save_path)
        else:
            self.savePathEdit.setText(os.path.join(
                self.default_save_path, f"pressure_data_{time.strftime('%m%d-%H%M')}.csv").replace("/", "\\"))

    @QtCore.pyqtSlot()
    def on_resetButton_clicked(self):
        logging.debug("Reset button clicked")
        if self.ardConnected:
            logging.info("Resetting")
            self.arduino_worker.set_valve_signal.emit([0, 0, 0, 0, 0, 0, 0, 0])
            self.arduino_worker.command_signal.emit("RESET")
            self.arduino_worker.command_signal.emit("RESTART")
            # self.valveStates = [0, 0, 0, 0, 0, 0, 0, 0]
            # self.update_valve_states()
            self.update_valve_button_states()

    @QtCore.pyqtSlot()
    def on_quickVentButton_clicked(self):
        logging.debug("Quick vent button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if self.vent_flag or self.sc.p2_data[-1] < 0.1:
                self.quickVentButton.setChecked(False)
                self.arduino_worker.set_valve_signal.emit(
                    self.previous_valve_states)
                self.toggle_valve_controls(True)
                self.vent_flag = False
            else:
                self.previous_valve_states = self.valveStates.copy()
                self.quickVentButton.setChecked(True)
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 1, 0, 1, 2, 2, 2])
                self.toggle_valve_controls(False)
                self.quickVentButton.setEnabled(True)
                self.vent_flag = True
        self.update_valve_states()
        self.update_valve_button_states()

    def on_slowVentButton_clicked(self):
        logging.debug("Slow vent button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if self.vent_flag or self.sc.p2_data[-1] < 0.1:
                self.slowVentButton.setChecked(False)
                self.arduino_worker.set_valve_signal.emit(
                    self.previous_valve_states)
                self.toggle_valve_controls(True)
                self.vent_flag = False
            else:
                self.slowVentButton.setChecked(True)
                self.previous_valve_states = self.valveStates.copy()
                self.arduino_worker.set_valve_signal.emit(
                    [2, 2, 1, 1, 1, 2, 2, 2])
                self.toggle_valve_controls(False)
                self.slowVentButton.setEnabled(True)
                self.vent_flag = True
        self.update_valve_states()
        self.update_valve_button_states()

    @QtCore.pyqtSlot()
    def on_beginSaveButton_clicked(self):
        # logging.debug("Begin save button clicked")
        if self.ardConnected:
            if self.saving:
                self.saving = False
                self.beginSaveButton.setChecked(False)
                self.beginSaveButton.setText("Begin Saving")
            else:
                if self.start_saving():
                    self.beginSaveButton.setChecked(True)
                    self.beginSaveButton.setText("Stop Saving")
                else:
                    self.saving = False
                    self.beginSaveButton.setChecked(False)
                    self.beginSaveButton.setText("Begin Saving")
                    logging.error("Error starting save")
        else:
            logging.info("Arduino not connected")

    def on_quickBubbleButton_clicked(self):
        if self.ardConnected:
            if not self.bubbleTimer.isActive():
                self.previous_valve_states = self.valveStates.copy()
                self.arduino_worker.set_valve_signal.emit(
                    [2, 1, 1, 1, 2, 2, 2, 2])
                duration = int(float(self.bubbleTimeDoubleSpinBox.text())*1000)
                self.bubbleTimer.start(duration)
                logging.info(f"Quick bubble for {duration} ms")
                self.quickBubbleButton.setChecked(True)
                self.toggle_valve_controls(False)
            else:
                logging.info("Already bubbling")
                self.quickBubbleButton.setChecked(True)
        else:
            logging.info("Arduino not connected")

    def bubble_timeout(self):
        logging.debug("Macro timer completed")
        if self.ardConnected:
            # Restore the previous valve states
            self.arduino_worker.set_valve_signal.emit(
                self.previous_valve_states)
            self.update_valve_states()
            self.update_valve_button_states()
        if self.quickBubbleButton.isChecked():
            self.quickBubbleButton.setChecked(False)
        # Enable all controls
        self.toggle_valve_controls(True)
        # Stop and disconnect the timer
        self.bubbleTimer.stop()
        self.bubbleTimer.timeout.disconnect(self.bubble_timeout)

    def on_buildPressureButton_clicked(self):
        logging.debug("Build pressure button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if self.valveStates[1] == 1:
                self.buildPressureButton.setChecked(False)
                self.arduino_worker.set_valve_signal.emit(
                    [2, 0, 2, 2, 2, 2, 2, 2])
            else:
                self.buildPressureButton.setChecked(True)
                self.arduino_worker.set_valve_signal.emit(
                    [2, 1, 2, 2, 2, 2, 2, 2])
        self.update_valve_states()
        self.update_valve_button_states()

    def on_switchGasButton_clicked(self):
        logging.debug("Switch gas button clicked")
        self.update_valve_states()
        if self.ardConnected:
            if self.valveStates[0] == 1:
                self.switchGasButton.setChecked(False)
                self.arduino_worker.set_valve_signal.emit(
                    [0, 2, 2, 2, 2, 2, 2, 2])
            else:
                self.switchGasButton.setChecked(True)
                self.arduino_worker.set_valve_signal.emit(
                    [1, 2, 2, 2, 2, 2, 2, 2])
        self.update_valve_states()
        self.update_valve_button_states()

    def on_valveMacro1Button_clicked(self):
        logging.debug("Valve macro 1 button clicked")
        if self.ardConnected:
            # Save current valve states
            self.previous_valve_states = self.valveStates.copy()
            # Set the new valve states
            self.arduino_worker.set_valve_signal.emit(
                self.macro_settings["1"]["Valves"])
            self.update_valve_states()
            self.update_valve_button_states()
            # Disable all controls
            self.toggle_valve_controls(False)
            # Start the timer
            # Convert to milliseconds
            timer_duration = int(self.macro_settings["1"]["Timer"] * 1000)
            self.bubbleTimer.timeout.connect(self.bubble_timeout)
            self.bubbleTimer.start(timer_duration)

    def on_valveMacro2Button_clicked(self):
        logging.debug("Valve macro 2 button clicked")
        if self.ardConnected:
            # Save current valve states
            self.previous_valve_states = self.valveStates.copy()
            # Set the new valve states
            self.arduino_worker.set_valve_signal.emit(
                self.macro_settings["2"]["Valves"])
            self.update_valve_states()
            self.update_valve_button_states()
            # Disable all controls
            self.toggle_valve_controls(False)
            # Start the timer
            # Convert to milliseconds
            timer_duration = int(self.macro_settings["2"]["Timer"] * 1000)
            self.bubbleTimer.timeout.connect(self.bubble_timeout)
            self.bubbleTimer.start(timer_duration)

    def on_valveMacro3Button_clicked(self):
        logging.debug("Valve macro 3 button clicked")
        if self.ardConnected:
            # Save current valve states
            self.previous_valve_states = self.valveStates.copy()
            # Set the new valve states
            self.arduino_worker.set_valve_signal.emit(
                self.macro_settings["3"]["Valves"])
            self.update_valve_states()
            self.update_valve_button_states()
            # Disable all controls
            self.toggle_valve_controls(False)
            # Start the timer
            # Convert to milliseconds
            timer_duration = int(self.macro_settings["3"]["Timer"] * 1000)
            self.bubbleTimer.timeout.connect(self.bubble_timeout)
            self.bubbleTimer.start(timer_duration)

    def on_valveMacro4Button_clicked(self):
        logging.debug("Valve macro 4 button clicked")
        if self.ardConnected:
            # Save current valve states
            self.previous_valve_states = self.valveStates.copy()
            # Set the new valve states
            self.arduino_worker.set_valve_signal.emit(
                self.macro_settings["4"]["Valves"])
            self.update_valve_states()
            self.update_valve_button_states()
            # Disable all controls
            self.toggle_valve_controls(False)
            # Start the timer
            # Convert to milliseconds
            timer_duration = int(self.macro_settings["4"]["Timer"] * 1000)
            self.bubbleTimer.timeout.connect(self.bubble_timeout)
            self.bubbleTimer.start(timer_duration)

    def start_saving(self):
        if self.savePathEdit.text().endswith(".csv"):
            self.save_path = self.savePathEdit.text()
        else:
            self.save_path = os.path.join(
                self.savePathEdit.text(), f"pressure_data_{time.strftime('%m%d-%H%M')}.csv").replace("/", "\\")
            self.savePathEdit.setText(self.save_path)
        try:
            with open(self.save_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["Time", "Pressure 1", "Pressure 2", "Pressure 3", "Pressure 4"])
                self.saving = True
                return True
        except Exception as e:
            logging.error("Could not open save file")
            self.saving = False
            return False

    def setup_arduino_watchdog(self):
        self.watchdog = QtCore.QTimer()
        self.watchdog.timeout.connect(self.check_arduino_state)
        self.watchdog.start(500)

    def check_arduino_state(self):
        # logging.debug("Checking arduino connection")
        self.update_valve_states()
        self.update_valve_button_states()
        if self.arduino_worker.controller.serial_connected == False:
            self.disconnect_ard()

    def setup_motor_watchdog(self):
        self.motor_watchdog = QtCore.QTimer()
        self.motor_watchdog.timeout.connect(self.check_motor_state)
        self.motor_watchdog.start(500)

    def check_motor_state(self):
        # logging.debug("Checking motor connection")
        if self.motor_worker.is_connected() == False:   # type: ignore
            self.motor_connected = False
            self.UIUpdateArdConnection()
            self.motor_worker.running = False   # type: ignore

    def on_motorAscentButton_clicked(self):
        logging.info("Motor Ascent button clicked")
        if self.motor_connected:
            self.motor_worker.ascent_signal.emit()

    def on_motorToTopButton_clicked(self):
        logging.info("Motor To Top button clicked")
        if self.motor_connected:
            self.motor_worker.top_signal.emit()

    def on_motorConnectButton_clicked(self):
        # logging.info("Connect motor button clicked")
        if self.motor_connected:
            logging.info("Disconnecting motor")
            self.motor_connected = False
            try:
                if getattr(self, 'motor_worker', None) is not None:
                    self.motor_worker.shutdown_signal.emit()
                    # self.motor_worker = None
                    self.motor_worker.running = False
                    self.motor_worker.timer.stop()
            except Exception as e:
                pass

            self.UIUpdateArdConnection()
        else:
            logging.info("Connecting motor")
            logging.info(f"Motor COM port: {self.motorCOMPortSpinBox.value()}")
            self.motor_worker = MotorWorker(
                parent=self, port=self.motorCOMPortSpinBox.value())
            self.motor_worker.connect()

            self.connect_motor_signals()    # Connect the worker signals to appropriate slots

            # Start the arduino time that read pressure readings every 500ms
            self.motor_worker.start_timer()

            # Create an event loop
            loop = QtCore.QEventLoop()

            # Define a function to check connection status
            def check_connection():
                if self.motor_worker.is_connected():
                    loop.quit()  # Exit event loop if connected

            # Set up a timer to periodically check connection
            connection_timer = QtCore.QTimer()
            connection_timer.timeout.connect(check_connection)
            connection_timer.start(100)  # Check every 100 ms

            # Set a timeout to exit the event loop after the specified time
            QtCore.QTimer.singleShot(5000, loop.quit)  # Timeout after 5000 ms

            # Start the event loop
            loop.exec()

            # Stop the connection timer
            connection_timer.stop()

            # Update the UI based on the connection status
            if self.motor_worker.is_connected():
                logging.info("Motor connected")
                self.motor_connected = True
                # Start the watchdog timer that updates arduino connection status
                self.setup_motor_watchdog()
            else:
                logging.error("Motor connection failed")
                self.motor_connected = False
                self.motor_worker.shutdown_signal.emit()
                self.ardWarningLabel.setText("Connection failed")
                self.ardWarningLabel.setStyleSheet("color: red")
        self.UIUpdateArdConnection()

    def on_motorCalibrateButton_clicked(self):
        logging.info("Calibrate motor button clicked")
        if self.motor_connected:
            self.motor_worker.calibrate_signal.emit()

    def on_motorStopButton_clicked(self):
        logging.info("Stop motor button clicked")
        if self.motor_connected:
            self.motor_worker.shutdown_signal.emit()

    def on_motorMoveToTargetButton_clicked(self):
        logging.info("Move to target button clicked")
        if self.motor_connected:
            try:
                # TODO: convert from mm to steps
                targetpos = int(self.targetMotorPosEdit.text())
                self.motor_worker.command_signal.emit(targetpos)
            except ValueError:
                logging.error("Invalid target position")

    def on_motorMacro1Button_clicked(self):
        logging.info("Motor macro 1 button clicked")
        if self.motor_connected:
            self.motor_worker.command_signal.emit(
                self.motor_macro_settings["1"]["Position"])

    def on_motorMacro2Button_clicked(self):
        logging.info("Motor macro 2 button clicked")
        if self.motor_connected:
            self.motor_worker.command_signal.emit(
                self.motor_macro_settings["2"]["Position"])

    def on_motorMacro3Button_clicked(self):
        logging.info("Motor macro 3 button clicked")
        if self.motor_connected:
            self.motor_worker.command_signal.emit(
                self.motor_macro_settings["3"]["Position"])

    def on_motorMacro4Button_clicked(self):
        logging.info("Motor macro 4 button clicked")
        if self.motor_connected:
            self.motor_worker.command_signal.emit(
                self.motor_macro_settings["4"]["Position"])

    def on_motorMacro5Button_clicked(self):
        logging.info("Motor macro 5 button clicked")
        if self.motor_connected:
            self.motor_worker.command_signal.emit(
                self.motor_macro_settings["5"]["Position"])

    def on_motorMacro6Button_clicked(self):
        logging.info("Motor macro 6 button clicked")
        if self.motor_connected:
            self.motor_worker.command_signal.emit(
                self.motor_macro_settings["6"]["Position"])

    def add_step(self, step_type, time_length):
        step = Step(step_type, time_length)
        self.steps.append(step)

    def remove_step(self, index):
        if 0 <= index < len(self.steps):
            del self.steps[index]

    def list_steps(self):
        for step in self.steps:
            print(f"Step Type: {step.step_type}, Time Length: {
                  step.time_length}")

    def edit_motor_macro(self):
        self.motor_macro_editor.exec()

    def edit_valve_macro(self):
        # dialog = ValveMacroEditor(self)
        self.macro_editor.exec()

    def toggle_valve_controls(self, state):
        self.switchGasButton.setEnabled(state)
        self.valveMacro1Button.setEnabled(state)
        self.valveMacro2Button.setEnabled(state)
        self.valveMacro3Button.setEnabled(state)
        self.valveMacro4Button.setEnabled(state)
        self.buildPressureButton.setEnabled(state)
        self.quickBubbleButton.setEnabled(state)
        self.bubbleTimeDoubleSpinBox.setEnabled(state)
        self.switchGasButton.setEnabled(state)
        self.quickVentButton.setEnabled(state)
        self.slowVentButton.setEnabled(state)
        self.Valve1Button.setEnabled(state)
        self.Valve2Button.setEnabled(state)
        self.Valve3Button.setEnabled(state)
        self.Valve4Button.setEnabled(state)
        self.Valve5Button.setEnabled(state)

    """Enables and disables controls based on the running mode"""

    def update_controls(self):
        if self.ardConnected:
            # Toggle connection controls
            self.manualRadioButton.setEnabled(False)
            self.autoConnectRadioButton.setEnabled(False)
            self.TTLRadioButton.setEnabled(False)
            self.ardCOMPortSpinBox.setEnabled(False)
            # Toggle graphing controls
            self.pressure1RadioButton.setEnabled(True)
            self.pressure2RadioButton.setEnabled(True)
            self.pressure3RadioButton.setEnabled(True)
            self.pressure4RadioButton.setEnabled(True)
            # Toggle save controls
            self.beginSaveButton.setEnabled(True)
            # self.savePathEdit.setEnabled(True)
            # self.selectSavePathButton.setEnabled(True)
            if self.selectedMode == 0:
                # Toggle valve controls
                self.devValveCheckbox.setEnabled(True)
                if self.devValveCheckbox.isChecked():
                    self.Valve1Button.setEnabled(True)
                    self.Valve2Button.setEnabled(True)
                    self.Valve3Button.setEnabled(True)
                    self.Valve4Button.setEnabled(True)
                    self.Valve5Button.setEnabled(True)
                else:
                    self.Valve1Button.setEnabled(False)
                    self.Valve2Button.setEnabled(False)
                    self.Valve3Button.setEnabled(False)
                    self.Valve4Button.setEnabled(False)
                    self.Valve5Button.setEnabled(False)
                # self.Valve6Button.setEnabled(True)
                # self.Valve7Button.setEnabled(True)
                # self.Valve8Button.setEnabled(True)
                # self.pressureMonitorButton.setEnabled(True)
                self.quickVentButton.setEnabled(True)
                self.slowVentButton.setEnabled(True)
                self.valveMacro1Button.setEnabled(True)
                self.valveMacro2Button.setEnabled(True)
                self.valveMacro3Button.setEnabled(True)
                self.valveMacro4Button.setEnabled(True)
                self.buildPressureButton.setEnabled(True)
                self.switchGasButton.setEnabled(True)
                self.quickBubbleButton.setEnabled(True)
                self.bubbleTimeDoubleSpinBox.setEnabled(True)
                self.Valve1Button.show()
                self.Valve2Button.show()
                self.Valve3Button.show()
                self.Valve4Button.show()
                self.Valve5Button.show()
                self.devValveCheckbox.show()
                self.currentStepTimeEdit.hide()
                self.currentStepTypeEdit.hide()
                self.stepsRemainingLabel.hide()
                self.currentStepTimeLabel.hide()
                self.currentStepTypeLabel.hide()
                self.stepsTimeRemainingLabel.hide()
            elif self.selectedMode == 1 or self.selectedMode == 2:
                # Toggle valve controls
                self.Valve1Button.setEnabled(False)
                self.Valve2Button.setEnabled(False)
                self.Valve3Button.setEnabled(False)
                self.Valve4Button.setEnabled(False)
                self.Valve5Button.setEnabled(False)
                self.devValveCheckbox.setEnabled(False)
                # self.Valve6Button.setEnabled(False)
                # self.Valve7Button.setEnabled(False)
                # self.Valve8Button.setEnabled(False)
                # self.pressureMonitorButton.setEnabled(False)
                self.quickVentButton.setEnabled(False)
                self.slowVentButton.setEnabled(False)
                self.valveMacro1Button.setEnabled(False)
                self.valveMacro2Button.setEnabled(False)
                self.valveMacro3Button.setEnabled(False)
                self.valveMacro4Button.setEnabled(False)
                self.buildPressureButton.setEnabled(False)
                self.switchGasButton.setEnabled(False)
                self.quickBubbleButton.setEnabled(False)
                self.bubbleTimeDoubleSpinBox.setEnabled(False)
                if self.selectedMode == 1:
                    self.Valve1Button.hide()
                    self.Valve2Button.hide()
                    self.Valve3Button.hide()
                    self.Valve4Button.hide()
                    self.Valve5Button.hide()
                    self.devValveCheckbox.hide()
                    self.currentStepTimeEdit.show()
                    self.currentStepTypeEdit.show()
                    self.stepsRemainingLabel.show()
                    self.currentStepTimeLabel.show()
                    self.currentStepTypeLabel.show()
                    self.stepsTimeRemainingLabel.show()
        else:
            # Toggle connection controls
            self.manualRadioButton.setEnabled(True)
            self.autoConnectRadioButton.setEnabled(True)
            self.TTLRadioButton.setEnabled(True)
            self.ardCOMPortSpinBox.setEnabled(True)
            # Toggle valve controls
            self.Valve1Button.setEnabled(False)
            self.Valve2Button.setEnabled(False)
            self.Valve3Button.setEnabled(False)
            self.Valve4Button.setEnabled(False)
            self.Valve5Button.setEnabled(False)
            self.devValveCheckbox.setEnabled(False)
            # self.Valve6Button.setEnabled(False)
            # self.Valve7Button.setEnabled(False)
            # self.Valve8Button.setEnabled(False)
            # self.pressureMonitorButton.setEnabled(False)
            self.quickVentButton.setEnabled(False)
            self.slowVentButton.setEnabled(False)
            self.valveMacro1Button.setEnabled(False)
            self.valveMacro2Button.setEnabled(False)
            self.valveMacro3Button.setEnabled(False)
            self.valveMacro4Button.setEnabled(False)
            self.quickBubbleButton.setEnabled(False)
            self.bubbleTimeDoubleSpinBox.setEnabled(False)
            self.buildPressureButton.setEnabled(False)
            self.switchGasButton.setEnabled(False)
            # Toggle graphing controls
            self.pressure1RadioButton.setEnabled(False)
            self.pressure2RadioButton.setEnabled(False)
            self.pressure3RadioButton.setEnabled(False)
            self.pressure4RadioButton.setEnabled(False)
            # Toggle save controls
            self.beginSaveButton.setEnabled(False)
            # self.savePathEdit.setEnabled(False)
            # self.selectSavePathButton.setEnabled(False)
        if self.saving:
            self.savePathEdit.setEnabled(False)
            self.selectSavePathButton.setEnabled(False)
        else:
            self.savePathEdit.setEnabled(True)
            self.selectSavePathButton.setEnabled(True)
        if self.motor_connected:
            self.motorConnectButton.setText("Disconnect")
            # logging.info("Motor connected")
            # logging.info(f"Calibrated? {self.motor_worker.calibrated}")
            if self.motor_worker.calibrated == 1:
                self.motorCalibrateButton.setEnabled(False)
                self.motorWarningLabel.setText("Calibrated")
                self.motorWarningLabel.setStyleSheet("color: green")
                self.toggle_motor_controls(True)
            else:
                self.motorCalibrateButton.setEnabled(True)
                self.motorWarningLabel.setText("Not Calibrated")
                self.motorWarningLabel.setStyleSheet("color: red")
                self.toggle_motor_controls(False)
        else:
            self.motorConnectButton.setText("Connect")
            self.motorWarningLabel.setText("Not Connected")
            self.motorWarningLabel.setStyleSheet("color: red")
            self.motorCalibrateButton.setEnabled(False)
            self.toggle_motor_controls(False)

    """
    def UIUpdateMotorConnection(self):
        if self.motor_connected:
            self.motorConnectButton.setText("Disconnect")
            if self.motor_worker.calibrated >= 1:
                self.motorCalibrateButton.setEnabled(False)
                self.motorWarningLabel.setText("Calibrated")
                self.motorWarningLabel.setStyleSheet("color: green")
                self.toggle_motor_controls(True)
            else:
                self.motorCalibrateButton.setEnabled(True)
                self.motorWarningLabel.setText("Not Calibrated")
                self.motorWarningLabel.setStyleSheet("color: red")
                self.toggle_motor_controls(False)
        else:
            self.motorConnectButton.setText("Connect")
            self.motorWarningLabel.setText("Not Connected")
            self.motorWarningLabel.setStyleSheet("color: red")
            self.motorCalibrateButton.setEnabled(False)
            self.toggle_motor_controls(False)
"""

    def toggle_motor_controls(self, state):
        self.motorStopButton.setEnabled(state)
        self.motorMoveToTargetButton.setEnabled(state)
        # self.targetMotorPosEdit.setEnabled(state)
        self.motorMacro1Button.setEnabled(state)
        self.motorMacro2Button.setEnabled(state)
        self.motorMacro3Button.setEnabled(state)
        self.motorMacro4Button.setEnabled(state)
        self.motorMacro5Button.setEnabled(state)
        self.motorMacro6Button.setEnabled(state)
        self.motorAscentButton.setEnabled(state)
        self.motorToTopButton.setEnabled(state)

    def connect_arduino_signals(self):
        self.arduino_worker.data_signal.connect(
            self.sc.update_plot)  # To update the plot
        self.arduino_worker.command_signal.connect(
            self.arduino_worker.send_command)
        self.arduino_worker.set_valve_signal.connect(
            self.arduino_worker.set_valve_states)
        self.arduino_worker.get_valve_signal.connect(
            self.arduino_worker.get_valve_states)

    def connect_motor_signals(self):
        self.motor_worker.command_signal.connect(
            self.motor_worker.move_to_target)
        self.motor_worker.shutdown_signal.connect(self.motor_worker.stop)
        self.motor_worker.calibrate_signal.connect(self.motor_worker.calibrate)
        self.motor_worker.ascent_signal.connect(self.motor_worker.ascent)
        self.motor_worker.top_signal.connect(self.motor_worker.to_top)


class Step:
    def __init__(self, step_type, time_length, motor_position=0):
        self.step_type = step_type
        self.time_length = time_length
        self.motor_position = motor_position


class QTextEditLogger(logging.Handler, QtCore.QObject):  # Console window
    appendPlainText = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        super().__init__()
        QtCore.QObject.__init__(self)
        self.widget = parent
        self.widget.setReadOnly(True)
        self.appendPlainText.connect(self.widget.insertPlainText)
        self.appendPlainText.connect(self.scroll_to_bottom)

    def emit(self, record):
        msg = self.format(record) + '\n'
        self.appendPlainText.emit(msg)

    @QtCore.pyqtSlot()
    def scroll_to_bottom(self):
        self.widget.verticalScrollBar().setValue(
            self.widget.verticalScrollBar().maximum())

    def close(self):
        self.widget.clear()
        super().close()


class MotorMacroEditor(QtWidgets.QDialog):  # Motor Macro Editor
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.setWindowTitle("Motor Macro Editor")
        self.setGeometry(100, 100, 300, 230)
        self.setFixedSize(300, 230)

        # Create a table widget
        self.table = QtWidgets.QTableWidget(self)
        self.table.setRowCount(6)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            ["Macro No.", "Label", "Position"])

        # Set layout
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.addWidget(self.table)
        self.setLayout(self.mainLayout)

        # Determine the directory of the executable
        self.executable_dir = os.path.dirname(sys.executable) if getattr(
            sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

        # Load data from JSON file if it exists
        self.load_data()

        # Resize all columns to fit
        self.table.resizeColumnsToContents()
        # Resize the Label column
        self.table.setColumnWidth(1, 130)  # Label column is now index 1

    def load_data(self):
        json_path = os.path.join("C:\\ssbubble", 'motor_macro_data.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                for i, macro in enumerate(data):
                    # Macro No.
                    item = QtWidgets.QTableWidgetItem(macro["Macro No."])
                    # Make the item read-only
                    item.setFlags(item.flags() & ~
                                  QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(i, 0, item)
                    # Label
                    label_text = macro.get("Label", "")
                    label_item = QtWidgets.QTableWidgetItem(label_text)
                    self.table.setItem(i, 1, label_item)
                    # Position SpinBox
                    position_spinbox = QtWidgets.QSpinBox()
                    # Adjust range as needed
                    position_spinbox.setRange(0, 2500000)
                    position_val = macro.get("Position", 0)   # Default to 0
                    position_spinbox.setValue(position_val)
                    self.table.setCellWidget(i, 2, position_spinbox)
            except (json.JSONDecodeError, KeyError, IndexError):
                self.set_default_values()
        else:
            self.set_default_values()

    def set_default_values(self):
        for i in range(6):
            # Macro No.
            item = QtWidgets.QTableWidgetItem(f"Macro {i+1}")
            # Make the item read-only
            item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item)
            # Label
            label_item = QtWidgets.QTableWidgetItem(f"Motor Macro {i+1}")
            self.table.setItem(i, 1, label_item)
            # Position SpinBox
            position_spinbox = QtWidgets.QSpinBox()
            position_spinbox.setRange(0, 2500000)  # Adjust range as needed
            position_spinbox.setValue(0)  # Default position value
            self.table.setCellWidget(i, 2, position_spinbox)

    def get_macro_data(self):
        data = []
        for row in range(self.table.rowCount()):
            macro_number = self.table.item(row, 0).text()   # type: ignore
            label_text = self.table.item(row, 1).text()     # type: ignore
            position_spinbox = self.table.cellWidget(row, 2)
            # Get Position value
            position_value = position_spinbox.value() if position_spinbox else 0   # type: ignore
            data.append({
                "Macro No.": macro_number,
                "Label": label_text,
                "Position": position_value
            })
        return data

    def get_macro_data_dict(self):
        data = {}
        for row in range(self.table.rowCount()):
            macro_number = self.table.item(row, 0).text()[-1]  # type: ignore
            label_text = self.table.item(row, 1).text()        # type: ignore
            position_spinbox = self.table.cellWidget(row, 2)
            position_value = position_spinbox.value() if position_spinbox else 0   # type: ignore
            data[macro_number] = {
                "Label": label_text,
                "Position": position_value
            }
        return data

    def closeEvent(self, event):
        # Update parent's macro_settings with the new data
        self.parent.motor_macro_settings = self.get_macro_data_dict()
        # Save data to JSON
        data = self.get_macro_data()
        json_path = os.path.join("C:\\ssbubble", 'motor_macro_data.json')
        json_dir = os.path.dirname(json_path)

        # Ensure the directory exists
        if not os.path.exists(json_dir):
            os.makedirs(json_dir)
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=4)

        # Update the main window's buttons with the new labels
        for i in range(6):
            label = self.parent.motor_macro_settings[str(i+1)]['Label']
            getattr(self.parent, f'motorMacro{i+1}Button').setText(label)

        super().closeEvent(event)


class ValveMacroEditor(QtWidgets.QDialog):  # Valve Macro Editor
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.setWindowTitle("Valve Macro Editor")
        self.setGeometry(100, 100, 650, 190)
        self.setFixedSize(623, 170)  # Adjusted width to accommodate new column

        # Create a table widget
        self.table = QtWidgets.QTableWidget(self)
        self.table.setRowCount(4)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Macro No.", "Label", "V1", "V2", "V3", "V4", "V5", "Timer (s)"])

        # Set layout
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.addWidget(self.table)
        self.setLayout(self.mainLayout)

        # Determine the directory of the executable
        self.executable_dir = os.path.dirname(sys.executable) if getattr(
            sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

        # Load data from JSON file if it exists
        self.load_data()

        # Resize all columns to fit
        self.table.resizeColumnsToContents()
        # Resize the Label column
        self.table.setColumnWidth(1, 120)  # Label column is now index 1
        # Resize the Timer column
        self.table.setColumnWidth(7, 80)  # Timer column is now index 7

    def load_data(self):
        json_path = os.path.join("C:\\ssbubble", 'valve_macro_data.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                for i, macro in enumerate(data):
                    # Macro No.
                    item = QtWidgets.QTableWidgetItem(macro["Macro No."])
                    # Make the item read-only
                    item.setFlags(item.flags() & ~
                                  QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(i, 0, item)
                    # Label
                    label_text = macro.get("Label", "")
                    label_item = QtWidgets.QTableWidgetItem(label_text)
                    self.table.setItem(i, 1, label_item)
                    # Valve States
                    # Only process the first 5 values
                    # start from column 2
                    for j, state in enumerate(macro["Valves"][:5], start=2):
                        combo = QtWidgets.QComboBox()
                        combo.addItems(["Open", "Closed", "Ignore"])
                        combo.setCurrentText(state)
                        self.table.setCellWidget(i, j, combo)
                    # Timer SpinBox
                    timer_spinbox = QtWidgets.QDoubleSpinBox()
                    timer_spinbox.setRange(0.1, 3600)
                    timer_spinbox.setSingleStep(0.1)
                    timer_val = macro.get("Timer", 1.0)   # Default to 1 second
                    timer_spinbox.setValue(timer_val)
                    # Timer column index is 7
                    self.table.setCellWidget(i, 7, timer_spinbox)
            except (json.JSONDecodeError, KeyError, IndexError):
                self.set_default_values()
        else:
            self.set_default_values()

    def set_default_values(self):
        for i in range(4):
            # Macro No.
            item = QtWidgets.QTableWidgetItem(f"Macro {i+1}")
            # Make the item read-only
            item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item)
            # Label
            label_item = QtWidgets.QTableWidgetItem("")
            self.table.setItem(i, 1, label_item)
            # Valve States
            for j in range(2, 7):  # Columns 2 to 6 for V1 to V5
                combo = QtWidgets.QComboBox()
                combo.addItems(["Open", "Closed", "Ignore"])
                combo.setCurrentIndex(1)  # Default to "Closed"
                self.table.setCellWidget(i, j, combo)
            # Timer SpinBox
            timer_spinbox = QtWidgets.QDoubleSpinBox()
            timer_spinbox.setRange(0.1, 3600)
            timer_spinbox.setSingleStep(0.1)
            timer_spinbox.setValue(1.0)  # Default timer value
            self.table.setCellWidget(i, 7, timer_spinbox)

    def get_macro_data(self):
        data = []
        for row in range(self.table.rowCount()):
            macro_number = self.table.item(row, 0).text()   # type: ignore
            label_text = self.table.item(row, 1).text()     # type: ignore
            valve_states = [self.table.cellWidget(
                # V1 to V5
                row, col).currentText() for col in range(2, 7)]  # type: ignore
            # Add "Closed" for the last 3 valves
            valve_states.extend(["Closed", "Closed", "Closed"])
            timer_spinbox = self.table.cellWidget(row, 7)
            # Get Timer value
            timer_value = timer_spinbox.value() if timer_spinbox else 1.0   # type: ignore
            data.append({
                "Macro No.": macro_number,
                "Label": label_text,
                "Valves": valve_states,
                "Timer": timer_value
            })
        return data

    def get_macro_data_dict(self):
        data = {}
        for row in range(self.table.rowCount()):
            macro_number = self.table.item(row, 0).text()[-1]  # type: ignore
            label_text = self.table.item(row, 1).text()        # type: ignore
            valve_states = [self.table.cellWidget(
                # V1 to V5
                row, col).currentText() for col in range(2, 7)]  # type: ignore
            valve_states_numeric = [
                1 if state == "Open" else 0 if state == "Closed" else 2 for state in valve_states]
            # Add 2 for the last 3 valves
            valve_states_numeric.extend([2, 2, 2])
            # Get Timer value
            timer_spinbox = self.table.cellWidget(row, 7)
            timer_value = timer_spinbox.value() if timer_spinbox else 1.0   # type: ignore
            data[macro_number] = {
                "Label": label_text,
                "Valves": valve_states_numeric,
                "Timer": timer_value
            }
        return data

    def closeEvent(self, event):
        # Update parent's macro_settings with the new data
        self.parent.macro_settings = self.get_macro_data_dict()
        # Save data to JSON
        data = self.get_macro_data()
        json_path = os.path.join("C:\\ssbubble", 'valve_macro_data.json')
        json_dir = os.path.dirname(json_path)

        # Ensure the directory exists
        if not os.path.exists(json_dir):
            os.makedirs(json_dir)
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=4)

        # Update the main window's buttons with the new labels
        for i in range(4):
            getattr(self.parent, f'valveMacro{
                    i+1}Button').setText(self.parent.macro_settings[str(i+1)]['Label'])

        super().closeEvent(event)


class RealTimePlot(FigureCanvasQTAgg, QtCore.QObject):

    def __init__(self, parent):
        self.fig, self.ax = plt.subplots()
        FigureCanvasQTAgg.__init__(self, self.fig)
        QtCore.QObject.__init__(self)

        self.parent = parent
        self.max_points = 500

        # Initialize data
        self.p1_data = []
        self.p2_data = []
        self.p3_data = []
        self.p4_data = []
        self.x_data = []
        self.parent = parent
        # Initialize an empty plot
        self.line1, = self.ax.plot([], [], lw=2, color="red")
        # Initialize an empty plot
        self.line2, = self.ax.plot([], [], lw=2, color="blue")
        # Initialize an empty plot
        self.line3, = self.ax.plot([], [], lw=2, color="green")
        # Initialize an empty plot
        self.line4, = self.ax.plot([], [], lw=2, color="purple")

        # Set plot limits and labels
        self.ax.set_xlim(0, self.max_points)
        self.ax.set_ylim(0, 11)
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('mBar')

    @QtCore.pyqtSlot(list)
    def update_plot(self, pressure_values):
        if pressure_values:
            # Update x_data and y_data with the newest value
            # Append new x (time) point
            if self.x_data == []:
                self.x_data.append(0)
            else:
                self.x_data.append(self.x_data[-1] + 1)

            # Limit the x_data size
            if len(self.x_data) > self.max_points:
                self.x_data = self.x_data[-self.max_points:]

            # Convert and append new y (pressure) points
            for i in range(4):
                pressure_values[i] = (
                    float(pressure_values[i]) - 203.53) / 0.8248 / 100
                p_data = getattr(self, f'p{i+1}_data')
                p_data.append(pressure_values[i])

                # Limit the p_data size
                if len(p_data) > self.max_points:
                    setattr(self, f'p{i+1}_data', p_data[-self.max_points:])

            # check this for time lag
            if self.parent.saving:
                with open(self.parent.save_path, "a") as f:
                    f.write(f"{time.strftime('%H:%M:%S')}, {pressure_values[0]}, {
                            pressure_values[1]}, {pressure_values[2]}, {pressure_values[3]}\n")

            # Check if venting is complete
            if self.parent.vent_flag:
                logging.info(f"Pressure 3: {pressure_values[2]}")
                if pressure_values[2] < 0.1:
                    logging.info("Venting complete")

            # Update the plot's data without clearing
            if self.parent.pressure1RadioButton.isChecked():
                self.line1.set_data(self.x_data, self.p1_data)
            else:
                self.line1.set_data([], [])
            if self.parent.pressure2RadioButton.isChecked():
                self.line2.set_data(self.x_data, self.p2_data)
            else:
                self.line2.set_data([], [])
            if self.parent.pressure3RadioButton.isChecked():
                self.line3.set_data(self.x_data, self.p3_data)
            else:
                self.line3.set_data([], [])
            if self.parent.pressure4RadioButton.isChecked():
                self.line4.set_data(self.x_data, self.p4_data)
            else:
                self.line4.set_data([], [])

            # Adjust limits if necessary
            if len(self.x_data) >= self.max_points:
                self.ax.set_xlim(self.x_data[0], self.x_data[-1])
            # Ensure y lim
            self.ax.set_ylim(0, 11)

            # Redraw the canvas with the new data
            self.draw()


class ArduinoWorker(QtCore.QThread):
    # Signal to send data to the main thread
    data_signal = QtCore.pyqtSignal(list)
    command_signal = QtCore.pyqtSignal(str)
    set_valve_signal = QtCore.pyqtSignal(list)
    get_valve_signal = QtCore.pyqtSignal()
    valve_states_updated = QtCore.pyqtSignal()

    def __init__(self, parent, port, mode, verbose):
        super().__init__()
        self.controller = ArduinoController(
            port=port, mode=mode, verbose=verbose)
        self.running = True
        self.parent = parent
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.poll_readings)
        self.mutex = QtCore.QMutex()

    def run(self):
        """Run the Arduino controller in a background thread."""
        self.controller.start()

    def start_timer(self):
        self.timer.start(self.parent.valveCheckInterval)

    def stop_timer(self):
        self.timer.stop()

    def stop(self):
        with QtCore.QMutexLocker(self.mutex):
            """Stop the worker and the Arduino controller."""
            self.running = False
            # if last step was pressurised then depressurise?
            self.controller.send_reset()
            self.controller.serial_connected = False
            self.quit()
            self.wait(100)

    def isConnected(self):
        # logging.info(f"Connection is {self.controller.serial_connected}")
        return self.controller.serial_connected

    @QtCore.pyqtSlot()
    def get_valve_states(self):
        with QtCore.QMutexLocker(self.mutex):
            self.parent.valveStates = self.controller.get_valve_states()
            self.valve_states_updated.emit()

    def poll_readings(self):
        if self.controller.serial_connected:
            with QtCore.QMutexLocker(self.mutex):
                if self.controller.get_readings():
                    data = self.controller.readings  # Get new readings from Arduino
                    # Emit signal with data to update the graph
                    self.data_signal.emit(data)
                # mode = self.controller.get_mode()
                # ttl_state = self.controller.get_ttl_state()
                # logging.info(f"mode: {mode} ttl: {ttl_state}")

    def depressurise(self):
        with QtCore.QMutexLocker(self.mutex):
            self.controller.send_depressurise()

    def set_valve_states(self, states):
        with QtCore.QMutexLocker(self.mutex):
            self.controller.set_valves(states)

    def send_command(self, command):
        with QtCore.QMutexLocker(self.mutex):
            if command == "RESET":
                self.controller.send_reset()
                logging.info("Resetting Arduino")
            elif command == "QUICK_VENT":
                self.controller.send_depressurise()
                logging.info("Depressurising Arduino")
            elif command == "RESTART":
                self.controller.start()
            elif command == "TTLDISABLE":
                self.controller.disableTTL()
            else:
                logging.info("Invalid command for arduino")


class MotorWorker(QtCore.QThread):
    command_signal = QtCore.pyqtSignal(int)
    shutdown_signal = QtCore.pyqtSignal()
    calibrate_signal = QtCore.pyqtSignal()
    ascent_signal = QtCore.pyqtSignal()
    top_signal = QtCore.pyqtSignal()

    def __init__(self, parent, port):
        super().__init__()
        self.motor = MotorController(port=port)
        self.parent = parent
        self.running = False
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.poll_position)
        self.calibrated = False
        self.mutex = QtCore.QMutex()
        self.top_position = "INIT"

    @QtCore.pyqtSlot()
    def stop(self):
        with QtCore.QMutexLocker(self.mutex):
            if self.motor.serial_connected:
                self.motor.shutdown()

    @QtCore.pyqtSlot()
    def calibrate(self):
        """Handle command signals to control the Arduino (e.g., turn on/off valves)."""
        with QtCore.QMutexLocker(self.mutex):
            if self.motor.serial_connected:
                self.top_position = "INIT"
                self.motor.calibrate()
                # logging.info("Calibrating motor, please wait")

    def poll_position(self):
        # logging.info("Polling motor position")
        with QtCore.QMutexLocker(self.mutex):
            try:
                if self.running:
                    if self.motor.serial_connected:
                        self.calibrated = self.motor.check_calibrated()
                        if self.calibrated:
                            if self.top_position == "INIT":
                                self.top_position = self.motor.get_top_position()
                                # logging.info(f"Top position: {
                                #             self.top_position}")
                            position = self.motor.get_current_position()
                            position = (int(self.top_position) - int(position))
                            position = self.steps_to_mm(position)
                            # logging.info(f"Current motor position: {position}")
                            self.parent.curMotorPosEdit.setText(str(position))
                    self.parent.UIUpdateArdConnection()
                else:
                    self.timer.stop()
                    self.running = False
                    self.motor.reset()
                    # self.stop()
            except Exception as e:
                logging.error(f"Error polling motor position: {e}")
                self.timer.stop()
                self.running = False
                self.motor.reset()
                # self.stop()

    def is_connected(self):
        return self.motor.serial_connected

    @QtCore.pyqtSlot(int)
    def move_to_target(self, target):
        with QtCore.QMutexLocker(self.mutex):
            if self.motor.serial_connected:
                logging.info(f"Moving motor to position {target}")
                target = self.mm_to_steps(target)
                self.motor.move_to_position(target)

    def start_timer(self):
        self.timer.start(10)

    def connect(self):
        self.motor.start()
        self.running = True

    @QtCore.pyqtSlot()
    def ascent(self):
        with QtCore.QMutexLocker(self.mutex):
            if self.motor.serial_connected:
                logging.info("Ascent")
                self.motor.ascent()

    @QtCore.pyqtSlot()
    def to_top(self):
        with QtCore.QMutexLocker(self.mutex):
            if self.motor.serial_connected:
                logging.info("To Top")
                self.motor.to_top()

    def steps_to_mm(self, steps):
        # 1mm = 6400 steps
        return steps / 6400

    def mm_to_steps(self, mm):
        return mm * 6400


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setup_logging()

    def setup_logging(self):
        # Initialize the logger
        self.logTextBox = QTextEditLogger(self.textBrowser)
        self.logTextBox.setFormatter(logging.Formatter('%(message)s'))
        # %(asctime)s %(levelname)s %(module)s %(funcName)s

        logging.getLogger().addHandler(self.logTextBox)
        logging.getLogger().setLevel(logging.DEBUG)

        """
        # Log to file
        fh = logging.FileHandler('my-log.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'))
        logging.getLogger().addHandler(fh)
        """

    def closeEvent(self, event):

        try:
            if self.arduino_worker:
                self.arduino_worker.stop()
                if self.verbosity:
                    print("Controller stopped")
        except AttributeError:
            pass
        try:
            if self.motor_worker:
                self.motor_worker.stop()
                if self.verbosity:
                    print("Motor stopped")
        except AttributeError:
            pass
        if self.verbosity:
            print("Application is closing...")

        """       
        # Remove and close logging handlers
        logger = logging.getLogger()
        handlers = logger.handlers[:]
        for handler in handlers:
            handler.close()
            logger.removeHandler(handler)

        # Ensure QTextEditLogger is properly closed
        if hasattr(self, 'logTextBox'):
            self.logTextBox.close()
        """
        # Call the base class method to ensure the window closes
        event.accept()


if __name__ == "__main__":
    global_stylesheet = """
        QPushButton:disabled {
            background-color: grey;
            color: white;
        }
        QLineEdit:disabled {
            background-color: grey;
            color: black;
        }
        QSpinBox:disabled {
            background-color: grey;
            color: black;
        }
        """

    app = QtWidgets.QApplication(sys.argv)

    app.setStyleSheet(global_stylesheet)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
