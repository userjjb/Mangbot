/* File: birth.c */

/* Purpose: create a player character */

/*
 * Copyright (c) 1989 James E. Wilson, Robert A. Koeneke
 *
 * This software may be copied and distributed for educational, research, and
 * not for profit purposes provided that this copyright and statement are
 * included in all such copies.
 */

#include "c-angband.h"
#include "../common/md5.h"


/*
 * Choose the character's name
 */
void choose_name(void)
{
	char tmp[MAX_CHARS];

	/* Prompt and ask */
	prt("Enter your player's name above (or hit ESCAPE).", 21, 2);

	/* Ask until happy */
	while (1)
	{
		/* Go to the "name" area */
		move_cursor(2, 15);

		/* Save the player name */
		my_strcpy(tmp, nick, MAX_CHARS);

		/* Get an input, ignore "Escape" */
		if (askfor_aux(tmp, MAX_NAME_LEN, 0)) my_strcpy(nick, tmp, MAX_CHARS);

		/* All done */
		break;
	}

#ifdef MOBILE_UI
	/* Save entered name to config file */
	/* TODO: maybe do it on all platforms? */
	conf_set_string("MAngband", "nick", nick);
#endif

	/* Pad the name (to clear junk) */
	sprintf(tmp, "%-15.15s", nick);

	/* Re-Draw the name (in light blue) */
	c_put_str(TERM_L_BLUE, tmp, 2, 15);

	/* Erase the prompt, etc */
	clear_from(20);
}


/*
 * Choose the character's password
 */
void enter_password(void)
{
	unsigned int c;
	char tmp[MAX_CHARS];

	/* Prompt and ask */
	prt("Enter your password above (or hit ESCAPE).", 21, 2);

	/* Default */
	my_strcpy(tmp, pass, MAX_CHARS);

	/* Ask until happy */
	while (1)
	{
		/* Go to the "name" area */
		move_cursor(3, 15);

		/* Get an input, ignore "Escape" */
		if (askfor_aux(tmp, 15, 1)) 
		{
			if (!strcmp(tmp, "passwd")) 
			{
			    prt("Please do not use `passwd` as your password.", 22, 2);
			    continue;
			}
			else
				my_strcpy(pass, tmp, MAX_CHARS);
		}

		/* All done */
		break;
	}

#ifdef MOBILE_UI
	/* Save entered password to config file */
	/* TODO: maybe do it on all platforms? */
	conf_set_string("MAngband", "pass", pass);
#endif

	/* Pad the name (to clear junk) 
	sprintf(tmp, "%-15.15s", pass); */

	 /* Re-Draw the name (in light blue) */
	for (c = 0; c < strlen(pass); c++)
		Term_putch(15+c, 3, TERM_L_BLUE, 'x');

	/* Now hash that sucker! */
	MD5Password(pass);

	/* Erase the prompt, etc */
	clear_from(20);
}

/*
 * Hack -- show birth options during birth
 */
void do_cmd_options_birth_call()
{
	/* Sync data */
	while (sync_data() == FALSE)	network_loop();

	/* Hack -- preload "options.prf" */
	process_pref_file("options.prf");

	/* Show */
	do_cmd_options_birth();
}


/*
 * Hack -- show help screen during birth
 */
void do_cmd_help_birth(void)
{
	/* Sync data */
	while (sync_data() == FALSE)	network_loop();

	/* Subscribe */
	init_subscriptions();

	/* Ask it */
	cmd_interactive(0, FALSE);
}

/*
 * Menu helpers
 * TODO: port V menus
 */
