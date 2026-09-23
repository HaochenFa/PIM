"""Shared screen model for the text fallback and the curses TTY UI.

Callers pass Working Collection state in; this module does not import
``controller`` or ``curses``. Text clipping uses display columns so CJK
Display Names do not break the Current Result table.
"""

from __future__ import annotations

from dataclasses import dataclass

from model.pir import format_datetime
from view.textwidth import clip, display_width, pad

MENU = (
    "create  search  clear  modify  print  print all  delete  "
    "save  save as  load  dismiss  help  quit"
)
# `d dismiss` is shown on the alarm banner itself, so the idle footer keeps
# room for the file keys.
HINTS = (
    "↑↓ move  / search  c create  m modify  p print  x delete  "
    "w save  o load  ? keys  q quit"
)
HINTS_FILTERED = HINTS + "  Esc clear"
EMPTY_INVITE = "No PIRs — press c, then pick a type"
SEARCH_EXAMPLE = 'type = event && description contains "COMP"'
SEARCH_HINT = 'type = note  ·  description contains "…"  ·  deadline < …  ·  && || !'
TYPE_PIN = {"note": "N", "task": "T", "event": "E", "contact": "C"}
NAME_WIDTH = 24
MIN_HEIGHT = 12
MIN_WIDTH = 60
WIDE_WIDTH = 80
DIVIDER_WIDTH = 76


@dataclass(frozen=True)
class AlarmRow:
    """One visible Alarm Alert for the banner."""

    status: str
    event_id: int
    description: str
    when: str


@dataclass(frozen=True)
class ResultRow:
    """One Current Result line. ``index`` is 1-based and is not identity."""

    index: int
    pir_id: int
    type_name: str
    display_name: str
    time_text: str
    time_short: str
    selected: bool


@dataclass(frozen=True)
class Screen:
    """Everything the View needs to paint, independent of the I/O backend."""

    title: str
    bound: str
    dirty: bool
    alarms: tuple[AlarmRow, ...]
    filter_label: str
    rows: tuple[ResultRow, ...]
    selected_id: int | None
    detail: tuple[tuple[str, str], ...]
    print_text: str
    status: str
    status_kind: str
    prompt: str
    criterion_line: str | None
    detail_heading: str
    detail_kind: str


@dataclass(frozen=True)
class Geometry:
    """Pane positions on a ``height`` × ``width`` terminal.

    Coordinates are 0-based rows/columns on stdscr. ``too_small`` means the
    UI should show a widen-the-terminal message instead of panes.
    """

    height: int
    width: int
    stacked: bool
    too_small: bool
    title_y: int
    alarm_y: int
    list_header_y: int
    list_y: int
    list_h: int
    list_x: int
    list_w: int
    detail_header_y: int
    detail_y: int
    detail_h: int
    detail_x: int
    detail_w: int
    status_y: int
    hints_y: int
    prompt_y: int
    composer_y: int
    composer_h: int


def short_time(dt) -> str:
    """Compact HKT clock face for the TUI Time column; empty if ``dt`` is None."""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def build_screen(
    *,
    bound_path,
    dirty: bool,
    due,
    result,
    selected_id,
    selected,
    has_criterion: bool,
    print_text: str,
    status: str,
    prompt: str,
    status_kind: str = "info",
    criterion_line: str | None = None,
) -> Screen:
    """Assemble a ``Screen`` from App-visible state and the current prompt."""
    bound = bound_path or "untitled"
    mark = "*" if dirty else ""
    title = f"PIM  {bound}{mark}"
    alarms = tuple(
        AlarmRow(
            status=item.status,
            event_id=item.event_id,
            description=item.description,
            when=format_datetime(item.at),
        )
        for item in due
    )
    rows = []
    for index, pir in enumerate(result, 1):
        instant = pir.relevant_time()
        rows.append(
            ResultRow(
                index=index,
                pir_id=pir.id,
                type_name=pir.type_name,
                display_name=pir.display_name,
                time_text=format_datetime(instant) if instant else "",
                time_short=short_time(instant),
                selected=pir.id == selected_id,
            )
        )
    detail: tuple[tuple[str, str], ...] = ()
    heading = ""
    kind = ""
    if selected is not None:
        detail = tuple(selected.detail_lines())
        heading = selected.display_name
        kind = selected.type_name
    if criterion_line:
        filter_label = criterion_line.strip()
    elif has_criterion:
        filter_label = "search"
    else:
        filter_label = "all"
    return Screen(
        title=title,
        bound=bound,
        dirty=dirty,
        alarms=alarms,
        filter_label=filter_label,
        rows=tuple(rows),
        selected_id=selected_id,
        detail=detail,
        print_text=print_text or "",
        status=status or "",
        status_kind=status_kind or "info",
        prompt=prompt,
        criterion_line=criterion_line,
        detail_heading=heading,
        detail_kind=kind,
    )


