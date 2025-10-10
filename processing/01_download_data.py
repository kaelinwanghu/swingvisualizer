import argparse
import logging
import sys
import zipfile
from pathlib import Path
from typing import Optional
import requests
from tqdm import tqdm

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent))
from config import (
    MIT_DIR, CENSUS_DIR, DEFAULT_CENSUS_URL,
    DEFAULT_SHAPEFILE_NAME, LOG_DIR, LOG_FORMAT
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_DIR / "01_download.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def download_file(url: str, output_path: Path, force: bool = False) -> bool:
    """
    Download a file with progress bar.
    
    Args:
        url: URL to download from
        output_path: Path to save file
        force: If True, re-download even if file exists
        
    Returns:
        True if download successful, False otherwise
    """
    # Check if file already exists
    if output_path.exists() and not force:
        logger.info(f"File already exists: {output_path.name}")
        return True
    
    try:
        logger.info(f"Downloading from {url}")
        
        # Stream download with progress bar
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download with progress bar
        with open(output_path, 'wb') as f, tqdm(
            desc=output_path.name,
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                size = f.write(chunk)
                pbar.update(size)
        
        logger.info(f"Successfully downloaded: {output_path.name}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def extract_zip(zip_path: Path, extract_dir: Path) -> bool:
    """
    Extract a ZIP file.
    
    Args:
        zip_path: Path to ZIP file
        extract_dir: Directory to extract to
        
    Returns:
        True if extraction successful
    """
    try:
        logger.info(f"Extracting {zip_path.name}")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        logger.info(f"Extracted to {extract_dir}")
        return True
        
    except zipfile.BadZipFile as e:
        logger.error(f"Failed to extract {zip_path}: {e}")
        return False


def download_mit_election_data(force: bool = False) -> bool:
    """
    Download MIT Election Lab county-level presidential returns.
    
    Note: This requires manual download from Harvard Dataverse.
    This function provides instructions and validates the download.
    
    Args:
        force: If True, prompt for re-download
        
    Returns:
        True if data is available
    """
    logger.info("=" * 70)
    logger.info("MIT ELECTION LAB DATA")
    logger.info("=" * 70)
    
    # Expected file name (may vary)
    expected_files = [
        MIT_DIR / "countypres_2000-2024.csv",
        MIT_DIR / "countypres_2000-2020.csv",
    ]
    
    # Check if any expected file exists
    existing_file = None
    for file_path in expected_files:
        if file_path.exists():
            existing_file = file_path
            break
    
    if existing_file and not force:
        logger.info(f"Election data found: {existing_file.name}")
        logger.info(f"  Size: {existing_file.stat().st_size / 1024 / 1024:.2f} MB")
        return True
    
    # Provide download instructions
    logger.warning("Election data not found!")
    logger.info("\nMANUAL DOWNLOAD REQUIRED:")
    logger.info("1. Visit: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/VOQCHQ")
    logger.info("2. Click 'Access Dataset' then 'Original Format ZIP'")
    logger.info("3. Extract the downloaded ZIP file")
    logger.info(f"4. Place 'countypres_2000-2024.csv' in: {MIT_DIR}")
    logger.info("\nAlternatively, you can use the Harvard Dataverse API:")
    logger.info("See: https://guides.dataverse.org/en/latest/api/native-api.html")
    logger.info("\n" + "=" * 70)
    
    return False


def download_census_shapefiles(force: bool = False) -> bool:
    """
    Download Census Bureau county shapefiles.
    
    Args:
        force: If True, re-download even if files exist
        
    Returns:
        True if download successful
    """
    logger.info("=" * 70)
    logger.info("CENSUS BUREAU SHAPEFILES")
    logger.info("=" * 70)
    
    # Define paths
    zip_filename = f"{DEFAULT_SHAPEFILE_NAME}.zip"
    zip_path = CENSUS_DIR / zip_filename
    extract_dir = CENSUS_DIR / DEFAULT_SHAPEFILE_NAME
    shapefile_path = extract_dir / f"{DEFAULT_SHAPEFILE_NAME}.shp"
    
    # Check if shapefile already exists
    if shapefile_path.exists() and not force:
        logger.info(f"Shapefile already exists: {shapefile_path.name}")
        return True
    
    # Download ZIP file
    if not download_file(DEFAULT_CENSUS_URL, zip_path, force):
        return False
    
    # Extract ZIP file
    if not extract_zip(zip_path, extract_dir):
        return False
    
    # Verify shapefile exists
    if shapefile_path.exists():
        logger.info("Successfully downloaded and extracted shapefile")
        logger.info(f"  Location: {shapefile_path}")
        
        zip_path.unlink()
        
        return True
    else:
        logger.error(f"Shapefile not found after extraction: {shapefile_path}")
        return False


def verify_downloads() -> dict:
    """
    Verify that all required data files are present.
    
    Returns:
        Dictionary with verification status
    """
    logger.info("=" * 70)
    logger.info("VERIFICATION")
    logger.info("=" * 70)
    
    status = {
        'election_data': False,
        'shapefiles': False,
        'all_ready': False
    }
    
    # Check for election data
    election_files = list(MIT_DIR.glob("countypres*.csv"))
    if election_files:
        status['election_data'] = True
        logger.info(f"Election data: {election_files[0].name}")
    else:
        logger.warning("Election data: NOT FOUND")
    
    # Check for shapefiles
    shapefile_dirs = list(CENSUS_DIR.glob("*county*"))
    if shapefile_dirs:
        shp_files = list(shapefile_dirs[0].glob("*.shp"))
        if shp_files:
            status['shapefiles'] = True
            logger.info(f"Shapefiles: {shp_files[0].name}")
        else:
            logger.warning("Shapefiles: DIRECTORY FOUND BUT NO .shp FILES")
    else:
        logger.warning("Shapefiles: NOT FOUND")
    
    # Overall status
    status['all_ready'] = status['election_data'] and status['shapefiles']
    
    if status['all_ready']:
        logger.info("\nAll required data is ready for processing!")
    else:
        logger.warning("\nSome data files are missing. Please download them.")
    
    logger.info("=" * 70)
    
    return status


def main():
    """Main download function."""
    parser = argparse.ArgumentParser(
        description="Download election data and shapefiles"
    )
    parser.add_argument(
        "--skip-election",
        action="store_true",
        help="Skip MIT election data download"
    )
    parser.add_argument(
        "--skip-census",
        action="store_true",
        help="Skip Census shapefile download"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download of existing files"
    )
    
    args = parser.parse_args()
    
    logger.info("Starting data download process...")
    logger.info(f"Force mode: {args.force}")
    
    # Download MIT election data (with manual instructions)
    if not args.skip_election:
        download_mit_election_data(args.force)
    
    # Download Census shapefiles (automated)
    if not args.skip_census:
        download_census_shapefiles(args.force)
    
    # Verify all downloads
    status = verify_downloads()
    
    # Exit with appropriate code
    sys.exit(0 if status['all_ready'] else 1)


if __name__ == "__main__":
    main()
