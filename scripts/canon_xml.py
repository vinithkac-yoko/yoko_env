"""Rewrite XML files in place as canonical XML (C14N): attributes sorted, no declaration.

Seamly2D's converters save measurement files with `QDomDocument::save`, whose attribute order and
declaration depend on the Qt version. The oracle scripts store those copies in canonical form so that
what is committed does not change with the Qt version used to produce it.

    python3 scripts/canon_xml.py file...
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

for name in sys.argv[1:]:
    p = Path(name)
    p.write_text(ET.canonicalize(xml_data=p.read_text(encoding="utf-8"), with_comments=True) + "\n")
