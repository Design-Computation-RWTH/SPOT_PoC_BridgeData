import os
import json
import mimetypes
from datetime import datetime
from pathlib import Path

from numpy.core.defchararray import capitalize

# general bridge file contains asset definiton and superstructure
bridge_file ="Input/bridge_zones.json"
with Path(bridge_file).open("r", encoding="utf-8") as f:
    bridge_json = json.load(f)


# Helper: Guess dcterms:type from mimetype
def guess_type(mimetype):
    if mimetype:
        if mimetype.startswith("image/"):
            return "image"
        elif mimetype.startswith("text/"):
            return "text"
        elif mimetype.startswith("application/"):
            return mimetype  # e.g., application/pdf
    return "other"

def select_area_class(base_name):
    if ("querschnitt" in base_name.lower()) or ("ansicht" in base_name.lower()) or ("längsschnitt" in base_name.lower()):
        return "VerticalAreaSpace"
    elif ("draufsicht" in base_name.lower()) or ("grundriss" in base_name.lower()) or ("horizontal" in base_name.lower()):
        return "HorizontalAreaSpace"
    else:
        return "AreaSpace"

def add_space_metadata(input_dir, filename, space_dict):
    # metadata
    metadata = dict()
    # Find corresponding resource file (not .json)
    # prefer image files (png, jpg) over PDFs and others
    resource_path = None
    for other in os.listdir(input_dir):
        if other.startswith(filename) and (other.endswith(".png") or other.endswith(".jpg")):
            resource_path = os.path.join(input_dir, other)
            break
        elif other.startswith(filename) and not other.endswith(".json") and not other.endswith(".txt"):
            resource_path = os.path.join(input_dir, other)
            break
    if resource_path:
        metadata["rel_access_url"] = str(os.path.relpath(resource_path, start="Input"))
        metadata["filetype"] = os.path.splitext(resource_path)[1][1:]  # e.g., 'pdf'
        mimetype, _ = mimetypes.guess_type(resource_path)
        metadata["dct_type"] = guess_type(mimetype)

        space_dict["metadata"] = metadata

    else:
        space_dict["metadata"] = metadata


def create_doc_space_dict(name):
    doc_space_dict = \
        {
        "class": "DocumentSpace",
        "name": name,
        "axes_directions":
            {
        "X": "Right",
        "Y": "Bottom"
            }
        }
    return doc_space_dict

def get_axis_dir_in_asset(ref_axis, ref_space_name):
    ref_space = next((obj for obj in bridge_json["entity_spaces"] if obj.get("name") == ref_space_name), None)
    ref_space_asset_apps = ref_space["asset_appearances"]
    ref_space_axes_mappings = ref_space_asset_apps[0]["axis_mappings"]
    for axes_mapping in ref_space_axes_mappings:
        if axes_mapping["source"]["axis"] == ref_axis:
            asset_axis = axes_mapping["target"]["axis"]
            inverse = axes_mapping["target"]["inverse"]

            asset_axis_dir = bridge_json["asset"]["axes_directions"][asset_axis]
            return asset_axis_dir,inverse

def get_asset_axis_dir(asset_axis):
    asset_axis_dir = bridge_json["asset"]["axes_directions"][asset_axis]
    return asset_axis_dir


