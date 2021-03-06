import shutil
import struct
import json
import os
import sys
import argparse
INF = float('inf')

#settings.original_maps_dir = './s1_original_maps'
#settings.editable_maps_dir = './s2_editable_maps'
#settings.final_maps_dir = './s3_final_maps'

DEFAULT_CONFIG = \
"""
original-maps-dir: s1_original_maps
editable-maps-dir: s2_editable_maps
final-maps-dir: s3_final_maps
""".strip()

HAS_WARNINGS = False

def read_config():
    CONFIG_FILE_NAME = './settings.txt'

    # create config file if it doesn't exist.
    if not os.path.isfile(CONFIG_FILE_NAME):
        f = open(CONFIG_FILE_NAME, 'w+')
        f.write(DEFAULT_CONFIG)
        f.close()

    config = {}
    if os.path.isfile(CONFIG_FILE_NAME):
        f = open(CONFIG_FILE_NAME)
        lines = f.read().split('\n')
        f.close()
        for line in lines:
            if ':' not in line: continue
            key, value = (x.strip() for x in line.split(':', 1))
            config[key] = value
    else:
        fail('settings file %s not found!' % CONFIG_FILE_NAME)
    return config

def parse_args():
    config = read_config()
    def check_for_key(keyname):
        if keyname not in config: fail('config key not found: %s' % keyname)
    check_for_key('original-maps-dir')
    check_for_key('editable-maps-dir')
    check_for_key('final-maps-dir')

    args = argparse.ArgumentParser(description='Rabi-Ribi Map Converter')
    args.add_argument('-original-maps-dir', default=config['original-maps-dir'], help='Source directory for original maps. Defaults to s1_original_maps/. Do not make the original maps dir the final maps dir.')
    args.add_argument('-editable-maps-dir', default=config['editable-maps-dir'], help='Directory for editable json maps. Defaults to s2_editable_maps/. Tilesets should be placed in this directory.')
    args.add_argument('-final-maps-dir', default=config['final-maps-dir'], help='Output directory for final map files. Defaults to s3_final_maps/. Do not make the original maps dir the final maps dir.')
    args.add_argument('--map-to-json', action='store_true', help='Use to convert original map files to editable json files.')
    args.add_argument('--json-to-map', action='store_true', help='Use to convert editable json files to final map files.')

    return args.parse_args(sys.argv[1:])

def fail(message):
    print('ERROR! %s' % message)
    print('\nFAILED TO CONVERT')
    sys.exit(1)

def warn(message):
    global HAS_WARNINGS
    HAS_WARNINGS = True
    print('WARNING: %s' % message)

MAP_SIZE = 100000
MINIMAP_SIZE = 450

ARRAY_MAP = 0
ARRAY_EVENT = 200000
ARRAY_ROOMTYPE = 400000
ARRAY_ROOMCOLOR = 400900
ARRAY_ROOMBG = 401800
ARRAY_ITEMS = 402700
INT_AREA = 602700
ARRAY_TILES_0 = 602704
ARRAY_TILES_1 = 802704
ARRAY_TILES_2 = 1002704
ARRAY_TILES_3 = 1202704
ARRAY_TILES_4 = 1402704
ARRAY_TILES_5 = 1602704
ARRAY_TILES_6 = 1802704
INT_VERSION = 2602704

COLLISION_TILESET_OFFSET = 5000

def transpose_d2l(data):
    x = [data[i::200] for i in range(200)]
    return [x for x in x for x in x] # flatten list

def transpose_l2d(data):
    x = [data[i::500] for i in range(500)]
    return [x for x in x for x in x] # flatten list

def collision_data_to_layer(data, name):
    def idmap(i):
        if i == 0: return 0
        return i + COLLISION_TILESET_OFFSET

    return {
        "width": 500,
        "height": 200,
        "x": 0,
        "y": 0,
        "type": "tilelayer",
        "visible": True,
        "opacity": 1,
        "name": name,
        "data": transpose_d2l([idmap(i) for i in data])
    }

