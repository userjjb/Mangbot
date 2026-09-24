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
 *   pos          {y, x}                     -- own position (absolute), on change
 *   ack          {cmd}                      -- command accepted and sent
 *   error        {text[, cmd]}
 *   (replies)    commands, status, inven, map -- see tool_do_command()
 *
 * Commands (one per line; DIR is a keypad digit 1-9, 5/0 = none):
 *   walk DIR                                -- also leaves a store
 *   pathfind Y X                            -- server-side path (<= ~25 tiles)
 *   open DIR | alter DIR                    -- e.g. enter a player shop
 *   examine SLOT                            -- in a store; reply is a popup
 *   leave                                   -- leave the store
 *   eat ITEM                                -- ITEM = inventory index (a=0)
 *   custom KEY [store] [item=N] [dir=N] [value=N] [entry=TEXT]
 *   commands | status | inven | map         -- queries
 *   quit                                    -- leave the game and exit
 */

#include "c-angband.h"

#include "../common/net-basics.h"
#include "../common/net-imps.h"

extern connection_type *serv;

bool tool_mode = FALSE;

static struct timeval tool_t0;

/* Prompts that asked for a key since the last loop iteration */
static int tool_blocked = 0;

/* Own position, from the server's MCURSOR_PLAYER cursor packets */
static int tool_py = -1, tool_px = -1;

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

/* recv_cursor() -- server marks our own position (absolute y, x) */
void tool_note_cursor(byte vis, byte y, byte x)
{
	int ny, nx;

	if (!(vis & MCURSOR_PLAYER)) return;

	/* Offline: we're outside the panel the server is showing */
	if (vis & MCURSOR_OFFLINE) return;

	ny = y;
	nx = x;
	if (ny == tool_py && nx == tool_px) return;
	tool_py = ny;
	tool_px = nx;

	tool_ev_begin("pos");
	tool_kv_int("y", tool_py);
	tool_kv_int("x", tool_px);
	tool_ev_end();
}

static void tool_error(cptr cmd, cptr text)
{
	tool_ev_begin("error");
	tool_kv_str("text", text);
	if (cmd) tool_kv_str("cmd", cmd);
	tool_ev_end();
}

static void tool_ack(cptr cmd)
{
	tool_ev_begin("ack");
	tool_kv_str("cmd", cmd);
	tool_ev_end();
}

/* Find a server-defined custom command by key (never hard-code indices) */
static int tool_find_custom(char key, bool store_cmd)
{
	int i;

	for (i = 0; i < custom_commands; i++)
	{
		custom_command_type *cc_ptr = &custom_command[i];
		bool is_store = (cc_ptr->flag & COMMAND_STORE) ? TRUE : FALSE;
		if (cc_ptr->m_catch == key && is_store == store_cmd) return i;
	}
	return -1;
}

static void tool_send_custom(cptr cmd, char key, bool store_cmd, int item, int dir, s32b value, cptr entry)
{
	char buf[60];
	int i = tool_find_custom(key, store_cmd);

	if (i < 0)
	{
		tool_error(cmd, format("No %scommand '%c' on this server", store_cmd ? "store " : "", key));
		return;
	}
	my_strcpy(buf, entry ? entry : "", sizeof(buf));
	if (!send_custom_command((byte)i, (char)item, (char)dir, value, buf))
	{
		tool_error(cmd, "send failed");
		return;
	}
	tool_ack(cmd);
}

static bool tool_valid_dir(int dir)
{
	return (dir >= 0 && dir <= 9);
}

static void tool_query_commands(void)
{
	int i;

	tool_ev_begin("commands");
	printf(",\"list\":[");
	for (i = 0; i < custom_commands; i++)
	{
		custom_command_type *cc_ptr = &custom_command[i];
		char key[2];

		key[0] = cc_ptr->m_catch;
		key[1] = '\0';
		if (i) putchar(',');
		printf("{\"i\":%d", i);
		tool_kv_str("key", key);
		tool_kv_int("pkt", (byte)cc_ptr->pkt);
		tool_kv_int("scheme", cc_ptr->scheme);
		printf(",\"flag\":\"0x%08lx\"", (unsigned long)cc_ptr->flag);
		printf(",\"store\":%s", (cc_ptr->flag & COMMAND_STORE) ? "true" : "false");
		tool_kv_str("display", cc_ptr->display);
		putchar('}');
	}
	printf("]");
	tool_ev_end();
}

static void tool_query_status(void)
{
	int i, j;

	tool_ev_begin("status");
	tool_kv_int("y", tool_py);
	tool_kv_int("x", tool_px);
	printf(",\"ghost\":%s", p_ptr->ghost ? "true" : "false");
	printf(",\"ind\":{");
	for (i = 0; i < known_indicators; i++)
	{
		indicator_type *i_ptr = &indicators[i];

		if (i) putchar(',');
		tool_json_str(i_ptr->mark ? i_ptr->mark : "?");
		putchar(':');
		if (i_ptr->type == INDITYPE_STRING)
		{
			tool_json_str(str_coffers[i] ? str_coffers[i] : "");
		}
		else
		{
			putchar('[');
			for (j = 0; j < i_ptr->amnt; j++)
			{
				if (j) putchar(',');
				printf("%ld", (long)coffers[coffer_refs[i] + j]);
			}
			putchar(']');
		}
	}
	printf("}");
	tool_ev_end();
}