def derive_reloc_relation_from_norm_coord(parent_dir, coord):
    prop = None
    if coord < 0:
        if parent_dir == "Front":
            prop = "disjointRear"
        if parent_dir == "Rear":
            prop = "disjointFront"
        if parent_dir == "Left":
            prop = "disjointRight"
        if parent_dir == "Right":
            prop = "disjointLeft"
        if parent_dir == "Top":
            prop = "disjointBottom"
        if parent_dir == "Bottom":
            prop = "disjointTop"
    elif 0 < coord <= 0.33:
        if parent_dir == "Front":
            prop = "containedInRear"
        if parent_dir == "Rear":
            prop = "containedInFront"
        if parent_dir == "Left":
            prop = "containedInRight"
        if parent_dir == "Right":
            prop = "containedInLeft"
        if parent_dir == "Top":
            prop = "containedInBottom"
        if parent_dir == "Bottom":
            prop = "containedInTop"
    elif 0.33 < coord <= 0.66:
        if parent_dir == "Front" or parent_dir == "Rear":
            prop = "containedInLongitudinalCenter"
        if parent_dir == "Left" or parent_dir == "Right":
            prop = "containedInTransversalCenter"
        if parent_dir == "Bottom" or parent_dir == "Top":
            prop = "containedInVerticalCenter"
    elif 0.66 < coord <= 1:
        if parent_dir == "Front":
            prop = "containedInFront"
        if parent_dir == "Rear":
            prop = "containedInRear"
        if parent_dir == "Left":
            prop = "containedInLeft"
        if parent_dir == "Right":
            prop = "containedInRight"
        if parent_dir == "Top":
            prop = "containedInTop"
        if parent_dir == "Bottom":
            prop = "containedInBottom"
    elif coord > 1:
        if parent_dir == "Front":
            prop = "disjointFront"
        if parent_dir == "Rear":
            prop = "disjointRear"
        if parent_dir == "Left":
            prop = "disjointLeft"
        if parent_dir == "Right":
            prop = "disjointRight"
        if parent_dir == "Top":
            prop = "disjointTop"
        if parent_dir == "Bottom":
            prop = "disjointBottom"
    return prop

def create_drawing_area_space(name, space_type, doc_ref, coord_dict, doc_directions, bp_accuracy, asset_ref ):
    area_space_dict = {
         "class": space_type,
         "name": name,
         "document_appearances": [],
         "asset_appearances":[],
         "entity_appearances": []
        }
    doc_app = {
        "ref_document": doc_ref,
        "axis_mappings": [],
        "boundary_point_mappings" : []
    }
    #add template document axis mappings (same  axes)
    for axis in ["X", "Y"]:
        axis_mp ={
            "source": {
                "axis": axis
            },
            "target": {
                "object": doc_ref,
                "axis": axis,
                "inverse": False
            },
            "accuracy": "Exact"
        }
        doc_app["axis_mappings"].append(axis_mp)

    for key_axis,value in coord_dict.items(): # bsp: X:{Min: val, Max: val}
        for bound, coord in value.items():
            parent_axis_dir = doc_directions.get(key_axis)
            reloc_rel = derive_reloc_relation_from_norm_coord(parent_axis_dir, coord)

            bp_mp = {
              "source": {
                "axis": key_axis,
                "boundary": bound
              },
              "reloc_relation": reloc_rel,
              "reloc_relation_target": doc_ref,
              "normalized_coordinate": coord,
              "accuracy": bp_accuracy
            }

            doc_app["boundary_point_mappings"].append(bp_mp)

    area_space_dict["document_appearances"].append(doc_app)

    if space_type == "VerticalAreaSpace" or space_type == "HorizontalAreaSpace":
        ass_app = {
            "axis_mappings": [],
            "boundary_point_mappings": []
        }
        vals = {}
        if space_type == "VerticalAreaSpace":
            val1 = {
            "src_axis" : "Y",
            "tgt_axis" : "Z",
            "inv" : True
            }
            vals["val1"] = val1
            if "quer" in name.lower():
                val2 = {
                    "src_axis": "X",
                    "tgt_axis": "Y",
                }
                vals["val2"] = val2
                val3 = {
                    "src_axis": "Z",
                    "tgt_axis": "X",
                }
                vals["val3"] = val3

            elif "längs" in name.lower():
                val2 = {
                    "src_axis": "X",
                    "tgt_axis": "X",
                }
                vals["val2"] = val2
                val3 = {
                    "src_axis": "Z",
                    "tgt_axis": "Y",
                }
                vals["val3"] = val3

        if space_type == "HorizontalAreaSpace":
            val1 = {
                "src_axis": "Z",
                "tgt_axis": "Z",
                "inv": True
            }
            vals["val1"] = val1

        for v in vals.values():
            axis_mp = {
                "source": {
                    "axis": v["src_axis"],
                },
                "target": {
                    "object": asset_ref,
                    "axis": v["tgt_axis"],
                    "inverse": v.get("inv", None)
                },
                "accuracy": "Exact"
            }
            ass_app["axis_mappings"].append(axis_mp)

        area_space_dict["asset_appearances"].append(ass_app)

    return area_space_dict

