/*
 * File: c-tool.c
 * Purpose: Tool mode main loop (used with the headless -mtool module).
 *
 * Replaces the interactive Game_loop(): keeps pumping the network (so
 * keepalives flow), services the server's requests without any UI, and
 * reports what happens as JSON lines on stdout. Commands are read as
 * lines from stdin.
 *
 * Events (one JSON object per line, always with "ev" and "t"):
 *   ready        {nick}                     -- in the game, loop running
 *   message      {type, text}
 *   popup        {header, lines[]}          -- e.g. MOTD, examine text
 *   pause        {}                         -- server asked for "any key"
 *   interactive  {header}                   -- remote browser; ESC sent back
 *   confirm      {type, id, prompt, answer} -- always declined
 *   store        {flag, name, owner, num, items[]}
 *   store_leave  {}                         -- server closed the store
 *   blocked_input {where}                   -- a prompt wanted a key; got ESC
 *   error        {text}
 *
 * Commands (one per line):
 *   quit                                    -- leave the game and exit
 */

#include "c-angband.h"

bool tool_mode = FALSE;

static struct timeval tool_t0;

/* Prompts that asked for a key since the last loop iteration */
static int tool_blocked = 0;

/* Partial command line from stdin */
static char tool_cmd_buf[1024];
static int tool_cmd_len = 0;

/*** JSON output ***/

static void tool_json_str(cptr s)
{
	putchar('"');
	for (; *s; s++)
	{
		unsigned char c = (unsigned char)*s;
		if (c == '"' || c == '\\') printf("\\%c", c);
		else if (c < 0x20 || c >= 0x7f) printf("\\u%04x", c);
		else putchar(c);
	}
	putchar('"');
}

static void tool_ev_begin(cptr ev)
{
	struct timeval now;
	gettimeofday(&now, NULL);
	printf("{\"ev\":\"%s\",\"t\":%.3f", ev,
	       (double)(now.tv_sec - tool_t0.tv_sec)
	       + (double)(now.tv_usec - tool_t0.tv_usec) / 1000000.0);
}

static void tool_kv_str(cptr key, cptr val)
{
	printf(",\"%s\":", key);
	tool_json_str(val);
}

static void tool_kv_int(cptr key, long val)
{
	printf(",\"%s\":%ld", key, val);
}

static void tool_ev_end(void)
{
	printf("}\n");
	fflush(stdout);
}

/* Copy a stream row to buf as text, right-trimmed */
static void tool_row_text(cave_view_type *row, int wid, char *buf, size_t len)
{
	int i, n = 0;

	for (i = 0; i < wid && n < (int)len - 1; i++)
	{
		buf[n++] = (row[i].c ? row[i].c : ' ');
	}
	while (n > 0 && buf[n - 1] == ' ') n--;
	buf[n] = '\0';
}

/*** Hooks called from the rest of the client ***/

/* do_handle_message() */
void tool_emit_message(cptr mesg, u16b type)
{
	tool_ev_begin("message");
	tool_kv_int("type", type);
	tool_kv_str("text", mesg);
	tool_ev_end();
}

/* show_popup() -- the popup text is complete */
void tool_emit_popup(void)
{
	byte win = p_ptr->remote_term;
	byte st = window_to_stream[win];
	int wid = p_ptr->stream_wid[st];
	int n;
	char buf[1024];

	tool_ev_begin("popup");
	tool_kv_str("header", special_line_header);
	printf(",\"lines\":[");
	for (n = 0; n <= last_remote_line[win]; n++)
	{
		tool_row_text(stream_cave(st, n), wid, buf, sizeof(buf));
		if (n) putchar(',');
		tool_json_str(buf);
	}
	printf("]");
	tool_ev_end();

	/* Popup handled */
	special_line_onscreen = FALSE;
}

/* inkey_ex() / Term_inkey() -- some prompt wants a key */
void tool_blocked_input(cptr where)
{
	tool_ev_begin("blocked_input");
	tool_kv_str("where", where);
	tool_ev_end();

	/* A prompt that keeps re-asking would spin forever */
	if (++tool_blocked > 1000) quit("Tool mode: stuck in an input prompt.");
}

/*** Requests from the server ***/

