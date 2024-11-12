import os
import rpy2.robjects as robjects
from rpy2.robjects.conversion import localconverter
from rpy2.robjects import default_converter
import pandas as pd
from .cell_selection import detect_delimiter

def bias_correction(work_dir, obs_data_file, rec_data_file, output_file):
    """
    Perform bias correction on reconstructed data using observed data.

    Args:
        work_dir (str): Working directory where the files are located.
        obs_data_file (str): CSV file name containing the observed data.
        rec_data_file (str): CSV file name containing the reconstructed data.
        output_file (str): CSV file name where the bias-corrected results will be saved.
    
    Returns:
        None: Outputs the bias-corrected data to the specified CSV file.
    """
    # Save current working directory
    current_dir = os.getcwd()

    try:
        # Change to the specified working directory
        os.chdir(work_dir)
        
        # Detect the delimiter used in the observed data file    
        obs_delimiter = detect_delimiter(os.path.join(work_dir, obs_data_file))

        # Use localconverter to ensure proper context handling
        with localconverter(default_converter):
            # Convert Python variables to R format using robjects
            r_obs_data_file = obs_data_file
            r_rec_data_file = rec_data_file
            r_output_file = output_file
            r_obs_delimiter = obs_delimiter
            
            # R code embedded in Python using rpy2
            r_code = '''
                library(qmap)

                # Read the observed and reconstructed data from CSV files
                obsData = read.csv("{obs_data_file}", sep="{obs_delimiter}", check.names = FALSE) # Prevent column names from being changed
                reconstructedData = read.csv("{rec_data_file}", sep=",", check.names = FALSE) # Prevent column names from being changed

                # Select the second column of obsData (independent of the name)
                obs_column_name <- names(obsData)[2]
                obsData[[obs_column_name]] <- as.numeric(obsData[[obs_column_name]])

                # Filter rows that don't have observed values (only keep years with observed data)
                obsDataCal = obsData[!is.na(obsData[[obs_column_name]]),]

                # Define the columns that contain reconstructions (excluding Year)
                reconstructed_columns = names(reconstructedData)[which(names(reconstructedData) != "Year")]

                # Create a dataframe to store the bias-corrected results
                bias_corrected_data = data.frame(Year = reconstructedData$Year)

                # Iterate over each reconstruction column
                for (col in reconstructed_columns) {{

                    # Filter the valid years for each reconstruction column
                    valid_rows = !is.na(reconstructedData[[col]])
                    temp_reconstructed = reconstructedData[valid_rows, ]

                    if (any(temp_reconstructed[[col]] <= 0, na.rm = TRUE)) {{
                        # If there are values <= 0, leave the column empty
                        bias_corrected_data[[col]] = NA
                    }} else {{
                        # Check if the column has constant values
                        if (length(unique(temp_reconstructed[[col]])) == 1) {{
                            # If the column is constant, copy the same values
                            bias_corrected_data[[col]] = temp_reconstructed[[col]]
                            warning(paste("The column", col, "contains constant values. No bias correction applied."))
                        }} else {{
                            # Filter overlapping years between the observed and reconstructed data
                            overlapping_years = merge(obsDataCal, temp_reconstructed[, c("Year", col)], by="Year")
                            
                            # Log-transform the observed and reconstructed values for overlapping years
                            y = log10(overlapping_years[[obs_column_name]]) 
                            x = log10(overlapping_years[[col]]) 
                            
                            # Check if there are sufficient unique values in 'x' and 'y'
                            if (length(unique(x)) < 2 || length(unique(y)) < 2) {{
                                # If there are not enough unique values, skip bias correction
                                bias_corrected_data[[col]] = NA
                                warning(paste("Insufficient unique values in column", col, "for quantile mapping."))
                            }} else {{
                                # Take the reconstructed values for all years
                                all = log10(temp_reconstructed[[col]])
                                
                                # Fit the quantile mapping model using RQUANT
                                qm.fit <- fitQmap(obs=y, mod=x, method="RQUANT", wet.day=FALSE)
                                
                                # Apply the bias correction to all reconstructed data
                                bcAll <- doQmap(all, qm.fit, type="tricub")
                                
                                # Transform the corrected results back to the original scale
                                transfBcAll = 10^bcAll
                                
                                # Add the bias-corrected results to the corresponding column in the output dataframe
                                bias_corrected_data[[col]] <- NA
                                bias_corrected_data[valid_rows, col] <- transfBcAll
                            }}
                        }}
                    }}
                }}

                # Write the results to an output CSV file
                write.csv(bias_corrected_data, "{output_file}", row.names = FALSE)
            '''.format(obs_data_file=r_obs_data_file, rec_data_file=r_rec_data_file, output_file=r_output_file, obs_delimiter=r_obs_delimiter)

            # Execute the R code
            robjects.r(r_code)
            obs_df = pd.read_csv(os.path.join(work_dir, obs_data_file), delimiter=obs_delimiter)
            rec_df = pd.read_csv(os.path.join(work_dir, rec_data_file))
            bc_df = pd.read_csv(os.path.join(work_dir, output_file))

            obs_column_name = obs_df.columns[1]
            obs_df.rename(columns={obs_column_name: 'obsData'}, inplace=True)

            bc_df = bc_df.add_suffix('_bc')
            bc_df.rename(columns={'Year_bc': 'Year'}, inplace=True)

            merged_df = pd.merge(rec_df, obs_df[['Year', 'obsData']], on='Year', how='left')
            merged_df = pd.merge(merged_df, bc_df, on='Year', how='left')

            rec_columns = [col for col in rec_df.columns if col != 'Year']
            bc_columns = [col for col in bc_df.columns if col != 'Year']

            merged_df = merged_df[['Year', 'obsData'] + rec_columns + bc_columns]
            merged_df.to_excel(os.path.join(work_dir, output_file.replace('.csv', '.xlsx')), index=False)

    finally:
        # Restaurar el directorio de trabajo
        os.chdir(current_dir)