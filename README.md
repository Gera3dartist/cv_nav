# OBJ to KMZ Converter

Convert 3D OBJ models to georeferenced KMZ files for use in ATAK.

## Installation

Requires Python 3.12+

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

## Usage
In this readme, assumed, commands invoked from project folder

```bash
uv run python -m src.3d_conversion <obj_path> <geo_path> [-o output.kmz]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `obj_path` | Path to the .obj file |
| `geo_path` | Path to georeferencing file (UTM coordinates) |
| `-o, --output` | Output .kmz path (default: `output/model.kmz`) |

### Example

```bash
uv run python -m src.3d_conversion \
    data/textured_model_geo.obj \
    data/georeferencing_model_geo.txt \
    -o output/model.kmz
```

## Georeferencing File Format

The georeferencing file should contain:

```
WGS84 UTM 35N
418574 5345544
```

- Line 1: Coordinate system (UTM zone)
- Line 2: Easting and Northing coordinates (model center)

## Output

The tool generates a `.kmz` file containing:
- `doc.kml` - KML with georeferenced model placement
- `models/model.dae` - COLLADA 3D model

Open the resulting KMZ in Google Earth Pro or ATAK to verify placement.

## P.S: 
- Time took approx: 19 - 11 - 2 = 6 hours
- Validation: the resulting KMZ opens in  viewers  (tried in https://imagetostl.com/view-kmz-online#convert and Google Earth Pro), 