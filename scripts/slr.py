import pandas as pd
import numpy as np
from scipy.stats import pearsonr
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson
import os
import zipfile as zf
from .bias_correction import bias_correction

def correlated_vectors(df, p_value_threshold=0.01):
    """
    Identify columns that have a positive correlation with the target variable (obsData)
    and have a p-value below the specified threshold.
    
    Args:
        df (pd.DataFrame): DataFrame containing the data.
        p_value_threshold (float): p-value threshold for significance.
    
    Returns:
        pd.DataFrame: DataFrame containing only the significant columns.
    """
    significant_vectors = ["Year", "obsData"]
    
    # Calculate the correlation between the observed data and each column
    for column in df.columns[2:]:
        correlation, p_value = pearsonr(df["obsData"], df[column])
        # Select vector if the correlation is positive and the p-value is below the threshold
        if correlation > 0 and p_value <= p_value_threshold:
            significant_vectors.append(column)
    
    return df[significant_vectors]

def stability_filter(df):
    """
    Filter columns based on their stability over a rolling window.
    
    Args:
        df (pd.DataFrame): DataFrame containing the data.
    
    Returns:
        pd.DataFrame: DataFrame with unstable columns removed.
    """
    # Determine the window size based on the length of the DataFrame
    window_size = len(df) // 3
    correlations_list = []
    
    # Calculate the correlation between the observed data and each column over a rolling window
    for start in range(0, len(df) - window_size + 1):
        end = start + window_size
        window_data = df.iloc[start:end]
        correlations = {}
        for column in df.columns[2:]:
            correlation, _ = pearsonr(window_data["obsData"], window_data[column])
            correlations[column] = correlation
        correlations_list.append(correlations)
    
    df_correlations = pd.DataFrame(correlations_list)
    
    # Remove columns with negative correlations
    for column in df_correlations.columns:
        if (df_correlations[column] < 0).any():
            df = df.drop(column, axis=1)
    
    return df

def create_df_list(df, window_size=50):
    """
    Create a list of DataFrames using a sliding window approach.
    
    Args:
        df (pd.DataFrame): DataFrame containing the data.
        window_size (int): Size of the sliding window.
    
    Returns:
        list: List of DataFrames.
    """
    df_list = []
    
    # Create a DataFrame for each window
    for start in range(0, len(df) - window_size + 1):
        end = start + window_size
        window_data = df.iloc[start:end].copy()
        corr_dfs = correlated_vectors(window_data)
        stbl_dfs = stability_filter(corr_dfs)
        df_list.append(stbl_dfs)
    
    return df_list

def export_df_list(df_list, file_name, single_sheet=False, single_sheet_name='Sheet1'):
    """
    Export a list of DataFrames to an Excel file.
    
    Args:
        df_list (list): List of DataFrames to export.
        file_name (str): Name of the output Excel file.
        single_sheet (bool): If True, export all DataFrames to a single sheet.
        single_sheet_name (str): Name of the single sheet if single_sheet is True.
    """
    with pd.ExcelWriter(file_name) as writer:
        if single_sheet:
            combined_df = pd.concat(df_list, ignore_index=True)
            combined_df.to_excel(writer, sheet_name=single_sheet_name, index=False)
        else:
            for df in df_list:
                if 'Year' in df.columns:
                    # Get the start and end years for the sheet name
                    non_empty_obs = df[df['obsData'].notna()]
                    if not non_empty_obs.empty:
                        start_year = non_empty_obs['Year'].iloc[0]
                        end_year = non_empty_obs['Year'].iloc[-1]
                        sheet_name = f"{start_year}-{end_year}"
                    else:
                        start_year = df['Year'].iloc[0]
                        end_year = df['Year'].iloc[-1]
                        sheet_name = f"{start_year}-{end_year}"
                elif 'Years' in df.columns:
                    # If the DataFrame has a 'Years' column, use it for the sheet name
                    sheet_name = df['Years'].iloc[0]
                else:
                    # If no column is found, use a default sheet name
                    sheet_name = "Stats"
                df.to_excel(writer, sheet_name=sheet_name, index=False)

def sign_test_comparison(observed, predicted):
    """
    Perform a sign test comparison between observed and predicted values.
    
    Args:
        observed (list): List of observed values.
        predicted (list): List of predicted values.
    
    Returns:
        str: Result of the sign test as a ratio.
    """
    differences = [o - p for o, p in zip(observed, predicted)]
    positive_diffs = sum(1 for d in differences if d > 0)
    negative_diffs = sum(1 for d in differences if d < 0)
    
    return "{}/{}".format(positive_diffs, negative_diffs)