def normalize_abs_coord(coord, min, max):
    norm_coord = (coord - min) / (max - min)
    return norm_coord

def create_camera_point_space(name, asset_name, orientation_dict, coord_dict, ref_space_boundaries, bp_accuracy):
    point_space_dict = {
        "class": "PointSpace",
        "name": name,
        "document_appearances": [],
        "asset_appearances": [],
        "entity_appearances": [],
    }
    asset_app = {
        "ref_entity": asset_name,
        "axis_mappings": [],
        "boundary_point_mappings": []
    }

    for source_axis, li in orientation_dict.items():
        asset_axis = li[0]
        cosine_angle = li[1]
        angle = abs(cosine_angle)
        # define inverse by sign
        if cosine_angle < 0:
            inverse = True
        else:
            inverse = False
        # define accuracy by angle value
        if angle >= 0.5 and angle <= 0.8:
            acc  = "Broad"
        elif angle > 0.8 and angle <= 0.99:
            acc = "Approximate"
        elif angle > 0.99:
            acc = "Exact"
        else:
            acc = ""

        axis_mp = {
            "source": {
                "axis": source_axis.upper(),
            },
            "target": {
                "object": asset_name,
                "axis": asset_axis.upper(),
                "inverse": inverse
            },
            "angle":angle,
            "accuracy": acc
        }
        asset_app["axis_mappings"].append(axis_mp)

    for asset_axis, coord in coord_dict.items():
        normalized_coord = normalize_abs_coord(coord, ref_space_boundaries[asset_axis]["Min"],
                                               ref_space_boundaries[asset_axis]["Max"])
        print(normalized_coord)
        axis_dir = get_asset_axis_dir(asset_axis)
        print(axis_dir)
        reloc_prop = derive_reloc_relation_from_norm_coord(axis_dir, normalized_coord)
        print(reloc_prop)


        # get related source axis to pcd axis
        source_axis_map = [map for map in asset_app["axis_mappings"] if map["target"]["axis"] == asset_axis]
        source_axis = source_axis_map[0]["source"]["axis"]

        bp_mp = {
            "source": {
                "axis": source_axis,
                "boundary": "BoundaryPoint"
            },
            "reloc_relation_target": asset_name,
            "reloc_relation": reloc_prop,
            "normalized_coordinate": normalized_coord,
            "accuracy": bp_accuracy
        }

        asset_app["boundary_point_mappings"].append(bp_mp)

    point_space_dict["asset_appearances"].append(asset_app)
    return point_space_dict

