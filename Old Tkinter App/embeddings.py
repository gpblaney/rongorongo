import numpy as np
import os
from scipy.cluster.hierarchy import linkage, dendrogram

# Define the embedding directory
EMBEDDING_DIR = r"RRC-64%-embeddings"

def load_embedding_for_glyph(glyph_address):
    """
    Attempts to load the embedding for a given glyph address.
    Expected file structure: EMBEDDING_DIR / first_letter / <glyph_address>_results.npz
    """
    if not glyph_address or len(glyph_address) < 3:
        print(f"❌ Invalid glyph address: {glyph_address}")
        return None
    
    subfolder = glyph_address[0]  # First letter as subdirectory
    file_path = os.path.join(EMBEDDING_DIR, subfolder, f"{glyph_address}_results.npz")
    
    if not os.path.exists(file_path):
        print(f"⚠️ No embedding file found for {glyph_address} at {file_path}")
        return None
    
    try:
        data = np.load(file_path)
        if 'embedding' in data:
            return data['embedding'].flatten()  # Ensure it's a 1D array
        else:
            print(f"⚠️ No 'embedding' key found in {file_path}")
            return None
    except Exception as e:
        print(f"❌ Error loading embedding for {glyph_address}: {e}")
        return None

def dendrogram_order_for_visual_embeddings(glyphs):
    """
    Computes a hierarchical clustering order for glyphs using visual embeddings
    fetched dynamically from files.
    """
    print("🔍 Generating dendrogram order based on visual embeddings...")

    embedding_list = []
    valid_glyphs = []
    
    for glyph_box in glyphs:
        glyph_address = getattr(glyph_box.glyph, 'address', None)
        embedding = load_embedding_for_glyph(glyph_address)
        
        if embedding is not None:
            embedding_list.append(embedding)
            valid_glyphs.append(glyph_box)
        else:
            print(f"❌ Skipping glyph {glyph_address} (no valid embedding)")
    
    if len(embedding_list) == 0:
        print("⚠️ No valid embeddings found. Returning original order.")
        return glyphs  # No sorting can be performed
    
    embedding_matrix = np.array(embedding_list)

    print("📊 Computing hierarchical clustering linkage...")
    Z = linkage(embedding_matrix, method='ward')

    print("🌳 Extracting dendrogram order...")
    dendro = dendrogram(Z, no_plot=True)
    order = dendro['leaves']
    print(f"✅ Dendrogram order computed: {order}")

    # Reorder valid glyphs based on dendrogram
    sorted_valid = [valid_glyphs[i] for i in order]

    # Append glyphs without embeddings at the end
    missing = [glyph for glyph in glyphs if glyph not in valid_glyphs]
    final_order = sorted_valid + missing
    print(f"✅ Final reordered glyph count: {len(final_order)}")
    
    return final_order
