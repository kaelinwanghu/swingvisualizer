"""
03_process_geography.py
Process Census Bureau county shapefiles for web mapping.

This script:
1. Loads Census TIGER/Line county shapefiles
2. Validates and fixes geometries
3. Simplifies geometries for web performance
4. Standardizes FIPS codes and column names
5. Exports as GeoJSON

Usage:
    python processing/03_process_geography.py [--simplify TOLERANCE] [--validate-only]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import geopandas as gpd
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))
from config import (
    CENSUS_DIR, GEOJSON_DIR, DEFAULT_SHAPEFILE_NAME,
    TARGET_CRS, SIMPLIFY_TOLERANCE, CENSUS_COLUMNS_TO_KEEP,
    LOG_DIR, LOG_FORMAT
)
from utils.geo_utils import (
    simplify_geometry, convert_to_geojson, validate_geometries,
    set_crs_if_missing, get_bounds
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "03_process_geography.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# LOADING
# ============================================================================

def load_county_shapefile() -> gpd.GeoDataFrame:
    """
    Load Census Bureau county shapefile.
    
    Returns:
        GeoDataFrame with county geometries
    """
    logger.info("=" * 70)
    logger.info("LOADING COUNTY SHAPEFILE")
    logger.info("=" * 70)
    
    # Find shapefile
    shapefile_dir = CENSUS_DIR / DEFAULT_SHAPEFILE_NAME
    shapefile_path = shapefile_dir / f"{DEFAULT_SHAPEFILE_NAME}.shp"
    
    if not shapefile_path.exists():
        raise FileNotFoundError(
            f"Shapefile not found: {shapefile_path}\n"
            "Please run 01_download_data.py first."
        )
    
    logger.info(f"Loading: {shapefile_path.name}")
    
    # Load with pyogrio for speed
    gdf = gpd.read_file(shapefile_path, engine="pyogrio")
    
    logger.info(f"Loaded {len(gdf):,} counties")
    logger.info(f"CRS: {gdf.crs}")
    logger.info(f"Columns: {list(gdf.columns)}")
    
    # Memory usage
    memory_mb = gdf.memory_usage(deep=True).sum() / 1024 / 1024
    logger.info(f"Memory usage: {memory_mb:.2f} MB")
    
    return gdf


# ============================================================================
# VALIDATION
# ============================================================================

def validate_shapefile(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
    """
    Validate shapefile data and geometries.
    
    Args:
        gdf: GeoDataFrame to validate
        
    Returns:
        Dictionary with validation results
    """
    logger.info("\nValidating shapefile...")
    
    validation = {
        'total_counties': len(gdf),
        'unique_fips': gdf['GEOID'].nunique(),
        'missing_geoid': gdf['GEOID'].isna().sum(),
        'missing_geometry': gdf['geometry'].isna().sum(),
        'invalid_geometries': (~gdf.is_valid).sum(),
        'geometry_types': gdf['geometry'].geom_type.value_counts().to_dict(),
        'bounds': get_bounds(gdf),
    }
    
    logger.info(f"  Total counties: {validation['total_counties']:,}")
    logger.info(f"  Unique FIPS codes: {validation['unique_fips']:,}")
    logger.info(f"  Missing GEOID: {validation['missing_geoid']}")
    logger.info(f"  Missing geometry: {validation['missing_geometry']}")
    logger.info(f"  Invalid geometries: {validation['invalid_geometries']}")
    logger.info(f"  Geometry types: {validation['geometry_types']}")
    
    # Check bounds (should cover continental US + territories)
    bounds = validation['bounds']
    logger.info(f"  Bounds: ({bounds['minx']:.2f}, {bounds['miny']:.2f}) to ({bounds['maxx']:.2f}, {bounds['maxy']:.2f})")
    
    return validation


# ============================================================================
# CLEANING
# ============================================================================

def standardize_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Standardize column names and select relevant columns.
    
    Args:
        gdf: GeoDataFrame with Census columns
        
    Returns:
        GeoDataFrame with standardized columns
    """
    logger.info("\nStandardizing columns...")
    
    # Keep only needed columns
    columns_to_keep = [col for col in CENSUS_COLUMNS_TO_KEEP if col in gdf.columns]
    columns_to_keep.append('geometry')  # Ensure geometry is included
    
    gdf = gdf[list(set(columns_to_keep))].copy()
    
    # Rename to more user-friendly names
    gdf = gdf.rename(columns={
        'GEOID': 'fips',
        'NAME': 'county_name',
        'NAMELSAD': 'county_full_name',
        'STATEFP': 'state_fips',
        'COUNTYFP': 'county_fips',
        'ALAND': 'land_area_sqm',
        'AWATER': 'water_area_sqm',
        'INTPTLAT': 'latitude',
        'INTPTLON': 'longitude',
    })
    
    # Calculate areas in square miles
    if 'land_area_sqm' in gdf.columns:
        gdf['land_area_sqmi'] = (gdf['land_area_sqm'] / 2589988.11).round(2)
    if 'water_area_sqm' in gdf.columns:
        gdf['water_area_sqmi'] = (gdf['water_area_sqm'] / 2589988.11).round(2)
    
    # Convert lat/lon to float
    for col in ['latitude', 'longitude']:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors='coerce')
    
    logger.info(f"  Kept columns: {list(gdf.columns)}")
    
    return gdf


