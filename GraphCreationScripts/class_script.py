# python
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD
import os
from datetime import datetime
import json
from pathlib import Path

# Namespaces
SPOT = Namespace("https://w3id.org/spot#")
SPOT_AM = Namespace("https://w3id.org/spot/am#")
RELOC = Namespace("https://w3id.org/reloc#")
EX = Namespace("http://example.org/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCTERMS = Namespace("http://purl.org/dc/terms/")


class URIBuilder:
    def __init__(self, base=EX):
        self.base = base

    def mk(self, label: str) -> URIRef:
        safe = "".join(c if c.isalnum() or c in "-_.~" else "_" for c in label)
        return URIRef(str(self.base) + safe)


class GraphManager:
    def __init__(self):
        self.g = Graph()
        self.g.bind("spot", SPOT)
        self.g.bind("spot-am", SPOT_AM)
        self.g.bind("reloc", RELOC)
        self.g.bind("", EX)
        self.g.bind("rdfs", RDFS)
        self.g.bind("dcat", DCAT)
        self.g.bind("dcterms", DCTERMS)

    def serialize(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.g.serialize(destination=path, format="turtle")


@dataclass
class RDFSubject:
    id: str
    uri_builder: URIBuilder
    uri: URIRef = field(init=False)
    label: Optional[str] = None

    def __post_init__(self):
        self.uri = self.uri_builder.mk(self.id)

    def to_rdf(self, g: Graph):
        if self.label:
            g.add((self.uri, RDFS.label, Literal(self.label)))


@dataclass
class BoundaryPoint(RDFSubject):
    bp_type: URIRef = field(default=SPOT_AM.BoundaryPoint)

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, self.bp_type))


@dataclass
class Axis(RDFSubject):
    direction: Optional[URIRef] = None
    boundary_points: Optional[Dict[str, BoundaryPoint]] = field(default_factory=dict)

    def to_rdf(self, g: Graph):
        super().to_rdf(g)
        g.add((self.uri, RDF.type, SPOT.Axis))
        if self.direction:
            g.add((self.uri, SPOT.hasDirection, self.direction))
        if self.boundary_points:
            for name, bp in self.boundary_points.items():
                bp.to_rdf(g)
                g.add((self.uri, SPOT_AM.hasBoundaryPoint, bp.uri))


@dataclass
class AxisMapping(RDFSubject):
    source_axis: Optional[URIRef] = None
    target_axis: Optional[URIRef] = None
    axis_relation_type: Optional[URIRef] = None
    accuracy: Optional[URIRef] = None
    angle: Optional[str] = None

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT_AM.AxisMapping))
        if self.source_axis:
            g.add((self.uri, SPOT_AM.hasSourceAxis, self.source_axis))
        if self.target_axis:
            g.add((self.uri, SPOT_AM.hasTargetAxis, self.target_axis))
        if self.axis_relation_type:
            g.add((self.uri, SPOT_AM.hasAxisRelationType, self.axis_relation_type))
        if self.accuracy:
            g.add((self.uri, SPOT_AM.hasAccuracy, self.accuracy))


@dataclass
class BoundaryPointMapping(RDFSubject):
    source_point: [URIRef] = None
    reloc_relation: Optional[URIRef] = None
    reloc_relation_target: Optional[URIRef] = None
    normalized_value: Optional[float] = None
    accuracy: Optional[URIRef] = None

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT_AM.BoundaryPointMapping))
        g.add((self.uri, SPOT_AM.hasSourcePoint, self.source_point))
        if self.reloc_relation:
            g.add((self.uri, self.reloc_relation, self.reloc_relation_target))
        if self.accuracy:
            g.add((self.uri, SPOT_AM.hasAccuracy, self.accuracy))


@dataclass
class Appearance(RDFSubject):
    appears_in: [URIRef] = None
    axis_mappings: Optional[List[AxisMapping]] = field(default_factory=list)
    boundary_point_mappings: Optional[List[BoundaryPointMapping]] = field(default_factory=list)

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.Appearance))

    def add_relations(self, g: Graph, source_space):
        g.add((source_space, SPOT.hasSuperSpace, self.appears_in))
        g.add((self.appears_in, SPOT.hasSubspace,source_space ))
        g.add((self.uri, SPOT.appearsIn, self.appears_in))
        if self.axis_mappings:
            for am in self.axis_mappings:
                am.to_rdf(g)
                g.add((self.uri, SPOT_AM.hasAxisMapping, am.uri))
        if self.boundary_point_mappings:
            for bpm in self.boundary_point_mappings:
                bpm.to_rdf(g)
                g.add((self.uri, SPOT_AM.hasBoundaryPointMapping, bpm.uri))


