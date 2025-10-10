import os;
from pathlib import Path;
from typing import List, Dict;

# DATA PATHS =================================================================

PROJECT_ROOT = Path(__file__).parent.parent;
PROCESSING_DIR = PROJECT_ROOT / "processing";
DATA_DIR = PROJECT_ROOT / "data";

RAW_DATA_DIR = DATA_DIR / "raw";
MIT_DIR = RAW_DATA_DIR / "mit-election-lab";
CENSUS_DIR = RAW_DATA_DIR / "census-shapefiles";

PROCESSED_DATA_DIR = DATA_DIR / "processed";
ELECTIONS_DIR = PROCESSED_DATA_DIR / "elections";
GEOJSON_DIR = PROCESSED_DATA_DIR / "geojson";
TILES_DIR = PROCESSED_DATA_DIR / "tiles";
COMBINED_DIR = PROCESSED_DATA_DIR / "combined";
EXPORTS_DIR = DATA_DIR / "exports";

for directory in [RAW_DATA_DIR, MIT_DIR, CENSUS_DIR, PROCESSED_DATA_DIR, ELECTIONS_DIR, GEOJSON_DIR, TILES_DIR, COMBINED_DIR, EXPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True);

# DATA SOURCES ==============================================================

MIT_DATAVERSE_DOI = "doi:10.7910/DVN/VOQCHQ"
MIT_DATAVERSE_API = "https://dataverse.harvard.edu/api/access/datafile"

CENSUS_BASE_URL = "https://www2.census.gov/geo/tiger"
CENSUS_YEAR = "2024"
CENSUS_URLS = {
    "county_500k": f"{CENSUS_BASE_URL}/GENZ{CENSUS_YEAR}/shp/cb_{CENSUS_YEAR}_us_county_500k.zip",
    "county_5m": f"{CENSUS_BASE_URL}/GENZ{CENSUS_YEAR}/shp/cb_{CENSUS_YEAR}_us_county_5m.zip",
    "county_20m": f"{CENSUS_BASE_URL}/GENZ{CENSUS_YEAR}/shp/cb_{CENSUS_YEAR}_us_county_20m.zip",
    "county_full": f"{CENSUS_BASE_URL}/TIGER{CENSUS_YEAR}/COUNTY/tl_{CENSUS_YEAR}_us_county.zip"
}

DEFAULT_CENSUS_URL = CENSUS_URLS["county_500k"]
DEFAULT_SHAPEFILE_NAME = f"cb_{CENSUS_YEAR}_us_county_500k"

# ELECTION CONFIG ===========================================================

ELECTION_YEARS = [2000, 2004, 2008, 2012, 2016, 2020, 2024]

# Major parties for filtering
MAJOR_PARTIES = ["DEMOCRAT", "REPUBLICAN"]

# Party colors
PARTY_COLORS = {
    "DEMOCRAT": "#0015BC",      # Blue
    "REPUBLICAN": "#FF0000",     # Red
    "LIBERTARIAN": "#FED105",    # Gold
    "GREEN": "#17AA5C",          # Green
    "OTHER": "#999999"           # Gray
}

# DATA PROCESSING CONFIG =====================================================

# Geographic parameters
TARGET_CRS = "EPSG:4326"  # WGS84 for GeoJSON
WEB_MERCATOR_CRS = "EPSG:3857"  # For web tiles

SIMPLIFY_TOLERANCE = 0.001  # ~100m resolution

MIN_TOTAL_VOTES = 10  # Minimum votes to consider valid
MAX_MISSING_COUNTIES_PERCENT = 5  # Max % of missing counties to allow


# NAME MAPPINGS ==============================================================

ELECTION_FILE_TEMPLATE = "elections_{year}.csv"
COUNTY_GEOJSON_TEMPLATE = "counties_{year}.geojson"
SWING_FILE_TEMPLATE = "swings_{year1}_to_{year2}.csv"
COMBINED_FILE_TEMPLATE = "election_data_{year}.geojson"

# Standardize column names from MIT data
MIT_COLUMN_MAPPING = {
    "county_fips": "fips",
    "county_name": "county",
    "state_po": "state_code",
    "candidatevotes": "votes",
    "totalvotes": "total_votes"
}

# Census shapefile columns to keep
CENSUS_COLUMNS_TO_KEEP = [
    "GEOID",      # FIPS code
    "NAME",       # County name
    "NAMELSAD",   # Full name
    "STATEFP",    # State FIPS
    "COUNTYFP",   # County FIPS
    "ALAND",      # Land area
    "AWATER",     # Water area
    "INTPTLAT",   # Centroid latitude
    "INTPTLON",   # Centroid longitude
    "geometry"    # Geometry
]

# SWING CALCULATION ========================================================

SWING_METHOD = "two_party"  # Options: "two_party", "margin", "percent_change"

# LOGGING CONFIG ===========================================================

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M"

# UTILS =====================================================================

def get_election_file_path(year: int, processed: bool = True) -> Path:
    """Get path to election data file for a given year."""
    if processed:
        return ELECTIONS_DIR / ELECTION_FILE_TEMPLATE.format(year=year)
    return MIT_DIR / f"election_{year}.csv"


def get_geojson_path(year: int) -> Path:
    """Get path to GeoJSON file for a given year."""
    return GEOJSON_DIR / COUNTY_GEOJSON_TEMPLATE.format(year=year)


def get_swing_file_path(year1: int, year2: int) -> Path:
    """Get path to swing calculation file."""
    return COMBINED_DIR / SWING_FILE_TEMPLATE.format(year1=year1, year2=year2)


def get_combined_file_path(year: int) -> Path:
    """Get path to combined election + geography file."""
    return COMBINED_DIR / COMBINED_FILE_TEMPLATE.format(year=year)


def validate_year(year: int) -> bool:
    """Check if year is a valid election year."""
    return year in ELECTION_YEARS


def get_adjacent_election_pairs() -> List[tuple]:
    """Get list of adjacent election year pairs for swing calculations."""
    return [(ELECTION_YEARS[i], ELECTION_YEARS[i+1]) 
            for i in range(len(ELECTION_YEARS)-1)]

# DATA QUALITY CHECKS ==================================================

def check_data_directory_structure() -> Dict[str, bool]:
    """Verify that all required directories exist."""
    dirs_to_check = {
        "raw_data": RAW_DATA_DIR.exists(),
        "mit_lab": MIT_DIR.exists(),
        "census": CENSUS_DIR.exists(),
        "processed": PROCESSED_DATA_DIR.exists(),
        "elections": ELECTIONS_DIR.exists(),
        "geojson": GEOJSON_DIR.exists(),
        "combined": COMBINED_DIR.exists(),
    }
    return dirs_to_check


if __name__ == "__main__":
    print("=" * 70)
    print("ELECTION SWING VISUALIZER - CONFIGURATION")
    print("=" * 70)
    print(f"\nProject Root: {PROJECT_ROOT}")
    print(f"Data Directory: {DATA_DIR}")
    print(f"\nElection Years: {ELECTION_YEARS}")
    print(f"Default Shapefile: {DEFAULT_SHAPEFILE_NAME}")
    print("\nDirectory Structure:")
    for name, exists in check_data_directory_structure().items():
        status = "OK" if exists else "ERROR"
        print(f"  {status} {name}")
    print("\n" + "=" * 70)