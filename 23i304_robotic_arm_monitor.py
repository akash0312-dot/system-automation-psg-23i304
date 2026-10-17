"""
23IF02 System Automation - Bonus Challenge
Robotic Arm Joint Health Monitoring System   (SINGLE-FILE VERSION)

RUN:   pip install numpy pandas scikit-learn
       python robotic_arm_monitor.py

On first run it creates historical_joint_data.csv (150 labelled synthetic
readings) and maintenance_log.txt (12 entries) next to this file, then runs
the full pipeline and prints one example for each of the four decisions.

PIPELINE
  1. Hard safety check  (plain if-limits, never uses ML)      -> EMERGENCY_STOP
  2. Spoofed-torque check (flatline / replay / step / cross-sensor)
  3. ML wear model + technician-notes keyword scan
  4. Combine into SAFE / MONITOR / SCHEDULE_MAINTENANCE / EMERGENCY_STOP

WRITTEN EXPLANATION
  Safety thresholds: torque > 130 % of rated (drive peak rating), temperature
  > 95 C, vibration > 11 mm/s RMS (ISO 10816 damage zone). The worst *failing*
  joint in my data reached only 100 % torque / 85 C / 8.8 mm/s, so the limits
  sit above anything seen before an ordinary failure; the ML model handles
  everything below them. Every single sample is checked, and missing/NaN
  readings also trigger a stop (fail-safe).

  Combining model + log: wear probability -> LOW <0.30, MED <0.60, HIGH.
  Notes -> NONE / MINOR / SEVERE (severe words 3 pts, minor 1 pt; negations
  and notes older than 14 days ignored). HIGH+SEVERE = EMERGENCY_STOP; one
  strong signal = SCHEDULE_MAINTENANCE; one weak signal = MONITOR; two weak =
  SCHEDULE_MAINTENANCE; none = SAFE. Model down -> SAFE is downgraded to MONITOR.

  Spoof defence: flatline, replay, impossible step, and cross-sensor check
  (torque predicted from temperature + vibration; > 3 sigma away is flagged).
  A flagged joint is re-scored by a model that ignores torque. Spoof + any
  other sign of trouble = EMERGENCY_STOP; spoof alone = SCHEDULE_MAINTENANCE.
  CATCHES: frozen values, replays, sudden drops, large noisy fakes.
  MISSES: small lies inside the 3-sigma tolerance, a coherent forgery of
  torque + temperature + vibration together, and very slow drift. A redundant
  sensor (e.g. motor current) would close most of these gaps.

REFERENCES (course reading list)
  Groover, M.P. - Automation, Production Systems, and Computer-Integrated
  Manufacturing, 5th Ed., Pearson, 2016.
  Krutz, R.L. - Industrial Automation and Control System Security Principles,
  2nd Ed., ISA, 2017.
  Srinivasaraghavan, A. & Joseph, V. - Machine Learning, Wiley, 2019.
"""
import os
import re
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Sample maintenance log (written to maintenance_log.txt if it does not exist)
MAINTENANCE_LOG_TEXT = r'''# Maintenance log - free text written by technicians.
# Format: YYYY-MM-DD HH:MM | ARM-xx | joint | note
2026-10-13 08:10 | ARM-01 | elbow    | Routine inspection done. No grinding noise, no leaks, joint feels normal.
2026-10-13 09:30 | ARM-01 | general  | Cleaned the safety fence glass and restocked the pallet area.
2026-10-12 14:05 | ARM-02 | wrist    | Slight squeak at the wrist at the start of each cycle, otherwise fine.
2026-10-12 10:45 | ARM-03 | general  | Replaced the coffee machine in the break room next to cell 3.
2026-10-11 16:20 | ARM-03 | shoulder | Touched up paint on the shoulder housing after the line audit.
2026-10-13 11:15 | ARM-05 | elbow    | Burning smell near the elbow and a grinding noise when it rotates.
2026-10-13 11:40 | ARM-05 | elbow    | Elbow housing hot to touch after 30 min of running.
2026-10-12 13:00 | ARM-06 | general  | Updated the cell signage and re-labelled the emergency stop button.
2026-10-10 07:50 | ARM-07 | general  | Tool changer calibrated, gripper fingers replaced. All normal.
2026-10-13 15:25 | ARM-08 | wrist    | Operator reported nothing unusual during the night shift.
2026-09-01 09:00 | ARM-04 | shoulder | Heard grinding at the shoulder; bearing re-greased, issue resolved.
2026-10-09 12:00 | ARM-04 | general  | Scheduled the quarterly software backup for next week.
this line is malformed and is ignored by the parser
'''

