/*
 * Kirby Super Star — desktop host shim.
 *
 * Identity and hooks, nothing else. The host itself is the framework's
 * (snesrecomp/runner/src/desktop/host_main.h): the pre-boot launcher, ROM
 * resolution and digest checks, config.ini and keybinds.ini, the window and
 * the SDL / OpenGL presenters, audio, gamepads, the in-game save-state
 * browser and rewind filmstrip, the OSD, the pacing clock, crash handlers and
 * the post-mortem report, mod packages, Generate & rebuild, and the netplay
 * barrier when the project is built with it. A fix there reaches this
 * project on a submodule pull; nothing in this file needs to change for it.
 *
 * This file used to BE the host -- a ~700-line copy made at scaffold time --
 * so every project scaffolded before a fix kept the bug. Two ports of the
 * same game, a week apart, had different hosts.
 *
 * Nothing here ever ships a ROM. The player supplies one; the host makes
 * that easy (launcher, then positional argument, then a copy beside the
 * executable, then the rom.cfg cache, then a file picker) and checks what it
 * is handed against the digests in rom_identity.txt.
 *
 * Grow this file only with what is specific to THIS title: a custom
 * presenter (prepare_frame / draw_frame), an SPC player, a pacing rule
 * (keep_pacing_debt), a Mods provider. See SnesDesktopHostGame for the
 * complete list of hooks and what each is for.
 */

#include "host_main.h"
#include "game_rtl.h"
#include "config.h"                   /* live desktop display settings */
#include "snesrecomp_rom_identity.h"  /* generated from rom_identity.txt */

#include <stdio.h>
#include <stdlib.h>
#include "snes/interp_bridge.h"

/* Emit the last interpreted guest instructions only in diagnostic CI runs.
 * This reveals whether a nominally successful boot is actually trapped in a
 * reset-vector/open-bus loop before the PPU receives any writes. */
static void kirby_dump_interpreter_tail(void)
{
    if (getenv("SNESRECOMP_DUMP_INTERP_RECENT") != NULL) {
        fprintf(stderr, "[kirby_boot] final interpreter trace\n");
        interp_bridge_dump_recent(512, stderr);
    }
}

/* The desktop host asks once per frame how wide the SNES PPU field should be.
 * Native mode stays 256 pixels; the experimental 16:9 mode exposes 43 extra
 * PPU pixels on both sides instead of stretching the original 4:3 picture. */
static void kirby_prepare_frame(int drawable_w, int drawable_h,
                                int *frame_w, int *frame_h)
{
    (void)drawable_w;
    (void)drawable_h;
    if (frame_w) {
        *frame_w = g_config.widescreen
            ? SnesDisplayAspect_ComputeWideFrameWidth(256)
            : 256;
    }
    if (frame_h) *frame_h = 224;
}

#ifndef __ANDROID__
#define SDL_MAIN_HANDLED 1
#endif
#include "desktop/sdl_compat.h"
#ifdef __ANDROID__
/* SDLActivity loads libmain.so and dlsyms its SDL_main. */
#define main SDL_main
#endif

#ifndef SNES_GAME_VERSION
#define SNES_GAME_VERSION "dev"
#endif

static const SnesDesktopHostGame kGameHost = {
    .display_name        = "Kirby Super Star",
    .window_title        = "Kirby Super Star",
    .region              = SNESRECOMP_ROM_REGION,
    .rom_file            = SNESRECOMP_ROM_FILE,
    .expected_sha256_hex = SNESRECOMP_ROM_EXPECTED_SHA256,
    .expected_crc32_hex  = SNESRECOMP_ROM_EXPECTED_CRC32,
    .game_id             = SNESRECOMP_ROM_GAME_ID,
    .build_version       = SNES_GAME_VERSION,
    .game_info           = &kGameInfo,
    .num_players         = 2,
    .widescreen_supported = 1,
    .frame_width         = 256,
    .frame_height        = 224,
    .native_widescreen   = 1,
    .prepare_frame       = kirby_prepare_frame,
    /* Battery-backed SRAM shows the launcher's SAVES panel. Leave NULL for a
     * title without one. The path is exe-relative. */
    .sram_path           = "saves/save.srm",
};

#ifndef __ANDROID__
#undef main   /* desktop: keep plain main() even if SDL_main.h remapped it */
#endif
int main(int argc, char **argv)
{
    if (getenv("SNESRECOMP_DUMP_INTERP_RECENT") != NULL)
        atexit(kirby_dump_interpreter_tail);
    return snesrecomp_desktop_main(&kGameHost, argc, argv);
}
