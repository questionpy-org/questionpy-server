
# Static Site Generators

## Sphinx

>   Ich hatte Probleme sphinx über poetry zu installieren: poetry konnte nicht die
    dependencies resolven (nach >1200s).
    Daher habe ich es bis jetzt mit pip installiert:
```
pip install sphinx
pip install markdown
```

```
cd docs/sphinx
```

### Generate source files from code:

shpinx-apidoc kann aus dem `questionpy_server` package, markdup dateien in RST
generieren, die dann im source folder gespeichert werden.
Um diese RST Dateien automatisch zu generieren, benutzt man:

```
sphinx-apidoc -o source/ ../../questionpy_server
```

Die RST Dateien kann man bearbeiten. Aus diesen Dateien generiert sphinx
dann im nächsten Schritt den build.

### Generate html from source files:
The options for this command are in the Makefile
```
make html 
```

### Theme

Für einen besseren Vergleich zu mkdocs, kann man das `material` theme installieren:
```
pip install sphinx-material
```
Dann noch in source/conf.py die Änderung vornehmen:
```
html_theme = 'sphinx_material'
```
## mkdocs

```
cd docs/mkdocs
```

### Serve development server on local machine

```
mkdocs serve -f docs/mkdocs/mkdocs.yml
```

### Generate 

```
mkdocs build -f docs/mkdocs/mkdocs.yml
```

## Hinweis:

mkdocs und sphinx verlangen verschieden Versionen von `markdown`