# ==========================================================================
# CONFIG - every threshold in one place
# ==========================================================================
JOINTS = ("shoulder", "elbow", "wrist")

# Rated (continuous) torque of each joint's actuator, in N·m.
RATED_TORQUE_NM = {"shoulder": 120.0, "elbow": 80.0, "wrist": 30.0}

# ---- Requirement 1: HARD safety limits (deterministic, no ML) --------------
SAFETY_LIMITS = {
    "torque_pct": 130.0,      # % of rated torque  (drive peak rating ~ 130 %)
    "temp_c": 95.0,           # joint housing temperature, deg C
    "vibration_mm_s": 11.0,   # RMS velocity; ISO 10816 "damage occurs" zone
}

# ---- Requirement 2: model risk levels --------------------------------------
WEAR_MED = 0.30    # wear probability >= this  -> MED
WEAR_HIGH = 0.60   # wear probability >= this  -> HIGH

# ---- Requirement 3: maintenance notes --------------------------------------
NOTE_MAX_AGE_DAYS = 14   # older notes are assumed to have been dealt with
NOTE_SEVERE_POINTS = 3   # points needed for level SEVERE
NOTE_MINOR_POINTS = 1    # points needed for level MINOR

# ---- Requirement 4: spoof-defence tuning -----------------------------------
SPOOF_FLATLINE_STD_PCT = 0.3    # real torque noise is ~3 %; < 0.3 % = frozen
SPOOF_MAX_STEP_PCT = 40.0       # max believable sample-to-sample jump
SPOOF_RESIDUAL_Z = 3.0          # cross-sensor disagreement, in std-devs

DECISIONS = ("SAFE", "MONITOR", "SCHEDULE_MAINTENANCE", "EMERGENCY_STOP")

# ==========================================================================
# REQ 2 - synthetic historical dataset generator
# ==========================================================================
import numpy as np
import pandas as pd


def sample_reading(rng, joint, load_pct, wear):
    """One physical sensor reading for a joint at a given load and wear level."""
    torque_pct = load_pct + 25.0 * wear + rng.normal(0, 3.0)
    temp_c = 35.0 + 0.30 * torque_pct + 20.0 * wear + rng.normal(0, 2.5)
    vib = 0.8 + 0.02 * torque_pct + 5.5 * wear + rng.normal(0, 0.35)
    return {
        "torque_nm": torque_pct / 100.0 * RATED_TORQUE_NM[joint],
        "temp_c": temp_c,
        "vibration_mm_s": max(vib, 0.05),
    }


def hours_since_service(rng, wear):
    return max(0.0, rng.uniform(50, 500) + 1500.0 * wear + rng.normal(0, 150))


def generate(n=150, seed=42, path="historical_joint_data.csv"):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        joint = JOINTS[i % 3]
        wear = rng.uniform(0, 1)
        load = rng.uniform(35, 75)
        r = sample_reading(rng, joint, load, wear)
        failed = int(wear + rng.normal(0, 0.07) > 0.60)
        rows.append({
            "reading_id": i + 1,
            "arm_id": f"ARM-{(i % 6) + 1:02d}",
            "joint": joint,
            "torque_nm": round(r["torque_nm"], 2),
            "temp_c": round(r["temp_c"], 1),
            "vibration_mm_s": round(r["vibration_mm_s"], 2),
            "hours_since_service": round(hours_since_service(rng, wear)),
            "failed_within_30d": failed,
        })
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return df

