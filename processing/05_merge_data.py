"""
05_merge_data.py
Merge election results with county geographies to create map-ready GeoJSON files.

This script:
1. Loads cleaned election data
2. Loads processed county geometries
3. Joins election data with geography on FIPS codes
4. Optionally includes swing data
5. Exports combined GeoJSON files for each year

Usage:
    python processing/05_merge_data.py [--year YEAR] [--all] [--include-swings]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
import pandas as pd
import geopandas as gpd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))
from config import (
    ELECTIONS_DIR, GEOJSON_DIR, COMBINED_DIR, ELECTION_YEARS,
    get_adjacent_election_pairs, LOG_DIR, LOG_FORMAT
)
from utils.geo_utils import convert_to_geojson

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "05_merge_data.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA LOADING
# ============================================================================

def load_base_geography() -> gpd.GeoDataFrame:
    """
    Load processed county geography.
    
    Returns:
        GeoDataFrame with county geometries
    """
    logger.info("Loading base geography...")
    
    geojson_file = GEOJSON_DIR / "counties.geojson"
    
    if not geojson_file.exists():
        raise FileNotFoundError(
            f"County GeoJSON not found: {geojson_file}\n"
            "Please run 03_process_geography.py first."
        )
    
    gdf = gpd.read_file(geojson_file)
    
    logger.info(f"  Loaded {len(gdf):,} county geometries")
    logger.info(f"  CRS: {gdf.crs}")
    
    # Ensure fips is string
    gdf['fips'] = gdf['fips'].astype(str).str.zfill(5)
    
    return gdf


def load_election_data(year: int) -> pd.DataFrame:
    """
    Load cleaned election data for a specific year.
    
    Args:
        year: Election year
        
    Returns:
        DataFrame with election results
    """
    file_path = ELECTIONS_DIR / f"elections_{year}.csv"
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Election data not found for {year}: {file_path}\n"
            "Please run 02_clean_elections.py first."
        )
    
    df = pd.read_csv(file_path)
    
    logger.info(f"  Loaded {len(df):,} county results for {year}")
    
    # Ensure fips is string - handle both string and numeric types
    # Remove any .0 decimal points that might exist
    df['fips'] = df['fips'].astype(str).str.replace('.0', '', regex=False).str.zfill(5)
    
    return df


def load_swing_data(year1: int, year2: int) -> Optional[pd.DataFrame]:
    """
    Load swing calculations if available.
    
    Args:
        year1: First election year
        year2: Second election year
        
    Returns:
        DataFrame with swing data, or None if not available
    """
    swing_file = COMBINED_DIR / f"swings_{year1}_to_{year2}.csv"
    
    if not swing_file.exists():
        logger.warning(f"  Swing data not found: {swing_file.name}")
        return None
    
    df = pd.read_csv(swing_file)
    
    logger.info(f"  Loaded swing data: {year1} -> {year2}")
    
    # Ensure fips is string - handle both string and numeric types
    # Remove any .0 decimal points that might exist
    df['fips'] = df['fips'].astype(str).str.replace('.0', '', regex=False).str.zfill(5)
    
    return df


# ============================================================================
# MERGING
# ============================================================================

def merge_election_with_geography(
    gdf: gpd.GeoDataFrame,
    election_df: pd.DataFrame,
    year: int
) -> gpd.GeoDataFrame:
    """
    Merge election data with county geometries.
    
    Args:
        gdf: GeoDataFrame with county geometries
        election_df: DataFrame with election results
        year: Election year
        
    Returns:
        Merged GeoDataFrame
    """
    logger.info(f"\nMerging {year} election data with geography...")
    
    # Remove 'geometry' column from election_df if it exists (shouldn't, but just in case)
    if 'geometry' in election_df.columns:
        logger.warning("  Removing 'geometry' column from election data")
        election_df = election_df.drop(columns=['geometry'])
    
    # Merge on FIPS code
    merged = gdf.merge(
        election_df,
        on='fips',
        how='left',
        suffixes=('_geo', '_elec')
    )
    
    # Count matches
    matched = merged['total_votes'].notna().sum()
    unmatched_geo = len(merged) - matched
    unmatched_elec = len(election_df) - matched
    
    logger.info(f"  Matched: {matched:,} counties")
    
    if unmatched_geo > 0:
        logger.warning(f"  Counties in geography but not in election data: {unmatched_geo}")
        unmatched_fips = merged[merged['total_votes'].isna()]['fips'].tolist()
        logger.warning(f"    Sample unmatched FIPS: {unmatched_fips[:10]}")
    
    if unmatched_elec > 0:
        logger.warning(f"  Counties in election data but not in geography: {unmatched_elec}")
        # Find which election FIPS are missing
        geo_fips = set(gdf['fips'])
        elec_fips = set(election_df['fips'])
        missing = elec_fips - geo_fips
        logger.warning(f"    Sample missing from geography: {list(missing)[:10]}")
    
    # Handle duplicate columns (keep election data where available, geography otherwise)
    if 'county_geo' in merged.columns and 'county_elec' in merged.columns:
        merged['county'] = merged['county_elec'].fillna(merged['county_geo'])
        merged = merged.drop(columns=['county_geo', 'county_elec'])
    
    if 'state_geo' in merged.columns and 'state_elec' in merged.columns:
        merged['state'] = merged['state_elec'].fillna(merged['state_geo'])
        merged = merged.drop(columns=['state_geo', 'state_elec'])
    
    # Add year column
    merged['year'] = year
    
    return merged


def add_swing_to_merged_data(
    merged_gdf: gpd.GeoDataFrame,
    swing_df: pd.DataFrame,
    year: int
) -> gpd.GeoDataFrame:
    """
    Add swing data to merged GeoDataFrame.
    Only includes swing metrics, not duplicate vote data.
    
    Args:
        merged_gdf: GeoDataFrame with election and geography
        swing_df: DataFrame with swing calculations
        year: Current election year
        
    Returns:
        GeoDataFrame with swing data added
    """
    logger.info(f"  Adding swing data for {year}...")
    
    # IMPORTANT: Only select swing calculation columns
    # Do NOT include y1/y2 vote data (that's already in election data)
    swing_cols = [
        'fips',
        'swing',                # Change in Democratic two-party share
        'swing_magnitude',      # Absolute value of swing
        'swing_direction',      # 'DEMOCRAT' or 'REPUBLICAN'
        'flipped',              # Boolean: did county flip parties?
        'flip_direction',       # e.g., 'DEMOCRAT_to_REPUBLICAN'
        'turnout_change_pct',   # Percentage change in turnout
        'margin_change'         # Change in vote margin (if available)
    ]
    
    # Remove 'geometry' from swing data if it exists
    if 'geometry' in swing_df.columns:
        logger.warning("  Removing 'geometry' column from swing data")
        swing_df = swing_df.drop(columns=['geometry'])
    
    # Select only columns that exist in swing_df
    available_cols = [col for col in swing_cols if col in swing_df.columns]
    
    if len(available_cols) <= 1:  # Only 'fips' found
        logger.warning("  No swing metrics found in data")
        return merged_gdf
    
    # Merge swing metrics (left join to preserve all counties)
    merged = merged_gdf.merge(
        swing_df[available_cols],
        on='fips',
        how='left'
    )
    
    swing_matched = merged['swing'].notna().sum()
    logger.info(f"  Added swing data for {swing_matched:,} counties")
    
    return merged


# ============================================================================
# EXPORT
# ============================================================================

def prepare_for_export(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prepare GeoDataFrame for export with proper null handling.
    
    Args:
        gdf: GeoDataFrame to prepare
        
    Returns:
        Cleaned GeoDataFrame
    """
    logger.info("\nPreparing data for export...")
    
    # CRITICAL: Remove any duplicate geometry columns before processing
    # This can happen after merging with suffixes
    if gdf.columns.duplicated().any():
        logger.warning("  Found duplicate column names - cleaning up")
        # Keep first occurrence of each column
        gdf = gdf.loc[:, ~gdf.columns.duplicated()]
    
    # Define column order (important ones first)
    priority_cols = [
        'fips', 'county', 'state', 'state_po', 'year',
        'total_votes', 'DEMOCRAT', 'REPUBLICAN', 
        'dem_share', 'rep_share', 'margin', 'winner',
        'swing', 'swing_magnitude', 'swing_direction',
        'flipped', 'flip_direction', 'turnout_change_pct',
        'land_area_sqmi', 'latitude', 'longitude',
        'geometry'
    ]
    
    # Get columns that exist in the GeoDataFrame
    existing_priority = [col for col in priority_cols if col in gdf.columns]
    other_cols = [col for col in gdf.columns 
                  if col not in existing_priority and col != 'geometry']
    
    # Reorder columns (priority first, then others, geometry always last)
    # Make sure geometry only appears once at the end
    ordered_cols = [col for col in existing_priority + other_cols if col != 'geometry'] + ['geometry']
    
    gdf = gdf[ordered_cols].copy()
    
    # Handle vote counts: keep null for missing data (don't fill with 0)
    vote_cols = ['total_votes', 'DEMOCRAT', 'REPUBLICAN', 'LIBERTARIAN', 
                 'GREEN', 'OTHER']
    for col in vote_cols:
        if col in gdf.columns:
            # Convert to nullable integer type (Int64 with capital I)
            gdf[col] = gdf[col].astype('Int64')
    
    # Handle percentages: fill null with 0 is acceptable
    pct_cols = ['dem_share', 'rep_share', 'margin', 'swing']
    for col in pct_cols:
        if col in gdf.columns:
            gdf[col] = gdf[col].fillna(0).round(2)
    
    # Handle turnout change: keep null for counties not in previous year
    if 'turnout_change_pct' in gdf.columns:
        gdf['turnout_change_pct'] = gdf['turnout_change_pct'].round(1)
    
    logger.info(f"  Final columns: {len(gdf.columns)}")
    logger.info(f"  Counties with vote data: {gdf['total_votes'].notna().sum():,}")
    logger.info(f"  Counties with geometry: {gdf['geometry'].notna().sum():,}")
    
    return gdf