static errr menu_sex_entry(char *buf, size_t max, menu_type *menu, int oid)
{
	if (oid == 0) my_strcpy(buf, "Male", max);
	if (oid == 1) my_strcpy(buf, "Female", max);
	return 0;
}
static errr menu_race_entry(char *buf, size_t max, menu_type *menu, int oid)
{
	player_race *rp_ptr;
	rp_ptr = &race_info[oid];
	my_strcpy(buf, p_name + rp_ptr->name, max);
	return 0;
}
static errr menu_class_entry(char *buf, size_t max, menu_type *menu, int oid)
{
	player_class *cp_ptr;
	cp_ptr = &c_info[oid];
	my_strcpy(buf, c_name + cp_ptr->name, max);
	return 0;
}
static errr menu_stat_entry(char *buf, size_t max, menu_type *menu, int oid)
{
	int i;
	my_strcpy(buf, stat_names[oid], max);
	buf[3] = '\0';
	for (i = 0; i < A_MAX; i++)
	{
		if (stat_order[i] == oid) buf[0] = '\0';
	}
	return 0;
}


/*
 * Choose the character's sex				-JWT-
 */
static void choose_sex(void)
{
	char        c;

	put_str("m) Male", 21, 2);
	put_str("f) Female", 21, 17);

	if (z_ask_menu_aux)
	{
		static menu_type menu;
		WIPE(&menu, menu);
		menu.cmd_keys = "\x8B\x8C\n\r";
		menu.count = 2;
		menu.menu_data = NULL;
		menu.selections = "mf";
		z_ask_menu_aux(&menu, &menu_sex_entry, 21, 2);
	}

	while (1)
	{
		put_str("Choose a sex (= for Options, ? for Help, Q to Quit): ", 20, 2);
		c = inkey();
		if (c == 'Q') quit(NULL);
		if ((c == 'm') || (c == 'M'))
		{
			sex = TRUE;
			c_put_str(TERM_L_BLUE, "Male", 4, 15);
			break;
		}
		else if ((c == 'f') || (c == 'F'))
		{
			sex = FALSE;
			c_put_str(TERM_L_BLUE, "Female", 4, 15);
			break;
		}
		else if (c == '=')
		{
			do_cmd_options_birth_call();
		}
		else if (c == '?')
		{
			do_cmd_help_birth();
		}
		else
		{
			bell();
		}
	}

	clear_from(20);
}


/*
 * Allows player to select a race			-JWT-
 */
static void choose_race(void)
{
	player_race *rp_ptr;
	int                 j, k, l, m;

	char                c;

	char		out_val[160];

	if (z_ask_menu_aux)
	{
		static menu_type menu;
		WIPE(&menu, menu);
		menu.cmd_keys = "\x8B\x8C\n\r";
		menu.count = z_info.p_max;
		menu.menu_data = NULL;
		menu.selections = "abcdefghijklmnopqrstuvwxyz";
		z_ask_menu_aux(&menu, &menu_race_entry, 21, 2);
	}

	k = 0;
	l = 2;
	m = 21;


	for (j = 0; j < z_info.p_max; j++)
	{
		rp_ptr = &race_info[j];
		(void)sprintf(out_val, "%c) %s", I2A(j), p_name + rp_ptr->name);
		put_str(out_val, m, l);
		l += 15;
		if (l > 70)
		{
			l = 2;
			m++;
		}
	}

	while (1)
	{
		put_str("Choose a race (= for Options, Q to Quit): ", 20, 2);
		c = inkey();
		if (c == 'Q') quit(NULL);
		j = (islower(c) ? A2I(c) : -1);
		if ((j < z_info.p_max) && (j >= 0))
		{
			race = j;
			rp_ptr = &race_info[j];
			c_put_str(TERM_L_BLUE, p_name + rp_ptr->name, 5, 15);
			break;
		}
		else if (c == '=')
		{
			do_cmd_options_birth_call();
		}
		else if (c == '?')
		{
			do_cmd_help_birth();
		}
		else
		{
			bell();
		}
	}

	clear_from(20);
}


/*
 * Gets a character class				-JWT-
 */
