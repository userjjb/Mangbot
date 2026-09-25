/*
 * File: c-pktlog.c
 * Purpose: Optional packet logger (debug aid for tool-driven clients).
 *
 * Enabled with "--pktlog PATH" on the command line (or the MANG_PKTLOG
 * environment variable). Writes one JSON object per line:
 *
 *   {"t":1.234,"dir":"R","id":51,"name":"PKT_STORE","len":40,"res":1,
 *    "hex":"33...","txt":"3...Broad Sword"}
 *
 * dir is "R" (server->client, one record per parsed packet), "S"
 * (client->server, one record per flushed chunk; keepalives are split out),
 * "E" (event/note), or "K" (a key consumed by a command or prompt:
 * {"key","code","keymap","icky"}; icky = a menu/popup screen was up).
 * "len" counts the packet id byte. Password hashes in sent packets are
 * blanked to X, and private (password) input is never key-logged.
 */

#include "c-angband.h"

#include "../common/net-basics.h"
#include "../common/net-imps.h"

static FILE *pktlog_fp = NULL;

/* While > 0 keys aren't logged (password prompts) */
static int pktlog_muted = 0;
static struct timeval pktlog_t0;

/* Names of client->server packets (from the server's table) */
static cptr send_names[256];

bool pktlog_enabled(void)
{
	return (pktlog_fp != NULL);
}

void pktlog_init(void)
{
	char path[1024] = { 0 };
	const char *env;
	int i;

	env = getenv("MANG_PKTLOG");
	if (env) my_strcpy(path, env, sizeof(path));
	clia_read_string(path, sizeof(path), "pktlog");
	if (STRZERO(path)) return;

	pktlog_fp = fopen(path, "a");
	if (!pktlog_fp)
	{
		plog(format("Unable to open packet log '%s'", path));
		return;
	}

	for (i = 0; i < 256; i++) send_names[i] = NULL;
#define PACKET(PKT, SCHEME, FUNC) send_names[PKT] = #PKT;
#define PCOMMAND(PKT, SCHEME, FUNC) send_names[PKT] = #PKT;
#include "../server/net-game.h"
#undef PCOMMAND
#undef PACKET
	/* Handled outside the server's packet table */
	send_names[PKT_LOGIN] = "PKT_LOGIN";

	gettimeofday(&pktlog_t0, NULL);
	/* Wall clock of t=0, to line the log up with other recordings */
	pktlog_note(format("pktlog started epoch=%ld.%06ld",
	                   (long)pktlog_t0.tv_sec, (long)pktlog_t0.tv_usec));
}

static double pktlog_elapsed(void)
{
	struct timeval now;
	gettimeofday(&now, NULL);
	return (double)(now.tv_sec - pktlog_t0.tv_sec)
	     + (double)(now.tv_usec - pktlog_t0.tv_usec) / 1000000.0;
}

/* Write a JSON-escaped string (quotes included) */
static void pktlog_json_str(cptr s)
{
	fputc('"', pktlog_fp);
	for (; *s; s++)
	{
		unsigned char c = (unsigned char)*s;
		if (c == '"' || c == '\\') fprintf(pktlog_fp, "\\%c", c);
		else if (c < 0x20 || c >= 0x7f) fprintf(pktlog_fp, "\\u%04x", c);
		else fputc(c, pktlog_fp);
	}
	fputc('"', pktlog_fp);
}

static void pktlog_record(cptr dir, byte id, cptr name, const char *buf, int len, int res)
{
	int i;

	fprintf(pktlog_fp, "{\"t\":%.3f,\"dir\":\"%s\",\"id\":%d,\"name\":",
	        pktlog_elapsed(), dir, id);
	pktlog_json_str(name ? name : "?");
	fprintf(pktlog_fp, ",\"len\":%d,\"res\":%d,\"hex\":\"", len, res);
	for (i = 0; i < len; i++) fprintf(pktlog_fp, "%02x", (byte)buf[i]);
	/* Printable view; non-printables become '.' */
	fprintf(pktlog_fp, "\",\"txt\":\"");
	for (i = 0; i < len; i++)
	{
		unsigned char c = (unsigned char)buf[i];
		if (c == '"' || c == '\\') fprintf(pktlog_fp, "\\%c", c);
		else if (c < 0x20 || c >= 0x7f) fputc('.', pktlog_fp);
		else fputc(c, pktlog_fp);
	}
	fprintf(pktlog_fp, "\"}\n");
	fflush(pktlog_fp);
}

