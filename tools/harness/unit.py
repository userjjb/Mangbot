"""unit -- the harness's U-kind set-pieces: the Pilot's decision code on constructed states, no server.

Restructure step 4 (the Advisor's set-piece memo: U = a unit test on a constructed state). Run after any
Pilot or rulebook change:

    python3 unit.py            # every case; exit status 1 if one fails
    python3 unit.py hunt       # the cases whose name contains "hunt"
    python3 unit.py --golden   # rewrite golden/reports.txt (reports_match_golden), after a report change on purpose

Layout (E8, 2026-11-03): this file is the runner. The cases are in unit_<family>.py (FAMILIES below), the shared
fixtures (W, pilot(), pilot_ast(), the golden report text...) in fixtures.py. A new case goes in its family's file,
decorated @case; ORDER is the order the cases run in (the order they were written in, kept from the single file).
A case not in ORDER runs after the listed ones, in FAMILIES order; a name in ORDER with no case, or two cases of one
name, stop the run.
"""
import importlib
import os
import sys

from fixtures import CASES, GOLDEN_REPORTS, render_reports

FAMILIES = ("unit_hunts", "unit_danger", "unit_status", "unit_levels", "unit_items", "unit_loot",
            "unit_gear", "unit_town", "unit_house", "unit_trips", "unit_orders", "unit_structure")