static void choose_class(void)
{
	player_class *cp_ptr;
	int          j, k, l, m;

	char         c;

	char	 out_val[160];

	if (z_ask_menu_aux)
	{
		static menu_type menu;
		WIPE(&menu, menu);
		menu.cmd_keys = "\x8B\x8C\n\r";
		menu.count = z_info.c_max;
		menu.menu_data = NULL;
		menu.selections = "abcdefghijklmnopqrstuvwxyz";
		z_ask_menu_aux(&menu, &menu_class_entry, 21, 2);
	}

	/* Prepare to list */
	k = 0;
	l = 2;
	m = 21;

	/* Display the legal choices */
	for (j = 0; j < z_info.c_max; j++)
	{
		cp_ptr = &c_info[j];
		sprintf(out_val, "%c) %s", I2A(j), c_name + cp_ptr->name);
		put_str(out_val, m, l);
		l += 15;
		if (l > 70)
		{
			l = 2;
			m++;
		}
	}

	/* Get a class */
	while (1)
	{
		put_str("Choose a class (= for Options, Q to Quit): ", 20, 2);
		c = inkey();
		if (c == 'Q') quit(NULL);
		j = (islower(c) ? A2I(c) : -1);
		if ((j < z_info.c_max) && (j >= 0))
		{
			pclass = j;
			cp_ptr = &c_info[j];
			c_put_str(TERM_L_BLUE, c_name + cp_ptr->name, 6, 15);
			break;
		}
		else if (c == '=')
		{
			do_cmd_options_birth_call();
		}
		else if (c == '?')
		{
			do_cmd_help_birth();
		}
		else
		{
			bell();
		}
	}

	clear_from(20);
}


/*
 * Get the desired stat order.
 */
void choose_stat_order(void)
{
	int i, j, k, avail[A_CAP];
	char c;
	char out_val[160], stats[A_CAP][4];

/* HACK!!! TODO: Deprecate at 1.6.0 !!! */
if (A_MAX == 0)
{
    A_MAX = 6;
    C_MAKE(stat_names, A_MAX, char*);
    stat_names[0] = string_make("STR");
    stat_names[1] = string_make("INT");
    stat_names[2] = string_make("WIS");
    stat_names[3] = string_make("DEX");
    stat_names[4] = string_make("CON");
    stat_names[5] = string_make("CHR");
}

	if (z_ask_menu_aux)
	{
		static menu_type menu;
		WIPE(&menu, menu);
		menu.cmd_keys = "\x8B\x8C\n\r";
		menu.count = A_MAX;
		menu.menu_data = NULL;
		menu.selections = "abcdefghijklmnopqrstuvwxyz";
		z_ask_menu_aux(&menu, &menu_stat_entry, 21, 1);
	}

	/* All stats are initially available */
	for (i = 0; i < A_MAX; i++)
	{
		strncpy(stats[i], stat_names[i], 3);
		stats[i][3] = '\0';
		avail[i] = 1;
		stat_order[i] = 0xFF;
	}

	/* Find the ordering of all 6 stats */
	for (i = 0; i < A_MAX; i++)
	{
		/* Clear bottom of screen */
		clear_from(20);

		/* Print available stats at bottom */
		for (k = 0; k < A_MAX; k++)
		{
			/* Check for availability */
			if (avail[k])
			{
				sprintf(out_val, "%c) %s", I2A(k), stats[k]);
				put_str(out_val, 21, k * 9 + 1);
			}
		}

		/* Get a stat */
		while (1)
		{
			put_str("Choose your stat order (= for Options, ? for Help, Q to Quit): ", 20, 2);
			c = inkey();
			if (c == 'Q') quit(NULL);
			j = (islower(c) ? A2I(c) : -1);
			if ((j < A_MAX) && (j >= 0) && (avail[j]))
			{
				stat_order[i] = j;
				c_put_str(TERM_L_BLUE, stats[j], 8 + i, 15);
				avail[j] = 0;
				break;
			}
			else if (c == '=')
			{
				do_cmd_options_birth_call();
			}
			else if (c == '?')
			{
				do_cmd_help_birth();
			}
			else
			{
				bell();
			}
		}
	}

	if (z_ask_menu_aux) z_ask_menu_aux(NULL, NULL, 0, 0);


	clear_from(20);
}


/*
 * Get the name/pass for this character.
 */
