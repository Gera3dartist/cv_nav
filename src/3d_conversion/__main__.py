import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer
import trimesh
import zipfile

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# todo: more precise types: literals, ranges
@dataclass
class CoordinateMap:
    epsg: int  # epsg code 
    crs: str   # parsed line from file
    easting: float
    northing: float


@dataclass(frozen=True)
class GPSCoordinate:
    long: float
    lat: float



def parse_coordinates(path: str) -> CoordinateMap:
    """
    assumed the file of this structure:
    '''
    WGS84 UTM 35N
    418574 5345544
    '''
    """
    with open(path, 'r') as data:
        crs, coordinates = [line.strip() for line in data.readlines()[:2]]
        # naïve parsing for northing zone
        zone = crs.split()[-1]
        easting_index, hemisphere = int(zone[:-1]), zone[-1], 
        (easting, northing) = coordinates.split()
        return CoordinateMap(
            crs=crs,
            epsg=(32600 if hemisphere == 'N' else 32700) + easting_index,
            easting=float(easting),
            northing=float(northing)
        )

def utm_to_long_lat(epsg_code: int, easting: float, northing: float) -> GPSCoordinate:
    transformer = Transformer.from_crs(f'EPSG:{epsg_code}', 'EPSG:4326', always_xy=True)
    return GPSCoordinate(*transformer.transform(easting, northing))

def get_dae_bytes_from_obj(obj_path: str, should_center: bool = True) -> bytes:
    mesh = trimesh.load(Path(obj_path).resolve(), force='mesh')
    if should_center:
        centroid = mesh.centroid.copy()
        centroid[2] = 0 # do not move Z
        mesh.vertices -= centroid
    mesh.visual = trimesh.visual.ColorVisuals(
        mesh, 
        face_colors = [180, 180, 180, 255] # light gray, becuase textures are not preserved
    )
    return trimesh.exchange.dae.export_collada(mesh)



def create_kml(
    lat: float,
    lon: float,
    model_path: str = "models/model.dae",
    altitude: float = 0.0,
    heading: float = 0.0,
    tilt: float = 0.0,
    roll: float = 0.0,
    scale: float = 1.0,
) -> str:
    """
    Create KML document with georeferenced 3D model.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees  
        model_path: Relative path to DAE file inside KMZ
        altitude: Height above ground in meters
        heading: Rotation around Z-axis (0=North, 90=East)
        tilt: Rotation around X-axis
        roll: Rotation around Y-axis
        scale: Uniform scale factor
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>3D Model</name>
    <Placemark>
      <name>Georeferenced Model</name>
      <Model id="model">
        <altitudeMode>relativeToGround</altitudeMode>
        <Location>
          <longitude>{lon}</longitude>
          <latitude>{lat}</latitude>
          <altitude>{altitude}</altitude>
        </Location>
        <Orientation>
          <heading>{heading}</heading>
          <tilt>{tilt}</tilt>
          <roll>{roll}</roll>
        </Orientation>
        <Scale>
          <x>{scale}</x>
          <y>{scale}</y>
          <z>{scale}</z>
        </Scale>
        <Link>
          <href>{model_path}</href>
        </Link>
      </Model>
    </Placemark>
  </Document>
</kml>"""

def write_kmz(
    kml: str, 
    dae_bytes: bytes, 
    kmz_name: str = 'output.kmz', 
    kml_name: str = 'doc.kml', 
    models_path: str = 'models/model.dae'
) -> None:
    with zipfile.ZipFile(kmz_name, 'w', zipfile.ZIP_DEFLATED) as kmz:
        kmz.writestr(kml_name,  kml)
        kmz.writestr(models_path,  dae_bytes)



def convert_obj_to_kmz(obj_path: str, geo_path: str, output_path: str) -> None:
    """Convert OBJ model to georeferenced KMZ file."""
    logger.info("Starting OBJ to KMZ conversion")

    # 1. Parse coordinates from georeferencing file
    logger.info(f"Step 1: Parsing coordinates from {geo_path}")
    coordinate_map = parse_coordinates(geo_path)
    logger.info(f"Parsed UTM coordinates: EPSG:{coordinate_map.epsg}, E:{coordinate_map.easting}, N:{coordinate_map.northing}")

    # 2. Convert UTM to WGS84
    logger.info("Step 2: Converting UTM to WGS84")
    gps_coordinates = utm_to_long_lat(
        epsg_code=coordinate_map.epsg,
        easting=coordinate_map.easting,
        northing=coordinate_map.northing,
    )
    logger.info(f"GPS coordinates: lat={gps_coordinates.lat}, lon={gps_coordinates.long}")

    # 3. Convert OBJ to COLLADA
    logger.info(f"Step 3: Converting OBJ to COLLADA from {obj_path}")
    dae_bytes = get_dae_bytes_from_obj(obj_path, should_center=True)
    logger.info(f"Generated DAE: {len(dae_bytes) / 1024 / 1024:.1f} MB")

    # 4. Create KML with georeferencing
    logger.info("Step 4: Creating KML document")
    kml_body = create_kml(lon=gps_coordinates.long, lat=gps_coordinates.lat)

    # 5. Package into KMZ
    logger.info(f"Step 5: Packaging into KMZ at {output_path}")
    write_kmz(kml=kml_body, dae_bytes=dae_bytes, kmz_name=output_path)
    logger.info("Conversion complete")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Convert a 3D OBJ model to georeferenced KMZ for ATAK'
    )
    parser.add_argument(
        'obj_path',
        help='Path to the .obj file'
    )
    parser.add_argument(
        'geo_path',
        help='Path to georeferencing_model_geo.txt'
    )
    parser.add_argument(
        '-o', '--output',
        default='output/model.kmz',
        help='Path to output .kmz file (default: output/model.kmz)'
    )

    args = parser.parse_args()

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    convert_obj_to_kmz(args.obj_path, args.geo_path, str(output_path))


if __name__ == "__main__":
    main()