void pktlog_note(cptr msg)
{
	if (!pktlog_fp) return;
	fprintf(pktlog_fp, "{\"t\":%.3f,\"dir\":\"E\",\"note\":", pktlog_elapsed());
	pktlog_json_str(msg);
	fprintf(pktlog_fp, "}\n");
	fflush(pktlog_fp);
}

/* A key consumed by a command or prompt (dir "K"); keymap = it came from
 * a keymap's action string rather than straight from the keyboard/macro */
void pktlog_key(char key, bool keymap)
{
	char buf[2];

	if (!pktlog_fp) return;
	if (pktlog_muted)
	{
		/* Keep the timing, never the key (e.g. a password) */
		fprintf(pktlog_fp, "{\"t\":%.3f,\"dir\":\"K\",\"muted\":true}\n", pktlog_elapsed());
		fflush(pktlog_fp);
		return;
	}
	buf[0] = key;
	buf[1] = '\0';
	fprintf(pktlog_fp, "{\"t\":%.3f,\"dir\":\"K\",\"key\":", pktlog_elapsed());
	pktlog_json_str(buf);
	fprintf(pktlog_fp, ",\"code\":%d,\"keymap\":%s,\"icky\":%d}\n",
	        (byte)key, keymap ? "true" : "false", screen_icky ? 1 : 0);
	fflush(pktlog_fp);
}

/* Stop/resume logging keys, around password prompts (calls nest) */
void pktlog_mute_keys(bool mute)
{
	pktlog_muted += (mute ? 1 : -1);
	if (pktlog_muted < 0) pktlog_muted = 0;
}

/* One parsed server->client packet; name is resolved by net-client.c */
void pktlog_recv(byte id, cptr name, const char *buf, int len, int res)
{
	if (!pktlog_fp) return;
	pktlog_record("R", id, name, buf, len, res);
}

/* Name an outgoing packet; custom commands get their key letter */
static cptr pktlog_send_name(const char *buf, int len, char *tmp, size_t tmplen)
{
	byte id = (byte)buf[0];
	int i;

	if (id == PKT_COMMAND && len > 1)
	{
		i = (byte)buf[1];
		strnfmt(tmp, tmplen, "PKT_COMMAND:'%c'", custom_command[i].m_catch);
		return tmp;
	}
	for (i = 0; i < custom_commands; i++)
	{
		if (custom_command[i].pkt == (char)PKT_COMMAND) continue;
		if ((byte)custom_command[i].pkt == id)
		{
			strnfmt(tmp, tmplen, "%s:'%c'",
			        send_names[id] ? send_names[id] : "CUSTOM",
			        custom_command[i].m_catch);
			return tmp;
		}
	}
	return send_names[id];
}

/* A chunk of client->server bytes about to hit the socket */
void pktlog_send(const char *buf, int len)
{
	static bool first_send = TRUE;
	char tmp[80];

	if (!pktlog_fp) return;

	/* The connection opens with a bare u16 "conntype", not a packet */
	if (first_send && len >= 2)
	{
		first_send = FALSE;
		pktlog_record("S", 0, "HANDSHAKE", buf, 2, 1);
		buf += 2;
		len -= 2;
	}

	/* Split out leading keepalives ("%c%l" = 5 bytes) */
	while (len >= 5 && (byte)buf[0] == PKT_KEEPALIVE)
	{
		pktlog_record("S", PKT_KEEPALIVE, "PKT_KEEPALIVE", buf, 5, 1);
		buf += 5;
		len -= 5;
	}
	if (len <= 0) return;
	{
		/* Never log password hashes ("$1$" + 32 hex, as sent by login and
		 * password change): on the wire they work like the password */
		char *copy = malloc(len);
		int i, j;

		if (!copy) return;
		memcpy(copy, buf, len);
		for (i = 0; i + 3 <= len; i++)
		{
			if (memcmp(copy + i, "$1$", 3)) continue;
			for (j = i + 3; j < len && j < i + 3 + 32 && isxdigit((unsigned char)copy[j]); j++)
				copy[j] = 'X';
		}
		pktlog_record("S", (byte)copy[0], pktlog_send_name(copy, len, tmp, sizeof(tmp)), copy, len, 1);
		free(copy);
	}
}

/* Connection wrapper: copy pending output to the socket buffer, logging it */
int pktlog_send_cb(int data1, data data2)
{
	connection_type *ct = (connection_type *)data2;
	int n = cq_read(&ct->wbuf, (char *)ct->uptr, PD_LARGE_BUFFER);
	if (n > 0) pktlog_send((char *)ct->uptr, n);
	return n;
}
