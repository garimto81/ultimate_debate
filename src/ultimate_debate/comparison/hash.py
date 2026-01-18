"""Hash-based comparison using SHA-256."""

import hashlib


class HashComparator:
    """SHA-256 hash-based comparator for exact text matching."""

    def compute_hash(self, text: str) -> str:
        """Compute SHA-256 hash of normalized text.

        Args:
            text: Text to hash

        Returns:
            SHA-256 hash string (hex)
        """
        normalized = self._normalize_text(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def compare(self, hashes: list[str]) -> dict:
        """Compare hashes for exact matches.

        Args:
            hashes: List of hash strings

        Returns:
            dict with keys:
                - unique_hashes: Number of unique hashes
                - all_match: Whether all hashes are identical
                - hash_groups: Dict mapping hash to count
        """
        if not hashes:
            return {
                "unique_hashes": 0,
                "all_match": False,
                "hash_groups": {},
            }

        # Count occurrences of each hash
        hash_groups = {}
        for h in hashes:
            hash_groups[h] = hash_groups.get(h, 0) + 1

        unique_count = len(hash_groups)
        all_match = unique_count == 1

        return {
            "unique_hashes": unique_count,
            "all_match": all_match,
            "hash_groups": hash_groups,
        }

    def _normalize_text(self, text: str) -> str:
        """Normalize text for hashing.

        Args:
            text: Raw text

        Returns:
            Normalized text (lowercase, whitespace collapsed)
        """
        return " ".join(text.lower().strip().split())