#war nur angelegt für bridge point cloud space, brauchen wir gerade nicht
def create_volume_space(name, ref_ent_space,axis_mps, bp_extents, volume_coords, acc):
    volume_space_dict = {
        "class": "VolumeSpace",
        "name": name,
        "document_appearances": [],
        "asset_appearances": [],
        "entity_appearances": []
    }

    ent_app = {
        "ref_entity": ref_ent_space,
        "axis_mappings": [],
        "boundary_point_mappings": []
    }

    for src_axis, trgt_axis in axis_mps.items():
        axis_mp = {
            "source": {
                "axis": src_axis,
            },
            "target": {
                "object": ref_ent_space,
                "axis": trgt_axis,
                "inverse": False
            },
            "accuracy": "Exact"
        }
        ent_app["axis_mappings"].append(axis_mp)

        for bound in {"min", "max"}:
            norm_coord = normalize_abs_coord(volume_coords[bound+"_"+str(src_axis.lower())],bp_extents[src_axis]["Min"],bp_extents[src_axis]["Max"])
            asset_dir, inv = get_axis_dir_in_asset(trgt_axis, ref_ent_space)
            if inv == False:
                reloc_rel=derive_reloc_relation_from_norm_coord(asset_dir, norm_coord)
            else:
                # wenn inverse true, richtung umwandeln und doch entity richtungen nutzen?? oder einfach gar keine reloc relation zwischen zwei entity spaces angehen?
                reloc_rel = None
            bp_mp = {
                "source": {
                    "axis": src_axis,
                    "boundary": bound.capitalize()
                },
                "reloc_relation_target": ref_ent_space,
                "reloc_relation": reloc_rel,
                "normalized_coordinate": norm_coord,
                "accuracy": acc
            }
            ent_app["boundary_point_mappings"].append(bp_mp)

    volume_space_dict["entity_appearances"].append(ent_app)
    return volume_space_dict

def create_asset_subSpace(name, asset_name, bp_mps):
    entity_space_dict = {
        "class": "VolumeSpace",
        "name": name,
        "document_appearances": [],
        "asset_appearances": [],
        "entity_appearances": []
    }
    ass_app = {
        "axis_mappings": [],
        "boundary_point_mappings": []
    }
    template_axes_mappings = {"X":"X", "Y":"Y", "Z":"Z"}
    for src, trgt in template_axes_mappings.items():
        axis_mp = {
            "source": {
                "axis": src,
            },
            "target": {
                "object": asset_name,
                "axis": trgt,
                "inverse": False
            },
            "accuracy": "Exact"
        }
        ass_app["axis_mappings"].append(axis_mp)

    for axis, map in bp_mps.items():
        for bp_type, relation in map.items():
            bp_mp = {
                "source": {
                    "axis": axis,
                    "boundary": bp_type
                },
                "reloc_relation_target": relation["tgt"],
                "reloc_relation": relation["rel"],
                "accuracy": "Exact"
            }
            ass_app["boundary_point_mappings"].append(bp_mp)

    entity_space_dict["asset_appearances"].append(ass_app)
    return entity_space_dict

