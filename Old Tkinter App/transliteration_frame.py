import tkinter as tk
from tkinter import Frame, Label, Text, Checkbutton, BooleanVar, Spinbox
from PIL import Image, ImageTk
import json
import os
from KohauCode_Horley import Glyph  # Assuming this imports the Glyph class
from tkinter import simpledialog, messagebox
from tkinter import ttk


# If you need to reference top-level data/functions in GlyphEditorWindow:
import GlyphEditorWindow  # May cause circular imports if not organized carefully

CONFIDENCE_COLORS = {
    0: ("Red", "#FF0000"),
    1: ("Orange", "#FFA500"),
    2: ("Yellow", "#FFFF00"),
    3: ("Light Green", "#90EE90"),
    4: ("Dark Green", "#008000"),
}

class TransliterationFrame(ttk.Frame):
    def __init__(self, parent, frame, *args, **kwargs):
        """
        The main transliteration frame.
        The same text widget is used for transliteration input and searching.
        """
        super().__init__(frame, *args, **kwargs)
        self.parent = parent  # Parent should support attributes like currentSelection, boxes, etc.
        
        # Boolean options
        self.lock_var = BooleanVar(value=False)
        self.view_connections_var = BooleanVar(value=True)
        self.multi_select_var = BooleanVar(value=True)
        self.show_addresses_var = BooleanVar(value=False)
        self.show_transliteration_var = BooleanVar(value=False)
        self.show_labels_var = BooleanVar(value=False)

        
        # Widgets and image labels
        self.info_label = None
        self.info_image = None
        self.info_split_image = None
        self.transcription_text = None
        self.selected_confidence = None
        self.selected_glyph = None

        
        self.corpus_transliterations = self.load_corpus_transliterations()
        
        self._create_widgets()

    def _create_widgets(self):
        # --- Top area: info label and images ---
        self.info_label = ttk.Label(self, text="Hover over a glyph", anchor="w")
        self.info_label.pack(fill="x", padx=5, pady=5)
        
        self.info_image = ttk.Label(self)
        self.info_image.pack(fill="x", padx=5, pady=5)
        
        self.info_split_image = ttk.Label(self)
        self.info_split_image.pack(fill="x", padx=5, pady=5)
        
        # --- Checkboxes ---
        checkbox_frame = ttk.Frame(self)
        checkbox_frame.pack(fill="x", padx=5, pady=5)
        
        lock_check = ttk.Checkbutton(checkbox_frame, text="Lock", variable=self.lock_var)
        lock_check.pack(side="top", anchor="w")
        
        view_conn_check = ttk.Checkbutton(
            checkbox_frame, text="View Connections",
            variable=self.view_connections_var,
            command=self.on_view_connections_checkbox
        )
        view_conn_check.pack(side="top", anchor="w")
        
        multi_select_check = ttk.Checkbutton(
            checkbox_frame, text="Enable Multi-Selection",
            variable=self.multi_select_var
        )
        multi_select_check.pack(side="top", anchor="w")

        show_addresses_check = ttk.Checkbutton(
            checkbox_frame, text="Show Addresses",
            variable=self.show_addresses_var,
            command=self.on_show_addresses_checkbox
        )
        show_addresses_check.pack(side="top", anchor="w")
                
                
        show_tran_check = ttk.Checkbutton(
            checkbox_frame, text="Show Transliteration",
            variable=self.show_transliteration_var,
            command=self.on_show_transliteration_checkbox
        )
        show_tran_check.pack(side="top", anchor="w")

        show_labels_check = ttk.Checkbutton(
            checkbox_frame, text="Show Labels",
            variable=self.show_labels_var,
            command=self.on_show_labels_checkbox
        )
        show_labels_check.pack(side="top", anchor="w")

        
        # --- Transcription / Search Input ---
        transcription_frame = ttk.Frame(self)
        transcription_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(transcription_frame, text="Transliteration:", font=("Helvetica", 12)
             ).pack(side="top", anchor="w")
        
        self.transcription_text = Text(transcription_frame, font=("Helvetica", 12), width=20, height=2)
        self.transcription_text.pack(fill="x", padx=5, pady=5)
        # Bind key release so that every keystroke triggers our combined update:
        self.transcription_text.bind("<KeyRelease>", self.update_transcription)
        
        ttk.Label(self, text="Confidence (0-4):", font=("Helvetica", 12)).pack(side="top", anchor="w")
    
        confidence_frame = ttk.Frame(self)
        confidence_frame.pack(fill="x", padx=5, pady=5)
        
        self.selected_confidence = 4  # Default confidence level
        self.confidence_buttons = {}  # Store button references
    
        for level, (text, color) in CONFIDENCE_COLORS.items():
            btn = tk.Button(
                confidence_frame,
                text=f"{level}",  # Display number
                bg=color,  # Set background color
                fg="black",
                width=4, height=2,
                command=lambda lvl=level: self.set_confidence_level(lvl, update = True)
            )
            btn.pack(side="left", padx=3)
            self.confidence_buttons[level] = btn  # Store button reference

        save_button = ttk.Button(
            transcription_frame, 
            text="Save to All Selected Glyphs", 
            command=self.save_transliteration_to_all
        )
        save_button.pack(side="top", padx=5, pady=10)

        alt_label = ttk.Label(self, text="Alternate Transliterations:", font=("Helvetica", 12))
        alt_label.pack(anchor="w", padx=5, pady=(10, 0))

        alt_button_frame = ttk.Frame(self)
        alt_button_frame.pack(fill="x", padx=5, pady=5)
        
        button_add_alt = tk.Button(alt_button_frame, text="Add", font=("Helvetica", 12), command=self.add_alternate)
        button_add_alt.pack(side="left", expand=True, fill="x", padx=5)
        
        button_remove_alt = tk.Button(alt_button_frame, text="Remove", font=("Helvetica", 12), command=self.remove_alternate)
        button_remove_alt.pack(side="left", expand=True, fill="x", padx=5)
        
        button_swap_alt = tk.Button(alt_button_frame, text="Swap", font=("Helvetica", 12), command=self.swap_preferred_with_alternate)
        button_swap_alt.pack(side="left", expand=True, fill="x", padx=5)
        

        self.alternate_listbox = tk.Listbox(self, font=("Helvetica", 12), height=5)
        self.alternate_listbox.pack(fill="both", padx=5, pady=5, expand=True)

        label_section = ttk.Label(self, text="Labels:", font=("Helvetica", 12))
        label_section.pack(anchor="w", padx=5, pady=(10, 0))
        
        label_button_frame = ttk.Frame(self)
        label_button_frame.pack(fill="x", padx=5, pady=5)
        
        button_add_label = tk.Button(label_button_frame, text="Add", font=("Helvetica", 12), command=self.add_label)
        button_add_label.pack(side="left", expand=True, fill="x", padx=2)
        
        button_remove_label = tk.Button(label_button_frame, text="Remove", font=("Helvetica", 12), command=self.remove_label)
        button_remove_label.pack(side="left", expand=True, fill="x", padx=2)
        
        button_add_label_all = tk.Button(label_button_frame, text="Add to All", font=("Helvetica", 12), command=self.add_label_to_all)
        button_add_label_all.pack(side="left", expand=True, fill="x", padx=2)
        
        button_remove_label_all = tk.Button(label_button_frame, text="Remove from All", font=("Helvetica", 12), command=self.remove_label_from_all)
        button_remove_label_all.pack(side="left", expand=True, fill="x", padx=2)
        
        self.label_listbox = tk.Listbox(self, font=("Helvetica", 12), height=5)
        self.label_listbox.pack(fill="both", padx=5, pady=5, expand=True)


    def add_label(self):
        if not self.selected_glyph or len(self.parent.currentSelection.glyphs) != 1:
            messagebox.showerror("Error", "Please select exactly one glyph to add a label.")
            return
    
        label = simpledialog.askstring("Add Label", "Enter new label:")
        if not label:
            return
    
        addr = self.selected_glyph.glyph.address
        if addr:
            glyph_data = GlyphEditorWindow.corpus_transliterations.setdefault(addr, {})
            labels = glyph_data.setdefault("labels", [])
    
            if label not in labels:
                labels.append(label)
                self.label_listbox.insert(tk.END, label)
                GlyphEditorWindow.save_transcriptions()

    def remove_label(self):
        if not self.selected_glyph or len(self.parent.currentSelection.glyphs) != 1:
            messagebox.showerror("Error", "Please select exactly one glyph to remove a label.")
            return
    
        try:
            index = self.label_listbox.curselection()[0]
            label = self.label_listbox.get(index)
            self.label_listbox.delete(index)
    
            addr = self.selected_glyph.glyph.address
            if addr:
                glyph_data = GlyphEditorWindow.corpus_transliterations.get(addr, {})
                labels = glyph_data.get("labels", [])
    
                if label in labels:
                    labels.remove(label)
                    GlyphEditorWindow.save_transcriptions()
        except IndexError:
            messagebox.showerror("Error", "Please select a label to remove.")

    def add_label_to_all(self):
        label = simpledialog.askstring("Add Label to All", "Enter label to add to all selected glyphs:")
        if not label:
            return
    
        updated = 0
        for glyph_box in self.parent.currentSelection.glyphs:
            addr = glyph_box.glyph.address if glyph_box.glyph else None
            if not addr:
                continue
    
            glyph_data = GlyphEditorWindow.corpus_transliterations.setdefault(addr, {})
            labels = glyph_data.setdefault("labels", [])
            if label not in labels:
                labels.append(label)
                updated += 1
    
        if updated > 0:
            GlyphEditorWindow.save_transcriptions()
            print(f"✅ Added label '{label}' to {updated} glyphs.")
        else:
            print("ℹ️ No changes made.")

    def remove_label_from_all(self):
        label = simpledialog.askstring("Remove Label from All", "Enter label to remove from all selected glyphs:")
        if not label:
            return
    
        updated = 0
        for glyph_box in self.parent.currentSelection.glyphs:
            addr = glyph_box.glyph.address if glyph_box.glyph else None
            if not addr:
                continue
    
            glyph_data = GlyphEditorWindow.corpus_transliterations.get(addr, {})
            labels = glyph_data.get("labels", [])
            if label in labels:
                labels.remove(label)
                updated += 1
    
        if updated > 0:
            GlyphEditorWindow.save_transcriptions()
            print(f"✅ Removed label '{label}' from {updated} glyphs.")
        else:
            print("ℹ️ Label not found on any selected glyphs.")





    def on_show_addresses_checkbox(self):
        """Show or hide address labels for all glyphs."""
        for box in self.parent.boxes:
            if self.show_addresses_var.get():
                box.repaint(force=True)
            else:
                box.remove_address_label()

    def add_alternate(self):
        """Adds an alternate transliteration for the currently selected glyph."""
        # Ensure exactly one glyph is selected
        if not self.selected_glyph or len(self.parent.currentSelection.glyphs) != 1:
            messagebox.showerror("Error", "Please select exactly one glyph to add an alternate transliteration.")
            return
    
        alt_text = simpledialog.askstring("Add Alternate", "Enter new alternate transliteration:")
        if not alt_text:
            return  # If input is empty, do nothing
    
        addr = self.selected_glyph.glyph.address
        if addr:
            glyph_data = GlyphEditorWindow.corpus_transliterations.setdefault(addr, {})
            alternates = glyph_data.setdefault("alternates", [])
    
            if alt_text not in alternates:
                alternates.append(alt_text)
                self.alternate_listbox.insert(tk.END, alt_text)
                GlyphEditorWindow.save_transcriptions()  # Persist the change


    def remove_alternate(self):
        """Removes the selected alternate transliteration from the currently selected glyph."""
        # Ensure exactly one glyph is selected
        if not self.selected_glyph or len(self.parent.currentSelection.glyphs) != 1:
            messagebox.showerror("Error", "Please select exactly one glyph to remove an alternate transliteration.")
            return
    
        try:
            index = self.alternate_listbox.curselection()[0]
            alt_text = self.alternate_listbox.get(index)
            self.alternate_listbox.delete(index)
    
            addr = self.selected_glyph.glyph.address
            if addr:
                glyph_data = GlyphEditorWindow.corpus_transliterations.get(addr, {})
                alternates = glyph_data.get("alternates", [])
                
                if alt_text in alternates:
                    alternates.remove(alt_text)
                    GlyphEditorWindow.save_transcriptions()  # Persist the change
        except IndexError:
            messagebox.showerror("Error", "Please select an alternate transliteration to remove.")


    def swap_preferred_with_alternate(self):
        """Swaps the preferred transliteration with a selected alternate transliteration."""
        # Ensure exactly one glyph is selected
        if not self.selected_glyph or len(self.parent.currentSelection.glyphs) != 1:
            messagebox.showerror("Error", "Please select exactly one glyph to swap transliteration.")
            return
    
        try:
            index = self.alternate_listbox.curselection()[0]
            alt_value = self.alternate_listbox.get(index)
            preferred_value = self.transcription_text.get("1.0", "end-1c").strip()
    
            # Update the text box
            self.transcription_text.delete("1.0", tk.END)
            self.transcription_text.insert("1.0", alt_value)
    
            # Update the listbox
            self.alternate_listbox.delete(index)
            self.alternate_listbox.insert(index, preferred_value)
    
            addr = self.selected_glyph.glyph.address
            if addr:
                glyph_data = GlyphEditorWindow.corpus_transliterations.setdefault(addr, {})
    
                # Swap values in the dictionary
                glyph_data["transliteration"] = alt_value
                alternates = glyph_data.setdefault("alternates", [])
                if preferred_value not in alternates:
                    alternates.append(preferred_value)
                if alt_value in alternates:
                    alternates.remove(alt_value)  # Avoid duplicate storage
    
                GlyphEditorWindow.save_transcriptions()  # Persist the change
    
                # Ensure the glyph UI updates
                if hasattr(self.selected_glyph, "repaint"):
                    self.selected_glyph.repaint()
        except IndexError:
            messagebox.showerror("Error", "Please select an alternate transliteration to swap.")


    def set_confidence_level(self, level=None, update = True):
        """Update the selected confidence level and apply changes."""
        self.selected_confidence = level  # Store selected value (can be None)

        if(level == None):
            self.selected_confidence = 4
            level = 4
        
        # Reset all button appearances
        for lvl, btn in self.confidence_buttons.items():
            btn.config(relief="raised")  # Reset all buttons
    
        # Highlight selected button only if confidence level is not None
        if level is not None and level in self.confidence_buttons:
            self.confidence_buttons[level].config(relief="sunken")

        if(update):
            self.update_transcription()
    

    def save_transliteration_to_all(self):
        """
        Saves the current transliteration and confidence to all selected glyphs.
        """
        text_val = self.transcription_text.get("1.0", "end-1c").strip()
        if not text_val:
            print("❌ No transliteration text to save.")
            return
    
        try:
            confidence_val = self.selected_confidence
        except ValueError:
            print("❌ Invalid confidence value.")
            return
    
        # Apply transliteration to all selected glyphs
        affected_glyphs = []
        for glyph_box in self.parent.currentSelection.glyphs:
            if glyph_box.glyph and glyph_box.glyph.address:
                addr = glyph_box.glyph.address
                prev_data = GlyphEditorWindow.corpus_transliterations.get(addr, {})
                prev_translit = prev_data.get("transliteration", "")
                prev_conf = prev_data.get("confidence", 5)
    
                # Only update if something has changed
                if prev_translit != text_val or prev_conf != confidence_val:
                    GlyphEditorWindow.corpus_transliterations[addr] = {
                        "transliteration": text_val,
                        "confidence": confidence_val
                    }
                    affected_glyphs.append(glyph_box)
    
        # Save if there were any changes
        if affected_glyphs:
            GlyphEditorWindow.save_transcriptions()
            print(f"✅ Saved transliteration to {len(affected_glyphs)} glyphs.")
        else:
            print("ℹ️ No changes to save.")
    
        # Update display for affected glyphs
        for glyph_box in affected_glyphs:
            if self.show_transliteration_var.get():
                glyph_box.repaint(force=True)
            else:
                glyph_box.remove_transliteration_label()
    
    def on_view_connections_checkbox(self):
        self.parent.repaint()
    
    def on_show_transliteration_checkbox(self):
        show_tr = self.show_transliteration_var.get()
    
        # If turning transliteration on, turn labels off
        if show_tr and self.show_labels_var.get():
            self.show_labels_var.set(False)
    
        # Repaint all glyph boxes based on new settings
        self.parent.repaint()
    
    
    def on_show_labels_checkbox(self):
        show_labels = self.show_labels_var.get()
    
        # If turning labels on, turn transliteration off
        if show_labels and self.show_transliteration_var.get():
            self.show_transliteration_var.set(False)
    
        # Repaint all glyph boxes based on new settings
        self.parent.repaint()
    

    
    def load_corpus_transliterations(self):
        """Load transliterations from JSON file for search purposes."""
        filename = "corpus_transliterations.json"
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"✅ Loaded {len(data)} corpus transliterations.")
                return data
            except Exception as e:
                print(f"❌ Failed to load corpus transliterations: {e}")
        return {}

    def resize_image_with_aspect_ratio(self, img, max_size):
        """Resize an image while maintaining its aspect ratio."""
        w, h = img.size
        aspect = w / h
        if aspect > 1:
            new_w = max_size
            new_h = int(max_size / aspect)
        else:
            new_h = max_size
            new_w = int(max_size * aspect)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    
    def on_result_click(self, transliteration):
        """
        When a search result is clicked, update the text widget and process the change.
        """
        self.transcription_text.delete("1.0", tk.END)
        self.transcription_text.insert("1.0", transliteration)
        self.update_transcription()
    
    def update_transcription(self, event=None):
        """
        Updates the transliteration (if a glyph is selected)
        """
        text_val = self.transcription_text.get("1.0", "end-1c").strip()

        
        if not text_val:
            return
        
        # If exactly one glyph is selected, update its transliteration
        if len(self.parent.currentSelection.glyphs) != 1:
            return
    
        if not self.selected_glyph:
            return  # Prevent updates if no valid glyph is selected
        
        try:
            confidence_val = self.selected_confidence
        except ValueError:
            return  # Prevent errors if confidence selection fails
    
        addr = self.selected_glyph.glyph.address
        prev_data = GlyphEditorWindow.corpus_transliterations.get(addr, {})
        prev_translit = prev_data.get("transliteration", "")
        prev_conf = prev_data.get("confidence", 5)
    
        # Only update if something has changed
        if prev_translit != text_val or prev_conf != confidence_val:
            GlyphEditorWindow.corpus_transliterations[addr] = {
                "transliteration": text_val,
                "confidence": confidence_val
            }
            GlyphEditorWindow.save_transcriptions()  # Save updated data
    
            # Trigger UI repaint if transliteration is shown
            if self.show_transliteration_var.get():
                print("self.selected_glyph.repaint(force=True)")
                self.selected_glyph.repaint(force=True)
            else:
                self.selected_glyph.remove_transliteration_label()
    
    def update_top_panel(self, glyph_box=None, text=None, glyph_image=None, split_image=None):
        """
        Updates the top info panel (e.g., when hovering over a glyph).
        """

        self.selected_glyph = glyph_box # Store the currently selected glyph

        if not hasattr(glyph_box, "glyph"):
            self.selected_glyph = None
            return

        if self.selected_glyph is None:
            self.alternate_listbox.delete(0, tk.END)  # Clear alternates list
            return

        if glyph_box is None or glyph_box.glyph is None:
            self.selected_glyph = None
            return  # If no valid glyph, reset selection and exit
        
        if not self.selected_glyph:
            return  # Prevent updates if no single glyph is selected
        
                
        if glyph_box is not None:
            addr = glyph_box.glyph.address if glyph_box.glyph and glyph_box.glyph.address else ""
            glyph_data = GlyphEditorWindow.corpus_transliterations.get(addr, {})
            translit = glyph_data.get("transliteration", "").strip()
            confidence = glyph_data.get("confidence", None) if translit else None  # No transliteration = No button selected

            self.info_label.config(text=f"Address: {addr} | Transliteration: {translit}")
            
            if self.show_addresses_var.get():
                self.selected_glyph.update_address_label()
            else:
                self.selected_glyph.remove_address_label()

            self.transcription_text.delete("1.0", "end")
            self.transcription_text.insert("1.0", translit)

            self.set_confidence_level(confidence, update = False)  # Set to None if translit is empty

            # ✅ Update the Listbox with alternates
            self.alternate_listbox.delete(0, tk.END)  # Clear previous list
            alternates = glyph_data.get("alternates", [])  # Retrieve stored alternates
            for alt in alternates:
                self.alternate_listbox.insert(tk.END, alt)  # Populate listbox with alternates

            # Update label listbox
            self.label_listbox.delete(0, tk.END)
            labels = glyph_data.get("labels", [])
            for label in labels:
                self.label_listbox.insert(tk.END, label)

                    
            try:
                tk_glyph_image = ImageTk.PhotoImage(glyph_box.image)
                self.info_image.config(image=tk_glyph_image)
                self.info_image.image = tk_glyph_image
            except Exception as e:
                print(f"Error updating glyph image: {e}")
            
        else:
            if text is not None:
                self.info_label.config(text=text)
            if glyph_image is not None:
                try:
                    tk_glyph_image = ImageTk.PhotoImage(glyph_image)
                    self.info_image.config(image=tk_glyph_image)
                    self.info_image.image = tk_glyph_image
                except Exception as e:
                    print(f"Error updating glyph image: {e}")
            if split_image is not None:
                try:
                    tk_split_image = ImageTk.PhotoImage(split_image)
                    self.info_split_image.config(image=tk_split_image)
                    self.info_split_image.image = tk_split_image
                except Exception as e:
                    print(f"Error updating split glyph image: {e}")