def stepwise_linear_regression(df, id_var, target_var, alpha_enter, alpha_remove, predictor_df):
    """
    Perform stepwise linear regression with a recursive sign constraint.
    If a predictor yields a negative coefficient, it is permanently removed 
    from the candidate pool, and the stepwise process restarts.
    """
    
    def run_stepwise(X, y, a_enter, a_remove):
        selected_predictors = []
        remaining_predictors = list(X.columns)
        
        while True:
            changed = False
            # Forward step: add the best predictor based on p-value
            best_pval = 1
            best_predictor = None
            for predictor in remaining_predictors:
                # Add constant to the subset of selected + the new candidate
                model = sm.OLS(y, sm.add_constant(X[selected_predictors + [predictor]])).fit()
                pval = model.pvalues[predictor]
                if pval < a_enter and pval < best_pval:
                    best_pval = pval
                    best_predictor = predictor
            
            if best_predictor:
                selected_predictors.append(best_predictor)
                remaining_predictors.remove(best_predictor)
                changed = True
            
            # Backward step: remove the worst predictor based on p-value
            if not selected_predictors:
                break
                
            model = sm.OLS(y, sm.add_constant(X[selected_predictors])).fit()
            pvalues = model.pvalues.drop('const')
            worst_pval = pvalues.max()
            if worst_pval > a_remove:
                remove_predictor = pvalues.idxmax()
                selected_predictors.remove(remove_predictor)
                remaining_predictors.append(remove_predictor)
                changed = True
            
            if not changed:
                break
        
        # Return the final model and the list of names
        final_model = sm.OLS(y, sm.add_constant(X[selected_predictors])).fit()
        return final_model, selected_predictors

    # --- New Recursive Logic Starts Here ---
    
    # 1. Define the initial pool of all possible candidates
    current_candidates = list(df.drop(columns=[id_var, target_var]).columns)
    y = df[target_var]
    model = None
    selected_predictors = []

    while True:
        # 2. Run stepwise using only the current allowed candidates
        X_current = df[current_candidates]
        model, selected_predictors = run_stepwise(X_current, y, alpha_enter, alpha_remove)
        
        # If no predictors were selected, we stop to avoid infinite loops
        if not selected_predictors:
            break
            
        # 3. Check for negative coefficients (ignoring the intercept at index 0)
        # model.params contains [const, pred1, pred2...]
        negative_predictors = [p for p, coef in zip(selected_predictors, model.params[1:]) if coef < 0]
        
        if negative_predictors:
            # 4. EXCLUSION STEP: Remove negative predictors from the TOTAL candidate pool
            for p in negative_predictors:
                if p in current_candidates:
                    current_candidates.remove(p)
            # The loop continues and restarts the stepwise process with fewer candidates
        else:
            # All selected predictors have positive coefficients: SUCCESS
            break

    # --- End of Recursive Logic ---

    # Get the final regression equation for reporting
    coefficients = model.params
    if selected_predictors:
        equation_terms = ["{:.4f} ({})".format(coefficients[col], col) for col in selected_predictors]
        equation = "predicted = {:.4f} + {}".format(coefficients['const'], ' + '.join(equation_terms))
    else:
        equation = "No significant predictors found"

    # Statistics Calculation (R2, R2_pred, etc.)
    r2 = model.rsquared

    def calculate_r2_pred(df_copy, predictors, target):
        if not predictors: return 0
        preds = []
        actuals = []
        for i in df_copy.index:
            df_train = df_copy.drop(index=i)
            df_test = df_copy.loc[[i]]
            m_cv = sm.OLS(df_train[target], sm.add_constant(df_train[predictors])).fit()
            const_test = sm.add_constant(df_test[predictors], has_constant='add')
            # Align columns in case of missing variables in test slice
            const_test = const_test.reindex(columns=m_cv.params.index, fill_value=1)
            prediction = m_cv.predict(const_test)
            preds.append(prediction.iloc[0])
            actuals.append(df_test[target].iloc[0])
        
        ss_res = sum((np.array(actuals) - np.array(preds)) ** 2)
        ss_tot = sum((np.array(actuals) - np.mean(actuals)) ** 2)
        return 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    r2_pred = calculate_r2_pred(df, selected_predictors, target_var)

    # VIF and Durbin-Watson
    if len(selected_predictors) <= 1:
        vif = [1] if selected_predictors else [0]
    else:
        try:
            vif = [variance_inflation_factor(df[selected_predictors].values, i) for i in range(len(selected_predictors))]
        except:
            vif = ["Collinearity error"]

    dw = durbin_watson(model.resid)
    sign_test_result = sign_test_comparison(y, model.predict(sm.add_constant(df[selected_predictors])))

    # Prepare outputs
    start_year, end_year = df['Year'].iloc[0], df['Year'].iloc[-1]
    stats_df = pd.DataFrame({
        'Years': [f"{start_year}-{end_year}"],
        'R^2': [r2],
        'R^2 Predicted': [r2_pred],
        'VIF': [vif],
        'Durbin-Watson': [dw],
        'SignTest': [sign_test_result],
        'Equation': [equation]
    })

    df_output = df[[id_var, target_var] + selected_predictors].copy()
    df_output['predictedData'] = model.predict(sm.add_constant(df[selected_predictors]))

    reconstruction_df = predictor_df[['YEAR'] + selected_predictors].copy().rename(columns={'YEAR': 'Year'})
    reconstruction_df['reconstructedData'] = model.predict(sm.add_constant(predictor_df[selected_predictors]))
    reconstruction_df = pd.merge(reconstruction_df, df[['Year', target_var]], on='Year', how='left')

    return stats_df, df_output, reconstruction_df