def export_combined_geojson(gdf: gpd.GeoDataFrame, year: int) -> Path:
    """
    Export combined data as GeoJSON.
    
    Args:
        gdf: GeoDataFrame to export
        year: Election year
        
    Returns:
        Path to exported file
    """
    output_file = COMBINED_DIR / f"election_map_{year}.geojson"
    
    logger.info(f"\nExporting to: {output_file}")
    
    # Export with moderate precision to balance file size and accuracy
    convert_to_geojson(gdf, output_file, precision=5)
    
    return output_file


# ============================================================================
# VALIDATION
# ============================================================================

def validate_merged_data(gdf: gpd.GeoDataFrame, year: int) -> Dict:
    """
    Validate merged data quality.
    
    Args:
        gdf: Merged GeoDataFrame
        year: Election year
        
    Returns:
        Dictionary with validation results
    """
    logger.info(f"\nValidating merged data for {year}...")
    
    validation = {
        'year': year,
        'total_counties': len(gdf),
        'counties_with_votes': gdf['total_votes'].notna().sum() if 'total_votes' in gdf.columns else 0,
        'counties_with_geometry': gdf['geometry'].notna().sum(),
        'total_votes': gdf['total_votes'].sum() if 'total_votes' in gdf.columns else 0,
        'counties_with_swing': gdf['swing'].notna().sum() if 'swing' in gdf.columns else 0,
    }
    
    logger.info(f"  Total counties: {validation['total_counties']:,}")
    logger.info(f"  Counties with election data: {validation['counties_with_votes']:,}")
    logger.info(f"  Counties with geometry: {validation['counties_with_geometry']:,}")
    
    if validation['counties_with_votes'] > 0:
        logger.info(f"  Total votes: {validation['total_votes']:,}")
    
    if validation['counties_with_swing'] > 0:
        logger.info(f"  Counties with swing data: {validation['counties_with_swing']:,}")
    
    # Check for critical issues
    if validation['counties_with_votes'] < validation['total_counties'] * 0.95:
        logger.warning(f"  WARNING: Only {validation['counties_with_votes'] / validation['total_counties'] * 100:.1f}% of counties have election data")
    
    return validation


