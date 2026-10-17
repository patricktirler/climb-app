"""Data models for the Climb App."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
import json


@dataclass
class Difficulty:
    """Climbing difficulty grade."""
    UIAA: Optional[str] = None
    French: Optional[str] = None
    WI: Optional[str] = None
    M: Optional[str] = None
    Numeric: Optional[int] = None


@dataclass
class RockClimb:
    """Record for a single climbing day session."""
    Date: datetime
    ClimbingArea: str
    Crag: str
    Sector: str
    Discipline: str
    Partner: str = ""
    Info: str = ""
    id: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            'Date': self.Date.isoformat(),
            'ClimbingArea': self.ClimbingArea,
            'Crag': self.Crag,
            'Sector': self.Sector,
            'Discipline': self.Discipline,
            'Partner': self.Partner,
            'Info': self.Info,
            'id': self.id,
            'type': 'RockClimb'
        }

    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        data.pop('type', None)
        if isinstance(data.get('Date'), str):
            data['Date'] = datetime.fromisoformat(data['Date'])
        return cls(**data)


@dataclass
class AlpineClimb:
    """Record for an alpine climbing expedition."""
    Date: datetime
    Type: str
    Name: str
    MountainMassif: str
    Difficulty: Difficulty
    ClimbingMeters: int = 0
    PitchCount: int = 0
    MountainWall: str = ""
    Orientation: str = ""
    Style: str = ""
    Partner: str = ""
    FirstAscent: bool = False
    Rating: int = 0
    Info: str = ""
    DateTo: Optional[datetime] = None
    id: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            'Date': self.Date.isoformat(),
            'DateTo': self.DateTo.isoformat() if self.DateTo else None,
            'Type': self.Type,
            'Name': self.Name,
            'MountainMassif': self.MountainMassif,
            'Difficulty': asdict(self.Difficulty),
            'ClimbingMeters': self.ClimbingMeters,
            'PitchCount': self.PitchCount,
            'MountainWall': self.MountainWall,
            'Orientation': self.Orientation,
            'Style': self.Style,
            'Partner': self.Partner,
            'FirstAscent': self.FirstAscent,
            'Rating': self.Rating,
            'Info': self.Info,
            'id': self.id,
            'type': 'AlpineClimb'
        }

    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        difficulty_data = data.pop('Difficulty', {})
        data['Difficulty'] = Difficulty(**difficulty_data)
        data.pop('type', None)
        if isinstance(data.get('Date'), str):
            data['Date'] = datetime.fromisoformat(data['Date'])
        if isinstance(data.get('DateTo'), str):
            data['DateTo'] = datetime.fromisoformat(data['DateTo'])
        return cls(**data)


@dataclass
class MountainTour:
    """Record for a mountain tour."""
    Date: datetime
    Type: str
    TourName: str
    MountainRange: str
    ElevationGain: int = 0
    Elevation: int = 0
    Partner: str = ""
    Info: str = ""
    DateTo: Optional[datetime] = None
    id: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            'Date': self.Date.isoformat(),
            'DateTo': self.DateTo.isoformat() if self.DateTo else None,
            'Type': self.Type,
            'TourName': self.TourName,
            'MountainRange': self.MountainRange,
            'ElevationGain': self.ElevationGain,
            'Elevation': self.Elevation,
            'Partner': self.Partner,
            'Info': self.Info,
            'id': self.id,
            'type': 'MountainTour'
        }

    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        data.pop('type', None)
        if isinstance(data.get('Date'), str):
            data['Date'] = datetime.fromisoformat(data['Date'])
        if isinstance(data.get('DateTo'), str):
            data['DateTo'] = datetime.fromisoformat(data['DateTo'])
        return cls(**data)


@dataclass
class Trip:
    """Record for a climbing trip."""
    Date: datetime
    Destination: str
    Country: str
    Duration: int = 0
    ElevationGain: int = 0
    Info: str = ""
    DateTo: Optional[datetime] = None
    id: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            'Date': self.Date.isoformat(),
            'DateTo': self.DateTo.isoformat() if self.DateTo else None,
            'Destination': self.Destination,
            'Country': self.Country,
            'Duration': self.Duration,
            'ElevationGain': self.ElevationGain,
            'Info': self.Info,
            'id': self.id,
            'type': 'Trip'
        }

    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        data.pop('type', None)
        if isinstance(data.get('Date'), str):
            data['Date'] = datetime.fromisoformat(data['Date'])
        if isinstance(data.get('DateTo'), str):
            data['DateTo'] = datetime.fromisoformat(data['DateTo'])
        return cls(**data)


@dataclass
class DailyNote:
    """Record for a daily note."""
    Date: datetime
    Note: str
    id: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            'Date': self.Date.isoformat(),
            'Note': self.Note,
            'id': self.id,
            'type': 'DailyNote'
        }

    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        data.pop('type', None)
        if isinstance(data.get('Date'), str):
            data['Date'] = datetime.fromisoformat(data['Date'])
        return cls(**data)


@dataclass
class TrainingSession:
    """Record for a training session."""
    Date: datetime
    ClimbingGym: str
    TrainingType: str = ""
    Info: str = ""
    id: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            'Date': self.Date.isoformat(),
            'ClimbingGym': self.ClimbingGym,
            'TrainingType': self.TrainingType,
            'Info': self.Info,
            'id': self.id,
            'type': 'TrainingSession'
        }

    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        data.pop('type', None)
        if isinstance(data.get('Date'), str):
            data['Date'] = datetime.fromisoformat(data['Date'])
        return cls(**data)
