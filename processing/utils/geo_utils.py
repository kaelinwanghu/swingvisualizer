"""
Geographic utility functions for processing shapefiles and geometries.
"""

import geopandas as gpd
from shapely.geometry import shape, mapping
from shapely import simplify as shapely_simplify
import json
import logging

logger = logging.getLogger(__name__)


def simplify_geometry(gdf: gpd.GeoDataFrame, tolerance: float = 0.001) -> gpd.GeoDataFrame:
    """
    Simplify geometries to reduce file size.
    
    Args:
        gdf: GeoDataFrame to simplify
        tolerance: Simplification tolerance (in CRS units)
        
    Returns:
        GeoDataFrame with simplified geometries
    """
    logger.info(f"Simplifying geometries with tolerance {tolerance}")
    
    original_size = gdf.memory_usage(deep=True).sum() / 1024 / 1024
    
    gdf['geometry'] = gdf['geometry'].simplify(tolerance, preserve_topology=True)
    
    new_size = gdf.memory_usage(deep=True).sum() / 1024 / 1024
    reduction = (1 - new_size / original_size) * 100
    
    logger.info(f"Size reduced by {reduction:.1f}% ({original_size:.2f} MB to {new_size:.2f} MB)")
    
    return gdf


def convert_to_geojson(gdf: gpd.GeoDataFrame, output_path, precision: int = 6):
    """
    Convert GeoDataFrame to GeoJSON with coordinate precision control.
    
    Args:
        gdf: GeoDataFrame to convert
        output_path: Path to save GeoJSON
        precision: Decimal places for coordinates
    """
    logger.info(f"Converting to GeoJSON: {output_path}")
    
    geodetic_crs = 'EPSG:4326'
    # Ensure CRS is WGS84 for GeoJSON
    if gdf.crs and gdf.crs.to_string() != geodetic_crs:
        logger.info(f"Reprojecting from {gdf.crs} to {geodetic_crs}")
        gdf = gdf.to_crs(geodetic_crs)

    # Save with coordinate precision
    gdf.to_file(output_path, driver='GeoJSON', precision=precision)
    
    file_size = output_path.stat().st_size / 1024 / 1024
    logger.info(f"Saved GeoJSON: {file_size:.2f} MB")


def reproject_gdf(gdf: gpd.GeoDataFrame, target_crs: str) -> gpd.GeoDataFrame:
    """
    Reproject GeoDataFrame to target CRS.
    
    Args:
        gdf: GeoDataFrame to reproject
        target_crs: Target CRS (e.g., 'EPSG:4326')
        
    Returns:
        Reprojected GeoDataFrame
        
    Raises:
        ValueError: If GeoDataFrame has no CRS defined
    """
    # Handle None CRS
    if gdf.crs is None:
        raise ValueError(
            "GeoDataFrame has no CRS defined. Cannot reproject. "
            "Set CRS first using: gdf.set_crs('EPSG:XXXX', inplace=True)"
        )
    
    # Check if reprojection is needed
    current_crs = gdf.crs.to_string()
    if current_crs != target_crs:
        logger.info(f"Reprojecting from {current_crs} to {target_crs}")
        return gdf.to_crs(target_crs)
    
    logger.info(f"GeoDataFrame already in {target_crs}, no reprojection needed")
    return gdf


def set_crs_if_missing(gdf: gpd.GeoDataFrame, default_crs: str = 'EPSG:4326') -> gpd.GeoDataFrame:
    """
    Set CRS if not already defined.
    
    Args:
        gdf: GeoDataFrame to check
        default_crs: Default CRS to set if missing
        
    Returns:
        GeoDataFrame with CRS defined
    """
    if gdf.crs is None:
        logger.warning(f"No CRS defined. Setting to {default_crs}")
        gdf.set_crs(default_crs, inplace=True)
    return gdf


def validate_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Validate and fix invalid geometries.
    
    Args:
        gdf: GeoDataFrame to validate
        
    Returns:
        GeoDataFrame with valid geometries
    """
    logger.info("Validating geometries...")
    
    # Check for invalid geometries
    invalid = ~gdf.is_valid
    invalid_count = invalid.sum()
    
    if invalid_count > 0:
        logger.warning(f"Found {invalid_count} invalid geometries. Attempting to fix...")
        
        # Fix invalid geometries using buffer(0) trick
        gdf.loc[invalid, 'geometry'] = gdf.loc[invalid, 'geometry'].buffer(0)
        
        # Check again
        still_invalid = ~gdf.is_valid
        still_invalid_count = still_invalid.sum()
        
        if still_invalid_count > 0:
            logger.warning(f"Could not fix {still_invalid_count} geometries. These will be dropped.")
            gdf = gdf[gdf.is_valid]
        else:
            logger.info("All invalid geometries fixed successfully")
    else:
        logger.info("All geometries are valid")
    
    return gdf


def get_bounds(gdf: gpd.GeoDataFrame) -> dict:
    """
    Get bounding box of GeoDataFrame.
    
    Args:
        gdf: GeoDataFrame
        
    Returns:
        Dictionary with minx, miny, maxx, maxy
    """
    bounds = gdf.total_bounds
    return {
        'minx': float(bounds[0]),
        'miny': float(bounds[1]),
        'maxx': float(bounds[2]),
        'maxy': float(bounds[3])
    }