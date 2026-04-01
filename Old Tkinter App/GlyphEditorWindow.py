import os
import re
import logging
import numpy as np
from msilib.schema import SelfReg
import io
import tkinter as tk
from tkinter import ttk, filedialog
from tkinter import simpledialog
import tkinter.font as tkFont
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import ImageDraw
from PIL import Image, ImageTk

import KohauCode_Horley
import embeddings
import transliteration_frame
import glyph_search_frame
from search_popup import SearchPopup


corpus=KohauCode_Horley.Corpus()
corpus.load()

allGlyphs = []
for tablet in corpus.tablets:  # Iterate over tablets in load order
    allGlyphs.extend(tablet.glyphs)  # Append glyphs in their stored order


def interpolate_color(confidence):

    if(confidence == None):
        confidence = -1

    if(confidence > 4):
        confidence = 4
        
    return transliteration_frame.CONFIDENCE_COLORS.get(confidence, ('blue',"#0000FF"))[0]  # Default to black if out of range

from PIL import ImageFont

def _render_label_pil(text, fontsize=42, color=(31, 77, 227)):  # blue
    # Try Times New Roman on Windows, then fall back.
    font = None
    font_candidates = [
        r"C:\Windows\Fonts\times.ttf",
        r"C:\Windows\Fonts\timesbd.ttf",
        r"C:\Windows\Fonts\Times.ttf",
        r"C:\Windows\Fonts\Times New Roman.ttf",
        r"C:\Windows\Fonts\timesi.ttf",
    ]
    for fp in font_candidates:
        try:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, fontsize)
                break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    # measure
    tmp = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    bbox = d.textbbox((0, 0), text, font=font)
    w = max(1, bbox[2] - bbox[0])
    h = max(1, bbox[3] - bbox[1])

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((-bbox[0], -bbox[1]), text, font=font, fill=color)
    return img


import json

# Global dictionary for glyph transliterations.
corpus_transliterations = {}

import shutil
from datetime import datetime

def load_corpus_transliterations(filename="corpus_transliterations.json"):
    global corpus_transliterations
    
    if os.path.exists(filename):
        # ✅ Create a timestamped backup before loading
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"transliterations_backup_{timestamp}.json"
        shutil.copy(filename, backup_filename)
        print(f"📝 Backup created: {backup_filename}")

        # ✅ Load the transliterations
        try:
            with open(filename, "r", encoding="utf-8") as f:
                corpus_transliterations = json.load(f)
            print(f"✅ Loaded {len(corpus_transliterations)} transliterations from {filename}")
        except Exception as e:
            print(f"❌ Error loading corpus_transliterations: {e}")
    else:
        corpus_transliterations = {}
        print("⚠️ transliterations.json not found. Starting with an empty dictionary.")


load_corpus_transliterations()

def save_transcriptions():
    try:
        with open("corpus_transliterations.json", "w", encoding="utf-8") as f:
            json.dump(corpus_transliterations, f, indent=2)
        print("Transcriptions saved instantly to transcriptions.json.")
    except Exception as e:
        print(f"Error saving transcriptions: {e}")


def create_circle(x, y, r, parent): #center coordinates, radius
    x0 = x - r
    y0 = y - r
    x1 = x + r
    y1 = y + r
    parent.canvas.delete(parent.MouseCircle)
    parent.MouseCircle=parent.canvas.create_oval(x0, y0, x1, y1)

globalGlyphCounter=0
SCALE_THRESHOLD = 0.25

class BaseBox():

    def __init__(self,parent):

        self.parent=parent
        self.x=0
        self.y=0
        self.linkedBoxes=[]
        self.notes=[]

    def linkto(self,box):
        
        if(box not in self.linkedBoxes):
            
            self.linkedBoxes.append(box)

    def bounds(self):
        return self.x,self.x,self.y,self.y

    def moved(self):
        return True
    
    def scaled(self):
        return self.parent.view.scale!=self.renderScale

    def getWidth(self, absolute=False):
        return 0

    def getHeight(self, absolute=False):
        return 0

    import math

    def draw_connecting_line(self, box, use_curved_line=True):

        current_scale = self.parent.view.scale
        if current_scale < SCALE_THRESHOLD:
            return
            
        import math
        """
        Draws a connecting line (either straight or cosine-curved) between self and box.
    
        :param box: The other element to connect to.
        :param use_curved_line: If True, draw a cosine-shaped curve; otherwise a straight line.
        """
    
        # Get bounding boxes for each object (as you already do).
        xl_1, yl_1, xh_1, yh_1 = self.bounds()
        xl_2, yl_2, xh_2, yh_2 = box.bounds()
    
        # Convert object coords to the canvas coords.
        x, y = self.parent.view.getCoords(self.x, self.y)
        x1, y1 = self.parent.view.getCoords(box.x, box.y)
    
        # Same orientation logic as your original snippet.
        # Check whether we are connecting side-to-side (horizontal overlap)
        # or top-to-bottom (vertical overlap).
        if yl_1 < yl_2 < yh_1 or yl_2 < yl_1 < yh_2:
            # -- SIDE-TO-SIDE connection --
    
            # Adjust so that connections "come out" from left/right edges
            y += self.getHeight() * 0.5
            y1 += box.getHeight() * 0.5
            if x > x1:
                x1 += box.getWidth()
            else:
                x += self.getWidth()
    
            # If not using the curved line, just draw a straight line:
            if not use_curved_line:
                line_id = self.parent.canvas.create_line(x, y, x1, y1, fill="blue", width=5)
                self.link_components.append(line_id)
                return
    
            # Otherwise, draw y = cos(x) from x->x1, y->y1 via param s in [0, pi].
            # The domain in s is [0, pi]. We'll sample points along s,
            # transform them so that the final endpoints match (x, y) and (x1, y1).
    
            # We'll name them (Xstart, Ystart) = (x, y)  and (Xend, Yend) = (x1, y1)
            Xstart, Ystart = x, y
            Xend,   Yend   = x1, y1
    
            # We want:
            #   x(s) = Xstart + (Xend - Xstart)*(s/pi)
            #   y(s) = A*cos(s) + B
            # where:
            #   y(0) = Ystart  => A*cos(0) + B = A + B = Ystart
            #   y(pi) = Yend   => A*cos(pi)+ B = -A + B = Yend
            # Solve:
            #   A + B = Ystart
            #  -A + B = Yend
            # =>  B = (Ystart + Yend)/2
            #     A = (Ystart - Yend)/2
            A = (Ystart - Yend) / 2.0
            B = (Ystart + Yend) / 2.0
    
            # Create a list of (x_i, y_i) points to feed create_line().
            # We'll discretize s from 0.pi with N steps.
            N = 50
            points = []
            for i in range(N + 1):
                s = (math.pi * i) / N
                x_s = Xstart + (Xend - Xstart)*(s/math.pi)
                y_s = A*math.cos(s) + B
                points.extend([x_s, y_s])
    
            line_id = self.parent.canvas.create_line(
                points, fill="black", width=2
            )
            self.link_components.append(line_id)
    
        else:
            # -- TOP-TO-BOTTOM connection --
    
            # Adjust so that connections come out from top/bottom edges
            x += self.getWidth() * 0.5
            x1 += box.getWidth() * 0.5
            if y > y1:
                y1 += box.getHeight()
            else:
                y += self.getHeight()
    
            # If not using the curved line, just draw a straight line:
            if not use_curved_line:
                line_id = self.parent.canvas.create_line(x, y, x1, y1, fill="black", width=2)
                self.link_components.append(line_id)
                return
    
            # Otherwise, draw x = cos(y) from (x,y) to (x1,y1).
            # We'll parameterize from s in [0, pi] with:
            #   y(s) = Ystart + (Yend - Ystart)*(s/pi)
            #   x(s) = A*cos(s) + B
            # subject to x(0) = Xstart, x(pi) = Xend.
    
            Xstart, Ystart = x,  y
            Xend,   Yend   = x1, y1
    
            # Solve for A,B in x(s) = A*cos(s) + B:
            #   x(0) = Xstart = A + B
            #   x(pi) = Xend  = -A + B
            # => B = (Xstart + Xend)/2
            #    A = (Xstart - Xend)/2
            A = (Xstart - Xend) / 2.0
            B = (Xstart + Xend) / 2.0
    
            # Build up the point list
            N = 50
            points = []
            for i in range(N + 1):
                s = (math.pi * i) / N
                y_s = Ystart + (Yend - Ystart)*(s/math.pi)
                x_s = A*math.cos(s) + B
                points.extend([x_s, y_s])
    
            line_id = self.parent.canvas.create_line(
                points, fill="black", width=2
            )
            self.link_components.append(line_id)



    def paint_links(self, force=False, secondaryForce=False):
        if not self.parent.transliteration_frame.view_connections_var.get():
            # If toggled off, remove existing lines but do not redraw them
            self._delete_link_components()  # or loop and delete
            return
    
        if self.moved() or self.scaled() or force:
            # Delete existing link components only if changes occurred
            for comp in self.link_components:
                self.parent.canvas.delete(comp)
            self.link_components = []
         
            # Only redraw links if the box is in frame
            if self.inFrame():
                for linkedGlyph in self.linkedBoxes:
                    self.draw_connecting_line(linkedGlyph)
        # DO NOT delete the link components when nothing has changed.
        if force and not secondaryForce:
            for g in self.linkedBoxes:
                g.paint_links(force=True, secondaryForce=True)


    
    def _delete_link_components(self):
        print(f"Deleting link components for {self}")
        for comp in self.link_components:
            print(f"Deleting component {comp}")
            self.parent.canvas.delete(comp)
        self.link_components = []

    def delete(self):
        self.parent.canvas.delete(self.canvasObject)
        for comp in self.link_components:
            self.parent.canvas.delete(comp)
        self.link_components = []

import hashlib
import colorsys

def seed_to_bright_hex(seed: str) -> str:
    # Hash the string seed to get a deterministic number
    hash_value = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    
    # Map to HSL space: Hue (0-360), Saturation (60-100%), Lightness (50-80%)
    hue = (hash_value % 360) / 360  # Normalize hue to [0,1]
    saturation = 0.6 + (hash_value % 40) / 100  # Keep it in a bright range [0.6, 1.0]
    lightness = 0.5 + (hash_value % 30) / 100   # Keep it non-black/white [0.5, 0.8]

    # Convert to RGB
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)

    # Convert to hex
    return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'
    
class CompoundBox(BaseBox):


    def __init__(self, boxes, title, parent):
        """
        A compound box groups several boxes and paints a rectangle around them with a title.
        
        :param boxes: List of box objects (glyphBox, textBox, etc.)
        :param title: The title for this compound group.
        :param parent: The parent (typically your glyphWindow) to access the canvas and view.
        """
        super().__init__(parent)
        self.boxes = boxes
        self.title = title
        self.rect_id = None
        self.title_id = None
        self.link_components = []
        self.boxIndex = parent.get_unique_boxIndex()
        self.color = seed_to_bright_hex(title)

        nice_labels_with_colors = {
            "No Agreement": "#d3d3d3",  # Gray for No Agreement
            "Full Agreement": "#ffff66",
            "Unsorted (H)": "#ff9999", 
            "Stylistic (H)": "#ff6666", 
            "Additions (H)": "#ff3333", 
            "Deletions (H)": "#cc0000",
            "Unsorted (P)": "#99ccff", 
            "Stylistic (P)": "#6699ff", 
            "Additions (P)": "#3366ff", 
            "Deletions (P)": "#0033cc",
            "Unsorted (Q)": "#99ff99", 
            "Stylistic (Q)": "#66cc66", 
            "Additions (Q)": "#339933", 
            "Deletions (Q)": "#006600",
        }

        if(title in nice_labels_with_colors):
            self.color = nice_labels_with_colors[title]
        

    def inFrame(self):
        """
        Determines if the CompoundBox is within the visible canvas area.
        """
        if not self.boxes:
            return False  # No boxes to check
    
        canvas_width = self.parent.canvas.winfo_width()
        canvas_height = self.parent.canvas.winfo_height()
        
        min_x, min_y, max_x, max_y = self.get_bounds()
        canvas_min_x, canvas_min_y = self.parent.view.getCoords(min_x, min_y)
        canvas_max_x, canvas_max_y = self.parent.view.getCoords(max_x, max_y)
    
        # Check if any part of the bounding box is in the visible area
        return (
            canvas_max_x > 0 and canvas_min_x < canvas_width and
            canvas_max_y > 0 and canvas_min_y < canvas_height
        )

    def inside(self, x, y):
        """
        Checks if a point (x, y) is inside the bounding box of this CompoundBox.
        """
        bounds = self.get_bounds()
        if bounds is None:
            return False
    
        min_x, min_y, max_x, max_y = bounds
        return min_x <= x <= max_x and min_y <= y <= max_y

    def get_bounds(self):
        """
        Compute the bounding rectangle that encloses all boxes.
        Returns (min_x, min_y, max_x, max_y) in logical coordinates.
        """
        if not self.boxes:
            return None
        min_x = min(box.x for box in self.boxes)
        min_y = min(box.y for box in self.boxes)
        max_x = max(box.x + box.getWidth(absolute=True) for box in self.boxes)
        max_y = max(box.y + box.getHeight(absolute=True) for box in self.boxes)
        return min_x, min_y, max_x, max_y

    def delete(self):
        if self.rect_id is not None:
            self.parent.canvas.delete(self.rect_id)
        if self.title_id is not None:
            self.parent.canvas.delete(self.title_id)

    def repaint(self, force=False):

        # 4) Get the current scale for rendering
        current_scale = self.parent.view.scale
    
        # 5) Render a small dot or the glyph image
        if current_scale < SCALE_THRESHOLD:
            if self.rect_id is not None:
                self.parent.canvas.delete(self.rect_id)
            if self.title_id is not None:
                self.parent.canvas.delete(self.title_id)
            return
                
        """
        Paint the compound box: draw a rectangle around the contained boxes and
        the title text above it.
        """
        # Remove previous drawings if any.
        if self.rect_id is not None:
            self.parent.canvas.delete(self.rect_id)
        if self.title_id is not None:
            self.parent.canvas.delete(self.title_id)

        bounds = self.get_bounds()
        if bounds is None:
            return

        min_x, min_y, max_x, max_y = bounds
        # Convert logical coordinates to canvas coordinates.
        canvas_min_x, canvas_min_y = self.parent.view.getCoords(min_x, min_y)
        canvas_max_x, canvas_max_y = self.parent.view.getCoords(max_x, max_y)

        # Draw the rectangle around the group.
        self.rect_id = self.parent.canvas.create_rectangle(
            canvas_min_x, canvas_min_y, canvas_max_x, canvas_max_y,
            outline=self.color, width=2
        )


        # Get font settings from transliteration_frame
        font_size = max(10, int(18 * self.parent.view.scale))
        font_str = f"Helvetica {font_size} bold"
    
        # Position the title above the compound box
        text_x = canvas_min_x + (canvas_max_x - canvas_min_x) // 2
        text_y = canvas_min_y - (font_size/5 + 30 * self.parent.view.scale)
    
        self.title_id = self.parent.canvas.create_text(
            text_x, text_y,
            text=self.title, anchor="n",
            fill=self.color, font=font_str
        )



from PIL import ImageColor

