"""
fix_2024_fips.py
Fix MIT Election Lab 2024 FIPS code errors by matching on county name + state

Strategy:
1. Load 2020 data as reference (known good FIPS codes)
2. For 2024, ignore FIPS from MIT and match by county name + state to get correct FIPS
3. Re-aggregate with corrected FIPS codes
"""

import pandas as pd
import logging
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from config import MIT_DIR, ELECTIONS_DIR, LOG_DIR, LOG_FORMAT

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "fix_2024_fips.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def normalize_county_name(name):
    """Normalize county name for matching."""
    if pd.isna(name):
        return ""
    name = str(name).upper().strip()
    
    # Normalize "ST." to "ST" and "STE." to "STE"
    name = name.replace('ST.', 'ST').replace('STE.', 'STE')
    
    # Normalize "SAINT" to "ST"
    name = name.replace('SAINT ', 'ST ')
    
    # Normalize Alaska districts: "DISTRICT 01" -> "DISTRICT 1"
    import re
    name = re.sub(r'DISTRICT\s+0(\d+)', r'DISTRICT \1', name)
    
    # Normalize spacing in common two-word names
    # Handle "DE WITT" -> "DEWITT", "JO DAVIESS" -> "JODAVIESS", etc.
    spacing_fixes = {
        'DE WITT': 'DEWITT',
        'DE KALB' : 'DEKALB',
        'JO DAVIESS': 'JODAVIESS',
        'LA SALLE': 'LASALLE',
        'DU PAGE': 'DUPAGE',
    }
    for spaced, unspaced in spacing_fixes.items():
        if spaced in name:
            name = name.replace(spaced, unspaced)
    
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name)
    
    # Remove common suffixes BUT preserve CITY/COUNTY distinction for places that have both
    # These jurisdictions have both a city and county with the same name:
    preserve_city_county = ['BALTIMORE', 'ST LOUIS', 'FAIRFAX', 'FRANKLIN', 'RICHMOND', 'ROANOKE']
    
    should_preserve = any(pc in name for pc in preserve_city_county)
    
    if should_preserve:
        # For these, only remove PARISH, BOROUGH, CENSUS AREA
        for suffix in [' PARISH', ' BOROUGH', ' CENSUS AREA']:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
    else:
        # For all others, remove all suffixes
        for suffix in [' COUNTY', ' PARISH', ' BOROUGH', ' CENSUS AREA', ' CITY']:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
    
    return name


def normalize_state_name(state):
    """Normalize state name."""
    if pd.isna(state):
        return ""
    return str(state).upper().strip()


def create_fips_lookup(df_2020):
    """Create a county name + state -> FIPS lookup from 2020 data."""
    logger.info("Creating FIPS lookup from 2020 data...")
    
    lookup = {}
    for _, row in df_2020.iterrows():
        key = (normalize_county_name(row['county']), normalize_state_name(row['state']))
        lookup[key] = row['fips']
    
    logger.info(f"  Created lookup with {len(lookup):,} entries")
    return lookup