# ==========================================================================
# REQ 1 - immediate safety stop (deterministic, NO ML)
# ==========================================================================
import math


def _bad(x):
    return x is None or (isinstance(x, float) and not math.isfinite(x))


def check_safety(arm_windows):
    """Return a list of human-readable trip reasons ([] means no trip).

    Every single sample of every joint is checked (not just an average):
    one dangerous reading is enough.  Missing / NaN readings are treated as a
    trip too (fail-safe: a blind arm is not a safe arm).
    """
    reasons = []
    for joint, w in arm_windows.items():
        rated = RATED_TORQUE_NM[joint]
        torque_limit_nm = rated * SAFETY_LIMITS["torque_pct"] / 100.0
        for i, (tq, tp, vb) in enumerate(zip(w.torque_nm, w.temp_c, w.vibration_mm_s)):
            if _bad(tq) or _bad(tp) or _bad(vb):
                reasons.append(f"{joint}[{i}]: missing/invalid reading (fail-safe)")
                continue
            if tq > torque_limit_nm:
                reasons.append(f"{joint}[{i}]: torque {tq:.1f} N·m > limit {torque_limit_nm:.1f} N·m")
            if tp > SAFETY_LIMITS["temp_c"]:
                reasons.append(f"{joint}[{i}]: temperature {tp:.1f} °C > limit {SAFETY_LIMITS['temp_c']} °C")
            if vb > SAFETY_LIMITS["vibration_mm_s"]:
                reasons.append(f"{joint}[{i}]: vibration {vb:.1f} mm/s > limit {SAFETY_LIMITS['vibration_mm_s']} mm/s")
    return reasons

# ==========================================================================
# REQ 2 - predictive wear model (ML)
# ==========================================================================
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FULL = ["torque_pct", "temp_c", "vibration_mm_s", "hours_since_service"]
NO_TORQUE = ["temp_c", "vibration_mm_s", "hours_since_service"]


def load_history(path="historical_joint_data.csv"):
    df = pd.read_csv(path)
    df["torque_pct"] = df.apply(
        lambda r: r.torque_nm / RATED_TORQUE_NM[r.joint] * 100.0, axis=1)
    return df


def _pipe():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))


class WearModel:
    def __init__(self, df):
        y = df["failed_within_30d"]
        self.full = _pipe().fit(df[FULL], y)
        self.no_torque = _pipe().fit(df[NO_TORQUE], y)
        # honest accuracy estimates (5-fold cross-validation)
        self.cv_full = cross_val_score(_pipe(), df[FULL], y, cv=5).mean()
        self.cv_no_torque = cross_val_score(_pipe(), df[NO_TORQUE], y, cv=5).mean()
        Xtr, Xte, ytr, yte = train_test_split(df[FULL], y, test_size=0.25,
                                              random_state=0, stratify=y)
        self.holdout_acc = _pipe().fit(Xtr, ytr).score(Xte, yte)

    def predict(self, torque_pct, temp_c, vib, hours, torque_trusted=True):
        """Probability that this joint fails within 30 days."""
        if torque_trusted:
            X = pd.DataFrame([[torque_pct, temp_c, vib, hours]], columns=FULL)
            return float(self.full.predict_proba(X)[0, 1])
        X = pd.DataFrame([[temp_c, vib, hours]], columns=NO_TORQUE)
        return float(self.no_torque.predict_proba(X)[0, 1])

# ==========================================================================
# REQ 3 - maintenance notes as a second signal
# ==========================================================================
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