@dataclass
class AssetAppearance(Appearance):
    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.AssetAppearance))
        RDFSubject.to_rdf(self, g)
        #super().add_relations(g,space_uri)


@dataclass
class DocumentAppearance(Appearance):
    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.DocumentAppearance))
        RDFSubject.to_rdf(self, g)
        #super().add_relations(g,space_uri)


@dataclass
class EntityAppearance(Appearance):
    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.EntityAppearance))
        RDFSubject.to_rdf(self, g)
        #super().add_relations(g,space_uri)


@dataclass
class Space:
    """Basisklasse für alle Space-Typen"""
    name: str
    uri_builder: URIBuilder
    uri: URIRef = field(init=False)
    label: Optional[str] = None
    axes: Dict[str, Axis] = field(default_factory=dict)

    def __post_init__(self):
        self.uri = self.uri_builder.mk(self.name)

    def __init__(self, name: str, uri_builder: URIBuilder, space_label: str,
                 axis_names: List[str] = ["X", "Y", "Z"],
                 with_directions: bool = False,
                 boundary_point_config: Optional[Dict[str, str]] = None,
                 metadata: Optional[Dict[str, str]] = None) :
        """
        Initialisiert einen Space mit konfigurierbaren Boundary Points.

        Args:
            name: Name des Space
            uri_builder: URI Builder für RDF URIs
            space_label: Label für den Space
            axis_names: Liste der Achsennamen (Standard: ["X", "Y", "Z"])
            with_directions: Ob Achsenrichtungen gesetzt werden sollen
            boundary_point_config: Dictionary das für jede Achse angibt, welche Art von
                                   Boundary Points erstellt werden sollen.
                                   Mögliche Werte: "min_max", "generic", None
                                   Beispiel: {"X": "min_max", "Y": "min_max", "Z": "generic"}
        """
        self.name = name
        self.uri_builder = uri_builder
        self.uri = uri_builder.mk(name)
        self.label = space_label
        self.metadata = metadata or {}

        # Automatisch Achsen erstellen
        self.axes = {}
        for axis_name in axis_names:
            axis_id = f"{name}_Axis_{axis_name}" #Name_Axis_X
            axis_label = f"{name} {axis_name} Axis"
            axis = Axis(axis_id, uri_builder, label=axis_label)

            # Boundary Points erstellen basierend auf Konfiguration
            if boundary_point_config and axis_name in boundary_point_config:
                bp_type = boundary_point_config[axis_name]

                if bp_type == "min_max":
                    # Min und Max Boundary Points erstellen
                    for bp_type_name, bp_class in [("Min", SPOT_AM.MinBoundaryPoint),
                                                   ("Max", SPOT_AM.MaxBoundaryPoint)]:
                        bp_id = f"{name}_Axis_{axis_name}_{bp_type_name}" #Bspw. Name_Axis_Y_Min
                        bp_label = f"{name} {axis_name} Axis {bp_type_name}"
                        axis.boundary_points[bp_type_name] = BoundaryPoint(
                            bp_id, uri_builder, label=bp_label, bp_type=bp_class
                        )

                elif bp_type == "generic":
                    # Nur einen generischen Boundary Point erstellen
                    bp_id = f"{name}_Axis_{axis_name}_BP"  #Bspw. Name_Axis_Y_BP
                    bp_label = f"{name} {axis_name} Axis Boundary Point"
                    axis.boundary_points["BoundaryPoint"] = BoundaryPoint(
                        bp_id, uri_builder, label=bp_label, bp_type=SPOT_AM.BoundaryPoint
                    )

            self.axes[f"{axis_name}Axis"] = axis

    def set_axis_direction(self, axis_name: str, direction: URIRef):
        """Setzt die Richtung für eine Achse"""
        if f"{axis_name}Axis" in self.axes:
            self.axes[f"{axis_name}Axis"].direction = direction

    def to_rdf(self, g: Graph):
        if self.label:
            g.add((self.uri, RDFS.label, Literal(self.label)))

        if self.metadata:
            if "rel_access_url" in self.metadata:
                g.add((self.uri, DCAT['accessURL'], Literal(self.metadata["rel_access_url"])))
            if "filetype" in self.metadata:
                g.add((self.uri, DCTERMS['format'], Literal(self.metadata["filetype"])))
            if "dct_type" in self.metadata:
                g.add((self.uri, DCTERMS['type'], Literal(self.metadata["dct_type"])))
            if "comment" in self.metadata:
                g.add((self.uri, RDFS.comment, Literal(self.metadata["comment"])))
            if "title" in self.metadata:
                g.add((self.uri, DCTERMS['title'], Literal(self.metadata["title"])))


    def add_axes_relations(self, g: Graph):
        for name, axis in self.axes.items():
            axis.to_rdf(g)
            if "X" in name:
                g.add((self.uri, SPOT.hasXAxis, axis.uri))
            elif "Y" in name:
                g.add((self.uri, SPOT.hasYAxis, axis.uri))
            elif "Z" in name:
                g.add((self.uri, SPOT.hasZAxis, axis.uri))