def text_lines(screen: Screen) -> list[str]:
    """Linear fallback layout used when stdin/stdout is not a TTY."""
    alarm_lines = ["ALARMS"]
    if screen.alarms:
        for item in screen.alarms:
            alarm_lines.append(
                f"  {item.status:<7}  Id {item.event_id}  {item.description}  {item.when}"
            )
        alarm_lines.append("  (dismiss)")
    else:
        alarm_lines.append("  (none)")
    rows = [
        f"Current Result ({screen.filter_label})",
        "    #   Id  Type      Name                      Time",
    ]
    if not screen.rows:
        rows.append("    (empty)")
    for row in screen.rows:
        mark = ">" if row.selected else " "
        name = clip(row.display_name, NAME_WIDTH)
        padded = name + (" " * max(0, NAME_WIDTH - display_width(name)))
        rows.append(
            f"{mark} {row.index:3d}  {row.pir_id:3d}  {row.type_name:<8}  {padded}  {row.time_text}"
        )
    detail = ["DETAIL"]
    if not screen.detail:
        detail.append("  (no selection)")
    else:
        for key, value in screen.detail:
            detail.append(f"  {key}: {value}")
    if screen.print_text:
        detail.append("PRINT")
        for line in screen.print_text.splitlines():
            detail.append(f"  {line}")
    divider = "-" * DIVIDER_WIDTH
    return [
        screen.title,
        divider,
        *alarm_lines,
        divider,
        *rows,
        divider,
        *detail,
        divider,
        screen.status,
        MENU,
        screen.prompt,
    ]


