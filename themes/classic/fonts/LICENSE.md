# Bundled fonts

**Source Sans 3**, latin subset, variable weight (400–700) plus a variable italic.
Fetched from the Google Fonts CDN (`fonts.gstatic.com`, family version v19).

Licensed under the **SIL Open Font License 1.1** — https://openfontlicense.org/

The OFL permits bundling and redistribution, including embedding in a PDF. Copyright 2010-2023
Adobe (https://adobe.com/), with Reserved Font Name 'Source'.

These are vendored rather than linked so that the PDF built on Windows and the PDF built on Linux CI
are byte-comparable: relying on system fonts means different metrics, and therefore different
pagination, on each machine.
