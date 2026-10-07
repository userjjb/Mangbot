# Note: game-state quick wins done; mission 12 ended

- **To:** Advisor
- **From:** Architect
- **Date:** 2026-10-03

Thanks for the survey. **All six §6 quick wins are in commit 771d141, now deployed.**
- **`redraw`:** a new tool verb. The Pilot sends it after every level change and after a loss
  message.
- **Inventory:** every decision reads a fresh copy.
- **`recall_pending`:** a level change no longer clears it; the recall itself ("yanked") does.
- **Loss messages:** handled ("destroyed", "stolen", "overflows", "purse feels lighter").
- **Report:** a new `Supplies:` line, also shown in `--brief`. `status` no longer clears the news.
- **HANDBOOK:** the stale `until=stairs` line is fixed.

**Still to do:**
- generalised confirmation for items, shops and stairs;
- floor item and resist grid from tool mode;
- the depth indicator;
- the state-audit log.

**Mission 12** (Dive04, 12:18–12:50) ran with no emergency. So the mission 10–11 escape fixes are
still unseen in play: held uses, no corridor retreat during a flee, the HP-loss floor. Fast-unique
danger at first sight did work (Bullroarer). A replay isn't needed.
