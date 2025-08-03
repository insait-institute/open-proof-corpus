import pandas as pd
from sklearn.linear_model import LogisticRegression
import numpy as np
import argparse
import ast 
import os
import yaml
import re


def compute_mle_elo(df: pd.DataFrame, C=1.0, **kwargs):
    """
    Fits an extended Bradley-Terry model using Logistic Regression.

    The model estimates player ratings and coefficients for bias terms.
    logit(P(a wins)) = (rating(a) - rating(b)) + sum(gamma_k * (bias_k_a - bias_k_b))

    Args:
        df (pd.DataFrame): DataFrame with comparison data. Must contain columns:
            'model_a': Name of the first player/model.
            'model_b': Name of the second player/model.
            'winner': Outcome ('model_a', 'model_b', or 'tie').
            It can also contain bias columns named '{bias_name}_a' and
            '{bias_name}_b' (e.g., 'length_a', 'length_b').
        C (float): Inverse of regularization strength for Logistic Regression.
                   Smaller values specify stronger regularization. Defaults to 1.0.
        **kwargs: Additional keyword arguments passed to LogisticRegression.

    Returns:
        tuple: A tuple containing:
            - pd.Series: Player ratings (log scale). Index is player name.
            - pd.Series: Bias coefficients (gamma). Index is bias name.

    Raises:
        ValueError: If required columns are missing or bias columns are inconsistent.
    """
    required_cols = ['model_a', 'model_b', 'winner']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"Input DataFrame must contain columns: {required_cols}")

    # --- 1. Identify Players and Biases ---
    players = pd.unique(df[['model_a', 'model_b']].values.ravel('K'))
    player_map = {name: i for i, name in enumerate(players)}
    num_players = len(players)

    bias_pattern = re.compile(r"^(.*)_a$")
    biases = []
    bias_cols_a = {}
    bias_cols_b = {}

    for col in df.columns:
        match = bias_pattern.match(col)
        if match:
            bias_name = match.group(1)
            if bias_name == "model":
                continue
            col_b = f"{bias_name}_b"
            if col_b in df.columns:
                biases.append(bias_name)
                bias_cols_a[bias_name] = col
                bias_cols_b[bias_name] = col_b
            else:
                raise ValueError(f"Found bias column '{col}' but missing corresponding '{col_b}'")
    num_biases = len(biases)

    # --- 2. Prepare Data for Logistic Regression ---
    # Separate wins/losses and ties
    df_no_ties = df[df['winner'] != 'tie'].copy()
    df_ties = df[df['winner'] == 'tie'].copy()

    # Duplicate tie rows: one where A wins, one where B wins
    if not df_ties.empty:
        df_ties_a_wins = df_ties.copy()
        df_ties_a_wins['winner'] = 'model_a' # Treat as A win
        df_ties_b_wins = df_ties.copy()
        df_ties_b_wins['winner'] = 'model_b' # Treat as B win (conceptually)
        processed_df = pd.concat([df_no_ties, df_ties_a_wins, df_ties_b_wins], ignore_index=True)
    else:
        processed_df = df_no_ties

    num_matches = len(processed_df)

    # --- 3. Construct Feature Matrix (X) and Target Vector (y) ---
    X = np.zeros((num_matches, num_players + num_biases))
    y = np.zeros(num_matches)

    for i, row in enumerate(processed_df.itertuples(index=False)):
        # Player columns: +1 for model_a, -1 for model_b
        idx_a = player_map[row.model_a]
        idx_b = player_map[row.model_b]
        X[i, idx_a] = 1
        X[i, idx_b] = -1

        # Bias columns: bias_a - bias_b
        for j, bias_name in enumerate(biases):
            bias_col_a = bias_cols_a[bias_name]
            bias_col_b = bias_cols_b[bias_name]
            X[i, num_players + j] = getattr(row, bias_col_a) - getattr(row, bias_col_b)

        # Target variable: 1 if model_a wins, 0 if model_b wins
        if row.winner == 'model_a':
            y[i] = 1
        # else: y[i] remains 0 (initialized as such)

    sample_weights = [1] * num_matches
    if all(y == 0):
        sample_weights.append(0)  # Add a sample weight of 0 for the first row
        # add a sample to X and y with label 1
        X = np.vstack([X, np.zeros(X.shape[1])])
        y = np.append(y, 1)
    elif all(y == 1):
        sample_weights.append(0)
        # add a sample to X and y with label 0
        X = np.vstack([X, np.zeros(X.shape[1])])
        y = np.append(y, 0)
    # --- 4. Fit Logistic Regression Model ---
    # No intercept because the difference structure accounts for the base rate.
    lr = LogisticRegression(fit_intercept=False, C=C, **kwargs)
    lr.fit(X, y, sample_weight=sample_weights)

    # --- 5. Extract Results ---
    coefficients = lr.coef_[0]

    # Player ratings (first num_players coefficients)
    # Note: Ratings are relative. They are identifiable up to an additive constant.
    # Often, one rating is fixed to 0, or the mean rating is centered at 0.
    # The raw coefficients from LR provide one valid set of relative ratings.
    player_ratings = pd.Series(coefficients[:num_players], index=players, name='Rating')

    # Bias coefficients (remaining coefficients)
    bias_coeffs = pd.Series(coefficients[num_players:], index=biases, name='Bias_Coefficient')

    return player_ratings, bias_coeffs