def validate_across_years(years: List[int]) -> Dict:
    """
    Validate consistency across multiple years.
    Checks that FIPS codes are consistent and counties don't disappear.
    
    Args:
        years: List of years to validate
        
    Returns:
        Dictionary with cross-year validation results
    """
    logger.info("\n" + "=" * 70)
    logger.info("CROSS-YEAR VALIDATION")
    logger.info("=" * 70)
    
    fips_by_year = {}
    
    # Load FIPS codes for each year
    for year in years:
        file_path = COMBINED_DIR / f"election_map_{year}.geojson"
        if file_path.exists():
            try:
                gdf = gpd.read_file(file_path)
                fips_by_year[year] = set(gdf['fips'].tolist())
                logger.info(f"  {year}: {len(fips_by_year[year]):,} counties")
            except Exception as e:
                logger.warning(f"  {year}: Could not load - {e}")
    
    if len(fips_by_year) < 2:
        logger.warning("  Not enough years to validate")
        return {'status': 'insufficient_data'}
    
    # Check for FIPS consistency
    all_fips = set.union(*fips_by_year.values())
    common_fips = set.intersection(*fips_by_year.values())
    
    logger.info(f"\n  Total unique FIPS across all years: {len(all_fips):,}")
    logger.info(f"  FIPS codes present in ALL years: {len(common_fips):,}")
    
    # Find counties that appear in some years but not others
    inconsistent = False
    for year in sorted(fips_by_year.keys()):
        missing = all_fips - fips_by_year[year]
        if missing:
            inconsistent = True
            logger.warning(f"\n  {year}: Missing {len(missing)} counties that appear in other years")
            # Show sample of missing FIPS
            sample_missing = list(missing)[:5]
            logger.warning(f"    Sample missing FIPS: {sample_missing}")
    
    # Check consistency status
    if not inconsistent:
        logger.info("\n  ✓ PASS: All years have consistent county coverage")
    else:
        logger.warning("\n  ⚠️  WARNING: County coverage varies between years")
        logger.warning("  This may be normal if county boundaries changed")
    
    return {
        'status': 'complete',
        'total_fips': len(all_fips),
        'common_fips': len(common_fips),
        'fips_by_year': {y: len(f) for y, f in fips_by_year.items()},
        'consistent': not inconsistent
    }


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_year(
    base_gdf: gpd.GeoDataFrame,
    year: int,
    include_swings: bool = False
) -> Dict:
    """
    Process merged data for a single year.
    
    Args:
        base_gdf: Base county geography
        year: Election year to process
        include_swings: Whether to include swing data
        
    Returns:
        Dictionary with processing results
    """
    logger.info("=" * 70)
    logger.info(f"PROCESSING YEAR: {year}")
    logger.info("=" * 70)
    
    try:
        # Load election data
        election_df = load_election_data(year)
        
        # Merge with geography
        merged_gdf = merge_election_with_geography(base_gdf, election_df, year)
        
        # Add swing data if requested and available
        if include_swings:
            # Find relevant swing periods
            pairs = get_adjacent_election_pairs()
            
            # Find swing TO this year
            for y1, y2 in pairs:
                if y2 == year:
                    swing_df = load_swing_data(y1, y2)
                    if swing_df is not None:
                        merged_gdf = add_swing_to_merged_data(merged_gdf, swing_df, year)
                    break
        
        # Prepare for export
        merged_gdf = prepare_for_export(merged_gdf)
        
        # Validate
        validation = validate_merged_data(merged_gdf, year)
        
        # Export
        output_file = export_combined_geojson(merged_gdf, year)
        
        logger.info(f"\n[OK] Successfully processed {year}")
        
        return {
            'year': year,
            'success': True,
            'validation': validation,
            'output_file': output_file
        }
        
    except Exception as e:
        logger.error(f"\n[ERROR] Failed to process {year}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'year': year,
            'success': False,
            'error': str(e)
        }