@dataclass
class AssetSpace(Space):
    def __init__(self, name: str, uri_builder: URIBuilder, metadata: Optional[Dict[str, str]] = None ):
        super().__init__(name, uri_builder,
                         space_label=f"{name} Asset Space",
                         axis_names=["X", "Y", "Z"],
                         with_directions=True,
                         boundary_point_config=None,
                         metadata=metadata)

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.AssetSpace))
        # Nur Achsen hinzufügen, nicht super().to_rdf() aufrufen
        RDFSubject.to_rdf(self, g)
        super().add_axes_relations(g)


@dataclass
class EntitySpace(Space):
    appearances: Optional[List[Appearance]] = field(default_factory=list)

    def __init__(self, name: str, uri_builder: URIBuilder, space_type: str = "Entity Space", metadata: Optional[Dict[str, str]] = None):
        super().__init__(name, uri_builder,
                         space_label=f"{name} {space_type}",
                         axis_names=["X", "Y", "Z"],
                         with_directions=False,
                         boundary_point_config={
                             "X": "min_max",
                             "Y": "min_max",
                             "Z": "min_max"
                         },
                         metadata=metadata)

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.EntitySpace))
        # Nur Achsen und Appearance hinzufügen, nicht super().to_rdf() aufrufen
        RDFSubject.to_rdf(self, g)
        super().to_rdf(g)
        super().add_axes_relations(g)


    def add_appearance_relation(self, g: Graph):
        if len(self.appearances) > 0:
            for appearance in self.appearances:
                appearance.to_rdf(g)
                g.add((self.uri, SPOT.hasAppearance, appearance.uri))
                # Source space an das Appearance weitergeben, damit es Beziehungen (Mappings, appearsIn) setzen kann
                appearance.add_relations(g, self.uri)


@dataclass
class AreaSpace(EntitySpace):
    appearances: Optional[List[Appearance]] = field(default_factory=list)

    def __init__(self, name: str, uri_builder: URIBuilder,metadata: Optional[Dict[str, str]] = None):
        Space.__init__(self, name, uri_builder,
                       space_label=f"{name} Area Space",
                       # wie definieren, was welche achse ist? also x = horizontal achse? oder egal?
                       axis_names=["X", "Y", "Z"],
                       with_directions=False,
                       boundary_point_config={
                           "X": "min_max",
                           "Y": "min_max",
                           "Z": "generic"  # Nur generischer BP für Z-Achse
                       },
                       metadata=metadata
                       )
        self.appearances = []

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.AreaSpace))
        # Nur Achsen und Appearance hinzufügen, nicht EntitySpace Typ
        RDFSubject.to_rdf(self, g)
        Space.to_rdf(self, g)
        super().add_axes_relations(g)
        self.add_appearance_relation(g)



@dataclass
class VerticalAreaSpace(AreaSpace):
    appearances: Optional[List[Appearance]] = field(default_factory=list)

    def __init__(self, name: str, uri_builder: URIBuilder,metadata: Optional[Dict[str, str]] = None):
        Space.__init__(self, name, uri_builder,
                       space_label=f"{name} Vertical Area Space",
                       axis_names=["X", "Y", "Z"],
                       with_directions=False,
                       boundary_point_config={
                           "X": "min_max",
                           "Y": "min_max",
                           "Z": "generic"  # Nur generischer BP für Z-Achse
                       },
                       metadata=metadata)
        self.appearances = []

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.VerticalAreaSpace))
        # Nur Achsen und Appearance hinzufügen, nicht AreaSpace oder EntitySpace Typ
        RDFSubject.to_rdf(self, g)
        Space.to_rdf(self, g)
        super().add_axes_relations(g)
        self.add_appearance_relation(g)


