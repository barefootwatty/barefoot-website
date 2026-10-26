# Article pipeline (not part of the website)

Everything the weekly article job needs to run without Glenn's Mac: the build
scripts, the lesson list (articles/manifest.json), the verified place-name list and
the article sources. `.vercelignore` keeps this folder off the live site.

The scripts expect the layout `ROOT/{tools,articles,site}`. In a fresh checkout:

    mkdir -p /tmp/work && cp -r pipeline/tools pipeline/articles /tmp/work/
    ln -s "$PWD" /tmp/work/site
    cd /tmp/work && python3 tools/check_places.py && python3 tools/build_article.py articles/src/<slug>.txt

Then copy any new `articles/src/*.txt` and `articles/placenames.txt` back into
`pipeline/articles/` before committing.
