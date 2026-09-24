"""Unit tests for generate_gate_explanation() — all decision branches covered."""
import pytest
from tradingos.core.nlp import generate_gate_explanation, generate_signal_text


# ── Helpers ───────────────────────────────────────────────────────────────────

def _base_kwargs(**overrides):
    """Return a minimal valid kwarg dict, with overrides applied."""
    defaults = dict(
        ticker="TST",
        action="WATCH",
        mfpm_score=60,
        mode_a_score=35,
        mode_b_score=20,
        mode_w_score=55,
        signal_mode="MODE_A",
        mc_prob=0.45,
        distribution_warning="NONE",
        amf_decision="PASS",
        hmm_state="TRENDING_UP",
        amd_phase="ACCUMULATION",
        rsi14=52.0,
        sms_raw=40,
        mcvd_trend="UP",
        stealth_accum=False,
        pt_net_5d=0.0,
        close=58.5,
        mode_w_conditions_failed=None,
    )
    defaults.update(overrides)
    return defaults


# ── Gate 0: Distribution warning overrides everything ─────────────────────────

class TestDistributionOverride:
    def test_exit_mentions_override(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="EXIT",
            mfpm_score=75,
            mc_prob=0.70,
            distribution_warning="EXIT",
        ))
        assert "override" in text.lower() or "phân phối" in text.lower()
        # Gate analysis sections must NOT appear (returned early)
        assert "Mode A" not in text and "Mode B" not in text and "W-Score" not in text

    def test_forced_exit_mentions_severity(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="FORCED_EXIT",
            distribution_warning="FORCED_EXIT",
        ))
        assert "FORCED_EXIT" in text or "MẠNH" in text

    def test_exit_returns_early_no_gate_lines(self):
        """When dist_warning is EXIT, gate 1+ lines should NOT appear."""
        text = generate_gate_explanation(**_base_kwargs(
            action="EXIT",
            distribution_warning="EXIT",
        ))
        # AMF gate and mode-specific analysis lines must be absent
        assert "AMF = PASS" not in text
        assert "Mode A" not in text and "Mode B" not in text and "W-Score" not in text


# ── Gate 1: AMF BLOCK ─────────────────────────────────────────────────────────

class TestAMFBlock:
    def test_amf_block_mentioned(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="NO_ACTION",
            amf_decision="BLOCK",
        ))
        assert "BLOCK" in text or "thao túng" in text.lower()

    def test_amf_block_upgrade_hint_not_about_mfpm(self):
        """AMF block path should not give MFPM upgrade hint."""
        text = generate_gate_explanation(**_base_kwargs(
            action="NO_ACTION",
            amf_decision="BLOCK",
        ))
        # Should not suggest "MFPM cần thêm X điểm"
        assert "MFPM cần thêm" not in text

    def test_amf_block_returns_early(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="NO_ACTION",
            amf_decision="BLOCK",
        ))
        assert "Mode A" not in text and "Mode B" not in text and "Mode W" not in text


# ── Mode W path ───────────────────────────────────────────────────────────────

