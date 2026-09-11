# Store a PIM File as UTF-8 JSON

The assignment only requires the `.pim` extension. It does not require a custom format. JSON (Python stdlib `json`) is inspectable, schema-documentable, and testable. YAML needs a third-party parser or a hand-rolled subset, which collides with the standard-library-only rule. `pickle` is stdlib but opaque, version-fragile, and a poor fit for verifiable requirements. A custom text format is extra parser work with no extra marks.

The file remains a `.pim` file. JSON is the representation inside it, not a different product feature.

**Status**: accepted