class glyphBox(BaseBox):
    
    def __init__(self,parent,x=0,y=0,image=-1,glyph=None):
        
        self.x=x
        self.y=y

        self.translated=False

        self.canvasImageId=-1
        self.parent=parent
        self.glyph=glyph
        self.imagefile=""
        self.boxIndex=-1

        self.linkedBoxes=[]
        self.link_components=[]

        self.renderedImage=None
        self.renderScale=-1
        
        self.image=image

        self.cachedRenders = {}
        
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.parent.images.append(self.tk_image)
        self.imageIndex=len(self.parent.images)-1
        self.isHighlighted=False
        
        self.repaint()
        #self.canvasImageId = canvas.create_image(self.x, self.y, image=IMAGE ,anchor = "nw")

    def get_xml(self):

        #import lxml.etree

        import lxml.builder    
        
        E = lxml.builder.ElementMaker()
        
        linkedAdresses=[]

        for g in self.linkedBoxes:
            linkedAdresses.append(g.boxIndex)

        address=None

        try:
            address=E.address(str(self.boxIndex))
        except:
            address=E.address("0")

        return E.glyphBox(

            E.imagefile(self.imagefile),
            E.position(str([self.x,self.y])),
            address,
            E.linkedComponents(str(linkedAdresses))

        )

    
    def match(self,glyph,doubleCheck=True):
        if(glyph in self.linkedBoxes):
            return True
        for g in self.linkedBoxes:
            if(g.boxIndex==glyph.boxIndex):
                return True
        if(doubleCheck):
            if(glyph.match(self,doubleCheck=False)):
                return True
        return False

    def bounds(self):
        return self.x,self.y,self.x+self.image.width,self.y+self.image.height
        
    def inside(self,x,y):
        
        return x>=self.x and y>=self.y and x<=self.x+self.image.width and y<=self.y+self.image.height
    
    def getWidth(self,absolute=False):

        if(absolute):
            return self.image.width
        else:
            return int(self.image.width*self.parent.view.scale)
    
    def getHeight(self,absolute=False):
        
        if(absolute):
            return self.image.height
        else:
            return int(self.image.height*self.parent.view.scale)

    def inFrame(self):
        grace_space = 100
        if self.renderedImage is not None:
            grace_space = self.renderedImage.width * 2
        canvas_width = self.parent.canvas.winfo_width()
        canvas_height = self.parent.canvas.winfo_height()  # Fixed here
        x, y = self.parent.view.getCoords(self.x, self.y)
        if x < canvas_width and y < canvas_height and x > -grace_space and y > -grace_space:
            return True
        return False
    

    def moved(self):

        if(self.parent.view.panning):

            return True

        return self.translated
    
    def delete(self):
        """Removes the glyph image and its associated transliteration label."""
        self.parent.canvas.delete(self.canvasImageId)
    
        # ✅ Remove associated transliteration label if it exists
        if self.boxIndex in self.parent.transliteration_ids:
            self.parent.canvas.delete(self.parent.transliteration_ids[self.boxIndex])
            del self.parent.transliteration_ids[self.boxIndex]
    
        # ✅ Remove linking components
        for comp in self.link_components:
            self.parent.canvas.delete(comp)
    
        self.link_components = []

    def remove_transliteration_label(self):
        """ Removes the transliteration label if it exists. """
        if self.boxIndex in self.parent.transliteration_ids:
            self.parent.canvas.delete(self.parent.transliteration_ids[self.boxIndex])
            del self.parent.transliteration_ids[self.boxIndex]
    

    def repaint(self, force=False):
        # 1) Clear previous components (including transliteration text)
       # for comp in self.parent.components:
        #    self.parent.canvas.delete(comp)
        #self.parent.components.clear()
    
        # 2) Determine if we need to repaint
        needs_repaint = force or self.moved() or self.scaled() or self.isHighlighted
        if not needs_repaint:
            return
    
        # 3) If the glyph is out of frame, remove it and return
        if not self.inFrame():
            self.parent.canvas.delete(self.canvasImageId)
            self.canvasImageId = -1
            self.remove_transliteration_label()
            self.remove_address_label()
            return
    
        # 4) Get the current scale for rendering
        current_scale = self.parent.view.scale
    
        # 5) Render a small dot or the glyph image
        if current_scale < SCALE_THRESHOLD:
            if self.canvasImageId != -1:
                self.parent.canvas.delete(self.canvasImageId)
                self.canvasImageId = -1
        
            # ✅ Adjust coordinates to center the dot inside the glyph box
            glyph_width = self.getWidth(absolute=True) // 2
            glyph_height = self.getHeight(absolute=True) // 2
            canvas_x, canvas_y = self.parent.view.getCoords(self.x + glyph_width, self.y + glyph_height)
        
            dot_radius = 1
            self.canvasImageId = self.parent.canvas.create_oval(
                canvas_x - dot_radius, canvas_y - dot_radius,
                canvas_x + dot_radius, canvas_y + dot_radius,
                fill="black", outline=""
            )
        
            self.remove_transliteration_label()
            self.remove_address_label()

        else:
            if current_scale != self.renderScale:
                new_width = max(1, int(self.image.width * current_scale))
                new_height = max(1, int(self.image.height * current_scale))
                quantized = quantize_scale(current_scale)
                if quantized not in self.cachedRenders:
                    resized = self.image.resize((new_width, new_height), Image.NEAREST)
                    self.cachedRenders[quantized] = resized
                self.renderedImage = self.cachedRenders[quantized]
                self.tk_image = ImageTk.PhotoImage(self.renderedImage)
                self.renderScale = current_scale
                self.parent.images[self.imageIndex] = self.tk_image
    
            if self.canvasImageId != -1:
                self.parent.canvas.delete(self.canvasImageId)
            canvas_x, canvas_y = self.parent.view.getCoords(self.x, self.y)
            self.canvasImageId = self.parent.canvas.create_image(
                canvas_x, canvas_y, image=self.tk_image, anchor="nw"
            )

            tf = self.parent.transliteration_frame

            # --- Labels vs Transliteration ---
            if tf.show_labels_var.get():
                # Show labels, hide transliteration
                self.update_label_label()
                self.remove_transliteration_label()
            else:
                # Show transliteration (if enabled), hide labels
                self.remove_label_label()
                
            if tf.show_transliteration_var.get():
                self.update_transliteration_label()
                self.remove_label_label()
            else:
                self.remove_transliteration_label()
            
            # --- Addresses (unchanged) ---
            if tf.show_addresses_var.get():
                self.update_address_label()
            else:
                self.remove_address_label()


    
        # 6) If highlighted, draw bounding box
        if self.isHighlighted:
            x1, y1 = self.parent.view.getCoords(self.x, self.y)
            x2, y2 = self.parent.view.getCoords(
                self.x + self.image.width, self.y + self.image.height
            )
            self.parent.components.append(
                self.parent.canvas.create_rectangle(x1, y1, x2, y2, outline="blue")
            )


    def update_address_label(self):
        """ Updates the address label displayed above the glyph. """
        if not (self.glyph and self.glyph.address):
            return  # No valid glyph or address
    
        glyph_addr = self.glyph.address[0]
    
        # If address should not be displayed, remove label
        if not self.parent.transliteration_frame.show_addresses_var.get():
            self.remove_address_label()
            return
    
        canvas_x, canvas_y = self.parent.view.getCoords(self.x, self.y)
        text_x = canvas_x + (self.getWidth() // 2)
        text_y = canvas_y - (10 * self.parent.view.scale)  # Address above the glyph
        font_size = max(10, int(18 * self.parent.view.scale))
        font_str = f"Helvetica {font_size} bold"
    
        if self.boxIndex in self.parent.address_ids:
            text_id = self.parent.address_ids[self.boxIndex]
            self.parent.canvas.coords(text_id, text_x, text_y)
            self.parent.canvas.itemconfig(text_id, text=glyph_addr, font=font_str, fill="black")
        else:
            text_id = self.parent.canvas.create_text(
                text_x, text_y, text=glyph_addr,
                font=font_str, fill="black", anchor="s",
                tags=("address_label",)
            )
            self.parent.address_ids[self.boxIndex] = text_id

    
    def update_label_label(self):
        """
        Draw labels_str (or joined labels) on the glyph, using the FULL JSON dataset
        loaded by TransliterationFrame.
        """
        addr = self.glyph.address if self.glyph else None
        if not addr:
            return
    
        # ✅ Load from the full JSON object, not GlyphEditorWindow!
        full_json = self.parent.transliteration_frame.corpus_transliterations
        data = full_json.get(addr, {})
    
        # Prefer labels_str, fall back to labels[]
        labels_str = (data.get("labels_str") or "").strip()
        if not labels_str:
            labels = data.get("labels", [])
            labels_str = ".".join(labels).strip()
    
        if not labels_str:
            self.remove_label_label()
            return
    
        # Coordinates
        canvas_x, canvas_y = self.parent.view.getCoords(self.x, self.y)
        text_x = canvas_x + (self.getWidth() // 2)
        text_y = canvas_y + self.getHeight() + (10 * self.parent.view.scale)
    
        font_size = max(10, int(18 * self.parent.view.scale))
        font_str = f"Helvetica {font_size} bold"
    
        # A place to store label overlay ids
        if not hasattr(self.parent, "label_ids"):
            self.parent.label_ids = {}
    
        # Create or update text
        if self.boxIndex in self.parent.label_ids:
            tid = self.parent.label_ids[self.boxIndex]
            self.parent.canvas.coords(tid, text_x, text_y)
            self.parent.canvas.itemconfig(tid, text=labels_str, font=font_str)
        else:
            tid = self.parent.canvas.create_text(
                text_x, text_y,
                text=labels_str,
                font=font_str,
                fill="black",
                anchor="n",
            )
            self.parent.label_ids[self.boxIndex] = tid

    
        
    def remove_label_label(self):
        if hasattr(self.parent, "label_ids") and self.boxIndex in self.parent.label_ids:
            tid = self.parent.label_ids[self.boxIndex]
            self.parent.canvas.delete(tid)
            del self.parent.label_ids[self.boxIndex]
    


    
    def remove_address_label(self):
        """ Removes the address label if it exists. """
        if self.boxIndex in self.parent.address_ids:
            self.parent.canvas.delete(self.parent.address_ids[self.boxIndex])
            del self.parent.address_ids[self.boxIndex]



    def update_transliteration_label(self):
        """
        Updates the transliteration text label displayed on the canvas for this glyph.
        If the glyph has a valid transliteration in the corpus_transliterations dictionary,
        it will be displayed above the glyph image.
        """
        
        #print("\n--- Running update_transliteration_label() ---")
        
        # Ensure the glyph object exists and has a valid address
        if not (self.glyph and self.glyph.address):
            print(f"[WARNING] GlyphBox at ({self.x}, {self.y}) has no associated glyph or address. Skipping update.")
            return
    
        glyph_addr = self.glyph.address
        print(f"[INFO] Checking transliteration for glyph address: {glyph_addr}")
    
        # Check if transliteration data exists in the global dictionary
        if glyph_addr not in corpus_transliterations:
            print(f"[WARNING] No transliteration found for {glyph_addr}. Removing any existing label.")
    
            # If a transliteration label exists for this glyph, remove it
            if self.boxIndex in self.parent.transliteration_ids:
                print(f"[INFO] Deleting transliteration label for boxIndex {self.boxIndex}")
                self.parent.canvas.delete(self.parent.transliteration_ids[self.boxIndex])
                del self.parent.transliteration_ids[self.boxIndex]
            return

        transliteration = corpus_transliterations[glyph_addr]['transliteration'].strip()
        confidence = corpus_transliterations[glyph_addr].get('confidence', 5)
        # Interpolate color (assume this helper is defined elsewhere):

        print(f"Updating label for glyph {glyph_addr} with transliteration '{transliteration}' and confidence {confidence}")

        
        text_color = interpolate_color(confidence)
        # Compute position for the transliteration label:
        canvas_x, canvas_y = self.parent.view.getCoords(self.x, self.y)
        text_x = canvas_x + (self.getWidth() // 2)
        text_y = canvas_y + self.getHeight() + (10 * self.parent.view.scale)
        font_size = max(10, int(18 * self.parent.view.scale))
        font_str = f"Helvetica {font_size} bold"

        # If a label already exists, update it; otherwise, create a new one.
        if self.boxIndex in self.parent.transliteration_ids:
            text_id = self.parent.transliteration_ids[self.boxIndex]
            self.parent.canvas.coords(text_id, text_x, text_y)
            self.parent.canvas.itemconfig(text_id, text=transliteration, font=font_str, fill=text_color)
        else:
            text_id = self.parent.canvas.create_text(
                text_x, text_y, text=transliteration,
                font=font_str, fill=text_color, anchor="n",
                tags=("transliteration",)
            )
            self.parent.transliteration_ids[self.boxIndex] = text_id



class imageBox(BaseBox):
    def __init__(self, parent, x=0, y=0, imagefile=""):
        self.x = x
        self.y = y
        self.translated = False
        self.canvasImageId = -1
        self.parent = parent
        self.imagefile = imagefile
        self.linkedBoxes = []
        self.link_components = []
        self.renderedImage = None
        self.renderScale = -1
        self.isHighlighted = False
        self.boxIndex = -1  # If needed for linking, otherwise remove

        # Load the image from the file
        try:
            self.image = Image.open(self.imagefile)
        except Exception as e:
            print(f"Error loading image {self.imagefile}: {e}")
            self.image = Image.new('RGB', (100, 100), color = 'red')  # Placeholder image

        self.cachedRenders = {}
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.parent.images.append(self.tk_image)
        self.imageIndex = len(self.parent.images) - 1

        self.repaint()

    def get_xml(self):
        import lxml.builder    
        E = lxml.builder.ElementMaker()
        linkedAddresses = [box.boxIndex for box in self.linkedBoxes]
        return E.imageBox(
            E.imagefile(self.imagefile),
            E.position(str([self.x, self.y])),
            E.linkedComponents(str(linkedAddresses))
        )

    def bounds(self):
        return self.x, self.y, self.x + self.image.width, self.y + self.image.height

    def inside(self, x, y):
        return self.x <= x <= self.x + self.image.width and self.y <= y <= self.y + self.image.height

    def getWidth(self, absolute=False):
        return self.image.width if absolute else int(self.image.width * self.parent.view.scale)

    def getHeight(self, absolute=False):
        return self.image.height if absolute else int(self.image.height * self.parent.view.scale)

    def inFrame(self):
        grace_space = 100 if not self.renderedImage else self.renderedImage.width * 2
        canvas_width = self.parent.canvas.winfo_width()
        canvas_height = self.parent.canvas.winfo_height()
        x, y = self.parent.view.getCoords(self.x, self.y)
        return -grace_space < x < canvas_width and -grace_space < y < canvas_height

    def moved(self):
        return self.parent.view.panning or self.translated

    def delete(self):
        self.parent.canvas.delete(self.canvasImageId)
        for comp in self.link_components:
            self.parent.canvas.delete(comp)
        self.link_components = []

    def repaint(self, force=False):
        if not (force or self.moved() or self.scaled() or self.isHighlighted):
            return

        if self.inFrame():
            scale = self.parent.view.scale
            if scale != self.renderScale:
                new_width = max(1, int(self.image.width * scale))
                new_height = max(1, int(self.image.height * scale))
                quantized_scale = quantize_scale(scale)
                if quantized_scale not in self.cachedRenders:
                    self.cachedRenders[quantized_scale] = self.image.resize((new_width, new_height), Image.NEAREST)
                self.renderedImage = self.cachedRenders[quantized_scale]
                self.tk_image = ImageTk.PhotoImage(self.renderedImage)
                self.renderScale = scale
                self.parent.images[self.imageIndex] = self.tk_image


            x, y = self.parent.view.getCoords(self.x, self.y)
            self.parent.canvas.delete(self.canvasImageId)
            self.canvasImageId = self.parent.canvas.create_image(x, y, image=self.tk_image, anchor="nw")
            self.translated = False
        else:
            self.parent.canvas.delete(self.canvasImageId)

        if self.isHighlighted:
            x1, y1 = self.parent.view.getCoords(self.x, self.y)
            x2, y2 = self.parent.view.getCoords(self.x + self.image.width, self.y + self.image.height)
            self.parent.components.append(self.parent.canvas.create_rectangle(x1, y1, x2, y2, outline='blue'))


def quantize_scale(scale):
    # Define the quantization step (adjust as needed)
    step = 0.001
    return round(scale / step) * step

class textBox(BaseBox):

    def __init__(self,parent,text="",x=0,y=0):

        self.text=text
        if(self.text==None):
            self.text="null"
        self.x=x
        self.y=y

        self.canvasObject=None

        self.translated=False

        self.canvasImageId=-1
        self.parent=parent
        self.imagefile=""
        self.boxIndex=-1

        self.linkedBoxes=[]
        self.link_components=[]

        self.renderedImage=None
        self.renderScale=-1

        self.isHighlighted=False
        
        try:
            self.repaint()
        except:
            None

    def get_xml(self):

        #import lxml.etree

        import lxml.builder    
        
        E = lxml.builder.ElementMaker()
        
        linkedAdresses=[]

        for g in self.linkedBoxes:
            linkedAdresses.append(g.boxIndex)

        address=None

        try:
            address=E.address(str(self.boxIndex))
        except:
            address=E.address("0")

        return E.textBox(
            E.text(self.text),
            E.position(str([self.x,self.y])),
            address,
            E.linkedComponents(str(linkedAdresses))
        )

    def getWidth(self, absolute=False):
        if absolute:
            return len(self.text) * 10  # Ignoring scale for absolute width
        return len(self.text) * 10 * self.parent.view.scale
    
    def getHeight(self, absolute=False):
        if absolute:
            return 30  # Ignoring scale for absolute height
        return 30 * self.parent.view.scale


    def inside(self, x, y):
        """
        Check if a point (in logical coordinates) is inside the text's bounding box.
        """
        x1, y1, x2, y2 = self.bounds()
        return x1 <= x <= x2 and y1 <= y <= y2
    

    def bounds(self):
        """
        Derive the bounding box using the current text, the font, and the scale.
        Returns (x1, y1, x2, y2) in logical coordinates.
        """
        scale = self.parent.view.scale
        # Determine font size based on scale (same logic as in repaint)
        font_size = int(scale * 15)
        if font_size < 5:
            font_size = 5

        # Create a Tkinter font object (make sure to use same family/weight)
        font = tkFont.Font(family="Helvetica", size=font_size, weight="bold")
        lines = self.text.split('\n')
        # Get the width of the longest line
        max_width = max((font.measure(line) for line in lines), default=0)
        # Total height is number of lines times the line spacing
        total_height = font.metrics("linespace") * len(lines)
        # The logical bounds start at (self.x, self.y)
        return (self.x, self.y, self.x + max_width, self.y + total_height)

    def inFrame(self):

        canvas_width=self.parent.canvas.winfo_width()

        canvas_height=self.parent.canvas.winfo_width()

        x,y=self.parent.view.getCoords(self.x,self.y)

        if(x<canvas_width and y<canvas_height and x> 0 and y> 0):

            return True

        return False

    def repaint(self, force=False):
        # Delete the old text rendering if it exists
        if self.canvasObject is not None:
            self.parent.canvas.delete(self.canvasObject)

        # Get the top-left corner in canvas (screen) coordinates.
        x, y = self.parent.view.getCoords(self.x, self.y)
        
        fontNum = int(self.parent.view.scale * 15)
        if fontNum < 5:
            fontNum = 5

        font = ('Helvetica', fontNum, 'bold')
        # Use anchor 'nw' so the text's top-left corner is fixed.
        self.canvasObject = self.parent.canvas.create_text(
            x, y,
            text=self.text,
            font=font,
            anchor='nw'
        )
        self.parent.components.append(self.canvasObject)

        # Update our cached bounds using the measured text from the font:
        self._logical_bounds = self.bounds()

        # Draw a highlight box if needed
        if self.isHighlighted:
            # Get bounds in logical coordinates
            x1_log, y1_log, x2_log, y2_log = self.bounds()
            # Convert them to canvas coordinates
            x1_canvas, y1_canvas = self.parent.view.getCoords(x1_log, y1_log)
            x2_canvas, y2_canvas = self.parent.view.getCoords(x2_log, y2_log)
            highlight = self.parent.canvas.create_rectangle(
                x1_canvas, y1_canvas, x2_canvas, y2_canvas, outline='blue'
            )
            self.parent.components.append(highlight)


def get_text_input(prompt):
    return simpledialog.askstring("Input Needed", prompt)

        
class View():
    
    def __init__(self):
        
        self.scale=1
        self.x_off=0
        self.y_off=0
        self.panning=False
        
    def getCoords(self,x,y):
        
        return x*self.scale+self.x_off,y*self.scale+self.y_off
    
    def getInvCoords(self,x,y):
        
        return (x-self.x_off)/self.scale, (y-self.y_off)/self.scale
    
    def rescale(self,delta,x,y):
        self.x_off=x-(x-self.x_off)*delta
        self.y_off=y-(y-self.y_off)*delta
        self.scale*=delta
        
class Mouse():
    
    def __init__(self):
        
        self.moving=False
        
        self.last_x=0
        self.last_y=0
        self.scroll_delta=1.1
        
class GlyphClusterGroup():

    def __init__(self,glyphs):

        self.groups=[]

        for g in glyphs:
            self.groups.append([g])

        self.mergeALL()


    def groupMatch(self,a,b):
        for x in a:
            for y in b:
                if(x.match(y)):
                    return True
        return False

    def mergeGroups(self,a,b):
        a.extend(b)
        return a

    def mergeALL(self):

        i=0
        j=0

        while(i<len(self.groups)):

            j=i+1

            while(j<len(self.groups)):

                group1=self.groups[i]
                group2=self.groups[j]

                if(self.groupMatch(group1,group2)):

                    self.groups[i]=self.mergeGroups(group1,group2)
                    self.groups.pop(j)

                else:

                    j+=1

            i+=1
    
def align_glyphs_horizontally(glyphs):
        
    if(len(glyphs)==0):
        return
        
    yz=[]
        
    for g in glyphs:
        yz.append(g.y)
    masterY=np.median(yz)
        
    for g in glyphs:
        g.y=masterY
            
def align_glyphs_vertically(glyphs):
        
    if(len(glyphs)==0):
        return
        
    xz=[]
        
    for g in glyphs:
        xz.append(g.x+g.getWidth()*0.5)
            
    masterX=np.median(xz)
        
    for g in glyphs:
        g.x=masterX - g.getWidth()*0.5

def find(parent, x):
    """Find with path compression."""
    if parent[x] != x:
        parent[x] = find(parent, parent[x])
    return parent[x]

def union(parent, rank, x, y):
    """Union by rank."""
    rootX = find(parent, x)
    rootY = find(parent, y)
    if rootX == rootY:
        return
    if rank[rootX] < rank[rootY]:
        parent[rootX] = rootY
    elif rank[rootX] > rank[rootY]:
        parent[rootY] = rootX
    else:
        parent[rootY] = rootX
        rank[rootX] += 1

def cuthill_mckee_order_for_connections(glyphs):
    """
    Given a list of glyphs (within one connected group), builds a connectivity graph
    based on each glyph’s linkedBoxes and returns a new ordering using a Cuthill–McKee-like BFS.
    """
    n = len(glyphs)
    index_map = {glyph: i for i, glyph in enumerate(glyphs)}
    
    # Build an undirected graph as a dict: index -> list of connected indices.
    graph = {i: [] for i in range(n)}
    for i, glyph in enumerate(glyphs):
        for neighbor in glyph.linkedBoxes:
            if neighbor in index_map:
                j = index_map[neighbor]
                if j not in graph[i]:
                    graph[i].append(j)
                if i not in graph[j]:
                    graph[j].append(i)
    
    visited = [False] * n
    order = []
    
    def bfs(start):
        from collections import deque
        q = deque([start])
        visited[start] = True
        comp_order = []
        while q:
            current = q.popleft()
            comp_order.append(current)
            # Process neighbors sorted by increasing degree.
            for neighbor in sorted(graph[current], key=lambda x: len(graph[x])):
                if not visited[neighbor]:
                    visited[neighbor] = True
                    q.append(neighbor)
        return comp_order

    for i in range(n):
        if not visited[i]:
            order.extend(bfs(i))
    
    return [glyphs[i] for i in order]

def group_and_sort_by_connections(glyphs):
    """
    Groups glyphs by connectivity using union–find, then sorts the groups so that
    multi‐element groups (size > 1) are ordered first (sorted by descending group size)
    with each group internally ordered by a Cuthill–McKee-like algorithm.
    Isolated glyphs (groups of size 1) are placed at the end.
    Returns a flattened list of glyphs in the new order.
    """
    # Build union–find structures.
    parent = {}
    rank = {}
    glyph_dict = {}  # Map from id(glyph) to the glyph object.
    for glyph in glyphs:
        gid = id(glyph)
        parent[gid] = gid
        rank[gid] = 0
        glyph_dict[gid] = glyph

    # Only consider neighbors that are in the current selection.
    glyph_ids = set(glyph_dict.keys())
    for glyph in glyphs:
        gid = id(glyph)
        for neighbor in glyph.linkedBoxes:
            neighbor_id = id(neighbor)
            if neighbor_id in glyph_ids:
                union(parent, rank, gid, neighbor_id)

    # Group glyphs by their root.
    groups_dict = {}
    for gid in glyph_ids:
        root = find(parent, gid)
        groups_dict.setdefault(root, []).append(glyph_dict[gid])
    groups = list(groups_dict.values())

    # Separate multi-element groups from isolated glyphs.
    groups_mult = [g for g in groups if len(g) > 1]
    groups_single = [g for g in groups if len(g) == 1]

    # Sort multi-element groups by descending size.
    groups_mult.sort(key=lambda g: len(g), reverse=True)

    sorted_groups = []
    # Apply Cuthill–McKee ordering within each multi-element group.
    for group in groups_mult:
        sorted_groups.append(cuthill_mckee_order_for_connections(group))
    # Append the singleton groups (order within a singleton group is trivial).
    sorted_groups.extend(groups_single)

    # Flatten the sorted groups into a single list.
    sorted_glyphs = [glyph for group in sorted_groups for glyph in group]
    return sorted_glyphs




class Selection_Box():
    
    def __init__(self,x,y):
        
        self.x1=x
        self.y1=y
        self.x2=x
        self.y2=y
        
        self.glyphs=[]

    def save_glyph_group(self,filename):

        file=open(filename,'w')

        for g in self.glyphs:

            file.write(g.glyph.address+"\n")
        
        file.close()

    
    def sort_glyphs(self, criterion):
        """
        Sorts self.glyphs in-place based on the given criterion.
        Criterion can be: "Transliteration", "Confidence", or "Order".
        """
    
        key_funcs = {
            "Transliteration": lambda g: corpus_transliterations.get(g.glyph.address, {}).get("transliteration", ""),
            "Confidence": lambda g: corpus_transliterations.get(g.glyph.address, {}).get("confidence", 0),
            "Order": lambda g: allGlyphs.index(g.glyph) if g.glyph in allGlyphs else float('inf'),
        }
    
        self.glyphs.sort(key=key_funcs.get(criterion, lambda g: 0))
    
    def reSortHorizontal(self, criterion="Order", space=3000):
        if not self.glyphs:
            return
        self.sort_glyphs_by_criterion(criterion)
        
        # Then place horizontally
        top_left_x = min(glyph.x for glyph in self.glyphs)
        top_left_y = min(glyph.y for glyph in self.glyphs)
        current_x, current_y = top_left_x, top_left_y
        for glyph in self.glyphs:
            glyph.x, glyph.y = current_x, current_y
            current_x += glyph.getWidth(absolute=True) + 30
            if current_x - top_left_x > space:  # wrap
                current_x = top_left_x
                current_y += 300
        # Repaint
        for glyph in self.glyphs:
            glyph.paint_links(force=True)
            glyph.repaint(force=True)

    def reSortVertical(self, criterion="Order", space=150):
        if not self.glyphs:
            return
        self.sort_glyphs_by_criterion(criterion)

        # Then place vertically
        top_left_x = min(glyph.x for glyph in self.glyphs)
        top_left_y = min(glyph.y for glyph in self.glyphs)
        current_x, current_y = top_left_x, top_left_y
        for glyph in self.glyphs:
            glyph.x, glyph.y = current_x, current_y
            current_y += space
        # Repaint
        for glyph in self.glyphs:
            glyph.paint_links(force=True)
            glyph.repaint(force=True)

    def sort_glyphs_by_criterion(self, criterion):

        def get_corpus_index_by_address(glyph_or_address):
            """
            Return the index of a glyph in corpus order by matching its address string.
            Works even if the glyph object is not the same instance as in allGlyphs.
            Returns a large number if not found.
            """
            address = glyph_or_address.address if hasattr(glyph_or_address, "address") else str(glyph_or_address)
            for i, g in enumerate(allGlyphs):
                if g.address == address:
                    return i
            return 999999
        
        if criterion == "Transliteration":
            self.glyphs.sort(key=lambda gb: self.transliteration_sort_key(self.get_transliteration(gb)))
        elif criterion == "Reverse Transliteration":
            self.glyphs.sort(key=lambda gb: self.reverse_token_sort_key(self.get_transliteration(gb)))
        elif criterion == "Token Count":
            self.glyphs.sort(key=lambda gb: self.num_tokens_sort_key(self.get_transliteration(gb)))
        elif criterion == "Confidence":
            self.glyphs.sort(key=lambda gb: self.get_confidence(gb), reverse=False)
        elif criterion == "Visual Embedding":
            print("Sorting by Visual Embedding using dendrogram similarity matrix...")
            self.glyphs = embeddings.dendrogram_order_for_visual_embeddings(self.glyphs)
        elif criterion == "Connections":
            self.glyphs = group_and_sort_by_connections(self.glyphs)
        else:
            self.glyphs.sort(key=lambda gb: get_corpus_index_by_address(gb.glyph))

    import re

    def num_tokens_sort_key(self, translit):
        return len(translit.split("."))

    def reverse_token_sort_key(self, translit):
        # Split by "." and reverse the tokens for right-to-left comparison
        tokens = translit.split(".")
        return [int(t) if t.isdigit() else t for t in reversed(tokens)]

    def transliteration_sort_key(self, translit):
        # Split into list of [int, str, int, str, ...]
        return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', translit)]

    def get_transliteration(self, glyphBox):
        addr = glyphBox.glyph.address
        if addr in corpus_transliterations:
            return corpus_transliterations[addr].get("transliteration", "")
        return ""

    def get_confidence(self, glyphBox):
        addr = glyphBox.glyph.address
        if addr in corpus_transliterations:
            return corpus_transliterations[addr].get("confidence", 0)
        return 0


    
    def linkSelectedGlyphs(self):
        if(len(self.glyphs)>1):
            for i in range(len(self.glyphs)):
                for j in range(i):
                    a=self.glyphs[i]
                    b=self.glyphs[j]
                    a.linkto(b)
                    b.linkto(a)
        for g in self.glyphs:
            g.paint_links(force=True)
                    
    def unlink(self):
        for i in range(len(self.glyphs)):
             self.glyphs[i].linkedBoxes=[]
        
    def add_glyphs(self,glyphs):
        
        for g in glyphs:
            if(g not in self.glyphs):
                self.glyphs.append(g)
        self.find_bounds()

    def repaint(self):
        for g in self.glyphs:
            g.repaint(force=True)
            g.paint_links(force=True)

        
    def inside(self, x, y):
        """
        Checks if a point (x, y) is inside the bounds defined by (x1, y1) and (x2, y2).
        """
        return min(self.x1, self.x2) <= x <= max(self.x1, self.x2) and \
               min(self.y1, self.y2) <= y <= max(self.y1, self.y2)

    
    def align_glyphs_horizontally(self, *args):
        align_glyphs_horizontally(self.glyphs)
        self.repaint()

    def align_glyphs_vertically(self, *args):
        align_glyphs_vertically(self.glyphs)
        self.repaint()

            
    def auto_align_glyphs(self):

        GG=GlyphClusterGroup(self.glyphs)

        if(len(GG.groups)==len(self.glyphs)):

            self.align_glyphs_horizontally()

        else:

            for group in GG.groups:

                alignable=True

                for i in range(len(group)):
                    for j in range(i):
                        A=group[i]
                        B=group[j]

                        if( not (A.y+A.image.height>B.y or B.y+B.image.height>A.y) ):

                            alignable=False

                if(alignable):

                    align_glyphs_vertically(group)

        self.repaint()
                
    def find_bounds(self):
        if self.glyphs:
            self.x1, self.y1, self.x2, self.y2 = float('inf'), float('inf'), float('-inf'), float('-inf')
            for g in self.glyphs:
                xl, yl, xh, yh = g.bounds()
                self.x1, self.y1 = min(self.x1, xl), min(self.y1, yl)
                self.x2, self.y2 = max(self.x2, xh), max(self.y2, yh)
                

class glyphWindow(TkinterDnD.Tk):  # Inherit from tk.Tk
    
    def __init__(self):
        
        super().__init__()  # or Toplevel() if you call it from another window
        self.title("Glyph Window")
        style = ttk.Style(self)
        style.theme_use("clam")
        
        self.images = []  # to hold references to images

        # Create a vertical PanedWindow so you have adjustable panels (top and bottom).
        self.paned = ttk.PanedWindow(self, orient="vertical")
        self.paned.pack(fill="both", expand=True)

        '''
        self.info_frame =ttk.Frame(self.paned, height=50)
        self.info_frame.pack_propagate(False)  # Prevent resizing
        
        # Create the image label; initially, no image is shown.
        self.glyph_info_image = Label(self.info_frame)
        self.glyph_info_image.pack(side=LEFT, padx=5, pady=5)
        
        # Create the text label for glyph info.
        self.glyph_info_label = Label(self.info_frame, text="Hover over a glyph", anchor="w")
        self.glyph_info_label.pack(side=LEFT, fill=BOTH, expand=True, padx=5, pady=5)
        
        self.paned.add(self.info_frame, minsize=50)
        '''

        # Main panel for the canvas and control panel (as before).
        self.main_paned = ttk.PanedWindow(self.paned, orient="horizontal")
        self.paned.add(self.main_paned)

        # Left panel for buttons and controls.
        self.panel_frame = ttk.Frame(self.main_paned, width=200, style="Side.TFrame")
        self.create_control_panel(self.panel_frame)  # Add buttons to this frame
        self.main_paned.add(self.panel_frame)

        self.glyph_inspection_frame = ttk.Frame(self.main_paned, width=200)
        self.transliteration_frame = transliteration_frame.TransliterationFrame(self, self.glyph_inspection_frame)
        self.transliteration_frame.pack(fill="both", expand=True)  # <-- Add this line
        self.main_paned.add(self.glyph_inspection_frame)

        # Right panel for the canvas.
        self.canvas_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.canvas_frame)

        self.glyph_search_frame = ttk.Frame(self.main_paned, width=200)
        self.transliteration_search_frame = glyph_search_frame.TransliterationSearchFrame(self.glyph_search_frame, self)
        self.transliteration_search_frame.pack(fill="both", expand=True)
        self.main_paned.add(self.glyph_search_frame)

        # Create and pack canvas in the canvas_frame.
        self.canvas = tk.Canvas(self.canvas_frame, bg="white", highlightthickness=0)
        self.canvas.pack(side="bottom", fill="both", expand=True)
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind('<<Drop>>', self.on_drop_files)
        self.canvas.images = []  # To store image references

        # Initialize various variables and bind events (same as your original code).
        self._clicked_on_glyph = False
        self.hover_text_id = None
        self.currentSelection = None
        self.selection_box = None
        self.control_down = False
        self.shift_down = False
        self.moving_selection = False
        self.MouseCircle = None
        self.link1 = None
        self.link2 = None
        self.fast = True
        self.components = []
        self.boxes = []
        self.transliteration_ids = {}
        self.address_ids = {}
        self.mouse = Mouse()
        self.view = View()

        # Bind canvas and root events.
        self.canvas.bind('<ButtonPress-1>', self.onLeftMouseDown)
        self.canvas.bind('<ButtonRelease-1>', self.onLeftMouseUp)
        self.canvas.bind('<Motion>', self.onMouseMove)
        self.canvas.bind('<MouseWheel>', self.scroll_wheel)
        self.canvas.bind('<Button-3>', self.onRightClick)
        #self.bind('<Return>', self.auto_align)
        self.bind('<Delete>', self.deleteSelectedGlyphs)
        #self.bind("<space>", self.linkSelectedGlyphs) now handled in on_key_press
        self.bind("<Control-v>", self.align_glyphs_vertically)
        self.bind("<Control-h>", self.align_glyphs_horizontally)
        self.bind("<Control-r>", self.insert_succeeding_glyph)
        self.bind("<Control-l>", self.insert_preseeding_glyph)
        self.bind("<Control-g>", self.make_group)
        self.bind("<Key>", self.on_key_press)

    def export_selected_glyphs_to_image(self, event=None, padding=50, label_gutter=100, label_left_pad=33):
        """
        Export selected glyph boxes to a composite image, with a 200px left gutter for line labels.
    
        Line-start detection:
          Box A starts a line iff there does NOT exist any other selected box B such that a horizontal ray
          drawn leftward from A's left edge can intersect B. Implemented as:
            - B is to the left of A (B.right <= A.left)
            - and B vertically overlaps A (their y-intervals overlap)
    
        Label:
          prefix = address.split('-', 1)[0]  (e.g., "Cr1")
          rendered in Times New Roman, blue, using matplotlib mathtext.
          placed in left gutter with left padding, vertically centered at the midpoint of the line-start box.
        """
        import os
        from PIL import Image, ImageDraw
        from tkinter import filedialog, messagebox
    
        # --- helper: render LaTeX-like text (mathtext) to a transparent RGBA image ---
        def _render_label_mathtext(text, fontsize=28, color="#1f4de3"):
            # Lazy import so editor doesn’t depend on mpl unless exporting
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
    
            # Use mathtext; \mathrm for upright roman look
            # Example: r"$\mathrm{Cr1}$"
            s = rf"$\mathrm{{{text}}}$"
    
            fig = plt.figure(figsize=(2, 1), dpi=200)
            fig.patch.set_alpha(0.0)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.axis("off")
    
            # Place text; we’ll tightly crop afterwards
            t = ax.text(
                0, 0.5, s,
                va="center", ha="left",
                color=color,
                fontsize=fontsize,
                fontfamily="Times New Roman"
            )
    
            # Render to buffer and crop tight
            buf = io.BytesIO()
            fig.canvas.draw()
            fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0.02)
            plt.close(fig)
            buf.seek(0)
            return Image.open(buf).convert("RGBA")
    
        # --- helper: get box bounds in logical coords (absolute image size) ---
        def _box_bounds(b):
            x0 = float(b.x)
            y0 = float(b.y)
            w = float(b.getWidth(absolute=True))
            h = float(b.getHeight(absolute=True))
            return x0, y0, x0 + w, y0 + h
    
        # 1) Validate selection
        if not getattr(self, "currentSelection", None) or not getattr(self.currentSelection, "glyphs", None):
            messagebox.showinfo("Export", "No glyphs selected.")
            return
    
        selected = [b for b in self.currentSelection.glyphs if hasattr(b, "image") and hasattr(b, "x") and hasattr(b, "y")]
        if not selected:
            messagebox.showinfo("Export", "Selection contains no image glyphs to export.")
            return
    
        # 2) Ask for save location
        path = filedialog.asksaveasfilename(
            title="Save selection as image",
            defaultextension=".png",
            filetypes=(("PNG Image", "*.png"), ("JPEG Image", "*.jpg;*.jpeg"), ("All Files", "*.*"))
        )
        if not path:
            return
    
        # 3) Compute tight bounds around selected boxes (logical coords)
        bounds = [_box_bounds(b) for b in selected]
        min_x = min(x0 for x0, y0, x1, y1 in bounds)
        min_y = min(y0 for x0, y0, x1, y1 in bounds)
        max_x = max(x1 for x0, y0, x1, y1 in bounds)
        max_y = max(y1 for x0, y0, x1, y1 in bounds)
    
        # 4) Output size includes: left label gutter + padding around everything
        out_w = int(round((max_x - min_x) + 2 * padding + label_gutter))
        out_h = int(round((max_y - min_y) + 2 * padding))
        out_w = max(1, out_w)
        out_h = max(1, out_h)
    
        # 5) Create white background
        composite = Image.new("RGB", (out_w, out_h), color=(255, 255, 255))
    
        # 6) Determine line-start boxes using your rule
        # Precompute bounds for speed
        info = []
        for b in selected:
            x0, y0, x1, y1 = _box_bounds(b)
            info.append((b, x0, y0, x1, y1))
    
        line_starts = []
        for (A, ax0, ay0, ax1, ay1) in info:
            A_is_start = True
            for (B, bx0, by0, bx1, by1) in info:
                if B is A:
                    continue
    
                # "a line drawn to the left from the left edge of A intersects B"
                # => B is to the left and vertical intervals overlap
                if bx1 <= ax0:
                    overlap = not (by1 <= ay0 or by0 >= ay1)
                    if overlap:
                        A_is_start = False
                        break
    
            if A_is_start:
                line_starts.append((A, ax0, ay0, ax1, ay1))
    
        # Optional: sort line-starts top-to-bottom then left-to-right
        line_starts.sort(key=lambda t: (t[2], t[1]))
    
        # 7) Paste glyph images (shifted by left gutter + padding)
        # shift maps logical coords -> output coords
        x_shift = label_gutter + padding - min_x
        y_shift = padding - min_y
    
        # Stable layering order
        selected_sorted = sorted(selected, key=lambda b: (float(b.y), float(b.x)))
    
        for b in selected_sorted:
            try:
                im = b.image
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA")
    
                px = int(round(float(b.x) + x_shift))
                py = int(round(float(b.y) + y_shift))
    
                if im.mode == "RGBA":
                    composite.paste(im, (px, py), im)
                else:
                    composite.paste(im, (px, py))
            except Exception as e:
                print(f"⚠️ Failed to paste glyph {getattr(b, 'address', '?')}: {e}")
    
        # 8) Render and paste labels into the left gutter
        # Labels are aligned to the midpoint y of the corresponding line-start box
        for (A, ax0, ay0, ax1, ay1) in line_starts:
            addr = ""
            if getattr(A, "glyph", None) is not None and getattr(A.glyph, "address", None):
                addr = str(A.glyph.address)
        
            prefix = addr.split("-", 1)[0] if "-" in addr else addr
            if not prefix:
                continue
        
            label_img = _render_label_pil(prefix, fontsize=42, color=(31, 77, 227))
            lw, lh = label_img.size
        
            mid_y = (ay0 + ay1) / 2.0
            y_center = int(round(mid_y + y_shift))
        
            lx = label_left_pad
            ly = int(round(y_center - lh / 2))
            ly = max(0, min(out_h - lh, ly))
        
            composite.paste(label_img, (lx, ly), label_img)
        
            
        # 9) Save
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                composite.convert("RGB").save(path, quality=95)
            else:
                composite.save(path)
        except Exception as e:
            messagebox.showerror("Export failed", f"Could not save image:\n{e}")
            return
    
        # 10) Open saved file
        try:
            os.startfile(path)
        except Exception as e:
            print(f"ℹ️ Saved to {path} but could not open automatically: {e}")



    def on_drop_files(self, event):
        from PIL import Image
    
        files = self.ttttk.splitlist(event.data)
    
        # Use actual mouse pointer location for drop position
        canvas_x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        canvas_y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        start_x, y = self.view.getInvCoords(canvas_x, canvas_y)
        current_x = start_x
        padding = 20
        line_height = 200
        canvas_width = self.canvas.winfo_width()
    
        for file in files:
            if not os.path.exists(file):
                print(f"⚠️ File not found: {file}")
                continue
            if not file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
                print(f"⚠️ Skipping unsupported file: {file}")
                continue
    
            try:
                with Image.open(file) as img:
                    width, height = img.width, img.height
    
                if (current_x + width > canvas_width / self.view.scale):
                    current_x = start_x
                    y += line_height
    
                self.addImageBox(file, current_x, y)
                current_x += width + padding
    
            except Exception as e:
                print(f"❌ Failed to add {file}: {e}")
    
        self.repaint()



    def create_control_panel(self, parent):
        """
        Create buttons in the left-side control panel.
        Adjust or add commands as needed.
        """
        # Use grid or pack to arrange your buttons.
        # Here, pack is used for simplicity:
        btn_load = ttk.Button(parent, text="Load", command=self.load)
        btn_load.pack(fill="x", padx=5, pady=2)

        btn_save = ttk.Button(parent, text="Save As", command=self.save)
        btn_save.pack(fill="x", padx=5, pady=2)

        self.export_btn = ttk.Button(parent, text="Render Selection", command=self.export_selected_glyphs_to_image)
        self.export_btn.pack(fill="x", padx=6, pady=(10, 0))

        btn_save_group = ttk.Button(parent, text="Save Glyph Selection", command=self.save_glyph_group)
        btn_save_group.pack(fill="x", padx=5, pady=2)

        btn_add_line = ttk.Button(parent, text="Add Glyph(s)", command=self.addGlyphsInLine)
        btn_add_line.pack(fill="x", padx=5, pady=2)

        btn_add_list = ttk.Button(parent, text="Add Glyph List", command=self.openGlyphListDialog)
        btn_add_list.pack(fill="x", padx=5, pady=2)

        # --- Copy Buttons ---
        btn_copy_addresses = ttk.Button(
            parent,
            text="Copy Selected Addresses",
            command=lambda: self.copy_all_addresses_to_clipboard(mode="list")
        )
        btn_copy_addresses.pack(fill="x", padx=5, pady=2)
        
        btn_copy_addresses_latex = ttk.Button(
            parent,
            text="Copy as LaTeX",
            command=lambda: self.copy_all_addresses_to_clipboard(mode="latex")
        )
        btn_copy_addresses_latex.pack(fill="x", padx=5, pady=2)


        btn_unlink = ttk.Button(parent, text="Unlink Glyphs", command=self.unlink)
        btn_unlink.pack(fill="x", padx=5, pady=2)

        btn_align_rows = ttk.Button(parent, text="Align Rows", command=lambda: self.align_selection_into_rows(row_gap=25))
        btn_align_rows.pack(fill="x", padx=5, pady=2)

        btn_align_horiz = ttk.Button(parent, text="Align Horizontally", command=self.align_glyphs_horizontally)
        btn_align_horiz.pack(fill="x", padx=5, pady=2)

        btn_align_vert = ttk.Button(parent, text="Align Vertically", command=self.align_glyphs_vertically)
        btn_align_vert.pack(fill="x", padx=5, pady=2)
    
        btn_add_text = ttk.Button(parent, text="Add Text Box", command=self.add_text_box)
        btn_add_text.pack(fill="x", padx=5, pady=2)

        btn_add_image = ttk.Button(parent, text="Add Image Box", command=self.add_image_box)
        btn_add_image.pack(fill="x", padx=5, pady=2)

        btn_make_group = ttk.Button(parent, text="Link Parallels", command=self.link_parallels)
        btn_make_group.pack(fill="x", padx=5, pady=2)

        btn_add_linked = ttk.Button(parent, text="Add All Parallels", command=self.add_linked_glyphs_from_folder)
        btn_add_linked.pack(fill="x", padx=5, pady=2)

        btn_add_divergent = ttk.Button(
            parent,
            text="Add Divergent Parallels",
            command=self.add_divergent_parallels_from_folder
        )

        btn_delete_unlinked = ttk.Button(parent, text="Delete Unlinked Glyphs", command=self.delete_unlinked_glyphs)
        btn_delete_unlinked.pack(fill="x", padx=5, pady=2)

        btn_add_divergent.pack(fill="x", padx=5, pady=2)
        btn_make_group = ttk.Button(parent, text="Make Group", command=self.make_group)
        btn_make_group.pack(fill="x", padx=5, pady=2)

        btn_remove_selected = ttk.Button(parent, text="Remove from Groups", command=self.remove_selected_glyphs_from_groups)
        btn_remove_selected.pack(fill="x", padx=5, pady=2)

        btn_sort_horiz = ttk.Button(parent, text="Sort Selection Horizontally", command=self.reSortHorizontal)
        btn_sort_horiz.pack(fill="x", padx=5, pady=2)

        btn_sort_vert = ttk.Button(parent, text="Sort Selection Vertically", command=self.reSortVertical)
        btn_sort_vert.pack(fill="x", padx=5, pady=2)

        btn_pca = ttk.Button(parent, text="PCA Layout", command=self.do_pca_on_selection)
        btn_pca.pack(fill="x", padx=5, pady=2)

        btn_add_similar = ttk.Button(
            parent,
            text="Add Similar (Avg Embedding)",
            command=self.add_closest_by_average_embedding
        )
        btn_add_similar.pack(fill="x", padx=5, pady=2)


        # Label for sorting criteria
        label = ttk.Label(parent, text="Sorting Criteria:")
        label.pack(pady=5)
        # Dropdown menu options
        options = ["Order", "Transliteration", "Reverse Transliteration", "Token Count",  "Confidence", "Visual Embedding", "Connections"]
        self.selected_sort_criteria = tk.StringVar(value="Order")  # Default selection
        dropdown = ttk.OptionMenu(parent, self.selected_sort_criteria, *options)
        dropdown.pack(pady=5)
        
        # You can add more buttons and controls as needed.
        # Optionally, add labels or other widgets for status updates.

    def startup(self):

        filename="corpus_transliterations.json"
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"transliterations_backup_{timestamp}.json"
        
        shutil.copy(filename, backup_filename)
        print(f"📝 Backup created: {backup_filename}")
        
        self.canvas.pack()
        self.mainloop()

    import os
    import json
    from tkinter import filedialog

    def add_closest_by_average_embedding(self, event=None):
        """
        Mean-embedding nearest neighbors:
        - averages embeddings of selected glyphs (using embeddings.load_embedding_for_glyph)
        - ranks corpus by cosine similarity
        - asks user for K
        - adds top K (excluding ones already selected)
        """
        import numpy as np
        from tkinter import simpledialog
    
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("⚠️ No glyphs currently selected.")
            return
    
        # Selected glyph objects
        selected_glyphs = [
            b.glyph for b in self.currentSelection.glyphs
            if getattr(b, "glyph", None) and getattr(b.glyph, "address", None)
        ]
        if not selected_glyphs:
            print("⚠️ Selection contains no valid glyphs.")
            return
    
        selected_addresses = {g.address for g in selected_glyphs}
    
        # --- build mean embedding from selection ---
        sel_vecs = []
        missing = []
        dim = None
    
        for g in selected_glyphs:
            v = embeddings.load_embedding_for_glyph(g.address)
            if v is None:
                missing.append(g.address)
                continue
            arr = np.asarray(v, dtype=np.float32)
            if arr.ndim != 1 or arr.size == 0:
                missing.append(g.address)
                continue
            if dim is None:
                dim = arr.size
            if arr.size != dim:
                # skip inconsistent dims
                continue
            sel_vecs.append(arr)
    
        if not sel_vecs:
            print("❌ Could not find embeddings for any selected glyphs.")
            print("   Missing examples:", missing[:10])
            return
    
        mean_vec = np.mean(np.stack(sel_vecs, axis=0), axis=0).astype(np.float32)
        mean_norm = float(np.linalg.norm(mean_vec))
        if mean_norm == 0:
            print("❌ Mean embedding norm is 0; cannot compute cosine similarity.")
            return
        mean_vec /= mean_norm
    
        # Ask user for K
        k = simpledialog.askinteger(
            "Add Similar Glyphs",
            "How many nearest glyphs should be added?",
            initialvalue=20,
            minvalue=1,
            maxvalue=500
        )
        if not k:
            print("❌ Cancelled.")
            return
    
        # --- score entire corpus ---
        scored = []
        skipped_in_selection = 0
        skipped_no_vec = 0
        skipped_dim = 0
    
        for g in allGlyphs:
            addr = getattr(g, "address", None)
            if not addr:
                continue
            if addr in selected_addresses:
                skipped_in_selection += 1
                continue
    
            v = embeddings.load_embedding_for_glyph(addr)
            if v is None:
                skipped_no_vec += 1
                continue
    
            arr = np.asarray(v, dtype=np.float32)
            if arr.ndim != 1 or arr.size == 0:
                skipped_no_vec += 1
                continue
            if arr.size != dim:
                skipped_dim += 1
                continue
    
            vnorm = float(np.linalg.norm(arr))
            if vnorm == 0:
                skipped_no_vec += 1
                continue
            arr = (arr / vnorm).astype(np.float32)
    
            sim = float(np.dot(mean_vec, arr))
            scored.append((sim, g))
    
        if not scored:
            print("❌ No corpus embeddings available to rank against after filtering.")
            print(f"   skipped_in_selection={skipped_in_selection}, skipped_no_vec={skipped_no_vec}, skipped_dim={skipped_dim}")
            return
    
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [g for _, g in scored[:k]]
    
        # Add to canvas (your helper already places them below existing content)
        self.add_glyphs_to_canvas(top)
    
        # Extend selection to include newly created glyphBoxes
        new_addrs = {getattr(g, "address", None) for g in top}
        added_boxes = []
        for b in self.boxes:
            if isinstance(b, glyphBox) and getattr(b, "glyph", None) and getattr(b.glyph, "address", None) in new_addrs:
                if b not in self.currentSelection.glyphs:
                    added_boxes.append(b)
    
        if added_boxes:
            self.currentSelection.add_glyphs(added_boxes)
            self.currentSelection.find_bounds()
            self.currentSelection.repaint()
    
        print(f"✅ Added {len(top)} nearest glyph(s) by average embedding.")
        print(f"   skipped_in_selection={skipped_in_selection}, skipped_no_vec={skipped_no_vec}, skipped_dim={skipped_dim}")
        self.repaint()

    
        if store is not None:
            print(f"✅ Embeddings found: embeddings.{store_name} (keyed by {mode})")
        else:
            print(f"✅ Embeddings found via function: embeddings.{getter.__name__} (expects {getter_mode})")
    
        def _get_vec(g):
            if store is not None:
                key = g.address if mode == "address" else getattr(g, "filepath", None)
                if not key:
                    return None
                v = store.get(key, None)
                if v is None:
                    return None
                try:
                    arr = np.asarray(v, dtype=np.float32)
                    return arr if arr.ndim == 1 and arr.size > 0 else None
                except Exception:
                    return None
            else:
                try:
                    key = g.address if getter_mode == "address" else getattr(g, "filepath", None)
                    if not key:
                        return None
                    v = getter(key)
                    if v is None:
                        return None
                    arr = np.asarray(v, dtype=np.float32)
                    return arr if arr.ndim == 1 and arr.size > 0 else None
                except Exception:
                    return None
    
        # ---------------------------------------------------------
        # Build mean embedding from selection
        # ---------------------------------------------------------
        sel_vecs = []
        missing = []
        for g in selected_glyphs:
            v = _get_vec(g)
            if v is None:
                missing.append(g.address)
            else:
                sel_vecs.append(v)
    
        if not sel_vecs:
            print("❌ Could not find embeddings for any selected glyphs.")
            print("   Missing examples:", missing[:10])
            return
    
        dim = sel_vecs[0].shape[0]
        sel_vecs = [v for v in sel_vecs if v.shape[0] == dim]
        if not sel_vecs:
            print("❌ Selection embeddings had inconsistent dimensions.")
            return
    
        mean_vec = np.mean(np.stack(sel_vecs, axis=0), axis=0).astype(np.float32)
        mean_norm = float(np.linalg.norm(mean_vec))
        if mean_norm == 0:
            print("❌ Mean embedding norm is 0; cannot compute cosine similarity.")
            return
        mean_vec /= mean_norm
    
        # Ask user for K
        k = simpledialog.askinteger(
            "Add Similar Glyphs",
            "How many nearest glyphs should be added?",
            initialvalue=20,
            minvalue=1,
            maxvalue=500
        )
        if not k:
            print("❌ Cancelled.")
            return
    
        # ---------------------------------------------------------
        # Score entire corpus
        # ---------------------------------------------------------
        scored = []
        skipped_in_selection = 0
        skipped_no_vec = 0
        skipped_dim = 0
    
        for g in allGlyphs:
            addr = getattr(g, "address", None)
            if not addr:
                continue
            if addr in selected_addresses:
                skipped_in_selection += 1
                continue
    
            v = _get_vec(g)
            if v is None:
                skipped_no_vec += 1
                continue
            if v.shape[0] != dim:
                skipped_dim += 1
                continue
    
            v = v.astype(np.float32)
            vnorm = float(np.linalg.norm(v))
            if vnorm == 0:
                continue
            v /= vnorm
    
            sim = float(np.dot(mean_vec, v))
            scored.append((sim, g))
    
        if not scored:
            print("❌ No corpus embeddings available to rank against after filtering.")
            print(f"   skipped_in_selection={skipped_in_selection}, skipped_no_vec={skipped_no_vec}, skipped_dim={skipped_dim}")
            return
    
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [g for _, g in scored[:k]]
    
        # Add to canvas
        self.add_glyphs_to_canvas(top)
    
        # Extend selection to include newly created glyphBoxes
        try:
            from GlyphEditorWindow import glyphBox
        except Exception:
            glyphBox = None
    
        new_addrs = {getattr(g, "address", None) for g in top}
        added_boxes = []
        for b in self.boxes:
            if glyphBox and not isinstance(b, glyphBox):
                continue
            if getattr(b, "glyph", None) and getattr(b.glyph, "address", None) in new_addrs:
                if b not in self.currentSelection.glyphs:
                    added_boxes.append(b)
    
        if added_boxes:
            self.currentSelection.add_glyphs(added_boxes)
            self.currentSelection.find_bounds()
            self.currentSelection.repaint()
    
        print(f"✅ Added {len(top)} nearest glyph(s) by average embedding.")
        print(f"   skipped_in_selection={skipped_in_selection}, skipped_no_vec={skipped_no_vec}, skipped_dim={skipped_dim}")
        self.repaint()

    

    def delete_unlinked_glyphs(self, event=None):
        """
        Deletes glyphBoxes that have NO links (len(linkedBoxes) == 0).
    
        Safety rule:
        - Do NOT delete glyphBoxes that are inside a CompoundBox (treat those as linked/grouped).
        """
    
        # If glyphBox / CompoundBox are in this module already, this import is harmless;
        # if not, it makes the references explicit.
        try:
            from GlyphEditorWindow import glyphBox, CompoundBox
        except Exception:
            # Fall back to names in current module scope if already defined
            glyphBox = globals().get("glyphBox", None)
            CompoundBox = globals().get("CompoundBox", None)
    
        if glyphBox is None:
            print("❌ delete_unlinked_glyphs: glyphBox class not found.")
            return
    
        # ---- 1) Build a set of glyphBoxes that are members of any CompoundBox ----
        compound_members = set()
        if CompoundBox is not None:
            for b in self.boxes:
                if isinstance(b, CompoundBox):
                    for member in getattr(b, "boxes", []):
                        compound_members.add(member)
    
        # ---- 2) Identify unlinked glyphBoxes (not in a compound group) ----
        to_delete = []
        for b in list(self.boxes):
            if isinstance(b, glyphBox):
                if b in compound_members:
                    continue  # treat as "linked" via grouping
                if not getattr(b, "linkedBoxes", []):  # len == 0
                    to_delete.append(b)
    
        if not to_delete:
            print("ℹ️ No unlinked glyphs to delete.")
            return
    
        # ---- 3) If any are selected, remove them from selection first ----
        if self.currentSelection is not None:
            self.currentSelection.glyphs = [g for g in self.currentSelection.glyphs if g not in to_delete]
            if len(self.currentSelection.glyphs) == 0:
                self.currentSelection = None
            else:
                self.currentSelection.find_bounds()
                self.currentSelection.repaint()
    
        # ---- 4) Delete them (mirrors your deleteSelectedGlyphs cleanup) ----
        deleted_count = 0
    
        for g in to_delete:
            # Remove references from other boxes' linkedBoxes
            for temp in self.boxes:
                if hasattr(temp, "linkedBoxes") and g in temp.linkedBoxes:
                    try:
                        temp.linkedBoxes.remove(g)
                    except Exception:
                        pass
    
            # Remove from any CompoundBox membership lists (extra safety)
            if CompoundBox is not None:
                for box in list(self.boxes):
                    if isinstance(box, CompoundBox):
                        if g in getattr(box, "boxes", []):
                            try:
                                box.boxes.remove(g)
                            except Exception:
                                pass
                        # If the compound becomes empty, delete it too
                        if hasattr(box, "boxes") and len(box.boxes) == 0:
                            try:
                                if box in self.boxes:
                                    self.boxes.remove(box)
                                del box
                            except Exception:
                                pass
    
            # Delete canvas objects + remove from main list
            try:
                g.delete()
            except Exception:
                pass
    
            if g in self.boxes:
                self.boxes.remove(g)
    
            deleted_count += 1
    
            try:
                del g
            except Exception:
                pass
    
        print(f"✅ Deleted {deleted_count} unlinked glyph(s).")
        self.repaint()


    def add_divergent_parallels_from_folder(self):
        """
        Adds glyphs that are linked to the current selection but share
        NO transliteration tokens with them.
    
        A "divergent parallel" is defined as:
        - glyph A and glyph B are linked
        - AND their transliteration token sets are disjoint
        """
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("⚠️ No glyphs currently selected.")
            return
    
        from tkinter import filedialog
        import os
        import json
    
        # -----------------------------
        # helpers
        # -----------------------------
        def get_tokens(addr: str) -> set:
            """
            Returns the set of transliteration tokens for a glyph address.
            Tokens are split by '.'.
            """
            data = corpus_transliterations.get(addr, {})
            translit = (data.get("transliteration") or "").strip()
            if not translit:
                return set()
            return {t.strip() for t in translit.split(".") if t.strip()}
    
        def is_divergent(a: str, b: str) -> bool:
            """
            Two glyphs are divergent if both have transliterations
            and their token sets do not overlap.
            """
            ta = get_tokens(a)
            tb = get_tokens(b)
            if not ta or not tb:
                return False
            return ta.isdisjoint(tb)
    
        # -----------------------------
        # selected glyph addresses
        # -----------------------------
        selected_addresses = {
            gb.glyph.address
            for gb in self.currentSelection.glyphs
            if getattr(gb, "glyph", None) and getattr(gb.glyph, "address", None)
        }
    
        if not selected_addresses:
            print("⚠️ Selection has no glyph addresses.")
            return
    
        # -----------------------------
        # choose folder
        # -----------------------------
        folder = filedialog.askdirectory(
            title="Select Folder Containing Linked Glyph JSON Files"
        )
        if not folder:
            print("❌ No folder selected. Operation cancelled.")
            return
    
        # -----------------------------
        # scan folder
        # -----------------------------
        divergent_neighbors = set()
    
        for root, _, files in os.walk(folder):
            for filename in files:
                if not filename.lower().endswith(".json"):
                    continue
    
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
    
                    for box in data.get("boxes", []):
                        if box.get("type") != "glyphBox":
                            continue
    
                        src = box.get("glyph_address")
                        if not src:
                            continue
    
                        for dst in box.get("linked_glyph_addresses", []) or []:
                            if not dst:
                                continue
    
                            # undirected: check either direction against selection
                            if src in selected_addresses and is_divergent(src, dst):
                                divergent_neighbors.add(dst)
    
                            if dst in selected_addresses and is_divergent(dst, src):
                                divergent_neighbors.add(src)
    
                except Exception as e:
                    print(f"❌ Error reading {filepath}: {e}")
    
        # -----------------------------
        # remove already-selected glyphs
        # -----------------------------
        new_addresses = divergent_neighbors - selected_addresses
    
        if not new_addresses:
            print("ℹ️ No divergent parallels found.")
            return
    
        # -----------------------------
        # map addresses → Glyph objects
        # -----------------------------
        glyphs_to_add = [
            g for g in allGlyphs
            if getattr(g, "address", None) in new_addresses
        ]
    
        if not glyphs_to_add:
            print("⚠️ Divergent parallel addresses found, but none matched allGlyphs.")
            return
    
        # preserve corpus order
        try:
            glyphs_to_add.sort(key=lambda g: allGlyphs.index(g))
        except Exception:
            pass
    
        # -----------------------------
        # add to canvas
        # -----------------------------
        self.add_glyphs_to_canvas(glyphs_to_add)
    
        # -----------------------------
        # extend current selection
        # -----------------------------
        try:
            from GlyphEditorWindow import glyphBox
        except Exception:
            glyphBox = None
    
        added_boxes = []
        for b in self.boxes:
            if glyphBox and not isinstance(b, glyphBox):
                continue
            if (
                getattr(b, "glyph", None)
                and getattr(b.glyph, "address", None) in new_addresses
                and b not in self.currentSelection.glyphs
            ):
                added_boxes.append(b)
    
        if added_boxes:
            self.currentSelection.add_glyphs(added_boxes)
            self.currentSelection.find_bounds()
            self.currentSelection.repaint()
    
        print(f"✅ Added {len(glyphs_to_add)} divergent parallel glyph(s).")
        self.repaint()


    def add_linked_glyphs_from_folder(self):
        """
        Scans a folder of JSON exports (same format used by link_parallels),
        finds ALL glyphs linked to ANY glyph in the current selection,
        removes glyphs already in the selection,
        then adds the new ones to the canvas and selection.
        """
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("⚠️ No glyphs currently selected.")
            return
    
        from tkinter import filedialog
        import os
        import json
    
        # Collect selected addresses
        selected_addresses = {
            gb.glyph.address
            for gb in self.currentSelection.glyphs
            if getattr(gb, "glyph", None) and getattr(gb.glyph, "address", None)
        }
    
        if not selected_addresses:
            print("⚠️ Selection has no glyph addresses.")
            return
    
        folder = filedialog.askdirectory(title="Select Folder Containing JSON Files")
        if not folder:
            print("❌ No folder selected. Operation cancelled.")
            return
    
        # Build an adjacency map (undirected)
        adjacency = {}  # addr -> set(neighbor_addrs)
    
        def add_edge(a, b):
            if not a or not b:
                return
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    
        # Walk through folder/subfolders like link_parallels
        for root, _, files in os.walk(folder):
            for filename in files:
                if not filename.lower().endswith(".json"):
                    continue
    
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
    
                    for box in data.get("boxes", []):
                        if box.get("type") == "glyphBox":
                            source = box.get("glyph_address")
                            for target in box.get("linked_glyph_addresses", []):
                                add_edge(source, target)
    
                except Exception as e:
                    print(f"❌ Error reading {filepath}: {e}")
    
        if not adjacency:
            print("⚠️ No link data found in the selected folder.")
            return
    
        # Union of neighbors of the selection
        linked_addresses = set()
        for addr in selected_addresses:
            linked_addresses |= adjacency.get(addr, set())
    
        # Remove anything already selected
        new_addresses = linked_addresses - selected_addresses
    
        if not new_addresses:
            print("ℹ️ No new linked glyphs found (everything linked is already selected).")
            return
    
        # Convert addresses -> Glyph objects (from your corpus list)
        # 'allGlyphs' is already used elsewhere in this file for lookups/sorting.
        glyphs_to_add = [g for g in allGlyphs if getattr(g, "address", None) in new_addresses]
    
        if not glyphs_to_add:
            print("⚠️ Linked addresses found, but none matched entries in allGlyphs.")
            print(f"   Example addresses: {list(sorted(new_addresses))[:10]}")
            return
    
        # Sort in corpus order (stable/expected)
        try:
            glyphs_to_add.sort(key=lambda g: allGlyphs.index(g))
        except Exception:
            pass
    
        # Add them to the canvas (existing helper)
        self.add_glyphs_to_canvas(glyphs_to_add)
    
        # Also add the newly created glyphBoxes into the current selection
        try:
            from GlyphEditorWindow import glyphBox  # if needed in your file layout
        except Exception:
            glyphBox = None
    
        added_boxes = []
        for b in self.boxes:
            if glyphBox and not isinstance(b, glyphBox):
                continue
            if getattr(b, "glyph", None) and getattr(b.glyph, "address", None) in new_addresses:
                if b not in self.currentSelection.glyphs:
                    added_boxes.append(b)
    
        if added_boxes:
            self.currentSelection.add_glyphs(added_boxes)
            self.currentSelection.find_bounds()
            self.currentSelection.repaint()
    
        print(f"✅ Added {len(glyphs_to_add)} linked glyph(s) to the frame (from {len(new_addresses)} linked address(es)).")
        self.repaint()

    
    def link_parallels(self):
        """
        Links glyphs in the current selection using address pairs found in JSON files
        from a user-selected folder and its subfolders.
        """
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("⚠️ No glyphs currently selected.")
            return
    
        folder = filedialog.askdirectory(title="Select Folder Containing JSON Files for Linking")
        if not folder:
            print("❌ No folder selected. Operation cancelled.")
            return
    
        linked_pairs = set()
    
        # Walk through the folder and subfolders to collect all linked address pairs
        for root, _, files in os.walk(folder):
            for filename in files:
                if filename.lower().endswith(".json"):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
    
                            for box in data.get("boxes", []):
                                if box.get("type") == "glyphBox":
                                    source = box.get("glyph_address")
                                    for target in box.get("linked_glyph_addresses", []):
                                        if source and target:
                                            pair = tuple(sorted((source, target)))
                                            linked_pairs.add(pair)
                    except Exception as e:
                        print(f"❌ Error reading {filepath}: {e}")
    
        if not linked_pairs:
            print("⚠️ No linked pairs found.")
            return
    
        # Build mapping from address to glyphBox for current selection
        selection_map = {
            gb.glyph.address: gb
            for gb in self.currentSelection.glyphs
            if hasattr(gb.glyph, "address")
        }
    
        links_made = 0
        for addr1, addr2 in linked_pairs:
            if addr1 in selection_map and addr2 in selection_map:
                box1 = selection_map[addr1]
                box2 = selection_map[addr2]
                box1.linkto(box2)
                box2.linkto(box1)
                box1.paint_links(force=True)
                box2.paint_links(force=True)
                links_made += 1
    
        print(f"✅ Linked {links_made} pairs in the current selection.")
        self.repaint()


    def add_glyphs_to_canvas(self, glyphs, start_x=0, padding_x=20, padding_y=100, max_width=5000):
        """
        Adds a list of KohauCode_Horley.Glyph objects to the canvas in a row/column layout.
        Automatically spaces rows and tracks vertical placement.
        """
        from PIL import Image
    
        if not glyphs:
            print("⚠️ No glyphs to add.")
            return
    
        # Determine starting Y position based on existing boxes
        current_y = 0
        if self.boxes:
            last_box = max(self.boxes, key=lambda b: b.y + b.getHeight(absolute=True))
            current_y = last_box.y + last_box.getHeight(absolute=True) + padding_y
    
        current_x = start_x
        added = 0
    
        for glyph in glyphs:
            try:
                im = Image.open(glyph.filepath)
                new_box = glyphBox(self, image=im, x=current_x, y=current_y, glyph=glyph)
                new_box.imagefile = glyph.filepath
                new_box.boxIndex = self.get_unique_boxIndex()
                self.boxes.append(new_box)
    
                current_x += im.width + padding_x
                added += 1
    
                # wrap to next line if too wide
                if current_x - start_x > max_width:
                    current_x = start_x
                    current_y += im.height + padding_y
    
            except Exception as e:
                print(f"❌ Failed to load {glyph.address}: {e}")
    
        print(f"✅ Added {added} glyphs.")
        self.repaint()


    def on_key_press(self, event):
        # If exactly one glyph is selected and it's a textBox, edit the text
        if self.currentSelection and len(self.currentSelection.glyphs) == 1:
            box = self.currentSelection.glyphs[0]
            if isinstance(box, textBox):
                if event.keysym == "BackSpace":
                    box.text = box.text[:-1]
                elif event.keysym == "space":
                    box.text += " "
                elif event.keysym == "Return":
                    box.text += "\n"
                elif event.char and event.char.isprintable():
                    box.text += event.char
                box.repaint(force=True)
                return  # prevent fall-through
    
        # If not editing text, check for other shortcut keys like space
        if event.keysym == "space":
            self.linkSelectedGlyphs()


    def openGlyphListDialog(self):
        # Use tk.* so we don't depend on "from tkinter import Toplevel, Label, Text"
        popup = tk.Toplevel(self)
        popup.title("Add Glyphs by Address")
        popup.geometry("350x450")
    
        # Optional but nice UX: keep dialog on top and modal-ish
        try:
            popup.transient(self)
            popup.grab_set()
        except Exception:
            pass
    
        tk.Label(popup, text="Paste a list of addresses:").pack(padx=10, pady=(10, 5))
    
        text = tk.Text(popup, height=20, width=30)
        text.pack(padx=10, pady=5, fill="both", expand=True)
    
        # Small helper label
        tk.Label(
            popup,
            text="(Comma or whitespace separated. Blank line = move down)",
            anchor="w",
            justify="left",
            wraplength=320,
        ).pack(padx=10, pady=(0, 10), fill="x")
    
        def addByAddress(input_text: str):
            editor = self
            padding_x = 20
            padding_y = 30
            max_width = 5000  # unused in this version (kept for compatibility)
    
            current_y = 0
            found = 0
    
            # Set starting Y position based on existing glyphs
            for box in getattr(editor, "boxes", []):
                if box:
                    try:
                        new_y = box.y + box.getHeight() + padding_y
                    except Exception:
                        # Some boxes use getHeight(absolute=True) elsewhere; fallback
                        try:
                            new_y = box.y + box.getHeight(absolute=True) + padding_y
                        except Exception:
                            continue
                    current_y = max(current_y, new_y)
    
            lines = input_text.strip().splitlines()
    
            for line in lines:
                line = line.strip()
    
                # Blank line = vertical spacing
                if not line:
                    current_y += 200
                    continue
    
                # Split by commas and/or whitespace
                tokens = [t for part in line.split(",") for t in part.strip().split()]
                current_x = 0
    
                for token in tokens:
                    # allGlyphs is assumed to exist in your module scope (as in your original code)
                    matched = next((g for g in allGlyphs if g.address == token), None)
    
                    if matched:
                        try:
                            im = Image.open(matched.filepath)
                            new_glyph_box = glyphBox(editor, image=im, x=current_x, y=current_y, glyph=matched)
                            new_glyph_box.imagefile = matched.filepath
                            new_glyph_box.boxIndex = editor.get_unique_boxIndex()
                            editor.boxes.append(new_glyph_box)
    
                            current_x += im.width + padding_x
                            found += 1
                        except Exception as e:
                            print(f"⚠️ Could not load {token} from {matched.filepath}: {e}")
                    else:
                        print(f"⚠️ No glyph found for address '{token}'")
    
                # Always move down after each non-empty line
                current_y += 200
    
            print(f"✅ Added {found} glyphs.")
            try:
                editor.repaint()
            except Exception:
                pass
            popup.destroy()
    
        def on_add():
            input_text = text.get("1.0", "end-1c")
            addByAddress(input_text)
    
        def on_cancel():
            popup.destroy()
    
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=10)
    
        ttk.Button(btn_frame, text="Add", command=on_add).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=5)
    
        # Close on Escape
        popup.bind("<Escape>", lambda e: popup.destroy())

    def align_selection_into_rows(self, row_gap=25):
        """
        Align currently selected boxes into rows using:
          - Two boxes are in the same row if their vertical spans overlap
            (i.e., exists a horizontal line that intersects both).
          - Greedily merge boxes into rows by transitive overlap.
          - Sort rows top->bottom by average y.
          - For each row:
              * Set all box.y to max(box.y) within that row (highest y).
              * Then place next row so that prev_row_bottom + row_gap = next_row_top
                (after its internal y unification).
        """
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("⚠️ No selection to align.")
            return
    
        boxes = list(self.currentSelection.glyphs)
    
        # Only boxes that have geometry
        boxes = [b for b in boxes if hasattr(b, "y") and hasattr(b, "getHeight")]
        if not boxes:
            print("⚠️ Selection has no alignable boxes.")
            return
    
        # Helper: vertical interval in logical coords
        def y_interval(b):
            y0 = float(b.y)
            y1 = y0 + float(b.getHeight(absolute=True))
            return y0, y1
    
        def overlaps(a, b):
            a0, a1 = y_interval(a)
            b0, b1 = y_interval(b)
            return not (a1 <= b0 or b1 <= a0)
    
        # --- Greedy grouping with transitive closure (like connected components) ---
        remaining = set(boxes)
        rows = []
    
        while remaining:
            seed = next(iter(remaining))
            group = {seed}
            remaining.remove(seed)
    
            changed = True
            while changed:
                changed = False
                # scan a snapshot because we'll remove from remaining
                for b in list(remaining):
                    # if b overlaps any in group, pull it in
                    if any(overlaps(b, g) for g in group):
                        group.add(b)
                        remaining.remove(b)
                        changed = True
            rows.append(list(group))
    
        # --- Sort rows top->bottom by average y (smaller y = higher on canvas) ---
        def row_avg_y(row):
            return sum(float(b.y) for b in row) / max(1, len(row))
    
        rows.sort(key=row_avg_y)
    
        # --- Align rows according to your rules ---
        # First row adopts the highest y among its boxes (max y)
        def row_top(row):
            return min(float(b.y) for b in row)
    
        def row_bottom(row):
            return max(float(b.y) + float(b.getHeight(absolute=True)) for b in row)
    
        # 1) unify first row y to max y
        first = rows[0]
        first_y = max(float(b.y) for b in first)
        for b in first:
            b.y = first_y
            b.translated = True
    
        prev_bottom = row_bottom(first)
    
        # 2) for each next row:
        for row in rows[1:]:
            # unify row y internally first (to its own max y)
            row_y = max(float(b.y) for b in row)
            for b in row:
                b.y = row_y
                b.translated = True
    
            # now shift whole row so that its top == prev_bottom + gap
            cur_top = row_top(row)
            target_top = prev_bottom + float(row_gap)
            dy = target_top - cur_top
    
            for b in row:
                b.y = float(b.y) + dy
                b.translated = True
    
            prev_bottom = row_bottom(row)
    
        # repaint
        try:
            self.currentSelection.find_bounds()
            self.currentSelection.repaint()
        except Exception:
            # fallback repaint
            for b in boxes:
                try:
                    b.repaint(force=True)
                    b.paint_links(force=True)
                except Exception:
                    pass
            self.repaint()



    def copy_all_addresses_to_clipboard(self, mode="list"):
        """
        Copy addresses of currently selected glyphs to clipboard.
        
        Args:
            mode (str): 
                - "list"  → newline-separated (default)
                - "latex" → '\\glyph{address} ' concatenation
        """
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("⚠️ No glyphs selected.")
            return
    
        # Get selected glyphs with valid addresses
        glyphs_with_addr = [
            box.glyph for box in self.currentSelection.glyphs
            if getattr(box, "glyph", None) and getattr(box.glyph, "address", None)
        ]
    
        # Sort them in corpus order
        glyphs_sorted = sorted(
            glyphs_with_addr,
            key=lambda g: allGlyphs.index(g) if g in allGlyphs else float('inf')
        )
    
        if not glyphs_sorted:
            print("⚠️ No valid glyph addresses found in selection.")
            return
    
        # Choose format
        if mode == "latex":
            address_text = "".join([f"\\glyph{{{g.address}}} " for g in glyphs_sorted])
        else:
            address_text = "\n".join([g.address for g in glyphs_sorted])
    
        # Copy to clipboard
        try:
            self.clipboard_clear()
            self.clipboard_append(address_text)
            self.update()
            print(f"✅ Copied {len(glyphs_sorted)} selected glyph addresses to clipboard ({mode} mode).")
        except Exception as e:
            print(f"❌ Error copying addresses to clipboard: {e}")
            

    def do_pca_on_selection(self):
        from sklearn.decomposition import PCA
        import numpy as np
        import math
    
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("No glyphs selected for PCA.")
            return
    
        glyphs = self.currentSelection.glyphs
        vectors = []
        valid_glyph_boxes = []
    
        # Load embeddings
        for g_box in glyphs:
            if g_box.glyph is None:
                continue
            
            embedding = embeddings.load_embedding_for_glyph(g_box.glyph.address)
            if embedding is not None:
                vectors.append(embedding)
                valid_glyph_boxes.append(g_box)
    
        if not vectors:
            print("No valid embeddings found for selection.")
            return
    
        X = np.array(vectors)
    
        # Perform PCA
        pca = PCA(n_components=2)
        coords_2d = pca.fit_transform(X)
    
        # Determine bounding box for the 2D coords
        xs = coords_2d[:, 0]
        ys = coords_2d[:, 1]
    
        min_x, max_x = xs.min(), xs.max()
        min_y, max_y = ys.min(), ys.max()
    
        range_x = max_x - min_x if max_x != min_x else 1
        range_y = max_y - min_y if max_y != min_y else 1
    
        # ---------------------------------------
        #  Keep a consistent glyphs-per-area ratio
        # ---------------------------------------
        N = len(valid_glyph_boxes)
        base_area_per_glyph = 250000  # For example: 40 glyphs => 10,000 total area => 250 per glyph
        desired_area = base_area_per_glyph * N
        
        # so the bounding "square" side is sqrt(desired_area)
        desired_size = math.sqrt(desired_area)
        
        # scale to fit PCA output into that bounding square
        scale_x = desired_size / range_x
        scale_y = desired_size / range_y
        scale = min(scale_x, scale_y)
        
        # Decide offsets so you don't start at (0,0)
        offset_x, offset_y = 100, 100
    
        for i, g_box in enumerate(valid_glyph_boxes):
            proj_x = (xs[i] - min_x) * scale + offset_x
            proj_y = (ys[i] - min_y) * scale + offset_y
    
            g_box.x = proj_x
            g_box.y = proj_y
            g_box.translated = True
    
        # Repaint
        for g_box in valid_glyph_boxes:
            g_box.repaint(force=True)
            g_box.paint_links(force=True)
    
        self.repaint()
        print("PCA layout complete.")



    def addTypeGlyph(self,num,x,y):
        
        numString=""
        if(num<10):
            numString="00"
        elif(num<100):
            numString="0"
        numString+=str(num)

        imagepath="Glyph Types\\"+numString+".GIF"
        try:
            glyph=KohauCode_Horley.Glyph()
            glyph.text=numString
            newGlyph=glyphBox(self,x=x,y=y,glyph=glyph,image=Image.open(imagepath))
            newGlyph.imagefile=imagepath
            self.boxes.append(newGlyph)
        except:
            None

    def make_group(self):

        occurrences = {
            "Stanza": 1,
            "No Agreement": 1,
            "Full Agreement": 1,
            "Unsorted (P)": 1,
            "Stylistic (P)": 1,
            "Additions (P)": 1,
            "Deletions (P)": 1,
            "Unsorted (Q)": 1,
            "Stylistic (Q)": 1,
            "Additions (Q)": 1,
            "Deletions (Q)": 1,
            "Unsorted (H)": 1,
            "Stylistic (H)": 1,
            "Additions (H)": 1,
            "Deletions (H)": 1,
        }
        
        """
        Opens a selection popup to choose a group category and creates a CompoundBox.
        """
        if self.currentSelection is None or not self.currentSelection.glyphs:
            print("No glyphs selected for grouping.")
            return
    
        # Open the search popup with the occurrences dictionary
        popup = SearchPopup(self, occurrences)
        self.wait_window(popup)  # Pause execution until popup closes
    
        # Retrieve the selected category
        selected_label = popup.result
        if not selected_label:
            print("Group creation canceled.")
            return
    
        # Create the CompoundBox using the selected label as the title
        new_group = CompoundBox(self.currentSelection.glyphs, selected_label, self)
        self.boxes.append(new_group)
        
        # Clear the current selection after grouping
        self.currentSelection = None
        self.repaint()
        print(f"✅ Created group: {selected_label}")

    def remove_selected_glyphs_from_groups(self):
        """
        Removes all selected glyphs from all compound glyph groups.
        If a group becomes empty, it is removed as well.
        """
        if not self.currentSelection or not self.currentSelection.glyphs:
            print("No glyphs selected for removal.")
            return
    
        selected_glyphs = set(self.currentSelection.glyphs)
    
        # Iterate through all CompoundBox instances
        for selected_box in selected_glyphs:
            for box in self.boxes:
                if isinstance(box, CompoundBox):
                    if(selected_box in box.boxes):
                        box.boxes.remove(selected_box)
    
        groups_to_remove = []
        for box in self.boxes:
            if isinstance(box, CompoundBox):
                if not box.boxes:
                    groups_to_remove.append(box)
    
        # Remove empty groups
        for group in groups_to_remove:
            group.delete()
            self.boxes.remove(group)
            del group
    
        self.repaint()
        print("✅ Selected glyphs removed from all groups.")

    
    def select_group_label(self):
        """
        Opens a popup for the user to select a label for the glyph group.
        Returns the selected label or None if canceled.
        """
        popup = ttk.Toplevel(self)
        popup.title("Select Group Label")
        popup.geometry("300x150")
        
        # Variable to store selection
        selected_var = tk.StringVar()
        selected_var.set("No Agreement")  # Default selection
    
        # Dropdown menu for labels
        label_dropdown = ttk.OptionMenu(popup, selected_var, *occurrences.keys())
        label_dropdown.pack(pady=10)
    
        # Confirm button
        def confirm():
            popup.selected_label = selected_var.get()
            popup.destroy()
    
        btn_confirm = ttk.Button(popup, text="Confirm", command=confirm)
        btn_confirm.pack(pady=10)
    
        # Wait until the popup is closed
        popup.selected_label = None
        popup.transient(self)
        popup.grab_set()
        self.wait_window(popup)
    
        return popup.selected_label

    

        
    def addGlyph(self,glyph,x,y,imagepath=""):
        
        if(imagepath==""):
            imagepath=glyph.filepath
        
        try:
            from PIL import Image
            Image.open(imagepath)
        except:
            glyph.saveSvg(KohauCode_Horley.root+"Glyphs\\temp.svg")
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPM
            from PIL import Image
            drawing = svg2rlg(KohauCode_Horley.root+"Glyphs\\temp.svg")
            renderPM.drawToFile(drawing, imagepath, fmt="jpg")

        newGlyph=glyphBox(self,x=x,y=y,glyph=glyph,image=Image.open(imagepath))
        newGlyph.imagefile=imagepath
        self.boxes.append(newGlyph)
        
    def linkSelectedGlyphs(self,ghost=None):
        if(self.currentSelection != None):
            self.currentSelection.linkSelectedGlyphs()
        self.currentSelection=None

    def rePlaced(self):
        #TODO
        return True
        
    def repaint(self):
        
        self.update_currentSelection()
            
        for comp in self.components:
            self.canvas.delete(comp)
        self.components=[]

        #print(len(self.boxes))
            
        for g in self.boxes:
                
            if(g != None):
                g.paint_links()
                    
        for g in self.boxes:
            if(g != None):
                g.repaint()
                
        if(self.selection_box!=None):
                
            x1,y1=self.selection_box.x1, self.selection_box.y1
            x2,y2=self.selection_box.x2, self.selection_box.y2
            self.components.append(self.canvas.create_rectangle(x1,y1,x2,y2,outline='blue'))
                
        if(self.currentSelection!=None):
                
            x1,y1=self.view.getCoords(self.currentSelection.x1, self.currentSelection.y1)
            x2,y2=self.view.getCoords(self.currentSelection.x2, self.currentSelection.y2)
                
            self.components.append(self.canvas.create_rectangle(x1,y1,x2,y2,outline='blue'))
            
        create_circle(self.mouse.last_x,self.mouse.last_y,5,self)
        
    def pan(self,dx,dy):
        
        self.view.x_off+=dx
        self.view.y_off+=dy
        self.view.panning=True
        
    def move_currentSelection(self,dx,dy):
        
        deltaX=dx/self.view.scale
        deltaY=dy/self.view.scale

        for g in self.currentSelection.glyphs:

            g.translated=True
            
            g.x+=deltaX
            g.y+=deltaY

            g.repaint(force=True)
            g.paint_links(force=True)

        self.currentSelection.find_bounds()
        
    def onMouseMove(self, e):
        print(self.transliteration_frame.lock_var.get())
        if self.mouse.moving:
            if self.selection_box is not None:
                # ✅ Dragging to create a selection box
                self.selection_box.x2 = e.x
                self.selection_box.y2 = e.y
                self.repaint_selection_box()

            else:
                if self.moving_selection and self.currentSelection is not None:
                # ✅ Moving selected glyphs (but only if lock is NOT enabled)
                    if not self.transliteration_frame.lock_var.get():
                        dx = (e.x - self.mouse.last_x) / self.view.scale
                        dy = (e.y - self.mouse.last_y) / self.view.scale
                        for g in self.currentSelection.glyphs:
                            g.x += dx
                            g.y += dy
                            g.translated = True
                            g.repaint(force=True)
                            g.paint_links(force=True)
                        self.currentSelection.find_bounds()
                    
                else:
                    # ✅ Panning the entire scene
                    dx = e.x - self.mouse.last_x
                    dy = e.y - self.mouse.last_y
                    self.pan(dx, dy)
    
                self.repaint()
                
        # Update last-known mouse coords
        self.mouse.last_x = e.x
        self.mouse.last_y = e.y

    def repaint_selection_box(self):
        """Redraws the selection box rectangle while dragging without updating glyph selection."""
        self.canvas.delete("selection_box")  # Remove old selection box
        if self.selection_box is not None:
            x1, y1 = self.selection_box.x1, self.selection_box.y1
            x2, y2 = self.selection_box.x2, self.selection_box.y2
            self.canvas.create_rectangle(x1, y1, x2, y2, outline='blue', tags="selection_box")


    def scroll_wheel(self,event):
        
        scale = 1.0
        
        if event.num == 5 or event.delta == -120:  # scroll down
            scale /= self.mouse.scroll_delta
        if event.num == 4 or event.delta == 120:  # scroll up
            scale *= self.mouse.scroll_delta

        self.view.rescale(scale,event.x,event.y)
        #self.view.scale*=scale

        self.repaint()
    
    def add_to_selected(self,glyphs):
        
        if(self.currentSelection==None):
                
            self.currentSelection=Selection_Box(0,0) 
                
        self.currentSelection.add_glyphs(glyphs)

    def add_image_box(self):
        imagefile = get_text_input("Enter image filename")
        x, y = self.view.getInvCoords(self.mouse.last_x, self.mouse.last_y)
        self.addImageBox(imagefile, x, y)


    def onRightClick(self,event):
        
        m = Menu(self.canvas, tearoff=0)
        
        m.add_command(label="Load",command=self.load)
        m.add_command(label="Save As",command=self.save)
        m.add_command(label="Save Glyph Selection",command=self.save_glyph_group)
        m.add_command(label="Add Line",command=self.addGlyphsInLine)
        #m.add_command(label="Delete",command=self.deleteSelectedGlyphs)
        m.add_command(label="Unlink Glyphs",command=self.unlink)
        m.add_command(label="Align Glyphs Horizontally",command=self.align_glyphs_horizontally)
        m.add_command(label="Align Glyphs Vertically",command=self.align_glyphs_vertically)
        m.add_command(label="Add Text Box",command=self.add_text_box)
        m.add_command(label="Add Image Box",command=self.add_image_box)
        m.add_command(label="Sort Selection",command=self.reSortHorizontal)
        m.add_command(label="Sort Selection Vertically", command=self.reSortVertical)
        #m.add_command(label="Insert Next Glyph",command=self.insert_next_glyph)
        
        try:
            
            m.tk_popup(event.x_root, event.y_root)
            
        finally:
            
            m.grab_release()

    def add_text_box(self):
        text=get_text_input("Please input text here")
        x,y=self.view.getCoords(self.mouse.last_x,self.mouse.last_y)
        self.boxes.append(textBox(self,text=text,x=x,y=y))

    def addImageBox(self, imagefile, x, y):
        newImageBox = imageBox(self, x=x, y=y, imagefile=imagefile)
        self.boxes.append(newImageBox)


    def load(self, filename=""):
        """
        Loads data from a file. If no filename is provided,
        a file dialog is opened to select the file.
        Supports txt, xml, and json formats.
        """
        import os
        from tkinter import filedialog
    
        if filename == "":
            filename = filedialog.askopenfilename(
                title="Open File",
                filetypes=(("JSON Files", "*.json"),
                           ("XML Files", "*.xml"),
                           ("Text Files", "*.txt"),
                           ("All Files", "*.*"))
            )
            if not filename:
                return  # User cancelled
    
        print(f"Loading from file: {filename}")
        # Decide what to do based on file extension.
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
    
        if ext == ".json":
            self.load_json(filename)
        elif ext == ".xml":
            self.load_xml(filename)
        elif ext == ".txt":
            self.load_txt(filename)
        else:
            print(f"Error: Unsupported file type for {filename}")


    def load_json(self, filename):

        global globalGlyphCounter
        
        import json
        import os
        from PIL import Image
    
        if not os.path.exists(filename):
            print(f"File not found: {filename}")
            return
    
        # Clear any existing data
        self.boxes.clear()
        self.canvas.delete("all")
    
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading JSON: {e}")
            return
    
        index_to_box = {}
        used_indices = set()          # Track existing indices (including duplicates)
        max_index = -1                # Track the largest index found
    
        # First pass: Create boxes (glyphBox, textBox, imageBox) without links
        for entry in data.get("boxes", []):
            box_type = entry.get("type", "")
            x = entry.get("x", 0)
            y = entry.get("y", 0)
    
            # -- 1) Check for duplicates --
            old_idx = entry.get("boxIndex", -1)
            if old_idx < 0:
                # If the file had an invalid or negative index, treat as “unassigned”
                old_idx = None
            elif old_idx in used_indices:
                # Found a duplicate!
                print(f"⚠️ Duplicate index {old_idx} encountered; reassigning.")
                old_idx = None
            else:
                # Mark it used
                used_indices.add(old_idx)
                max_index = max(max_index, old_idx)
    
            # Decide what box to create (glyphBox, textBox, imageBox)
            if box_type == "glyphBox":
                glyph_address = entry.get("glyph_address", "")
                glyph_obj = None
                if glyph_address:
                    try:
                        glyph_obj = KohauCode_Horley.Glyph(glyph_address)
                    except Exception as e:
                        print(f"Error loading glyph from address {glyph_address}: {e}")
    
                # Load image if possible
                imagefile = glyph_obj.filepath if glyph_obj else ""
                if os.path.exists(imagefile):
                    im = Image.open(imagefile)
                else:
                    im = None
    
                new_box = glyphBox(self, x=x, y=y, image=im)
                new_box.imagefile = imagefile
                new_box.glyph = glyph_obj
    
            elif box_type == "textBox":
                text = entry.get("text", "")
                new_box = textBox(self, text=text, x=x, y=y)
    
            elif box_type == "imageBox":
                imagefile = entry.get("imagefile", "")
                new_box = imageBox(self, x=x, y=y, imagefile=imagefile)
            elif box_type == "CompoundBox":
                title = entry.get("title", "Untitled Group")
                boxIndex = entry.get("boxIndex", None)  # ✅ Preserve boxIndex
                linked_glyph_indices = entry.get("linked_glyph_indices", [])
                linked_glyph_addresses = entry.get("linked_glyph_addresses", [])
                
                # Collect referenced glyphs using both index and address redundancy
                linked_glyphs = []
                for idx in linked_glyph_indices:
                    if idx in index_to_box:
                        linked_glyphs.append(index_to_box[idx])
                
                # In case some glyphs were missed, use glyph addresses as a fallback
                if not linked_glyphs:
                    for glyph in allGlyphs:
                        if glyph.address in linked_glyph_addresses:
                            for box in self.boxes:
                                if box.glyph and box.glyph.address == glyph.address:
                                    linked_glyphs.append(box)
        
                # If glyphs were found, recreate the CompoundBox
                if linked_glyphs:
                    new_group = CompoundBox(linked_glyphs, title, self)
                    new_group.boxIndex = boxIndex if boxIndex else self.get_unique_boxIndex()
                    self.boxes.append(new_group)
                    index_to_box[new_group.boxIndex] = new_group  # ✅ Store in index mapping
    
            else:
                print(f"Unknown box type '{box_type}' - skipping.")
                continue
    
            # -- 2) Reassign a unique index if needed --
            if old_idx is None:
                # We reassign using either an internal counter or by scanning used_indices
                while globalGlyphCounter in used_indices:
                    globalGlyphCounter += 1
                assigned_idx = globalGlyphCounter
                used_indices.add(assigned_idx)
                globalGlyphCounter += 1
            else:
                # old_idx was valid and not a duplicate
                assigned_idx = old_idx
    
            new_box.boxIndex = assigned_idx
            index_to_box[assigned_idx] = new_box
            self.boxes.append(new_box)
    
        # Make sure globalGlyphCounter is at least max_index + 1
        #if max_index >= globalGlyphCounter:
        #    globalGlyphCounter = max_index + 1
    
        # Second pass: Link boxes together
        for entry in data.get("boxes", []):
            old_idx = entry.get("boxIndex", -1)
            linked_indices = entry.get("linkedIndices", [])
    
            # If the old_idx was forced to change above, that’s fine – 
            # we only link if old_idx is a valid key in index_to_box
            if old_idx not in index_to_box:
                continue
    
            current_box = index_to_box[old_idx]
            for linked_idx in linked_indices:
                if linked_idx in index_to_box:
                    current_box.linkto(index_to_box[linked_idx])
                else:
                    print(f"⚠️ Link target {linked_idx} not found.")
    
        print(f"✅ Loaded JSON from: {filename} - all glyphs now have unique indices.")
        self.repaint()




    def save(self, filename=""):
        """
        Save the project to a file. Supports txt, xml, and json formats.
        - Defaults to JSON if no extension is provided.
        - Saves in extended JSON format for .json files.
        """
        if not filename:
            filename = filedialog.asksaveasfilename(
                title="Save As",
                defaultextension=".json",
                filetypes=(
                    ("JSON Files", "*.json"),
                    ("XML Files", "*.xml"),
                    ("Text Files", "*.txt"),
                    ("All Files", "*.*"),
                )
            )
            if not filename:
                return  # User canceled save

        # Determine file extension
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        # Route to appropriate save handler
        if ext == ".txt":
            self.save_txt(filename)
        elif ext == ".xml":
            self.save_xml(filename)
        elif ext == ".json":
            self.save_json(filename)  # Use the updated JSON save function
        else:
            print(f"Unsupported file format: {ext}")

    def save_json(self, filename):
        """
        Saves the project to a JSON file in extended format.
        Includes:
          - glyph_address for glyphBox
          - linked_glyph_addresses (list of linked glyph addresses)
          - linked_text_strings (list of text from linked textBoxes)
          - boxIndex and linkedIndices for loading integrity
        """
        import json

        # Prepare data structure
        data = {
            "boxes": []
        }

        # Collect info from self.boxes
        for box in self.boxes:
            # Common fields for all boxes
            box_info = {
                "type": box.__class__.__name__,  # e.g., "glyphBox", "textBox", "imageBox"
                "x": box.x,
                "y": box.y,
                "boxIndex": box.boxIndex  # Ensure this is unique per box
            }

            # Handle glyphBox-specific fields
            if isinstance(box, glyphBox):
                glyph_address = box.glyph.address if box.glyph else ""
                linked_glyph_addresses = []
                linked_text_strings = []
                linked_indices = []

                # Process linked boxes
                for linked_obj in box.linkedBoxes:
                    if isinstance(linked_obj, glyphBox) and linked_obj.glyph:
                        linked_glyph_addresses.append(linked_obj.glyph.address)
                        linked_indices.append(linked_obj.boxIndex)
                    elif isinstance(linked_obj, textBox):
                        linked_text_strings.append(linked_obj.text)
                        linked_indices.append(linked_obj.boxIndex)  # Assuming textBox has boxIndex

                # Add glyphBox fields
                box_info["glyph_address"] = glyph_address
                box_info["linked_glyph_addresses"] = linked_glyph_addresses
                box_info["linked_text_strings"] = linked_text_strings
                box_info["linkedIndices"] = linked_indices  # Standard linking field

            # Handle textBox-specific fields
            elif isinstance(box, textBox):
                box_info["text"] = box.text
                linked_indices = []
                for linked_obj in box.linkedBoxes:
                    if isinstance(linked_obj, glyphBox):
                        linked_indices.append(linked_obj.boxIndex)
                box_info["linkedIndices"] = linked_indices

            # Handle imageBox-specific fields
            elif isinstance(box, imageBox):
                box_info["imagefile"] = box.imagefile
                linked_indices = []
                for linked_obj in box.linkedBoxes:
                    if isinstance(linked_obj, glyphBox):
                        linked_indices.append(linked_obj.boxIndex)
                    elif isinstance(linked_obj, textBox):
                        linked_indices.append(linked_obj.boxIndex)  # Assuming textBox has boxIndex
                box_info["linkedIndices"] = linked_indices

            elif isinstance(box, CompoundBox):
                # Save CompoundBox with its glyph references
                linked_glyph_indices = [g.boxIndex for g in box.boxes]
                linked_glyph_addresses = [g.glyph.address for g in box.boxes if g.glyph]
            
                box_info["type"] = "CompoundBox"
                box_info["boxIndex"] = box.boxIndex  # ✅ Now properly assigned
                box_info["title"] = box.title
                box_info["linked_glyph_indices"] = linked_glyph_indices
                box_info["linked_glyph_addresses"] = linked_glyph_addresses  # Redundancy
                
                data["boxes"].append(box_info)

            # Append box info
            data["boxes"].append(box_info)

        # Write JSON to disk
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"JSON saved successfully to: {filename}")
        except Exception as e:
            print(f"Error saving JSON: {e}")
                                                            
    def add_type_glyph(self, glyph_index, x_offset=0, y_offset=0):
        """
        Adds a glyph of the specified type at a position offset by x_offset and y_offset.
        """

        # Validate glyph_index and format as a 3-digit string
        try:
            glyph_index = int(glyph_index)
            num_string = f"{glyph_index:03}"  # Formats as 3 digits with leading zeros
        except ValueError:
            print(f"Invalid glyph index: {glyph_index}")
            return
    
        # Build image file path
        imfile = rf"C:\Users\gpbla\Desktop\RongoRongo Studies\Beta\Glyph Types\{num_string}.GIF"
    
        try:
            # Load image
            im = Image.open(imfile)
        except FileNotFoundError:
            print(f"Image file not found: {imfile}")
            return
    
        # Create new glyph object
        glyph = KohauCode_Horley.Glyph()
        glyph.text = num_string
    
        xhigh = self.currentSelection.x2
        yhigh = self.currentSelection.y1
    
        new_glyph_box = glyphBox(
            self, 
            image=im, 
            x=xhigh + x_offset, 
            y=yhigh + y_offset, 
            glyph=glyph
        )
        new_glyph_box.imagefile = imfile
        new_glyph_box.boxIndex = self.get_unique_boxIndex()
    
        # Add the new glyph box to the list of boxes
        self.boxes.append(new_glyph_box)

    def add_corpus(self, max_width=5000, padding=30):
        """
        Adds all glyphs in the corpus in a horizontal layout.
        Wraps to the next line when exceeding max_width.
        """
        import os
        from PIL import Image
    
        # Find the max Y position for placing the corpus glyphs below existing ones
        max_y = 0
        for box in self.boxes:
            if box:
                new_y = box.y + box.getHeight() + padding
                max_y = max(max_y, new_y)
        
        current_x, current_y = 0, max_y
    
        for glyph in allGlyphs:  # Iterate over all glyphs in the corpus
            try:
                im_file = glyph.filepath  # Assume this is the correct file path
                if not os.path.exists(im_file):
                    print(f"⚠️ Image file not found: {im_file}")
                    continue
    
                im = Image.open(im_file)
    
                # Create a new glyphBox and add it to the display
                new_glyph_box = glyphBox(
                    self,
                    image=im,
                    x=current_x,
                    y=current_y,
                    glyph=glyph
                )
                new_glyph_box.imagefile = im_file
                new_glyph_box.boxIndex = self.get_unique_boxIndex()
    
                self.boxes.append(new_glyph_box)
    
                # Move to the next position
                current_x += im.width + 20
                if current_x > max_width:  # Wrap to the next row if needed
                    current_x = 0
                    current_y += 200
    
            except Exception as e:
                print(f"❌ Error adding glyph {glyph.address}: {e}")
    
        self.repaint()
            

    def addGlyphsInLine(self, address="", max_width=5000, padding=30):
        """
        Adds glyphs in a horizontal 'line' based on an address input.
        
        - If the address contains multiple space-separated numbers, each number is interpreted as a glyph index
          to be added horizontally.
        - If the address is a single integer, a type glyph is added directly.
        - Otherwise, it searches through `allGlyphs` for candidates whose addresses (or subglyph addresses in compound glyphs)
          contain the provided address and places matching glyphs horizontally.
        
        :param address: The user-input address string (can be blank; will prompt if empty).
        :param max_width: The maximum horizontal space before wrapping to the next line.
        :param padding: Vertical padding applied when calculating the next row's Y-position.
        """
        import os
        from PIL import Image
    
        # 1. Prompt user if no address is provided.
        if not address:
            address = get_text_input("Input Line")
        print(f"DEBUG: Starting addGlyphsInLine with address: {address}")
    
        # 2. If address contains spaces, assume it’s multiple glyph indices.
        if " " in address:
            x_offset = 0
            for glyph_num_str in address.split():
                print(f"DEBUG: Adding glyph from number string: {glyph_num_str}")
                self.add_type_glyph(glyph_num_str, x_offset=x_offset)
                x_offset += 30
            return
    
        # 3. Calculate the maximum Y coordinate among existing boxes.
        max_y = 0
        for box in self.boxes:
            if box:
                new_y = box.y + box.getHeight() + padding
                max_y = max(max_y, new_y)
        print(f"DEBUG: Calculated max_y for new glyphs: {max_y}")
    
        # 4. If address is a single integer, call add_type_glyph.
        try:
            int_value = int(address)
            print(f"DEBUG: Address interpreted as single integer: {int_value}")
            self.add_type_glyph(int_value)
            return
        except ValueError:
            print(f"DEBUG: Address is not a single integer: {address}")
    
        if not address.strip():
            print("DEBUG: Address is empty (after stripping). Exiting addGlyphsInLine.")
            return
    
        current_x, current_y = 0, max_y + 200
    
        # 5. Iterate over allGlyphs to find matching candidates.
        for glyph_candidate in allGlyphs:
            # Skip the candidate if its main address is empty.
            if not glyph_candidate.address.strip():
                print(f"DEBUG: Skipping candidate with empty address: {glyph_candidate}")
                continue
    
            glyph_match = False
    
            # Check whether the search address is in the candidate's main address.
            if address in glyph_candidate.address:
                glyph_match = True
    
            # If no match was found, skip this candidate.
            if not glyph_match:
                continue
    
            try:
                # 6. Build the image file path.
                if isinstance(glyph_candidate, KohauCode_Horley.Glyph):
                    im_file = glyph_candidate.filepath
                    print(f"DEBUG: (Simple Glyph) Constructed image path: {im_file}")
                else:
                    print(f"DEBUG: Unknown glyph type for candidate: {type(glyph_candidate)}. Skipping.")
                    continue
    
                # 7. Check if the image file exists.
                if not os.path.exists(im_file):
                    print(f"ERROR: Image file not found for candidate (expected file: {im_file})")
                    continue
    
                print(f"DEBUG: Attempting to open image file: {im_file}")
                im = Image.open(im_file)
    
                # 8. Create a new glyphBox for the matched glyph.
                new_glyph_box = glyphBox(self, image=im, x=current_x, y=current_y, glyph=glyph_candidate)
                new_glyph_box.imagefile = im_file
                new_glyph_box.boxIndex = self.get_unique_boxIndex()
    
                # 9. Update the x (and potentially y) position for the next glyph.
                current_x += im.width + 20
                if current_x > max_width:  # Wrap to the next row if needed.
                    current_x = 0
                    current_y += 200
    
                self.boxes.append(new_glyph_box)
    
            except Exception as e:
                print(f"ERROR: Could not process candidate {glyph_candidate} with file {im_file} due to: {e}")




                    
    def deleteSelectedGlyphs(self, event=None):
        """Deletes all selected glyphs and ensures their transliteration labels are removed."""
        if self.currentSelection is not None:
            for g in self.currentSelection.glyphs:
                for tempG in self.boxes:
                    if g in tempG.linkedBoxes:
                        tempG.linkedBoxes.remove(g)
    
                g.delete()
                if g in self.boxes:
                    self.boxes.remove(g)

                #handle instances in compound boxes
                for box in self.boxes:
                    if(type(box) == CompoundBox):
                        if(g in box.boxes):
                            box.boxes.remove(g)
                        if(len(box.boxes) == 0):
                            self.boxes.remove(box)
                            del box
                del g
    
            self.currentSelection = None
            self.repaint()

            
    def unlink(self):
        if(self.currentSelection != None):
            self.currentSelection.unlink()

    def align_glyphs_horizontally(self, *args):
        if(self.currentSelection != None):
            self.currentSelection.align_glyphs_horizontally()
            self.currentSelection=None
    
    def align_glyphs_vertically(self, *args):
        if(self.currentSelection != None):
            self.currentSelection.align_glyphs_vertically()
            self.currentSelection=None

    def auto_align(self,ghost):
        if(self.currentSelection != None):
            self.currentSelection.auto_align_glyphs()

    def save_glyph_group(self, filename=""):
        from tkinter import filedialog
    
        if filename == "":
            filename = filedialog.asksaveasfilename(
                title="Save Glyph Group As",
                defaultextension=".txt",
                filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
            )
            if not filename:  # User cancelled
                return
    
        if self.currentSelection is not None:
            self.currentSelection.save_glyph_group(filename)

    def reSortHorizontal(self):
        if self.currentSelection is not None:
            # Get the chosen criterion from the dropdown
            criterion = self.selected_sort_criteria.get()
            self.currentSelection.reSortHorizontal(criterion=criterion)
    
    def reSortVertical(self):
        if self.currentSelection is not None:
            criterion = self.selected_sort_criteria.get()
            self.currentSelection.reSortVertical(criterion=criterion)

    def get_unique_boxIndex(self):
        """
        Finds the next available unique boxIndex.
        Ensures that no two glyphs get the same index.
        """
        global globalGlyphCounter
        used_indices = {g.boxIndex for g in self.boxes}  # Collect all used indices

        while globalGlyphCounter in used_indices:
            globalGlyphCounter += 1  # Skip used indices
        
        return globalGlyphCounter

    def insert_succeeding_glyph(self, event=None):
        """
        Inserts the next glyph (based on the index in `allGlyphs`) 
        to the right of each glyph in the current selection.
        """
        def get_glyph_index(glyph_obj):
                """Return the index of glyph_obj in allGlyphs, or -1 if not found."""
                for idx, glyph in enumerate(allGlyphs):
                    if glyph_obj.address == glyph.address:
                        return idx
                return -1
    
    
        # If no current selection, do nothing
        if not self.currentSelection:
            return
    
        new_selected_glyphs = []
    
        # For each glyph in the current selection, insert the next glyph in `allGlyphs`
        for selected_box in self.currentSelection.glyphs:
            glyph_obj = selected_box.glyph
            glyph_idx = get_glyph_index(glyph_obj)
    
            # Ensure a valid index and that there's a succeeding glyph
            if glyph_idx == -1 or glyph_idx >= len(allGlyphs) - 1:
                continue
    
            # Prepare the new glyph object and image
            try:
                next_glyph_obj = allGlyphs[glyph_idx + 1]
                img_filename = next_glyph_obj.filepath
                new_image = Image.open(img_filename)
            except Exception as e:
                print(f"Error: could not add new glyph from {img_filename} - {e}")
                continue
    
            # Create a new glyphBox to the right of the selected glyph
            new_box = glyphBox(
                self,
                image=new_image,
                x=selected_box.x + selected_box.getWidth(absolute=True) + 30,
                y=selected_box.y,
                glyph=next_glyph_obj
            )
            new_box.imagefile = img_filename
            new_box.boxIndex = self.get_unique_boxIndex()
    
            self.boxes.append(new_box)
            new_selected_glyphs.append(new_box)
    
        # Update the selection to only include the newly added glyphs
        self.currentSelection.glyphs = new_selected_glyphs
        self.currentSelection.find_bounds()
        self.currentSelection.repaint()


    def insert_preseeding_glyph(self, event=None):
        """
        Inserts the preceding glyph (based on the index in `allGlyphs`) 
        to the left of each glyph in the current selection.
        """
        def get_glyph_index(glyph_obj):
            """Returns the index of `glyph_obj` in `allGlyphs`, or -1 if not found."""
            for idx, glyph in enumerate(allGlyphs):
                if glyph_obj.address == glyph.address:
                    return idx
            return -1
    
        # Ensure there is a current selection
        if not self.currentSelection:
            return
    
        new_selected_glyphs = []
    
        # Iterate through the glyphs in the current selection
        for selected_box in self.currentSelection.glyphs:
            glyph_obj = selected_box.glyph
            glyph_idx = get_glyph_index(glyph_obj)
    
            # Check for valid index and ensure there's a preceding glyph
            if glyph_idx == -1 or glyph_idx == 0:
                continue
    
            try:
                # Get the preceding glyph and its image
                preceding_glyph_obj = allGlyphs[glyph_idx - 1]
                img_filename = preceding_glyph_obj.filepath
                img = Image.open(img_filename)
    
                # Create a new glyphBox to the left of the selected glyph
                new_box = glyphBox(
                    self,
                    image=img,
                    x=selected_box.x - img.width - 30,
                    y=selected_box.y,
                    glyph=preceding_glyph_obj
                )
                new_box.imagefile = img_filename

                
                new_box.boxIndex = self.get_unique_boxIndex()

                # Append the new glyphBox to the list
                self.boxes.append(new_box)
                new_selected_glyphs.append(new_box)
    
            except Exception as e:
                print(f"Error: could not add new glyph - {e}")
    
        # Update the current selection with the new glyphs
        self.currentSelection.glyphs = new_selected_glyphs
        self.currentSelection.find_bounds()
        self.currentSelection.repaint()

                                       
    def onLeftMouseDown(self, e):
        self.control_down = bool(e.state & 0x0004)  # Control key check
        self.shift_down = bool(e.state & 0x0001)  # Shift key check
    
        self.mouse.last_x = e.x
        self.mouse.last_y = e.y
        x_log, y_log = self.view.getInvCoords(e.x, e.y)
    
        clicked_box = None
        for g in self.boxes:
            if g and g.inside(x_log, y_log):
                clicked_box = g
                break
    
        if clicked_box:
            self._clicked_on_glyph = True
            self.transliteration_frame.update_top_panel(clicked_box)

            if not self.transliteration_frame.multi_select_var.get():  # If multi-selection is OFF
                self.currentSelection = None  # Clear previous selection
    
            if self.currentSelection is None:
                self.currentSelection = Selection_Box(0, 0)
    
            # If the glyph is **not** already selected, add it to selection
            if clicked_box not in self.currentSelection.glyphs:
                self.currentSelection.add_glyphs([clicked_box])
    
            # If lock is enabled, do **not** allow moving
            if not self.transliteration_frame.lock_var.get():
                self.moving_selection = True
                self.mouse.moving = True  # ✅ Now dragging is enabled
    
        else:
            # Clicked empty space: deselect everything
            self._clicked_on_glyph = False
            if self.control_down:
                # Start a selection box
                self.selection_box = Selection_Box(e.x, e.y)
                self.mouse.moving = True
            else:
                # Only deselect if clicking empty space (not on a glyph)
                self.currentSelection = None
                self.mouse.moving = True  # Allow panning
    
        self.repaint()

    def onLeftMouseUp(self, e):
        if self.selection_box is not None:
            # Finalize selection box
            x1, y1 = self.view.getInvCoords(self.selection_box.x1, self.selection_box.y1)
            x2, y2 = self.view.getInvCoords(self.selection_box.x2, self.selection_box.y2)
            lx, hx = min(x1, x2), max(x1, x2)
            ly, hy = min(y1, y2), max(y1, y2)
    
            selected_glyphs = []
            for g in self.boxes:
                if g is not None:
                    center_x = g.x + g.getWidth(absolute=True) / 2
                    center_y = g.y + g.getHeight(absolute=True) / 2
                    if lx <= center_x <= hx and ly <= center_y <= hy:
                        selected_glyphs.append(g)
    
            if self.currentSelection is None:
                self.currentSelection = Selection_Box(x1, y1)
            self.currentSelection.add_glyphs(selected_glyphs)
            self.selection_box = None
            
        else:
            # If we didn't drag a selection box...
            if not self.moving_selection and not self.control_down and not self._clicked_on_glyph:
                # Clicked empty space w/o moving => clear selection
                self.currentSelection = None
        
        # Reset movement states
        self.moving_selection = False
        self.mouse.moving = False
        self.control_down = False
        self.shift_down = False
        self.canvas.delete("selection_box")
        self._clicked_on_glyph = False
        self.repaint()
        
            
    def update_currentSelection(self):
        # If there is a selection box, update its glyphs by checking their centers.
        if self.selection_box is not None:
            # Convert selection box corners from screen to logical coordinates.
            x1, y1 = self.view.getInvCoords(self.selection_box.x1, self.selection_box.y1)
            x2, y2 = self.view.getInvCoords(self.selection_box.x2, self.selection_box.y2)
            lx, hx = min(x1, x2), max(x1, x2)
            ly, hy = min(y1, y2), max(y1, y2)
            
            newGlyphs = []
            for g in self.boxes:
                if g is not None:
                    # Use the center of the box for inclusion testing.
                    center_x = g.x + g.getWidth(absolute=True) / 2
                    center_y = g.y + g.getHeight(absolute=True) / 2
                    if lx <= center_x <= hx and ly <= center_y <= hy:
                        newGlyphs.append(g)
                        g.isHighlighted = True
                    else:
                        g.isHighlighted = False
            self.selection_box.glyphs = newGlyphs


    
        

    
