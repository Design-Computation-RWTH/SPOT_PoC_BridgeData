# -*- coding: utf-8 -*-
# SPOT Editor - Tkinter GUI (Windows 11, Python 3.9.7)
# Lädt JSON aus Datei und schreibt Änderungen zurück in dieselbe Datei.
# Am Layout der Mock-ups orientiert.

import json
import os
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

        # History leeren, da es den Space noch nicht gibt
        self.history_list.config(state="normal")
        self.history_list.delete("1.0", "end")
        self.history_list.insert("end",
                                 "Neuen Space anlegen: Bitte Name und Space Class eingeben und 'Submit' drücken.\n")
        self.history_list.config(state="disabled")

        # Hinweis im Status
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
            if not current_space["asset_appearances"]:
                if not create_if_missing:
                    return None
                current_space["asset_appearances"].append({"axis_mappings": [], "boundary_point_mappings": []})
            return current_space["asset_appearances"][0]
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
            for app in current_space["entity_appearances"]:
                if app.get("ref_entity") == ref_name:
                    return app
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
        self.update_reference_info()
        self.update_history_box()
        self.refresh_axis_tree()
        self.refresh_bnd_tree()
        self.update_dual_preview()  # <<< Vorschau aktualisieren

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
                m.get("accuracy", ""),
                m.get("angle", "")
            ))

    def refresh_bnd_tree(self):
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
                m.get("normalized_coordinate", ""),
                m.get("accuracy", "")
            ))

    def on_axis_select(self, event=None):
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
        self.angle_var.set("" if "angle" not in m else str(m.get("angle")))

    def on_bnd_select(self, event=None):
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
        self.norm_coord_var.set("" if "normalized_coordinate" not in m else str(m.get("normalized_coordinate")))
        self.acc_bnd_var.set(m.get("accuracy", "None"))

    def clear_axis_form(self):
        self.selected_axis_index = None
        self.src_axis_var.set("")
        self.tgt_axis_var.set("")
        self.inverse_var.set(False)
        self.acc_axis_var.set("None")
        self.angle_var.set("")

    def clear_bnd_form(self):
        self.selected_bnd_index = None
        self.bsrc_axis_var.set("")
        self.boundary_var.set("")
        self.relation_var.set("")
        self.relation_target_var.set(self.asset_name or "")
        self.norm_coord_var.set("")
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

        angle_str = self.angle_var.get().strip()
        if angle_str:
            try:
                m["angle"] = float(angle_str)
            except ValueError:
                messagebox.showwarning("Hinweis", "Angle muss eine Zahl sein.")
                return
        else:
            m.pop("angle", None)

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

        norm_str = self.norm_coord_var.get().strip()
        if norm_str:
            try:
                val = float(norm_str)
                if not (0.0 <= val <= 1.0):
                    raise ValueError("out of range")
                m["normalized_coordinate"] = val
            except Exception:
                messagebox.showwarning("Hinweis", "Normalized Coordinate muss eine Zahl zwischen 0 und 1 sein.")
                return
        else:
            m.pop("normalized_coordinate", None)

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
            self.cur_preview_label.configure(image="", text="Keine Datei im Current Space.", fg="#dddddd")

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


    def _load_into_label(self, full_path: Path, label: tk.Label, side: str):
        """Hilfsmethode: Datei laden und anzeigen (Bild/PDF-Hinweis). side = 'cur' oder 'ref'."""
        if not full_path.exists():
            label.configure(image="", text=f"Datei nicht gefunden:\n{full_path}", fg="#dddddd")
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
                        label.configure(image=photo, text="")
                        # Referenz halten
                        if side == "cur":
                            self.cur_preview_image_tk = photo
                        else:
                            self.ref_preview_image_tk = photo
                    except Exception as e:
                        label.configure(image="", text=f"Bild konnte nicht geladen werden:\n{e}", fg="#dddddd")
                else:
                    label.configure(image="", text="Bitte Pillow installieren: pip install pillow", fg="#dddddd")
        elif ext == ".pdf":
            label.configure(image="",
                            text="PDF kann hier nicht inline angezeigt werden.\nBitte 'Datei öffnen' verwenden.",
                            fg="#dddddd")
        else:
            label.configure(image="", text=f"Nicht unterstützter Dateityp: {ext}", fg="#dddddd")

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

    def _render_fit(self, img: Image.Image, label: tk.Label, which: str):
        """Skaliert proportional auf die verfügbare Fläche des Labels."""
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
        label.configure(image=photo, text="")
        # Referenz halten
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

        # LINKER PANE: Controls
        left = ttk.Frame(paned, padding=10)
        left.columnconfigure(0, weight=1)
        left.columnconfigure(1, weight=1)

        # RECHTER PANE: Preview (oben/unten)
        right = ttk.Frame(paned, padding=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)  # der Preview-Teil wächst mit

        paned.add(left, minsize=520)  # Mindestbreite für Controls
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
                                        lambda e: (self.update_reference_info(), self.update_history_box(),
                                                   self.update_dual_preview()))
        ref_frame.columnconfigure(1, weight=1)

        # Info boxes
        info_axis = ttk.LabelFrame(left, text="Info: Reference Space Axis Directions", padding=10)
        info_axis.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.info_axis_text = tk.Text(info_axis, height=6, width=40)
        self.info_axis_text.pack(fill="both", expand=True)

        info_history = ttk.LabelFrame(left, text="History of Submitted Mappings", padding=10)
        info_history.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.history_list = tk.Text(info_history, height=6, width=40)
        self.history_list.pack(fill="both", expand=True)

        # Axis Mappings
        axis_frame = ttk.LabelFrame(left, text="Axis Mappings", padding=10)
        axis_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
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
        ttk.Label(axis_frame, text="Angle (optional)").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.angle_var = tk.StringVar()
        ttk.Entry(axis_frame, textvariable=self.angle_var, width=20).grid(row=4, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(axis_frame, text="Submit Axis Mapping", command=self.submit_axis_mapping) \
            .grid(row=5, column=1, sticky="e", padx=5, pady=10)

        cols = ("#", "source", "target", "inverse", "accuracy", "angle")
        self.axis_tree = ttk.Treeview(axis_frame, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (40, 80, 80, 70, 90, 80)):
            self.axis_tree.heading(c, text=c)
            self.axis_tree.column(c, width=w, anchor="center")
        self.axis_tree.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.axis_tree.bind("<<TreeviewSelect>>", self.on_axis_select)

        axis_btns = ttk.Frame(axis_frame)
        axis_btns.grid(row=7, column=0, columnspan=2, sticky="e", padx=5, pady=5)
        ttk.Button(axis_btns, text="Neu", command=self.clear_axis_form).pack(side="left", padx=3)
        ttk.Button(axis_btns, text="Aktualisieren", command=self.update_axis_mapping).pack(side="left", padx=3)
        ttk.Button(axis_btns, text="Löschen", command=self.delete_axis_mapping).pack(side="left", padx=3)

        # Boundary Point Mappings
        bnd_frame = ttk.LabelFrame(left, text="Boundary Point Mappings", padding=10)
        bnd_frame.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
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
        ttk.Label(bnd_frame, text="Normalized Coordinate (0..1)").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.norm_coord_var = tk.StringVar()
        ttk.Entry(bnd_frame, textvariable=self.norm_coord_var, width=20).grid(row=4, column=1, sticky="w", padx=5,
                                                                              pady=5)
        ttk.Label(bnd_frame, text="Accuracy").grid(row=5, column=0, sticky="w", padx=5, pady=5)
        self.acc_bnd_var = tk.StringVar(value="None")
        acc_bnd_frame = ttk.Frame(bnd_frame);
        acc_bnd_frame.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        for acc in ACCURACY:
            ttk.Radiobutton(acc_bnd_frame, text=acc, value=acc, variable=self.acc_bnd_var).pack(side="left", padx=2)
        ttk.Button(bnd_frame, text="Submit Boundary Point Mapping", command=self.submit_boundary_mapping) \
            .grid(row=6, column=1, sticky="e", padx=5, pady=10)

        bcols = ("#", "src_axis", "boundary", "relation", "target", "norm", "accuracy")
        self.bnd_tree = ttk.Treeview(bnd_frame, columns=bcols, show="headings", height=8)
        for c, w in zip(bcols, (40, 80, 90, 140, 160, 80, 90)):
            self.bnd_tree.heading(c, text=c)
            self.bnd_tree.column(c, width=w, anchor="center")
        self.bnd_tree.grid(row=7, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.bnd_tree.bind("<<TreeviewSelect>>", self.on_bnd_select)

        bnd_btns = ttk.Frame(bnd_frame)
        bnd_btns.grid(row=8, column=0, columnspan=2, sticky="e", padx=5, pady=5)
        ttk.Button(bnd_btns, text="Neu", command=self.clear_bnd_form).pack(side="left", padx=3)
        ttk.Button(bnd_btns, text="Aktualisieren", command=self.update_boundary_mapping).pack(side="left", padx=3)
        ttk.Button(bnd_btns, text="Löschen", command=self.delete_boundary_mapping).pack(side="left", padx=3)

        # Export
        export_frame = ttk.Frame(left)
        export_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
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
        self.cur_preview_label = tk.Label(cur_box, anchor="center", relief="sunken", bg="#202020")
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
        angle_str = self.angle_var.get().strip()

        mapping = {"source": {"axis": src_axis}, "target": {"object": ref_name, "axis": tgt_axis, "inverse": inverse}, "accuracy": acc}
        if angle_str:
            try:
                mapping["angle"] = float(angle_str)
            except ValueError:
                messagebox.showwarning("Hinweis", "Angle muss eine Zahl sein.")
                return

        app.setdefault("axis_mappings", []).append(mapping)
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
        norm_str = self.norm_coord_var.get().strip()

        mapping = {"source": {"axis": src_axis, "boundary": boundary}, "reloc_relation": relation, "reloc_relation_target": rel_target, "accuracy": acc}
        if norm_str:
            try:
                val = float(norm_str)
                if not (0.0 <= val <= 1.0):
                    raise ValueError("out of range")
                mapping["normalized_coordinate"] = val
            except Exception:
                messagebox.showwarning("Hinweis", "Normalized Coordinate muss eine Zahl zwischen 0 und 1 sein.")
                return

        app.setdefault("boundary_point_mappings", []).append(mapping)
        self.update_history_box()
        self.refresh_bnd_tree()
        self.persist_json(show_toast=False)
        messagebox.showinfo("OK", "Boundary Point Mapping hinzugefügt und gespeichert.")

    def update_reference_info(self):
        self.info_axis_text.config(state="normal")
        self.info_axis_text.delete("1.0", "end")
        ref = self.reference_space_var.get().strip()
        axes = self.get_axes_directions(ref)
        if axes:
            self.info_axis_text.insert("end", f"X Axis : {axes.get('X','-')}\n")
            self.info_axis_text.insert("end", f"Y Axis : {axes.get('Y','-')}\n")
            self.info_axis_text.insert("end", f"Z Axis : {axes.get('Z','-')}\n")
        else:
            self.info_axis_text.insert("end", "Keine Axis-Directions verfügbar.\n")
        self.info_axis_text.config(state="disabled")
        self.refresh_axis_tree()
        self.refresh_bnd_tree()

    def update_history_box(self):
        self.history_list.config(state="normal")
        self.history_list.delete("1.0", "end")
        if not self.current_space:
            self.history_list.insert("end", "Kein Space ausgewählt.\n")
            self.history_list.config(state="disabled")
            return
        ref_name = self.reference_space_var.get().strip()
        if not ref_name:
            self.history_list.insert("end", "Kein Reference Space ausgewählt.\n")
            self.history_list.config(state="disabled")
            return
        app = self.get_or_create_appearance(self.current_space, ref_name, create_if_missing=False)
        if not app:
            self.history_list.insert("end", "Keine Mappings für diese Referenz.\n")
            self.history_list.config(state="disabled")
            return
        axis_m = app.get("axis_mappings", [])
        bnd_m = app.get("boundary_point_mappings", [])
        self.history_list.insert("end", f"AxisMappings ({len(axis_m)}):\n")
        for i, m in enumerate(axis_m, 1):
            self.history_list.insert("end", f"  {i}. source_{m['source']['axis']} -> target_{m['target']['axis']} "
                                            f"(inverse={m['target'].get('inverse')}, acc={m.get('accuracy')}"
                                            f"{', angle='+str(m.get('angle')) if 'angle' in m else ''})\n")
        self.history_list.insert("end", f"\nBoundaryPointMappings ({len(bnd_m)}):\n")
        for i, m in enumerate(bnd_m, 1):
            src = m["source"]
            self.history_list.insert("end", f"  {i}. {src['axis']}/{src['boundary']} -> {m.get('reloc_relation')} "
                                            f"to {m.get('reloc_relation_target')} "
                                            f"{'(norm='+str(m.get('normalized_coordinate'))+')' if 'normalized_coordinate' in m else ''} "
                                            f"(acc={m.get('accuracy')})\n")
        self.history_list.config(state="disabled")

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