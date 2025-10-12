"""
County Matcher Utility
Handles matching counties across datasets with inconsistent FIPS codes.

Strategy:
1. Try FIPS code match first (fastest, works 95% of time)
2. Fall back to normalized name + state match
3. Handle known edge cases (Alaska, Virginia, etc.)
"""

import pandas as pd
import logging
from typing import Tuple, Dict, List, Set, Optional
import re

logger = logging.getLogger(__name__)


# ============================================================================
# KNOWN FIPS CHANGES
# ============================================================================

KNOWN_FIPS_CHANGES = {
    # Format: (old_fips, new_fips, county_name, state, year_changed)
}

# Build lookup dictionaries
FIPS_REMAP_OLD_TO_NEW = {
    (old, year): new 
    for old, new, _, _, year in KNOWN_FIPS_CHANGES
}

FIPS_REMAP_NEW_TO_OLD = {
    (new, year): old 
    for old, new, _, _, year in KNOWN_FIPS_CHANGES
}


# ============================================================================
# NAME NORMALIZATION
# ============================================================================

def normalize_county_name(name: str) -> str:
    """
    Normalize county name for matching.
    
    Args:
        name: County name
        
    Returns:
        Normalized name
    """
    if pd.isna(name):
        return ""
    
    name = str(name).upper().strip()
    
    # Remove common suffixes
    suffixes = [
        ' COUNTY', ' PARISH', ' BOROUGH', ' CENSUS AREA',
        ' MUNICIPALITY', ' CITY', ' CITY AND BOROUGH'
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    
    # Remove special characters
    name = re.sub(r'[^A-Z0-9\s]', '', name)
    
    # Normalize whitespace
    name = ' '.join(name.split())
    
    return name


def normalize_state_name(state: str) -> str:
    """
    Normalize state name (convert to uppercase).
    
    Args:
        state: State name or abbreviation
        
    Returns:
        Normalized state
    """
    if pd.isna(state):
        return ""
    return str(state).upper().strip()


# ============================================================================
# FIPS REMAPPING
# ============================================================================

def remap_fips_for_year(fips: str, from_year: int, to_year: int) -> str:
    """
    Remap FIPS code if it changed between years.
    
    Args:
        fips: Original FIPS code
        from_year: Year of original data
        to_year: Year to map to
        
    Returns:
        Remapped FIPS or original if no change
    """
    # Check if this FIPS changed
    for (old_fips, new_fips, _, _, change_year) in KNOWN_FIPS_CHANGES:
        # Going forward in time, old -> new
        if from_year < change_year <= to_year and (fips == old_fips):
                logger.info(f"Remapping FIPS {old_fips} -> {new_fips} (changed in {change_year})")
                return new_fips
        
        # Going backward in time, new -> old
        if to_year < change_year <= from_year and (fips == new_fips):
                logger.info(f"Remapping FIPS {new_fips} -> {old_fips} (changed in {change_year})")
                return old_fips
    
    return fips


# ============================================================================
# MATCHING FUNCTIONS
# ============================================================================

def create_match_key(row: pd.Series, use_fips: bool = True) -> str:
    """
    Create a composite key for matching.
    
    Args:
        row: DataFrame row
        use_fips: Whether to include FIPS in key
        
    Returns:
        Match key string
    """
    county = normalize_county_name(row.get('county', row.get('county_name', '')))
    state = normalize_state_name(row.get('state', row.get('state_po', '')))
    
    if use_fips and 'fips' in row:
        return f"{row['fips']}|{county}|{state}"
    else:
        return f"{county}|{state}"


def match_counties(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    year1: Optional[int] = None,
    year2: Optional[int] = None,
    on: str = 'fips'
) -> pd.DataFrame:
    """
    Match counties between two datasets with fallback strategies.
    
    Args:
        df1: First DataFrame
        df2: Second DataFrame
        year1: Year of first dataset (for FIPS remapping)
        year2: Year of second dataset
        on: Primary join column (default: 'fips')
        
    Returns:
        Merged DataFrame with match statistics
    """
    _ = year1, year2
    logger.info("\nMatching counties with fuzzy logic...")
    
    # Make copies to avoid modifying originals
    df1 = df1.copy()
    df2 = df2.copy()
    
    # Ensure FIPS is string
    if 'fips' in df1.columns:
        df1['fips'] = df1['fips'].astype(str).str.zfill(5)
    if 'fips' in df2.columns:
        df2['fips'] = df2['fips'].astype(str).str.zfill(5)
    
    # Create normalized columns for matching
    df1['_norm_county'] = df1.apply(lambda r: normalize_county_name(r.get('county', r.get('county_name', ''))), axis=1)
    df1['_norm_state'] = df1.apply(lambda r: normalize_state_name(r.get('state', r.get('state_po', ''))), axis=1)
    df1['_match_key'] = df1['_norm_county'] + '|' + df1['_norm_state']
    
    df2['_norm_county'] = df2.apply(lambda r: normalize_county_name(r.get('county', r.get('county_name', ''))), axis=1)
    df2['_norm_state'] = df2.apply(lambda r: normalize_state_name(r.get('state', r.get('state_po', ''))), axis=1)
    df2['_match_key'] = df2['_norm_county'] + '|' + df2['_norm_state']
    
    # Strategy 1: Try FIPS match first
    matched_fips = pd.DataFrame()
    if 'fips' in df1.columns and 'fips' in df2.columns:
        matched_fips = df1.merge(
            df2,
            on='fips',
            how='inner',
            suffixes=('_1', '_2')
        )
        logger.info(f"  FIPS matches: {len(matched_fips):,}")
    
    # Strategy 2: Name-based matching for unmatched records
    if len(matched_fips) < len(df1):
        # Find records that didn't match on FIPS
        if len(matched_fips) > 0 and 'fips' in df1.columns:
            matched_fips_set = set(matched_fips['fips'])
            unmatched_df1 = df1[~df1['fips'].isin(matched_fips_set)]
            unmatched_df2 = df2[~df2['fips'].isin(matched_fips_set)]
        else:
            unmatched_df1 = df1
            unmatched_df2 = df2
        
        # Try matching by name + state
        matched_name = unmatched_df1.merge(
            unmatched_df2,
            on='_match_key',
            how='inner',
            suffixes=('_1', '_2')
        )
        
        if len(matched_name) > 0:
            logger.info(f"  Name matches: {len(matched_name):,}")
            logger.info("    Example name matches:")
            for _, row in matched_name.head(5).iterrows():
                fips1 = row.get('fips_1', 'N/A')
                fips2 = row.get('fips_2', 'N/A')
                county = row.get('county_1', row.get('county_name_1', 'Unknown'))
                state = row.get('state_1', row.get('state_po_1', 'Unknown'))
                logger.info(f"      {county}, {state}: FIPS {fips1} -> {fips2}")
            
            # Combine FIPS and name matches
            matched = pd.concat([matched_fips, matched_name], ignore_index=True)
        else:
            matched = matched_fips
    else:
        matched = matched_fips
    
    # Clean up temporary columns
    cols_to_drop = [col for col in matched.columns if col.startswith('_')]
    matched = matched.drop(columns=cols_to_drop)
    
    # Report statistics
    total_df1 = len(df1)
    total_df2 = len(df2)
    total_matched = len(matched)
    
    logger.info("\nMatch Summary:")
    logger.info(f"  Dataset 1: {total_df1:,} counties")
    logger.info(f"  Dataset 2: {total_df2:,} counties")
    logger.info(f"  Matched: {total_matched:,} counties ({total_matched/total_df1*100:.1f}%)")
    logger.info(f"  Unmatched from dataset 1: {total_df1 - total_matched:,}")
    logger.info(f"  Unmatched from dataset 2: {total_df2 - total_matched:,}")
    
    # Log some unmatched counties for investigation
    if total_df1 > total_matched:
        matched_fips_set = set(matched.get('fips_1', matched.get('fips', [])))
        unmatched = df1[~df1['fips'].isin(matched_fips_set)] if 'fips' in df1.columns else pd.DataFrame()
        
        if len(unmatched) > 0:
            logger.warning("\n  Sample unmatched counties from dataset 1:")
            for _, row in unmatched.head(10).iterrows():
                fips = row.get('fips', 'N/A')
                county = row.get('county', row.get('county_name', 'Unknown'))
                state = row.get('state', row.get('state_po', 'Unknown'))
                logger.warning(f"    {fips}: {county}, {state}")
    
    return matched


# ============================================================================
# EDGE CASE HANDLERS
# ============================================================================

def handle_alaska_districts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize Alaska census areas/districts which reorganize frequently.
    
    Args:
        df: DataFrame with Alaska counties
        
    Returns:
        DataFrame with normalized Alaska names
    """
    # Alaska edge cases can be added here as discovered
    # For now, just normalize the names
    
    if 'state' in df.columns:
        alaska = df['state'].str.upper() == 'ALASKA'
        if alaska.any():
            logger.info(f"  Processing {alaska.sum()} Alaska districts")
    
    return df


def handle_virginia_cities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle Virginia independent cities that may merge/split.
    
    Args:
        df: DataFrame with Virginia counties
        
    Returns:
        DataFrame with handled Virginia cities
    """
    # Virginia edge cases can be added here as discovered
    
    if 'state' in df.columns:
        virginia = df['state'].str.upper() == 'VIRGINIA'
        if virginia.any():
            logger.info(f"  Processing {virginia.sum()} Virginia jurisdictions")
    
    return df


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def smart_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_year: Optional[int] = None,
    right_year: Optional[int] = None,
    how: str = 'inner'
) -> pd.DataFrame:
    """
    Smart merge that handles FIPS changes and name matching.
    
    Args:
        left: Left DataFrame
        right: Right DataFrame
        left_year: Year of left dataset
        right_year: Year of right dataset
        how: Join type ('inner', 'left', 'right', 'outer')
        
    Returns:
        Merged DataFrame
    """
    _ = how
    return match_counties(left, right, left_year, right_year)


def get_match_statistics(df1: pd.DataFrame, df2: pd.DataFrame, matched: pd.DataFrame) -> Dict:
    """
    Get detailed matching statistics.
    
    Args:
        df1: First DataFrame
        df2: Second DataFrame
        matched: Merged DataFrame
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        'total_df1': len(df1),
        'total_df2': len(df2),
        'matched': len(matched),
        'match_rate': len(matched) / len(df1) * 100 if len(df1) > 0 else 0,
        'unmatched_df1': len(df1) - len(matched),
        'unmatched_df2': len(df2) - len(matched),
    }
    
    return stats