ORDER = """
    hunt_hill_giant_by_hp disenchant_refused_when_more_than_the_kill hunt_ranger_summoner hunt_qualitative_vetoes hunt_repeat_unique jewellery_unknown_plusses
    bracketed_ego_valued override_debt_counts_the_stack unique_drop_feeling junk_kinds_from_rulebook shop_pay_by_owner town_kit_tiers
    trip_conditions_parse ability_proofs unique_drop_fetched loot_band_stops_looting a5_unseen_caster_news_above_80
    game_clock_from_fuel band_leave_finds_stairs town_kit_townfarms_when_broke crutch_devices_sold_on_test
    pack_full_makes_room c1_valuable_sale_refused c2_unknown_charges c6_ambiguous_names c7_unknown_ring_not_worn
    c9_identify_good_first e1_supply_gate f1_stale_order stairs_beside_mold loot_owed_and_valuables
    provisions_one_food_no_oil refused_stairs_dont_end_explore unseen_drainer_leaves band_condition_only_while_live
    town_makes_room_before_buying emergency_speed_first_berserk_hard_fights fear_cure_order run_loop_walks
    ability_weapon_kept bands_by_expected_cost_weak_drainers_news quiet_level_left
    disenchanter_beside_path_not_fought flee_maps_before_unexplored estimator_memo_rules shadow_estimator_logs
    shadow_snapshot_total_plusses ability_armour_kept town_identifies_scrolls_in_hand rates_gold_found_not_shopping
    gear_review_finds_free_slot speed_potion_over_junk_weapon better_ring_replaces_worn
    gear_line_keeps_ability_armour unique_drop_pushes_out_only_cheap room_eat_never_gorges theft_is_news
    weight_limit_sheds_cheap_heavy_loot flee_at_max_depth_teleports fullest_lantern_worn breeder_swarm_leaves
    hard_fight_shadow_once_per_fight speed_at_hard_fight_start_and_kit xp_per_gold_rolling
    why_explains_the_last_escape prep_report_sections actions_say_who floor_junk_destroyed_when_quiet
    blind_cured_when_it_matters ask_price_and_buy_commas engage_nearby_monster_only_when_appropriate
    trip_clock_condition_across_midnight tavern_stash_and_one_lantern fled_stairs_refused_two_minutes_only
    dive_loots_beside_its_path quiet_wait_finds_a_spot_and_wakes escape_landing_and_trapdoor_notes
    loadout_moves_free_action house_bank_round_trip recall_cures_confusion_first confusion_lock_is_cured
    house_bank_in_the_wilderness house_keeps_the_stash tavern_stash_drops_inside ehp_counts_ac_hp_and_resists
    proxy_counts_resists_by_ehp ehp_gate_and_tie_break plan_town_survives_the_house_tile
    house_walk_stops_at_the_crossing item_commands_wait_for_the_pack trip_dmin_counts_dungeon_minutes
    empty_devices_recharged_or_sold ask_quiet_waits_for_the_answer supply_minutes_and_quiet_cap
    enchant_armour_to_the_stopping_place weapon_enchant_to_the_stopping_place enchant_cap_shared_by_armour_and_weapon
    disenchant_value_by_what_the_pilot_buys town_waits_for_restock flee_replans_after_a_phase
    trip_level_state_survives_restart trip_recalls_when_a_level_wont_let_go mission_label_survives_restart
    gear_items_parsed_from_names gear_model_matches_dive04_sheet gear_evaluator_no_loss_rules
    gear_optimizer_same_loss_rule_as_verdict gear_score_rests_and_paired_error rations_by_need_and_heavy_loot_left
    shadow_agrees_by_the_action_taken structures_on_the_aligned_lattice food_warning_and_trip_rate
    navigator_rules_review_and_nopickup confusion_window_teleports react_hunt_resumes_the_goal
    asleep_flags_from_look_answers breeder_swarm_pin_teleports_once
    blind_escape_uses_the_staff_and_sees_refused_reads ask_limits_lifted_by_the_flag_file
    escape_stairs_flag_ends_with_its_walk flavour_no_more_matches_type review_wear_says_what_happens
    emergency_loop_counts_actions_only emergency_notices_say_if_action autodestroy_spares_kept_items
    trip_until_wor_guard failed_hunt_never_counts_as_slain autodestroy_junk_kinds_without_feelings
    mushrooms_by_expected_value torch_light_is_not_permanent emergency_loop_says_already_fleeing order_all_or_nothing
    oil_by_need_and_fuel_before_destroying architect_role_needs_the_token house_reply_with_and_without_a_house
    pickup_none_no_loot_walks rings_of_damage_and_accuracy junk_one_rule weapon_numbers_by_geareval
    stash_in_house_json_only better_ac_by_geareval supplies_one_kind_with_fields pay_cut_in_shopmath_and_aware
    command_table_methods_exist command_table_fields_valid command_table_help_lists_every_command
    command_table_architect_only_refused reflex_escape_step_lists town_plan_step_tables reports_match_golden
    boldness_fallback_for_heroism satisfy_hunger_a_dungeon_stopgap clw_sold_in_kits_b_and_c
    mushrooms_sold_in_town_but_restores torches_the_lanterns_fallback mapping_scrolls_a_crutch_on_test
    enchant_and_recharge_scrolls_kept_to_read lantern_filled_in_town stomach_pinned_by_hunger_crossings
    stomach_through_the_pilot rations_kept_by_a_pinned_stomach
    stash_backups_for_worn_slots store_list_matches_and_command house_full_overflows_to_the_tavern_then_asks
    stash_records_fresh_and_credited restore_mushrooms_for_drains
    house_reconcile_rebuilds_the_record house_deposit_only_on_a_bare_square house_never_picks_up_the_wrong_item
    finds_marked_with_the_mission_label
    far_fetch_kit_and_valuable_potions backups_must_be_worth_it word_of_recall_three_in_kits_b_and_c
    make_room_news_counts_what_went plan_line_shows_the_trip_end login_level_not_set_by_the_first_dungeon_level stale_bank_record_recovers
    avoid_zone_blocking_the_stairs_asks_the_navigator dive_holds_when_a_zone_blocks_its_stairs
    plan_sent_during_plan_town_is_queued no_food_alert_on_the_crossing_tick
    refused_drops_end_the_stash_step a_permanent_light_beats_the_lantern
    dive_walks_to_stairs_past_unexplored_squares
    unknowns_identified_before_sale
    felt_good_gear_identified_average_sold
""".split()


def _in_order():
    for m in FAMILIES:
        importlib.import_module(m)
    names = [f.__name__ for f in CASES]
    twice = sorted({n for n in names if names.count(n) > 1})
    missing = [n for n in ORDER if n not in names]
    if twice or missing:
        sys.exit(f"unit.py: cases defined twice: {twice or 'none'}; in ORDER with no case: {missing or 'none'}")
    rank = {n: i for i, n in enumerate(ORDER)}
    CASES.sort(key=lambda f: rank.get(f.__name__, len(ORDER)))


_in_order()


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    if want == "--golden":                             # (reports_match_golden: the report text changed on purpose)
        os.makedirs(os.path.dirname(GOLDEN_REPORTS), exist_ok=True)
        text = render_reports()
        open(GOLDEN_REPORTS, "w").write(text)
        print(f"wrote {GOLDEN_REPORTS}: {text.count(chr(10))} lines")
        return
    fails = ran = 0
    for f in CASES:
        if want and want not in f.__name__:
            continue
        ran += 1
        try:
            ok, detail = f()
        except Exception as e:
            ok, detail = False, f"error {e!r}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {f.__name__}: {detail}")
    print(f"{ran - fails} passed, {fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