def main():
    """Main processing function."""
    parser = argparse.ArgumentParser(
        description="Merge election data with county geography"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Process a specific year only"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all available years"
    )
    parser.add_argument(
        "--include-swings",
        action="store_true",
        help="Include swing calculations in output"
    )
    
    args = parser.parse_args()
    
    try:
        # Load base geography (only once, reused for all years)
        base_gdf = load_base_geography()
        
        # Process years
        results = []
        
        if args.year:
            # Single year
            if args.year not in ELECTION_YEARS:
                logger.error(f"Invalid year: {args.year}. Valid years: {ELECTION_YEARS}")
                return 1
            
            result = process_year(base_gdf, args.year, args.include_swings)
            results.append(result)
            
        elif args.all:
            # All years
            for year in ELECTION_YEARS:
                result = process_year(base_gdf, year, args.include_swings)
                results.append(result)
                
        else:
            # Default: most recent year
            latest_year = max(ELECTION_YEARS)
            logger.info(f"No year specified. Processing latest year: {latest_year}")
            logger.info("Use --year YEAR for specific year, or --all for all years")
            
            result = process_year(base_gdf, latest_year, args.include_swings)
            results.append(result)
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("MERGE SUMMARY")
        logger.info("=" * 70)
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        logger.info(f"\nProcessed: {len(results)} years")
        logger.info(f"Successful: {len(successful)}")
        logger.info(f"Failed: {len(failed)}")
        
        if successful:
            logger.info("\nSuccessful years:")
            for result in successful:
                val = result['validation']
                logger.info(
                    f"  {result['year']}: {val['counties_with_votes']:,} counties with data, "
                    f"{val['total_votes']:,} total votes"
                )
        
        if failed:
            logger.warning("\nFailed years:")
            for result in failed:
                logger.warning(f"  {result['year']}: {result['error']}")
        
        # Cross-year validation if multiple years processed
        if len(successful) > 1:
            processed_years = [r['year'] for r in successful]
            validate_across_years(processed_years)
        
        logger.info("\n" + "=" * 70)
        logger.info("[OK] Merge process complete")
        logger.info("=" * 70)
        
        return 0 if all(r['success'] for r in results) else 1
        
    except Exception as e:
        logger.error(f"\n[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())