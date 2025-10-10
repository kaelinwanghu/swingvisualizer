"""
04_calculate_swings.py
Calculate electoral swings between consecutive election cycles.

This script:
1. Loads cleaned election data for multiple years
2. Calculates partisan swing between election pairs
3. Identifies counties that flipped parties
4. Computes swing magnitude and direction
5. Exports swing calculations

Usage:
    python processing/04_calculate_swings.py [--year1 YEAR1 --year2 YEAR2] [--all]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))
from config import (
    ELECTIONS_DIR, COMBINED_DIR, ELECTION_YEARS,
    get_adjacent_election_pairs, LOG_DIR, LOG_FORMAT
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "04_calculate_swings.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA LOADING
# ============================================================================

def load_election_year(year: int) -> pd.DataFrame:
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
    
    logger.info(f"Loading {year} data: {file_path.name}")
    df = pd.read_csv(file_path)
    
    logger.info(f"  Loaded {len(df):,} counties")
    
    return df


# ============================================================================
# SWING CALCULATIONS
# ============================================================================

def calculate_two_party_swing(
    year1_df: pd.DataFrame,
    year2_df: pd.DataFrame,
    year1: int,
    year2: int
) -> pd.DataFrame:
    """
    Calculate two-party swing between two elections.
    
    Two-party swing = Change in Democratic two-party vote share
    Positive swing = Shift toward Democrats
    Negative swing = Shift toward Republicans
    
    Args:
        year1_df: Election data for first year
        year2_df: Election data for second year
        year1: First election year
        year2: Second election year
        
    Returns:
        DataFrame with swing calculations
    """
    logger.info(f"\nCalculating swing: {year1} -> {year2}")
    
    # Select relevant columns and rename for clarity
    y1 = year1_df[['fips', 'county', 'state', 'state_po', 'dem_share', 'rep_share', 
                    'DEMOCRAT', 'REPUBLICAN', 'total_votes', 'winner']].copy()
    y1.columns = ['fips', 'county', 'state', 'state_po', 'dem_share_y1', 'rep_share_y1',
                  'dem_votes_y1', 'rep_votes_y1', 'total_votes_y1', 'winner_y1']
    
    y2 = year2_df[['fips', 'county', 'state', 'state_po', 'dem_share', 'rep_share',
                    'DEMOCRAT', 'REPUBLICAN', 'total_votes', 'winner']].copy()
    y2.columns = ['fips', 'county', 'state', 'state_po', 'dem_share_y2', 'rep_share_y2',
                  'dem_votes_y2', 'rep_votes_y2', 'total_votes_y2', 'winner_y2']
    
    # Merge on FIPS (inner join - only counties present in both years)
    swing_df = y1.merge(y2, on='fips', how='inner', suffixes=('', '_dup'))
    
    # Keep only one set of identifying columns
    swing_df = swing_df[['fips', 'county', 'state', 'state_po',
                          'dem_share_y1', 'rep_share_y1', 'dem_votes_y1', 'rep_votes_y1', 
                          'total_votes_y1', 'winner_y1',
                          'dem_share_y2', 'rep_share_y2', 'dem_votes_y2', 'rep_votes_y2',
                          'total_votes_y2', 'winner_y2']]
    
    logger.info(f"  Matched {len(swing_df):,} counties in both years")
    
    # Calculate swing (change in Democratic two-party share)
    swing_df['swing'] = swing_df['dem_share_y2'] - swing_df['dem_share_y1']
    
    # Calculate margin change
    margin_y1 = swing_df['dem_share_y1'] - swing_df['rep_share_y1']
    margin_y2 = swing_df['dem_share_y2'] - swing_df['rep_share_y2']
    swing_df['margin_change'] = margin_y2 - margin_y1
    
    # Swing magnitude (absolute value)
    swing_df['swing_magnitude'] = swing_df['swing'].abs()
    
    # Swing direction
    def _swing_direction_label(x):
        if x > 0:
            return 'DEMOCRAT'
        elif x < 0:
            return 'REPUBLICAN'
        else:
            return 'NO_CHANGE'
    swing_df['swing_direction'] = swing_df['swing'].apply(_swing_direction_label)
    
    # Identify county flips
    swing_df['flipped'] = swing_df['winner_y1'] != swing_df['winner_y2']
    swing_df['flip_direction'] = swing_df.apply(
        lambda row: f"{row['winner_y1']}_to_{row['winner_y2']}" if row['flipped'] else 'NO_FLIP',
        axis=1
    )
    
    # Turnout change
    swing_df['turnout_change'] = swing_df['total_votes_y2'] - swing_df['total_votes_y1']
    swing_df['turnout_change_pct'] = (
        (swing_df['total_votes_y2'] - swing_df['total_votes_y1']) / 
        swing_df['total_votes_y1'] * 100
    ).round(2)
    
    # Add year labels
    swing_df['year1'] = year1
    swing_df['year2'] = year2
    swing_df['period'] = f"{year1}_{year2}"
    
    return swing_df


# ============================================================================
# ANALYSIS
# ============================================================================

def analyze_swing(swing_df: pd.DataFrame, year1: int, year2: int) -> Dict:
    """
    Analyze swing patterns and generate statistics.
    
    Args:
        swing_df: DataFrame with swing calculations
        year1: First year
        year2: Second year
        
    Returns:
        Dictionary with analysis results
    """
    logger.info(f"\nAnalyzing swing patterns: {year1} -> {year2}")
    
    analysis = {
        'year1': year1,
        'year2': year2,
        'total_counties': len(swing_df),
        'avg_swing': swing_df['swing'].mean(),
        'median_swing': swing_df['swing'].median(),
        'std_swing': swing_df['swing'].std(),
        'max_dem_swing': swing_df['swing'].max(),
        'max_rep_swing': swing_df['swing'].min(),
        'counties_swing_dem': (swing_df['swing'] > 0).sum(),
        'counties_swing_rep': (swing_df['swing'] < 0).sum(),
        'counties_no_swing': (swing_df['swing'] == 0).sum(),
        'total_flips': swing_df['flipped'].sum(),
        'dem_to_rep': ((swing_df['winner_y1'] == 'DEMOCRAT') & 
                       (swing_df['winner_y2'] == 'REPUBLICAN')).sum(),
        'rep_to_dem': ((swing_df['winner_y1'] == 'REPUBLICAN') & 
                       (swing_df['winner_y2'] == 'DEMOCRAT')).sum(),
        'avg_turnout_change_pct': swing_df['turnout_change_pct'].mean(),
    }
    
    logger.info(f"  Average swing: {analysis['avg_swing']:+.2f}% toward "
                f"{'Democrats' if analysis['avg_swing'] > 0 else 'Republicans'}")
    logger.info(f"  Median swing: {analysis['median_swing']:+.2f}%")
    logger.info(f"  Swing range: {analysis['max_rep_swing']:.2f}% to {analysis['max_dem_swing']:.2f}%")
    logger.info(f"  Counties swinging toward Democrats: {analysis['counties_swing_dem']:,}")
    logger.info(f"  Counties swinging toward Republicans: {analysis['counties_swing_rep']:,}")
    logger.info(f"  Total county flips: {analysis['total_flips']:,}")
    logger.info(f"    Democrat -> Republican: {analysis['dem_to_rep']:,}")
    logger.info(f"    Republican -> Democrat: {analysis['rep_to_dem']:,}")
    logger.info(f"  Average turnout change: {analysis['avg_turnout_change_pct']:+.1f}%")
    
    return analysis


def identify_bellwether_counties(all_swings: List[pd.DataFrame]) -> pd.DataFrame:
    """
    Identify counties with consistent swing patterns.
    
    Args:
        all_swings: List of swing DataFrames for all election pairs
        
    Returns:
        DataFrame with bellwether analysis
    """
    logger.info("\nIdentifying bellwether counties...")
    
    # For each county, count how often it flipped
    all_fips = set()
    for df in all_swings:
        all_fips.update(df['fips'].unique())
    
    bellwether_data = []
    
    for fips in all_fips:
        county_swings = []
        county_info = None
        
        for df in all_swings:
            county_data = df[df['fips'] == fips]
            if not county_data.empty:
                if county_info is None:
                    county_info = {
                        'fips': fips,
                        'county': county_data.iloc[0]['county'],
                        'state': county_data.iloc[0]['state']
                    }
                county_swings.append({
                    'period': county_data.iloc[0]['period'],
                    'swing': county_data.iloc[0]['swing'],
                    'flipped': county_data.iloc[0]['flipped']
                })
        
        if county_info and county_swings:
            avg_swing_magnitude = np.mean([abs(s['swing']) for s in county_swings])
            total_flips = sum([s['flipped'] for s in county_swings])
            
            county_info['appearances'] = len(county_swings)
            county_info['total_flips'] = total_flips
            county_info['avg_swing_magnitude'] = avg_swing_magnitude
            
            bellwether_data.append(county_info)
    
    bellwether_df = pd.DataFrame(bellwether_data)
    
    if not bellwether_df.empty:
        logger.info(f"  Analyzed {len(bellwether_df):,} counties across all periods")
        logger.info(f"  Most volatile: {bellwether_df.nlargest(5, 'avg_swing_magnitude')[['county', 'state', 'avg_swing_magnitude']].to_string(index=False)}")
    
    return bellwether_df


# ============================================================================
# EXPORT
# ============================================================================

def export_swing_data(swing_df: pd.DataFrame, year1: int, year2: int) -> Path:
    """
    Export swing calculations to CSV.
    
    Args:
        swing_df: DataFrame with swing data
        year1: First year
        year2: Second year
        
    Returns:
        Path to exported file
    """
    output_file = COMBINED_DIR / f"swings_{year1}_to_{year2}.csv"
    
    logger.info(f"\nExporting to: {output_file}")
    
    swing_df.to_csv(output_file, index=False)
    
    file_size = output_file.stat().st_size / 1024
    logger.info(f"  File size: {file_size:.1f} KB")
    
    return output_file


def export_summary_stats(analyses: List[Dict]) -> Path:
    """
    Export summary statistics across all election pairs.
    
    Args:
        analyses: List of analysis dictionaries
        
    Returns:
        Path to summary file
    """
    summary_df = pd.DataFrame(analyses)
    output_file = COMBINED_DIR / "swing_summary.csv"
    
    logger.info(f"\nExporting summary to: {output_file}")
    summary_df.to_csv(output_file, index=False)
    
    return output_file


# ============================================================================
# MAIN
# ============================================================================

def process_swing_pair(year1: int, year2: int) -> Tuple[pd.DataFrame, Dict]:
    """
    Process swing calculation for a pair of election years.
    
    Args:
        year1: First election year
        year2: Second election year
        
    Returns:
        Tuple of (swing DataFrame, analysis dict)
    """
    logger.info("=" * 70)
    logger.info(f"CALCULATING SWING: {year1} -> {year2}")
    logger.info("=" * 70)
    
    try:
        # Load data
        year1_df = load_election_year(year1)
        year2_df = load_election_year(year2)
        
        # Calculate swing
        swing_df = calculate_two_party_swing(year1_df, year2_df, year1, year2)
        
        # Analyze patterns
        analysis = analyze_swing(swing_df, year1, year2)
        
        # Export
        export_swing_data(swing_df, year1, year2)
        
        logger.info(f"\n[OK] Successfully processed swing: {year1} -> {year2}")
        
        return swing_df, analysis
        
    except Exception as e:
        logger.error(f"\n[ERROR] Failed to process swing: {e}")
        raise


def main():
    """Main processing function."""
    parser = argparse.ArgumentParser(
        description="Calculate electoral swings between elections"
    )
    parser.add_argument(
        "--year1",
        type=int,
        help="First election year"
    )
    parser.add_argument(
        "--year2",
        type=int,
        help="Second election year"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all adjacent election pairs"
    )
    
    args = parser.parse_args()
    
    try:
        all_swings = []
        all_analyses = []
        
        if args.year1 and args.year2:
            # Single pair
            if args.year1 >= args.year2:
                logger.error("year1 must be less than year2")
                return 1
            
            swing_df, analysis = process_swing_pair(args.year1, args.year2)
            all_swings.append(swing_df)
            all_analyses.append(analysis)
            
        elif args.all:
            # All adjacent pairs
            pairs = get_adjacent_election_pairs()
            logger.info(f"\nProcessing {len(pairs)} election pairs")
            
            for year1, year2 in pairs:
                try:
                    swing_df, analysis = process_swing_pair(year1, year2)
                    all_swings.append(swing_df)
                    all_analyses.append(analysis)
                except Exception as e:
                    logger.error(f"Failed to process {year1}->{year2}: {e}")
                    continue
        
        else:
            # Default: most recent pair
            pairs = get_adjacent_election_pairs()
            if pairs:
                year1, year2 = pairs[-1]
                logger.info(f"No years specified. Processing most recent pair: {year1} -> {year2}")
                logger.info("Use --year1 YEAR1 --year2 YEAR2 for specific pair, or --all for all pairs")
                
                swing_df, analysis = process_swing_pair(year1, year2)
                all_swings.append(swing_df)
                all_analyses.append(analysis)
            else:
                logger.error("No election pairs available")
                return 1
        
        # Summary
        if len(all_analyses) > 1:
            logger.info("\n" + "=" * 70)
            logger.info("SUMMARY ACROSS ALL PERIODS")
            logger.info("=" * 70)
            
            export_summary_stats(all_analyses)
            
            # Identify bellwether counties
            bellwether_df = identify_bellwether_counties(all_swings)
            if not bellwether_df.empty:
                bellwether_file = COMBINED_DIR / "bellwether_counties.csv"
                bellwether_df.to_csv(bellwether_file, index=False)
                logger.info(f"Exported bellwether analysis: {bellwether_file}")
        
        logger.info("\n" + "=" * 70)
        logger.info("[OK] Swing calculations complete")
        logger.info("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())