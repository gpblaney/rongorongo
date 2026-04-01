import tkinter as tk
from PIL import Image, ImageTk
import json
import os
import re
from KohauCode_Horley import Glyph  # Assuming this imports the Glyph class


def token_match(query_token: str, token: str, include_letters: bool = False) -> bool:
    """
    Returns True if query_token matches the transliteration token.

    If include_letters is True, allow matches like '600' -> '600a' (but not '6' -> '600').
    Still allows exact matches like '600' == '600'.
    """
    if token and token[0].isdigit():
        m = re.match(r'(\d+)', token)
        if m:
            num_part = m.group(1)
            if query_token.isdigit():
                if include_letters:
                    # Allow either exact match OR startswith followed by letters
                    return token == query_token or (
                        token.startswith(query_token) and token[len(query_token):].isalpha()
                    )
                else:
                    return query_token == num_part
            else:
                return query_token == token
        return query_token == token
    else:
        return query_token == token


def match_transliteration(query: str, transliteration: str, include_letters: bool = False) -> bool:
    """
    Returns True if the query matches a contiguous subsequence of tokens
    in the transliteration.
    """
    query_tokens = query.split('.')
    translit_tokens = transliteration.split('.')

    for start in range(len(translit_tokens) - len(query_tokens) + 1):
        if all(token_match(query_tokens[i], translit_tokens[start + i], include_letters)
               for i in range(len(query_tokens))):
            return True
    return False



