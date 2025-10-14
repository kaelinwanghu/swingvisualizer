"""
06_calculate_trends.py
Calculate long-term political trends and classifications for counties.

This script:
1. Loads all election years for each county
2. Calculates trend metrics (stability, volatility, trajectory)
3. Classifies counties (solid, lean, swing, bellwether)
4. Adds metrics back to each year's GeoJSON file
5. FIXES boolean fields (flipped) and handles NaN values properly

Usage:
    python processing/06_calculate_trends.py [--recalculate]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd
import numpy as np
import geopandas as gpd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))
from config import (
    COMBINED_DIR, ELECTION_YEARS, LOG_DIR, LOG_FORMAT
)
from utils.geo_utils import convert_to_geojson

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "06_calculate_trends.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLEANING
# ============================================================================

def clean_boolean_field(value) -> bool:
    """
    Convert string/mixed boolean values to proper Python bool.
    
    Args:
        value: Value to convert
        
    Returns:
        Boolean value
    """
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes']
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def clean_numeric_field(value, default=0.0):
    """
    Clean numeric field, handling NaN values.
    
    Args:
        value: Value to clean
        default: Default value if NaN
        
    Returns:
        Cleaned numeric value
    """
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ============================================================================
# TREND CALCULATIONS
# ============================================================================

def calculate_county_trends(county_history: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate trend metrics for a single county across all years.
    
    Args:
        county_history: DataFrame with one row per year for this county
        
    Returns:
        Dictionary with trend metrics
    """
    # Sort by year
    county_history = county_history.sort_values('year')
    
    metrics: Dict[str, Any] = {
        'years_with_data': int(len(county_history)),
        'first_year': int(county_history['year'].min()),
        'last_year': int(county_history['year'].max())
    }
    
    # Skip if insufficient data
    if len(county_history) < 3:
        return {**metrics, 'classification': 'INSUFFICIENT_DATA'}
    
    # Get margins (positive = Dem, negative = Rep)
    margins = county_history['margin'].fillna(0).to_numpy()
    winners = county_history['winner'].fillna('UNKNOWN').to_numpy()
    
    # === STABILITY METRICS ===
    
    # How many times did the winner stay the same?
    flips = sum(1 for i in range(1, len(winners)) if winners[i] != winners[i-1])
    metrics['total_flips'] = int(flips)
    metrics['flip_rate'] = float(flips / (len(winners) - 1)) if len(winners) > 1 else 0.0
    
    # === LEAN METRICS ===
    
    # Average margin over all years
    metrics['avg_margin'] = float(np.mean(margins))
    metrics['median_margin'] = float(np.median(margins))
    
    # Standard deviation of margins (volatility)
    metrics['margin_std'] = float(np.std(margins))
    
    # How often did each party win?
    dem_wins = int(np.sum(winners == 'DEMOCRAT'))
    rep_wins = int(np.sum(winners == 'REPUBLICAN'))
    total_known = dem_wins + rep_wins
    
    if total_known > 0:
        metrics['dem_win_pct'] = float(dem_wins / total_known * 100)
        metrics['rep_win_pct'] = float(rep_wins / total_known * 100)
    else:
        metrics['dem_win_pct'] = 0.0
        metrics['rep_win_pct'] = 0.0
    
    # === TRAJECTORY (Linear Trend) ===
    
    # Is the county moving left or right?
    years_numeric = county_history['year'].to_numpy()
    if len(years_numeric) >= 3:
        # Normalize years to prevent overflow
        years_normalized = (years_numeric - years_numeric.min()) / 4  # Divide by election cycle
        slope = np.polyfit(years_normalized, margins, 1)[0]
        metrics['trajectory'] = float(slope)
        
        # Classify trajectory
        if slope > 2:
            metrics['trajectory_direction'] = 'TRENDING_DEM'
        elif slope < -2:
            metrics['trajectory_direction'] = 'TRENDING_REP'
        else:
            metrics['trajectory_direction'] = 'STABLE'
    else:
        metrics['trajectory'] = 0.0
        metrics['trajectory_direction'] = 'INSUFFICIENT_DATA'
    
    # === VOLATILITY ===
    
    # Calculate swing magnitudes
    if 'swing' in county_history.columns:
        swings = county_history['swing'].fillna(0).to_numpy()
        if len(swings) > 0:
            metrics['avg_swing_magnitude'] = float(np.mean(np.abs(swings)))
            metrics['max_swing'] = float(np.max(np.abs(swings)))
        else:
            metrics['avg_swing_magnitude'] = 0.0
            metrics['max_swing'] = 0.0
    else:
        metrics['avg_swing_magnitude'] = 0.0
        metrics['max_swing'] = 0.0
    
    # === COMPETITIVENESS ===
    
    # How often were elections close (margin < 5%)?
    close_elections = int(np.sum(np.abs(margins) < 5))
    metrics['close_election_rate'] = float(close_elections / len(margins) * 100)
    
    # Average absolute margin (how competitive on average)
    metrics['avg_competitiveness'] = float(np.mean(np.abs(margins)))
    
    # === CLASSIFICATION ===
    
    metrics['classification'] = classify_county(metrics)
    
    # === BELLWETHER SCORE ===
    
    metrics['bellwether_score'] = float(calculate_bellwether_score(county_history))
    
    return metrics