def fix_2024_fips():
    """Fix 2024 FIPS codes using 2020 reference data."""
    
    logger.info("=" * 70)
    logger.info("FIXING 2024 FIPS CODES")
    logger.info("=" * 70)
    
    # Load 2020 reference data (known good)
    logger.info("\nLoading 2020 reference data...")
    df_2020 = pd.read_csv(ELECTIONS_DIR / "elections_2020.csv")
    logger.info(f"  Loaded {len(df_2020):,} counties from 2020")
    
    # Create FIPS lookup
    fips_lookup = create_fips_lookup(df_2020)
    
    # Load raw 2024 data
    logger.info("\nLoading raw 2024 data...")
    csv_files = list(MIT_DIR.glob("countypres*.csv"))
    if not csv_files:
        raise FileNotFoundError("No MIT data file found!")
    
    df = pd.read_csv(csv_files[0], low_memory=False)
    df_2024 = df[df['year'] == 2024].copy()
    logger.info(f"  Loaded {len(df_2024):,} rows from raw data")
    
    # Normalize county and state names
    df_2024['_norm_county'] = df_2024['county_name'].apply(normalize_county_name)
    df_2024['_norm_state'] = df_2024['state'].apply(normalize_state_name)
    
    # Map to correct FIPS using name lookup
    logger.info("\nMapping county names to correct FIPS codes...")
    
    # Build corrected FIPS using a list comprehension over the normalized county/state columns
    df_2024['fips_corrected'] = [
        fips_lookup.get((c, s), None)
        for c, s in zip(df_2024['_norm_county'], df_2024['_norm_state'])
    ]
    
    # Check for unmatched counties
    unmatched = df_2024['fips_corrected'].isna()
    if unmatched.any():
        logger.warning(f"  Could not match {unmatched.sum()} rows to 2020 FIPS codes")
        logger.warning("  Sample unmatched counties:")
        for _, row in df_2024[unmatched].head(10).iterrows():
            logger.warning(f"    {row['county_name']}, {row['state']}")
        
        # Drop unmatched rows
        df_2024 = df_2024[~unmatched].copy()
    
    logger.info(f"  Successfully mapped {len(df_2024):,} rows")
    
    # Compare original vs corrected FIPS
    fips_changed = df_2024['county_fips'] != df_2024['fips_corrected'].astype(float)
    logger.info(f"  FIPS codes corrected: {fips_changed.sum():,} rows ({fips_changed.sum()/len(df_2024)*100:.1f}%)")
    
    if fips_changed.any():
        logger.info("  Sample corrections:")
        for _, row in df_2024[fips_changed].head(10).iterrows():
            logger.info(f"    {row['county_name']}, {row['state']}: {row['county_fips']} → {row['fips_corrected']}")
    
    # Use corrected FIPS
    df_2024['fips'] = df_2024['fips_corrected']
    
    # Standardize party names
    party_mapping = {
        'DEMOCRAT': 'DEMOCRAT',
        'REPUBLICAN': 'REPUBLICAN',
        'LIBERTARIAN': 'LIBERTARIAN',
        'GREEN': 'GREEN',
    }
    
    df_2024['party'] = df_2024['party'].str.upper().map(party_mapping).fillna('OTHER')
    
    # Aggregate by county and party
    logger.info("\nAggregating votes by county and party...")
    
    agg_df = df_2024.groupby(['fips', 'county_name', 'state', 'party']).agg({
        'candidatevotes': 'sum',
        'totalvotes': 'first'
    }).reset_index()
    
    agg_df = agg_df.rename(columns={
        'county_name': 'county',
        'candidatevotes': 'votes',
        'totalvotes': 'total_votes'
    })
    
    logger.info(f"  Aggregated to {len(agg_df):,} rows")
    
    # Convert to wide format
    logger.info("\nConverting to wide format...")
    
    wide_df = agg_df.pivot_table(
        index=['fips', 'county', 'state', 'total_votes'],
        columns='party',
        values='votes',
        fill_value=0
    ).reset_index()
    
    wide_df.columns.name = None
    
    # Ensure major party columns exist
    for party in ['DEMOCRAT', 'REPUBLICAN']:
        if party not in wide_df.columns:
            wide_df[party] = 0
    
    # Calculate shares and margins
    wide_df['major_party_votes'] = wide_df['DEMOCRAT'] + wide_df['REPUBLICAN']
    wide_df['dem_share'] = (wide_df['DEMOCRAT'] / wide_df['major_party_votes'] * 100).round(2)
    wide_df['rep_share'] = (wide_df['REPUBLICAN'] / wide_df['major_party_votes'] * 100).round(2)
    wide_df['margin'] = (wide_df['dem_share'] - wide_df['rep_share']).round(2)
    
    wide_df['winner'] = wide_df.apply(
        lambda row: 'DEMOCRAT' if row['DEMOCRAT'] > row['REPUBLICAN'] else 'REPUBLICAN',
        axis=1
    )
    
    # Handle division by zero
    wide_df['dem_share'] = wide_df['dem_share'].fillna(0)
    wide_df['rep_share'] = wide_df['rep_share'].fillna(0)
    wide_df['margin'] = wide_df['margin'].fillna(0)
    
    # Add state abbreviation from 2020 data
    state_abbrev = df_2020[['state', 'state_po']].drop_duplicates().set_index('state')['state_po'].to_dict()
    wide_df['state_po'] = wide_df['state'].map(state_abbrev)
    
    logger.info(f"  Final output: {len(wide_df):,} counties")
    
    # Export
    output_file = ELECTIONS_DIR / "elections_2024_fixed.csv"
    logger.info(f"\nExporting to: {output_file}")
    wide_df.to_csv(output_file, index=False)
    
    # Replace the original
    original_file = ELECTIONS_DIR / "elections_2024.csv"
    backup_file = ELECTIONS_DIR / "elections_2024_broken.csv"
    
    if original_file.exists():
        logger.info(f"Backing up broken file to: {backup_file}")
        original_file.rename(backup_file)
    
    logger.info(f"Renaming fixed file to: {original_file}")
    output_file.rename(original_file)
    
    logger.info("\n" + "=" * 70)
    logger.info("[OK] 2024 FIPS codes fixed successfully!")
    logger.info("=" * 70)
    
    # Verify
    logger.info("\nVerification:")
    logger.info(f"  Counties: {len(wide_df):,}")
    logger.info(f"  Total votes: {wide_df['total_votes'].sum():,}")
    logger.info(f"  Democrat votes: {wide_df['DEMOCRAT'].sum():,}")
    logger.info(f"  Republican votes: {wide_df['REPUBLICAN'].sum():,}")
    
    return wide_df


if __name__ == "__main__":
    try:
        fix_2024_fips()
    except Exception as e:
        logger.error(f"Error fixing 2024 data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)