void get_char_name(void)
{
	/* Clear screen */
	Term_clear();

	/* Title everything */
	put_str("Name        :", 2, 1);
	put_str("Password    :", 3, 1);

	/* Dump the default name */
	c_put_str(TERM_L_BLUE, nick, 2, 15);


	/* Display some helpful information XXX XXX XXX */

	/* Tool mode -- name/pass are preset; hash exactly like enter_password() */
	if (no_prompt)
	{
		MD5Password(pass);
	}
	else
	{
		/* Choose a name */
		choose_name();

		/* Enter password */
		enter_password();
	}
	
	/* Capitalize the name */
	nick[0] = toupper(nick[0]);

	/* Message */
	put_str("Connecting to server....", 21, 1);

	/* Make sure the message is shown */
	Term_fresh();

	/* Note player birth in the message recall */
	c_message_add(" ", MSG_LOCAL);
	c_message_add("  ", MSG_LOCAL);
	c_message_add("====================", MSG_LOCAL);
	c_message_add("  ", MSG_LOCAL);
	c_message_add(" ", MSG_LOCAL);
}

/*
 * Tool mode -- the character to create, from --birth, as
 * "RACE:CLASS:SEX:STAT,STAT,..." e.g. "Half-Orc:Warrior:m:DEX,STR,CON,WIS,CHR,INT".
 * Names match the server's lists case-insensitively; stats not listed
 * follow in their usual order. Empty means "never create a character".
 */
char tool_birth_spec[160] = "";

static int tool_birth_find(cptr want, int max, cptr (*name_of)(int))
{
	int i;

	for (i = 0; i < max; i++)
	{
		if (!my_stricmp(want, name_of(i))) return i;
	}
	return -1;
}

static cptr tool_race_name(int i) { return p_name + race_info[i].name; }
static cptr tool_class_name(int i) { return c_name + c_info[i].name; }
static cptr tool_stat_name(int i)
{
	/* The server sends e.g. "STR: "; match on the letters only */
	static char buf[16];
	int n = 0;
	cptr s;

	for (s = stat_names[i]; *s && n < (int)sizeof(buf) - 1; s++)
	{
		if (isalpha((unsigned char)*s)) buf[n++] = *s;
	}
	buf[n] = '\0';
	return buf;
}

/*
 * Fill race, pclass, sex and stat_order from tool_birth_spec (instead of
 * get_char_info()'s menus). Needs the race/class/stat lists the server
 * sends with its login reply. Returns NULL on success, else an error.
 */
cptr tool_birth_apply(void)
{
	char buf[160], *f[4], *s, *tok;
	int i, n = 0, used[A_CAP];

	my_strcpy(buf, tool_birth_spec, sizeof(buf));
	for (s = buf; n < 4; n++)
	{
		f[n] = s;
		if (n == 3) break;
		if (!(s = strchr(s, ':'))) return "Birth spec: expected RACE:CLASS:SEX:STATS";
		*s++ = '\0';
	}

	if ((race = tool_birth_find(f[0], z_info.p_max, tool_race_name)) < 0)
		return format("Birth spec: no race '%s' on this server", f[0]);
	if ((pclass = tool_birth_find(f[1], z_info.c_max, tool_class_name)) < 0)
		return format("Birth spec: no class '%s' on this server", f[1]);
	if (!my_stricmp(f[2], "m") || !my_stricmp(f[2], "male")) sex = TRUE;
	else if (!my_stricmp(f[2], "f") || !my_stricmp(f[2], "female")) sex = FALSE;
	else return format("Birth spec: sex must be m or f, not '%s'", f[2]);

	/* Listed stats first, in the given order; the rest after them */
	for (i = 0; i < A_MAX; i++) used[i] = 0;
	n = 0;
	for (tok = strtok(f[3], ","); tok; tok = strtok(NULL, ","))
	{
		i = tool_birth_find(tok, A_MAX, tool_stat_name);
		if (i < 0) return format("Birth spec: no stat '%s'", tok);
		if (used[i]) return format("Birth spec: stat '%s' listed twice", tok);
		used[i] = 1;
		stat_order[n++] = i;
	}
	for (i = 0; i < A_MAX; i++)
	{
		if (!used[i]) stat_order[n++] = i;
	}
	return NULL;
}

/*
 * Get the other info for this character.
 */