def run_stepwise_regression(input_file, predictor_file, window_size, output_directory):
    """
    Run the complete stepwise linear regression process and save the results.
    
    Args:
        input_file (str): Path to the input data file.
        predictor_file (str): Path to the predictor data file.
        window_size (int): Size of the sliding window.
        output_directory (str): Directory to save the results.
    """
    df = pd.read_csv(input_file)
    predictor_df = pd.read_csv(predictor_file)
    df_list = create_df_list(df, window_size)
    df_list.insert(0, stability_filter(correlated_vectors(df)))
    export_df_list(df_list, os.path.join(output_directory, 'slr_preprocessed_data.xlsx'))

    stats_list = []
    predictions_list = []
    reconstructions_list = []
    slr_reconstructions_df = pd.DataFrame({'Year': predictor_df['YEAR']})
    reconstruction_columns = {}
    for df_window in df_list:
        stats_df, prediction_df, reconstruction_df = stepwise_linear_regression(df_window, 'Year', 'obsData', 0.05, 0.1, predictor_df)
        stats_list.append(stats_df)
        predictions_list.append(prediction_df)
        reconstructions_list.append(reconstruction_df)

        start_year = df_window['Year'].iloc[0]
        end_year = df_window['Year'].iloc[-1]
        reconstruction_window = f"{start_year}-{end_year}"
        reconstruction_series = reconstruction_df.drop_duplicates('Year').set_index('Year')['reconstructedData']
        reconstruction_columns[reconstruction_window] = slr_reconstructions_df['Year'].map(reconstruction_series)

    if reconstruction_columns:
        slr_reconstructions_df = pd.concat(
            [slr_reconstructions_df, pd.DataFrame(reconstruction_columns)],
            axis=1
        ).copy()

    export_df_list(stats_list, os.path.join(output_directory, 'slr_stats.xlsx'), single_sheet=True, single_sheet_name='stats')
    export_df_list(predictions_list, os.path.join(output_directory, 'slr_predictions.xlsx'))
    export_df_list(reconstructions_list, os.path.join(output_directory, 'slr_reconstructions.xlsx'))
    slr_reconstructions_df.to_csv(os.path.join(output_directory, 'slr_reconstructions_summary.csv'), index=False)
    # Perform bias correction on the reconstructed data
    bias_correction(os.path.abspath(output_directory), 'observed_data.csv', 'slr_reconstructions_summary.csv', 'slr_bias_correction.csv')

    # Create a zip file of the results
    with zf.ZipFile(os.path.join(output_directory, 'results.zip'), 'w') as zipObj:
        zipObj.write(os.path.join(output_directory, 'slr_preprocessed_data.xlsx'), arcname='slr_preprocessed_data.xlsx')
        zipObj.write(os.path.join(output_directory, 'slr_stats.xlsx'), arcname='slr_stats.xlsx')
        zipObj.write(os.path.join(output_directory, 'slr_predictions.xlsx'), arcname='slr_predictions.xlsx')
        zipObj.write(os.path.join(output_directory, 'slr_reconstructions.xlsx'), arcname='slr_reconstructions.xlsx')
        zipObj.write(os.path.join(output_directory, 'slr_bias_correction.xlsx'), arcname='slr_bias_correction.xlsx')
