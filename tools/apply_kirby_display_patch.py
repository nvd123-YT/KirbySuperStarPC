#!/usr/bin/env python3
"""Apply Kirby-owned display integration to the pinned shared submodules.

The submodules stay pinned and clean in Git. These guarded source edits run at
CMake configure time so local builds, CI and Generate & rebuild use the same
Kirby-specific widescreen and output-resolution support.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def replace_once(path: Path, old: str, new: str, marker: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"Required pinned source is missing: {path}")
    source = path.read_text(encoding="utf-8")
    if marker in source:
        return
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one patch anchor in {path}, found {count}: {old[:100]!r}"
        )
    source = source.replace(old, new, 1)
    if marker not in source:
        raise RuntimeError(f"Patch marker missing after editing {path}: {marker}")
    path.write_text(source, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework-root", required=True, type=Path)
    parser.add_argument("--ui-root", required=True, type=Path)
    args = parser.parse_args()

    fw = args.framework_root
    ui = args.ui_root

    try:
        # The shared host owns the PPU's native expanded-field path. Keep the
        # user's current 3x/other scale as the initial equivalent window width.
        replace_once(
            fw / "runner/src/desktop/host_main.c",
            "  ls->window_scale  = g_config.window_scale ? g_config.window_scale : 2;\n",
            "  ls->window_scale  = g_config.window_scale ? g_config.window_scale : 2;\n"
            "  /* KIRBY_DISPLAY_SETTINGS_SEED: persist the native/fixed-wide view and\n"
            "   * expose output sizes without changing the existing startup size. */\n"
            "  ls->widescreen = g_config.widescreen ? 1 : 0;\n"
            "  ls->window_width = g_config.window_width > 0 ? g_config.window_width :\n"
            "      ls->window_scale * WindowBaseWidth(g_snes_width > 0 ? g_snes_width : 256);\n",
            "KIRBY_DISPLAY_SETTINGS_SEED",
        )
        replace_once(
            fw / "runner/src/desktop/host_main.c",
            "  gi->has_renderer     = 1;\n",
            "  /* KIRBY_DISPLAY_WINDOW_SIZE: this host can apply explicit pixel dimensions. */\n"
            "  gi->has_window_size = 1;\n"
            "  gi->has_renderer     = 1;\n",
            "KIRBY_DISPLAY_WINDOW_SIZE",
        )
        replace_once(
            fw / "runner/src/desktop/host_main.c",
            "  g_config.window_scale        = (uint8)ls->window_scale;\n",
            "  g_config.window_scale        = (uint8)ls->window_scale;\n"
            "  /* KIRBY_DISPLAY_SETTINGS_COMMIT: resolution controls the output window,\n"
            "   * while the widescreen switch changes the PPU field itself. */\n"
            "  g_config.widescreen = ls->widescreen != 0;\n"
            "  g_config.window_width = ls->window_width > 0 ? ls->window_width :\n"
            "      (ls->window_scale > 0 ? ls->window_scale : 2) *\n"
            "      WindowBaseWidth(g_snes_width > 0 ? g_snes_width : 256);\n"
            "  if (g_config.window_width < 1) g_config.window_width = 960;\n"
            "  g_config.window_height = g_config.widescreen\n"
            "      ? (g_config.window_width * 9) / 16\n"
            "      : (g_config.window_width * 3) / 4;\n",
            "KIRBY_DISPLAY_SETTINGS_COMMIT",
        )
        replace_once(
            fw / "runner/src/desktop/host_main.c",
            "  bool custom_size = g_config.window_width != 0 && g_config.window_height != 0;\n"
            "  if (!custom_size && !(g_win_flags & fs_mask) &&\n"
            "      (g_config.window_scale != before->window_scale ||\n"
            "       g_config.display_aspect != before->display_aspect ||\n"
            "       g_config.fullscreen != before->fullscreen)) {\n"
            "    if (g_config.window_scale)\n"
            "      g_current_window_scale = IntMin(g_config.window_scale, kMaxWindowScale);\n"
            "    ChangeWindowScale(0);\n"
            "  }\n",
            "  bool custom_size = g_config.window_width != 0 && g_config.window_height != 0;\n"
            "  bool custom_size_changed =\n"
            "      g_config.window_width != before->window_width ||\n"
            "      g_config.window_height != before->window_height;\n"
            "  /* KIRBY_DISPLAY_LIVE_RESIZE: apply a changed preset immediately in\n"
            "   * an in-game launcher; fullscreen remains owned by the display mode. */\n"
            "  if (!(g_win_flags & fs_mask) && custom_size && custom_size_changed) {\n"
            "    SDL_SetWindowSize(g_window, g_config.window_width, g_config.window_height);\n"
            "  } else if (!custom_size && !(g_win_flags & fs_mask) &&\n"
            "             (g_config.window_scale != before->window_scale ||\n"
            "              g_config.display_aspect != before->display_aspect ||\n"
            "              g_config.fullscreen != before->fullscreen)) {\n"
            "    if (g_config.window_scale)\n"
            "      g_current_window_scale = IntMin(g_config.window_scale, kMaxWindowScale);\n"
            "    ChangeWindowScale(0);\n"
            "  }\n",
            "KIRBY_DISPLAY_LIVE_RESIZE",
        )

        # WindowSize was already parsed but was absent from WriteConfigFile's
        # key list. Add the matching writer so chosen resolutions survive exit.
        replace_once(
            fw / "runner/src/desktop/mmx_config.c",
            '    { "Graphics", "WindowScale" },\n',
            '    { "Graphics", "WindowScale" },\n'
            '    { "Graphics", "WindowSize" },\n',
            'KIRBY_WINDOW_SIZE_CONFIG_KEY',
        )
        replace_once(
            fw / "runner/src/desktop/mmx_config.c",
            '  const int N = (int)countof(kvs);\n'
            '  CfgSet(kvs, N, "Graphics", "WindowScale", "%d",\n',
            '  const int N = (int)countof(kvs);\n'
            '  /* KIRBY_WINDOW_SIZE_CONFIG_WRITE: Auto retains legacy scale behavior. */\n'
            '  char window_size[32];\n'
            '  if (g_config.window_width > 0 && g_config.window_height > 0)\n'
            '    snprintf(window_size, sizeof(window_size), "%dx%d",\n'
            '             g_config.window_width, g_config.window_height);\n'
            '  else\n'
            '    snprintf(window_size, sizeof(window_size), "Auto");\n'
            '  CfgSet(kvs, N, "Graphics", "WindowSize", "%s", window_size);\n'
            '  CfgSet(kvs, N, "Graphics", "WindowScale", "%d",\n',
            "KIRBY_WINDOW_SIZE_CONFIG_WRITE",
        )

        # Offer standard window widths through 8K (7680x4320 in 16:9 mode).
        # The current default (3x: 960x720) remains in the list and unchanged.
        replace_once(
            ui / "src/common/launcher_model.c",
            "static const int kWindowWidths[]    = { 960, 1280, 1600, 1920 };",
            "static const int kWindowWidths[]    = {\n"
            "    320, 400, 512, 640, 800, 960, 1280, 1600, 1920,\n"
            "    2240, 2560, 2880, 3200, 3840, 5120, 7680\n"
            "}; /* KIRBY_8K_WINDOW_PRESETS */",
            "KIRBY_8K_WINDOW_PRESETS",
        )
        replace_once(
            ui / "src/common/launcher_model.c",
            "    int aspect = clampi(m->s.aspect_index, 0, 2);\n"
            "    int h = (aspect == 1) ? (w * 9 / 16) : (aspect == 2) ? (w * 9 / 21) : (w * 3 / 4);\n",
            "    int aspect = clampi(m->s.aspect_index, 0, 2);\n"
            "    /* KIRBY_8K_WINDOW_ASPECT: the output window follows the fixed\n"
            "     * 16:9 view when widescreen is enabled, otherwise stays 4:3. */\n"
            "    int h = m->widescreen_supported\n"
            "        ? (m->s.widescreen ? (w * 9 / 16) : (w * 3 / 4))\n"
            "        : ((aspect == 1) ? (w * 9 / 16) :\n"
            "           (aspect == 2) ? (w * 9 / 21) : (w * 3 / 4));\n",
            "KIRBY_8K_WINDOW_ASPECT",
        )

        # The pinned launcher model had the widescreen mutator but no visible
        # row in its display panel. Add it to both minimal and deep display paths.
        replace_once(
            ui / "src/common/backends/imgui/launcher_imgui.cpp",
            "    ImGui::PopID();\n"
            "}\n\n"
            "// True when this game exposes ANY of the deeper PSX-style DISPLAY controls.",
            "    ImGui::PopID();\n"
            "}\n\n"
            "static void draw_widescreen_row(LauncherModel* m, const LauncherTheme& th) {\n"
            "    if (!m || !m->widescreen_supported) return;\n"
            "    row_label_right(\"Widescreen\", th, ImGui::GetFrameHeight());\n"
            "    bool enabled = m->s.widescreen != 0;\n"
            "    if (ImGui::Checkbox(\"##widescreen\", &enabled))\n"
            "        launcher_model_toggle_widescreen(m);\n"
            "    if (ImGui::IsItemHovered(ImGuiHoveredFlags_DelayNormal))\n"
            "        ImGui::SetTooltip(\"Experimental: renders additional SNES picture area on both sides.\n\"\n"
            "                          \"Some screen-edge or HUD elements may need title-specific tuning.\n\"\n"
            "                          \"This does not increase the original game's pixel detail.\");\n"
            "}\n\n"
            "// True when this game exposes ANY of the deeper PSX-style DISPLAY controls.",
            "KIRBY_WIDESCREEN_SETTINGS_ROW",
        )
        replace_once(
            ui / "src/common/backends/imgui/launcher_imgui.cpp",
            "        draw_aspect_row(m, th);\n"
            "        if (m->has_integer_scale)",
            "        draw_aspect_row(m, th);\n"
            "        draw_widescreen_row(m, th);\n"
            "        if (m->has_integer_scale)",
            "KIRBY_WIDESCREEN_LEGACY_CALL",
        )
        replace_once(
            ui / "src/common/backends/imgui/launcher_imgui.cpp",
            "    draw_aspect_row(m, th);\n\n"
            "    if (m->has_sharp_filter)",
            "    draw_aspect_row(m, th);\n"
            "    draw_widescreen_row(m, th);\n\n"
            "    if (m->has_sharp_filter)",
            "KIRBY_WIDESCREEN_DEEP_CALL",
        )

    except Exception as exc:
        print(f"Kirby display patch failed: {exc}", file=sys.stderr)
        return 2

    print("Kirby widescreen + 8K output-resolution patches are active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
