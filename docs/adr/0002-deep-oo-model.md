# Make `model` a deep OO module

The assignment requires a separate `model` package as the unit-test surface, and grades design on modularity and extendibility. We will put a small `PIM` interface in front of a PIR type hierarchy and a composite Search Criterion tree, rather than a procedural function set or a single service class over dataclasses.

Callers (controller and tests) should need `create` / `modify` / `delete` / `search` / `save` / `load` and the criterion constructors — not the internals of matching or persistence. Persistence stays inside the module and is tested with temporary files; a one-implementation `Storage` port would be a fake seam.

**Status**: accepted
