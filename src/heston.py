import numpy as np
import pandas as pd
from scipy.stats import norm

def get_gbm_percentiles(S0, mu, sd, days_left):
    """
    S0: Current Price
    mu: Annualized Drift (e.g. 0.05 for 5%)
    sigma: Annualized Volatility (e.g. 0.20 for 20%)
    days_left: Trading days remaining in the month
    """
    dt = 1/252  # Daily time step

    T_years = dt * days_left
    t = np.linspace(0, T_years, days_left + 1)
    tail_prob = (1 - 0.8) / 2
    z_score = norm.ppf(1 - tail_prob) # e.g., 1.28 for 80%
    
    # 3. The Geometric Brownian Motion Formula
    # Drift Term: (mu - 0.5 * sigma^2) * t
    drift_term = (mu - 0.5 * sd**2) * t
    
    # Volatility Term: sigma * sqrt(t)
    vol_term = sd * np.sqrt(t)
    
    # 4. Calculate Bounds
    # Median: exp(drift) -> The 50th percentile (z=0)
    median_path = S0 * np.exp(drift_term)
    
    # Upper/Lower: exp(drift +/- z * vol)
    upper_band = S0 * np.exp(drift_term + z_score * vol_term)
    lower_band = S0 * np.exp(drift_term - z_score * vol_term)
    
    # Exclude t=0 from return if you only want FUTURE days
    return median_path, upper_band, lower_band