def add_asset_subSpaces(nr_of_spans):
    asset_name = bridge_json["asset"]["name"]
    superStructure_bmp = {
        "X" : {
                "Min":
                    {"rel": "meetFront", "tgt":asset_name},
                "Max":
                    {"rel": "meetRear", "tgt": asset_name}
              },
        "Y": {
                "Min":
                    {"rel": "meetRight", "tgt":asset_name},
                "Max":
                    {"rel": "meetLeft", "tgt": asset_name}
              },
        "Z": {
                "Min":
                    {"rel": "meetTop", "tgt":"SubStructureZone"},
                "Max":
                    {"rel": "meetTop", "tgt": asset_name}
              }
    }
    superZone = create_asset_subSpace("SuperStructureZone",asset_name,superStructure_bmp)
    bridge_json["entity_spaces"].append(superZone)

    subStructure_bmp = {
        "X": {
            "Min":
                {"rel": "meetFront", "tgt": asset_name},
            "Max":
                {"rel": "meetRear", "tgt": asset_name}
        },
        "Y": {
            "Min":
                {"rel": "meetRight", "tgt": asset_name},
            "Max":
                {"rel": "meetLeft", "tgt": asset_name}
        },
        "Z": {
            "Min":
                {"rel": "meetBottom", "tgt": asset_name},
            "Max":
            #containedintop um keinen zirkelschluss mit superstructure zu erzeugen (bei nib brücke norm. wert wäre 0.5-0.75)
                {"rel": "containedInTop", "tgt": asset_name}
        }
    }
    subZone = create_asset_subSpace("SubStructureZone", asset_name, subStructure_bmp)
    bridge_json["entity_spaces"].append(subZone)

    span_count = nr_of_spans
    spans = []
    for i in range(1, span_count + 1):
        print(i)
        span_name = "Span_" + str(i)
        span_bmp = {
            "Y": {
                "Min":
                    {"rel": "meetRight", "tgt": asset_name},
                "Max":
                    {"rel": "meetLeft", "tgt": asset_name}
            },
            "Z": {
                "Min":
                    {"rel": "meetBottom", "tgt": asset_name},
                "Max":
                    {"rel": "meetTop", "tgt": asset_name}
            }
        }
        if i == 1:
            x_map = {
                "Min":
                    {"rel": "meetFront", "tgt": asset_name},
                "Max":
                    {"rel": "meetFront", "tgt": "Span_" + str(i+1)}
            }
            span_bmp["X"] = x_map

        if i > 1 and i < span_count:
            x_map = {
                "Min":
                    {"rel": "meetRear", "tgt": spans[i-2]},
                "Max":
                    {"rel": "meetFront", "tgt": "Span_" + str(i + 1)}
            }
            span_bmp["X"] = x_map

        if i == span_count:
            x_map = {
                "Min":
                    {"rel": "meetRear", "tgt": spans[i - 2]},
                "Max":
                    {"rel": "meetRear", "tgt": asset_name}
            }
            span_bmp["X"] = x_map

        spans.append(span_name)

        span = create_asset_subSpace(span_name, asset_name, span_bmp)
        bridge_json["entity_spaces"].append(span)