def object_data_to_layer(data, name, color):
    def make_object(index, value):
        return {
            "width": 32,
            "height": 32,
            "x": 32*(index//200),
            "y": 32*(index%200),
            "name": str(value)
        }
    objects = [make_object(i, o) for i, o in enumerate(data) if o != 0]

    return {
        "draworder":"topdown",
        "name": name,
        "objects": objects,
        "opacity":1,
        "color": color,
        "type":"objectgroup",
        "visible": True,
        "x":0,
        "y":0,
    }

def tile_data_to_layer(data, name):
    def idmap(i):
        if i == 0: return 0
        actualid = 0
        if i < 0:
            actualid += 0x80000000
            i = -i
        if i >= 5000:
            actualid += 0x40000000
            i -= 5000
        i -= 2*(i//32)
        return actualid + i + 1

    return {
        "width": 500,
        "height": 200,
        "x": 0,
        "y": 0,
        "type": "tilelayer",
        "visible": True,
        "opacity": 1,
        "name": name,
        "data": transpose_d2l([idmap(i) for i in data])
    }

def minimap_data_to_layer(data, name, color, visible=True):
    def make_object(index, value):
        x, y = index//18, index%18
        return {
            "width": 640,
            "height": 352,
            "x": 640*x,
            "y": 32 * (11*y + (y+3)//4),
            "type": "(%d, %d)" % (x,y),
            "name": str(value)
        }
    objects = [make_object(i, o) for i, o in enumerate(data)]

    return {
        "draworder":"topdown",
        "name": name,
        "objects": objects,
        "color": color,
        "opacity": 0.35,
        "locked": True,
        "type":"objectgroup",
        "visible": visible,
        "x":0,
        "y":0,
    }

def object_layer_to_data(layer_data, layer_name):
    data = [0]*MAP_SIZE

    for item in layer_data['objects']:
        try:
            value = int(item['name'])
            if item['x']%32 != 0 or item['y']%32 != 0:
                warn('Object "%s" with invalid coordinates %.2f, %.2f found in layer "%s". Object will be ignored. Please make sure you have "snap to grid" checked.'
                    % (item['name'], item['x'], item['y'], layer_name))
                continue
            index = item['x']//32 * 200 + item['y']//32
            data[index] = value
        except ValueError as e:
            warn('Object with invalid name "%s" at position %.2f, %.2f in layer "%s". Object will be ignored.'
                % (item['name'], item['x'], item['y'], layer_name))

    return data

def minimap_layer_to_data(layer_data, layer_name):
    data = [None]*MINIMAP_SIZE

    def fail_details(item, message):
        x = '?'
        if 'x' in item: x = '%.2f' % item['x']
        y = '?'
        if 'y' in item: y = '%.2f' % item['y']
        name = '?'
        if 'name' in item: name = item['name']
        fail('Minimap layer "%s", object "%s" at %s, %s: %s' % (layer_name, name, x, y, message))


    for item in layer_data['objects']:
        try:
            value = int(item['name'])
            if item['x']%32 != 0 or item['y']%32 != 0:
                fail_details(item, 'Minimap tile object not positioned correctly.')
            x = item['x']//640
            y = item['y']//32
            y = 4*(y//45) + max(0,y%45-1)//11
            index = x*18 + y
            if data[index] != None:
                fail_details(item, 'Duplicate minimap tile object.')
            data[index] = value
        except ValueError as e:
            fail_details(item, 'Minimap tile name needs to be a number.')

    for i, val in enumerate(data):
        if val == None:
            x, y = i//18, i%18
            fail('Layer %s\'s map tile at (%d, %d) is missing.' % (layer_name, x, y))

    return data

def map_to_json(filename, settings):
    print('Converting Original map file -> Json : %s' % filename)
    # location of source map file
    sourcefile = "%s/%s.map" % (settings.original_maps_dir, filename)
    targetfile = "%s/%s.json" % (settings.editable_maps_dir, filename)
    
    # LOADING MAP DATA
    f = open(sourcefile, "rb")
    f.seek(ARRAY_MAP)
    tiledata_map = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_EVENT)
    tiledata_event = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_ITEMS)
    tiledata_items = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    
    f.seek(ARRAY_ROOMTYPE)
    tiledata_roomtype = list(struct.unpack('%dh' % MINIMAP_SIZE, f.read(MINIMAP_SIZE*2)))
    f.seek(ARRAY_ROOMCOLOR)
    tiledata_roomcolor = list(struct.unpack('%dh' % MINIMAP_SIZE, f.read(MINIMAP_SIZE*2)))
    f.seek(ARRAY_ROOMBG)
    tiledata_roombg = list(struct.unpack('%dh' % MINIMAP_SIZE, f.read(MINIMAP_SIZE*2)))
    
    f.seek(INT_AREA)
    metadata_area = list(struct.unpack('i', f.read(4)))[0]
    
    f.seek(ARRAY_TILES_0)
    tiledata_tiles0 = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_TILES_1)
    tiledata_tiles1 = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_TILES_2)
    tiledata_tiles2 = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_TILES_3)
    tiledata_tiles3 = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_TILES_4)
    tiledata_tiles4 = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_TILES_5)
    tiledata_tiles5 = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    f.seek(ARRAY_TILES_6)
    tiledata_tiles6 = list(struct.unpack('%dh' % MAP_SIZE, f.read(MAP_SIZE*2)))
    
    f.seek(INT_VERSION)
    metadata_version = list(struct.unpack('i', f.read(4)))[0]
    f.close()

    extracted_metadata, new_tiledata_event = extract_encoded_metadata(tiledata_event)
    bunmania_mode = (extracted_metadata['bm_name'] != '')
    if bunmania_mode:
        tiledata_event = new_tiledata_event

    # layer draw order: 0 3 4 1 5 6 2
    layers = [
        collision_data_to_layer(tiledata_map, "collision"),
        tile_data_to_layer(tiledata_tiles0, "tiles0"),
        tile_data_to_layer(tiledata_tiles3, "tiles3"),
        tile_data_to_layer(tiledata_tiles4, "tiles4"),
        tile_data_to_layer(tiledata_tiles1, "tiles1"),
        tile_data_to_layer(tiledata_tiles5, "tiles5"),
        tile_data_to_layer(tiledata_tiles6, "tiles6"),
        tile_data_to_layer(tiledata_tiles2, "tiles2"),
        object_data_to_layer(tiledata_event, "event", "#8080ff"),
        object_data_to_layer(tiledata_items, "items", "#ff6000"),
        minimap_data_to_layer(tiledata_roomtype, "roomtype", "#00ffff", visible=False),
        minimap_data_to_layer(tiledata_roomcolor, "roomcolor", "#ffff00", visible=False),
        minimap_data_to_layer(tiledata_roombg, "roombg", "#00ff00", visible=False),
    ]

    data = {
        "width": 500,
        "height": 200,
        "tilewidth": 32,
        "tileheight": 32,
        "orientation":"orthogonal",
        "renderorder":"right-down",
        "tiledversion":"1.0.2402",
        "tilesets":[
            {
             "firstgid": 1,
             "source":"TILE_A.tsx",
            }, 
            {
             "firstgid":COLLISION_TILESET_OFFSET,
             "source":"collision.tsx",
            }],
        "properties":
            {
             "area": metadata_area,
             "version": metadata_version,
             "bunmania": False,

             "bm_name": 'untitled',
             "bm_author": '-',
             "bm_par5": 150,
             "bm_par4": 110,
             "bm_par3": 90,
             "bm_par2": 75,
             "bm_par1": 60,
             "bm_fullexp": False,
             "bm_difficulty": 1,
             "bm_numeggs": 0,
            },
        "propertytypes":
            {
             "area":"int",
             "version":"int",
             "bunmania":"bool",

             "bm_name": 'string',
             "bm_author": 'string',
             "bm_par5": 'float',
             "bm_par4": 'float',
             "bm_par3": 'float',
             "bm_par2": 'float',
             "bm_par1": 'float',
             "bm_fullexp": 'bool',
             "bm_difficulty": "int",
             "bm_numeggs": "int",
            },
        "type":"map",
        "version":1,
        "layers": layers,
    }

    if bunmania_mode:
        properties = data['properties']
        for key, value in extracted_metadata.items():
            if value != None: properties[key] = value
        properties['bunmania'] = True


    f = open(targetfile, 'w+')
    f.write(json.dumps(data))
    f.close()