@dataclass
class HorizontalAreaSpace(AreaSpace):
    appearances: Optional[List[Appearance]] = field(default_factory=list)

    def __init__(self, name: str, uri_builder: URIBuilder,metadata: Optional[Dict[str, str]] = None):
        Space.__init__(self, name, uri_builder,
                       space_label=f"{name} Horizontal Area Space",
                       axis_names=["X", "Y", "Z"],
                       with_directions=False,
                       boundary_point_config={
                           "X": "min_max",
                           "Y": "min_max",
                           "Z": "generic"  # Nur generischer BP für Z-Achse
                       },
                       metadata=metadata)
        self.appearances = []

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.HorizontalAreaSpace))
        # Nur Achsen und Appearance hinzufügen, nicht AreaSpace oder EntitySpace Typ
        RDFSubject.to_rdf(self, g)
        Space.to_rdf(self, g)
        super().add_axes_relations(g)
        self.add_appearance_relation(g)


@dataclass
class PointSpace(EntitySpace):
    appearances: Optional[List[Appearance]] = field(default_factory=list)

    def __init__(self, name: str, uri_builder: URIBuilder,metadata: Optional[Dict[str, str]] = None):
        Space.__init__(self, name, uri_builder,
                       space_label=f"{name} Point Area Space",
                       axis_names=["X", "Y", "Z"],
                       with_directions=False,
                       boundary_point_config={
                           "X": "generic",
                           "Y": "generic",
                           "Z": "generic"  # Nur generischer BP für Z-Achse
                       },
                       metadata=metadata)
        self.appearances = []

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.PointSpace))
        # Nur Achsen und Appearance hinzufügen, nicht EntitySpace Typ
        RDFSubject.to_rdf(self, g)
        Space.to_rdf(self, g)
        super().add_axes_relations(g)
        self.add_appearance_relation(g)


@dataclass
class VolumeSpace(EntitySpace):
    appearances: Optional[List[Appearance]] = field(default_factory=list)

    def __init__(self, name: str, uri_builder: URIBuilder,metadata: Optional[Dict[str, str]] = None):
        Space.__init__(self, name, uri_builder,
                       space_label=f"{name} Volume Area Space",
                       axis_names=["X", "Y", "Z"],
                       with_directions=False,
                       boundary_point_config={
                           "X": "min_max",
                           "Y": "min_max",
                           "Z": "min_max"
                       },
                       metadata=metadata)
        self.appearances = []

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.VolumeSpace))
        # Nur Achsen und Appearance hinzufügen, nicht EntitySpace Typ
        RDFSubject.to_rdf(self, g)
        Space.to_rdf(self, g)
        super().add_axes_relations(g)
        self.add_appearance_relation(g)


@dataclass
class DocumentSpace(Space):
    def __init__(self, name: str, uri_builder: URIBuilder,metadata: Optional[Dict[str, str]] = None):
        super().__init__(name, uri_builder,
                         space_label=f"{name} Document Space",
                         axis_names=["X", "Y"],  # Nur X und Y für DocumentSpace
                         with_directions=True,
                         boundary_point_config=None,
                         metadata=metadata)

    def to_rdf(self, g: Graph):
        g.add((self.uri, RDF.type, SPOT.DocumentSpace))
        # Nur Achsen hinzufügen, nicht super().to_rdf() aufrufen
        RDFSubject.to_rdf(self, g)
        Space.to_rdf(self, g)
        super().add_axes_relations(g)


