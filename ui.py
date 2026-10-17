"""UI components for the Climb App."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QDateTimeEdit, QTextEdit, QCheckBox, QComboBox, QPushButton,
    QApplication, QTableWidget, QTableWidgetItem, QWidget, QTabWidget,
    QScrollArea, QGroupBox, QFormLayout, QMessageBox, QMenuBar, QMenu, QDoubleSpinBox,
    QFileDialog, QProgressDialog
)
from PySide6.QtCore import Qt, QDateTime, Signal, QSize
from PySide6.QtGui import QIcon, QFont
from models import RockClimb, AlpineClimb, MountainTour, Trip, DailyNote, TrainingSession, Difficulty
from datetime import datetime


class AddActivityDialog(QDialog):
    """Dialog for adding climbing activities."""
    
    def __init__(self, parent=None, activity_type: str = "ClimbingDay", activity=None):
        super().__init__(parent)
        self.activity_type = activity_type
        self.activity = activity
        self.init_ui()
        if activity:
            self.load_activity(activity)
    
    def init_ui(self):
        """Initialize the dialog UI."""
        dialog_title = f"{"Edit" if self.activity else "Add"} {self.activity_type}"
        self.setWindowTitle(dialog_title)
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.setStyleSheet(self.get_dialog_style())
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title = QLabel(dialog_title)
        title_font = QFont("Arial", 14, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #2c3e50;")
        main_layout.addWidget(title)
        
        # Separator
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)
        
        # Content in scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: white; }")
        
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        if self.activity_type == "RockClimb":
            self.ui_rock_climb(layout)
        elif self.activity_type == "AlpineClimb":
            self.ui_alpine_climb(layout)
        elif self.activity_type == "MountainTour":
            self.ui_mountain_tour(layout)
        elif self.activity_type == "Trip":
            self.ui_trip(layout)
        elif self.activity_type == "DailyNote":
            self.ui_daily_note(layout)
        elif self.activity_type == "TrainingSession":
            self.ui_training_session(layout)
        
        layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        save_btn = QPushButton("✓ Save")
        cancel_btn = QPushButton("✕ Cancel")
        
        save_btn.setMinimumHeight(40)
        cancel_btn.setMinimumHeight(40)
        save_btn.setMinimumWidth(120)
        cancel_btn.setMinimumWidth(120)
        
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #6c7a7b;
            }
        """)
        
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def get_dialog_style(self):
        """Return CSS for dialog styling."""
        return """
        QDialog {
            background-color: #fafafa;
        }
        QLabel {
            color: #333;
        }
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 3px;
            padding: 5px;
            color: #333;
        }
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus {
            border: 2px solid #27ae60;
            background-color: #fafafa;
        }
        QGroupBox {
            color: #333;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
        QCheckBox {
            color: #333;
            spacing: 5px;
        }
        """
    
    def ui_rock_climb(self, layout):
        """Create UI for RockClimb."""
        group = QGroupBox("Climbing Session Details")
        form = QFormLayout(group)
        form.setSpacing(10)
        form.setContentsMargins(10, 10, 10, 10)
        
        self.date = QDateTimeEdit()
        self.date.setDateTime(QDateTime.currentDateTime())
        self.date.setCalendarPopup(True)
        
        self.climbing_area = QLineEdit()
        self.climbing_area.setPlaceholderText("e.g., Fontainebleau")
        
        self.crag = QLineEdit()
        self.crag.setPlaceholderText("e.g., Trois Pignons")
        
        self.sector = QLineEdit()
        self.sector.setPlaceholderText("e.g., Apremont")
        
        self.discipline = QLineEdit()
        self.discipline.setPlaceholderText("e.g., Boulder, Sport, Trad")
        
        self.partner = QLineEdit()
        self.partner.setPlaceholderText("Climbing partner name")
        
        self.info = QTextEdit()
        self.info.setPlaceholderText("Session notes...")
        self.info.setMaximumHeight(100)
        
        form.addRow("Date & Time:", self.date)
        form.addRow("Climbing Area:", self.climbing_area)
        form.addRow("Crag:", self.crag)
        form.addRow("Sector:", self.sector)
        form.addRow("Discipline:", self.discipline)
        form.addRow("Partner:", self.partner)
        form.addRow("Notes:", self.info)
        
        layout.addWidget(group)
    
    def ui_alpine_climb(self, layout):
        """Create UI for AlpineClimb."""
        form = QFormLayout()
        self.date = QDateTimeEdit()
        self.date.setDateTime(QDateTime.currentDateTime())
        self.date_to = QDateTimeEdit()
        self.date_to.setDateTime(QDateTime.currentDateTime())
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Rock Climb", "Ice Climb", "Mixed Climb"])
        self.name = QLineEdit()
        self.mountain_massif = QLineEdit()
        self.mountain_wall = QLineEdit()
        self.orientation = QLineEdit()
        self.climbing_meters = QSpinBox()
        self.climbing_meters.setMaximum(10000)
        self.pitch_count = QSpinBox()
        self.style = QLineEdit()
        self.partner = QLineEdit()
        self.first_ascent = QCheckBox()
        self.rating = QSpinBox()
        self.rating.setMaximum(10)
        self.info = QTextEdit()
        self.session = QSpinBox()
        
        # Difficulty
        self.difficulty_uiaa = QLineEdit()
        self.difficulty_french = QLineEdit()
        self.difficulty_wi = QLineEdit()
        self.difficulty_m = QLineEdit()
        self.difficulty_numeric = QSpinBox()
        
        form.addRow("Date:", self.date)
        form.addRow("Date To:", self.date_to)
        form.addRow("Type:", self.type_combo)
        form.addRow("Name:", self.name)
        form.addRow("Mountain Massif:", self.mountain_massif)
        form.addRow("Mountain Wall:", self.mountain_wall)
        form.addRow("Orientation:", self.orientation)
        form.addRow("Climbing Meters:", self.climbing_meters)
        form.addRow("Pitch Count:", self.pitch_count)
        form.addRow("Style:", self.style)
        form.addRow("Partner:", self.partner)
        form.addRow("First Ascent:", self.first_ascent)
        form.addRow("Rating:", self.rating)
        form.addRow("Session:", self.session)
        form.addRow("Info:", self.info)
        
        # Difficulty group
        diff_group = QGroupBox("Difficulty")
        diff_layout = QFormLayout()
        diff_layout.addRow("UIAA:", self.difficulty_uiaa)
        diff_layout.addRow("French:", self.difficulty_french)
        diff_layout.addRow("WI:", self.difficulty_wi)
        diff_layout.addRow("M:", self.difficulty_m)
        diff_layout.addRow("Numeric:", self.difficulty_numeric)
        diff_group.setLayout(diff_layout)
        
        layout.addLayout(form)
        layout.addWidget(diff_group)
    
    def ui_mountain_tour(self, layout):
        """Create UI for MountainTour."""
        form = QFormLayout()
        self.date = QDateTimeEdit()
        self.date.setDateTime(QDateTime.currentDateTime())
        self.date_to = QDateTimeEdit()
        self.date_to.setDateTime(QDateTime.currentDateTime())
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Hiking", "Mountaineering", "Ski Touring"])
        self.tour_name = QLineEdit()
        self.mountain_range = QLineEdit()
        self.elevation_gain = QSpinBox()
        self.elevation_gain.setMaximum(10000)
        self.elevation = QSpinBox()
        self.elevation.setMaximum(10000)
        self.partner = QLineEdit()
        self.info = QTextEdit()
        self.session = QSpinBox()
        
        form.addRow("Date:", self.date)
        form.addRow("Date To:", self.date_to)
        form.addRow("Type:", self.type_combo)
        form.addRow("Tour Name:", self.tour_name)
        form.addRow("Mountain Range:", self.mountain_range)
        form.addRow("Elevation Gain:", self.elevation_gain)
        form.addRow("Elevation:", self.elevation)
        form.addRow("Partner:", self.partner)
        form.addRow("Session:", self.session)
        form.addRow("Info:", self.info)
        layout.addLayout(form)
    
    def ui_trip(self, layout):
        """Create UI for Trip."""
        form = QFormLayout()
        self.date = QDateTimeEdit()
        self.date.setDateTime(QDateTime.currentDateTime())
        self.date_to = QDateTimeEdit()
        self.date_to.setDateTime(QDateTime.currentDateTime())
        self.destination = QLineEdit()
        self.country = QLineEdit()
        self.duration = QSpinBox()
        self.duration.setMaximum(365)
        self.elevation_gain = QSpinBox()
        self.elevation_gain.setMaximum(100000)
        self.info = QTextEdit()
        
        form.addRow("Date:", self.date)
        form.addRow("Date To:", self.date_to)
        form.addRow("Destination:", self.destination)
        form.addRow("Country:", self.country)
        form.addRow("Duration (days):", self.duration)
        form.addRow("Elevation Gain:", self.elevation_gain)
        form.addRow("Info:", self.info)
        layout.addLayout(form)
    
    def ui_daily_note(self, layout):
        """Create UI for DailyNote."""
        group = QGroupBox("Daily Note")
        form = QFormLayout(group)
        form.setSpacing(10)
        form.setContentsMargins(10, 10, 10, 10)
        
        self.date = QDateTimeEdit()
        self.date.setDateTime(QDateTime.currentDateTime())
        self.date.setCalendarPopup(True)
        
        self.note = QTextEdit()
        self.note.setPlaceholderText("Write your daily notes here...")
        self.note.setMinimumHeight(150)
        
        form.addRow("Date & Time:", self.date)
        form.addRow("Note:", self.note)
        layout.addWidget(group)
    
    def ui_training_session(self, layout):
        """Create UI for TrainingSession."""
        group = QGroupBox("Training Session")
        form = QFormLayout(group)
        form.setSpacing(10)
        form.setContentsMargins(10, 10, 10, 10)
        
        self.date = QDateTimeEdit()
        self.date.setDateTime(QDateTime.currentDateTime())
        self.date.setCalendarPopup(True)
        
        self.climbing_gym = QLineEdit()
        self.climbing_gym.setPlaceholderText("e.g., Local Gym")
        
        self.training_type = QLineEdit()
        self.training_type.setPlaceholderText("e.g., Endurance, Strength, Technique")
        
        self.info = QTextEdit()
        self.info.setPlaceholderText("Training details and notes...")
        self.info.setMaximumHeight(100)
        
        form.addRow("Date & Time:", self.date)
        form.addRow("Climbing Gym:", self.climbing_gym)
        form.addRow("Training Type:", self.training_type)
        form.addRow("Notes:", self.info)
        layout.addWidget(group)
    
    def load_activity(self, activity):
        """Load existing activity data into the form."""
        if isinstance(activity, RockClimb):
            self.date.setDateTime(QDateTime(activity.Date))
            self.climbing_area.setText(activity.ClimbingArea)
            self.crag.setText(activity.Crag)
            self.sector.setText(activity.Sector)
            self.discipline.setText(activity.Discipline)
            self.partner.setText(activity.Partner)
            self.info.setPlainText(activity.Info)
        elif isinstance(activity, AlpineClimb):
            self.date.setDateTime(QDateTime(activity.Date))
            if activity.DateTo:
                self.date_to.setDateTime(QDateTime(activity.DateTo))
            self.type_combo.setCurrentText(activity.Type)
            self.name.setText(activity.Name)
            self.mountain_massif.setText(activity.MountainMassif)
            self.mountain_wall.setText(activity.MountainWall)
            self.orientation.setText(activity.Orientation)
            self.climbing_meters.setValue(activity.ClimbingMeters)
            self.pitch_count.setValue(activity.PitchCount)
            self.style.setText(activity.Style)
            self.partner.setText(activity.Partner)
            self.first_ascent.setChecked(activity.FirstAscent)
            self.rating.setValue(activity.Rating)
            self.info.setPlainText(activity.Info)
            if activity.Difficulty:
                self.difficulty_uiaa.setText(activity.Difficulty.UIAA or "")
                self.difficulty_french.setText(activity.Difficulty.French or "")
                self.difficulty_wi.setText(activity.Difficulty.WI or "")
                self.difficulty_m.setText(activity.Difficulty.M or "")
                if activity.Difficulty.Numeric:
                    self.difficulty_numeric.setValue(activity.Difficulty.Numeric)
        elif isinstance(activity, MountainTour):
            self.date.setDateTime(QDateTime(activity.Date))
            if activity.DateTo:
                self.date_to.setDateTime(QDateTime(activity.DateTo))
            self.type_combo.setCurrentText(activity.Type)
            self.tour_name.setText(activity.TourName)
            self.mountain_range.setText(activity.MountainRange)
            self.elevation_gain.setValue(activity.ElevationGain)
            self.elevation.setValue(activity.Elevation)
            self.partner.setText(activity.Partner)
            self.info.setPlainText(activity.Info)
        elif isinstance(activity, Trip):
            self.date.setDateTime(QDateTime(activity.Date))
            if activity.DateTo:
                self.date_to.setDateTime(QDateTime(activity.DateTo))
            self.destination.setText(activity.Destination)
            self.country.setText(activity.Country)
            self.duration.setValue(activity.Duration)
            self.elevation_gain.setValue(activity.ElevationGain)
            self.info.setPlainText(activity.Info)
        elif isinstance(activity, DailyNote):
            self.date.setDateTime(QDateTime(activity.Date))
            self.note.setPlainText(activity.Note)
        elif isinstance(activity, TrainingSession):
            self.date.setDateTime(QDateTime(activity.Date))
            self.climbing_gym.setText(activity.ClimbingGym)
            self.training_type.setText(activity.TrainingType)
            self.info.setPlainText(activity.Info)
    
    def get_activity(self):
        """Return the activity object based on the form data."""
        date = self.date.dateTime().toPython()
        
        if self.activity_type == "RockClimb":
            return RockClimb(
                Date=date,
                ClimbingArea=self.climbing_area.text(),
                Crag=self.crag.text(),
                Sector=self.sector.text(),
                Discipline=self.discipline.text(),
                Partner=self.partner.text(),
                Info=self.info.toPlainText(),
                id=self.activity.id if self.activity else ""
            )
        elif self.activity_type == "AlpineClimb":
            date_to = self.date_to.dateTime().toPython() if self.date_to.dateTime().isValid() else None
            difficulty = Difficulty(
                UIAA=self.difficulty_uiaa.text() or None,
                French=self.difficulty_french.text() or None,
                WI=self.difficulty_wi.text() or None,
                M=self.difficulty_m.text() or None,
                Numeric=self.difficulty_numeric.value() if self.difficulty_numeric.value() > 0 else None
            )
            return AlpineClimb(
                Date=date,
                Type=self.type_combo.currentText(),
                Name=self.name.text(),
                MountainMassif=self.mountain_massif.text(),
                MountainWall=self.mountain_wall.text(),
                Orientation=self.orientation.text(),
                ClimbingMeters=self.climbing_meters.value(),
                PitchCount=self.pitch_count.value(),
                Style=self.style.text(),
                Partner=self.partner.text(),
                FirstAscent=self.first_ascent.isChecked(),
                Rating=self.rating.value(),
                Info=self.info.toPlainText(),
                DateTo=date_to,
                Difficulty=difficulty,
                id=self.activity.id if self.activity else ""
            )
        elif self.activity_type == "MountainTour":
            date_to = self.date_to.dateTime().toPython() if self.date_to.dateTime().isValid() else None
            return MountainTour(
                Date=date,
                Type=self.type_combo.currentText(),
                TourName=self.tour_name.text(),
                MountainRange=self.mountain_range.text(),
                ElevationGain=self.elevation_gain.value(),
                Elevation=self.elevation.value(),
                Partner=self.partner.text(),
                Info=self.info.toPlainText(),
                DateTo=date_to,
                id=self.activity.id if self.activity else ""
            )
        elif self.activity_type == "Trip":
            date_to = self.date_to.dateTime().toPython() if self.date_to.dateTime().isValid() else None
            return Trip(
                Date=date,
                Destination=self.destination.text(),
                Country=self.country.text(),
                Duration=self.duration.value(),
                ElevationGain=self.elevation_gain.value(),
                Info=self.info.toPlainText(),
                DateTo=date_to,
                id=self.activity.id if self.activity else ""
            )
        elif self.activity_type == "DailyNote":
            return DailyNote(
                Date=date,
                Note=self.note.toPlainText(),
                id=self.activity.id if self.activity else ""
            )
        elif self.activity_type == "TrainingSession":
            return TrainingSession(
                Date=date,
                ClimbingGym=self.climbing_gym.text(),
                TrainingType=self.training_type.text(),
                Info=self.info.toPlainText(),
                id=self.activity.id if self.activity else ""
            )
        return None


