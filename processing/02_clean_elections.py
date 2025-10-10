"""
02_clean_elections.py
Clean and standardize MIT Election Lab county-level presidential returns.

This script:
1. Loads raw election data from MIT Election Lab
2. Standardizes party names and FIPS codes
3. Aggregates votes by county, year, and party
4. Validates data quality
5. Exports cleaned data by election year

Usage:
    python processing/02_clean_elections.py [--year YEAR] [--all] [--validate-only]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))
from config import (
    MIT_DIR, ELECTIONS_DIR, ELECTION_YEARS, 
    MAJOR_PARTIES, LOG_DIR, LOG_FORMAT,
    MIN_TOTAL_VOTES
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "02_clean_elections.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# PARTY NAME STANDARDIZATION
# ============================================================================

PARTY_MAPPING = {
    # Democrat variations
    'DEMOCRAT': 'DEMOCRAT',
    'DEMOCRATIC': 'DEMOCRAT',
    'DEMOCRATIC-FARMER-LABOR': 'DEMOCRAT',
    'DEM': 'DEMOCRAT',
    'D': 'DEMOCRAT',
    
    # Republican variations
    'REPUBLICAN': 'REPUBLICAN',
    'REP': 'REPUBLICAN',
    'R': 'REPUBLICAN',
    
    # Libertarian variations
    'LIBERTARIAN': 'LIBERTARIAN',
    'LIB': 'LIBERTARIAN',
    
    # Green variations
    'GREEN': 'GREEN',
    'GREEN PARTY': 'GREEN',
    
    # Independent/Other
    'INDEPENDENT': 'INDEPENDENT',
    'IND': 'INDEPENDENT',
    'OTHER': 'OTHER',
    'WRITE-IN': 'OTHER',
    'WRITEIN': 'OTHER',
}


def standardize_party_name(party: str) -> str:
    """
    Standardize party names to consistent format.
    
    Args:
        party: Raw party name from data
        
    Returns:
        Standardized party name
    """
    if pd.isna(party):
        return 'OTHER'
    
    # Convert to uppercase and strip whitespace
    party_upper = str(party).upper().strip()
    
    # Check mapping
    if party_upper in PARTY_MAPPING:
        return PARTY_MAPPING[party_upper]
    
    # Default to OTHER for unmapped parties
    logger.debug(f"Unmapped party: {party} -> OTHER")
    return 'OTHER'


# ============================================================================
# DATA LOADING AND VALIDATION
# ============================================================================

def load_raw_election_data() -> pd.DataFrame:
    """
    Load raw election data from MIT Election Lab.
    
    Returns:
        DataFrame with raw election data
    """
    logger.info("=" * 70)
    logger.info("LOADING RAW ELECTION DATA")
    logger.info("=" * 70)
    
    # Find the data file
    csv_files = list(MIT_DIR.glob("countypres*.csv"))
    
    if not csv_files:
        raise FileNotFoundError(
            f"No election data found in {MIT_DIR}. "
            "Please run 01_download_data.py first."
        )
    
    csv_file = csv_files[0]
    logger.info(f"Loading: {csv_file.name}")
    
    # Load data
    df = pd.read_csv(csv_file, low_memory=False)
    
    logger.info(f"Loaded {len(df):,} rows")
    logger.info(f"Columns: {list(df.columns)}")
    logger.info(f"Years: {sorted(df['year'].unique())}")
    logger.info(f"States: {df['state'].nunique()} unique")
    
    return df


def validate_raw_data(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Perform validation checks on raw data.
    
    Args:
        df: Raw election DataFrame
        
    Returns:
        Dictionary with validation results
    """
    logger.info("\nValidating raw data...")
    
    validation = {
        'total_rows': len(df),
        'missing_fips': df['county_fips'].isna().sum(),
        'missing_votes': df['candidatevotes'].isna().sum(),
        'missing_total': df['totalvotes'].isna().sum(),
        'negative_votes': (df['candidatevotes'] < 0).sum(),
        'years': sorted(df['year'].unique()),
        'parties': df['party'].nunique(),
    }
    
    logger.info(f"  Total rows: {validation['total_rows']:,}")
    logger.info(f"  Missing FIPS: {validation['missing_fips']:,}")
    logger.info(f"  Missing votes: {validation['missing_votes']:,}")
    logger.info(f"  Missing total votes: {validation['missing_total']:,}")
    logger.info(f"  Negative votes: {validation['negative_votes']:,}")
    logger.info(f"  Years: {validation['years']}")
    logger.info(f"  Unique parties: {validation['parties']}")
    
    return validation


