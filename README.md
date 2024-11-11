# PALEO-RECON

**PALEO-RECON** is an automated tool for paleoclimate reconstruction of variables such as streamflow or precipitation, based on observed data and self-calibrated Palmer Drought Severity Index (scPDSI) cells. This platform enables fast, accurate, and reproducible reconstructions through the following steps:

- **scPDSI Cell Selection**: Selects relevant scPDSI cells within a specified radius around an observation point.
- **Cell Mapping**: Visualizes the selected scPDSI cells on a map and, if enabled, highlights the major basin in which the observation point is located.
- **Stepwise Linear Regression (SLR)**: Conducts paleoclimate reconstruction using SLR, optimizing predictor variables and calculating performance metrics such as R², DW and VIF.
- **Bias Correction**: Applies Quantile Mapping (RQUANT) for bias correction, aligning reconstructed values more closely with observed data.

## Installation Requirements

1. **Python and R**: Install Python (version 3.10.12 or higher) and R (version 4.3.1 or higher) on your system.
2. **Anaconda Environment**: Creating an Anaconda environment for this project is recommended for easier dependency management.

   ```bash
   conda create -n paleo-recon python=3.10.12
   conda activate paleo-recon
   ```

3. **Python and R Libraries**: Required libraries are listed in the `requirements.txt` file (to be generated), which you can install with the following command:

   ```bash
   pip install -r requirements.txt
   ```

   Additionally, install the `qmap` package in R for bias correction:

   ```R
   install.packages("qmap")
   ```

4. **Datasets and References**:
   - **OWDA (Old World Drought Atlas)** for Europe: [Cook et al., 2015](https://www.science.org/doi/abs/10.1126/sciadv.1500561)
   - **LBDA (Living Blended Drought Atlas)** for North America: [Cook et al., 2010](https://onlinelibrary.wiley.com/doi/abs/10.1002/jqs.1303)
   - **QMAP for Bias Correction**: [Robeson et al., 2020](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2019GL086689)
   - **Major River Basins of the World (GeoJSON)**: [Global Runoff Data Centre, 2020](https://mrb.grdc.bafg.de/)

## Running the Application

1. **Start the Application**: Run the following command in your terminal to start the application:

   ```bash
   python app.py
   ```

2. **Access in Browser**: Open your web browser and go to `http://127.0.0.1:5000` to access the application.

## Entering Data in the Interface

The PALEO-RECON interface allows you to specify parameters for the reconstruction. Here’s the required format for each field:

- **Coordinate Format**: Choose between decimal or DMS (degrees, minutes, seconds) format for entering observation point coordinates.
  - **Decimal**: Enter latitude and longitude in decimal format.
  - **DMS**: Enter degrees, minutes, and seconds, selecting the appropriate direction (N, S, E, W).

- **Auto-Detect Basin**: Enable this option to highlight the major basin if the observation point falls within one of the world's largest river basins.

- **Search Radius (km)**: Define the radius, in kilometers, around the observation point to select relevant scPDSI cells.

- **Window Size for SLR**: Select the size of the reconstruction window for the stepwise linear regression.

- **Observed Data (CSV)**:
  - The file should be in CSV format with two columns: "Year" and observed data.
  - Years must be in integer format in the first column, and observed values should be in decimal format in the second.
  - The file can use commas (`,`) or semicolons (`;`) as delimiters.

## Application Functionality

Once all fields are filled, press the **Reconstruct** button. The application will:

1. Select and map the scPDSI cells within the search radius.
2. Execute the paleoclimate reconstruction using SLR.
3. Display the map and generate download links for:
   - Selected coordinates.
   - Data from selected cells.
   - SLR results.

## Citation

If you use **PALEO-RECON** in your research, please cite it in either of these two ways:

1. **To cite PALEO-RECON as introduced in**:
   > Ramírez Molina, A.A., Tootle, G., Formetta, G., Piechota, T., Gong, J., "Extraordinary 21st Century Drought in the Po River Basin (Italy)," *Submitted to Hydrology*, 2024.
   *Once the paper is published, please update the citation accordingly.*

2. **To cite the PALEO-RECON software directly**:
    > Ramírez Molina, A. A. (2024). PALEO-RECON: An Automated Tool for Paleoclimate Reconstructions [Software] (v.1.0.0). Zenodo. DOI: [10.5281/zenodo.14061377](https://doi.org/10.5281/zenodo.14061377)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
