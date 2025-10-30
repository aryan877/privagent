"""
Privacy Knowledge Graph Engine using MeTTa Symbolic AI

This module implements a hybrid neural-symbolic reasoning system for privacy analysis:

1. **MeTTa Symbolic AI** (Optional, preferred):
   - MeTTa is a meta-language for neural-symbolic AGI (Artificial General Intelligence)
   - Developed by SingularityNET/TrueAGI as part of the Hyperon project
   - Combines symbolic logic (rules, patterns) with neural networks (learning)

   Key Concepts:
   - **Atoms**: Fundamental data units (symbols, numbers, expressions)
   - **Spaces**: Collections of atoms (like knowledge bases or databases)
   - **Pattern Matching**: Unification-based query system (like Prolog)
   - **Evaluation**: Reducing expressions to final values using rules

2. **Rule-Based Fallback** (Default when MeTTa not available):
   - Deterministic privacy scoring using weighted heuristics
   - No symbolic reasoning, just algorithmic calculations

3. **Privacy Scoring Dimensions**:
   - Compression ratio (ZK state compression usage)
   - Counterparty diversity (unique wallets interacted with)
   - Address reuse (how often same address is used)
   - Timing variance (predictability of transaction patterns)

Why Neural-Symbolic AI?
- Symbolic AI: Explainable, precise, rule-based reasoning
- Neural AI: Pattern recognition, learning from data
- Combined: Best of both worlds - explainable AND adaptive

References:
- MeTTa Language: https://github.com/trueagi-io/hyperon-experimental
- Hyperon Project: https://singularitynet.io/hyperon/
- Paper: "Neural-Symbolic AI in 2024: A Systematic Review"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

# Optional dependency: MeTTa symbolic AI engine
# Falls back to rule-based analysis if not installed
try:
    from hyperon import MeTTa  # Hyperon experimental implementation

    METTA_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    MeTTa = None
    METTA_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


@dataclass
class PrivacyAnalysis:
    """
    Result of privacy analysis for a wallet.

    Attributes:
        score (int): Privacy score 0-100
            - 0-50: Poor privacy, high risk
            - 51-70: Average privacy, moderate risk
            - 71-90: Good privacy, low risk
            - 91-100: Excellent privacy, minimal risk

        grade (str): Letter grade (A+, A, B, C, D, F)
            - Provides human-readable assessment
            - Aligns with common grading systems for easy interpretation

        recommendations (List[str]): Actionable advice to improve privacy
            - Prioritized by impact (most important first)
            - Maximum 5 recommendations to avoid overwhelming user
            - Examples: "Enable ZK compression", "Rotate addresses"

        threats (List[str]): Detected privacy vulnerabilities
            - Specific issues found in wallet's behavior
            - Helps user understand why score is low
            - Examples: "Address clustering detected", "Low compression usage"

        backend (str): Which reasoning engine was used
            - "metta": Neural-symbolic AI engine (preferred, explainable)
            - "rules": Deterministic heuristic engine (fallback, faster)
            - Useful for debugging and understanding results
    """
    score: int
    grade: str
    recommendations: List[str]
    threats: List[str]
    backend: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert analysis to JSON-serializable dictionary.

        Returns a clean dict suitable for API responses and storage.
        """
        return {
            "score": self.score,
            "grade": self.grade,
            "recommendations": self.recommendations,
            "threats_detected": self.threats,
            "reasoning_engine": self.backend,  # Track which backend was used
        }


