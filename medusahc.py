# /// script
# requires-python = ">=3.12"
#
# [tool.orcaslicer.plugin]
# name = "MedusaHC"
# description = "After a tool change, travel in XY before a Z hop. After the first layer, set temperature instead of waiting."
# author = "topi"
# version = "1.0.0"
# ///
"""Post-process exported G-code for MedusaHC.

OrcaSlicer selects this capability from a process preset. The two checkboxes on
that preset choose the tool-change travel swap and the M109 to M104 conversion.
"""

import json
import re

try:
    import orca
except ImportError:  # Unit tests import this module outside OrcaSlicer.
    orca = None

_DEFAULTS = {
    "swap_toolchange_travel": True,
    "convert_m109": True,
}

_TOOL_RE = re.compile(r"^\s*T\d+\s*$", re.IGNORECASE)
_MOVE_RE = re.compile(r"^\s*G[01]\b", re.IGNORECASE)
_G1_RE = re.compile(r"^\s*G1\b", re.IGNORECASE)
_M109_RE = re.compile(r"^\s*M109\b", re.IGNORECASE)
_AXIS_RE = {
    axis: re.compile(rf"(?<![A-Za-z]){axis}\s*[-+]?(?:\d+\.?\d*|\.\d+)", re.IGNORECASE)
    for axis in "XYZE"
}
_F_RE = re.compile(r"(?<![A-Za-z])F\s*([-+]?(?:\d+\.?\d*|\.\d+))", re.IGNORECASE)
_F_WORD_RE = re.compile(r"\s*(?<![A-Za-z])F\s*[-+]?(?:\d+\.?\d*|\.\d+)", re.IGNORECASE)
_M109_WORD_RE = re.compile(r"^\s*M109\b", re.IGNORECASE)
_R_TEMP_RE = re.compile(r"(?<![A-Za-z])R\s*([-+]?(?:\d+\.?\d*|\.\d+))", re.IGNORECASE)

_CONFIG_UI = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: sans-serif; color: CanvasText; background: Canvas; margin: 1rem; }
  label { display: block; margin: 0.75rem 0; }
  button { margin-top: 0.5rem; }
</style>
</head>
<body>
  <label><input id="swap" type="checkbox"> Swap Z and XY travel after a tool change</label>
  <label><input id="convert" type="checkbox"> Convert M109 to M104 after the first layer</label>
  <button id="save" type="button">Save</button>
  <script>
    function readConfig() {
      let config = {};
      try {
        config = window.orca.getConfig() || {};
        if (typeof config === "string") config = JSON.parse(config);
      } catch (e) {
        config = {};
      }
      return config;
    }
    const config = readConfig();
    document.getElementById("swap").checked = config.swap_toolchange_travel !== false;
    document.getElementById("convert").checked = config.convert_m109 !== false;
    document.getElementById("save").onclick = () => {
      window.orca.saveConfig({
        swap_toolchange_travel: document.getElementById("swap").checked,
        convert_m109: document.getElementById("convert").checked
      });
    };
  </script>