class SettingsDialog(QDialog):
    """Settings dialog with import functionality."""
    
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.init_ui()
    
    def init_ui(self):
        """Initialize the settings dialog UI."""
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setStyleSheet(self.get_dialog_style())
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title = QLabel("Application Settings")
        title_font = QFont("Arial", 14, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #2c3e50;")
        main_layout.addWidget(title)
        
        # Separator
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)
        
        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: white; }")
        
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Import section
        import_group = QGroupBox("Import")
        import_layout = QVBoxLayout(import_group)
        import_layout.setSpacing(10)
        
        import_label = QLabel("Import data from Climb App V1")
        import_label.setStyleSheet("font-weight: bold; color: #333;")
        import_layout.addWidget(import_label)
        
        info_label = QLabel(
            "Select a V1 data file to import all climbing activities, training sessions, "
            "and notes. Your existing data will be merged with the imported data."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 10pt;")
        import_layout.addWidget(info_label)
        
        import_btn = QPushButton("📂 Select V1 Data File")
        import_btn.setMinimumHeight(40)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
            }
        """)
        import_btn.clicked.connect(self.import_from_v1)
        import_layout.addWidget(import_btn)
        
        layout.addWidget(import_group)
        
        # About section
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout(about_group)
        
        app_name = QLabel("🧗 Climb App V2")
        app_name.setFont(QFont("Arial", 12, QFont.Bold))
        app_name.setStyleSheet("color: #2c3e50;")
        about_layout.addWidget(app_name)
        
        version_label = QLabel("Version: 2.0.0")
        version_label.setStyleSheet("color: #666;")
        about_layout.addWidget(version_label)
        
        about_text = QLabel(
            "A modern climbing activity tracker application.\n\n"
            "Track your climbing sessions, alpine climbs, mountain tours, training, and more."
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: #666; margin-top: 10px;")
        about_layout.addWidget(about_text)
        
        layout.addWidget(about_group)
        layout.addStretch()
        
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        close_btn = QPushButton("✓ Close")
        close_btn.setMinimumHeight(40)
        close_btn.setMinimumWidth(120)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def get_dialog_style(self):
        """Return CSS for dialog styling."""
        return """
        QDialog {
            background-color: #fafafa;
        }
        QLabel {
            color: #333;
        }
        QGroupBox {
            color: #333;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
        """
    
    def import_from_v1(self):
        """Open file dialog and import V1 data."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Climb App V1 Data File",
            "",
            "All Files (*);;Text Files (*.txt);;Data Files (*.dat)"
        )
        
        if not file_path:
            return
        
        # Import the data
        self.perform_import(file_path)
    
    def perform_import(self, file_path: str):
        """Perform the actual import of V1 data."""
        from import_v1 import import_v1_file
        
        # Import data
        activities_data = import_v1_file(file_path)
        
        # Convert dicts to model objects
        if self.db and activities_data:
            activities_to_add = []
            for activity_data in activities_data:
                activity_type = activity_data.get('type')
                try:
                    if activity_type == 'RockClimb':
                        activity = RockClimb.from_dict(activity_data)
                        activities_to_add.append(activity)
                    elif activity_type == 'AlpineClimb':
                        activity = AlpineClimb.from_dict(activity_data)
                        activities_to_add.append(activity)
                    elif activity_type == 'MountainTour':
                        activity = MountainTour.from_dict(activity_data)
                        activities_to_add.append(activity)
                    elif activity_type == 'Trip':
                        activity = Trip.from_dict(activity_data)
                        activities_to_add.append(activity)
                    elif activity_type == 'DailyNote':
                        activity = DailyNote.from_dict(activity_data)
                        activities_to_add.append(activity)
                    elif activity_type == 'TrainingSession':
                        activity = TrainingSession.from_dict(activity_data)
                        activities_to_add.append(activity)
                except Exception as e:
                    print(f"Error converting activity {activity_data}: {e}")
            
            # Add all activities at once (single save)
            if activities_to_add:
                self.db.add_activities_batch(activities_to_add)
        
        # Refresh parent window
        if self.parent_window:
            self.parent_window.calendar_widget.refresh()
            for activity_type in ["RockClimb", "AlpineClimb", "MountainTour", "Trip", "TrainingSession", "DailyNote"]:
                table = getattr(self.parent_window, f"table_{activity_type}", None)
                if table:
                    self.parent_window.refresh_table(activity_type, table)
        
        print(f"Successfully imported {len(activities_data)} activities from V1 data file.")
        print("Your data has been merged with the existing data in the application.")