static void tool_emit_store(void)
{
	int i;

	tool_ev_begin("store");
	tool_kv_int("flag", store_flag);
	tool_kv_str("name", store_name);
	tool_kv_str("owner", store_owner_name);
	tool_kv_int("num", store.stock_num);
	printf(",\"items\":[");
	for (i = 0; i < store.stock_num && i < STORE_INVEN_MAX; i++)
	{
		object_type *o_ptr = &store.stock[i];

		if (i) putchar(',');
		printf("{\"slot\":%d", i);
		tool_kv_str("name", store_names[i]);
		tool_kv_int("number", o_ptr->number);
		tool_kv_int("price", store_prices[i]);
		tool_kv_int("weight", o_ptr->weight);
		/* recv_store() stashes the glyph in ix/iy and tval attr in sval */
		tool_kv_int("ga", (byte)o_ptr->ix);
		tool_kv_int("gc", (byte)o_ptr->iy);
		tool_kv_int("attr", (byte)o_ptr->sval);
		putchar('}');
	}
	printf("]");
	tool_ev_end();
}

/* Tool-mode counterpart of process_requests(): no UI, never blocks */
static void tool_process_requests(void)
{
	if (pause_requested)
	{
		pause_requested = FALSE;
		tool_ev_begin("pause");
		tool_ev_end();
	}
	if (local_browser_requested)
	{
		local_browser_requested = FALSE;
		tool_ev_begin("local_browser");
		tool_kv_str("header", special_line_header);
		tool_ev_end();
	}
	if (simple_popup_requested)
	{
		/* Accept the popup; tool_emit_popup() reports it when complete */
		simple_popup_requested = FALSE;
		special_line_onscreen = TRUE;
	}
	if (special_line_requested)
	{
		/* Remote browser / interactive mode: decline by sending ESC */
		special_line_requested = FALSE;
		tool_ev_begin("interactive");
		tool_kv_str("header", special_line_header);
		tool_ev_end();
		send_term_key(ESCAPE);
	}
	if (confirm_requested)
	{
		/* Always decline (not answering is how get_check() says no) */
		confirm_requested = FALSE;
		tool_ev_begin("confirm");
		tool_kv_int("type", confirm_type);
		tool_kv_int("id", confirm_id);
		tool_kv_str("prompt", confirm_prompt);
		printf(",\"answer\":false");
		tool_ev_end();
	}
	if (enter_store)
	{
		enter_store = FALSE;
		tool_emit_store();
	}
	if (leave_store)
	{
		leave_store = FALSE;
		tool_ev_begin("store_leave");
		tool_ev_end();
	}
}

/*** Commands from stdin ***/

static void tool_do_command(char *line)
{
	if (streq(line, "quit"))
	{
		quit(NULL);
	}
	else if (!STRZERO(line))
	{
		tool_ev_begin("error");
		tool_kv_str("text", format("Unknown command: %s", line));
		tool_ev_end();
	}
}

static void tool_poll_stdin(void)
{
	char buf[256];
	int n, i;

	n = read(0, buf, sizeof(buf));

	/* Tool went away */
	if (n == 0) quit(NULL);

	/* Nothing ready (EAGAIN) */
	if (n < 0) return;

	for (i = 0; i < n; i++)
	{
		if (buf[i] == '\n' || buf[i] == '\r')
		{
			tool_cmd_buf[tool_cmd_len] = '\0';
			tool_cmd_len = 0;
			tool_do_command(tool_cmd_buf);
		}
		else if (tool_cmd_len < (int)sizeof(tool_cmd_buf) - 1)
		{
			tool_cmd_buf[tool_cmd_len++] = buf[i];
		}
	}
}

/*** Main loop ***/

void tool_loop(void)
{
	int flags;

	gettimeofday(&tool_t0, NULL);

	/* Commands arrive on stdin; never block on it */
	flags = fcntl(0, F_GETFL, 0);
	if (flags >= 0) fcntl(0, F_SETFL, flags | O_NONBLOCK);

	tool_ev_begin("ready");
	tool_kv_str("nick", nick);
	tool_ev_end();

	while (TRUE)
	{
		tool_blocked = 0;

		/* Do networking (also runs the keepalive timer) */
		network_loop();

		/* Service server requests */
		tool_process_requests();

		/* Read commands */
		tool_poll_stdin();

		/* Keep client-side state (and the virtual screen) current */
		flush_updates();
	}
}
