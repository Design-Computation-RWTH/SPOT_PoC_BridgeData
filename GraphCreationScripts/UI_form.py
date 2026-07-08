# -*- coding: utf-8 -*-
# SPOT Editor - Tkinter GUI (Windows 11, Python 3.9.7)
# Lädt JSON aus Datei und schreibt Änderungen zurück in dieselbe Datei.
# Am Layout der Mock-ups orientiert.

import json
import copy
import os
import re
import tempfile
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import argparse
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

#relations from reloc direct ziehen (eqaul..)
RELATIONS = [
    "meetFront", "meetRear", "meetRight", "meetLeft", "meetTop", "meetBottom",
    "containedInLeft", "containedInRight", "containedInTop", "containedInBottom","containedInFront", "containedInRear",
    "containedInTransversalCenter", "containedInVerticalCenter", "containedInLongitudinalCenter",
    "disjointFront", "disjointRear", "disjointRight", "disjointLeft", "disjointTop", "disjointBottom"
]

SPACE_CLASSES = ["EntitySpace","VolumeSpace", "HorizontalAreaSpace", "VerticalAreaSpace", "PointSpace", "DocumentSpace"]
AXES = ["X", "Y", "Z"]
BOUNDARIES = ["Min", "Max", "BoundaryPoint"]
ACCURACY = ["Exact", "Approximate", "Broad", "None"]


