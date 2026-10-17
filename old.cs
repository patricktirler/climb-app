namespace ClimbApp
{
    public class SortedStringSet
    {
        public IReadOnlyList<string> Items { get; }
        public int Count { get; }
    }

    public class HierarchyNode
    {
        public string Name { get; }
        public ReadOnlyCollection<HierarchyNode> Children { get; }
        public SortedStringSet Leaves { get; }
    }

    public class HierarchyCollection
    {
        public IReadOnlyCollection<HierarchyNode> Roots { get; }
        public int Count { get; }
    }

    public interface IActivityCollection
    {
        DateTime StartDate { get; }
        DateTime EndDate { get; }
        int ActivityCount { get; }
        int ActivityCountOn(DateTime date);
        void Clear();
    }

    public abstract class ActivityCollection<T> : IActivityCollection where T : class, new()
    {
        protected List<T> Items { get; }
        public int Count { get; }
        public virtual DateTime StartDate { get; }
        public virtual DateTime EndDate { get; }
        public abstract int ActivityCount { get; }
    }

    public class ClimbDatabase
    {
        public Training Training { get; }
        public ClimbingDays ClimbingDays { get; }
        public AlpineClimbs AlpineClimbs { get; }
        public MountainTours MountainTours { get; }
        public Trips Trips { get; }
        public DailyNotes DailyNotes { get; }

        public HierarchyCollection ClimbingAreas { get; private set; }
        public HierarchyCollection MountainMassifs { get; private set; }
        public HierarchyCollection MountainRanges { get; private set; }

        public DateTime StartDate { get; }
        public DateTime EndDate { get; }
        public int WeekCount { get; }
        public int EntryCount { get; }
        public int ActivityCount { get; }
    }

    public class Training : IActivityCollection
    {
        public TrainingSessions TrainingSessions { get; }
        public FitnessSessions FitnessSessions { get; }

        public SortedStringSet ClimbingGyms { get; }
        public int ActivityCountOn(DateTime d) => 0;
        public DateTime StartDate { get; }
        public DateTime EndDate { get; }
    }

    public class TrainingSessions : ActivityCollection<TrainingSession>
    {
        public TrainingDatabase TrainingData { get; private set; }
        public override int ActivityCount { get; }
    }

    public class FitnessSessions : ActivityCollection<FitnessSession>
    {
        public override int ActivityCount { get; }
    }

    public class TrainingSession
    {
        public string ClimbingGym { get; set; }
        public string TrainingPhase { get; set; }
        public TrainingDetails Details { get; set; }
        public string Info { get; set; }
        public int Session { get; set; }
        public DateTime Date { get; set; }
        public Selection Selection { get; }
    }

    public class FitnessSession
    {
        public string Type { get; set; }
        public int Duration { get; set; }
        public double Distance { get; set; }
        public string Info { get; set; }
        public int Session { get; set; }
        public DateTime Date { get; set; }
        public string DistanceUnit { get; }
        public Selection Selection { get; }
    }

    public class TrainingDatabase
    {
        public IReadOnlyList<TrainingMethod> Methods { get; }
    }

    public class TrainingMethod
    {
        public string Discipline { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public SortedStringSet Holds { get; }
    }

    public class TrainingDetails
    {
        public IReadOnlyList<TrainingDetail> Details { get; }
    }

    public class TrainingDetail
    {
        public TrainingMethod Method { get; set; }
        public int Duration { get; set; }
        public int Repetitions { get; set; }
        public int Rest { get; set; }
        public string DeviceHold { get; set; }
        public string Info { get; set; }
    }

    public class ClimbingDays : ActivityCollection<ClimbingDay>
    {
        public override int ActivityCount { get; }
    }

    public class ClimbingDay
    {
        public string ClimbingArea { get; set; }
        public string Crag { get; set; }
        public string Sector { get; set; }
        public string Discipline { get; set; }
        public string Partner { get; set; }
        public string Info { get; set; }
        public Attachment Attachment { get; set; }
        public int Session { get; set; }
        public DateTime Date { get; set; }
        public string[] Partners { get; }
        public Selection Selection { get; }
    }

    public class AlpineClimbs : ActivityCollection<AlpineClimb>
    {
        public override int ActivityCount { get; }
    }

    public class AlpineClimb
    {
        public string Type { get; set; }
        public string MountainMassif { get; set; }
        public string MountainWall { get; set; }
        public string Name { get; set; }
        public string Orientation { get; set; }
        public Difficulty Difficulty { get; set; }
        public int ClimbingMeters { get; set; }
        public int PitchCount { get; set; }
        public string Style { get; set; }
        public string Partner { get; set; }
        public bool FirstAscent { get; set; }
        public DateTime ClimbingTime { get; set; }
        public string Info { get; set; }
        public int Rating { get; set; }
        public TourRouteAlpine Route { get; set; }
        public Attachment Attachment { get; set; }
        public int Session { get; set; }
        public DateTime Date { get; set; }
        public DateTime DateTo { get; set; }
        public bool MultiDayTour { get; }
        public string[] Partners { get; }
        public Selection Selection { get; }
    }

    public class MountainTours : ActivityCollection<MountainTour>
    {
        public override int ActivityCount { get; }
    }

    public class MountainTour
    {
        public string Type { get; set; }
        public string MountainRange { get; set; }
        public string TourName { get; set; }
        public int ElevationGain { get; set; }
        public int Elevation { get; set; }
        public DateTime Time { get; set; }
        public string Partner { get; set; }
        public string Info { get; set; }
        public RoutePath Route { get; set; }
        public Attachment Attachment { get; set; }
        public int Session { get; set; }
        public DateTime Date { get; set; }
        public DateTime DateTo { get; set; }
        public bool MultiDayTour { get; }
        public string[] Partners { get; }
        public Selection Selection { get; }
    }

    public class Trips : ActivityCollection<Trip>
    {
        public override int ActivityCount { get; }
    }

    public class Trip
    {
        public string Name { get; set; }
        public string Destination { get; set; }
        public string Country { get; set; }
        public string Type { get; set; }
        public int Duration { get; set; }
        public string Info { get; set; }
        public Attachment Attachment { get; set; }
        public int Session { get; set; }
        public DateTime Date { get; set; }
        public DateTime DateTo { get; set; }
        public int ElevationGain { get; set; }
        public bool MultiDayTour { get; }
        public Selection Selection { get; }
    }

    public class DailyNotes : ActivityCollection<DailyNote>
    {
        public override int ActivityCount { get; }
    }

    public class DailyNote
    {
        public DateTime Date { get; set; }
        public string Note { get; set; }
        public int Session { get; set; }
        public Selection Selection { get; }
    }

    public class Difficulty
    {
        public string UIAA { get; set; }
        public string French { get; set; }
        public string WI { get; set; }
        public string M { get; set; }
        public int Numeric { get; set; }
    }
}