class TransliterationSearchFrame(tk.Frame):
    def __init__(self, parent, glyphEditorWindow, transliterations_file="corpus_transliterations.json", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.glyphEditorWindow = glyphEditorWindow
        self.transliterations_file = transliterations_file
        self.corpus_transliterations = self.load_transliterations()

        # --- Search Parameters Panel ---
        self.params_frame = tk.Frame(self)
        self.params_frame.pack(fill=tk.X, padx=5, pady=5)

        # Search Entry
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.params_frame, textvariable=self.search_var, font=("Helvetica", 12))
        self.search_entry.pack(fill=tk.X, padx=5, pady=2)

        # --- Button Row Frame ---
        self.button_frame = tk.Frame(self.params_frame)
        self.button_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Search Button
        self.search_button = tk.Button(self.button_frame, text="Search", command=self.on_search)
        self.search_button.pack(side=tk.LEFT, padx=5)
        
        # Add Glyphs to Frame Button
        self.add_glyphs_button = tk.Button(self.button_frame, text="Add Glyphs to Frame", command=self.on_add_glyphs)
        self.add_glyphs_button.pack(side=tk.LEFT, padx=5)


        # Exact Match Checkbox
        # Horizontal Frame for checkboxes, slider, and results label
        self.controls_frame = tk.Frame(self.params_frame)
        self.controls_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Exact Match Checkbox
        self.exact_match_var = tk.BooleanVar(value=False)
        self.exact_match_checkbox = tk.Checkbutton(
            self.controls_frame,
            text="Exact match",
            variable=self.exact_match_var
        )
        self.exact_match_checkbox.pack(side=tk.LEFT, padx=5)
        
        # Include Letters Checkbox
        self.include_letters_var = tk.BooleanVar(value=True)
        self.include_letters_checkbox = tk.Checkbutton(
            self.controls_frame,
            text="Exact letters",
            variable=self.include_letters_var
        )
        self.include_letters_checkbox.pack(side=tk.LEFT, padx=5)

        self.search_labels_var = tk.BooleanVar(value=True)
        self.search_labels_checkbox = tk.Checkbutton(
            self.controls_frame,
            text="Search labels",
            variable=self.search_labels_var
        )
        self.search_labels_checkbox.pack(side=tk.LEFT, padx=5)
        
        # Glyph Size Slider
        self.image_size_var = tk.IntVar(value=80)
        self.size_slider = tk.Scale(
            self.controls_frame,
            from_=40,
            to=150,
            orient=tk.HORIZONTAL,
            variable=self.image_size_var,
            label="Glyph Size"
        )
        self.size_slider.pack(side=tk.LEFT, padx=10)
        
        # Search Result Counter Label
        self.result_counter_label = tk.Label(self.controls_frame, text="No results", font=("Helvetica", 10))
        self.result_counter_label.pack(side=tk.LEFT, padx=10)


        # --- Scrollable Canvas Setup ---
        self.canvas = tk.Canvas(self)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)



        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Mouse wheel binding
        #self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # Pre-compute distinct transliterations and frequency counts
        self.update_distinct_transliterations()

    def on_add_glyphs(self):
        
        from GlyphEditorWindow import glyphBox
        
        print("🌀 'Add Glyphs to Frame' button clicked.")
    
        if not hasattr(self, 'glyphEditorWindow') or not self.glyphEditorWindow:
            print("⚠️ glyphEditorWindow not found or not set.")
            return
    
        if not hasattr(self, 'search_results') or not self.search_results:
            print("⚠️ No search results to add.")
            return
    
        # Add each glyph to the editor using the same method as in addGlyphsInLine
        editor = self.glyphEditorWindow
        from PIL import Image
        import os
    
        # Determine vertical offset
        padding = 30
        max_width = 5000
        current_x = 0
        max_y = 0
    
        for box in editor.boxes:
            if box:
                new_y = box.y + box.getHeight() + padding
                max_y = max(max_y, new_y)
        current_y = max_y
    
        for glyph_candidate in self.search_results:
            if not hasattr(glyph_candidate, "filepath"):
                print(f"⚠️ Glyph candidate missing filepath: {glyph_candidate}")
                continue
    
            im_file = glyph_candidate.filepath
            if not os.path.exists(im_file):
                print(f"⚠️ File not found: {im_file}")
                continue
    
            try:
                im = Image.open(im_file)
                new_glyph_box = glyphBox(editor, image=im, x=current_x, y=current_y, glyph=glyph_candidate)
                new_glyph_box.imagefile = im_file
                new_glyph_box.boxIndex = editor.get_unique_boxIndex()
                editor.boxes.append(new_glyph_box)
    
                # Update position
                current_x += im.width + 20
                if current_x > max_width:
                    current_x = 0
                    current_y += 200
    
            except Exception as e:
                print(f"⚠️ Failed to add glyph {glyph_candidate} from {im_file}: {e}")



    def load_transliterations(self):
        """Load transliterations from JSON."""
        if os.path.exists(self.transliterations_file):
            try:
                with open(self.transliterations_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"✅ Loaded {len(data)} transliterations.")
                return data
            except Exception as e:
                print(f"❌ Failed to load transliterations: {e}")
        return {}

    def update_distinct_transliterations(self):
        """Collect unique non-empty transliterations and count their frequency."""
        self.distinct_transliterations = set()
        self.translit_freq = {}
        for data in self.corpus_transliterations.values():
            translit = data.get("transliteration", "").strip()
            if translit:
                self.distinct_transliterations.add(translit)
                self.translit_freq[translit] = self.translit_freq.get(translit, 0) + 1
        self.distinct_transliterations = list(self.distinct_transliterations)

    def on_mousewheel(self, event):
        """Enable scrolling with the mouse wheel."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_search(self, *args):

        """Triggered when the Search button is clicked."""

        # Reload from disk in case JSON changed
        self.corpus_transliterations = self.load_transliterations()
        self.update_distinct_transliterations()

        exact_match = self.exact_match_var.get()
        include_letters = self.include_letters_var.get()
        search_labels = self.search_labels_var.get()

        query = self.search_var.get().strip()
        # Clear previous results in the UI
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not query:
            self.result_counter_label.config(text="No results")
            self.search_results = []
            return

        # ---------------------------------------------
        # 1️⃣ Build transliteration-based matches
        #    Key: transliteration -> best sort key
        # ---------------------------------------------
        matches_dict = {}  # translit -> (sort_key tuple)

        for transliteration in self.distinct_transliterations:
            transliteration = transliteration.strip()
            if not transliteration:
                continue

            if exact_match:
                if query == transliteration:
                    freq = self.translit_freq.get(transliteration, 0)
                    sort_key = (-freq, len(transliteration), -1, 0)
                else:
                    continue
            else:
                if not match_transliteration(query, transliteration, include_letters=include_letters):
                    continue
                starts_with = transliteration.startswith(query)
                index_of_query = transliteration.find(query)
                freq = self.translit_freq.get(transliteration, 0)
                sort_key = (-freq, len(transliteration), -int(starts_with), index_of_query)

            if transliteration not in matches_dict or sort_key < matches_dict[transliteration]:
                matches_dict[transliteration] = sort_key

        # ---------------------------------------------
        # 2️⃣ Label-based search: adds MORE transliterations
        #    and records which addresses matched labels
        # ---------------------------------------------
        label_matched_addresses = set()

        if search_labels:
            q_lower = query.lower()

            for address, data in self.corpus_transliterations.items():
                translit = (data.get("transliteration") or "").strip()
                if not translit:
                    continue

                # Get labels_str or fallback to joined labels list
                labels_str = (data.get("labels_str") or "").strip()
                if not labels_str:
                    labels = data.get("labels", [])
                    labels_str = ".".join(labels).strip()

                if not labels_str:
                    continue

                ls = labels_str.lower()

                if exact_match:
                    if q_lower != ls:
                        continue
                    starts_with = False
                    index_of_query = -1
                else:
                    if q_lower not in ls:
                        continue
                    starts_with = ls.startswith(q_lower)
                    index_of_query = ls.find(q_lower)

                # Record this address as a label match
                label_matched_addresses.add(address)

                # Add/update transliteration entry in matches_dict
                freq = self.translit_freq.get(translit, 0)
                sort_key = (-freq, len(translit), -int(starts_with), index_of_query)
                if translit not in matches_dict or sort_key < matches_dict[translit]:
                    matches_dict[translit] = sort_key

        # ---------------------------------------------
        # 3️⃣ Turn dict into sorted match list
        # ---------------------------------------------
        matches = [
            sort_key + (translit,)
            for translit, sort_key in matches_dict.items()
        ]
        matches.sort()

        # ---------------------------------------------
        # 4️⃣ Build rows: (transliteration, glyph_list)
        #    Apply label filtering to glyph_list if needed
        # ---------------------------------------------
        self.search_results = []
        rows = []

        for *_, transliteration in matches:
            glyphs = self.find_glyphs_for_transliteration(transliteration)

            if search_labels:
                glyphs = [g for g in glyphs if g.address in label_matched_addresses]

            # Skip transliterations that end up with no glyphs
            if not glyphs:
                continue

            rows.append((transliteration, glyphs))
            self.search_results.extend(glyphs)

        # Update the result counter label with total transliteration rows
        total_rows = len(rows)
        if total_rows == 0:
            self.result_counter_label.config(text="No results")
        else:
            self.result_counter_label.config(text=f"Showing {total_rows} transliteration groups")

        # ---------------------------------------------
        # 5️⃣ Display rows
        # ---------------------------------------------
        for transliteration, glyphs in rows:
            self.display_transliteration_row(transliteration, glyphs)


    def display_transliteration_row(self, transliteration, glyphs=None):
        """
        Display one transliteration row with glyph images flowing until they hit
        the edge of the row's width.

        If `glyphs` is provided, it should be a list of Glyph objects to display.
        Otherwise, all glyphs for that transliteration are used.
        """
        # Create a frame for the transliteration row.
        row_frame = tk.Frame(self.scrollable_frame, highlightbackground="gray", highlightthickness=1)
        row_frame.pack(fill=tk.X, padx=5, pady=5)

        # Bind click event to print and update search box.
        row_frame.bind("<Button-1>", lambda event, t=transliteration: self.on_row_click(t))

        # Decide which glyph list to use
        if glyphs is None:
            images = self.find_glyphs_for_transliteration(transliteration)
        else:
            images = glyphs

        # Label for the transliteration text.
        label = tk.Label(
            row_frame,
            text=f"{transliteration} ({len(images)} matches)",
            font=("Helvetica", 12, "bold")
        )
        label.pack(side=tk.TOP, anchor="w", padx=5)
        label.bind("<Button-1>", lambda event, t=transliteration: self.on_row_click(t))

        # Create a sub-frame to hold the glyph images.
        images_frame = tk.Frame(row_frame, bg='white')
        images_frame.pack(fill=tk.X, padx=5, pady=5)

        # Force update to ensure row_frame geometry is computed.
        self.canvas.update_idletasks()

        available_width = self.canvas.winfo_width() * 0.6
        print(f"available_width {available_width}")

        current_row = 0
        current_col = 0
        current_width = 0
        horizontal_padding = 10  # Combined extra spacing between glyphs

        for glyph in images:
            img = glyph.load_image()
            if img:
                # Resize image using the slider's value.
                max_size = self.image_size_var.get()
                resized_img = self.resize_image_with_aspect_ratio(img, max_size)
                img_tk = ImageTk.PhotoImage(resized_img)
                glyph_width = resized_img.width

                # Check if adding this glyph would exceed the available width.
                if current_width + glyph_width + horizontal_padding > available_width and current_col > 0:
                    current_row += 1
                    current_col = 0
                    current_width = 0

                image_label = tk.Label(images_frame, image=img_tk, bg='white')
                image_label.image = img_tk  # Keep a reference.
                image_label.grid(row=current_row, column=current_col, padx=5, pady=5)
                image_label.bind("<Button-1>", lambda event, t=transliteration: self.on_row_click(t))

                current_width += glyph_width + horizontal_padding
                current_col += 1



    def on_row_click(self, transliteration):
        """Print the selected transliteration, update the search box, and reset scroll position."""
        print(f"Selected Transliteration: {transliteration}")
        self.search_var.set(transliteration)
        self.on_search()
        self.canvas.yview_moveto(0)

    def find_glyphs_for_transliteration(self, transliteration):
        """Find all glyphs matching the transliteration."""
        glyphs = []
        for address, data in self.corpus_transliterations.items():
            if data.get("transliteration", "").strip() == transliteration:
                glyph = Glyph(address)
                glyphs.append(glyph)
        return glyphs

    def resize_image_with_aspect_ratio(self, img, max_size):
        """Resize an image while maintaining aspect ratio."""
        w, h = img.size
        aspect = w / h
        if aspect > 1:
            new_w = max_size
            new_h = int(max_size / aspect)
        else:
            new_h = max_size
            new_w = int(max_size * aspect)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
