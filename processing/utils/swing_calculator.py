"""
Functions for calculating electoral swings and margins.
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def calculate_margin(df: pd.DataFrame, dem_col: str = 'dem_votes', 
                     rep_col: str = 'rep_votes', total_col: str = 'total_votes') -> pd.Series:
    """
    Calculate vote margin: (D - R) / Total * 100
    
    Args:
        df: DataFrame with vote counts
        dem_col: Column name for Democratic votes
        rep_col: Column name for Republican votes
        total_col: Column name for total votes
        
    Returns:
        Series with margin values
    """
    return ((df[dem_col] - df[rep_col]) / df[total_col] * 100)


def calculate_two_party_share(df: pd.DataFrame, dem_col: str = 'dem_votes',
                               rep_col: str = 'rep_votes') -> pd.Series:
    """
    Calculate Democratic two-party vote share: D / (D + R) * 100
    
    Args:
        df: DataFrame with vote counts
        dem_col: Column name for Democratic votes
        rep_col: Column name for Republican votes
        
    Returns:
        Series with two-party share values
    """
    return (df[dem_col] / (df[dem_col] + df[rep_col]) * 100)


def calculate_swing(year1_df: pd.DataFrame, year2_df: pd.DataFrame,
                    join_col: str = 'fips', method: str = 'two_party') -> pd.DataFrame:
    """
    Calculate swing between two elections.
    
    Args:
        year1_df: DataFrame for first election
        year2_df: DataFrame for second election
        join_col: Column to join on (usually 'fips')
        method: 'two_party' or 'margin'
        
    Returns:
        DataFrame with swing calculations
    """
    logger.info(f"Calculating {method} swing")
    
    # Merge dataframes
    merged = year1_df.merge(
        year2_df,
        on=join_col,
        suffixes=('_y1', '_y2'),
        how='inner'
    )
    
    if method == 'two_party':
        # Calculate two-party share for each year
        merged['share_y1'] = calculate_two_party_share(
            merged, 'dem_votes_y1', 'rep_votes_y1'
        )
        merged['share_y2'] = calculate_two_party_share(
            merged, 'dem_votes_y2', 'rep_votes_y2'
        )
        # Swing is change in two-party share
        merged['swing'] = merged['share_y2'] - merged['share_y1']
        
    elif method == 'margin':
        # Calculate margin for each year
        merged['margin_y1'] = calculate_margin(
            merged, 'dem_votes_y1', 'rep_votes_y1', 'total_votes_y1'
        )
        merged['margin_y2'] = calculate_margin(
            merged, 'dem_votes_y2', 'rep_votes_y2', 'total_votes_y2'
        )
        # Swing is change in margin
        merged['swing'] = merged['margin_y2'] - merged['margin_y1']
    
    # Determine swing direction
    merged['swing_direction'] = np.where(
        merged['swing'] > 0, 'D', 'R'
    )
    merged['swing_magnitude'] = np.abs(merged['swing'])
    
    logger.info(f"Calculated swing for {len(merged):,} counties")
    
    return merged
