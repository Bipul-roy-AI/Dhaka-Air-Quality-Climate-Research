"""Export a credited location map as 600-dpi PNG, editable SVG and vector PDF.

Country context and the reported Dhaka monitor location are mapped in WGS84 / UTM46N.
No concentration surface, city boundary or unverified extraction node is inferred.
"""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import patches, ticker
from matplotlib.path import Path as PlotPath
import numpy as np
from pyproj import Geod, Transformer

CRS = 'EPSG:32646'
PROJECT = Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
INVERSE = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True)
GEOD = Geod(ellps='WGS84')
COLORS = {'Bangladesh': '#e3d4aa', 'default': '#ecebe7', 'border': '#686c70',
          'sea': '#eaf4f8', 'embassy': '#b7432e'}


def project(lon, lat):
    lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    if not (np.isfinite(lon).all() and np.isfinite(lat).all()):
        raise ValueError('Coordinates must be finite')
    if ((lon < 87) | (lon > 97) | (lat < 18) | (lat > 30)).any():
        raise ValueError('Study locations must be explicit Bangladesh-region longitude/latitude')
    return PROJECT.transform(lon, lat)


def projected_extent(bounds):
    west, south, east, north = bounds
    lon = np.array([west, east, east, west])
    lat = np.array([south, south, north, north])
    x, y = project(lon, lat)
    return [float(min(x)), float(max(x)), float(min(y)), float(max(y))]


def geometry_paths(geometry):
    polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
    for polygon in polygons:
        vertices, codes = [], []
        for ring in polygon:
            points = np.asarray(ring, dtype=float)
            x, y = PROJECT.transform(points[:, 0], points[:, 1])
            vertices.extend(zip(x, y))
            codes.extend([PlotPath.MOVETO] + [PlotPath.LINETO] * (len(points) - 2) + [PlotPath.CLOSEPOLY])
        yield PlotPath(vertices, codes)


def draw_context(ax, context, bounds):
    ax.set_facecolor(COLORS['sea'])
    for feature in context['features']:
        name = feature['properties']['name']
        for path in geometry_paths(feature['geometry']):
            ax.add_patch(patches.PathPatch(path, facecolor=COLORS.get(name, COLORS['default']),
                                          edgecolor=COLORS['border'], lw=.6, zorder=2))
    xmin, xmax, ymin, ymax = projected_extent(bounds)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: f'{value / 1000:.0f}'))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: f'{value / 1000:.0f}'))
    ax.tick_params(labelsize=8, length=3)
    for spine in ax.spines.values():
        spine.set_color('#7b8185')


def scale_bar(ax, metres, label, fraction=(.09, .09)):
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    x, y = xmin + fraction[0] * (xmax - xmin), ymin + fraction[1] * (ymax - ymin)
    height = (ymax - ymin) * .009
    for i, color in enumerate(['#25313a', 'white']):
        ax.add_patch(patches.Rectangle((x + i * metres / 2, y), metres / 2, height,
                                     facecolor=color, edgecolor='#25313a', lw=.7, zorder=8))
    ax.text(x, y - 1.1 * height, '0', ha='center', va='top', fontsize=8, zorder=9)
    ax.text(x + metres, y - 1.1 * height, label, ha='center', va='top', fontsize=8, zorder=9)


def true_north(ax):
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    x, y = xmin + .89 * (xmax - xmin), ymin + .84 * (ymax - ymin)
    lon, lat = INVERSE.transform(x, y)
    lon_n, lat_n, _ = GEOD.fwd(lon, lat, 0, (ymax - ymin) * .075)
    xn, yn = PROJECT.transform(lon_n, lat_n)
    ax.annotate('', xy=(xn, yn), xytext=(x, y),
                arrowprops={'arrowstyle': '-|>', 'color': '#25313a', 'lw': 1.3}, zorder=10)
    ax.text(xn, yn + (ymax - ymin) * .012, 'N', ha='center', fontsize=10, weight='bold', zorder=10)