def classify_county(metrics: Dict[str, Any]) -> str:
    """
    Classify county based on voting patterns.
    
    Classifications:
    - SOLID_DEM / SOLID_REP: Consistently one party, rarely competitive
    - LEAN_DEM / LEAN_REP: Usually one party, occasionally competitive
    - SWING: Frequently flips or highly competitive
    - COMPETITIVE: Close elections, leans slightly one way
    
    Args:
        metrics: Dictionary with calculated metrics
        
    Returns:
        Classification string
    """
    avg_margin = metrics['avg_margin']
    margin_std = metrics['margin_std']
    flip_rate = metrics['flip_rate']
    close_rate = metrics['close_election_rate']
    
    # Solid: Avg margin > 15%, low volatility, rarely flips
    if abs(avg_margin) > 15 and margin_std < 8 and flip_rate < 0.2:
        return 'SOLID_DEM' if avg_margin > 0 else 'SOLID_REP'
    
    # Lean: Avg margin 5-15%, moderate volatility
    elif abs(avg_margin) > 5 and flip_rate < 0.4:
        return 'LEAN_DEM' if avg_margin > 0 else 'LEAN_REP'
    
    # Swing: Flips often OR very competitive
    elif flip_rate >= 0.4 or close_rate > 60:
        return 'SWING'
    
    # Competitive but leans one way
    elif abs(avg_margin) <= 5:
        return 'COMPETITIVE_DEM' if avg_margin > 0 else 'COMPETITIVE_REP'
    
    # Default to lean
    else:
        return 'LEAN_DEM' if avg_margin > 0 else 'LEAN_REP'


