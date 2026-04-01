import os
from PIL import Image
import re
from natsort import natsorted

root = r"RRC-64%"

class Glyph:
    def __init__(self, address):
        """
        Parameters:
            address (str): The glyph address (e.g., "Gr1-002")
            tablet (str): The name of the tablet (i.e., folder name)
            filepath (str): Full path to the image file
        """
        self.address = address
        match = re.search(r'[arbv]', address)
        substring = address[:match.start()] if match else address  # Get substring up to 'a' or 'r'
        self.filepath = os.path.join(root, substring, f'{address}.png')
        self._image = None  # Lazy-loaded image
        self.text = ""
        self.tablet = address[0]
        self.subGlyphs = []

    def load_image(self):
        """Load and return the glyph image using PIL."""
        if self._image is None:
            try:
                self._image = Image.open(self.filepath)
            except Exception as e:
                print(f"Error loading image for {self.address} from {self.filepath}: {e}")
        return self._image

    def show(self):
        """Display the glyph image."""
        img = self.load_image()
        if img:
            img.show()

    def __repr__(self):
        return f"Glyph(address='{self.address}', tablet='{self.tablet}')"


class Tablet:
    def __init__(self, folder, root):
        """
        Parameters:
            folder (str): The folder name representing the tablet.
            root (str): The path to the root directory containing all tablet folders.
        """
        self.name = folder
        self.root = root
        self.glyphs = []

    def load(self):
        """Load all PNG glyph files from the tablet folder."""
        folder_path = os.path.join(self.root, self.name)
        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist.")
            return

        for filename in natsorted(os.listdir(folder_path)):
            if filename.lower().endswith('.png'):
                # Derive the glyph address from the filename (without the extension)
                address = os.path.splitext(filename)[0]
                glyph = Glyph(address)
                self.glyphs.append(glyph)

    def __repr__(self):
        return f"Tablet(name='{self.name}', glyph_count={len(self.glyphs)})"


class Corpus:
    def __init__(self):
        """
        Parameters:
            root (str): The path to the root directory containing the tablet folders.
        """
        self.root = root
        self.tablets = []
        self.glyph_index = {}  # Allows fast lookup of glyphs by address

    def load(self):
        """Traverse the root directory, load each tablet folder, and index glyphs by address."""
        for folder in os.listdir(self.root):
            folder_path = os.path.join(self.root, folder)
            if os.path.isdir(folder_path):
                tablet = Tablet(folder, self.root)
                tablet.load()
                self.tablets.append(tablet)
                # Index glyphs by their address for quick lookup
                for glyph in tablet.glyphs:
                    self.glyph_index[glyph.address] = glyph

    def get_glyph(self, address):
        """Return the Glyph object with the given address, or None if not found."""
        return self.glyph_index.get(address)

    def get_tablet(self, tablet_name):
        """Return the Tablet object with the given name, or None if not found."""
        for tablet in self.tablets:
            if tablet.name == tablet_name:
                return tablet
        return None

    def __repr__(self):
        return f"Corpus(tablet_count={len(self.tablets)})"

corpus = Corpus()
corpus.load()