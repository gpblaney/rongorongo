from django.contrib import admin
from django.urls import path
from viewer.views import (
    board_view,
    corpus_glyph_png,
    glyphs_by_address_api,
    glyph_meta_update,
    glyph_search_api,
    sign_catalog_view,
    sort_layout_api,
    step_glyph_api,
    tablet_load_api,
    transliteration_sign_examples_api,
    transliteration_sign_replace_api,
    transliteration_sign_stats_api,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', board_view, name='board'),
    path('sign-catalog/', sign_catalog_view, name='sign_catalog'),
    path('api/glyph-meta/update', glyph_meta_update, name='glyph_meta_update'),
    path('api/glyph-search', glyph_search_api, name='glyph_search'),
    path('api/transliteration-signs/stats', transliteration_sign_stats_api, name='transliteration_sign_stats'),
    path('api/transliteration-signs/examples', transliteration_sign_examples_api, name='transliteration_sign_examples'),
    path('api/transliteration-signs/replace', transliteration_sign_replace_api, name='transliteration_sign_replace'),
    path('api/glyphs-by-address', glyphs_by_address_api, name='glyphs_by_address'),
    path('api/tablet-load', tablet_load_api, name='tablet_load'),
    path('api/sort-layout', sort_layout_api, name='sort_layout'),
    path('api/step-glyph', step_glyph_api, name='step_glyph'),
    path('api/corpus-glyph/<str:address>', corpus_glyph_png, name='corpus_glyph'),
]