def compute_geometry(height: int, width: int, composer_h: int = 2) -> Geometry:
    """Split a terminal into titled panes plus a bottom composer.

    Side-by-side master–detail at ``WIDE_WIDTH`` or more; stacked list above
    detail when narrower. ``composer_h`` is the selector / field / hint strip.
    Below ``MIN_HEIGHT`` × ``MIN_WIDTH`` the layout is flagged ``too_small``.
    """
    too_small = height < MIN_HEIGHT or width < MIN_WIDTH
    stacked = width < WIDE_WIDTH
    composer_h = max(2, composer_h)
    composer_y = max(0, height - composer_h)
    if too_small:
        return Geometry(
            height=height,
            width=width,
            stacked=stacked,
            too_small=True,
            title_y=0,
            alarm_y=1,
            list_header_y=0,
            list_y=0,
            list_h=0,
            list_x=0,
            list_w=max(0, width),
            detail_header_y=0,
            detail_y=0,
            detail_h=0,
            detail_x=0,
            detail_w=max(0, width),
            status_y=max(0, composer_y - 1),
            hints_y=max(0, height - 2),
            prompt_y=max(0, height - 1),
            composer_y=composer_y,
            composer_h=composer_h,
        )
    title_y = 0
    alarm_y = 1
    status_y = max(2, composer_y - 1)
    hints_y = height - 2
    prompt_y = height - 1
    body_top = 2
    body_bottom = status_y - 1
    body_h = max(1, body_bottom - body_top + 1)
    if stacked:
        list_block = max(4, body_h // 2)
        list_header_y = body_top
        list_y = body_top + 1
        list_h = max(1, list_block - 1)
        detail_header_y = list_y + list_h
        if detail_header_y >= body_bottom:
            detail_header_y = body_bottom
        detail_y = detail_header_y + 1
        detail_h = max(0, body_bottom - detail_y + 1)
        return Geometry(
            height=height,
            width=width,
            stacked=True,
            too_small=False,
            title_y=title_y,
            alarm_y=alarm_y,
            list_header_y=list_header_y,
            list_y=list_y,
            list_h=list_h,
            list_x=0,
            list_w=width,
            detail_header_y=detail_header_y,
            detail_y=detail_y,
            detail_h=detail_h,
            detail_x=0,
            detail_w=width,
            status_y=status_y,
            hints_y=hints_y,
            prompt_y=prompt_y,
            composer_y=composer_y,
            composer_h=composer_h,
        )
    list_w = max(36, min(52, width * 5 // 8))
    detail_x = list_w + 1
    detail_w = max(1, width - detail_x)
    list_header_y = body_top
    list_y = body_top + 1
    list_h = max(1, body_h - 1)
    return Geometry(
        height=height,
        width=width,
        stacked=False,
        too_small=False,
        title_y=title_y,
        alarm_y=alarm_y,
        list_header_y=list_header_y,
        list_y=list_y,
        list_h=list_h,
        list_x=0,
        list_w=list_w,
        detail_header_y=list_header_y,
        detail_y=list_y,
        detail_h=list_h,
        detail_x=detail_x,
        detail_w=detail_w,
        status_y=status_y,
        hints_y=hints_y,
        prompt_y=prompt_y,
        composer_y=composer_y,
        composer_h=composer_h,
    )


def visible_list_window(row_count: int, selected_index: int | None, height: int) -> int:
    """Return the first visible row index so the selection stays in view."""
    if height <= 0 or row_count <= height:
        return 0
    if selected_index is None:
        return 0
    if selected_index < 0:
        return 0
    max_scroll = row_count - height
    if selected_index < height:
        return 0
    scroll = selected_index - height + 1
    return min(max_scroll, max(0, scroll))


def format_list_row(row: ResultRow, width: int, *, short_time_col: bool) -> str:
    """One Current Result row: pin + name + time gutter, clipped to ``width``."""
    mark = ">" if row.selected else " "
    pin = TYPE_PIN.get(row.type_name, "?")
    time_text = row.time_short if short_time_col else row.time_text
    if not time_text:
        time_text = "·"
    time_w = 16 if short_time_col else 25
    time = pad(clip(time_text, time_w), time_w)
    # mark + index + id + pin + gaps ≈ 16; time gutter on the right.
    name_w = max(8, width - 16 - time_w)
    name = pad(clip(row.display_name, name_w), name_w)
    line = f"{mark}{row.index:3d} {row.pir_id:3d} {pin} {name} {time}"
    return clip(line, width)


def format_list_header(width: int, *, short_time_col: bool) -> str:
    """Column captions matching ``format_list_row``."""
    dummy = ResultRow(0, 0, "note", "Name", "", "", False)
    # Build against the same widths, then replace the data with labels.
    time_w = 16 if short_time_col else 25
    name_w = max(8, width - 16 - time_w)
    name = pad("Name", name_w)
    time = pad("Time", time_w)
    line = f" {'#':>3} {'Id':>3} · {name} {time}"
    return clip(line, width)


def card_fields(detail: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    """Detail rows without Id/type, which the pane title already shows."""
    skip = {"id", "type"}
    return tuple((key, value) for key, value in detail if key.casefold() not in skip)


def list_pane_title(screen: Screen, *, first: int, visible: int) -> str:
    """Current Result title: filter, then visible range when the list scrolls."""
    count = len(screen.rows)
    if count == 0:
        shown = "none"
    elif visible > 0 and visible < count:
        last = min(count, first + visible)
        shown = f"{first + 1}–{last} of {count}"
    else:
        shown = str(count)
    return f"Current Result · {screen.filter_label} · {shown}"


def idle_hints(has_criterion: bool) -> str:
    """Footer when nothing is being asked."""
    return HINTS_FILTERED if has_criterion else HINTS


def picker_weekday_row(box_y: int) -> int:
    """Row of Mo–Su. Time slots must start strictly below this."""
    return box_y + 2


def picker_time_origin(box_y: int) -> int:
    """First clock-face row; kept below the weekday header."""
    return box_y + 3