SEVERE_PATTERNS = [
    r"burn\w*\s+smell", r"smell\w*\s+(?:of\s+)?burn\w*", r"\bburnt\b",
    r"\bsmok\w+", r"\bgrind\w*", r"metal\s+(?:shavings|flakes|filings|particles)",
    r"\bcrack\w*", r"\bseiz\w+", r"\bsparks?\b", r"\bknock\w*",
]
MINOR_PATTERNS = [
    r"\bsqueak\w*", r"\bsqueal\w*", r"\brattl\w*", r"\bwhin\w+", r"\bhumm\w*",
    r"\bnois\w+", r"\bvibrat\w+", r"\bwarm\b", r"\bhot\b", r"\boverheat\w*",
    r"\bloose\w*", r"\bbacklash\b", r"\bplay\b", r"\bstiff\w*", r"\bsticky\b",
    r"\bjerk\w*", r"\bleak\w*", r"\bseep\w*", r"\bdiscolou?r\w*",
]
NEGATORS = {"no", "not", "without", "never", "none", "nothing", "isnt", "didnt",
            "doesnt", "cant", "free"}
LINE_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?\s*\|\s*([\w-]+)\s*\|\s*([\w-]*)\s*\|\s*(.+?)\s*$")


@dataclass
class NoteResult:
    points: int = 0
    level: str = "NONE"
    evidence: list = field(default_factory=list)


def _negated(words_before):
    return any(w in NEGATORS for w in words_before[-3:])


def score_text(text):
    """Return (points, [evidence]) for a single note."""
    points, evidence = 0, []
    # split into clauses so "no leaks, but grinding noise" negates only "leaks"
    for clause in re.split(r"[.,;:!?]|\bbut\b|\bhowever\b", text.lower()):
        clause = clause.replace("'", "")
        for patterns, pts in ((SEVERE_PATTERNS, NOTE_SEVERE_POINTS), (MINOR_PATTERNS, 1)):
            for pat in patterns:
                m = re.search(pat, clause)
                if not m:
                    continue
                before = re.findall(r"[a-z]+", clause[:m.start()])
                if _negated(before):
                    continue
                points += pts
                evidence.append(m.group(0))
    return points, evidence