static void tool_query_inven(void)
{
	int i;
	bool first = TRUE;

	tool_ev_begin("inven");
	printf(",\"items\":[");
	for (i = 0; i < INVEN_TOTAL; i++)
	{
		object_type *o_ptr = &inventory[i];

		if (!o_ptr->tval) continue;
		if (!first) putchar(',');
		first = FALSE;
		printf("{\"item\":%d", i);
		printf(",\"equip\":%s", (i >= INVEN_WIELD) ? "true" : "false");
		tool_kv_str("name", inventory_name[i]);
		tool_kv_int("tval", o_ptr->tval);
		tool_kv_int("number", o_ptr->number);
		tool_kv_int("weight", o_ptr->weight);
		putchar('}');
	}
	printf("]");
	tool_ev_end();
}

static void tool_query_map(void)
{
	int st, wid, hgt, n;
	char buf[1024];

	/* The subscribed stream that draws the dungeon view */
	for (st = 0; st < known_streams; st++)
	{
		if (streams[st].addr == NTERM_WIN_OVERHEAD && p_ptr->stream_hgt[st]) break;
	}
	if (st >= known_streams)
	{
		tool_error("map", "no dungeon stream subscribed");
		return;
	}
	wid = p_ptr->stream_wid[st];
	hgt = p_ptr->stream_hgt[st];

	tool_ev_begin("map");
	tool_kv_str("stream", streams[st].mark);
	tool_kv_int("wid", wid);
	tool_kv_int("hgt", hgt);
	printf(",\"rows\":[");
	for (n = 0; n < hgt; n++)
	{
		int i;

		/* Keep full width (no trim) so columns line up */
		for (i = 0; i < wid && i < (int)sizeof(buf) - 1; i++)
		{
			char c = stream_cave(st, n)[i].c;
			buf[i] = (c ? c : ' ');
		}
		buf[i] = '\0';
		if (n) putchar(',');
		tool_json_str(buf);
	}
	printf("]");
	tool_ev_end();
}

static void tool_do_command(char *line)
{
	char verb[32] = { 0 };
	int a = 0, b = 0, n;

	n = sscanf(line, "%31s %d %d", verb, &a, &b);
	if (n < 1) return;

	if (streq(verb, "quit"))
	{
		quit(NULL);
	}
	else if (streq(verb, "walk"))
	{
		if (n < 2 || !tool_valid_dir(a)) { tool_error(line, "usage: walk DIR"); return; }
		send_walk((char)a);
		tool_ack(line);
	}
	else if (streq(verb, "pathfind"))
	{
		if (n < 3 || a < 0 || a > 255 || b < 0 || b > 255)
		{
			tool_error(line, "usage: pathfind Y X");
			return;
		}
		cq_printf(&serv->wbuf, "%c%c%c", PKT_PATHFIND, (byte)a, (byte)b);
		tool_ack(line);
	}
	else if (streq(verb, "open") || streq(verb, "alter"))
	{
		if (n < 2 || !tool_valid_dir(a)) { tool_error(line, "usage: open|alter DIR"); return; }
		tool_send_custom(line, (verb[0] == 'o' ? 'o' : '+'), FALSE, 0, a, 0, NULL);
	}
	else if (streq(verb, "examine"))
	{
		if (n < 2 || a < 0 || a >= STORE_INVEN_MAX) { tool_error(line, "usage: examine SLOT"); return; }
		tool_send_custom(line, 'l', TRUE, a, 0, 0, NULL);
	}
	else if (streq(verb, "leave"))
	{
		send_store_leave();
		tool_ack(line);
	}
	else if (streq(verb, "eat"))
	{
		if (n < 2 || a < 0 || a >= INVEN_PACK) { tool_error(line, "usage: eat ITEM"); return; }
		tool_send_custom(line, 'E', FALSE, a, 0, 0, NULL);
	}
	else if (streq(verb, "custom"))
	{
		/* custom KEY [store] [item=N] [dir=N] [value=N] [entry=TEXT (rest of line)] */
		char *s = line + strlen("custom");
		char key;
		bool store_cmd = FALSE;
		int item = 0, dir = 0;
		long value = 0;
		char *entry = NULL;
		char *tok;

		while (*s == ' ') s++;
		if (!*s) { tool_error(line, "usage: custom KEY [store] [item=N] [dir=N] [value=N] [entry=TEXT]"); return; }
		key = *s++;

		/* entry= swallows the rest of the line, so cut it off first */
		if ((tok = strstr(s, "entry=")) != NULL)
		{
			entry = tok + strlen("entry=");
			*tok = '\0';
		}
		for (tok = strtok(s, " "); tok; tok = strtok(NULL, " "))
		{
			if (streq(tok, "store")) store_cmd = TRUE;
			else if (prefix(tok, "item=")) item = atoi(tok + 5);
			else if (prefix(tok, "dir=")) dir = atoi(tok + 4);
			else if (prefix(tok, "value=")) value = atol(tok + 6);
			else { tool_error(line, format("bad argument '%s'", tok)); return; }
		}
		tool_send_custom(line, key, store_cmd, item, dir, (s32b)value, entry);
	}
	else if (streq(verb, "commands")) tool_query_commands();
	else if (streq(verb, "status")) tool_query_status();
	else if (streq(verb, "inven")) tool_query_inven();
	else if (streq(verb, "map")) tool_query_map();
	else
	{
		tool_error(line, "Unknown command");
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
