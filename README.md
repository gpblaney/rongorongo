# Glyph Board Test (Django + Konva)

This is a very small test app that does exactly this:

- loads images from a folder
- places them at random positions on an infinite-feeling canvas
- lets you pan by dragging the background
- lets you zoom with the mouse wheel
- lets you drag individual images around

## Quick start

1. Install Django:

```bash
pip install django
```

2. Go into the project folder:

```bash
cd glyphboard_test
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Start the server:

```bash
python manage.py runserver
```

5. Open:

```text
http://127.0.0.1:8000/
```

## Where to put your images

Put your images here:

```text
viewer/static/viewer/images/
```

You can delete the sample images and replace them with your own.

Supported image types in this test:

- png
- jpg
- jpeg
- gif
- webp
- svg

## Why this is a good refactor direction

Your Python code can stay in Django views, helper modules, or APIs, while Konva handles the canvas interaction in the browser.

So the split is:

- Django/Python = logic
- Konva.js = visual editor surface

## Notes

This test uses Konva from the official CDN with:

```html
<script src="https://unpkg.com/konva@10/konva.min.js"></script>
```

If you later want, the next logical step is:

- save moved positions back to Django
- load coordinates from JSON/database instead of random placement
- add selection boxes
- add linking lines between glyphs
- add clustering/layout buttons powered by your old Python code