def clean_fips_codes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Ensure FIPS codes are standardized.
    
    Args:
        gdf: GeoDataFrame with fips column
        
    Returns:
        GeoDataFrame with cleaned FIPS
    """
    logger.info("\nCleaning FIPS codes...")
    
    gdf = gdf.copy()
    
    # Ensure FIPS is string with leading zeros (5 digits)
    gdf['fips'] = gdf['fips'].astype(str).str.zfill(5)
    
    # Validate FIPS format
    valid_fips = gdf['fips'].str.match(r'^\d{5}$', na=False)
    invalid_count = (~valid_fips).sum()
    
    if invalid_count > 0:
        logger.warning(f"  Removing {invalid_count} counties with invalid FIPS codes")
        invalid_fips = gdf[~valid_fips]['fips'].tolist()
        logger.warning(f"  Invalid FIPS: {invalid_fips[:10]}...")  # Show first 10
        gdf = gdf[valid_fips]
    
    # Check for duplicates
    duplicates = gdf['fips'].duplicated().sum()
    if duplicates > 0:
        logger.warning(f"  Found {duplicates} duplicate FIPS codes")
        duplicate_fips = gdf[gdf['fips'].duplicated(keep=False)]['fips'].unique()
        logger.warning(f"  Duplicate FIPS: {duplicate_fips}")
    
    logger.info(f"  Valid FIPS codes: {gdf['fips'].nunique():,} unique")
    
    return gdf


# ============================================================================
# PROCESSING
# ============================================================================

def reproject_to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Reproject to WGS84 (EPSG:4326) for web mapping.
    
    Args:
        gdf: GeoDataFrame to reproject
        
    Returns:
        Reprojected GeoDataFrame
    """
    logger.info("\nReprojecting to WGS84...")
    
    # Set CRS if missing
    if gdf.crs is None:
        logger.warning("  No CRS found. Assuming NAD83 (EPSG:4269)")
        gdf.set_crs('EPSG:4269', inplace=True)

    current_crs = gdf.crs.to_string() # type: ignore
    # Reproject if needed
    if current_crs != TARGET_CRS:
        logger.info(f"  Converting from {current_crs} to {TARGET_CRS}")
        gdf = gdf.to_crs(TARGET_CRS)
    else:
        logger.info(f"  Already in {TARGET_CRS}")
    
    return gdf


def process_geometries(
    gdf: gpd.GeoDataFrame, 
    tolerance: float = SIMPLIFY_TOLERANCE
) -> gpd.GeoDataFrame:
    """
    Validate, fix, and simplify geometries.
    
    Args:
        gdf: GeoDataFrame to process
        tolerance: Simplification tolerance
        
    Returns:
        Processed GeoDataFrame
    """
    logger.info("\nProcessing geometries...")
    
    # Validate and fix
    gdf = validate_geometries(gdf)
    
    # Simplify
    logger.info(f"Simplifying with tolerance: {tolerance}")
    gdf = simplify_geometry(gdf, tolerance)
    
    return gdf