def parse_log(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m or line.lstrip().startswith("#"):
                continue
            date, time, arm, joint, text = m.groups()
            ts = datetime.strptime(f"{date} {time or '00:00'}", "%Y-%m-%d %H:%M")
            entries.append({"ts": ts, "arm": arm.upper(), "joint": joint.lower(), "text": text})
    return entries


def score_log(path, now):
    """Return {arm_id: NoteResult} using only recent notes."""
    cutoff = now - timedelta(days=NOTE_MAX_AGE_DAYS)
    totals = defaultdict(NoteResult)
    for e in parse_log(path):
        if e["ts"] < cutoff or e["ts"] > now:
            continue
        pts, ev = score_text(e["text"])
        if pts:
            r = totals[e["arm"]]
            r.points += pts
            r.evidence.extend(f"{e['joint'] or 'general'}: {w}" for w in ev)
    for r in totals.values():
        r.level = ("SEVERE" if r.points >= NOTE_SEVERE_POINTS
                   else "MINOR" if r.points >= NOTE_MINOR_POINTS else "NONE")
    return totals

# ==========================================================================
# REQ 4 - spoofed-torque defence
# ==========================================================================
import numpy as np


class SpoofDetector:
    def __init__(self, history_df):
        X = np.column_stack([np.ones(len(history_df)),
                             history_df["temp_c"], history_df["vibration_mm_s"]])
        y = history_df["torque_pct"].to_numpy()
        self.coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        self.sigma = float(np.std(y - X @ self.coef))
        z = np.abs((y - X @ self.coef) / self.sigma)
        self.history_false_alarm_rate = float((z > SPOOF_RESIDUAL_Z).mean())

    def expected_torque_pct(self, temp_c, vib):
        return float(self.coef @ np.array([1.0, temp_c, vib]))

    def check(self, joint, w):
        """Return a list of spoof flags for this joint's window ([] = looks real)."""
        tq = np.asarray(w.torque_nm, dtype=float) / RATED_TORQUE_NM[joint] * 100.0
        flags = []
        if tq.std() < SPOOF_FLATLINE_STD_PCT:
            flags.append("flatline: torque has no sensor noise (frozen/injected value)")
        n = len(tq) // 2
        if n >= 4 and tq.std() >= SPOOF_FLATLINE_STD_PCT and np.allclose(tq[:n], tq[n:2 * n]):
            flags.append("replay: second half of window is a copy of the first")
        if len(tq) > 1 and np.abs(np.diff(tq)).max() > SPOOF_MAX_STEP_PCT:
            flags.append(f"implausible step: torque jumped {np.abs(np.diff(tq)).max():.0f} % of rated in one sample")
        exp = self.expected_torque_pct(np.mean(w.temp_c), np.mean(w.vibration_mm_s))
        z = (tq.mean() - exp) / self.sigma
        if abs(z) > SPOOF_RESIDUAL_Z:
            flags.append(f"cross-sensor mismatch: torque {tq.mean():.0f} % but temp/vibration "
                         f"imply ~{exp:.0f} % (z={z:+.1f})")
        return flags

# ==========================================================================
# REQ 5 - one final decision per arm
# ==========================================================================
from dataclasses import dataclass, field
import numpy as np

RANK = {d: i for i, d in enumerate(DECISIONS)}
SAFE, MONITOR, SCHEDULE, STOP = DECISIONS

TABLE = {
    ("LOW", "NONE"): SAFE,      ("LOW", "MINOR"): MONITOR,      ("LOW", "SEVERE"): SCHEDULE,
    ("MED", "NONE"): MONITOR,   ("MED", "MINOR"): SCHEDULE,     ("MED", "SEVERE"): SCHEDULE,
    ("HIGH", "NONE"): SCHEDULE, ("HIGH", "MINOR"): SCHEDULE,    ("HIGH", "SEVERE"): STOP,
}


@dataclass
class JointWindow:
    torque_nm: list
    temp_c: list
    vibration_mm_s: list
    hours_since_service: float = 0.0


@dataclass
class ArmReport:
    arm_id: str
    decision: str = SAFE
    reasons: list = field(default_factory=list)
    safety_trips: list = field(default_factory=list)
    spoof_flags: dict = field(default_factory=dict)
    wear_prob: float = None
    model_level: str = "UNAVAILABLE"
    note_level: str = "NONE"


def model_level(p):
    return "LOW" if p < WEAR_MED else "MED" if p < WEAR_HIGH else "HIGH"


def assess_arm(arm_id, windows, model, spoof_detector, notes):
    rep = ArmReport(arm_id)

    # 1. HARD SAFETY - first, and returns before the model is ever called.
    trips = check_safety(windows)
    if trips:
        rep.decision, rep.safety_trips = STOP, trips
        rep.reasons.append("HARD SAFETY LIMIT crossed: " + trips[0] + (f" (+{len(trips)-1} more)" if len(trips) > 1 else ""))
        return rep

    # 2. spoof check per joint
    for joint, w in windows.items():
        flags = spoof_detector.check(joint, w) if spoof_detector else []
        if flags:
            rep.spoof_flags[joint] = flags

    # 3. ML wear probability (max over joints); torque ignored on spoofed joints
    probs = []
    try:
        for joint, w in windows.items():
            torque_pct = float(np.mean(w.torque_nm)) / RATED_TORQUE_NM[joint] * 100.0
            p = model.predict(torque_pct, float(np.mean(w.temp_c)), float(np.mean(w.vibration_mm_s)),
                              w.hours_since_service, torque_trusted=joint not in rep.spoof_flags)
            probs.append(p)
        rep.wear_prob = max(probs)
        rep.model_level = model_level(rep.wear_prob)
    except Exception as exc:                      # model missing / broken
        rep.reasons.append(f"model unavailable ({type(exc).__name__}) - running on notes only")

    # 4. maintenance notes
    nr = notes.get(arm_id)
    rep.note_level = nr.level if nr else "NONE"
    if nr:
        rep.reasons.append(f"notes {nr.level}: " + ", ".join(nr.evidence))

    # 5. combine
    lvl = rep.model_level if rep.model_level != "UNAVAILABLE" else "LOW"
    d = TABLE[(lvl, rep.note_level)]
    if rep.model_level == "UNAVAILABLE" and d == SAFE:
        d = MONITOR
    if rep.wear_prob is not None:
        rep.reasons.append(f"model {rep.model_level} (p={rep.wear_prob:.2f})"
                           + (" [degraded: torque ignored]" if rep.spoof_flags else ""))

    if rep.spoof_flags:
        rep.reasons.append("SPOOF suspected on " + ", ".join(rep.spoof_flags))
        corroborated = rep.model_level in ("MED", "HIGH") or rep.note_level != "NONE"
        d = STOP if corroborated else max(d, SCHEDULE, key=RANK.get)
        rep.reasons.append("other signals corroborate a real problem -> STOP" if corroborated
                           else "no corroboration -> inspect sensor")
    rep.decision = d
    return rep

# ==========================================================================
# DEMO - one run per outcome + spoof-attack test
# ==========================================================================
import os
from datetime import datetime
import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "historical_joint_data.csv")
LOG = os.path.join(HERE, "maintenance_log.txt")
NOW = datetime(2026, 10, 14, 12, 0)
N = 20  # samples per window
rng = np.random.default_rng(7)


