# MVC as three top-level packages, model named `model`

The assignment requires the system model in a package named `model`, other major parts identifiable, and grades design on modularity. Python stdlib MVC for this CLI is three sibling packages plus a thin entry script:

- `model/` — Working Collection, PIR types, Search Criterion, PIM File JSON. The test surface.
- `view/` — terminal layout, event loop, Alarm Alerts. Knows stdin and ANSI. Does not know JSON schema.
- `controller/` — parses one user action into `model` calls and asks `view` to render.
- `pim.py` — instantiates PIM, View, Controller and starts the loop.

`pim.model` as a nested name would fail the literal package name `model`. Flattening View/Controller into `pim.py` would fail “easily identifiable” and let the event loop leak into the model. Splitting `model` into many micro-packages would shallow the interface.

**Status**: accepted
