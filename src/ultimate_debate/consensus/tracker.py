"""Convergence tracking for debate rounds."""


class ConvergenceTracker:
    """Track consensus convergence over multiple rounds."""

    def __init__(self, window_size: int = 3):
        """Initialize convergence tracker.

        Args:
            window_size: Number of recent rounds to consider for convergence detection
        """
        self.history: list[float] = []
        self.window_size = window_size

    def add_score(self, score: float) -> None:
        """Add consensus score from current round.

        Args:
            score: Consensus percentage (0-1)
        """
        self.history.append(score)

    def is_converging(self) -> bool:
        """Check if consensus scores are converging (increasing trend).

        Returns:
            True if recent scores show upward trend
        """
        if len(self.history) < self.window_size:
            return False

        # Get recent window
        recent = self.history[-self.window_size :]

        # Check if monotonically increasing
        return all(recent[i + 1] > recent[i] for i in range(len(recent) - 1))

    def is_diverging(self) -> bool:
        """Check if consensus scores are diverging (decreasing trend).

        Returns:
            True if recent scores show downward trend
        """
        if len(self.history) < self.window_size:
            return False

        # Get recent window
        recent = self.history[-self.window_size :]

        # Check if monotonically decreasing
        return all(recent[i + 1] < recent[i] for i in range(len(recent) - 1))

    def is_stable(self, tolerance: float = 0.05) -> bool:
        """Check if consensus scores are stable (within tolerance).

        Args:
            tolerance: Maximum allowed variation for stability

        Returns:
            True if recent scores vary within tolerance
        """
        if len(self.history) < self.window_size:
            return False

        # Get recent window
        recent = self.history[-self.window_size :]

        # Check variance
        mean = sum(recent) / len(recent)
        max_deviation = max(abs(s - mean) for s in recent)

        return max_deviation <= tolerance

    def get_trend(self) -> str:
        """Get current convergence trend.

        Returns:
            Trend string: "CONVERGING" | "DIVERGING" | "STABLE" | "UNKNOWN"
        """
        if self.is_converging():
            return "CONVERGING"
        elif self.is_diverging():
            return "DIVERGING"
        elif self.is_stable():
            return "STABLE"
        else:
            return "UNKNOWN"

    def get_statistics(self) -> dict:
        """Get convergence statistics.

        Returns:
            dict with keys:
                - total_rounds: Number of tracked rounds
                - current_score: Latest consensus score
                - trend: Current trend
                - history: Full score history
        """
        return {
            "total_rounds": len(self.history),
            "current_score": self.history[-1] if self.history else 0.0,
            "trend": self.get_trend(),
            "history": self.history,
        }