void get_char_info(void)
{
	/* Title everything */
	put_str("Sex         :", 4, 1);
	put_str("Race        :", 5, 1);
	put_str("Class       :", 6, 1);
	put_str("Stat order  :", 8, 1);


	/* Clear bottom of screen */
	clear_from(20);

	/* Display some helpful information XXX XXX XXX */

	/* Choose a sex */
	choose_sex();

	/* Choose a race */
	choose_race();

	/* Choose a class */
	choose_class();

	/* Choose stat order */
	choose_stat_order();

	/* Clear */
	clear_from(20);

	/* Message */
	put_str("Entering game...  [Hit any key]", 21, 1);

	/* Wait for key */
	inkey();

	/* Clear */
	clear_from(20);
}

static bool enter_server_name(void)
{
	bool result;
	char *s;

	/* Clear screen */
	Term_clear();

	/* Message */
	prt("Enter the server name you want to connect to (ESCAPE to quit): ", 3, 1);

	/* Move cursor */
	move_cursor(5, 1);

	/* Default */
	strcpy(server_name, "localhost");

	/* Ask for server name */
	result = askfor_aux(server_name, MAX_COLS, 0);

	s = strchr(server_name, ':');
	if (!s) return result;

	sscanf(s, ":%d", &server_port);
	strcpy (s, "\0");

	return result;
}

/*
 * Have the player choose a server from the list given by the
 * metaserver.
 */
bool get_server_name(void)
{
	int i, j, y, srvnum, bytes, offsets[20];
	bool server, info;
	char buf[8192], *ptr, c, out_val[160];
	int ports[30];

	/* Perhaps we already have a server name from config file ? */
	if(strlen(server_name) > 0) return TRUE;

	/* Message */
	prt("Connecting to metaserver for server list....", 1, 1);

	/* Make sure message is shown */
	Term_fresh();

	/* Connect to metaserver */
	buf[0] = '\0';
	bytes = call_metaserver(META_ADDRESS, 8802, buf, 8192);

	/* Some kind of failure */
	if (bytes <= 0)
	{
		return enter_server_name();
	}

	/* Start at the beginning */
	ptr = buf;
	i = y = srvnum  = 0;

	/* Print each server */
	while (ptr - buf < bytes)
	{
		/* Check for no entry */
		if (strlen(ptr) <= 1)
		{
			/* Increment */
			ptr++;

			/* Next */
			continue;
		}
		info = TRUE;
		/* Save server entries */
		if (*ptr == '%')
		{
			server = info = FALSE;

			/* Save port */
			ports[i] = atoi(ptr+1);
		}
		else if (*ptr != ' ')
		{
			server = TRUE;

			/* Save offset */
			offsets[i] = ptr - buf;

			/* Format entry */
			sprintf(out_val, "%c) %s", I2A(i), ptr);
		}
		else
		{
			server = FALSE;

			/* Display notices */
			sprintf(out_val, "%s", ptr);
		}

		if (info) {
			/* Strip off offending characters */
			out_val[strlen(out_val) - 1] = '\0';

			/* Print this entry */
			prt(out_val, y + 1, 1);

			/* One more entry */
			if (server) {
				i++;
				srvnum++;
			}
			y++;
		}

		/* Go to next metaserver entry */
		ptr += strlen(ptr) + 1;

		/* We can't handle more than 20 entries -- BAD */
		if (i > 20) break;
	}

	/* Prompt */
	prt("Choose a server to connect to (Q for manual entry): ", y + 2, 1);

	/* Show onscreen keyboard */
	Term_show_keyboard(0);

	/* Ask until happy */
	while (1)
	{
		/* Get a key */
		c = inkey();

		/* Check for quit */
		if ((c == 'Q') || (c == 'q' && srvnum < 17))
		{
			return enter_server_name();
		}

		/* Index */
		j = (islower(c) ? A2I(c) : -1);

		/* Check for legality */
		if (j >= 0 && j < i)
			break;
	}

	/* Extract server name */
	sscanf(buf + offsets[j], "%s", server_name);

	/* Set port */
	server_port = ports[j+1];

	/* Success */
	return TRUE;
}
