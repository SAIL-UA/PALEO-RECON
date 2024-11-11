import matplotlib
matplotlib.use('Agg')  # Required to save figures when using SSH
import matplotlib.ticker as mticker
import matplotlib.patheffects as PathEffects
import os
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
import geopandas as gpd
from shapely.geometry import Point, shape
from shapely.geometry.polygon import Polygon
from cartopy.geodesic import Geodesic
from cartopy.mpl.gridliner import LongitudeFormatter, LatitudeFormatter

def dms_to_decimal(coord_str):
    """
    Convert a coordinate in DMS (Degrees, Minutes, Seconds) format to decimal format.
    
    Args:
        coord_str (str): A string representing the coordinate in DMS format, e.g., "N35°58'53.45" or "W83°09'40.35".
    
    Returns:
        float: The coordinate in decimal format.
    """
    direction = coord_str[0]
    if direction not in ('N', 'S', 'E', 'W'):
        raise ValueError("Invalid format. The string should start with either N, S, E, or W.")
    
    degrees, minutes, seconds = map(float, (coord_str[1:].split('°')[0], 
                                           coord_str.split('°')[1].split('\'')[0], 
                                           coord_str.split('\'')[1].split('"')[0]))
    
    # Calculate the decimal coordinate
    decimal_coord = degrees + minutes / 60 + seconds / 3600
    
    # If direction is South or West, make the coordinate negative
    if direction in ('S', 'W'):
        decimal_coord = -decimal_coord

    return decimal_coord

def detect_delimiter(file_path, num_lines=5):
    """
    Detect the delimiter of a CSV file by analyzing the first few lines.

    Args:
        file_path (str): Path to the CSV file.
        num_lines (int): Number of lines to analyze.

    Returns:
        str: Detected delimiter (',' or ';').
    """
    delimiters = [',', ';']
    delimiter_counts = {delimiter: 0 for delimiter in delimiters}
    
    with open(file_path, 'r') as file:
        for _ in range(num_lines):
            line = file.readline()
            for delimiter in delimiters:
                delimiter_counts[delimiter] += line.count(delimiter)

    # Return the delimiter with the highest count
    return max(delimiter_counts, key=delimiter_counts.get)