def read_metadata(properties, property_types):
    metadata = {}

    def set_metadata(property_name, value):
        metadata[property_name] = value

    def get_property(property_name, property_type, default_value):
        if property_name not in properties:
            warn('bunmania property %s (%s) not found. using default value of %s' % (property_name, property_type, default_value))
            return set_metadata(property_name, default_value)
        if property_name not in property_types:
            warn('bunmania property %s (%s) not found. using default value of %s' % (property_name, property_type, default_value))
            return set_metadata(property_name, default_value)
        if property_types[property_name] != property_type:
            fail('bunmania property %s has wrong type. should be %s, not %s' % (property_name, property_type, property_types[property_name]))

        set_metadata(property_name, properties[property_name])

    get_property('bm_name', 'string', 'untitled')
    get_property('bm_author', 'string', '-')
    get_property('bm_par5', 'float', 150)
    get_property('bm_par4', 'float', 110)
    get_property('bm_par3', 'float', 90)
    get_property('bm_par2', 'float', 75)
    get_property('bm_par1', 'float', 60)
    get_property('bm_fullexp', 'bool', False)
    get_property('bm_difficulty', 'int', 1)
    get_property('bm_numeggs', 'int', 0)

    return metadata

def apply_metadata(map_arrays, metadata):
    def get_string_data(string_name, string, charlimit):
        if len(string) > charlimit: fail('%s cannot be longer than %d chars.' % (string_name, charlimit))
        if not all(ord(c) < 128 for c in string): fail('%s must use only ASCII characters.' % string_name)

        return (5000+ord(c) for c in string)

    def get_time_data(time_name, time_value):
        if time_value <= 0: fail('Time %s cannot be negative or zero.' % time_name)
        if time_value >= 3600: fail('Time %s exceeds 60 minutes.' % time_name)

        mins = int(time_value//60)
        secs = int(time_value%60)
        millis = int(time_value%1 * 60)

        return (5000+x for x in (mins, secs, millis))

    def get_bool_data(bool_name, bool_value):
        return (5000+(1 if bool_value else 0),)

    def get_int_data(int_name, int_value):
        return (5000+int_value,)

    def write_into_row(row, data):
        for x, v in enumerate(data):
            map_arrays['event'][row+200*x] = v

    write_into_row(0, get_string_data('map name', metadata['bm_name'], 32))
    write_into_row(1, get_string_data('author name', metadata['bm_author'], 16))
    
    write_into_row(2, get_time_data('par5 (bronze)', metadata['bm_par5']))
    write_into_row(3, get_time_data('par4 (silver)', metadata['bm_par4']))
    write_into_row(4, get_time_data('par3 (gold)', metadata['bm_par3']))
    write_into_row(5, get_time_data('par2 (platinum)', metadata['bm_par2']))
    write_into_row(6, get_time_data('par1 (rainbow)', metadata['bm_par1']))

    write_into_row(7, get_bool_data('full exp', metadata['bm_fullexp']))

    write_into_row(8, get_int_data('difficulty', metadata['bm_difficulty']))
    write_into_row(9, get_int_data('number of eggs', metadata['bm_numeggs']))


def extract_encoded_metadata(tiledata_event):
    new_tiledata_event = tiledata_event[:]
    metadata = {}

    def decode_string_data(data):
        if len(data) < 1: return None
        to_chr = lambda v : chr(min(127, max(0, v-5000)))
        return ''.join(map(to_chr, data)).strip()

    def decode_time_data(data):
        if len(data) < 3: return None

        clamp = lambda v : min(59, max(0, v-5000))
        mins, secs, millis = map(clamp, data[:3])

        return mins*60 + secs + millis/60

    def decode_bool_data(data):
        if len(data) < 1: return None
        return bool(data[0]-5000)

    def decode_int_data(data):
        if len(data) < 1: return None
        return data[0]-5000

    def get_raw_data(row, length, blanks_as_spaces=False):
        data = []
        for x in range(length):
            v = tiledata_event[row+200*x]
            if v < 5000:
                if blanks_as_spaces:
                    v = 5032
                else:
                    break
            new_tiledata_event[row+200*x] = 0
            data.append(v)
        return data

    metadata['bm_name'] = decode_string_data(get_raw_data(row=0, length=32, blanks_as_spaces=True))
    metadata['bm_author'] = decode_string_data(get_raw_data(row=1, length=16, blanks_as_spaces=True))

    metadata['bm_par5'] = decode_time_data(get_raw_data(row=2, length=3))
    metadata['bm_par4'] = decode_time_data(get_raw_data(row=3, length=3))
    metadata['bm_par3'] = decode_time_data(get_raw_data(row=4, length=3))
    metadata['bm_par2'] = decode_time_data(get_raw_data(row=5, length=3))
    metadata['bm_par1'] = decode_time_data(get_raw_data(row=6, length=3))

    metadata['bm_fullexp'] = decode_bool_data(get_raw_data(row=7, length=1))

    metadata['bm_difficulty'] = decode_int_data(get_raw_data(row=8, length=1))
    metadata['bm_numeggs'] = decode_int_data(get_raw_data(row=9, length=1))

    return metadata, new_tiledata_event
    

def convert_to_ranges(first_gids):
    gid_list = list(first_gids.values())
    gid_ranges = {}
    for gid_name in first_gids.keys():
        first_gid = first_gids[gid_name]
        end_gid = min([INF] + [gid for gid in gid_list if gid > first_gid])
        gid_ranges[gid_name] = (first_gid, end_gid-first_gid)
    return gid_ranges


def json_to_map(filename, settings):
    print('Converting Json -> Final map file : %s' % filename)
    # location of source map file
    basemapfile = "%s/%s.map" % (settings.original_maps_dir, filename)
    sourcefile = "%s/%s.json" % (settings.editable_maps_dir, filename)
    targetfile = "%s/%s.map" % (settings.final_maps_dir, filename)
    shutil.copyfile(basemapfile, targetfile)

    f = open(sourcefile)
    jsondata = json.loads(f.read())
    f.close()

    bunmania_mode = ('bunmania' in jsondata['properties'] and jsondata['properties']['bunmania'] == True)

    if bunmania_mode:
        metadata = read_metadata(jsondata['properties'], jsondata['propertytypes'])

    gid_ranges = {}
    for tileset in jsondata['tilesets']:
        if 'TILE_A' in tileset['source']:
            gid_ranges['tiles'] = tileset['firstgid']
        if 'collision' in tileset['source']:
            gid_ranges['collision'] = tileset['firstgid']
    gid_ranges = convert_to_ranges(gid_ranges)

    layers = jsondata['layers']
    layers = dict((layer['name'], layer) for layer in layers)

    def warn_index(index, layer_name, message):
        x, y = index//200, index%200
        warn('%s(%d,%d) : %s' % (layer_name, x, y, message))
        return 0

    def collision_layer_to_data(layer_name, gid_name):
        layer_data = layers[layer_name]
        first_gid, gid_range = gid_ranges[gid_name]

        def rev_idmap(v):
            index, i = v
            if i == 0: return 0
            dataid = (i&0x0000FFFF) - first_gid
            if dataid < 0 or dataid >= gid_range:
                return warn_index(index, layer_name, 'Not a collision tile!')
            if i & 0xC0000000 != 0:
                warn_index(index, layer_name, 'Flipped collision tile. Do not flip collision tiles! Flipped collision tiles will be treated as their unflipped versions.')
            return dataid

        return transpose_l2d(list(map(rev_idmap, enumerate(layer_data['data']))))

    def tile_layer_to_data(layer_name, gid_name):
        layer_data = layers[layer_name]
        first_gid, gid_range = gid_ranges[gid_name]

        def rev_idmap(v):
            index, i = v
            if i == 0: return 0
            dataid = (i&0x0000FFFF) - first_gid
            if dataid < 0 or dataid >= gid_range:
                return warn_index(index, layer_name, 'Not a tile from the tileset!')
            dataid += 2*(dataid//30)
            if i & 0x40000000 != 0: dataid += 5000
            if i & 0x80000000 != 0: dataid = -dataid
            return dataid

        return transpose_l2d(list(map(rev_idmap, enumerate(layer_data['data']))))

    try:
        map_arrays = {
            "collision": collision_layer_to_data("collision", "collision"),
            "event": object_layer_to_data(layers["event"], "event"),
            "items": object_layer_to_data(layers["items"], "items"),
            "tiles0": tile_layer_to_data("tiles0", "tiles"),
            "tiles3": tile_layer_to_data("tiles3", "tiles"),
            "tiles4": tile_layer_to_data("tiles4", "tiles"),
            "tiles1": tile_layer_to_data("tiles1", "tiles"),
            "tiles5": tile_layer_to_data("tiles5", "tiles"),
            "tiles6": tile_layer_to_data("tiles6", "tiles"),
            "tiles2": tile_layer_to_data("tiles2", "tiles"),
        }
        for minimap_name in ["roomtype", "roomcolor", "roombg"]:
            if minimap_name in layers:
                map_arrays[minimap_name] = minimap_layer_to_data(layers[minimap_name], minimap_name)
            else:
                warn('Minimap layer "%s" not found. All %s tiles be set to the default value 0.' % (minimap_name, minimap_name))
                map_arrays[minimap_name] = None
    except KeyError as e:
        fail('Layer not found: %s. Please create the layer, or check that you have named the layers correctly.' % e)

    if bunmania_mode:
        apply_metadata(map_arrays, metadata)

    f = open(targetfile, "r+b")
    f.seek(ARRAY_MAP)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['collision']))
    f.seek(ARRAY_EVENT)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['event']))
    f.seek(ARRAY_ITEMS)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['items']))
    if map_arrays["roomtype"]:
        f.seek(ARRAY_ROOMTYPE)
        f.write(struct.pack('%dh' % MINIMAP_SIZE, *map_arrays["roomtype"]))
    if map_arrays["roomcolor"]:
        f.seek(ARRAY_ROOMCOLOR)
        f.write(struct.pack('%dh' % MINIMAP_SIZE, *map_arrays["roomcolor"]))
    if map_arrays["roombg"]:
        f.seek(ARRAY_ROOMBG)
        f.write(struct.pack('%dh' % MINIMAP_SIZE, *map_arrays["roombg"]))
    f.seek(ARRAY_TILES_0)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['tiles0']))
    f.seek(ARRAY_TILES_1)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['tiles1']))
    f.seek(ARRAY_TILES_2)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['tiles2']))
    f.seek(ARRAY_TILES_3)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['tiles3']))
    f.seek(ARRAY_TILES_4)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['tiles4']))
    f.seek(ARRAY_TILES_5)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['tiles5']))
    f.seek(ARRAY_TILES_6)
    f.write(struct.pack('%dh' % MAP_SIZE, *map_arrays['tiles6']))
    f.close()