# ============================================================================
# DATA CLEANING
# ============================================================================

def clean_fips_codes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and standardize FIPS codes.
    
    Args:
        df: DataFrame with county_fips column
        
    Returns:
        DataFrame with standardized fips column
    """
    logger.info("Cleaning FIPS codes...")
    
    # Create new fips column
    df = df.copy()
    
    # Convert to string and remove decimals
    df['fips'] = df['county_fips'].astype(str).str.replace('.0', '', regex=False)
    
    # Pad with leading zeros to 5 digits
    df['fips'] = df['fips'].str.zfill(5)
    
    # Remove rows with invalid FIPS
    valid_fips = df['fips'].str.match(r'^\d{5}$', na=False)
    invalid_count = (~valid_fips).sum()
    
    if invalid_count > 0:
        logger.warning(f"  Removing {invalid_count:,} rows with invalid FIPS codes")
        df = df[valid_fips]
    
    logger.info(f"  Valid FIPS codes: {df['fips'].nunique():,} unique counties")
    
    return df


def standardize_parties(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize party names.
    
    Args:
        df: DataFrame with party column
        
    Returns:
        DataFrame with standardized party column
    """
    logger.info("Standardizing party names...")
    
    df = df.copy()
    
    # Show original party distribution
    original_parties = df['party'].value_counts()
    logger.info(f"  Original parties: {len(original_parties)}")
    
    # Standardize
    df['party'] = df['party'].apply(standardize_party_name)
    
    # Show standardized distribution
    standardized_parties = df['party'].value_counts()
    logger.info(f"  Standardized parties: {len(standardized_parties)}")
    for party, count in standardized_parties.items():
        logger.info(f"    {party}: {count:,} rows")
    
    return df


def handle_missing_votes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing or invalid vote counts.
    
    Args:
        df: DataFrame with candidatevotes column
        
    Returns:
        DataFrame with cleaned vote counts
    """
    logger.info("Handling missing votes...")
    
    df = df.copy()
    
    # Fill missing candidate votes with 0
    missing_votes = df['candidatevotes'].isna().sum()
    if missing_votes > 0:
        logger.warning(f"  Filling {missing_votes:,} missing vote counts with 0")
        df['candidatevotes'] = df['candidatevotes'].fillna(0)
    
    # Convert to integer
    df['candidatevotes'] = df['candidatevotes'].astype(int)
    
    # Remove negative votes
    negative = (df['candidatevotes'] < 0).sum()
    if negative > 0:
        logger.warning(f"  Removing {negative:,} rows with negative votes")
        df = df[df['candidatevotes'] >= 0]
    
    return df


# ============================================================================
# DATA AGGREGATION
# ============================================================================

def aggregate_by_county_party(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Aggregate votes by county and party for a given year.
    
    Args:
        df: Cleaned election data
        year: Election year to process
        
    Returns:
        Aggregated DataFrame
    """
    logger.info(f"\nAggregating data for {year}...")
    
    # Filter to specific year
    year_df = df[df['year'] == year].copy()
    logger.info(f"  Records for {year}: {len(year_df):,}")
    
    # Aggregate by county and party
    # Sum votes in case there are multiple candidates per party
    agg_df = year_df.groupby(['fips', 'state', 'state_po', 'county_name', 'party']).agg({
        'candidatevotes': 'sum',
        'totalvotes': 'first'  # Total votes should be same for all rows in county
    }).reset_index()
    
    # Rename columns
    agg_df.rename(columns={
        'candidatevotes': 'votes',
        'totalvotes': 'total_votes',
        'county_name': 'county'
    }, inplace=True)
    
    logger.info(f"  Counties: {agg_df['fips'].nunique():,}")
    logger.info(f"  Total votes: {agg_df['votes'].sum():,}")
    
    return agg_df