class SpotEditorApp:
    def __init__(self, root, input_path: str):
        self.root = root
        self.root.title("SPOT Editor")
        self.input_path = str(Path(input_path))
        self.data = self.load_json_file()
        #self.base_dir = Path(self.input_path).resolve().parent
        self.input_dir = "Input"  # Prefix "Input\"

        # Current (links) + Reference (rechts) Preview-States
        self.cur_preview_current_path = None
        self.cur_preview_original_image = None
        self.cur_preview_image_tk = None
        self.cur_preview_path_var = None  # wird im UI angelegt

        self.ref_preview_current_path = None
        self.ref_preview_original_image = None
        self.ref_preview_image_tk = None
        self.ref_preview_path_var = None  # wird im UI angelegt

        self.asset_name = self.data.get("asset", {}).get("name")
        self.refresh_space_lists()

        # Auswahl des zu bearbeitenden Space (Dokument oder Entity)
        default_space = self.editable_space_names[0] if self.editable_space_names else ""
        self.current_space_name = tk.StringVar(value=default_space)
        self.entity_appearance_var = tk.StringVar(value="")
        self.entity_appearance_name_var = tk.StringVar(value="")
        self.entity_appearance_copy_var = tk.BooleanVar(value=True)
        self.asset_appearance_var = tk.StringVar(value="")
        self.asset_appearance_name_var = tk.StringVar(value="")
        self.asset_appearance_copy_var = tk.BooleanVar(value=True)

        self.notebook = ttk.Notebook(self.root)
        self.frame_basics = ttk.Frame(self.notebook)
        self.frame_appearance = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_basics, text="Basics")
        self.notebook.add(self.frame_appearance, text="Appearance")
        self.notebook.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value=f"Datei: {self.input_path}")

        self.build_basics_tab()
        self.build_appearance_tab()
        self.build_status_bar()

        self.set_current_space(self.current_space_name.get())
        self.selected_axis_index = None
        self.selected_bnd_index = None

        self.exit_status = "closed"  # default: if user clicks the window X

    # ---------- Datei-Handling ----------
    def load_json_file(self):
        p = Path(self.input_path)
        if not p.exists():
            messagebox.showwarning("Hinweis", f"Datei nicht gefunden:\n{p}\nEs wird eine leere Struktur erzeugt.")
            data = {"asset": {}, "document_spaces": [], "entity_spaces": []}
        else:
            try:
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                messagebox.showerror("Fehler", f"JSON konnte nicht geladen werden:\n{e}\nEs wird eine leere Struktur erzeugt.")
                data = {"asset": {}, "document_spaces": [], "entity_spaces": []}
        # Mindeststruktur sicherstellen
        data.setdefault("asset", {})
        data.setdefault("document_spaces", [])
        data.setdefault("entity_spaces", [])
        return data

    def persist_json(self, show_toast=True):
        try:
            orig = Path(self.input_path)
            tmp = orig.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            if orig.exists():
                backup = orig.with_suffix(".bak")
                try:
                    shutil.copy2(orig, backup)
                except Exception:
                    # Backup optional, Fehler hier nicht kritisch
                    pass
            os.replace(str(tmp), str(orig))  # atomisch auf Windows
            self.status_var.set(f"Gespeichert: {self.input_path}")
            if show_toast:
                messagebox.showinfo("Gespeichert", f"Änderungen in Datei geschrieben:\n{self.input_path}")
        except Exception as e:
            messagebox.showerror("Speicherfehler", f"Schreiben fehlgeschlagen:\n{e}")

    # ---------- Hilfsfunktionen ----------
    def refresh_space_lists(self):
        self.document_names = [doc.get("name") for doc in self.data.get("document_spaces", []) if doc.get("name")]
        self.entity_names = [ent.get("name") for ent in self.data.get("entity_spaces", []) if ent.get("name")]
        self.reference_space_names = []
        if self.asset_name:
            self.reference_space_names.append(self.asset_name)
        self.reference_space_names.extend(self.document_names)
        self.reference_space_names.extend(self.entity_names)
        self.editable_space_names = self.document_names + self.entity_names

    def start_new_space(self):
        """
        Setzt das Formular in den Neuanlage-Modus:
        Felder werden geleert, History deaktiviert, bis 'Submit' ausgeführt wurde.
        """
        self.current_space = None
        self.current_space_name.set("")  # Combobox leeren
        self.space_name_var.set("")  # Name-Feld leeren
        self.space_class_var.set("")  # Klasse-Feld leeren (oder Default setzen)
        # Optional: Default-Klasse vorwählen
        # self.space_class_var.set("VolumeSpace")

        # Hinweis im Status (history removed)
        self.status_var.set("Neuen Space anlegen – Name und Space Class wählen, dann Submit.")

    def find_space(self, name):
        if not name:
            return None
        if self.asset_name == name:
            return self.data.get("asset")
        for doc in self.data.get("document_spaces", []):
            if doc.get("name") == name:
                return doc
        for ent in self.data.get("entity_spaces", []):
            if ent.get("name") == name:
                return ent
        return None

    def space_kind(self, space):
        if not space:
            return None
        if space is self.data.get("asset"):
            return "asset"
        if space in self.data.get("document_spaces", []):
            return "document"
        return "entity"

    def get_axes_directions(self, ref_name):
        space = self.find_space(ref_name)
        if not space:
            return None
        return space.get("axes_directions")

    def get_or_create_appearance(self, current_space, ref_name, create_if_missing=True):
        if not current_space or not ref_name:
            return None
        ref_space = self.find_space(ref_name)
        ref_type = self.space_kind(ref_space)
        if ref_type == "asset":
            current_space.setdefault("asset_appearances", [])
            apps = [app for app in current_space["asset_appearances"] if app.get("ref_asset", ref_name) == ref_name]
            selected_idx = self.get_selected_asset_appearance_index()
            if apps:
                if 0 <= selected_idx < len(apps):
                    return apps[selected_idx]
                return apps[0]
            if not create_if_missing:
                return None
            app = {"ref_asset": ref_name, "name": "Appearance", "axis_mappings": [], "boundary_point_mappings": []}
            current_space["asset_appearances"].append(app)
            return app
        elif ref_type == "document":
            current_space.setdefault("document_appearances", [])
            for app in current_space["document_appearances"]:
                if app.get("ref_document") == ref_name:
                    return app
            if not create_if_missing:
                return None
            app = {"ref_document": ref_name, "axis_mappings": [], "boundary_point_mappings": []}
            current_space["document_appearances"].append(app)
            return app
        elif ref_type == "entity":
            current_space.setdefault("entity_appearances", [])
            apps = [app for app in current_space["entity_appearances"] if app.get("ref_entity") == ref_name]
            selected_idx = self.get_selected_entity_appearance_index()
            if apps:
                if 0 <= selected_idx < len(apps):
                    return apps[selected_idx]
                return apps[0]
            if not create_if_missing:
                return None
            app = {"ref_entity": ref_name, "axis_mappings": [], "boundary_point_mappings": []}
            current_space["entity_appearances"].append(app)
            return app
        else:
            return None

    def current_appearance(self, create_if_missing=False):
        """Appearance-Container für aktuellen Space + ausgewählten Reference Space holen."""
        if not self.current_space:
            return None
        ref_name = self.reference_space_var.get().strip()
        if not ref_name:
            return None
        return self.get_or_create_appearance(self.current_space, ref_name, create_if_missing=create_if_missing)

    def set_current_space(self, name):
        self.current_space = self.find_space(name)
        # Basics aktualisieren
        if self.current_space and self.space_kind(self.current_space) != "asset":
            self.space_name_var.set(self.current_space.get("name", ""))
            self.space_class_var.set(self.current_space.get("class", ""))
        else:
            self.space_name_var.set("")
            self.space_class_var.set("")
        # Reference-Liste
        self.refresh_space_lists()
        self.reference_space_combo["values"] = self.reference_space_names
        self.relation_target_combo["values"] = self.reference_space_names
        if self.reference_space_names:
            self.reference_space_var.set(self.reference_space_names[0])
            self.relation_target_var.set(self.reference_space_names[0])
        else:
            self.reference_space_var.set("")
            self.relation_target_var.set("")
        self.refresh_appearance_selector()
        self.refresh_existing_appearances_box()
        self.update_reference_info()
        self.update_history_box()
        self.refresh_axis_tree()
        self.refresh_bnd_tree()
        self.update_dual_preview()  # <<< Vorschau aktualisieren

    def get_entity_appearances_for_reference(self, current_space=None, ref_name=None):
        current_space = current_space or self.current_space
        ref_name = (ref_name if ref_name is not None else self.reference_space_var.get()).strip()
        if not current_space or not ref_name:
            return []
        return [app for app in current_space.get("entity_appearances", []) if app.get("ref_entity") == ref_name]

    def get_asset_appearances(self, current_space=None, ref_name=None):
        current_space = current_space or self.current_space
        if not current_space:
            return []
        ref_name = (ref_name if ref_name is not None else self.reference_space_var.get()).strip()
        return [app for app in current_space.get("asset_appearances", []) if app.get("ref_asset", ref_name) == ref_name]

    def get_selected_index_from_value(self, value):
        match = re.match(r"^(\d+)\s*:", (value or "").strip())
        if match:
            try:
                return max(0, int(match.group(1)) - 1)
            except ValueError:
                return 0
        return 0

    def get_selected_entity_appearance_index(self):
        return self.get_selected_index_from_value(self.entity_appearance_var.get())

    def get_selected_asset_appearance_index(self):
        return self.get_selected_index_from_value(self.asset_appearance_var.get())

    def refresh_appearance_selector(self):
        if not hasattr(self, "appearance_frame"):
            return
        current_space = self.current_space
        ref_name = self.reference_space_var.get().strip() if hasattr(self, "reference_space_var") else ""
        ref_space = self.find_space(ref_name) if ref_name else None
        is_entity_space = bool(current_space) and self.space_kind(current_space) == "entity"
        ref_type = self.space_kind(ref_space)

        if not is_entity_space or ref_type not in ("asset", "entity"):
            self.appearance_frame.grid_remove()
            self.asset_appearance_var.set("")
            self.asset_appearance_name_var.set("")
            self.entity_appearance_var.set("")
            self.entity_appearance_name_var.set("")
            self.asset_appearance_combo["values"] = []
            self.entity_appearance_combo["values"] = []
            self.asset_appearance_combo.configure(state="disabled")
            self.entity_appearance_combo.configure(state="disabled")
            self.asset_appearance_name_entry.configure(state="disabled")
            self.entity_appearance_name_entry.configure(state="disabled")
            self.asset_appearance_create_btn.configure(state="disabled")
            self.entity_appearance_create_btn.configure(state="disabled")
            self.existing_appearances_visible.set(False)
            self.existing_appearances_toggle_btn.configure(state="disabled")
            self.existing_appearances_body.grid_remove()
            return

        self.appearance_frame.grid()
        self.existing_appearances_toggle_btn.configure(state="normal")
        if ref_type == "asset":
            self.asset_appearance_frame.grid()
            self.entity_appearance_frame.grid_remove()
            apps = self.get_asset_appearances(current_space, ref_name)
            values = []
            for i, app in enumerate(apps, 1):
                label = app.get("name") or "Appearance"
                values.append(f"{i}: {label}")
            self.asset_appearance_combo.configure(state="readonly")
            self.asset_appearance_name_entry.configure(state="normal")
            self.asset_appearance_create_btn.configure(state="normal")
            self.asset_appearance_combo["values"] = values
            if values:
                current = self.asset_appearance_var.get().strip()
                if current not in values:
                    self.asset_appearance_var.set(values[0])
            else:
                self.asset_appearance_var.set("")
        else:
            self.asset_appearance_frame.grid_remove()
            self.entity_appearance_frame.grid()
            apps = self.get_entity_appearances_for_reference(current_space, ref_name)
            values = []
            for i, app in enumerate(apps, 1):
                label = app.get("name") or "Appearance"
                values.append(f"{i}: {label}")
            self.entity_appearance_combo.configure(state="readonly")
            self.entity_appearance_name_entry.configure(state="normal")
            self.entity_appearance_create_btn.configure(state="normal")
            self.entity_appearance_combo["values"] = values
            if values:
                current = self.entity_appearance_var.get().strip()
                if current not in values:
                    self.entity_appearance_var.set(values[0])
            else:
                self.entity_appearance_var.set("")
        self.refresh_existing_appearances_box()

    def on_entity_appearance_selected(self, event=None):
        self.selected_axis_index = None
        self.selected_bnd_index = None
        self.refresh_existing_appearances_box()

    def on_asset_appearance_selected(self, event=None):
        self.selected_axis_index = None
        self.selected_bnd_index = None
        self.refresh_existing_appearances_box()

    def create_asset_appearance(self):
        if not self.current_space or self.space_kind(self.current_space) != "entity":
            messagebox.showwarning("Hinweis", "Bitte einen Entity-Space auswählen.")
            return
        ref_name = self.reference_space_var.get().strip()
        ref_space = self.find_space(ref_name) if ref_name else None
        if self.space_kind(ref_space) != "asset":
            messagebox.showwarning("Hinweis", "Bitte einen Asset Reference Space auswählen.")
            return

        new_app_name = self.asset_appearance_name_var.get().strip() or "Appearance"
        new_app = {"ref_asset": ref_name, "name": new_app_name, "axis_mappings": [], "boundary_point_mappings": []}
        if self.asset_appearance_copy_var.get():
            src_app = self.get_or_create_appearance(self.current_space, ref_name, create_if_missing=False)
            if src_app:
                new_app["axis_mappings"] = copy.deepcopy(src_app.get("axis_mappings", []))
                new_app["boundary_point_mappings"] = copy.deepcopy(src_app.get("boundary_point_mappings", []))
        self.current_space.setdefault("asset_appearances", []).append(new_app)
        self.refresh_appearance_selector()
        apps = self.get_asset_appearances(ref_name=ref_name)
        self.asset_appearance_var.set(f"{len(apps)}: {new_app_name}")
        self.asset_appearance_name_var.set("")
        self.persist_json(show_toast=False)
        self.refresh_existing_appearances_box()
        messagebox.showinfo("OK", "Neue Asset Appearance erstellt.")

    def create_entity_appearance(self):
        if not self.current_space or self.space_kind(self.current_space) != "entity":
            messagebox.showwarning("Hinweis", "Bitte einen Entity-Space auswählen.")
            return
        ref_name = self.reference_space_var.get().strip()
        ref_space = self.find_space(ref_name) if ref_name else None
        if not ref_name or self.space_kind(ref_space) != "entity":
            messagebox.showwarning("Hinweis", "Bitte einen Entity Reference Space auswählen.")
            return

        new_app_name = self.entity_appearance_name_var.get().strip() or "Appearance"
        new_app = {"ref_entity": ref_name, "name": new_app_name, "axis_mappings": [], "boundary_point_mappings": []}
        if self.entity_appearance_copy_var.get():
            src_app = self.get_or_create_appearance(self.current_space, ref_name, create_if_missing=False)
            if src_app:
                new_app["axis_mappings"] = copy.deepcopy(src_app.get("axis_mappings", []))
                new_app["boundary_point_mappings"] = copy.deepcopy(src_app.get("boundary_point_mappings", []))
        self.current_space.setdefault("entity_appearances", []).append(new_app)
        self.refresh_appearance_selector()
        apps = self.get_entity_appearances_for_reference()
        self.entity_appearance_var.set(f"{len(apps)}: {new_app_name}")
        self.entity_appearance_name_var.set("")
        self.persist_json(show_toast=False)
        self.refresh_existing_appearances_box()
        messagebox.showinfo("OK", "Neue Entity Appearance erstellt.")

    def toggle_existing_appearances_panel(self):
        if not hasattr(self, "existing_appearances_body"):
            return
        if self.existing_appearances_visible.get():
            self.existing_appearances_body.grid()
            self.existing_appearances_toggle_btn.configure(text="Hide Existing Mappings")
        else:
            self.existing_appearances_body.grid_remove()
            self.existing_appearances_toggle_btn.configure(text="Show Existing Mappings")

    def refresh_existing_appearances_box(self):
        if not hasattr(self, "axis_tree") or not hasattr(self, "bnd_tree"):
            return
        self.refresh_axis_tree()
        self.refresh_bnd_tree()

    def get_rel_access_url_candidate(self):
        """Bevorzugt die Datei des Reference Space; wenn dort keine vorhanden,
        nimmt die des aktuell bearbeiteten Space."""
        # 1) Reference Space
        ref_name = self.reference_space_var.get().strip() if hasattr(self, "reference_space_var") else ""
        ref_space = self.find_space(ref_name) if ref_name else None
        if ref_space:
            rel = ref_space.get("metadata", {}).get("rel_access_url")
            if rel:
                return rel, ref_space

        # 2) Bearbeiteter Space
        if self.current_space:
            rel2 = self.current_space.get("metadata", {}).get("rel_access_url")
            if rel2:
                return rel2, self.current_space

        return None, None

    def open_preview_file(self):
        """Öffnet die Vorschau-Datei mit der Standardanwendung (Windows)."""
        p = self.preview_current_path
        if not p or not os.path.exists(p):
            messagebox.showwarning("Hinweis", "Keine Datei vorhanden.")
            return
        try:
            os.startfile(p)  # Windows-spezifisch
        except Exception as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geöffnet werden:\n{e}")

    def refresh_axis_tree(self):
        if not hasattr(self, "axis_tree"):
            return
        self.axis_tree.delete(*self.axis_tree.get_children())
        app = self.current_appearance(create_if_missing=False)
        if not app:
            return
        for idx, m in enumerate(app.get("axis_mappings", [])):
            self.axis_tree.insert("", "end", iid=str(idx), values=(
                idx + 1,
                m.get("source", {}).get("axis", ""),
                m.get("target", {}).get("axis", ""),
                str(m.get("target", {}).get("inverse", False)),
                m.get("accuracy", "")
            ))

    def refresh_bnd_tree(self):
        if not hasattr(self, "bnd_tree"):
            return
        self.bnd_tree.delete(*self.bnd_tree.get_children())
        app = self.current_appearance(create_if_missing=False)
        if not app:
            return
        for idx, m in enumerate(app.get("boundary_point_mappings", [])):
            src = m.get("source", {})
            self.bnd_tree.insert("", "end", iid=str(idx), values=(
                idx + 1,
                src.get("axis", ""),
                src.get("boundary", ""),
                m.get("reloc_relation", ""),
                m.get("reloc_relation_target", ""),
                m.get("accuracy", "")
            ))

    def on_axis_select(self, event=None):
        if not hasattr(self, "axis_tree"):
            return
        sel = self.axis_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.selected_axis_index = idx
        app = self.current_appearance(create_if_missing=False)
        if not app:
            return
        m = app.get("axis_mappings", [])[idx]
        # Formular vorbelegen
        self.src_axis_var.set(m.get("source", {}).get("axis", "X"))
        self.tgt_axis_var.set(m.get("target", {}).get("axis", "X"))
        self.inverse_var.set(bool(m.get("target", {}).get("inverse", False)))
        self.acc_axis_var.set(m.get("accuracy", "None"))

    def on_bnd_select(self, event=None):
        if not hasattr(self, "bnd_tree"):
            return
        sel = self.bnd_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.selected_bnd_index = idx
        app = self.current_appearance(create_if_missing=False)
        if not app:
            return
        m = app.get("boundary_point_mappings", [])[idx]
        src = m.get("source", {})
        self.bsrc_axis_var.set(src.get("axis", "X"))
        self.boundary_var.set(src.get("boundary", "Min"))
        self.relation_var.set(m.get("reloc_relation", ""))
        self.relation_target_var.set(m.get("reloc_relation_target", self.asset_name or ""))
        self.acc_bnd_var.set(m.get("accuracy", "None"))

    def clear_axis_form(self):
        self.selected_axis_index = None
        self.src_axis_var.set("")
        self.tgt_axis_var.set("")
        self.inverse_var.set(False)
        self.acc_axis_var.set("None")

    def clear_bnd_form(self):
        self.selected_bnd_index = None
        self.bsrc_axis_var.set("")
        self.boundary_var.set("")
        self.relation_var.set("")
        self.relation_target_var.set(self.asset_name or "")
        self.acc_bnd_var.set("None")

    def update_axis_mapping(self):
        if self.selected_axis_index is None:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Axis-Mapping-Eintrag in der Liste auswählen.")
            return
        app = self.current_appearance(create_if_missing=False)
        if not app:
            messagebox.showwarning("Hinweis", "Keine Appearance für diese Referenz vorhanden.")
            return
        try:
            m = app["axis_mappings"][self.selected_axis_index]
        except Exception:
            messagebox.showerror("Fehler", "Ausgewählter Mapping-Eintrag existiert nicht mehr.")
            return

        # Werte aus Formular übernehmen
        m["source"] = {"axis": self.src_axis_var.get()}
        m["target"] = {"object": self.reference_space_var.get().strip(),
                       "axis": self.tgt_axis_var.get(),
                       "inverse": bool(self.inverse_var.get())}
        m["accuracy"] = self.acc_axis_var.get()

        self.persist_json(show_toast=False)
        self.refresh_axis_tree()
        self.update_history_box()
        messagebox.showinfo("OK", "Axis-Mapping aktualisiert und gespeichert.")

    def delete_axis_mapping(self):
        if self.selected_axis_index is None:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Axis-Mapping-Eintrag auswählen.")
            return
        app = self.current_appearance(create_if_missing=False)
        if not app:
            return
        try:
            del app["axis_mappings"][self.selected_axis_index]
        except Exception:
            messagebox.showerror("Fehler", "Löschen fehlgeschlagen.")
            return
        self.selected_axis_index = None
        self.persist_json(show_toast=False)
        self.refresh_axis_tree()
        self.update_history_box()
        messagebox.showinfo("OK", "Axis-Mapping gelöscht und gespeichert.")

    def update_boundary_mapping(self):
        if self.selected_bnd_index is None:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Boundary-Mapping-Eintrag in der Liste auswählen.")
            return
        app = self.current_appearance(create_if_missing=False)
        if not app:
            messagebox.showwarning("Hinweis", "Keine Appearance für diese Referenz vorhanden.")
            return
        try:
            m = app["boundary_point_mappings"][self.selected_bnd_index]
        except Exception:
            messagebox.showerror("Fehler", "Ausgewählter Mapping-Eintrag existiert nicht mehr.")
            return

        # Werte aus Formular
        m["source"] = {"axis": self.bsrc_axis_var.get(), "boundary": self.boundary_var.get()}
        m["reloc_relation"] = self.relation_var.get()
        m["reloc_relation_target"] = self.relation_target_var.get().strip()
        m["accuracy"] = self.acc_bnd_var.get()

        self.persist_json(show_toast=False)
        self.refresh_bnd_tree()
        self.update_history_box()
        messagebox.showinfo("OK", "Boundary-Mapping aktualisiert und gespeichert.")

    def delete_boundary_mapping(self):
        if self.selected_bnd_index is None:
            messagebox.showwarning("Hinweis", "Bitte zuerst einen Boundary-Mapping-Eintrag auswählen.")
            return
        app = self.current_appearance(create_if_missing=False)
        if not app:
            return
        try:
            del app["boundary_point_mappings"][self.selected_bnd_index]
        except Exception:
            messagebox.showerror("Fehler", "Löschen fehlgeschlagen.")
            return
        self.selected_bnd_index = None
        self.persist_json(show_toast=False)
        self.refresh_bnd_tree()
        self.update_history_box()
        messagebox.showinfo("OK", "Boundary-Mapping gelöscht und gespeichert.")

    def finish_and_close(self):
        # Mark as finished and close the window (mainloop will return)
        self.exit_status = "finished"
        try:
            self.persist_json(show_toast=False)  # ensure file is saved
        except Exception:
            pass
        self.root.quit()  # leave mainloop; caller will destroy the root

    # ---------- UI ----------
    def build_full_path(self, rel: str) -> Path:
        """Prefix 'Input\\' + rel_access_url relativ zur JSON-Datei."""
        try:
            rel_path = Path(rel)  # akzeptiert Backslashes
        except Exception:
            rel_path = Path(str(rel))
        return (self.input_dir / rel_path).resolve()

    def update_dual_preview(self):
        # Current Space
        self.cur_preview_original_image = None
        self.cur_preview_image_tk = None
        self.cur_preview_current_path = None
        cur_rel = self.current_space.get("metadata", {}).get("rel_access_url") if self.current_space else None
        if cur_rel:
            cur_full = self.build_full_path(cur_rel)
            self.cur_preview_current_path = str(cur_full)
            self.cur_preview_path_var.set(self.cur_preview_current_path)
            self._load_into_label(cur_full, self.cur_preview_label, side="cur")
        else:
            self.cur_preview_path_var.set("")
            self._set_preview_message(self.cur_preview_label, "Keine Datei im Current Space.", side="cur")

        # Reference Space
        self.ref_preview_original_image = None
        self.ref_preview_image_tk = None
        self.ref_preview_current_path = None
        ref_name = self.reference_space_var.get().strip() if hasattr(self, "reference_space_var") else ""
        ref_space = self.find_space(ref_name) if ref_name else None
        ref_rel = ref_space.get("metadata", {}).get("rel_access_url") if ref_space else None
        if ref_rel:
            ref_full = self.build_full_path(ref_rel)
            self.ref_preview_current_path = str(ref_full)
            self.ref_preview_path_var.set(self.ref_preview_current_path)
            self._load_into_label(ref_full, self.ref_preview_label, side="ref")
        else:
            self.ref_preview_path_var.set("")
            self.ref_preview_label.configure(image="", text="Keine Datei im Reference Space.", fg="#dddddd")


    def _load_into_label(self, full_path: Path, label, side: str):
        """Hilfsmethode: Datei laden und anzeigen (Bild/PDF-Hinweis). side = 'cur' oder 'ref'."""
        if not full_path.exists():
            self._set_preview_message(label, f"Datei nicht gefunden:\n{full_path}", side=side)
            return

        ext = full_path.suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp"):
            if PIL_AVAILABLE:
                try:
                    img = Image.open(full_path)
                except Exception as e:
                    label.configure(image="", text=f"Bild konnte nicht geladen werden:\n{e}", fg="#dddddd")
                    return
                if side == "cur":
                    self.cur_preview_original_image = img
                else:
                    self.ref_preview_original_image = img
                # Erstes Rendern; spätere Resizes kommen über <Configure>
                if side == "cur":
                    self.render_cur_preview_fit()
                else:
                    self.render_ref_preview_fit()
            else:
                if ext in (".png", ".gif"):
                    try:
                        photo = tk.PhotoImage(file=str(full_path))
                        if isinstance(label, tk.Canvas):
                            label.delete("all")
                            label.create_image(0, 0, image=photo, anchor="nw")
                            if side == "cur":
                                self.cur_preview_image_tk = photo
                            else:
                                self.ref_preview_image_tk = photo
                            self._draw_static_axes(label)
                        else:
                            label.configure(image=photo, text="")
                            # Referenz halten
                            if side == "cur":
                                self.cur_preview_image_tk = photo
                            else:
                                self.ref_preview_image_tk = photo
                    except Exception as e:
                        self._set_preview_message(label, f"Bild konnte nicht geladen werden:\n{e}", side=side)
                else:
                    self._set_preview_message(label, "Bitte Pillow installieren: pip install pillow", side=side)
        elif ext == ".pdf":
            self._set_preview_message(label,
                                      "PDF kann hier nicht inline angezeigt werden.\nBitte 'Datei öffnen' verwenden.",
                                      side=side)
        else:
            self._set_preview_message(label, f"Nicht unterstützter Dateityp: {ext}", side=side)

    def _set_preview_message(self, widget, text: str, side: str):
        if isinstance(widget, tk.Canvas):
            widget.delete("all")
            w = max(1, widget.winfo_width())
            h = max(1, widget.winfo_height())
            widget.create_text(w // 2, h // 2, text=text, fill="#dddddd", justify="center")
            if side == "cur":
                self._draw_static_axes(widget)
            return
        widget.configure(image="", text=text, fg="#dddddd")

    def _draw_static_axes(self, canvas):
        if not isinstance(canvas, tk.Canvas):
            return
        canvas.delete("axes_overlay")
        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())
        pad = 18
        x0 = pad
        y0 = pad
        x1 = max(x0 + 40, w - 48)
        y1 = max(y0 + 40, h - 48)
        canvas.create_line(x0, y0, x1, y0, fill="#d46a6a", width=4, arrow=tk.LAST, tags=("axes_overlay",))
        canvas.create_line(x0, y0, x0, y1, fill="#78c96b", width=4, arrow=tk.LAST, tags=("axes_overlay",))
        canvas.create_text(x1 + 14, y0, text="X", fill="white", font=("Segoe UI", 14, "bold"),
                           anchor="w", tags=("axes_overlay",))
        canvas.create_text(x0, y1 + 14, text="y", fill="white", font=("Segoe UI", 14, "bold"),
                           anchor="n", tags=("axes_overlay",))

    def on_cur_preview_resize(self, _evt=None):
        if self.cur_preview_original_image is not None:
            self.render_cur_preview_fit()

    def on_ref_preview_resize(self, _evt=None):
        if self.ref_preview_original_image is not None:
            self.render_ref_preview_fit()

    def render_cur_preview_fit(self):
        self._render_fit(self.cur_preview_original_image, self.cur_preview_label, which="cur")

    def render_ref_preview_fit(self):
        self._render_fit(self.ref_preview_original_image, self.ref_preview_label, which="ref")

    def _render_fit(self, img: Image.Image, label, which: str):
        """Skaliert proportional auf die verfügbare Fläche des Ziel-Widgets."""
        if img is None:
            return
        lw = max(1, label.winfo_width() - 8)
        lh = max(1, label.winfo_height() - 8)
        if lw <= 1 or lh <= 1:
            self.root.after(100, lambda: self._render_fit(img, label, which))
            return
        scale = min(lw / float(img.width), lh / float(img.height))
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        try:
            resized = img.resize((new_w, new_h), Image.LANCZOS)
        except Exception:
            resized = img.resize((new_w, new_h))
        photo = ImageTk.PhotoImage(resized)
        if isinstance(label, tk.Canvas):
            label.delete("all")
            canvas_w = max(1, label.winfo_width())
            canvas_h = max(1, label.winfo_height())
            label.create_image(canvas_w // 2, canvas_h // 2, image=photo, anchor="center")
            label.image = photo
            if which == "cur":
                self.cur_preview_image_tk = photo
                self._draw_static_axes(label)
            else:
                self.ref_preview_image_tk = photo
        else:
            label.configure(image=photo, text="")
            if which == "cur":
                self.cur_preview_image_tk = photo
            else:
                self.ref_preview_image_tk = photo

    def open_cur_preview_file(self):
        p = self.cur_preview_current_path
        if not p or not os.path.exists(p):
            messagebox.showwarning("Hinweis", "Keine Datei im Current Space vorhanden.")
            return
        try:
            os.startfile(p)
        except Exception as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geöffnet werden:\n{e}")

    def open_ref_preview_file(self):
        p = self.ref_preview_current_path
        if not p or not os.path.exists(p):
            messagebox.showwarning("Hinweis", "Keine Datei im Reference Space vorhanden.")
            return
        try:
            os.startfile(p)
        except Exception as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geöffnet werden:\n{e}")

    def open_preview_popup(self, path: str):
        """Ein gemeinsamer Pop-out für Current/Reference; zeigt die angegebene Datei an."""
        if not path or not os.path.exists(path):
            messagebox.showwarning("Hinweis", "Keine Datei vorhanden.")
            return
        top = tk.Toplevel(self.root)
        top.title(f"Preview – {os.path.basename(path)}")
        top.geometry("1200x800")
        frame = ttk.Frame(top, padding=8)
        frame.pack(fill="both", expand=True)
        canvas = tk.Label(frame, anchor="center", relief="sunken", bg="#202020")
        canvas.pack(fill="both", expand=True)
        local_image_orig = None
        local_image_tk = None
        ext = Path(path).suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp") and PIL_AVAILABLE:
            try:
                local_image_orig = Image.open(path)
            except Exception as e:
                canvas.configure(text=f"Bild konnte nicht geladen werden:\n{e}", fg="#dddddd")
                return
        else:
            canvas.configure(text="Nicht unterstützter Typ für Pop-out oder Pillow nicht installiert.", fg="#dddddd")
            return

        def _render(_evt=None):
            nonlocal local_image_tk
            w = max(1, canvas.winfo_width() - 8)
            h = max(1, canvas.winfo_height() - 8)
            scale = min(w / float(local_image_orig.width), h / float(local_image_orig.height))
            new_w = max(1, int(local_image_orig.width * scale))
            new_h = max(1, int(local_image_orig.height * scale))
            local_image_tk = ImageTk.PhotoImage(local_image_orig.resize((new_w, new_h), Image.LANCZOS))
            canvas.configure(image=local_image_tk, text="")
            canvas.image = local_image_tk

        _render()
        canvas.bind("<Configure>", _render)

    def build_basics_tab(self):
        container = ttk.Frame(self.frame_basics, padding=15)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)
        container.columnconfigure(2, weight=0)

        ttk.Label(container, text="Editing Space:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.editing_space_combo = ttk.Combobox(container, values=self.editable_space_names, textvariable=self.current_space_name, state="readonly", width=40)
        self.editing_space_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.editing_space_combo.bind("<<ComboboxSelected>>", lambda e: self.set_current_space(self.current_space_name.get()))

        ttk.Button(container, text="Neuen Space anlegen",
                   command=self.start_new_space).grid(row=0, column=2, sticky="w", padx=5, pady=5)

        ttk.Label(container, text="Space Name").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.space_name_var = tk.StringVar()
        self.space_name_entry = ttk.Entry(container, textvariable=self.space_name_var, width=40)
        self.space_name_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(container, text="Space Class").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.space_class_var = tk.StringVar()
        self.space_class_combo = ttk.Combobox(container, values=SPACE_CLASSES, textvariable=self.space_class_var, state="readonly", width=40)
        self.space_class_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        submit_btn = ttk.Button(container, text="Submit", command=self.submit_basics)
        submit_btn.grid(row=3, column=1, sticky="e", padx=5, pady=10)

    def build_appearance_tab(self):
        # Container + PanedWindow für flexible Höhenaufteilung
        container = ttk.Frame(self.frame_appearance, padding=0)
        container.pack(fill="both", expand=True)

        paned = tk.PanedWindow(container, orient="horizontal", sashwidth=8)
        paned.pack(fill="both", expand=True)

        # LINKER PANE: Controls (scrollable)
        left_container = ttk.Frame(paned)
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(0, weight=1)

        # Canvas + vertical scrollbar for left controls
        left_canvas = tk.Canvas(left_container, borderwidth=0, highlightthickness=0)
        left_vscroll = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_vscroll.set)
        left_canvas.grid(row=0, column=0, sticky="nsew")
        left_vscroll.grid(row=0, column=1, sticky="ns")

        # Inner frame that holds actual controls (kept named 'left' to minimize further changes)
        left = ttk.Frame(left_canvas, padding=10)
        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")

        def _on_left_config(_evt=None):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
            try:
                left_canvas.itemconfig(left_window, width=left_canvas.winfo_width())
            except Exception:
                pass
        left.bind("<Configure>", _on_left_config)

        # Mouse wheel scrolling (Windows)
        left_canvas.bind_all("<MouseWheel>", lambda e: left_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # RECHTER PANE: Preview (oben/unten)
        right = ttk.Frame(paned, padding=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)  # der Preview-Teil wächst mit

        paned.add(left_container, minsize=520)  # Mindestbreite für Controls
        paned.add(right, minsize=320)  # Mindestbreite für Preview

        # Reference Space selection
        ref_frame = ttk.LabelFrame(left, text="Reference Space", padding=10)
        ref_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        ttk.Label(ref_frame, text="Select Reference Space:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.reference_space_var = tk.StringVar()
        self.reference_space_combo = ttk.Combobox(ref_frame, values=self.reference_space_names,
                                                  textvariable=self.reference_space_var, state="readonly", width=40)
        self.reference_space_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.reference_space_combo.bind("<<ComboboxSelected>>",
                                        lambda e: (self.refresh_appearance_selector(), self.update_reference_info(), self.update_history_box(),
                                                   self.update_dual_preview()))
        ref_frame.columnconfigure(1, weight=1)

        self.appearance_frame = ttk.LabelFrame(left, text="Appearances", padding=10)
        self.appearance_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.appearance_frame.columnconfigure(1, weight=1)

        self.asset_appearance_frame = ttk.LabelFrame(self.appearance_frame, text="Asset Appearances", padding=10)
        self.asset_appearance_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.asset_appearance_frame.columnconfigure(1, weight=1)
        ttk.Label(self.asset_appearance_frame, text="Appearance Name").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.asset_appearance_name_entry = ttk.Entry(self.asset_appearance_frame, textvariable=self.asset_appearance_name_var, width=28)
        self.asset_appearance_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(self.asset_appearance_frame, text="Active Appearance").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.asset_appearance_combo = ttk.Combobox(self.asset_appearance_frame, textvariable=self.asset_appearance_var,
                                                   state="readonly", width=28)
        self.asset_appearance_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.asset_appearance_combo.bind("<<ComboboxSelected>>", self.on_asset_appearance_selected)
        ttk.Checkbutton(
            self.asset_appearance_frame,
            text="Copy values from selected appearance",
            variable=self.asset_appearance_copy_var
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 5))
        self.asset_appearance_create_btn = ttk.Button(self.asset_appearance_frame, text="Create New Asset Appearance",
                                                      command=self.create_asset_appearance)
        self.asset_appearance_create_btn.grid(row=0, column=2, rowspan=3, sticky="ns", padx=5, pady=5)

        self.entity_appearance_frame = ttk.LabelFrame(self.appearance_frame, text="Entity Appearances", padding=10)
        self.entity_appearance_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.entity_appearance_frame.columnconfigure(1, weight=1)
        ttk.Label(self.entity_appearance_frame, text="Appearance Name").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.entity_appearance_name_entry = ttk.Entry(self.entity_appearance_frame, textvariable=self.entity_appearance_name_var, width=28)
        self.entity_appearance_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(self.entity_appearance_frame, text="Active Appearance").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.entity_appearance_combo = ttk.Combobox(self.entity_appearance_frame, textvariable=self.entity_appearance_var,
                                                    state="readonly", width=28)
        self.entity_appearance_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.entity_appearance_combo.bind("<<ComboboxSelected>>", self.on_entity_appearance_selected)
        ttk.Checkbutton(
            self.entity_appearance_frame,
            text="Copy values from selected appearance",
            variable=self.entity_appearance_copy_var
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 5))
        self.entity_appearance_create_btn = ttk.Button(self.entity_appearance_frame, text="Create New Entity Appearance",
                                                       command=self.create_entity_appearance)
        self.entity_appearance_create_btn.grid(row=0, column=2, rowspan=3, sticky="ns", padx=5, pady=5)

        self.existing_appearances_visible = tk.BooleanVar(value=False)
        self.existing_appearances_toggle_btn = ttk.Button(
            left,
            text="Show Existing Mappings",
            command=lambda: (self.existing_appearances_visible.set(not self.existing_appearances_visible.get()),
                             self.toggle_existing_appearances_panel())
        )
        self.existing_appearances_toggle_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
        self.existing_appearances_body = ttk.LabelFrame(left, text="Existing Mappings in JSON", padding=10)
        self.existing_appearances_body.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.existing_appearances_body.columnconfigure(0, weight=1)

        axis_existing = ttk.LabelFrame(self.existing_appearances_body, text="Axis Mappings", padding=8)
        axis_existing.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        axis_existing.columnconfigure(0, weight=1)
        axis_cols = ("#", "source", "target", "inverse", "accuracy")
        self.axis_tree = ttk.Treeview(axis_existing, columns=axis_cols, show="headings", height=6)
        for c, w in zip(axis_cols, (40, 80, 80, 70, 90)):
            self.axis_tree.heading(c, text=c)
            self.axis_tree.column(c, width=w, anchor="center")
        self.axis_tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.axis_tree.bind("<<TreeviewSelect>>", self.on_axis_select)
        axis_existing_buttons = ttk.Frame(axis_existing)
        axis_existing_buttons.grid(row=1, column=0, columnspan=2, sticky="e", padx=4, pady=4)
        ttk.Button(axis_existing_buttons, text="New", command=self.clear_axis_form).pack(side="left", padx=3)
        ttk.Button(axis_existing_buttons, text="Update", command=self.update_axis_mapping).pack(side="left", padx=3)
        ttk.Button(axis_existing_buttons, text="Delete", command=self.delete_axis_mapping).pack(side="left", padx=3)

        bnd_existing = ttk.LabelFrame(self.existing_appearances_body, text="Boundary Point Mappings", padding=8)
        bnd_existing.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        bnd_existing.columnconfigure(0, weight=1)
        bnd_cols = ("#", "src_axis", "boundary", "relation", "target", "accuracy")
        self.bnd_tree = ttk.Treeview(bnd_existing, columns=bnd_cols, show="headings", height=6)
        for c, w in zip(bnd_cols, (40, 80, 90, 140, 160, 90)):
            self.bnd_tree.heading(c, text=c)
            self.bnd_tree.column(c, width=w, anchor="center")
        self.bnd_tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.bnd_tree.bind("<<TreeviewSelect>>", self.on_bnd_select)
        bnd_existing_buttons = ttk.Frame(bnd_existing)
        bnd_existing_buttons.grid(row=1, column=0, columnspan=2, sticky="e", padx=4, pady=4)
        ttk.Button(bnd_existing_buttons, text="New", command=self.clear_bnd_form).pack(side="left", padx=3)
        ttk.Button(bnd_existing_buttons, text="Update", command=self.update_boundary_mapping).pack(side="left", padx=3)
        ttk.Button(bnd_existing_buttons, text="Delete", command=self.delete_boundary_mapping).pack(side="left", padx=3)

        self.existing_appearances_body.grid_remove()

        # Info boxes
        # Axis Mappings
        axis_frame = ttk.LabelFrame(left, text="Axis Mappings", padding=10)
        axis_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        ttk.Label(axis_frame, text="Source Axis").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.src_axis_var = tk.StringVar(value=None)
        ttk.Combobox(axis_frame, values=AXES, textvariable=self.src_axis_var, state="readonly", width=20) \
            .grid(row=0, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(axis_frame, text="Target Axis [of ref. Space]").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.tgt_axis_var = tk.StringVar(value=None)
        ttk.Combobox(axis_frame, values=AXES, textvariable=self.tgt_axis_var, state="readonly", width=20) \
            .grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.inverse_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(axis_frame, text="is inverse", variable=self.inverse_var).grid(row=2, column=0, sticky="w",
                                                                                       padx=5, pady=5)
        ttk.Label(axis_frame, text="Accuracy").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.acc_axis_var = tk.StringVar(value="None")
        acc_frame = ttk.Frame(axis_frame);
        acc_frame.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        for acc in ACCURACY:
            ttk.Radiobutton(acc_frame, text=acc, value=acc, variable=self.acc_axis_var).pack(side="left", padx=2)
        ttk.Button(axis_frame, text="Submit Axis Mapping", command=self.submit_axis_mapping) \
            .grid(row=4, column=1, sticky="e", padx=5, pady=10)

        axis_btns = ttk.Frame(axis_frame)
        axis_btns.grid(row=5, column=0, columnspan=2, sticky="e", padx=5, pady=5)
        ttk.Button(axis_btns, text="Neu", command=self.clear_axis_form).pack(side="left", padx=3)

        # Boundary Point Mappings
        bnd_frame = ttk.LabelFrame(left, text="Boundary Point Mappings", padding=10)
        bnd_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        ttk.Label(bnd_frame, text="Source Axis").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.bsrc_axis_var = tk.StringVar(value=None)
        ttk.Combobox(bnd_frame, values=AXES, textvariable=self.bsrc_axis_var, state="readonly", width=20) \
            .grid(row=0, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(bnd_frame, text="Point Type").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.boundary_var = tk.StringVar(value=None)
        ttk.Combobox(bnd_frame, values=BOUNDARIES, textvariable=self.boundary_var, state="readonly", width=20) \
            .grid(row=1, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(bnd_frame, text="Reloc Relation").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.relation_var = tk.StringVar(value=None)
        ttk.Combobox(bnd_frame, values=RELATIONS, textvariable=self.relation_var, state="readonly", width=30) \
            .grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(bnd_frame, text="Reloc Relation Target").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.relation_target_var = tk.StringVar(value=None)
        self.relation_target_combo = ttk.Combobox(bnd_frame, values=self.reference_space_names,
                                                  textvariable=self.relation_target_var, state="readonly", width=30)
        self.relation_target_combo.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(bnd_frame, text="Accuracy").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.acc_bnd_var = tk.StringVar(value="None")
        acc_bnd_frame = ttk.Frame(bnd_frame);
        acc_bnd_frame.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        for acc in ACCURACY:
            ttk.Radiobutton(acc_bnd_frame, text=acc, value=acc, variable=self.acc_bnd_var).pack(side="left", padx=2)
        ttk.Button(bnd_frame, text="Submit Boundary Point Mapping", command=self.submit_boundary_mapping) \
            .grid(row=5, column=1, sticky="e", padx=5, pady=10)

        # Existing boundary mappings list hidden per request
        ttk.Label(bnd_frame, text="(Existing mappings hidden)").grid(row=6, column=0, columnspan=2, padx=5, pady=5)

        bnd_btns = ttk.Frame(bnd_frame)
        bnd_btns.grid(row=7, column=0, columnspan=2, sticky="e", padx=5, pady=5)
        ttk.Button(bnd_btns, text="Neu", command=self.clear_bnd_form).pack(side="left", padx=3)

        # Export
        export_frame = ttk.Frame(left)
        export_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
        ttk.Button(export_frame, text="Show JSON", command=self.show_json).pack(side="right", padx=5)
        ttk.Button(export_frame, text="Speichern", command=lambda: self.persist_json(show_toast=True)).pack(
            side="right", padx=5)
        ttk.Button(export_frame, text="Finish", command=self.finish_and_close).pack(side="right", padx=5)

        # --- RECHTER PANE: zwei Previews untereinander ---
        # Wir nutzen ein vertikales PanedWindow, damit man die Höhe der beiden Bilder per Maus anpassen kann.
        right_paned = tk.PanedWindow(right, orient="vertical", sashwidth=6)
        right_paned.grid(row=0, column=0, sticky="nsew")

        # Current Space (oben)
        cur_box = ttk.LabelFrame(right_paned, text="Current Space", padding=8)
        cur_box.columnconfigure(0, weight=1)
        cur_box.rowconfigure(2, weight=1)  # Bildbereich wächst

        # Pfadzeile
        self.cur_preview_path_var = tk.StringVar(value="")
        path_row = ttk.Frame(cur_box)
        path_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(path_row, text="Pfad:").grid(row=0, column=0, sticky="w")
        cur_path_entry = ttk.Entry(path_row, textvariable=self.cur_preview_path_var, state="readonly")
        cur_path_entry.grid(row=0, column=1, sticky="ew", padx=5)
        path_row.columnconfigure(1, weight=1)  # Entry dehnt sich

        # Buttonzeile (unter dem Pfad)
        cur_btns = ttk.Frame(cur_box)
        cur_btns.grid(row=1, column=0, sticky="w", pady=(4, 6))
        ttk.Button(cur_btns, text="Neu laden", command=self.update_dual_preview).pack(side="left", padx=3)
        ttk.Button(cur_btns, text="Pop-out",
                   command=lambda: self.open_preview_popup(self.cur_preview_current_path)).pack(side="left", padx=3)
        ttk.Button(cur_btns, text="Öffnen", command=self.open_cur_preview_file).pack(side="left", padx=3)
        ttk.Button(cur_btns, text="Kopieren",
                   command=lambda: self.copy_to_clipboard(self.cur_preview_path_var.get())).pack(side="left", padx=3)

        # Bildfläche
        self.cur_preview_label = tk.Canvas(cur_box, relief="sunken", bg="#202020", highlightthickness=0)
        self.cur_preview_label.grid(row=2, column=0, sticky="nsew")
        self.cur_preview_label.bind("<Configure>", self.on_cur_preview_resize)

        # Reference Space (unten)
        ref_box = ttk.LabelFrame(right_paned, text="Reference Space", padding=8)
        ref_box.columnconfigure(0, weight=1)
        ref_box.rowconfigure(2, weight=1)  # Bildbereich wächst

        # Pfadzeile
        self.ref_preview_path_var = tk.StringVar(value="")
        ref_path_row = ttk.Frame(ref_box)
        ref_path_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(ref_path_row, text="Pfad:").grid(row=0, column=0, sticky="w")
        ref_path_entry = ttk.Entry(ref_path_row, textvariable=self.ref_preview_path_var, state="readonly")
        ref_path_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ref_path_row.columnconfigure(1, weight=1)

        # Buttonzeile (unter dem Pfad)
        ref_btns = ttk.Frame(ref_box)
        ref_btns.grid(row=1, column=0, sticky="w", pady=(4, 6))
        ttk.Button(ref_btns, text="Neu laden", command=self.update_dual_preview).pack(side="left", padx=3)
        ttk.Button(ref_btns, text="Pop-out",
                   command=lambda: self.open_preview_popup(self.ref_preview_current_path)).pack(side="left", padx=3)
        ttk.Button(ref_btns, text="Öffnen", command=self.open_ref_preview_file).pack(side="left", padx=3)
        ttk.Button(ref_btns, text="Kopieren",
                   command=lambda: self.copy_to_clipboard(self.ref_preview_path_var.get())).pack(side="left", padx=3)

        # Bildfläche
        self.ref_preview_label = tk.Label(ref_box, anchor="center", relief="sunken", bg="#202020")
        self.ref_preview_label.grid(row=2, column=0, sticky="nsew")
        self.ref_preview_label.bind("<Configure>", self.on_ref_preview_resize)

        # In das vertikale Pane einhängen
        right_paned.add(cur_box, minsize=160)
        right_paned.add(ref_box, minsize=160)

    def build_status_bar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status_var, anchor="w").pack(fill="x", padx=8, pady=4)

    # ---------- Aktionen ----------
    def submit_basics(self):
        name = self.space_name_var.get().strip()
        cls = self.space_class_var.get().strip()
        if not name or not cls:
            messagebox.showwarning("Hinweis", "Bitte Name und Space Class ausfüllen.")
            return

        existing_doc = next((d for d in self.data.get("document_spaces", []) if d.get("name") == name), None)
        existing_ent = next((e for e in self.data.get("entity_spaces", []) if e.get("name") == name), None)

        if existing_doc or existing_ent:
            messagebox.showwarning("Hinweis",
                                   f"Ein Space mit dem Namen '{name}' existiert bereits.\n"
                                   "Bitte einen anderen Namen wählen oder den bestehenden Space bearbeiten.")
            return

        if cls == "DocumentSpace":
            if existing_doc:
                existing_doc["class"] = cls
                messagebox.showinfo("Aktualisiert", f"DocumentSpace '{name}' wurde aktualisiert und gespeichert.")
            else:
                new_doc = {"class": "DocumentSpace", "name": name, "axes_directions": {"X": "Right", "Y": "Bottom"}, "metadata": {}}
                self.data.setdefault("document_spaces", []).append(new_doc)
                messagebox.showinfo("Erstellt", f"DocumentSpace '{name}' wurde angelegt und gespeichert.")
        else:
            if existing_ent:
                existing_ent["class"] = cls
                messagebox.showinfo("Aktualisiert", f"EntitySpace '{name}' wurde aktualisiert und gespeichert.")
            else:
                new_ent = {"class": cls, "name": name, "asset_appearances": [], "document_appearances": [], "entity_appearances": []}
                self.data.setdefault("entity_spaces", []).append(new_ent)
                messagebox.showinfo("Erstellt", f"EntitySpace '{name}' wurde angelegt und gespeichert.")

        # Liste aktualisieren und Auswahl setzen
        self.refresh_space_lists()
        self.editing_space_combo["values"] = self.editable_space_names
        self.current_space_name.set(name)
        self.set_current_space(name)


        # Direkt in Datei schreiben
        self.persist_json(show_toast=False)
        self.update_dual_preview()

    def submit_axis_mapping(self):
        if not self.current_space or self.space_kind(self.current_space) == "asset":
            messagebox.showwarning("Hinweis", "Bitte einen Document- oder Entity-Space zum Bearbeiten auswählen.")
            return
        ref_name = self.reference_space_var.get().strip()
        if not ref_name:
            messagebox.showwarning("Hinweis", "Bitte einen Reference Space auswählen.")
            return

        app = self.get_or_create_appearance(self.current_space, ref_name, create_if_missing=True)
        if not app:
            messagebox.showerror("Fehler", "Appearance konnte nicht erstellt werden.")
            return

        src_axis = self.src_axis_var.get()
        tgt_axis = self.tgt_axis_var.get()
        inverse = bool(self.inverse_var.get())
        acc = self.acc_axis_var.get()

        mapping = {"source": {"axis": src_axis}, "target": {"object": ref_name, "axis": tgt_axis, "inverse": inverse}, "accuracy": acc}

        app.setdefault("axis_mappings", []).append(mapping)
        self.refresh_appearance_selector()
        self.update_history_box()
        self.refresh_axis_tree()
        self.persist_json(show_toast=False)
        messagebox.showinfo("OK", "Axis Mapping hinzugefügt und gespeichert.")

    def submit_boundary_mapping(self):
        if not self.current_space or self.space_kind(self.current_space) == "asset":
            messagebox.showwarning("Hinweis", "Bitte einen Document- oder Entity-Space zum Bearbeiten auswählen.")
            return
        ref_name = self.reference_space_var.get().strip()
        if not ref_name:
            messagebox.showwarning("Hinweis", "Bitte einen Reference Space auswählen.")
            return

        app = self.get_or_create_appearance(self.current_space, ref_name, create_if_missing=True)
        if not app:
            messagebox.showerror("Fehler", "Appearance konnte nicht erstellt werden.")
            return

        src_axis = self.bsrc_axis_var.get()
        boundary = self.boundary_var.get()
        relation = self.relation_var.get()
        rel_target = self.relation_target_var.get().strip()
        acc = self.acc_bnd_var.get()

        mapping = {"source": {"axis": src_axis, "boundary": boundary}, "reloc_relation": relation, "reloc_relation_target": rel_target, "accuracy": acc}

        app.setdefault("boundary_point_mappings", []).append(mapping)
        self.refresh_appearance_selector()
        self.update_history_box()
        self.refresh_bnd_tree()
        self.persist_json(show_toast=False)
        messagebox.showinfo("OK", "Boundary Point Mapping hinzugefügt und gespeichert.")

    def update_reference_info(self):
        # Info box removed — refresh mapping lists and previews
        self.refresh_axis_tree()
        self.refresh_bnd_tree()
        self.update_dual_preview()

    def update_history_box(self):
        # History view removed per UI simplification request — keep function as no-op for compatibility
        return

    def show_json(self):
        top = tk.Toplevel(self.root)
        top.title("Current JSON")
        txt = tk.Text(top, wrap="none", width=120, height=40)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", json.dumps(self.data, indent=4))
        txt.config(state="normal")
        ttk.Button(top, text="In Zwischenablage kopieren", command=lambda: self.copy_to_clipboard(txt.get("1.0", "end-1c"))).pack(pady=5)

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("OK", "JSON in die Zwischenablage kopiert.")


def run_editor(input_json_path, theme="light"):
    root = tk.Tk()
    root.geometry("1200x800")
    root.minsize(900,600)
    # Optional theme
    try:
        root.tk.call("source", "azure.tcl")
        root.tk.call("set_theme", theme)
    except Exception:
        pass

    app = SpotEditorApp(root, input_path=input_json_path)

    # Ensure we mark status and save on window close (X)
    def on_close():
        app.exit_status = "closed"
        try:
            app.persist_json(show_toast=False)
        except Exception:
            pass
        root.quit()

    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()        # blocks until Finish or window close
    root.destroy()         # clean up
    return app.exit_status


if __name__ == "__main__":
    run_editor("output/output_json/nibelungen_spaces.json")