def is_extension(ext):
    return lambda f : f.endswith('.%s' % ext)

trim_extension = lambda f : f[:f.rfind('.')]

def main():
    settings = parse_args()
    if settings.map_to_json == settings.json_to_map:
        fail('Either convert --map-to-json or --json-to-map. Not both or none.')

    if settings.map_to_json:
        filenames = list(map(trim_extension, filter(is_extension('map'), os.listdir(settings.original_maps_dir))))
        has_override = False
        for filename in filenames:
            if os.path.isfile('%s/%s.json' % (settings.editable_maps_dir, filename)):
                print('The file %s/%s.json already exists.' % (settings.editable_maps_dir, filename))
                has_override = True

        if has_override:
            fail('There are editable .json files that would be overwritten! '
                'Please delete them manually before running this again. '
                'We do not automatically override .json files as they may contain unsaved data.')

        for filename in filenames:
            map_to_json(filename, settings)

    elif settings.json_to_map:
        filenames = list(map(trim_extension, filter(is_extension('json'), os.listdir(settings.editable_maps_dir))))
        has_missing_map = False
        for filename in filenames:
            if not os.path.isfile('%s/%s.map' % (settings.original_maps_dir, filename)):
                print('The map %s/%s.map is missing!' % (settings.original_maps_dir, filename))
                has_missing_map = True
        if has_missing_map:
            fail('There are missing maps from %s! We cannot generate map files from the '
                '.json files if the corresponding original .map files are not present.' % settings.original_maps_dir)

        for filename in filenames:
            if os.path.isfile('%s/%s.map' % (settings.final_maps_dir, filename)):
                print('Automatically overriding %s/%s.map.' % (settings.final_maps_dir, filename))

        for filename in filenames:
            json_to_map(filename, settings)



if __name__ == '__main__':
    main()
    if HAS_WARNINGS:
        sys.exit(1)