def calculate_bellwether_score(county_history: pd.DataFrame) -> float:
    """
    Calculate how well county predicts national winner.
    
    Score of 100 = perfect bellwether, 0 = always wrong
    
    Args:
        county_history: DataFrame with county results
        
    Returns:
        Bellwether score (0-100)
    """
    # National popular vote winners by year
    NATIONAL_WINNERS: Dict[int, str] = {
        2000: 'DEMOCRAT',   # Gore won popular vote
        2004: 'REPUBLICAN',
        2008: 'DEMOCRAT',
        2012: 'DEMOCRAT',
        2016: 'DEMOCRAT',   # Clinton won popular vote
        2020: 'DEMOCRAT',
        2024: 'REPUBLICAN'
    }
    
    matches = 0
    total = 0
    
    for _, row in county_history.iterrows():
        year = int(row['year'])
        if year in NATIONAL_WINNERS:
            winner = str(row['winner']) if pd.notna(row['winner']) else 'UNKNOWN'
            if winner == NATIONAL_WINNERS[year]:
                matches += 1
            total += 1
    
    return float((matches / total * 100)) if total > 0 else 0.0


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def load_all_county_data() -> pd.DataFrame:
    """
    Load all years of election data and combine into one DataFrame.
    
    Returns:
        DataFrame with all counties across all years
    """
    logger.info("Loading all election years...")
    
    all_data = []
    
    for year in ELECTION_YEARS:
        file_path = COMBINED_DIR / f"election_map_{year}.geojson"
        
        if not file_path.exists():
            logger.warning(f"  Missing data for {year}")
            continue
        
        # Load GeoJSON and convert to DataFrame (without geometry for speed)
        gdf = gpd.read_file(file_path)
        df = pd.DataFrame(gdf.drop(columns='geometry'))
        
        # Fix boolean fields that might be strings
        if 'flipped' in df.columns:
            df['flipped'] = df['flipped'].apply(clean_boolean_field)
        
        all_data.append(df)
        logger.info(f"  Loaded {year}: {len(df):,} counties")
    
    # Combine all years
    combined = pd.concat(all_data, ignore_index=True)
    logger.info(f"\nTotal records: {len(combined):,}")
    logger.info(f"Unique counties: {combined['fips'].nunique():,}")
    
    return combined


