import pandas as pd
import geopandas as gpd
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


def load_election_data(
    file_path: Path,
    columns: Optional[List[str]] = None,
    filter_year: Optional[int] = None
) -> pd.DataFrame:
    """
    Load election data from CSV file.
    
    Args:
        file_path: Path to CSV file
        columns: Optional list of columns to load
        filter_year: Optional year to filter data
        
    Returns:
        DataFrame with election data
    """
    logger.info(f"Loading election data from {file_path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Load with specific columns if provided
    df = pd.read_csv(file_path, usecols=columns, low_memory=False)
    
    logger.info(f"Loaded {len(df):,} rows")
    
    # Filter by year if specified
    if filter_year and 'year' in df.columns:
        df = df[df['year'] == filter_year]
        logger.info(f"Filtered to year {filter_year}: {len(df):,} rows")
    
    return df


def load_shapefile(
    shapefile_path: Path,
    columns: Optional[List[str]] = None
) -> gpd.GeoDataFrame:
    """
    Load county shapefile.
    
    Args:
        shapefile_path: Path to .shp file
        columns: Optional list of columns to load
        
    Returns:
        GeoDataFrame with county geometries
    """
    logger.info(f"Loading shapefile from {shapefile_path}")
    
    if not shapefile_path.exists():
        raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")
    
    # Load with pyogrio engine (faster)
    gdf = gpd.read_file(shapefile_path, engine="pyogrio")
    
    # Select specific columns if provided
    if columns:
        available_cols = [col for col in columns if col in gdf.columns]
        gdf = gdf[available_cols + ['geometry']]
    
    logger.info(f"Loaded {len(gdf):,} counties")
    logger.info(f"CRS: {gdf.crs}")
    
    return gdf


def validate_fips_codes(df: pd.DataFrame, fips_column: str = 'fips') -> pd.DataFrame:
    """
    Validate and standardize FIPS codes.
    
    Args:
        df: DataFrame with FIPS codes
        fips_column: Name of FIPS column
        
    Returns:
        DataFrame with standardized FIPS codes
    """
    # Ensure FIPS is string with leading zeros (5 digits)
    df[fips_column] = df[fips_column].astype(str).str.zfill(5)
    
    # Remove invalid FIPS (non-numeric or wrong length)
    valid_fips = df[fips_column].str.match(r'^\d{5}$')
    invalid_count = (~valid_fips).sum()
    
    if invalid_count > 0:
        logger.warning(f"Removing {invalid_count} rows with invalid FIPS codes")
        df = df[valid_fips]
    
    return df


def check_data_quality(df: pd.DataFrame, required_columns: List[str]) -> dict:
    """
    Perform basic data quality checks.
    
    Args:
        df: DataFrame to check
        required_columns: List of required column names
        
    Returns:
        Dictionary with quality metrics
    """
    metrics = {
        'total_rows': len(df),
        'missing_columns': [],
        'null_counts': {},
        'duplicate_rows': 0
    }
    
    # Check for missing columns
    for col in required_columns:
        if col not in df.columns:
            metrics['missing_columns'].append(col)
    
    # Count nulls in each column
    for col in df.columns:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            metrics['null_counts'][col] = null_count
    
    # Check for duplicates
    metrics['duplicate_rows'] = df.duplicated().sum()
    
    return metrics