</body>
</html>
"""


def _split_line(line):
    ending = ""
    body = line
    if body.endswith("\r\n"):
        ending, body = "\r\n", body[:-2]
    elif body.endswith("\n"):
        ending, body = "\n", body[:-1]
    elif body.endswith("\r"):
        ending, body = "\r", body[:-1]
    if ";" in body:
        code, comment = body.split(";", 1)
        return code, ";" + comment, ending
    return body, "", ending


def _join_line(code, comment, ending):
    code = code.rstrip()
    if comment:
        gap = " " if code else ""
        return f"{code}{gap}{comment.strip()}{ending}"
    return f"{code}{ending}"


def _has_axis(code, axis):
    return _AXIS_RE[axis].search(code) is not None


def _is_e_only(code):
    return (
        _G1_RE.match(code)
        and _has_axis(code, "E")
        and not _has_axis(code, "X")
        and not _has_axis(code, "Y")
        and not _has_axis(code, "Z")
    )


def _is_z_only(code):
    return (
        _MOVE_RE.match(code)
        and _has_axis(code, "Z")
        and not _has_axis(code, "X")
        and not _has_axis(code, "Y")
        and not _has_axis(code, "E")
    )


def _is_xy_only(code):
    return (
        _MOVE_RE.match(code)
        and (_has_axis(code, "X") or _has_axis(code, "Y"))
        and not _has_axis(code, "Z")
        and not _has_axis(code, "E")
    )


def _move_feedrate(z_line, xy_line):
    """Carry F from the Z hop onto the XY travel when the travel has none."""
    z_code, z_comment, z_ending = _split_line(z_line)
    xy_code, xy_comment, xy_ending = _split_line(xy_line)
    feedrate = _F_RE.search(z_code)
    if feedrate is None or _F_RE.search(xy_code):
        return z_line, xy_line
    z_code = _F_WORD_RE.sub("", z_code, count=1)
    xy_code = f"{xy_code.rstrip()} F{feedrate.group(1)}"
    return (
        _join_line(z_code, z_comment, z_ending),
        _join_line(xy_code, xy_comment, xy_ending),
    )


def _convert_temperature(line):
    code, comment, ending = _split_line(line)
    code = _M109_WORD_RE.sub("M104", code, count=1)
    code = _R_TEMP_RE.sub(r"S\1", code, count=1)
    return _join_line(code, comment, ending)


def _flag(config, key):
    value = config.get(key, True)
    return value if isinstance(value, bool) else True


def process(lines, swap_toolchange_travel=True, convert_m109=True):
    """Rewrite ``lines`` in place. Return True when any line changed."""
    changed = False

    if convert_m109:
        layer_index = None
        for index, line in enumerate(lines):
            if line.lstrip().startswith(";LAYER_CHANGE"):
                layer_index = index
                break
        if layer_index is not None:
            for index in range(layer_index + 1, len(lines)):
                code, _, _ = _split_line(lines[index])
                if _M109_RE.match(code.strip()):
                    updated = _convert_temperature(lines[index])
                    if updated != lines[index]:
                        lines[index] = updated
                        changed = True

    if not swap_toolchange_travel:
        return changed

    index = 0
    while index < len(lines):
        code, _, _ = _split_line(lines[index])
        if not _TOOL_RE.match(code.strip()):
            index += 1
            continue

        z_index = None
        xy_index = None
        saw_move = False
        scan = index + 1
        while scan < len(lines):
            command, _, _ = _split_line(lines[scan])
            command = command.strip()
            if _TOOL_RE.match(command):
                break
            if not saw_move and _is_e_only(command):
                scan += 1
                continue
            if not saw_move and _MOVE_RE.match(command):
                saw_move = True
                if _is_z_only(command):
                    z_index = scan
                else:
                    break
                scan += 1
                continue
            if z_index is not None and _is_xy_only(command):
                xy_index = scan
                break
            scan += 1

        if z_index is None or xy_index is None:
            index += 1
            continue

        new_z, new_xy = _move_feedrate(lines[z_index], lines[xy_index])
        if new_z != lines[z_index] or new_xy != lines[xy_index]:
            lines[z_index], lines[xy_index] = new_z, new_xy
            changed = True
        lines[z_index], lines[xy_index] = lines[xy_index], lines[z_index]
        changed = True
        index = xy_index + 1

    return changed


if orca is not None:

    class MedusaHC(orca.slicing.SlicingPipelineCapabilityBase):
        def get_name(self):
            return "MedusaHC"

        def get_default_config(self):
            return dict(_DEFAULTS)

        def has_config_ui(self):
            return True

        def get_config_ui(self):
            return _CONFIG_UI

        def execute(self, ctx):
            if ctx.step != orca.slicing.Step.psGCodePostProcess:
                return orca.ExecutionResult.success()
            if not ctx.gcode_path:
                return orca.ExecutionResult.success()

            try:
                config = json.loads(self.get_config() or "{}")
            except (TypeError, json.JSONDecodeError):
                config = {}
            if not isinstance(config, dict):
                config = {}

            swap = _flag(config, "swap_toolchange_travel")
            convert = _flag(config, "convert_m109")
            try:
                with open(ctx.gcode_path, "r", encoding="utf-8", errors="ignore") as gcode:
                    lines = gcode.readlines()
                if process(lines, swap_toolchange_travel=swap, convert_m109=convert):
                    with open(ctx.gcode_path, "w", encoding="utf-8", newline="") as gcode:
                        gcode.writelines(lines)
            except OSError as exc:
                return orca.ExecutionResult.failure(
                    orca.PluginResult.RecoverableError,
                    f"Could not update G-code: {exc}",
                )
            return orca.ExecutionResult.success("G-code updated" if swap or convert else "")

    @orca.plugin
    class MedusaHCPlugin(orca.base):
        def register_capabilities(self):
            orca.register_capability(MedusaHC)