def calculate_all_trends(all_data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate trends for all counties.
    
    Args:
        all_data: DataFrame with all counties across all years
        
    Returns:
        DataFrame with trend metrics per FIPS
    """
    logger.info("\nCalculating trends for all counties...")
    
    trends = []
    
    # Group by FIPS and calculate trends
    for fips, group in all_data.groupby('fips'):
        trend = calculate_county_trends(group)
        trend['fips'] = fips
        trends.append(trend)
    
    trends_df = pd.DataFrame(trends)
    
    logger.info(f"  Calculated trends for {len(trends_df):,} counties")
    
    # Log classification distribution
    logger.info("\nClassification Distribution:")
    for classification, count in trends_df['classification'].value_counts().items():
        pct = count / len(trends_df) * 100
        logger.info(f"  {classification}: {count:,} ({pct:.1f}%)")
    
    return trends_df


def merge_trends_into_geojson(year: int, trends_df: pd.DataFrame) -> bool:
    """
    Merge trend data back into a year's GeoJSON file.
    
    Also fixes any data type issues (booleans, NaN values).
    
    Args:
        year: Election year
        trends_df: DataFrame with trend metrics
        
    Returns:
        True if successful
    """
    file_path = COMBINED_DIR / f"election_map_{year}.geojson"
    
    if not file_path.exists():
        logger.warning(f"  File not found: {file_path}")
        return False
    
    logger.info(f"\nProcessing {year}...")
    
    # Load GeoJSON
    gdf = gpd.read_file(file_path)
    logger.info(f"  Loaded {len(gdf):,} counties")
    
    # Fix boolean fields before merge
    if 'flipped' in gdf.columns:
        logger.info("  Fixing 'flipped' field...")
        gdf['flipped'] = gdf['flipped'].apply(clean_boolean_field)
    
    # Merge trends
    # Drop any duplicate columns first to avoid conflicts
    duplicate_cols = [col for col in trends_df.columns if col in gdf.columns and col != 'fips']
    if duplicate_cols:
        logger.info(f"  Dropping duplicate columns before merge: {duplicate_cols}")
        gdf = gdf.drop(columns=duplicate_cols)
    
    gdf = gdf.merge(trends_df, on='fips', how='left')
    logger.info("  Merged trends data")
    
    # Count how many got trends added (check if classification exists)
    if 'classification' in gdf.columns:
        with_trends = gdf['classification'].notna().sum()
        logger.info(f"  Added trends to {with_trends:,} counties")
    else:
        logger.warning(f"  Warning: 'classification' column not found after merge")
    
    # Fill NaN values with appropriate defaults
    numeric_cols = gdf.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col not in ['geometry']:
            gdf[col] = gdf[col].fillna(0)
    
    # Fill string NaN with empty string or appropriate default
    string_cols = gdf.select_dtypes(include=['object']).columns
    for col in string_cols:
        if col not in ['geometry']:
            gdf[col] = gdf[col].fillna('')
    
    # Save back to GeoJSON
    output_file = COMBINED_DIR / f"election_map_{year}.geojson"
    convert_to_geojson(gdf, output_file, precision=5)
    
    return True


# ============================================================================
# EXPORT SUMMARY STATS
# ============================================================================

def export_classification_summary(trends_df: pd.DataFrame) -> Path:
    """
    Export summary statistics about county classifications.
    
    Args:
        trends_df: DataFrame with trends
        
    Returns:
        Path to exported file
    """
    output_file = COMBINED_DIR / "county_classifications.csv"
    
    logger.info(f"\nExporting classification summary: {output_file}")
    
    # Select interesting columns
    summary = trends_df[[
        'fips', 'classification', 'avg_margin', 'margin_std',
        'trajectory', 'trajectory_direction', 'total_flips',
        'bellwether_score', 'avg_competitiveness'
    ]].sort_values('fips')
    
    summary.to_csv(output_file, index=False)
    
    logger.info(f"  Exported {len(summary):,} counties")
    
    return output_file


def export_bellwether_counties(trends_df: pd.DataFrame) -> Path:
    """
    Export list of top bellwether counties.
    
    Args:
        trends_df: DataFrame with trends
        
    Returns:
        Path to exported file
    """
    output_file = COMBINED_DIR / "bellwether_counties.csv"
    
    logger.info(f"\nExporting bellwether counties: {output_file}")
    
    # Get swing counties with high bellwether scores
    bellwethers = trends_df[
        (trends_df['classification'] == 'SWING') &
        (trends_df['bellwether_score'] >= 80)
    ].sort_values('bellwether_score', ascending=False)
    
    bellwethers.to_csv(output_file, index=False)
    
    logger.info(f"  Found {len(bellwethers):,} bellwether counties")
    
    if len(bellwethers) > 0:
        logger.info("\nTop 10 Bellwether Counties:")
        for _, row in bellwethers.head(10).iterrows():
            logger.info(f"  {row['fips']}: Score {row['bellwether_score']:.0f}, "
                       f"Flips: {row['total_flips']}")
    
    return output_file


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main processing function."""
    parser = argparse.ArgumentParser(
        description="Calculate political trends for counties"
    )
    parser.add_argument(
        "--recalculate",
        action="store_true",
        help="Recalculate even if trends already exist"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("=" * 70)
        logger.info("CALCULATING COUNTY POLITICAL TRENDS")
        logger.info("=" * 70)
        
        # Load all data
        all_data = load_all_county_data()
        
        if all_data.empty:
            logger.error("No data loaded. Please run previous pipeline steps.")
            return 1
        
        # Calculate trends
        trends_df = calculate_all_trends(all_data)
        
        # Merge back into each year's GeoJSON
        logger.info("\n" + "=" * 70)
        logger.info("MERGING TRENDS INTO GEOJSON FILES")
        logger.info("=" * 70)
        
        success_count = 0
        for year in ELECTION_YEARS:
            if merge_trends_into_geojson(year, trends_df):
                success_count += 1
        
        logger.info(f"\nSuccessfully updated {success_count}/{len(ELECTION_YEARS)} years")
        
        # Export summaries
        export_classification_summary(trends_df)
        export_bellwether_counties(trends_df)
        
        logger.info("\n" + "=" * 70)
        logger.info("[OK] Trend calculation complete")
        logger.info("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n[ERROR] Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())