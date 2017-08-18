import shutil
import struct
import json
import os
import sys

DIR_ORIGINAL_MAPS = './s1_original_maps'
DIR_EDITABLE_MAPS = './s2_editable_maps'
DIR_FINAL_MAPS = './s3_final_maps'

MAP_SIZE = 100000
MINIMAP_SIZE = 450

ARRAY_MAP = 0
ARRAY_EVENT = 200000
ARRAY_ROOMTYPE = 400000
ARRAY_ROOMCOLOR = 400900
ARRAY_ROOMBG = 401800
ARRAY_ITEMS = 402700
ARRAY_TILES_0 = 602704
ARRAY_TILES_1 = 802704
ARRAY_TILES_2 = 1002704
ARRAY_TILES_3 = 1202704
ARRAY_TILES_4 = 1402704
ARRAY_TILES_5 = 1602704
ARRAY_TILES_6 = 1802704

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


def collision_layer_to_data(layer_data, firstgid):
    def rev_idmap(i):
        if i == 0: return 0
        x = i & 0x0000FFFF
        return 0 if x == 0 else x - firstgid

    return transpose_l2d([rev_idmap(i) for i in layer_data['data']])

def object_layer_to_data(layer_data):
    data = [0]*MAP_SIZE

    for item in layer_data['objects']:
        value = int(item['name'])
        index = item['x']//32 * 200 + item['y']//32
        data[index] = value

    return data

def tile_layer_to_data(layer_data, firstgid):
    def rev_idmap(i):
        if i == 0: return 0
        dataid = (i-firstgid) & 0x0000FFFF
        dataid += 2*(dataid//30)
        if i & 0x40000000 != 0: dataid += 5000
        if i & 0x80000000 != 0: dataid = -dataid
        return dataid
    return transpose_l2d([rev_idmap(i) for i in layer_data['data']])

def minimap_layer_to_data(layer_data):
    data = [0]*MINIMAP_SIZE

    for item in layer_data['objects']:
        value = int(item['name'])
        x = item['x']//640
        y = item['y']//32
        y = 4*(y//45) + max(0,y%45-1)//11
        index = x*18 + y
        data[index] = value

    return data

def map_to_json(filename):
    print('Converting Original map file -> Json : %s' % filename)
    # location of source map file
    sourcefile = "%s/%s.map" % (DIR_ORIGINAL_MAPS, filename)
    targetfile = "%s/%s.json" % (DIR_EDITABLE_MAPS, filename)
    
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
    f.close()

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
             "source":"TILE_A.tsx"
            }, 
            {
             "firstgid":COLLISION_TILESET_OFFSET,
             "source":"collision.tsx"
            }],
        "type":"map",
        "version":1,
        "layers": layers,
    }

    f = open(targetfile, 'w+')
    f.write(json.dumps(data))
    f.close()

def json_to_map(filename):
    print('Converting Json -> Final map file : %s' % filename)
    # location of source map file
    basemapfile = "%s/%s.map" % (DIR_ORIGINAL_MAPS, filename)
    sourcefile = "%s/%s.json" % (DIR_EDITABLE_MAPS, filename)
    targetfile = "%s/%s.map" % (DIR_FINAL_MAPS, filename)
    shutil.copyfile(basemapfile, targetfile)

    f = open(sourcefile)
    jsondata = json.loads(f.read())
    f.close()

    for tileset in jsondata['tilesets']:
        if 'TILE_A' in tileset['source']:
            GID_TILES = tileset['firstgid']
        if 'collision' in tileset['source']:
            GID_COLLISION = tileset['firstgid']

    layers = jsondata['layers']
    layers = dict((layer['name'], layer) for layer in layers)

    map_arrays = {
        "collision": collision_layer_to_data(layers["collision"], GID_COLLISION),
        "event": object_layer_to_data(layers["event"]),
        "items": object_layer_to_data(layers["items"]),
        "roomtype": minimap_layer_to_data(layers["roomtype"]) if "roomtype" in layers else None,
        "roomcolor": minimap_layer_to_data(layers["roomcolor"]) if "roomcolor" in layers else None,
        "roombg": minimap_layer_to_data(layers["roombg"]) if "roombg" in layers else None,
        "tiles0": tile_layer_to_data(layers["tiles0"], GID_TILES),
        "tiles3": tile_layer_to_data(layers["tiles3"], GID_TILES),
        "tiles4": tile_layer_to_data(layers["tiles4"], GID_TILES),
        "tiles1": tile_layer_to_data(layers["tiles1"], GID_TILES),
        "tiles5": tile_layer_to_data(layers["tiles5"], GID_TILES),
        "tiles6": tile_layer_to_data(layers["tiles6"], GID_TILES),
        "tiles2": tile_layer_to_data(layers["tiles2"], GID_TILES),
    }

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
    if len(sys.argv) <= 1: return
    if sys.argv[1] == 'map_to_json':
        filenames = list(map(trim_extension, filter(is_extension('map'), os.listdir(DIR_ORIGINAL_MAPS))))
        has_override = False
        for filename in filenames:
            if os.path.isfile('%s/%s.json' % (DIR_EDITABLE_MAPS, filename)):
                print('The file %s/%s.json already exists.' % (DIR_EDITABLE_MAPS, filename))
                has_override = True

        if has_override:
            print('There are editable .json files that would be overwritten! '
                'Please delete them manually before running this again. '
                'We do not automatically override .json files as they may contain unsaved data.')
            quit()

        for filename in filenames:
            map_to_json(filename)

    elif sys.argv[1] == 'json_to_map':
        filenames = list(map(trim_extension, filter(is_extension('json'), os.listdir(DIR_EDITABLE_MAPS))))
        has_missing_map = False
        for filename in filenames:
            if not os.path.isfile('%s/%s.map' % (DIR_ORIGINAL_MAPS, filename)):
                print('The map %s/%s.map is missing!' % (DIR_ORIGINAL_MAPS, filename))
                has_missing_map = True
        if has_missing_map:
            print('There are missing maps from %s! We cannot generate map files from the '
                '.json files if the corresponding original .map files are not present.' % DIR_ORIGINAL_MAPS)
            quit()

        for filename in filenames:
            if os.path.isfile('%s/%s.map' % (DIR_FINAL_MAPS, filename)):
                print('Automatically overriding %s/%s.map.' % (DIR_FINAL_MAPS, filename))

        for filename in filenames:
            json_to_map(filename)



if __name__ == '__main__':
    main()