/*
 * File: main-tool.c
 * Purpose: Headless "display module" for tool-driven clients (-mtool).
 *
 * Provides a single large in-memory term (z-term keeps its screen buffer) with
 * no-op output hooks and no keyboard. Selecting it turns on tool mode:
 * login never prompts, and c-init.c runs tool_loop() (c-tool.c) instead
 * of the interactive Game_loop().
 */

#include "c-angband.h"

static term tool_term_body;

/*
 * Nobody is at the keyboard. If some code path blocks waiting for a key
 * anyway, feed it ESCAPE (and report it) rather than hanging.
 */
static errr Term_xtra_tool(int n, int v)
{
	switch (n)
	{
		case TERM_XTRA_EVENT:
		if (v)
		{
			tool_blocked_input("Term_inkey");
			Term_keypress(ESCAPE);
			return (0);
		}
		return (1);

		case TERM_XTRA_DELAY:
		if (v > 0) usleep(1000 * v);
		return (0);

		case TERM_XTRA_FLUSH:
		case TERM_XTRA_CLEAR:
		case TERM_XTRA_FRESH:
		case TERM_XTRA_NOISE:
		case TERM_XTRA_SHAPE:
		case TERM_XTRA_ALIVE:
		return (0);
	}
	return (1);
}

static errr Term_curs_tool(int x, int y) { return (0); }
static errr Term_wipe_tool(int x, int y, int n) { return (0); }
static errr Term_text_tool(int x, int y, int n, byte a, cptr s) { return (0); }

const char help_tool[] =
	"  -mtool                    Headless tool mode: JSON-lines events on stdout,\n"
	"                            commands on stdin (implies --noprompt).\n";

errr init_tool(void)
{
	term *t = &tool_term_body;

	/* Big enough that the dungeon stream subscribes at the full level size
	 * (MAX_WID x MAX_HGT = 198 x 66, plus sidebar and status lines). The
	 * server then pins the panel at (0,0), so map coordinates are absolute. */
	term_init(t, MAX_WID + SCREEN_CLIP_X + 1, MAX_HGT + 4, 256);

	t->attr_blank = TERM_WHITE;
	t->char_blank = ' ';

	t->text_hook = Term_text_tool;
	t->wipe_hook = Term_wipe_tool;
	t->curs_hook = Term_curs_tool;
	t->xtra_hook = Term_xtra_tool;

	Term_activate(t);
	ang_term[0] = t; /* == term_screen */

	/* Headless means nobody can answer prompts */
	tool_mode = TRUE;
	no_prompt = TRUE;

	return (0);
}
