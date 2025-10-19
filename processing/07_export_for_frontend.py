"""
07_export_for_frontend.py
Export processed GeoJSON files optimized for frontend consumption.

This script:
1. Extracts base geometry from one GeoJSON file (loaded once)
2. Extracts election data per year (loaded on-demand)
3. Handles NaN values and boolean strings properly for JSON
4. Optimizes file sizes for web delivery
5. Generates data manifest for frontend

Strategy:
- Geometry file: ~12 MB (one-time load)
- Election data per year: ~800 KB each (lazy load)
- Total data size: ~17-20 MB instead of ~105 MB

Usage:
    python processing/07_export_for_frontend.py
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Set
import geopandas as gpd
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))
from config import (
    COMBINED_DIR, ELECTION_YEARS, LOG_DIR, LOG_FORMAT
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "07_export_frontend.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Default frontend data directory
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"

# Geographic properties to keep in base geometry
BASE_GEOMETRY_PROPERTIES = {
    'fips',
    'county_name',
    'county_full_name', 
    'county',
    'state',
    'state_po',
    'state_fips',
    'county_fips',
    'land_area_sqmi',
    'water_area_sqmi',
    'land_area_sqm',
    'water_area_sqm',
}

# Election data properties (everything else)
# These will be extracted to separate JSON files per year
ELECTION_MAP_PROPERTIES = {
    'year',
    'total_votes',
    'DEMOCRAT',
    'REPUBLICAN',
    'LIBERTARIAN',
    'GREEN',
    'OTHER',
    'major_party_votes',
    'dem_share',
    'rep_share',
    'margin',
    'margin_change',
    'winner',
    'swing',
    'swing_magnitude',
    'swing_direction',
    'flipped',
    'flip_direction',
    'turnout_change_pct',
    # Historical/pattern metrics
    'years_with_data',
    'first_year',
    'last_year',
    'total_flips',
    'flip_rate',
    'avg_margin',
    'median_margin',
    'margin_std',
    'dem_win_pct',
    'rep_win_pct',
    'trajectory',
    'trajectory_direction',
    'avg_swing_magnitude',
    'max_swing',
    'close_election_rate',
    'avg_competitiveness',
    'classification',
    'bellwether_score',
}

# Boolean field names that should be converted to proper booleans
BOOLEAN_FIELDS = {'flipped'}


# ============================================================================
# VALUE CLEANING FOR JSON
# ============================================================================

def clean_value_for_json(value: Any, prop_name: str) -> Any:
    """
    Clean a value for JSON export, handling NaN, boolean strings, etc.
    
    Args:
        value: Value to clean
        prop_name: Property name (for context-specific handling)
        
    Returns:
        JSON-serializable value or None
    """
    # Handle None first
    if value is None:
        return None
    
    # Handle pandas NA types
    if pd.isna(value):
        return None
    
    # Handle numpy scalars
    if hasattr(value, 'item'):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    
    # Handle float NaN/inf
    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return None
        if value.is_integer():
            return int(value)
        return round(value, 6)  # Limit precision
    
    # Handle integers
    if isinstance(value, (int, np.integer)):
        return int(value)
    
    # Handle booleans (including string booleans)
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        # Convert string booleans to proper booleans
        value_lower = value.lower()
        if value_lower in ['true', '1', 'yes']:
            return True
        elif value_lower in ['false', '0', 'no']:
            return False
        
        # Check for string representations of NaN
        if value_lower in ['nan', 'none', '<na>', 'nat', '']:
            return None
        
        # Check if this is a boolean field that has a string value
        if prop_name in BOOLEAN_FIELDS:
            return value_lower == 'true'
        
        return value
    
    # Default: convert to string
    return str(value)


# ============================================================================
# GEOMETRY EXTRACTION
# ============================================================================

def extract_base_geometry(
    source_geojson: Path,
    output_dir: Path
) -> Path:
    """
    Extract base geometry file with only geographic properties.
    
    This file will be loaded once and reused for all years.
    
    Args:
        source_geojson: Source GeoJSON file (any year)
        output_dir: Output directory

    Returns:
        Path to created geometry file
    """
    logger.info("=" * 70)
    logger.info("EXTRACTING BASE GEOMETRY")
    logger.info("=" * 70)
    logger.info(f"Source: {source_geojson.name}")
    
    # Load GeoJSON
    gdf = gpd.read_file(source_geojson)
    logger.info(f"Loaded {len(gdf):,} counties")
    
    # Keep only base properties
    properties_to_keep = [col for col in BASE_GEOMETRY_PROPERTIES if col in gdf.columns]
    properties_to_keep.append('geometry')  # Always keep geometry
    
    base_gdf = gdf[properties_to_keep].copy()
    
    logger.info(f"Keeping {len(properties_to_keep)} properties:")
    for prop in sorted(properties_to_keep):
        if prop != 'geometry':
            logger.info(f"  - {prop}")
    
    # Export as GeoJSON
    output_file = output_dir / "counties.geojson"
    base_gdf.to_file(output_file, driver='GeoJSON')
    
    # Report size
    size_mb = output_file.stat().st_size / 1024 / 1024
    logger.info(f"\nExported: {output_file.name}")
    logger.info(f"Size: {size_mb:.2f} MB")
    logger.info(f"Counties: {len(base_gdf):,}")
    
    return output_file


# ============================================================================
# ELECTION DATA EXTRACTION
# ============================================================================

def extract_election_data(
    source_geojson: Path,
    year: int,
    output_dir: Path
) -> Path:
    """
    Extract election data for a specific year without geometry.
    
    Creates a JSON file indexed by FIPS code.
    
    Args:
        source_geojson: Source GeoJSON file for this year
        year: Election year
        output_dir: Output directory
        
    Returns:
        Path to created election data file
    """
    logger.info(f"\nProcessing {year}...")
    
    # Load GeoJSON
    gdf = gpd.read_file(source_geojson)
    
    # Extract election data (no geometry)
    election_data = {}
    
    for idx, row in gdf.iterrows():
        fips = str(row['fips'])  # Ensure FIPS is string
        
        # Collect all election properties
        county_data = {}
        for prop in ELECTION_MAP_PROPERTIES:
            if prop in row:
                value = row[prop]
                cleaned_value = clean_value_for_json(value, prop)
                
                # Only include non-null values
                if cleaned_value is not None:
                    county_data[prop] = cleaned_value
        
        election_data[fips] = county_data
    
    # Export as compact JSON (no whitespace)
    output_file = output_dir / f"elections_{year}.json"
    with open(output_file, 'w') as f:
        json.dump(election_data, f, separators=(',', ':'))
    
    # Report size
    size_kb = output_file.stat().st_size / 1024
    logger.info(f"  {year}: {size_kb:.1f} KB ({len(election_data):,} counties)")
    
    return output_file


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def process_all_years(
    combined_dir: Path,
    output_dir: Path,
    years: List[int]
) -> List[Path]:
    """
    Process all election year GeoJSON files.
    
    Args:
        combined_dir: Directory containing combined GeoJSON files
        output_dir: Output directory for election data
        years: List of years to process
        
    Returns:
        List of created election data files
    """
    logger.info("=" * 70)
    logger.info("EXTRACTING ELECTION DATA")
    logger.info("=" * 70)
    
    election_files = []
    missing_years = []
    
    for year in years:
        # Look for combined GeoJSON file
        geojson_file = combined_dir / f"election_map_{year}.geojson"
        
        if not geojson_file.exists():
            logger.warning(f"Missing GeoJSON for {year}: {geojson_file.name}")
            missing_years.append(year)
            continue
        
        # Extract election data
        try:
            election_file = extract_election_data(geojson_file, year, output_dir)
            election_files.append(election_file)
        except Exception as e:
            logger.error(f"Failed to process {year}: {e}")
            missing_years.append(year)
    
    if missing_years:
        logger.warning(f"\nMissing years: {missing_years}")
        logger.warning("These years will not be available in the frontend")
    
    logger.info(f"\nSuccessfully processed {len(election_files)} years")
    
    return election_files


# ============================================================================
# MANIFEST GENERATION
# ============================================================================

def generate_manifest(
    geometry_file: Path,
    election_files: List[Path],
    output_dir: Path
) -> Path:
    """
    Generate manifest describing all available data files.
    
    Args:
        geometry_file: Base geometry file
        election_files: List of election data files
        output_dir: Output directory
        
    Returns:
        Path to manifest file
    """
    logger.info("\n" + "=" * 70)
    logger.info("GENERATING MANIFEST")
    logger.info("=" * 70)
    
    manifest = {
        'version': '1.0.0',
        'generated_at': pd.Timestamp.now().isoformat(),
        'description': 'Election swing visualization data',
        'usage': {
            'geometry': 'Load once on app initialization',
            'elections': 'Load on-demand when user selects a year'
        },
        'files': {
            'geometry': {
                'path': 'geojson/counties.geojson',
                'size_mb': round(geometry_file.stat().st_size / 1024 / 1024, 2),
                'counties': None,  # Will be filled by frontend
                'description': 'Base county geometries - load once and reuse'
            },
            'elections': {}
        },
        'available_years': []
    }
    
    # Add election files
    total_data_size = 0
    for file in sorted(election_files):
        year = int(file.stem.split('_')[1])
        size_kb = file.stat().st_size / 1024
        total_data_size += size_kb
        
        manifest['files']['elections'][year] = {
            'path': f'elections/{file.name}',
            'size_kb': round(size_kb, 1)
        }
        manifest['available_years'].append(year)
    
    # Add summary statistics
    manifest['summary'] = {
        'total_years': len(election_files),
        'geometry_size_mb': manifest['files']['geometry']['size_mb'],
        'total_election_data_mb': round(total_data_size / 1024, 2),
        'estimated_total_load_mb': round(
            manifest['files']['geometry']['size_mb'] + (total_data_size / 1024),
            2
        )
    }
    
    # Write manifest
    manifest_file = output_dir / 'manifest.json'
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    logger.info("Created manifest.json")
    logger.info("\nData Summary:")
    logger.info(f"  Geometry: {manifest['summary']['geometry_size_mb']} MB")
    logger.info(f"  Election data (all years): {manifest['summary']['total_election_data_mb']} MB")
    logger.info(f"  Total (if all loaded): {manifest['summary']['estimated_total_load_mb']} MB")
    logger.info(f"  Available years: {manifest['available_years']}")
    
    return manifest_file


# ============================================================================
# VALIDATION
# ============================================================================

def validate_export(
    frontend_data_dir: Path,
    expected_years: List[int]
) -> Dict[str, Any]:
    """
    Validate exported files.
    
    Args:
        frontend_data_dir: Frontend data directory
        expected_years: Expected election years
        
    Returns:
        Validation results
    """
    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION")
    logger.info("=" * 70)
    
    validation = {
        'success': True,
        'missing_files': [],
        'warnings': []
    }
    
    # Check geometry
    geometry_file = frontend_data_dir / "geojson" / "counties.geojson"
    if not geometry_file.exists():
        validation['missing_files'].append('counties.geojson')
        validation['success'] = False
        logger.error("✗ Missing: counties.geojson")
    else:
        logger.info("✓ Found: counties.geojson")
    
    # Check election files
    elections_dir = frontend_data_dir / "elections"
    found_years = []
    for year in expected_years:
        election_file = elections_dir / f"elections_{year}.json"
        if not election_file.exists():
            validation['missing_files'].append(f'elections_{year}.json')
            validation['warnings'].append(f'Missing data for year {year}')
            logger.warning(f"⚠ Missing: elections_{year}.json")
        else:
            found_years.append(year)
    
    logger.info(f"✓ Found election data for {len(found_years)} years: {found_years}")
    
    # Check manifest
    manifest_file = frontend_data_dir / "manifest.json"
    if not manifest_file.exists():
        validation['missing_files'].append('manifest.json')
        logger.warning("⚠ Missing: manifest.json")
    else:
        logger.info("✓ Found: manifest.json")
    
    # Overall status
    if validation['success']:
        logger.info("\n✓ All required files present")
    else:
        logger.error("\n✗ Some required files missing - see above")
    
    if validation['warnings']:
        logger.warning(f"\n⚠ {len(validation['warnings'])} warnings")
    
    return validation


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main export function."""
    parser = argparse.ArgumentParser(
        description="Export processed GeoJSON for frontend (optimized)"
    )
    parser.add_argument(
        "--combined-dir",
        type=Path,
        default=COMBINED_DIR,
        help="Directory containing combined GeoJSON files"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_FRONTEND_DATA,
        help="Frontend data output directory"
    )
    parser.add_argument(
        "--source-year",
        type=int,
        default=2024,
        help="Year to use as source for base geometry (default: 2024)"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("=" * 70)
        logger.info("FRONTEND DATA EXPORT (OPTIMIZED)")
        logger.info("=" * 70)
        logger.info(f"Source: {args.combined_dir}")
        logger.info(f"Output: {args.output_dir}")
        logger.info("")
        logger.info("Strategy:")
        logger.info("  1. Extract base geometry (load once)")
        logger.info("  2. Extract election data per year (load on-demand)")
        logger.info("  3. Handle NaN values and boolean strings")
        logger.info("  4. Frontend joins them using FIPS codes")
        logger.info("")
        
        # Create output directories
        output_dir = args.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        geojson_out = output_dir / "geojson"
        elections_out = output_dir / "elections"
        
        geojson_out.mkdir(exist_ok=True)
        elections_out.mkdir(exist_ok=True)
        
        # Step 1: Extract base geometry from one year
        source_geojson = args.combined_dir / f"election_map_{args.source_year}.geojson"
        
        if not source_geojson.exists():
            logger.error(f"Source GeoJSON not found: {source_geojson}")
            logger.error("Please ensure you have combined GeoJSON files from previous pipeline steps")
            return 1
        
        geometry_file = extract_base_geometry(source_geojson, geojson_out)
        
        # Step 2: Extract election data for all years
        election_files = process_all_years(
            args.combined_dir,
            elections_out,
            ELECTION_YEARS
        )
        
        if not election_files:
            logger.error("No election data files were created")
            return 1
        
        # Step 3: Generate manifest
        manifest_file = generate_manifest(
            geometry_file,
            election_files,
            output_dir
        )
        
        # Step 4: Validate
        validation = validate_export(output_dir, ELECTION_YEARS)
        
        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("EXPORT COMPLETE")
        logger.info("=" * 70)
        logger.info(f"\nOutput directory: {output_dir}")
        logger.info("\nFiles created:")
        logger.info("  - geojson/counties.geojson")
        logger.info(f"  - elections/elections_*.json ({len(election_files)} files)")
        logger.info("  - manifest.json")
        logger.info("\nFrontend integration:")
        logger.info("  1. Load counties.geojson once on app mount")
        logger.info("  2. Load elections_YEAR.json when user selects year")
        logger.info("  3. Join using FIPS code: electionData[feature.properties.fips]")
        
        if not validation['success']:
            logger.warning("\n⚠ Some issues detected - see validation above")
            return 1
        
        logger.info("\n✓ Ready for frontend!")
        return 0
        
    except Exception as e:
        logger.error(f"\n[ERROR] Export failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())