def extract_appearance_details(app_obj, json_appearance, space, objects, uri_builder, name_pre):
    """
    Extrahiert Appearance Details aus JSON und fügt sie zum Appearance Objekt hinzu.

    Args:
        app_obj: Das Appearance Objekt (AssetAppearance, DocumentAppearance, etc.)
        json_appearance: JSON Dictionary mit den Appearance Daten
        space: Der Source Space
        objects: Dictionary aller verfügbaren Spaces/Objekte
        uri_builder: URI Builder für RDF URIs
    """
    # Axis Mappings verarbeiten
    if json_appearance.get("axis_mappings"):
        for axis_mapping in json_appearance["axis_mappings"]:
            src_axis_name = axis_mapping["source"]["axis"]  # z.B. "X"
            src_axis = space.axes[f"{src_axis_name}Axis"]
            trgt_obj = objects[axis_mapping["target"]["object"]]
            trgt_axis = trgt_obj.axes[f"{axis_mapping['target']['axis']}Axis"]
            inverse = axis_mapping.get("target", {}).get("inverse", False)
            angle = axis_mapping.get("angle")
            acc = axis_mapping.get("accuracy")
            if acc == "None":
                acc = None
            else:
                acc = SPOT_AM[acc] if acc else None

            # alle Zielachsen immer via hasTargetAxis, Relationstyp als hasAxisRelationType setzen
            relation_type = SPOT_AM.Codirectional
            if inverse:
                relation_type = SPOT_AM.Antiparallel

            sp_ax_mp = AxisMapping(
                f"{name_pre}_AM_{space.name}_{src_axis_name}", uri_builder,
                source_axis=src_axis.uri,
                target_axis=trgt_axis.uri,
                axis_relation_type=relation_type,
                accuracy=acc,
                angle=angle
            )

            app_obj.axis_mappings.append(sp_ax_mp)

    # Boundary Point Mappings verarbeiten
    if json_appearance.get("boundary_point_mappings"):
        for bp_mapping in json_appearance["boundary_point_mappings"]:
            src_axis_name = bp_mapping["source"]["axis"]
            src_boundary_key = bp_mapping["source"]["boundary"]  # z.B. "Min", "Max", oder "BoundaryPoint"

            # Boundary Point aus der Achse holen
            src_axis = space.axes[f"{src_axis_name}Axis"]

            # Prüfen, ob der angegebene Boundary Point existiert
            if src_boundary_key in src_axis.boundary_points:
                src_point = src_axis.boundary_points[src_boundary_key]
            else:
                print(f"Warning: Boundary point '{src_boundary_key}' not found for axis {src_axis_name}")
                continue

            reloc_rel = None
            reloc_rel_target = None
            bp_accuracy = None
            if "reloc_relation" in bp_mapping:
                reloc_rel = RELOC[bp_mapping["reloc_relation"]]
            if "reloc_relation_target" in bp_mapping:
                try:
                    reloc_rel_target = objects[bp_mapping["reloc_relation_target"]].uri
                except KeyError:
                    print(bp_mapping["reloc_relation_target"], "not in objects list yet")
                    reloc_rel_target = URIRef(EX + bp_mapping["reloc_relation_target"])
            if "accuracy" in bp_mapping:
                bp_accuracy =  bp_mapping["accuracy"]
                if bp_accuracy == "None":
                    bp_accuracy = None
                else:
                    bp_accuracy = SPOT_AM[bp_accuracy]


            norm_value = bp_mapping.get("normalized_coordinate")

            sp_bpm = BoundaryPointMapping(
                f"{name_pre}_BPM_{space.name}_{src_axis_name}_{src_boundary_key}", uri_builder,
                source_point=src_point.uri,
                reloc_relation=reloc_rel,
                reloc_relation_target=reloc_rel_target,
                normalized_value=norm_value,
                accuracy = bp_accuracy
            )

            app_obj.boundary_point_mappings.append(sp_bpm)