class PrivacyKnowledgeEngine:
    """
    Hybrid privacy reasoning engine using MeTTa symbolic AI.

    Architecture:
    ┌──────────────────────────────────────────────────────┐
    │              PrivacyKnowledgeEngine                  │
    ├──────────────────────────────────────────────────────┤
    │                                                      │
    │  ┌────────────────┐         ┌──────────────────┐   │
    │  │  MeTTa Engine  │  OR     │  Rule Engine     │   │
    │  │  (Symbolic AI) │         │  (Heuristics)    │   │
    │  └────────────────┘         └──────────────────┘   │
    │         ↓                            ↓              │
    │  Pattern Matching              If-Then Rules        │
    │  + Knowledge Base              + Weighted Scoring   │
    │  + Unification                 + Deterministic      │
    │         ↓                            ↓              │
    │  ┌──────────────────────────────────────┐          │
    │  │      Privacy Score + Recommendations  │          │
    │  └──────────────────────────────────────┘          │
    └──────────────────────────────────────────────────────┘

    MeTTa Spaces (Knowledge Bases):
    - &rules: Pattern-based reasoning rules
      Example: (grade-message A+ "Outstanding privacy posture")
      Example: (recommend compression_ratio low "Enable ZK compression")

    - &facts: Runtime wallet data (cleared each analysis)
      Example: (score-value 85)
      Example: (compression_ratio 0.75)
      Example: (category reuse_ratio high)

    Why Two Spaces?
    - Separation of permanent knowledge (&rules) from temporary data (&facts)
    - Rules persist across analyses, facts are ephemeral
    - Enables clean reasoning without interference

    Query Flow:
    1. Assert wallet metrics as facts: !(assert! &facts (compression_ratio 0.8))
    2. Categorize metrics: low/medium/high buckets
    3. Match patterns in rules: !(match &rules (recommend compression_ratio low $msg) $msg)
    4. Collect recommendations and threats
    5. Return PrivacyAnalysis with explainable reasoning

    Fallback:
    If MeTTa is unavailable, uses deterministic rule-based scoring.
    Results are similar but less explainable (no symbolic reasoning trace).
    """

    def __init__(self, enabled: bool = True) -> None:
        """
        Initialize the privacy knowledge engine.

        Args:
            enabled: Whether to attempt MeTTa initialization (True by default)

        The engine will auto-fallback to rule-based analysis if:
        - MeTTa library is not installed
        - Initialization fails for any reason
        """
        # Only enable MeTTa if user requested AND library is available
        self.enabled = enabled and METTA_AVAILABLE
        self.logger = LOGGER
        self.backend = "rules"  # Default to rule-based (deterministic)
        self.metta = None  # MeTTa runtime (None until initialized)

        if self.enabled:
            try:
                # Create new MeTTa interpreter instance
                # This initializes the evaluation engine and creates an empty space
                self.metta = MeTTa()

                # Load privacy knowledge base (rules, patterns, recommendations)
                self._initialize_engine()

                # Success! Switch to symbolic reasoning backend
                self.backend = "metta"
                self.logger.info("loaded MeTTa knowledge base for privacy analysis")
            except Exception as exc:  # pragma: no cover - defensive
                # Failed to initialize - log warning and fallback to rules
                self.logger.warning("failed to initialize MeTTa engine: %s", exc)
                self.enabled = False

    def analyze_privacy_score(self, wallet_data: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer MeTTa reasoning when the runtime is available, otherwise fall back to deterministic rules.
        analysis = self._run_metta(wallet_data) if self.enabled else None
        if analysis:
            return analysis.to_dict()

        fallback_analysis = self._rule_based_analysis(wallet_data)
        return fallback_analysis.to_dict()

    def _run_metta(self, wallet_data: Dict[str, Any]) -> Optional[PrivacyAnalysis]:
        if not self.metta:
            return None

        try:
            analysis = self._metta_reason(wallet_data)
            if analysis:
                return analysis
        except Exception as exc:
            self.logger.debug("metta reasoning failed, falling back to rules: %s", exc)

        return self._rule_based_analysis(wallet_data)

    def _rule_based_analysis(self, wallet_data: Dict[str, Any]) -> PrivacyAnalysis:
        score = self._calculate_score(wallet_data)
        grade = self._grade(score)
        recommendations = self._recommendations(wallet_data, score)
        threats = self._threats(wallet_data, score)

        return PrivacyAnalysis(
            score=score,
            grade=grade,
            recommendations=recommendations,
            threats=threats,
            backend=self.backend,
        )

    def _calculate_score(self, data: Dict[str, Any]) -> int:
        """
        Calculate privacy score using weighted heuristics.

        **Privacy Scoring Algorithm** (Total: 100 points)

        The score is calculated across 4 dimensions:

        1. **Compression Ratio** (40 points max - MOST IMPORTANT)
           - Measures usage of ZK state compression (Light Protocol)
           - Why 40%? Compression directly hides transaction data on-chain
           - Formula: 40 * compression_ratio (clamped to [0, 1])
           - Example: 0.75 compression = 30 points

        2. **Counterparty Diversity** (25 points max)
           - Measures how many unique wallets user interacts with
           - Why? More counterparties = harder to cluster/deanonymize
           - Tiered scoring (inspired by graph analysis research):
             * 12+ counterparties: 25 points (excellent diversity)
             * 8-11 counterparties: 18 points (good diversity)
             * 4-7 counterparties: 12 points (moderate diversity)
             * 0-3 counterparties: 6 points (poor diversity, easy to cluster)

        3. **Address Reuse** (20 points max)
           - Inverse of reuse_ratio (lower reuse = higher score)
           - Why? Address reuse enables clustering attacks (linking transactions)
           - Formula: 20 * (1.0 - reuse_ratio)
           - Example: 0.3 reuse ratio = 14 points (70% score)

        4. **Timing Variance** (15 points max)
           - Measures unpredictability of transaction timing
           - Why? Predictable timing enables behavioral fingerprinting
           - Tiered scoring (based on seconds variance):
             * 3600+ seconds (1 hour+): 15 points (highly random)
             * 1800-3599 seconds (30-60 min): 10 points (moderately random)
             * 900-1799 seconds (15-30 min): 5 points (slightly random)
             * 0-899 seconds (<15 min): 0 points (predictable, risky)

        **Total Score Interpretation:**
        - 90-100: A+ grade (outstanding privacy)
        - 80-89: A grade (strong privacy)
        - 70-79: B grade (solid privacy)
        - 60-69: C grade (average privacy)
        - 50-59: D grade (weak privacy)
        - 0-49: F grade (critical privacy issues)

        Args:
            data: Dictionary containing wallet metrics

        Returns:
            Privacy score clamped to [0, 100]
        """
        # Extract metrics with safe defaults (0.0 = worst case)
        compression_ratio = float(data.get("compression_ratio", 0.0))
        unique_counterparties = int(data.get("unique_counterparties", 0))
        reuse_ratio = float(data.get("reuse_ratio", 1.0))  # 1.0 = always reuse (worst)
        timing_variance = float(data.get("timing_variance", 0.0))

        score = 0

        # DIMENSION 1: Compression Ratio (40 points)
        # Weight compression first because it directly hides balances on-chain
        # Clamp to [0, 1] to prevent negative or >100 scores
        score += int(40 * min(max(compression_ratio, 0.0), 1.0))

        # DIMENSION 2: Counterparty Diversity (25 points)
        # Tiered system based on graph clustering research
        if unique_counterparties >= 12:
            score += 25  # Excellent diversity, hard to deanonymize
        elif unique_counterparties >= 8:
            score += 18  # Good diversity, moderate resistance
        elif unique_counterparties >= 4:
            score += 12  # Moderate diversity, some clustering risk
        else:
            score += 6  # Poor diversity, easy to cluster/link

        # DIMENSION 3: Address Reuse (20 points)
        # Lower reuse = better privacy (harder to link transactions)
        # Formula: score = 20 * (1 - reuse_ratio)
        # Example: 0% reuse = 20 points, 50% reuse = 10 points, 100% reuse = 0 points
        score += int(20 * (1.0 - min(max(reuse_ratio, 0.0), 1.0)))

        # DIMENSION 4: Timing Variance (15 points)
        # Higher variance = less predictable = better privacy
        if timing_variance >= 3600:  # 1 hour or more
            score += 15  # Highly unpredictable, excellent privacy
        elif timing_variance >= 1800:  # 30-60 minutes
            score += 10  # Moderately unpredictable, good privacy
        elif timing_variance >= 900:  # 15-30 minutes
            score += 5  # Slightly unpredictable, some privacy

        # Clamp final score to valid range [0, 100]
        return max(0, min(100, score))

    def _grade(self, score: int) -> str:
        if score >= 90:
            return "A+"
        if score >= 80:
            return "A"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C"
        if score >= 50:
            return "D"
        return "F"

    def _recommendations(self, data: Dict[str, Any], score: int) -> List[str]:
        suggestions: List[str] = []
        compression_ratio = float(data.get("compression_ratio", 0.0))
        reuse_ratio = float(data.get("reuse_ratio", 1.0))
        unique_counterparties = int(data.get("unique_counterparties", 0))
        timing_variance = float(data.get("timing_variance", 0.0))

        if compression_ratio < 0.4:
            suggestions.append("Increase account compression coverage to reduce on-chain footprint.")

        if reuse_ratio > 0.5:
            suggestions.append("Rotate receiving addresses more frequently to avoid clustering attacks.")

        if unique_counterparties < 6:
            suggestions.append("Add more counterparties or use mixing services to diversify flows.")

        if timing_variance < 1200:
            suggestions.append("Vary transaction timing or use automation with jitter to resist timing correlation.")

        if score < 60:
            suggestions.append("Consider privacy-enhancing swaps or cross-chain bridges to break traceability.")

        return suggestions[:5] or ["No immediate action required."]

    def _threats(self, data: Dict[str, Any], score: int) -> List[str]:
        threats: List[str] = []
        reuse_ratio = float(data.get("reuse_ratio", 0.0))
        compression_ratio = float(data.get("compression_ratio", 0.0))
        unique_counterparties = int(data.get("unique_counterparties", 0))

        if reuse_ratio > 0.7 and unique_counterparties < 3:
            threats.append("Address clustering likely; activity concentrated across few counterparties.")
        if compression_ratio < 0.2:
            threats.append("Limited use of compression exposes full transaction history.")
        if score < 50:
            threats.append("Overall privacy posture is weak; wallet is susceptible to linkage attacks.")

        return threats

    def _initialize_engine(self) -> None:
        """
        Initialize MeTTa knowledge base with privacy reasoning rules.

        **MeTTa Knowledge Base Structure**

        This creates two spaces (think: separate knowledge graphs):

        1. **&rules**: Permanent knowledge (pattern→message mappings)
           - Contains all reasoning rules for privacy analysis
           - Persists across all wallet analyses
           - Think of it like a "rule book" or "expert system"

        2. **&facts**: Temporary runtime data (cleared each analysis)
           - Holds current wallet's metrics
           - Gets reset before each new analysis
           - Think of it like "working memory"

        **MeTTa Syntax Explained:**

        ```metta
        !(bind! &rules (new-space))
        ```
        - `!` = Execute this expression (don't just parse it)
        - `bind!` = Create a variable binding
        - `&rules` = Variable name (& prefix denotes a space/atomspace)
        - `new-space` = Create a new empty knowledge base

        ```metta
        !(assert! &rules (grade-message A+ "Outstanding privacy posture"))
        ```
        - `assert!` = Add an atom (fact/rule) to a space
        - `&rules` = Target space
        - `(grade-message A+ "...")` = Pattern tuple
          * `grade-message` = Relation type
          * `A+` = Grade symbol (matches literal)
          * `"..."` = Message string

        **Pattern Matching & Unification:**

        When we query: `!(match &rules (grade-message A+ $msg) $msg)`
        1. `match` = Find all atoms matching pattern
        2. `(grade-message A+ $msg)` = Pattern with variable $msg
        3. `$msg` = Variable to capture (like regex capture group)
        4. Returns: All $msg values where pattern matches

        Example:
        - Stored: `(grade-message A+ "Outstanding privacy")`
        - Query: `(grade-message A+ $msg)`
        - Match: YES! Bind $msg = "Outstanding privacy"
        - Return: ["Outstanding privacy"]

        **Knowledge Categories:**

        1. Grade Messages (human-readable grade interpretations)
        2. Recommendations (actionable advice per metric+category)
        3. Threats (warnings for critical issues)

        Each category uses a 3-tuple pattern:
        - (relation-type metric category message)
        - Example: (recommend compression_ratio low "Enable compression")

        This enables flexible querying:
        - All recommendations for compression_ratio: (recommend compression_ratio $cat $msg)
        - Only "low" recommendations: (recommend $metric low $msg)
        - Specific metric+category: (recommend compression_ratio low $msg)
        """
        if not self.metta:
            return

        # Inject privacy reasoning knowledge base into MeTTa
        # This is written in MeTTa language (similar to Lisp/Scheme)
        init_script = """
!(bind! &rules (new-space))
!(bind! &facts (new-space))

;; ═══════════════════════════════════════════════════════════
;; GRADE MESSAGING - Human-readable grade interpretations
;; Pattern: (grade-message <grade> <message>)
;; ═══════════════════════════════════════════════════════════

!(assert! &rules (grade-message A+ "Outstanding privacy posture. Continue current practices."))
!(assert! &rules (grade-message A "Strong privacy posture with room for minor improvements."))
!(assert! &rules (grade-message B "Solid privacy, address highlighted recommendations to improve."))
!(assert! &rules (grade-message C "Privacy posture is average; prioritize improvements soon."))
!(assert! &rules (grade-message D "Privacy gaps detected. Address recommendations immediately."))
!(assert! &rules (grade-message F "Critical privacy issues detected. Immediate action required."))

;; ═══════════════════════════════════════════════════════════
;; RECOMMENDATIONS - Actionable advice by metric category
;; Pattern: (recommend <metric> <category> <message>)
;; Categories: low, medium, high
;; ═══════════════════════════════════════════════════════════

;; Compression Ratio Recommendations
!(assert! &rules (recommend compression_ratio low "Increase account compression coverage to reduce on-chain footprint."))
!(assert! &rules (recommend compression_ratio medium "Consider compressing additional high-balance accounts."))
!(assert! &rules (recommend compression_ratio high "Compression usage looks healthy."))

;; Address Reuse Recommendations (NOTE: high reuse = bad, so inverted logic)
!(assert! &rules (recommend reuse_ratio high "Rotate receiving addresses to prevent address clustering analysis."))
!(assert! &rules (recommend reuse_ratio medium "Monitor address reuse and rotate addresses more frequently."))
!(assert! &rules (recommend reuse_ratio low "Address reuse is within an acceptable range."))

;; Counterparty Diversity Recommendations
!(assert! &rules (recommend unique_counterparties low "Expand counterparty diversity or use mixing strategies."))
!(assert! &rules (recommend unique_counterparties medium "Counterparty diversity is adequate. Continue monitoring."))
!(assert! &rules (recommend unique_counterparties high "Counterparty diversity is strong."))

;; Timing Variance Recommendations
!(assert! &rules (recommend timing_variance low "Introduce randomised execution timing to avoid temporal correlations."))
!(assert! &rules (recommend timing_variance medium "Add slight random delays to transactions to improve privacy."))
!(assert! &rules (recommend timing_variance high "Transaction timing variance looks healthy."))

;; ═══════════════════════════════════════════════════════════
;; THREATS - Privacy vulnerability warnings
;; Pattern: (threat <metric> <category> <message>)
;; Only triggered for "high" risk categories
;; ═══════════════════════════════════════════════════════════

!(assert! &rules (threat reuse_ratio high "High address reuse detected; clustering risk elevated."))
!(assert! &rules (threat compression_ratio low "Low use of compression leaves full history exposed."))
!(assert! &rules (threat unique_counterparties low "Low counterparty diversity makes deanonymisation easier."))
!(assert! &rules (threat timing_variance low "Predictable transaction cadence enables timing analysis."))
"""
        # Execute the MeTTa script to load knowledge base
        # Returns list of evaluation results (ignored, we just want side effects)
        self._run_metta(init_script)

    def _reset_fact_space(self) -> None:
        self._run_metta("!(bind! &facts (new-space))")

    def _run_metta(self, script: str) -> List[str]:
        if not self.metta:
            return []

        result = self.metta.run(script)
        return [self._atom_to_string(atom) for atom in result]

    def _atom_to_string(self, atom: Any) -> str:
        if hasattr(atom, "to_string"):
            return atom.to_string()
        return str(atom)

    def _assert_fact(self, statement: str) -> None:
        self._run_metta(f"!(assert! &facts {statement})")

    def _match_messages(self, pattern: str, capture: str) -> List[str]:
        matches = self._run_metta(f"!(match &rules {pattern} {capture})")
        cleaned: List[str] = []
        for match in matches:
            value = match.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            cleaned.append(value)
        return cleaned

    def _metta_reason(self, wallet_data: Dict[str, Any]) -> Optional[PrivacyAnalysis]:
        """
        Perform symbolic reasoning using MeTTa knowledge base.

        **Symbolic Reasoning Flow (Neural-Symbolic AI):**

        ┌─────────────────────────────────────────────────────────┐
        │ 1. Calculate Score (Numerical → 0-100)                  │
        │    Uses weighted heuristics (_calculate_score)          │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 2. Reset &facts Space (Clear Working Memory)            │
        │    !(bind! &facts (new-space))                          │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 3. Assert Facts (Load Wallet Metrics)                   │
        │    !(assert! &facts (compression_ratio 0.75))           │
        │    !(assert! &facts (reuse_ratio 0.3))                  │
        │    !(assert! &facts (score-value 85))                   │
        │    !(assert! &facts (grade-symbol A))                   │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 4. Categorize Metrics (Bucket into low/medium/high)     │
        │    compression_ratio: 0.75 → "high"                     │
        │    reuse_ratio: 0.3 → "low"                             │
        │    !(assert! &facts (category compression_ratio high))  │
        │    !(assert! &facts (category reuse_ratio low))         │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 5. Pattern Match Recommendations (Query &rules)         │
        │    !(match &rules (recommend compression_ratio high $m) $m)│
        │    Returns: ["Compression usage looks healthy."]        │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 6. Pattern Match Grade Message (Query &rules)           │
        │    !(match &rules (grade-message A $msg) $msg)          │
        │    Returns: ["Strong privacy posture..."]               │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 7. Pattern Match Threats (Query &rules for "high" risk) │
        │    For each category="high": match threat patterns      │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 8. Aggregate + Deduplicate Results                      │
        │    - Flatten nested recommendation lists                │
        │    - Prepend grade message                              │
        │    - Remove duplicates (preserve order)                 │
        └────────────────────┬────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────────────────────┐
        │ 9. Return PrivacyAnalysis (Explainable Result)          │
        │    - Score, Grade, Recommendations, Threats             │
        │    - backend="metta" (tracks reasoning engine used)     │
        └─────────────────────────────────────────────────────────┘

        **Why Symbolic Reasoning?**

        1. **Explainability**: Every recommendation traces back to a rule
           - "Why did it say X?" → Because rule (recommend compression_ratio low "X")
           - Traditional ML: "black box", hard to explain

        2. **Modularity**: Rules can be updated without retraining
           - Add new threat: Just assert a new pattern
           - Traditional ML: Retrain entire model

        3. **Consistency**: Same inputs always produce same outputs
           - No randomness, no learning drift
           - Critical for compliance and auditability

        4. **Knowledge Reuse**: Rules encode domain expertise
           - Privacy experts define rules
           - System executes them consistently

        Args:
            wallet_data: Dictionary of wallet metrics

        Returns:
            PrivacyAnalysis with symbolic reasoning results, or None if MeTTa unavailable
        """
        if not self.metta:
            return None

        # STEP 1: Calculate numerical score (0-100)
        # Uses weighted heuristics, not symbolic reasoning
        score = self._calculate_score(wallet_data)
        grade = self._grade(score)

        # STEP 2: Reset fact space (clear previous wallet's data)
        # Ensures clean slate for each analysis
        self._reset_fact_space()

        # STEP 3: Assert wallet metrics as facts (load into working memory)
        # Format: (metric-name value)
        # These become queryable atoms in the &facts space
        self._assert_fact(f"(score-value {score})")
        self._assert_fact(f"(compression_ratio {wallet_data.get('compression_ratio', 0.0):.4f})")
        self._assert_fact(f"(reuse_ratio {wallet_data.get('reuse_ratio', 0.0):.4f})")
        self._assert_fact(f"(unique_counterparties {int(wallet_data.get('unique_counterparties', 0))})")
        self._assert_fact(f"(timing_variance {wallet_data.get('timing_variance', 0.0):.2f})")
        self._assert_fact(f"(grade-symbol {grade})")

        # STEP 4: Categorize metrics into buckets (low/medium/high)
        # Enables pattern matching with categorical rules
        categories = self._categorise(wallet_data)
        for metric, category in categories.items():
            # Assert category facts: (category compression_ratio high)
            self._assert_fact(f"(category {metric} {category})")

        # STEP 5: Collect recommendations by pattern matching
        # For each metric+category, query: (recommend metric category $msg)
        # Returns dict: {metric: [recommendation_messages]}
        recommendations = self._collect_recommendations(categories)

        # STEP 6: Fetch grade-specific message
        # Query: (grade-message A $msg) → ["Strong privacy posture..."]
        grade_message = self._match_messages(f"(grade-message {grade} $msg)", "$msg")

        # STEP 7: Collect threats (only for high-risk categories)
        # Query: (threat metric category $msg) where category="high"
        threats = self._collect_threats(categories)

        # STEP 8: Aggregate and deduplicate results
        # Flatten nested recommendation lists into single list
        recommendation_set: List[str] = []
        for rec_list in recommendations.values():
            recommendation_set.extend(rec_list)

        # Prepend grade message (makes it first recommendation)
        if grade_message:
            recommendation_set = grade_message + recommendation_set

        # Fallback: If no recommendations found, use rule-based defaults
        if not recommendation_set:
            recommendation_set = self._recommendations(wallet_data, score)

        # Remove duplicates while preserving order
        recommendation_set = self._deduplicate(recommendation_set)
        threats = self._deduplicate(threats or self._threats(wallet_data, score))

        # STEP 9: Return explainable analysis
        # backend="metta" indicates symbolic reasoning was used
        return PrivacyAnalysis(
            score=score,
            grade=grade,
            recommendations=recommendation_set,
            threats=threats,
            backend="metta",  # Tracks which reasoning engine was used
        )

    def _categorise(self, wallet_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Categorize wallet metrics into low/medium/high buckets.

        **Why Bucketing?**
        Converts continuous numeric values into discrete categories.
        This enables:
        1. Pattern matching in MeTTa (can't match on continuous ranges)
        2. Human-readable reasoning ("low compression" vs "compression=0.23")
        3. Rule simplification (3 rules per metric vs infinite thresholds)

        **Bucket Thresholds** (Research-Based):

        | Metric                   | Low       | Medium    | High      |
        |--------------------------|-----------|-----------|-----------|
        | compression_ratio        | < 0.2     | 0.2-0.5   | > 0.5     |
        | reuse_ratio (inverted)   | < 0.4     | 0.4-0.7   | > 0.7     |
        | unique_counterparties    | < 5       | 5-10      | > 10      |
        | timing_variance (sec)    | < 1800    | 1800-3600 | > 3600    |

        Note: reuse_ratio uses inverted logic (high reuse = "high" category = bad)

        Returns:
            Dict mapping metric names to category strings ("low", "medium", "high")

        Example:
            Input: {"compression_ratio": 0.75, "reuse_ratio": 0.3}
            Output: {"compression_ratio": "high", "reuse_ratio": "low"}
        """
        # Extract raw metric values
        compression_ratio = float(wallet_data.get("compression_ratio", 0.0))
        reuse_ratio = float(wallet_data.get("reuse_ratio", 0.0))
        unique_counterparties = int(wallet_data.get("unique_counterparties", 0))
        timing_variance = float(wallet_data.get("timing_variance", 0.0))

        # Bucket each metric using appropriate thresholds
        categories = {
            # Higher compression = better (normal bucketing)
            "compression_ratio": self._bucket(compression_ratio, (0.2, 0.5)),

            # Higher reuse = worse (inverted bucketing)
            "reuse_ratio": self._bucket_high_bad(reuse_ratio, (0.4, 0.7)),

            # More counterparties = better (normal bucketing)
            "unique_counterparties": self._bucket(unique_counterparties, (5, 10)),

            # Higher variance = better (normal bucketing)
            "timing_variance": self._bucket(timing_variance, (1800, 3600)),
        }
        return categories

    def _bucket(self, value: float, thresholds: Tuple[float, float]) -> str:
        """
        Bucket a value into low/medium/high (higher = better).

        Thresholds define two cut points:
        - value < low_threshold → "low" (bad)
        - low_threshold <= value < high_threshold → "medium" (okay)
        - value >= high_threshold → "high" (good)

        Used for metrics where higher values indicate better privacy:
        - compression_ratio: more compression = better
        - unique_counterparties: more diversity = better
        - timing_variance: more randomness = better

        Args:
            value: Numeric metric value
            thresholds: (low_cutoff, high_cutoff) tuple

        Returns:
            Category string: "low", "medium", or "high"
        """
        low, high = thresholds
        if value < low:
            return "low"  # Below low threshold = poor
        if value < high:
            return "medium"  # Between thresholds = acceptable
        return "high"  # Above high threshold = good

    def _bucket_high_bad(self, value: float, thresholds: Tuple[float, float]) -> str:
        """
        Bucket a value into low/medium/high (INVERTED: higher = worse).

        This is the INVERSE of _bucket():
        - value > high_threshold → "high" (BAD!)
        - low_threshold < value <= high_threshold → "medium" (okay)
        - value <= low_threshold → "low" (good)

        Used for metrics where higher values indicate WORSE privacy:
        - reuse_ratio: high reuse = bad (enables clustering attacks)

        Why invert?
        Makes MeTTa rules consistent: "high" category always means "needs attention"
        - Normal: low compression → "low" category → trigger warning
        - Inverted: high reuse → "high" category → trigger warning

        Args:
            value: Numeric metric value
            thresholds: (low_cutoff, high_cutoff) tuple

        Returns:
            Category string: "low", "medium", or "high"
        """
        low, high = thresholds
        if value > high:
            return "high"  # Above high threshold = BAD (high reuse risk)
        if value > low:
            return "medium"  # Between thresholds = moderate risk
        return "low"  # Below low threshold = GOOD (low reuse)

    def _collect_recommendations(self, categories: Dict[str, str]) -> Dict[str, List[str]]:
        collected: Dict[str, List[str]] = {}
        for metric, category in categories.items():
            recs = self._match_messages(f"(recommend {metric} {category} $msg)", "$msg")
            if recs:
                collected[metric] = recs
        return collected

    def _collect_threats(self, categories: Dict[str, str]) -> List[str]:
        threats: List[str] = []
        for metric, category in categories.items():
            if category == "high":
                threat_msgs = self._match_messages(f"(threat {metric} $msg)", "$msg")
                threats.extend(threat_msgs)
        return threats

    def _deduplicate(self, items: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered


@lru_cache()
def get_knowledge_engine() -> PrivacyKnowledgeEngine:
    return PrivacyKnowledgeEngine()
