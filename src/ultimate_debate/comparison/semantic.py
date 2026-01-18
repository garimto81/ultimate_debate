"""Semantic comparison using TF-IDF."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SemanticComparator:
    """TF-IDF based semantic similarity comparator."""

    def __init__(self, threshold: float = 0.9):
        """Initialize semantic comparator.

        Args:
            threshold: Similarity threshold for considering texts as similar (0-1)
        """
        self.threshold = threshold
        self.vectorizer = TfidfVectorizer()

    def compare(self, texts: list[str]) -> dict:
        """Compare texts using TF-IDF cosine similarity.

        Args:
            texts: List of text strings to compare

        Returns:
            dict with keys:
                - similarity_matrix: Pairwise similarity scores
                - max_similarity: Maximum similarity score
                - is_similar: Whether all texts are similar above threshold
                - clusters: Grouped similar texts
        """
        if len(texts) < 2:
            return {
                "similarity_matrix": [],
                "max_similarity": 0.0,
                "is_similar": False,
                "clusters": [],
            }

        # Compute TF-IDF vectors
        tfidf_matrix = self.vectorizer.fit_transform(texts)

        # Compute pairwise cosine similarity
        similarity_matrix = cosine_similarity(tfidf_matrix)

        # Extract max similarity (excluding diagonal)
        n = len(texts)
        max_similarity = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                if similarity_matrix[i][j] > max_similarity:
                    max_similarity = similarity_matrix[i][j]

        # Check if all texts are similar
        is_similar = max_similarity >= self.threshold

        # Cluster similar texts
        clusters = self._cluster_texts(texts, similarity_matrix)

        return {
            "similarity_matrix": similarity_matrix.tolist(),
            "max_similarity": float(max_similarity),
            "is_similar": is_similar,
            "clusters": clusters,
        }

    def _cluster_texts(self, texts: list[str], similarity_matrix) -> list[list[int]]:
        """Cluster texts based on similarity threshold.

        Args:
            texts: Original text list
            similarity_matrix: Pairwise similarity matrix

        Returns:
            List of clusters (each cluster is a list of text indices)
        """
        n = len(texts)
        visited = [False] * n
        clusters = []

        for i in range(n):
            if visited[i]:
                continue

            cluster = [i]
            visited[i] = True

            for j in range(i + 1, n):
                if not visited[j] and similarity_matrix[i][j] >= self.threshold:
                    cluster.append(j)
                    visited[j] = True

            clusters.append(cluster)

        return clusters