def create_wide_format(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert long format (one row per county-party) to wide format (one row per county).
    
    Args:
        df: Long format DataFrame
        
    Returns:
        Wide format DataFrame with separate columns for each party
    """
    logger.info("Converting to wide format...")
    
    # Pivot to wide format
    wide_df = df.pivot_table(
        index=['fips', 'state', 'state_po', 'county', 'total_votes'],
        columns='party',
        values='votes',
        fill_value=0
    ).reset_index()
    
    # Flatten column names
    wide_df.columns.name = None
    
    # Ensure major party columns exist
    for party in ['DEMOCRAT', 'REPUBLICAN']:
        if party not in wide_df.columns:
            wide_df[party] = 0
    
    # Calculate total major party votes
    wide_df['major_party_votes'] = wide_df['DEMOCRAT'] + wide_df['REPUBLICAN']
    
    # Calculate vote shares and margins
    wide_df['dem_share'] = (wide_df['DEMOCRAT'] / wide_df['major_party_votes'] * 100).round(2)
    wide_df['rep_share'] = (wide_df['REPUBLICAN'] / wide_df['major_party_votes'] * 100).round(2)
    wide_df['margin'] = (wide_df['dem_share'] - wide_df['rep_share']).round(2)
    
    # Determine winner
    wide_df['winner'] = wide_df.apply(
        lambda row: 'DEMOCRAT' if row['DEMOCRAT'] > row['REPUBLICAN'] else 'REPUBLICAN',
        axis=1
    )
    
    # Handle division by zero (counties with no major party votes)
    wide_df['dem_share'] = wide_df['dem_share'].fillna(0)
    wide_df['rep_share'] = wide_df['rep_share'].fillna(0)
    wide_df['margin'] = wide_df['margin'].fillna(0)
    
    logger.info(f"  Wide format: {len(wide_df):,} counties")
    
    return wide_df


# ============================================================================
# DATA QUALITY CHECKS
# ============================================================================

def quality_check(df: pd.DataFrame, year: int) -> Dict[str, Any]:
    """
    Perform quality checks on cleaned data.
    
    Args:
        df: Cleaned DataFrame
        year: Election year
        
    Returns:
        Dictionary with quality metrics
    """
    logger.info(f"\nQuality checks for {year}:")
    
    metrics = {
        'year': year,
        'counties': len(df),
        'total_votes': df['total_votes'].sum(),
        'dem_votes': df.get('DEMOCRAT', pd.Series([0])).sum(),
        'rep_votes': df.get('REPUBLICAN', pd.Series([0])).sum(),
        'min_votes': df['total_votes'].min(),
        'max_votes': df['total_votes'].max(),
        'avg_votes': df['total_votes'].mean(),
        'counties_low_turnout': (df['total_votes'] < MIN_TOTAL_VOTES).sum(),
    }
    
    logger.info(f"  Counties: {metrics['counties']:,}")
    logger.info(f"  Total votes: {metrics['total_votes']:,}")
    logger.info(f"  Democratic votes: {metrics['dem_votes']:,}")
    logger.info(f"  Republican votes: {metrics['rep_votes']:,}")
    logger.info(f"  Vote range: {metrics['min_votes']:,} - {metrics['max_votes']:,}")
    logger.info(f"  Average votes/county: {metrics['avg_votes']:,.0f}")
    
    if metrics['counties_low_turnout'] > 0:
        logger.warning(f"  Counties with <{MIN_TOTAL_VOTES} votes: {metrics['counties_low_turnout']}")
    
    return metrics


# ============================================================================
# EXPORT
# ============================================================================

def export_cleaned_data(df: pd.DataFrame, year: int) -> Path:
    """
    Export cleaned data to CSV.
    
    Args:
        df: Cleaned DataFrame
        year: Election year
        
    Returns:
        Path to exported file
    """
    output_file = ELECTIONS_DIR / f"elections_{year}.csv"
    
    logger.info(f"\nExporting to: {output_file}")
    
    df.to_csv(output_file, index=False)
    
    file_size = output_file.stat().st_size / 1024
    logger.info(f"  File size: {file_size:.1f} KB")
    
    return output_file


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_year(df: pd.DataFrame, year: int) -> Dict[str, Any]:
    """
    Process election data for a single year.
    
    Args:
        df: Raw election DataFrame
        year: Year to process
        
    Returns:
        Dictionary with processing results
    """
    logger.info("=" * 70)
    logger.info(f"PROCESSING YEAR: {year}")
    logger.info("=" * 70)
    
    try:
        # Aggregate data
        agg_df = aggregate_by_county_party(df, year)
        
        # Convert to wide format
        wide_df = create_wide_format(agg_df)
        
        # Quality checks
        metrics = quality_check(wide_df, year)
        
        # Export
        output_file = export_cleaned_data(wide_df, year)
        
        logger.info(f"\n[OK] Successfully processed {year}")
        
        return {
            'year': year,
            'success': True,
            'metrics': metrics,
            'output_file': output_file
        }
        
    except Exception as e:
        logger.error(f"\n[ERROR] Failed to process {year}: {e}")
        return {
            'year': year,
            'success': False,
            'error': str(e)
        }


def process_all_years(df: pd.DataFrame, years: Optional[List[int]] = None) -> List[Dict]:
    """
    Process election data for multiple years.
    
    Args:
        df: Raw election DataFrame
        years: List of years to process (default: all available)
        
    Returns:
        List of processing results
    """
    if years is None:
        years = sorted(df['year'].unique())
    
    results = []
    
    for year in years:
        result = process_year(df, year)
        results.append(result)
    
    return results


def print_summary(results: List[Dict]):
    """
    Print summary of processing results.
    
    Args:
        results: List of processing results
    """
    logger.info("\n" + "=" * 70)
    logger.info("PROCESSING SUMMARY")
    logger.info("=" * 70)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    logger.info(f"\nProcessed: {len(results)} years")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    
    if successful:
        logger.info("\nSuccessful years:")
        for result in successful:
            metrics = result['metrics']
            logger.info(
                f"  {result['year']}: {metrics['counties']:,} counties, "
                f"{metrics['total_votes']:,} total votes"
            )
    
    if failed:
        logger.warning("\nFailed years:")
        for result in failed:
            logger.warning(f"  {result['year']}: {result['error']}")
    
    logger.info("\n" + "=" * 70)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main processing function."""
    parser = argparse.ArgumentParser(
        description="Clean and standardize election data"
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
        "--validate-only",
        action="store_true",
        help="Only validate raw data without processing"
    )
    
    args = parser.parse_args()
    
    try:
        # Load raw data
        df = load_raw_election_data()
        
        # Clean FIPS codes
        df = clean_fips_codes(df)
        
        # Standardize parties
        df = standardize_parties(df)
        
        # Handle missing votes
        df = handle_missing_votes(df)
        
        # Validate
        validation = validate_raw_data(df)
        
        if args.validate_only:
            logger.info("\n[OK] Validation complete. Use --year or --all to process data.")
            return 0
        
        # Process data
        if args.year:
            # Single year
            if args.year not in ELECTION_YEARS:
                logger.error(f"Invalid year: {args.year}. Valid years: {ELECTION_YEARS}")
                return 1
            
            results = [process_year(df, args.year)]
            
        elif args.all:
            # All years
            results = process_all_years(df, ELECTION_YEARS)
            
        else:
            # Default: process most recent year as test
            latest_year = max(df['year'].unique())
            logger.info(f"No year specified. Processing latest year: {latest_year}")
            logger.info("Use --year YEAR to process specific year, or --all for all years")
            results = [process_year(df, latest_year)]
        
        # Print summary
        print_summary(results)
        
        # Return success if all processed successfully
        return 0 if all(r['success'] for r in results) else 1
        
    except Exception as e:
        logger.error(f"\n[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())