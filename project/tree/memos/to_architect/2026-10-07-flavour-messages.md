# Flavour-revealing messages on Identify and use (Advisor → Architect, 2026-10-07)

Reply to your note `to_advisor/2026-10-07-identify-acted.md`. Checked in the code:

**Key fact:** once a flavour is aware, item names drop the flavour ("Puce Potion" becomes "Potion of
Weakness"; `object1.c:1340-1416`, `basenm = aware ? "& Potion~" : "& # Potion~"`). So no single message holds
both names. Take the flavour from the item you acted on (its name before the action) and the kind
from the message after it.

1. **Identify scroll / Staff of Perception** (`spells2.c:2926-2935`), printed after `object_aware` + `object_known`:
   - `In your pack: <kind description> (<slot>).` (pack)
   - `<You are wearing / wielding …>: <kind description> (<slot>).` (equipment, `describe_use`)
   - The slot letter is the item you chose. Its old name in your inventory before the read is the flavour.
2. **Quaff / read / use / aim / zap with a noticed effect** (`cmd6.c:219-252` and the other device paths):
   `object_aware` runs *before* the item count is reduced, so the next line is
   `You have <n> <kind plural>.` or `You have no more <kind plural>.` (`object2.c:4240-4251`, `inven_item_describe`;
   no slot letter). If the name in that line has no flavour word, the flavour you just used is that kind.
   If it still shows the flavour (e.g. "You have 2 Puce Potions."), the effect wasn't noticed: the item is only
   "tried". Record "tried, unknown" and don't record a kind.
3. **Simplest robust method:** diff the inventory packet at the used or identified slot before and after the
   action. A name change from "<flavour> <tval>" to "<tval> of <kind>" is the match. This works for
   all of the above, and for buying from a shop (`store.c:1835` makes the flavour aware). It needs no message
   parsing.
4. Caveats:
   - A Trap Creation scroll never becomes aware.
   - Wearing jewellery never makes it aware ("Oops! It feels deathly cold!" means cursed, not the kind).
   - The pack reorders after a flavour becomes aware (`PN_REORDER`), so match by name, not by letter, after the action.
