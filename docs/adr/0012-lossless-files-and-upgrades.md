# 0012. Lossless Seamly2D files, and upgrades checked against Seamly2D

Status: accepted

**What "lossless" means.** Reading a Seamly2D file and writing it back gives the same bytes, when the file was written by Seamly2D's own saver (`QXmlStreamWriter`, attributes sorted by name, 4-space indent). Nothing we do not interpret is dropped: unknown elements, comments, text, attributes, the order of top-level sections, the line endings (Windows files keep CRLF) and the XML declaration all ride along (`RawNode`, `Pattern.layout`, `RawDocument`). Files written by older savers (unsorted attributes, a single-quoted declaration, a raw `>` in an attribute) are lossless in content, not in bytes, unless written with `canonical=False`, which keeps the attribute order.

**The writer is Qt's, copied.** `yoko_io.xmlwrite` reproduces `QXmlStreamWriter` auto-formatting, including its odd cases (text then element, element then text, comments inside text). Those cases were checked against the real Qt 6.4 writer; the common ones (every element of 24 real patterns, one of them 6 MB) are checked by comparing with what the pinned Seamly2D saves.

**Write the version you read.** `write_pattern` keeps the format version. `<increments>` is only written for formats before 0.6.9.

**Upgrades.** `upgrade_pattern` (0.6.8 to 0.7.5) and `upgrade_measurements` (multisize 0.4.4 to 0.4.5, individual 0.3.3 to 0.3.4) port the steps of Seamly2D's converters (`vpatternconverter.cpp`, `multi_size_converter.cpp`, `individual_size_converter.cpp`). From 0.6.8 to 0.7.5 the only content change is `increments` to `variables`; on save Seamly2D also rewrites the leading comment with its own version. We port only the steps a file in our range needs. Older files (patterns before 0.6.8, multisize before 0.4.4, individual before 0.3.3) are not read or upgraded here: open them in Seamly2D once, or use the upgraded copies in `fixtures/external/seamly2d/upgraded/`.

**How it is verified.** The oracle patch (`docker/oracle/yoko-oracle-dump.patch`) has two more hooks: `YOKO_ORACLE_SAVE=<file>` saves the loaded pattern with Seamly2D's own saver, and `YOKO_ORACLE_CONVERTED_DIR=<dir>` keeps what the converters produced. Tests compare our upgrade with both, byte for byte for patterns and structurally for measurement files (the converter writes with `QDomDocument::save`, which orders attributes differently). The CI oracle job regenerates all of it with Qt 6.11.1 and fails on any difference.

**Limits.** On save Seamly2D only updates a leading comment that already exists (`VPattern::SaveDocument`); so does `upgrade_pattern`. The reader refuses comments inside `<calculation>` and `<variables>`, and attributes on `<calculation>`, instead of dropping them silently. Text before the root element is not kept.