# ============================================================================
# EXPORT
# ============================================================================

def export_geojson(gdf: gpd.GeoDataFrame, output_name: str = "counties") -> Path:
    """
    Export GeoDataFrame as GeoJSON.
    
    Args:
        gdf: GeoDataFrame to export
        output_name: Output filename (without extension)
        
    Returns:
        Path to exported file
    """
    output_file = GEOJSON_DIR / f"{output_name}.geojson"
    
    logger.info(f"\nExporting to: {output_file}")
    
    # Export with precision to reduce file size
    convert_to_geojson(gdf, output_file, precision=6)
    
    return output_file


def create_summary_stats(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
    """
    Create summary statistics for the shapefile.
    
    Args:
        gdf: Processed GeoDataFrame
        
    Returns:
        Dictionary with summary stats
    """
    stats = {
        'total_counties': len(gdf),
        'states': gdf['state_fips'].nunique() if 'state_fips' in gdf.columns else 'N/A',
        'total_land_area_sqmi': gdf['land_area_sqmi'].sum() if 'land_area_sqmi' in gdf.columns else 'N/A',
        'avg_land_area_sqmi': gdf['land_area_sqmi'].mean() if 'land_area_sqmi' in gdf.columns else 'N/A',
        'smallest_county': gdf.nsmallest(1, 'land_area_sqmi')[['county_name', 'land_area_sqmi']].to_dict('records')[0] if 'land_area_sqmi' in gdf.columns else 'N/A',
        'largest_county': gdf.nlargest(1, 'land_area_sqmi')[['county_name', 'land_area_sqmi']].to_dict('records')[0] if 'land_area_sqmi' in gdf.columns else 'N/A',
    }
    
    return stats


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main processing function."""
    parser = argparse.ArgumentParser(
        description="Process county shapefiles for web mapping"
    )
    parser.add_argument(
        "--simplify",
        type=float,
        default=SIMPLIFY_TOLERANCE,
        help=f"Simplification tolerance (default: {SIMPLIFY_TOLERANCE})"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate shapefile without processing"
    )
    parser.add_argument(
        "--no-simplify",
        action="store_true",
        help="Skip geometry simplification"
    )
    
    args = parser.parse_args()
    
    try:
        # Load shapefile
        gdf = load_county_shapefile()
        
        # Validate
        validation = validate_shapefile(gdf)
        
        if args.validate_only:
            logger.info("\n[OK] Validation complete. Use without --validate-only to process.")
            return 0
        
        # Clean and standardize
        gdf = standardize_columns(gdf)
        gdf = clean_fips_codes(gdf)
        
        # Reproject to WGS84
        gdf = reproject_to_wgs84(gdf)
        
        # Process geometries
        if not args.no_simplify:
            gdf = process_geometries(gdf, tolerance=args.simplify)
        else:
            logger.info("\nSkipping simplification (--no-simplify)")
            gdf = validate_geometries(gdf)
        
        # Create summary stats
        stats = create_summary_stats(gdf)
        
        logger.info("\n" + "=" * 70)
        logger.info("SUMMARY STATISTICS")
        logger.info("=" * 70)
        logger.info(f"Total counties: {stats['total_counties']:,}")
        logger.info(f"States/territories: {stats['states']}")
        if isinstance(stats['total_land_area_sqmi'], (int, float)):
            logger.info(f"Total land area: {stats['total_land_area_sqmi']:,.0f} sq mi")
            logger.info(f"Average county area: {stats['avg_land_area_sqmi']:,.0f} sq mi")
            if stats['smallest_county'] != 'N/A':
                logger.info(f"Smallest county: {stats['smallest_county']['county_name']} ({stats['smallest_county']['land_area_sqmi']:.2f} sq mi)")
            if stats['largest_county'] != 'N/A':
                logger.info(f"Largest county: {stats['largest_county']['county_name']} ({stats['largest_county']['land_area_sqmi']:.2f} sq mi)")
        
        # Export
        output_file = export_geojson(gdf, "counties")
        
        logger.info("\n" + "=" * 70)
        logger.info("[OK] Successfully processed county shapefile")
        logger.info(f"Output: {output_file}")
        logger.info("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())