def build_and_serialize(input_file, output_filename=None):
    uri_builder = URIBuilder()
    gm = GraphManager()
    deferred_relations: List[tuple[str, Callable]] = []
    objects: Dict[str, object] = {}

    def defer_or_resolve(target_name: str, action: Callable):
        if target_name in objects:
            action(objects[target_name])
        else:
            deferred_relations.append((target_name, action))

    with Path(input_file).open("r", encoding="utf-8") as f:
        bjson = json.load(f)

    uri_builder = URIBuilder()
    gm = GraphManager()

    #asset space erstellen
    asset_entry = bjson["asset"]
    asset = AssetSpace(asset_entry["name"], uri_builder)
    for axis_simple, dir_str in asset_entry["axes_directions"].items():
        asset.set_axis_direction(axis_simple, SPOT[dir_str])
    objects[asset_entry["name"]] = asset

    asset.to_rdf(gm.g)

    #document spaces erstellen
    for doc in bjson["document_spaces"]:
        doc_metadata = doc.get("metadata", {})
        doc_space = DocumentSpace(doc["name"], uri_builder, metadata=doc_metadata)
        for axis_simple, dir_str in doc["axes_directions"].items():
            doc_space.set_axis_direction(axis_simple, SPOT[dir_str])
        objects[doc["name"]] = doc_space

        doc_space.to_rdf(gm.g)

     #entity spaces erstellen
    for obj in bjson["entity_spaces"]:
        print(obj)
        obj_class = obj["class"]
        obj_name = obj["name"]
        obj_metadata = obj.get("metadata", {})

        if obj_class == "EntitySpace":
            sp = EntitySpace(obj_name, uri_builder,metadata=obj_metadata)
        elif obj_class == "AreaSpace":
            sp = AreaSpace(obj_name, uri_builder,metadata=obj_metadata)
        elif obj_class == "VerticalAreaSpace":
            sp = VerticalAreaSpace(obj_name, uri_builder,metadata=obj_metadata)
        elif obj_class == "HorizontalAreaSpace":
            sp = HorizontalAreaSpace(obj_name, uri_builder,metadata=obj_metadata)
        elif obj_class == "VolumeSpace":
            sp = VolumeSpace(obj_name, uri_builder,metadata=obj_metadata)
        elif obj_class == "PointSpace":
            sp = PointSpace(obj_name, uri_builder,metadata=obj_metadata)
        else:
            print(f"Unbekannte Space-Klasse: {obj_class}")
            continue

        objects[obj_name] = sp

        if len(obj["asset_appearances"]) > 0:
            for ass_ap in obj["asset_appearances"]:
                nr = obj["asset_appearances"].index(ass_ap)
                name_pre = "AssetAP_"+str(nr)
                sp_ass_ap_id = f"{name_pre}_{sp.name}_in_{asset.name}"
                sp_ass_ap_label = f"Appearance {nr} of {sp.name} in {asset.name}"
                sp_ass_ap = AssetAppearance(sp_ass_ap_id, uri_builder, appears_in=asset.uri,
                                            label=sp_ass_ap_label)

                extract_appearance_details(sp_ass_ap,ass_ap,sp,objects,uri_builder,name_pre)
                sp.appearances.append(sp_ass_ap)

        if len(obj.get("document_appearances", [])) > 0:
            for doc_ap in obj["document_appearances"]:
                nr = obj["document_appearances"].index(doc_ap)
                name_pre = "DocumentAP_" + str(nr)
                ref_name = doc_ap["ref_document"]

                def create_doc_ap(resolved_doc, nr=nr, name_pre=name_pre, doc_ap=doc_ap, sp=sp,
                                  uri_builder=uri_builder):
                    sp_doc_ap_id = f"{name_pre}_{sp.name}_in_{resolved_doc.name}"
                    sp_doc_ap_label = f"Appearance {nr} of {sp.name} in {resolved_doc.name}"
                    sp_doc_ap = DocumentAppearance(sp_doc_ap_id, uri_builder, label=sp_doc_ap_label,
                                                   appears_in=resolved_doc.uri)
                    extract_appearance_details(sp_doc_ap, doc_ap, sp, objects, uri_builder, name_pre)
                    sp.appearances.append(sp_doc_ap)

                defer_or_resolve(ref_name, create_doc_ap)

        if len(obj.get("entity_appearances", [])) > 0:
            for ent_ap in obj["entity_appearances"]:
                nr = obj["entity_appearances"].index(ent_ap)
                name_pre = "EntityAP_" + str(nr)
                ref_name = ent_ap["ref_entity"]

                def create_ent_ap(resolved_ent, nr=nr, name_pre=name_pre, ent_ap=ent_ap, sp=sp,
                                  uri_builder=uri_builder):
                    sp_ent_ap_id = f"{name_pre}_{sp.name}_in_{resolved_ent.name}"
                    sp_ent_ap_label = f"Appearance {nr} of {sp.name} in {resolved_ent.name}"
                    sp_ent_ap = EntityAppearance(sp_ent_ap_id, uri_builder, label=sp_ent_ap_label,
                                                 appears_in=resolved_ent.uri)
                    extract_appearance_details(sp_ent_ap, ent_ap, sp, objects, uri_builder, name_pre)
                    sp.appearances.append(sp_ent_ap)

                defer_or_resolve(ref_name, create_ent_ap)

    for target_name, action in deferred_relations:
        if target_name in objects:
            action(objects[target_name])
        else:
            print("Warning: deferred target was never created.", target_name)

    for sp in objects.values():
        sp.to_rdf(gm.g)

    out_path = "output/ClassScript_Instance_" + (output_filename or "Paper") + datetime.now().strftime("%Y%m%d") + ".ttl"
    gm.serialize(out_path)
    return out_path

if __name__ == "__main__":
    input_file = "output/output_json/nibelungen_spaces.json"
    build_and_serialize(input_file)