class TestModeW:
    def test_strong_buy_all_checks_passed(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="STRONG_BUY",
            signal_mode="MODE_W",
            mode_w_score=98,
            mc_prob=0.65,
            amf_decision="PASS",
        ))
        assert "STRONG_BUY" in text
        assert "✅" in text

    def test_buy_w_above_80(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="BUY",
            signal_mode="MODE_W",
            mode_w_score=85,
            mc_prob=0.57,
        ))
        assert "BUY" in text
        assert "85" in text

    def test_watch_shows_w_score_gap(self):
        """WATCH on Mode W: should show W score vs BUY threshold."""
        text = generate_gate_explanation(**_base_kwargs(
            action="WATCH",
            signal_mode="MODE_W",
            mode_w_score=65,  # ≥60 (watch) but <80 (buy)
            mc_prob=0.48,
        ))
        assert "65" in text
        assert "80" in text or "BUY" in text

    def test_no_action_mode_w_below_watch(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="NO_ACTION",
            signal_mode="MODE_W",
            mode_w_score=45,  # <60
            mc_prob=0.40,
        ))
        assert "60" in text  # minimum watch threshold shown
        assert "NO" in text.upper() or "chưa đạt" in text.lower()

    def test_w_fail_conditions_shown(self):
        fails = ["W-2: SMS raw < 60", "W-5: HMM not BULL"]
        text = generate_gate_explanation(**_base_kwargs(
            action="WATCH",
            signal_mode="MODE_W",
            mode_w_score=62,
            mc_prob=0.50,
            mode_w_conditions_failed=fails,
        ))
        assert "W-2" in text
        assert "W-5" in text

    def test_upgrade_hint_for_watch_mode_w(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="WATCH",
            signal_mode="MODE_W",
            mode_w_score=70,   # 80-70=10 points needed
            mc_prob=0.50,
        ))
        assert "10" in text or "BUY" in text

    def test_upgrade_hint_for_buy_mode_w(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="BUY",
            signal_mode="MODE_W",
            mode_w_score=88,   # 95-88=7 points needed
            mc_prob=0.58,
        ))
        assert "STRONG_BUY" in text


# ── Mode A / B path ───────────────────────────────────────────────────────────

class TestModeAB:
    """
    Gate logic (mirrors mfpm.py):
      BUY:   MFPM ≥ 70 AND AMF=PASS AND MC ≥ 55%
      WATCH: MFPM ≥ 50
      else:  NO_ACTION
    """

    def test_watch_mfpm_below_70_shown(self):
        """TN1-like: MFPM=75 but MC=19% < 55% → WATCH."""
        text = generate_gate_explanation(**_base_kwargs(
            ticker="TN1",
            action="WATCH",
            signal_mode="MODE_A",
            mfpm_score=75,
            mc_prob=0.19,
        ))
        assert "19%" in text or "0.19" in text or "19" in text.replace(",", ".")
        assert "55%" in text or "0.55" in text

    def test_watch_mfpm_exactly_below_buy(self):
        """GLT-like: MFPM=60 → WATCH — shows exactly 10 points to BUY."""
        text = generate_gate_explanation(**_base_kwargs(
            ticker="GLT",
            action="WATCH",
            signal_mode="MODE_A",
            mfpm_score=60,
            mc_prob=0.45,
        ))
        assert "10" in text  # 70-60=10

    def test_bottleneck_identified_as_mc_when_mfpm_and_amf_pass(self):
        """All Mode A gates except MC: bottleneck message about MC."""
        text = generate_gate_explanation(**_base_kwargs(
            action="WATCH",
            signal_mode="MODE_A",
            mfpm_score=75,
            amf_decision="PASS",
            mc_prob=0.40,
        ))
        assert "Bottleneck" in text or "bottleneck" in text or "MC" in text
        assert "55%" in text

    def test_buy_mode_a_all_gates_pass(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="BUY",
            signal_mode="MODE_A",
            mfpm_score=75,
            amf_decision="PASS",
            mc_prob=0.60,
        ))
        assert "✅" in text
        assert "BUY" in text

    def test_buy_mode_b_all_gates_pass(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="BUY",
            signal_mode="MODE_B",
            mfpm_score=72,
            amf_decision="PASS",
            mc_prob=0.57,
        ))
        assert "Mode B" in text
        assert "✅" in text

    def test_no_action_mfpm_below_watch(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="NO_ACTION",
            signal_mode="MODE_A",
            mfpm_score=40,
            mc_prob=0.30,
        ))
        assert "50" in text  # minimum watch threshold
        assert "chưa đạt" in text.lower() or "40" in text

    def test_upgrade_hint_buy_to_strong_buy(self):
        text = generate_gate_explanation(**_base_kwargs(
            action="BUY",
            signal_mode="MODE_A",
            mfpm_score=78,
            amf_decision="PASS",
            mc_prob=0.60,
        ))
        # Mode A BUY: hint says already strong
        assert "BUY" in text

    def test_upgrade_hint_watch_lists_bottlenecks(self):
        """WATCH with MFPM=60 and MC=0.40: both shown in upgrade hint."""
        text = generate_gate_explanation(**_base_kwargs(
            action="WATCH",
            signal_mode="MODE_A",
            mfpm_score=60,
            amf_decision="PASS",
            mc_prob=0.40,
        ))
        assert "BUY" in text  # upgrade hint mentions BUY
        # Either MFPM gap or MC gap should appear
        assert "10" in text or "55%" in text


