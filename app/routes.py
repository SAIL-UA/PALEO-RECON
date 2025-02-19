from flask import Blueprint, render_template, request, jsonify, url_for
import os
import pandas as pd
from scripts import create_output_directory, generate_output_files, dms_to_decimal, detect_delimiter, run_stepwise_regression, bias_correction
import logging

main = Blueprint('main', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define a dictionary that maps regions to their corresponding data files
DATA_FILES = {
    'Europe': {
        'coords': 'data/europe/coordPDSI_Europe.csv',
        'data': 'data/europe/dataPDSI_Europe.csv'
    },
    'North America': {
        'coords': 'data/north_america/coordPDSI_NorthAmerica.csv',
        'data': 'data/north_america/dataPDSI_NorthAmerica.csv'
    },
    # Add more regions and corresponding files as needed
}

def get_region(lat, lon):
    """Determine the region based on latitude and longitude."""
    if 26 <= lat <= 72 and -10 <= lon <= 46:
        return 'Europe'
    elif 14 <= lat <= 84 and -172 <= lon <= -51:
        return 'North America'
    # Add more conditions for other regions as needed
    else:
        return None

def validate_observed_data(file_path):
    """
    Validate the observed data file format.
    
    Args:
        file_path (str): Path to the observed data file.
    
    Returns:
        bool: True if the file format is valid, False otherwise.
        str: The name of the observed data column.
    """
    try:
        # Detect delimiter for observed data file
        observed_delimiter = detect_delimiter(file_path)
        df = pd.read_csv(file_path, delimiter=observed_delimiter)
        # Check if the DataFrame has two columns
        if len(df.columns) != 2:
            return False, None
        
        # Check if the first column is named 'Year' and contains integer values
        if not df.columns[0].lower() == 'year':
            return False, None
        
        if not pd.api.types.is_integer_dtype(df[df.columns[0]]):
            return False, None
        
        # Check if the second column contains float values
        if not pd.api.types.is_float_dtype(df[df.columns[1]]):
            return False, None
        
        return True, df.columns[1]
    except Exception as e:
        logger.error(f"Error validating observed data: {str(e)}")
        return False, None

def combine_data(observed_file, selected_file, output_file):
    """
    Combine observed data with selected PDSI cells data.
    
    Args:
        observed_file (str): Path to the observed data file.
        selected_file (str): Path to the selected PDSI cells data file.
        output_file (str): Path to the output combined data file.
    """
    try:
        # Detect delimiter for observed data file
        observed_delimiter = detect_delimiter(observed_file)
        observed_df = pd.read_csv(observed_file, delimiter=observed_delimiter)
        selected_df = pd.read_csv(selected_file)

        # Normalize column names
        observed_df.columns = ['Year', 'obsData']
        selected_df.columns = ['Year'] + list(selected_df.columns[1:])

        # Merge data on common years
        combined_df = pd.merge(observed_df, selected_df, how='inner', on='Year')
        
        if combined_df.empty:
            return False

        combined_df.to_csv(output_file, index=False)
        return True
    except Exception as e:
        logger.error(f"Error combining data: {str(e)}")
        return False

@main.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            coord_format = request.form['coord_format']
            radius_km = float(request.form['radius_km'])

            if coord_format == 'decimal':
                lat = float(request.form['lat'])
                lon = float(request.form['lon'])
                logger.debug(f"Received decimal coordinates: lat={lat}, lon={lon}")
            else:
                lat_deg = int(request.form['lat_deg'])
                lat_min = int(request.form['lat_min'])
                lat_sec = float(request.form['lat_sec'])
                lat_dir = request.form['lat_dir']
                lat = dms_to_decimal(f"{lat_dir}{lat_deg}°{lat_min}'{lat_sec}\"")

                lon_deg = int(request.form['lon_deg'])
                lon_min = int(request.form['lon_min'])
                lon_sec = float(request.form['lon_sec'])
                lon_dir = request.form['lon_dir']
                lon = dms_to_decimal(f"{lon_dir}{lon_deg}°{lon_min}'{lon_sec}\"")

            # Determine the region based on the coordinates
            region = get_region(lat, lon)
            if region is None:
                return jsonify({'error': 'Coordinates are out of the supported regions. Please enter a valid coordinate for Europe or North America.'}), 400

            detect_basin = request.form.get('detect_basin') == 'on'

            window_size = int(request.form['window_size'])

            file = request.files['file']
            if file:
                output_directory = create_output_directory(lat, lon, radius_km)
                observed_data_path = os.path.join(output_directory, 'observed_data.csv')
                file.save(observed_data_path)

                # Validate observed data format
                is_valid, obs_column = validate_observed_data(observed_data_path)
                if not is_valid:
                    return jsonify({'error': 'Invalid observed data format. Ensure the file has two columns: Year and observed data.'}), 400

                # Get the correct data files for the determined region
                coord_file = DATA_FILES[region]['coords']
                coord_df = pd.read_csv(coord_file)
                if len(coord_df) == 0:
                    return jsonify({'error': 'No PDSI Cells found for the selected search radius.'}), 400
                data_file = DATA_FILES[region]['data']

                generate_output_files(lat, lon, radius_km, coord_file, data_file, detect_basin)

                # Combine observed data with selected PDSI data
                selected_data_path = os.path.join(output_directory, 'selected_data.csv')
                combined_data_path = os.path.join(output_directory, 'modeling_data.csv')
                if not combine_data(observed_data_path, selected_data_path, combined_data_path):
                    return jsonify({'error': 'No common years found between observed data and PDSI data.'}), 400

                # Run stepwise linear regression
                run_stepwise_regression(combined_data_path, selected_data_path, window_size, output_directory)

                map_url = url_for('static', filename=f'results/{os.path.basename(output_directory)}/map.png')
                coords_url = url_for('static', filename=f'results/{os.path.basename(output_directory)}/selected_coords.csv')
                data_url = url_for('static', filename=f'results/{os.path.basename(output_directory)}/selected_data.csv')
                results_zip_url = url_for('static', filename=f'results/{os.path.basename(output_directory)}/results.zip')
                return jsonify({'map_url': map_url, 'coords_url': coords_url, 'data_url': data_url, 'results_zip_url': results_zip_url})

        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            return jsonify({'error': str(e)}), 500

    return render_template('index.html')