def process_input_data(parent_folder_name, all_plans=True, output_filename=None):
    # get Asset Name
    asset_name = bridge_json["asset"]["name"]
    # create AssetSubSpaces
    add_asset_subSpaces(4)

    # first cerate and add  Documents
    plans_dir = os.path.join(parent_folder_name, "Plans")
    if os.path.exists(plans_dir):
        for fname in os.listdir(plans_dir):
            if not fname.endswith(".json"):
                continue
            if not all_plans:
                # nur diese spezifischen Pläne zulassen, sonst überspringen
                if fname not in ("002.json", "6292_202e.json"):
                    continue
            json_path = os.path.join(plans_dir, fname)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("Filename")
            comment = data.get("Plankopf", "")

            doc_space_dict = create_doc_space_dict(name)
            add_space_metadata(plans_dir, name, doc_space_dict)
            doc_space_dict['metadata']['comment'] = comment

            bridge_json["document_spaces"].append(doc_space_dict)


    # AreaSpaces
    singleviews_dir = os.path.join(parent_folder_name, "SingleViews")
    if os.path.exists(singleviews_dir):
        for folder in os.listdir(singleviews_dir): #folder name = reference document name
            print(folder)
            if not all_plans:
                # nur diese Order der spezifischen Pläne zulassen, sonst überspringen
                if folder not in ("002", "6292_202e"):
                    continue
            folder_path = os.path.join(singleviews_dir, folder)
            if os.path.isdir(folder_path):
                for fname in os.listdir(folder_path):
                    if "Vorland" in fname:
                        continue
                    if fname.endswith(".json"):
                        print(fname)
                        json_path = os.path.join(folder_path, fname)
                        with open(json_path, encoding="utf-8") as f:
                            data = json.load(f)
                        # only choose plans with high  confidence
                        conf_bbox = data.get("Confidence View Boundingbox", "")
                        try:
                            conf_val = float(conf_bbox)
                        except Exception:
                            conf_val = 0.0
                        if conf_val <= 0.6:
                            continue

                        bp_acc = None
                        if conf_val >= 0.99:
                            bp_acc = "Exact"
                        elif conf_val >=0.8:
                            bp_acc = "Approximate"
                        elif conf_val >=0.6:
                            bp_acc = "Broad"

                       # get boundary box coordinates
                        bbox_str = data.get("View Boundingbox", "")
                        bbox = None
                        if bbox_str:
                            try:
                                bbox_values = [float(x) for x in bbox_str.split()]
                                cx, cy, w, h = bbox_values
                                xmin = cx - w / 2
                                xmax = cx + w / 2
                                ymin = cy - h / 2
                                ymax = cy + h / 2
                                bbox = {
                                    "X":
                                        { "Min": xmin,
                                          "Max": xmax },
                                    "Y":
                                        { "Min": ymin,
                                          "Max": ymax,}
                                }
                            except Exception:
                                bbox = None

                        base_name = os.path.splitext(fname)[0]
                        title = data.get("View Title", "")
                        name = title.strip().replace(":", "_").replace(".", "_")
                        comment = data.get("Plankopf", "")
                        #derive spot space class from name if possible
                        space_type = select_area_class(name)
                        # get relation to reference space
                        ref_doc= data.get("Filename")
                        ref_doc_entry = [e for e in bridge_json["document_spaces"] if e["name"] == ref_doc]
                        #get directions of ref spaces axes for reloc property derivation
                        ref_doc_directions = ref_doc_entry[0]["axes_directions"]
                        # create area space dict entry
                        area_space_dict = create_drawing_area_space(name, space_type, ref_doc, bbox, ref_doc_directions, bp_acc, bridge_json["asset"]["name"])
                        # add metadata
                        add_space_metadata(folder_path, base_name, area_space_dict)
                        area_space_dict['metadata']['comment'] = comment
                        area_space_dict['metadata']['title'] = title

                        bridge_json["entity_spaces"].append(area_space_dict)

    #Load PointCloud Data
    pcd_path = os.path.join(parent_folder_name, "PointCloud/pcd_meta.json")
    with open(pcd_path, "r", encoding="utf-8") as f:
        pcd_meta = json.load(f)
    # bounding volume of bridge structure in point cloud
    pcd_entry_trim = pcd_meta["point_cloud_volume_trimmed"]
    pcd_trim_boundaries = pcd_entry_trim["boundary_extent"]

    # Load camera parameters
    pictures_dir = os.path.join(parent_folder_name, "Pictures")
    camera_params_path = os.path.join(pictures_dir, "camera_params.json")
    with open(camera_params_path, "r", encoding="utf-8") as f:
        camera_params = json.load(f)

    # Load single picture files
    for fname in os.listdir(pictures_dir):
        print(fname)
        if fname.lower().endswith(".jpg"):
            # find corresponding entry in camera params
            point_space_name = f"Camera_{os.path.splitext(fname)[0]}"
            cam_param = camera_params.get(fname)
            if not cam_param:
                print(f"Warning: No camera parameters found for {fname}")
                continue

            orientation = cam_param.get("orientation", {})
            orientation.pop("x_dir")
            orientation.pop("y_dir")
            orientation.pop("z_dir")

            pic_center_coords = cam_param.get("localization", {}).get("center", None)
            # !!!! Axes refer here to target/ PCD axes, not to camera axes !!!!
            pic_center_coords_dict = {
                "X": pic_center_coords[0],
                "Y": pic_center_coords[1],
                "Z": pic_center_coords[2],
            }

            cam_point_space_dict = create_camera_point_space(point_space_name, asset_name, orientation, pic_center_coords_dict,pcd_trim_boundaries, "Approximate")
            add_space_metadata(pictures_dir, fname, cam_point_space_dict)

            bridge_json["entity_spaces"].append(cam_point_space_dict)



    bridge_json_path = os.path.join("Output/output_json", (output_filename or "Nibelungen_Spaces_Paper")+datetime.now().strftime("%Y%m%d")+".json")
    with open(bridge_json_path, "w", encoding="utf-8") as f:
        json.dump(bridge_json, f, indent=4, ensure_ascii=False)

    return bridge_json_path


