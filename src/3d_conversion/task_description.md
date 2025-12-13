# Task 1: Conversion of a 3D Model (OBJ) to KMZ with Georeferencing for

## Use in ATAK
Objective: You need to implement a Python script that converts a 3D model in .obj format into a
.kmz file with correct spatial georeferencing. The resulting .kmz file must open in ATAK with the
model accurately positioned on the map.

## #Input files:
    - .obj — 3D model of the area
    - georeferencing_model_geo.txt — contains the geospatial reference of the model in the
following format:
    WGS84 UTM 35N
    418574 5345544
    These are the coordinates of the model’s center in the UTM Zone 35N projection
    (EPSG:32635).

## Script requirements:
- Read the .obj file and the coordinate file.
- Insert the model into a .kmz file, taking into account the calculated geolocation.
- Save the resulting .kmz file compatible with ATAK.
- Work entirely on a server (no GUI), under Linux.

## Expected result:
A Python script or CLI utility that accepts the following parameterfs:
- Path to the .obj file
- Path to georeferencing_model_geo.txt
- Path to the output .kmz file
- requirements.txt or installation instructions for dependencies
- README.md or a short usage example
- One .kmz file where the 3D model is correctly georeferenced according to the provided coordinates

## Technical recommendations:
- you may use any open-source libraries.
- The solution must work on a Linux server without a graphical interface (GUI).

## Test files:
- OBJ model
- georeferencing_model_geo.txt (located in the same directory as the .obj file)