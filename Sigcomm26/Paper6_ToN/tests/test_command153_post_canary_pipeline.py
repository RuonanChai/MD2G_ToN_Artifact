#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""H2 must precede FINAL_DEV freeze; 945 queue denominator stays 945."""
import ast
import json
import unittest
from pathlib import Path

TON = ton_root()


class TestCommand153PostCanaryPipeline(unittest.TestCase):
    def test_continue_runs_h2_before_scaling_and_freeze(self):
        txt = (TON / "scripts" / "command153_continue.py").read_text()
        self.assertIn("h2_cross_stack_dash_required_before_final_dev_freeze", txt)
        self.assertIn("def _fail_closed", txt)
        self.assertIn("loot_incomplete", txt)
        self.assertIn("scaling_incomplete", txt)
        ev = (TON / "scripts" / "command153_evidence.py").read_text()
        self.assertIn("evidence_incomplete", ev)
        idx = ev.find("reason\": \"evidence_incomplete")
        self.assertGreater(idx, 0)
        self.assertIn("COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED", ev[idx : idx + 1200])
        self.assertIn("mixed_epoch_in_canonical_rows", ev)
        self.assertIn("COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE", ev)
        cell = (TON / "scripts" / "command148_canary_cell.py").read_text()
        self.assertIn('rec["epoch_id"]', cell)
        main = txt.split("def main() -> int:", 1)[1]
        self.assertLess(main.find("COMMAND153_CROSS_STACK_DASH_COMPLETE"), main.find("COMMAND153_SCALING_COMPLETE"))
        self.assertLess(main.find("COMMAND153_SCALING_COMPLETE"), main.find("step_final_dev_freeze"))
        self.assertIn("command153_cross_stack_dash.py", main)

    def test_dash_matrix_is_predeclared_48(self):
        import sys

        sys.path.insert(0, str(TON / "scripts"))
        from command153_cross_stack_dash import matrix  # noqa: E402

        rows = matrix()
        self.assertEqual(len(rows), 48)
        self.assertTrue(all("loot" not in r["key"] for r in rows))
        self.assertTrue(all(r["seed"] in (151, 152) for r in rows))
        frozen = json.loads(
            (TON.parents[1] / "state" / "COMMAND153_CROSS_STACK_DASH_MANIFEST.json").read_text()
        )
        self.assertEqual(list(frozen.get("keys") or []), [r["key"] for r in rows])
        self.assertEqual(int(frozen.get("n") or 0), 48)

    def test_main_dev_queue_n_is_945(self):
        txt = (TON / "scripts" / "command148_main_dev.py").read_text()
        self.assertIn('q["n"] = 945', txt)
        self.assertIn('env["COMMAND148_QUEUE_N"] = "945"', txt)
        self.assertIn("assert len(rows) == 945", txt)

    def test_injected_cell_does_not_rerun_v1_gate(self):
        tree = ast.parse((TON / "scripts" / "command148_canary_cell.py").read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_main_injected")
        src = ast.get_source_segment((TON / "scripts" / "command148_canary_cell.py").read_text(), fn)
        self.assertIn("do_five_report=False", src)

    def test_injected_cell_does_not_clobber_canary_fail_closed(self):
        txt = (TON / "scripts" / "command148_canary_cell.py").read_text()
        self.assertIn("COMMAND153_INJECTED_FAIL_CLOSED.json", txt)
        self.assertIn("command153_dev_reports.py", txt)

    def test_evidence_requires_full_canonical_n(self):
        txt = (TON / "scripts" / "command153_evidence.py").read_text()
        self.assertIn("len(loot) < 315", txt)
        self.assertIn("len(dev) < 945", txt)
        self.assertIn("len(canary) < 120", txt)
        self.assertIn("len(scaling) < 150", txt)
        self.assertIn("COMMAND153_CROSS_STACK_DASH_COMPLETE", txt)
        self.assertIn("COMMAND153_LOOT_HOLDOUT_FROZEN", txt)
        self.assertIn("command153_continue.py", txt)
        self.assertIn("command153_cross_stack_dash.py", txt)
        self.assertIn("command148_main_dev.py", txt)
        self.assertIn("COMMAND153_KNOWN_FAILURES_AND_FIXES.md", txt)
        self.assertIn("COMMAND148_CANARY120_QUEUE.json", txt)
        self.assertIn("COMMAND148_MAINDEV_QUEUE.json", txt)
        self.assertIn("COMMAND153_LOOT_QUEUE.json", txt)
        self.assertIn("_load_rows_for_keys", txt)
        self.assertIn("COMMAND153_CROSS_STACK_DASH_STATS.json", txt)
        self.assertIn("COMMAND153_CROSS_STACK_DASH_QUEUE.json", txt)
        self.assertIn("not_experimental_validation_for_na", txt)
        self.assertIn("not_150_new_executions", txt)
        self.assertIn("NOT_APPLICABLE_NOT_VALIDATION", txt)
        self.assertIn("COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json", txt)
        self.assertIn("a0_reuse_dev_md2g_n", txt)
        self.assertIn("a6_reuse_dev_rule_n", txt)

    def test_scaling_matrix_is_150_with_90_reuse_60_new(self):
        import sys

        sys.path.insert(0, str(TON / "scripts"))
        from command153_continue import scaling_matrix  # noqa: E402

        rows = scaling_matrix()
        self.assertEqual(len(rows), 150)
        reuse = [r for r in rows if r["users"] in (20, 60, 100)]
        new = [r for r in rows if r["users"] in (10, 40)]
        self.assertEqual(len(reuse), 90)
        self.assertEqual(len(new), 60)
        self.assertTrue(all(r["content"] == "redandblack" for r in rows))
        self.assertTrue(all(r["network"] in ("default_mix", "wifi_dominant") for r in rows))

    def test_v1_gate_writes_canary120_complete(self):
        txt = (TON / "scripts" / "command148_canary_v1_gate.py").read_text()
        self.assertIn("COMMAND148_CANARY120_COMPLETE.json", txt)
        self.assertLess(txt.find("canary_n_lt_120"), txt.find("COMMAND148_CANARY120_COMPLETE.json"))

    def test_freeze_requires_945_h2_scaling_counts(self):
        txt = (TON / "scripts" / "command153_continue.py").read_text()
        self.assertIn("counts[\"maindev\"] < 945", txt)
        self.assertIn("counts[\"h2\"] < 48", txt)
        self.assertIn("counts[\"scaling\"] < 150", txt)
        self.assertIn("loot_sealed_until_final_dev_frozen", txt)
        self.assertIn("def _fail_closed", txt)
        self.assertIn('_fail_closed("loot_sealed_until_final_dev_frozen")', txt)
        self.assertIn("dash_live", txt)
        self.assertIn("any(k not in done for k in expected)", txt)
        h2 = (TON / "scripts" / "command153_cross_stack_dash.py").read_text()
        complete = h2.split("if pending is None:", 1)[1].split("if pending[\"content\"]", 1)[0]
        self.assertIn("COMMAND153_CROSS_STACK_DASH_COMPLETE.json", complete)
        self.assertNotIn("h2_incomplete", complete)

    def test_e027_sentinel_rerun_before_final_dev(self):
        cont = (TON / "scripts" / "command153_continue.py").read_text()
        self.assertIn("def step_sentinel_rerun", cont)
        self.assertIn("COMMAND153_SENTINEL_RERUN_REQUIRED", cont)
        self.assertIn("COMMAND153_SENTINEL_RERUN_COMPLETE", cont)
        main = cont.split("def main()", 1)[1]
        self.assertLess(main.find("step_overhead()"), main.find("step_sentinel_rerun()"))
        self.assertLess(main.find("step_sentinel_rerun()"), main.find("step_final_dev_freeze()"))
        freeze = cont.split("def step_final_dev_freeze", 1)[1].split("def step_loot", 1)[0]
        self.assertIn("COMMAND153_SENTINEL_RERUN_COMPLETE", freeze)
        md = (TON / "scripts" / "command148_main_dev.py").read_text()
        self.assertIn("sentinel_keys()", md)
        led = (TON / "scripts" / "command153_ledger.py").read_text()
        self.assertIn("E027_SENTINEL_REUSE_WITHOUT_RAW_DUMPS", led)

    def test_cluster_unseals_holdout_only_after_final_dev_frozen(self):
        cluster = Path("str(artifact_root())/moq_cluster_Sigcomm.py")
        txt = cluster.read_text()
        fn = txt.split("def _apply_nested_component_video_paths", 1)[1].split("\n\n", 1)[0]
        self.assertIn("COMMAND153_FINAL_DEV_FROZEN.json", fn)
        self.assertIn("Loot network holdout sealed", fn)
        self.assertIn("if not _frozen.is_file()", fn)
        self.assertFalse(
            Path("str(artifact_root())/state/COMMAND153_FINAL_DEV_FROZEN.json").is_file()
        )
        client = (TON / "lib" / "command147_nested_client.py").read_text()
        self.assertIn("COMMAND153_FINAL_DEV_FROZEN.json", client)
        ev = (TON / "scripts" / "command153_evidence.py").read_text()
        self.assertIn("moq_cluster_Sigcomm.py", ev.split("HASH_FILES", 1)[1].split("def exists", 1)[0])
        tracks = Path("str(artifact_root())/media/ton_nested_components_v1")
        for content in ("redandblack", "longdress", "soldier"):
            for n in ("b0", "db1", "db2", "e1", "e2"):
                self.assertTrue((tracks / content / "tracks" / n / "120s.mp4").is_file())
        holdout = tracks / "loot"
        for n in ("b0", "db1", "db2", "e1", "e2"):
            self.assertTrue((holdout / "tracks" / n / "120s.mp4").is_file())

    def test_h2_fail_closed_if_dash_media_init_missing(self):
        txt = (TON / "scripts" / "command153_cross_stack_dash.py").read_text()
        self.assertIn("dash_media_init_missing", txt)
        self.assertIn("COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED", txt)
        self.assertIn("rep1_init.mp4", txt)
        self.assertIn("h2_loot_key_before_final_dev_frozen", txt)
        from pathlib import Path as P

        root = P("str(artifact_root())/media/ton_dash_reference_ladder_v1")
        for content in ("redandblack", "longdress"):
            self.assertTrue((root / content / "dash_live" / "dash" / "rep1" / "rep1_init.mp4").is_file())

    def test_h2_manifest_does_not_rewrite_after_freeze(self):
        txt = (TON / "scripts" / "command153_cross_stack_dash.py").read_text()
        fn = txt.split("def write_manifest()", 1)[1].split("def score_cell", 1)[0]
        self.assertIn("COMMAND153_CROSS_STACK_DASH_MANIFEST.json", fn)
        self.assertIn("CROSS_STACK_DASH_MANIFEST.json", fn)
        self.assertIn("if not existing_p.is_file()", fn)
        self.assertIn('int(prev.get("n") or 0) != 48', fn)
        self.assertIn("h2_matrix_diverged_from_frozen_manifest", fn)
        self.assertLess(fn.find("return prev"), fn.find("dump_dual"))
        main = txt.split("def main()", 1)[1]
        self.assertLess(main.find("main_dev_incomplete"), main.find("man = write_manifest()"))

    def test_h2_validity_uses_unicast_gate_not_nested_score(self):
        txt = (TON / "scripts" / "command153_cross_stack_dash.py").read_text()
        fn = txt.split("def main()", 1)[1]
        self.assertIn('valid_cell and proof.get("independent_http_sessions")', fn)
        self.assertIn("physical_pressure_samples", fn)
        self.assertIn("n_press >= 2", fn)
        self.assertNotIn("and sc.get(\"ok\")", fn)
        launch = (TON / "scripts" / "command153_continue.py").read_text()
        self.assertIn('env["COMMAND148_QUEUE_N"] = str(n)', launch)
        dash = (TON.parents[1] / "DASH" / "rolling_dash_experiment.py").read_text()
        self.assertIn("def _start_command151_pressure", dash)
        self.assertIn("PHYSICAL_PRESSURE_TIMESERIES.jsonl", dash)
        self.assertIn("r0.popen", dash)
        self.assertNotIn("r0.cmd(\"cat /sys/class/net/r0-eth1", dash)
        clf = (TON / "scripts" / "command153_classify_and_repair.py").read_text()
        self.assertIn("E021_DASH_H2_MISSING_COMMAND151_PRESSURE", clf)
        led = (TON / "scripts" / "command153_ledger.py").read_text()
        self.assertIn("E021_DASH_H2_MISSING_COMMAND151_PRESSURE", led)
        self.assertIn("E022_EXACT_KEY_REAUTHORIZE_INFINITE_RETRY", led)

    def test_h2_takes_scientific_executor_lock(self):
        txt = (TON / "scripts" / "command153_cross_stack_dash.py").read_text()
        self.assertIn("try_acquire", txt)
        self.assertIn("command152_owns_launches", txt)
        fn = txt.split("def main()", 1)[1]
        self.assertIn("executor_lock_held", fn)
        self.assertIn("release(lock_fd)", fn)
        self.assertLess(fn.find("lock_fd = try_acquire"), fn.find("proc = subprocess.run"))
        cont = (TON / "scripts" / "command153_continue.py").read_text()
        main = cont.split("def main() -> int:", 1)[1]
        self.assertIn('env["COMMAND152_LAUNCH"]', main)
        self.assertIn("command153_cross_stack_dash.py", main)
        txt = (TON / "scripts" / "command153_cross_stack_dash.py").read_text()
        self.assertIn("exact_key_authorized", txt)
        self.assertIn("h2_fail_closed", txt)
        self.assertIn("n_try >= 3 and auth is None", txt)
        self.assertNotIn("n_try >= 3 or auth is None", txt)
        self.assertIn("PHYSICAL_PRESSURE_TIMESERIES.jsonl", fn)
        self.assertIn("h2_proc_unbound", fn)
        self.assertIn("COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED", txt)
        self.assertIn("h2_fail_closed", txt)
        self.assertIn("dash_live", txt)
        clf = (TON / "scripts" / "command153_classify_and_repair.py").read_text()
        self.assertIn("COMMAND153_CROSS_STACK_DASH_QUEUE.json", clf)
        self.assertIn("exact_key_already_consumed", clf)
        self.assertIn("_already_consumed_exact_key", clf)

    def test_main_dev_complete_requires_945(self):
        txt = (TON / "scripts" / "command148_main_dev.py").read_text()
        self.assertIn("maindev_incomplete", txt)
        self.assertIn('"expected": 945', txt)
        self.assertIn("any(k not in done for k in expected)", txt)
        self.assertIn("COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED", txt)
        self.assertIn("maindev_fail_closed", txt)
        self.assertIn("n_try >= 3 and auth is None", txt)

    def test_supervisor_classifies_maindev_fail_before_retry(self):
        txt = (TON / "scripts" / "command152_production_supervisor.py").read_text()
        self.assertIn("LEDGER_CONSULT_BEFORE_MAINDEV_REPAIR", txt)
        self.assertIn("COMMAND148_MAINDEV_QUEUE.json", txt)
        block = txt.split("COMMAND148_MAIN_DEV_CELL", 1)[1].split("if exists(\"COMMAND148_MAINDEV_COMPLETE\")", 1)[0]
        self.assertIn("command153_classify_and_repair.py", block)
        self.assertIn("dash_live", block)

    def test_overhead_reads_rbv1_and_maindev_sidecars(self):
        txt = (TON / "scripts" / "command153_continue.py").read_text()
        oh = txt.split("def step_overhead()", 1)[1].split("def step_final_dev_freeze()", 1)[0]
        self.assertIn("command148_canary120_rbv1", oh)
        self.assertIn("DEV_ART", oh)
        self.assertIn("student_infer_ms_n_maindev", oh)
        self.assertIn("_student_infer_ms", txt)

    def test_canary_cell_waits_for_dash_or_moq_live(self):
        txt = (TON / "scripts" / "command148_canary_cell.py").read_text()
        self.assertIn("dash_live", txt)
        self.assertIn("executor_already_live", txt)
        self.assertIn("unsupervised_live_after_lock_dead", txt)
        self.assertIn("handle_unsupervised_live_wait", txt)
        md = (TON / "scripts" / "command148_main_dev.py").read_text()
        self.assertIn('env["COMMAND152_LAUNCH"]', md.split("COMMAND148_MAINDEV_COMPLETE.json", 1)[1])
        cont = (TON / "scripts" / "command153_continue.py").read_text()
        self.assertIn("unsupervised_live_grace", cont)
        self.assertIn("unsupervised_live_after_lock_dead", cont)
        self.assertIn("kill_live_cell", cont)
        h2 = (TON / "scripts" / "command153_cross_stack_dash.py").read_text()
        self.assertIn("handle_unsupervised_live_wait", h2)
        io = (TON / "lib" / "command147_io.py").read_text()
        self.assertIn("stale_s: float = 180.0", io)
        self.assertIn("unsupervised_live_after_lock_dead", io)
        proc = (TON / "scripts" / "command137_proc.py").read_text()
        self.assertIn("def unsupervised_live", proc)
        self.assertIn("def scientific_lock_pid_alive", proc)

    def test_scaling_reuses_validity_sidecar(self):
        txt = (TON / "scripts" / "command153_continue.py").read_text()
        self.assertIn("CELL_VALIDITY.json", txt)
        scale = txt.split("def step_scaling()", 1)[1].split("ABLATION_VARIANTS", 1)[0]
        self.assertIn("CELL_VALIDITY.json", scale)

    def test_ablation_manifest_freeze_once_before_complete(self):
        txt = (TON / "scripts" / "command153_continue.py").read_text()
        self.assertIn("def write_ablation_manifest()", txt)
        self.assertIn("frozen_before_first_ablation_result", txt)
        fn = txt.split("def write_ablation_manifest()", 1)[1].split("def write_fov_not_applicable()", 1)[0]
        self.assertIn("if existing_p.is_file()", fn)
        self.assertLess(fn.find("return prev"), fn.find("dump_dual"))
        step = txt.split("def step_ablation_manifest()", 1)[1].split("def step_fov()", 1)[0]
        self.assertIn("write_ablation_manifest()", step)
        self.assertIn("COMMAND153_ABLATION_COMPLETE.json", step)
        self.assertIn("ablation_dev_reuse_incomplete", step)
        self.assertIn("_dev_strategy_keys", txt)
        self.assertIn("a0_reuse_dev_md2g_n", step)
        self.assertIn("a6_reuse_dev_rule_n", step)
        main = txt.split("def main() -> int:", 1)[1]
        self.assertIn("COMMAND153_ABLATION_COMPLETE", main)
        self.assertNotIn('if not exists("COMMAND153_ABLATION_MANIFEST")', main)
        self.assertIn("def write_fov_not_applicable()", txt)
        fov = txt.split("def write_fov_not_applicable()", 1)[1].split("def step_ablation_manifest()", 1)[0]
        self.assertIn("if existing_p.is_file()", fov)
        self.assertLess(fov.find("return prev"), fov.find("dump_dual"))

    def test_frozen_ablation_manifest_has_na_majority(self):
        man_p = Path("str(artifact_root())/state/COMMAND153_ABLATION_MANIFEST.json")
        self.assertTrue(man_p.is_file())
        man = json.loads(man_p.read_text())
        variants = man["variants"]
        self.assertEqual(variants["A0_full"]["status"], "APPLICABLE_REUSE_DEV_MD2G")
        self.assertEqual(variants["A6_rule_only"]["status"], "APPLICABLE_REUSE_DEV_RULE")
        na = [k for k, v in variants.items() if v.get("status") == "NOT_APPLICABLE"]
        self.assertEqual(sorted(na), ["A1_no_fov_group_overlap", "A2_no_device", "A3_no_component_headroom", "A4_no_completion_playability", "A5_fixed_grouping", "A7_naive_cumulative_cost"])
        self.assertTrue(man.get("frozen_before_first_ablation_result"))
        self.assertFalse((Path("str(artifact_root())/state/COMMAND153_ABLATION_COMPLETE.json")).is_file())
        fov_p = Path("str(artifact_root())/state/COMMAND153_FOV_NOT_APPLICABLE.json")
        self.assertTrue(fov_p.is_file())
        self.assertFalse((Path("str(artifact_root())/state/COMMAND153_FOV_COMPLETE.json")).is_file())


if __name__ == "__main__":
    unittest.main()