def window(joint, load, wear, hours=None, torque_override=None):
    """Simulate N samples from a joint; optionally replace the torque channel."""
    rows = [sample_reading(rng, joint, load, wear) for _ in range(N)]
    tq = [r["torque_nm"] for r in rows] if torque_override is None else list(torque_override)
    return JointWindow(tq, [r["temp_c"] for r in rows], [r["vibration_mm_s"] for r in rows],
                       hours if hours is not None else 150 + 1500 * wear)


def healthy_arm():
    return {"shoulder": window("shoulder", 55, 0.05), "elbow": window("elbow", 50, 0.05),
            "wrist": window("wrist", 45, 0.05)}


def pct_to_nm(joint, pct_list):
    return [p / 100 * RATED_TORQUE_NM[joint] for p in pct_list]


def fake_torque(joint, pct, noise=3.0):
    """Attacker-supplied torque that *looks* noisy and realistic."""
    return pct_to_nm(joint, rng.normal(pct, noise, N))


class BrokenModel:
    def predict(self, *a, **k):
        raise RuntimeError("model server down")


def scenarios():
    s = {}
    s["ARM-01"] = ("Healthy arm, clean notes", healthy_arm())
    s["ARM-02"] = ("Sensors fine, technician hears a squeak", healthy_arm())
    a = healthy_arm(); a["elbow"] = window("elbow", 65, 0.85)
    s["ARM-03"] = ("Elbow clearly worn, no notes", a)
    a = healthy_arm(); a["shoulder"].torque_nm[11] = 175.0   # 146 % of rated, single sample
    s["ARM-04"] = ("One shoulder torque spike over hard limit", a)
    a = healthy_arm(); a["elbow"] = window("elbow", 65, 0.85)
    s["ARM-05"] = ("Elbow worn + 'burning smell / grinding' notes", a)
    a = healthy_arm(); a["elbow"] = window("elbow", 65, 0.85)
    a["elbow"].torque_nm = fake_torque("elbow", 35)           # attacker hides ~90 % torque
    s["ARM-06"] = ("SPOOFED elbow torque (hides worn joint)", a)
    a = healthy_arm(); a["wrist"].torque_nm = [14.0] * N      # frozen value, everything else healthy
    s["ARM-07"] = ("Frozen wrist torque, nothing else wrong", a)
    s["ARM-08"] = ("Healthy arm but model service is down", healthy_arm())
    return s


