from __future__ import annotations
from PIL import Image, ImageTk
import hashlib
import colorsys
from dataclasses import dataclass
from typing import Any, Optional, Tuple

SCALE_THRESHOLD = 0.25

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

    def draw_connecting_line(self, box, use_curved_line=True):

        current_scale = self.parent.view.scale
        if current_scale < SCALE_THRESHOLD:
            return
            
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