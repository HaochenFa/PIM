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
HINTS = (
    "↑↓ select  / search  c create  m modify  p print  x delete  "
    "d dismiss  : command  ? help  q quit"
)
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
    prompt: str


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
    if selected is not None:
        detail = tuple(selected.detail_lines())
    return Screen(
        title=title,
        bound=bound,
        dirty=dirty,
        alarms=alarms,
        filter_label="search" if has_criterion else "all",
        rows=tuple(rows),
        selected_id=selected_id,
        detail=detail,
        print_text=print_text or "",
        status=status or "",
        prompt=prompt,
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


def compute_geometry(height: int, width: int) -> Geometry:
    """Split a terminal into title, alarm, list, detail, status, hints, prompt.

    Side-by-side master–detail at ``WIDE_WIDTH`` or more; stacked list above
    detail when narrower. Below ``MIN_HEIGHT`` × ``MIN_WIDTH`` the layout is
    flagged ``too_small``.
    """
    too_small = height < MIN_HEIGHT or width < MIN_WIDTH
    stacked = width < WIDE_WIDTH
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
            status_y=max(0, height - 3),
            hints_y=max(0, height - 2),
            prompt_y=max(0, height - 1),
        )
    title_y = 0
    alarm_y = 1
    status_y = height - 3
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
    """One Current Result row clipped to ``width`` columns."""
    mark = ">" if row.selected else " "
    time_text = row.time_short if short_time_col else row.time_text
    # 2+4+1+4+1+8+1 = 21 before the name; leave 16+ for time when possible.
    name_w = max(8, min(NAME_WIDTH, width - 38))
    name = pad(clip(row.display_name, name_w), name_w)
    line = (
        f"{mark} {row.index:3d}  {row.pir_id:3d}  {row.type_name:<8}  {name}  {time_text}"
    )
    return clip(line, width)