def main():
    if not os.path.exists(CSV):
        generate(path=CSV)
    hist = load_history(CSV)
    model = WearModel(hist)
    spoof = SpoofDetector(hist)
    notes = score_log(LOG, NOW)

    print(f"Dataset: {len(hist)} labelled readings | model 5-fold CV accuracy "
          f"{model.cv_full:.0%} (no-torque degraded model {model.cv_no_torque:.0%}) | "
          f"spoof-check false-alarm rate on history {spoof.history_false_alarm_rate:.1%}\n")

    reports = {}
    for arm, (title, w) in scenarios().items():
        m = BrokenModel() if arm == "ARM-08" else model
        reports[arm] = assess_arm(arm, w, m, spoof, notes)
        r = reports[arm]
        print(f"{arm}  {r.decision:<21} <- {title}")
        for line in r.reasons:
            print(f"          - {line}")
        for j, fl in r.spoof_flags.items():
            for f in fl:
                print(f"          - [{j}] {f}")
        print()

    # ---- ARM-04: safety stop must work with NO model at all ------------------
    r = assess_arm("ARM-04", scenarios()["ARM-04"][1], None, None, {})
    assert r.decision == "EMERGENCY_STOP"
    print("Safety independence check: ARM-04 still -> EMERGENCY_STOP with model=None "
          "and spoof detector=None.\n")

    # ---- all four outcomes reachable? ----------------------------------------
    got = {r.decision for r in reports.values()}
    print("Outcomes demonstrated:", ", ".join(sorted(got, key=DECISIONS.index)))
    assert got == set(DECISIONS), "not every decision was reached!"

    spoof_attack_table(spoof)


def spoof_attack_table(spoof):
    """Which attacks does the spoof defence catch, and which does it miss?"""
    print("\nSpoofed-torque attack test (elbow joint, true state = worn, ~90 % torque):")
    true = window("elbow", 65, 0.85)
    cases = {}
    cases["Frozen value (flatline at 35 %)"] = JointWindow(pct_to_nm("elbow", [35.0] * N), true.temp_c, true.vibration_mm_s)
    rec = pct_to_nm("elbow", rng.normal(35, 3, N // 2))
    cases["Replay of a recorded 10-sample window"] = JointWindow(rec + rec, true.temp_c, true.vibration_mm_s)
    stepped = list(true.torque_nm[:10]) + pct_to_nm("elbow", rng.normal(35, 3, 10))
    cases["Sudden drop mid-window (hide a fault)"] = JointWindow(stepped, true.temp_c, true.vibration_mm_s)
    cases["Noisy fake value, far from truth (35 %)"] = JointWindow(fake_torque("elbow", 35), true.temp_c, true.vibration_mm_s)
    cases["Noisy fake, only modestly low (true -10 %)"] = JointWindow(
        pct_to_nm("elbow", np.array(true.torque_nm) / 80 * 100 - 10), true.temp_c, true.vibration_mm_s)
    healthy = window("elbow", 50, 0.05)
    cases["Coherent fake: torque+temp+vibration all forged"] = JointWindow(
        fake_torque("elbow", 50), healthy.temp_c, healthy.vibration_mm_s)
    print(f"  {'attack':<52}{'caught?'}")
    for name, w in cases.items():
        caught = bool(spoof.check("elbow", w))
        print(f"  {name:<52}{'YES' if caught else 'NO  (known limitation)'}")



# Make sure the log file exists next to this script (demo() reads it).
if not os.path.exists(LOG):
    with open(LOG, "w", encoding="utf-8") as _f:
        _f.write(MAINTENANCE_LOG_TEXT)

if __name__ == "__main__":
    main()