# ── Distribution non-exit (NONE, WATCH, CAUTION) ─────────────────────────────

class TestDistributionNonExit:
    def test_none_does_not_trigger_override(self):
        """dist_warning=NONE: should NOT mention override."""
        text = generate_gate_explanation(**_base_kwargs(
            action="WATCH",
            distribution_warning="NONE",
        ))
        assert "override" not in text.lower()

    def test_caution_does_not_override(self):
        """dist_warning=CAUTION: gate logic still runs normally."""
        text = generate_gate_explanation(**_base_kwargs(
            action="WATCH",
            distribution_warning="CAUTION",
            mfpm_score=60,
            amf_decision="PASS",
            mc_prob=0.40,
        ))
        assert "Mode A" in text  # normal gate path ran


# ── SAF scenario: EXIT overrides MFPM=65 ─────────────────────────────────────

class TestSAFScenario:
    def test_saf_exit_overrides_watch_mfpm(self):
        """SAF: MFPM=65 would be WATCH but dist=EXIT → EXIT, explanation shows override."""
        text = generate_gate_explanation(**_base_kwargs(
            ticker="SAF",
            action="EXIT",
            mfpm_score=65,
            mc_prob=0.52,
            distribution_warning="EXIT",
        ))
        assert "override" in text.lower() or "phân phối" in text.lower()
        # Gate analysis (Mode A/B/W analysis) must NOT appear — returned early
        assert "Mode A" not in text and "Mode B" not in text and "W-Score" not in text


# ── generate_signal_text integration ─────────────────────────────────────────

class TestSignalTextIntegration:
    """Verify gate explanation block appears inside generate_signal_text output."""

    def _sig_kwargs(self, **overrides):
        defaults = dict(
            ticker="VCB",
            action="BUY",
            confidence="HIGH",
            mfpm_score=78,
            mode_w_score=55,
            sms_raw=60,
            hmm_state="STEADY_BULL",
            signal_mode="MODE_A",
            entry=58.1,
            sl=56.1,
            tp1=63.4,
            tp2=67.0,
            rr=2.65,
            mc_prob=0.62,
            distribution_warning="NONE",
            mode_a_score=45,
            mode_b_score=28,
            amf_decision="PASS",
            stealth_accum=False,
            mcvd_trend="UP",
            mcvd_5d=50000.0,
            rsi14=54.0,
            close=58.5,
        )
        defaults.update(overrides)
        return defaults

    def test_gate_section_present_for_buy(self):
        text = generate_signal_text(**self._sig_kwargs())
        assert "Tại sao lại là **BUY**" in text

    def test_gate_section_present_for_watch(self):
        text = generate_signal_text(**self._sig_kwargs(
            action="WATCH",
            mfpm_score=62,
            mc_prob=0.42,
            confidence="MEDIUM",
        ))
        assert "Tại sao lại là **WATCH**" in text

    def test_gate_section_present_for_exit(self):
        text = generate_signal_text(**self._sig_kwargs(
            action="EXIT",
            distribution_warning="EXIT",
            confidence="—",
        ))
        assert "Tại sao lại là **EXIT**" in text

    def test_no_double_heading(self):
        """Section header should appear exactly once."""
        text = generate_signal_text(**self._sig_kwargs())
        assert text.count("Tại sao lại là") == 1