def create_output_directory(lat, lon, radius_km):
    """
    Create a directory for storing the results based on latitude, longitude, and radius.
    
    Args:
        lat (float): Latitude of the center point.
        lon (float): Longitude of the center point.
        radius_km (float): Search radius in kilometers.
    
    Returns:
        str: Path to the created directory.
    """
    directory_name = f"{lat:.2f}_{lon:.2f}_{int(radius_km)}Km"
    directory_path = os.path.join('app', 'static', 'results', directory_name)  # Adjusting to create results directory in the parent directory
    
    # if os.path.exists(directory_path):
    #    shutil.rmtree(directory_path)  # Delete the existing directory and its contents
    
    os.makedirs(directory_path, exist_ok=True)
    return directory_path

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth's surface.
    
    Args:
        lat1, lon1, lat2, lon2 (float): Latitude and longitude of two points in decimal degrees.
    
    Returns:
        float: Distance between the two points in kilometers.
    """
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    r = 6371.0
    return r * c

def select_grid_points(lat, lon, radius_km, coord_df):
    """
    Select PDSI cells within a given radius from a specified coordinate.

    Args:
        lat (float): Latitude of the center point.
        lon (float): Longitude of the center point.
        radius_km (float): Search radius in kilometers.
        coord_df (pd.DataFrame): DataFrame containing PDSI cell coordinates and IDs.

    Returns:
        list: List of IDs of the PDSI cells within the search radius.
    """
    mask = coord_df.apply(lambda row: haversine(lat, lon, row['LATITUDE'], row['LONGITUDE']) <= radius_km, axis=1)
    return coord_df[mask]['ID'].tolist()

def generate_output_files(lat, lon, radius_km, coord_file, data_file, detect_basin):
    """
    Generate output files containing selected PDSI cells and their data, and a map of the selected area.

    Args:
        lat (float): Latitude of the center point.
        lon (float): Longitude of the center point.
        radius_km (float): Search radius in kilometers.
        coord_file (str): Path to the CSV file containing PDSI cell coordinates.
        data_file (str): Path to the CSV file containing PDSI cell data.
    """
    coord_df = pd.read_csv(coord_file)
    data_df = pd.read_csv(data_file)
    
    # Filter coordinates within the search radius
    selected_ids = select_grid_points(lat, lon, radius_km, coord_df)

    # Convert all column names to integers except the 'YEAR' column
    data_df.columns = ['YEAR'] + [int(col) for col in data_df.columns if col != 'YEAR']

    selected_coords = coord_df[coord_df['ID'].isin(selected_ids)]
    cols_to_keep = ['YEAR'] + [col for col in data_df.columns if col in selected_ids]
    selected_data = data_df[cols_to_keep]

    # Remove rows where all PDSI cells are NA
    selected_data = selected_data.dropna(how='all', subset=selected_data.columns[1:])

    # Sort the columns in the selected data and save the files
    cols = ['YEAR'] + sorted([col for col in selected_data.columns if col != 'YEAR'])
    selected_data = selected_data[cols]

    # Save the selected coordinates and data to CSV files
    output_directory = create_output_directory(lat, lon, radius_km)
    output_coord_file = os.path.join(output_directory, 'selected_coords.csv')
    output_data_file = os.path.join(output_directory, 'selected_data.csv')
    map_file = os.path.join(output_directory, 'map.png')
    
    selected_coords.to_csv(output_coord_file, index=False)
    selected_data.to_csv(output_data_file, index=False)

    mrb_geojson = os.path.join('data', 'mrb_basins.json')
        
    #plot_map(lat, lon, radius_km, coord_df, selected_ids, map_file, projection='PlateCarree', centered=True, outside_points=False)
    plot_map(lat, lon, radius_km, coord_df, selected_ids, map_file, mrb_geojson, detect_basin=detect_basin, projection='PlateCarree', centered=True, outside_points=False)

def plot_map(lat, lon, radius_km, coord_df, selected_ids, map_file, mrb_geojson, detect_basin=False, projection='PlateCarree', centered=True, outside_points=False, visibility_threshold=1.0):
    """
    Plot a map showing the selected PDSI cells within the search radius, and highlight major river basin (MRB) if the coordinates fall within one.

    Args:
        lat (float): Latitude of the center point.
        lon (float): Longitude of the center point.
        radius_km (float): Search radius in kilometers.
        coord_df (pd.DataFrame): DataFrame containing all PDSI cell coordinates.
        selected_ids (list): List of the selected PDSI cells.
        map_file (str): Path to the output map file.
        mrb_geojson (str): Path to the GeoJSON file with MRB polygons.
        projection (str): Type of map projection to use.
        centered (bool): Whether to center the map on the selected point or in the centroid of North America.
        outside_points (bool): Whether to plot the points outside the selected area.
        visibility_threshold (float): Minimum visible area required to display a country's name.
    """
    
    # Load MRB polygons from GeoJSON
    mrb_gdf = gpd.read_file(mrb_geojson)
    
    # Create point from lat, lon
    point = Point(lon, lat)
    
    if detect_basin:
        # Initialize variables for the MRB name and polygon
        mrb_name = None
        mrb_polygon = None
        
        # Find if the point is within any MRB polygon
        for _, basin in mrb_gdf.iterrows():
            if basin.geometry.contains(point):
                mrb_name = basin['RIVERBASIN'].lower().title()  # Direct access to the RIVERBASIN field
                mrb_polygon = basin.geometry
                break  # Stop at the first match


    # Filter the selected and outside points
    inside_df = coord_df[coord_df['ID'].isin(selected_ids)]
    outside_df = coord_df[~coord_df['ID'].isin(selected_ids)]

    # Create the map
    fig, ax = plt.subplots(figsize=(15, 10), subplot_kw={'projection': getattr(ccrs, projection)()})

    # Add features to the map
    ax.add_feature(cfeature.BORDERS, linewidth=1.5)
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.RIVERS, linewidth=2.3)
    ax.add_feature(cfeature.LAKES)
    ax.add_feature(cfeature.STATES, linestyle=':', linewidth=0.5)
    ax.add_feature(cfeature.OCEAN, color='lightblue')

    # Set map limits
    if centered:
        margin_factor = 1.3  # Increase this factor to ensure more margin
        delta_lat = (margin_factor * radius_km) / 111  # Approx. 1 degree latitude ~ 111 km
        delta_lon = (margin_factor * radius_km) / (111 * abs(np.cos(np.radians(lat))))  # Adjust for longitude
        ax.set_extent([lon - delta_lon, lon + delta_lon, lat - delta_lat, lat + delta_lat], getattr(ccrs, projection)())
    else:
        ax.set_extent([-170, -50, 10, 85], getattr(ccrs, projection)())

    if detect_basin:
        facecolor = 'red'
        edgecolor = 'darkred'
        alpha = 0.2

        # Plot MRB polygon if found
        if mrb_polygon is not None:
            mrb_patch = gpd.GeoSeries(mrb_polygon)
            mrb_patch.plot(ax=ax, facecolor=facecolor, edgecolor=edgecolor, alpha=alpha, transform=getattr(ccrs, projection)(), zorder=11)
            mrb_patch = Patch(facecolor=facecolor, edgecolor=edgecolor, alpha=alpha, label=f"{mrb_name} River Basin")
        else:
            mrb_patch = None

    # Load and add country names within the visible area
    countries_shp = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
    for country in shpreader.Reader(countries_shp).records():
        country_name = country.attributes['NAME']
        country_geom = country.geometry

        # Check if any part of the country's geometry intersects with the visible map area
        x0, x1, y0, y1 = ax.get_extent()
        visible_area = Polygon([[x0, y0], [x0, y1], [x1, y1], [x1, y0]])  # Create a polygon of the visible area

        # Find the intersection of the country's geometry and the visible area
        intersection = country_geom.intersection(visible_area)
        
        # Calculate the absolute visible area
        if not intersection.is_empty:
            visible_area_size = intersection.area  # Absolute area of the intersection
            
            # If the visible area size is below the threshold, skip adding the country name
            if visible_area_size < visibility_threshold:
                continue
            
            # Use a representative point within the intersection area for label placement
            label_point = intersection.representative_point()
            ax.text(label_point.x, label_point.y, country_name,
                    transform=ccrs.PlateCarree(),
                    fontsize=10,  # Increased font size for better visibility
                    fontweight='bold',
                    color='darkblue',  # Changed to a darker color for contrast
                    ha='center', va='center',
                    path_effects=[PathEffects.withStroke(linewidth=3, foreground='white')],  # More pronounced outline
                    zorder=12)

    # Plot outside points if needed
    if outside_points:
        ax.scatter(outside_df['LONGITUDE'], outside_df['LATITUDE'], color='gray', s=30, edgecolor='k', zorder=9, transform=getattr(ccrs, projection)(), label="Outside Radius")

    # Plot selected points and the center point
    # ax.scatter(inside_df['LONGITUDE'], inside_df['LATITUDE'], color='red', s=40, edgecolor='k', zorder=10, transform=getattr(ccrs, projection)(), label="Inside Radius")
    # ax.scatter(lon, lat, color='green', s=60, edgecolor='k', zorder=11, transform=getattr(ccrs, projection)(), label=f"Center Point (Lat: {lat:.4f}, Lon: {lon:.4f})")
    inside_radius = ax.scatter(inside_df['LONGITUDE'], inside_df['LATITUDE'], color='red', s=40, edgecolor='k', zorder=10, transform=getattr(ccrs, projection)(), label=f"PDSI Cells Within a {radius_km:.0f} km Radius")
    center_point = ax.scatter(lon, lat, color='green', s=60, edgecolor='k', zorder=11, transform=getattr(ccrs, projection)(), label=f"Gauge Location (Lat: {lat:.4f}, Lon: {lon:.4f})")

    # Draw a circle around the center point to represent the search radius
    geod = Geodesic()
    circle_points = geod.circle(lon=lon, lat=lat, radius=radius_km * 1000, n_samples=80)
    poly = Polygon(circle_points)
    ax.add_geometries([poly], crs=getattr(ccrs, projection)(), facecolor='none', edgecolor='blue', linestyle='--')

    # Add gridlines and labels for latitude and longitude
    gridlines = ax.gridlines(draw_labels=True, crs=getattr(ccrs, projection)(), linewidth=1, color='gray', alpha=0.5, linestyle='--')
    gridlines.xlabels_bottom = True
    gridlines.ylabels_left = True
    gridlines.xlabels_top = False
    gridlines.ylabels_right = False
    gridlines.xformatter = LongitudeFormatter()
    gridlines.yformatter = LatitudeFormatter()
    gridlines.xlocator = mticker.MaxNLocator(nbins=5)
    gridlines.ylocator = mticker.MaxNLocator(nbins=5)

    # Add a legend and title
    ax.set_title('Selected Tree-Ring PDSI Gridpoints')
    #legend = ax.legend(loc='upper left', facecolor='white', framealpha=1, edgecolor='black')
    # Include the MRB patch in the legend only if it exists
    legend_handles = [inside_radius, center_point]
    if detect_basin:
        if mrb_patch: legend_handles.insert(0, mrb_patch)
    
    legend = ax.legend(handles=legend_handles, loc='upper left', facecolor='white', framealpha=1, edgecolor='black')

    legend.set_zorder(20)

    # Save the map
    plt.savefig(map_file, dpi=300, bbox_inches='tight')
    plt.close(fig)