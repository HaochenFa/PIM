-- Pipe tables need `\|` to write `|` inside a cell. Pandoc keeps the
-- backslash in code spans, so `str \| None` would print literally.
function Code(el)
  el.text = el.text:gsub("\\|", "|")
  return el
end