def render(context_path, locations_path, output, dpi=600):
    manifest_path = context_path.with_name('context_manifest.json')
    source_manifest = json.loads(manifest_path.read_text())
    context_hash = hashlib.sha256(context_path.read_bytes()).hexdigest()
    if context_hash != source_manifest['selected_context_sha256']:
        raise ValueError('Map context differs from its acquisition manifest')
    context = json.loads(context_path.read_text())
    locations = json.loads(locations_path.read_text())
    points = {}
    for feature in locations['features']:
        if feature['geometry']['type'] != 'Point':
            raise ValueError('Only reported point locations are supported')
        key = feature['properties']['id']
        if key in points:
            raise ValueError('Duplicate location identifier')
        lon, lat = feature['geometry']['coordinates']
        points[key] = (lon, lat, *project(lon, lat))
    if 'embassy' not in points:
        raise ValueError('The explicitly sourced Dhaka monitor location is required')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none'})
    fig = plt.figure(figsize=(6.4, 8.0), facecolor='white')
    ax = fig.add_axes([.16, .15, .80, .73])
    draw_context(ax, context, [87.8, 20.4, 93.35, 26.9])
    ax.set_title('Bangladesh and the Dhaka study location', fontsize=11, loc='left', pad=10)
    ax.set_xlabel('Easting (km, UTM zone 46N)', labelpad=7)
    ax.set_ylabel('Northing (km, UTM zone 46N)', labelpad=7)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(100000))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(100000))
    for name, lon, lat, rotation in [('BANGLADESH', 90.25, 24.9, 0), ('INDIA', 88.15, 24.4, 90),
                                      ('MYANMAR', 92.8, 22.0, 65), ('Bay of Bengal', 90.9, 21.1, 0)]:
        x, y = PROJECT.transform(lon, lat)
        ax.text(x, y, name, ha='center', va='center', rotation=rotation,
                color='#4f5c62', fontsize=9 if name != 'BANGLADESH' else 10, zorder=5)
    _, _, x, y = points['embassy']
    ax.scatter([x], [y], marker='*', s=110, color=COLORS['embassy'], edgecolor='white', linewidth=.7, zorder=7)
    ax.annotate('Dhaka', xy=(x, y), xytext=(20, 14), textcoords='offset points',
                fontsize=10, weight='bold', arrowprops={'arrowstyle': '-', 'lw': .8}, zorder=8)
    true_north(ax)
    scale_bar(ax, 100000, '100 km')
    fig.suptitle('Dhaka, Bangladesh | Study area', x=.14, y=.95, ha='left', fontsize=14, weight='bold')
    fig.text(.14, .055, 'WGS84 / UTM zone 46N (EPSG:32646) • Scale in projected grid metres', fontsize=7)
    fig.text(.14, .03, 'Context: Natural Earth 1:10m (public domain) • Location: EPA-associated study', fontsize=6.8, color='#4f5c62')
    output.mkdir(parents=True, exist_ok=False)
    for extension in ['png', 'svg', 'pdf']:
        fig.savefig(output / f'study_area.{extension}', dpi=dpi, facecolor='white')
    plt.close(fig)
    record = {'purpose': 'Simple study-area location map; not a concentration surface or an administrative city boundary',
              'map_crs': CRS, 'source_crs': 'EPSG:4326; longitude,latitude', 'raster_dpi': dpi,
              'vector_formats': ['SVG with editable text', 'PDF with embedded TrueType fonts'],
              'context_sha256': context_hash, 'context_source_commit': source_manifest['source_commit'],
              'locations_sha256': hashlib.sha256(locations_path.read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'locations': [feature for feature in locations['features'] if feature['properties']['id'] == 'embassy'],
              'layout': 'Single national location panel; reference-point inset and coordinate panel omitted',
              'licence': source_manifest['licence'],
              'attribution': source_manifest['attribution'],
              'scale_bar_definition': 'Projected UTM grid metres; true north from WGS84 geodesic direction',
              'figure_is_not_a_manuscript': True}
    (output / 'map_manifest.json').write_text(json.dumps(record, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', type=Path, default=Path('data/maps/context.geojson'))
    parser.add_argument('--locations', type=Path, default=Path('data/maps/locations.geojson'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dpi', type=int, default=600)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory')
    if args.dpi < 300:
        parser.error('Use at least 300 dpi for publication exports')
    render(args.context, args.locations, args.output, args.dpi)
    print(args.output)


if __name__ == '__main__':
    main()
