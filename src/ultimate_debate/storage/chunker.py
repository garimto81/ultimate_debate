"""Chunking system for efficient context loading."""

from enum import IntEnum
from pathlib import Path


class LoadLevel(IntEnum):
    """Context loading levels for progressive disclosure."""

    METADATA = 0   # ~100 bytes (task_id, status, timestamp)
    SUMMARY = 1    # ~300 bytes (brief summary, consensus %)
    CONCLUSION = 2 # ~800 bytes (final conclusions, agreed items)
    FULL = 3       # ~4000 bytes (full content with analyses)


class ChunkManager:
    """Manage chunked markdown files for efficient context loading."""

    # Chunk markers for delimiting sections in markdown
    MARKERS = {
        "SUMMARY": ("<!-- CHUNK:SUMMARY:START -->", "<!-- CHUNK:SUMMARY:END -->"),
        "CONCLUSION": ("<!-- CHUNK:CONCLUSION:START -->", "<!-- CHUNK:CONCLUSION:END -->"),
        "FULL": ("<!-- CHUNK:FULL:START -->", "<!-- CHUNK:FULL:END -->"),
    }

    def load_level(self, file_path: Path, level: LoadLevel) -> dict[str, str]:
        """Load content at specified level.

        Args:
            file_path: Path to markdown file
            level: Loading level

        Returns:
            dict with keys based on level:
                - METADATA: task_id, status, timestamp
                - SUMMARY: above + summary, consensus_percentage
                - CONCLUSION: above + conclusions, agreed_items
                - FULL: all chunks
        """
        if not file_path.exists():
            return {}

        content = file_path.read_text(encoding="utf-8")

        if level == LoadLevel.METADATA:
            return self._load_metadata(content)
        elif level == LoadLevel.SUMMARY:
            return {**self._load_metadata(content), **self._load_chunk(content, "SUMMARY")}
        elif level == LoadLevel.CONCLUSION:
            return {
                **self._load_metadata(content),
                **self._load_chunk(content, "SUMMARY"),
                **self._load_chunk(content, "CONCLUSION"),
            }
        else:  # FULL
            return {
                **self._load_metadata(content),
                **self._load_chunk(content, "SUMMARY"),
                **self._load_chunk(content, "CONCLUSION"),
                **self._load_chunk(content, "FULL"),
            }

    def _load_metadata(self, content: str) -> dict[str, str]:
        """Extract metadata from markdown frontmatter.

        Args:
            content: Full markdown content

        Returns:
            dict with metadata fields
        """
        # Simple extraction (can be enhanced with frontmatter library)
        lines = content.split("\n")
        metadata = {}

        for line in lines[:20]:  # Check first 20 lines
            if "Created:" in line or "- Created:" in line:
                metadata["timestamp"] = line.split(":", 1)[1].strip()
            elif "Status:" in line or "- Status:" in line:
                metadata["status"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Task:"):
                metadata["task_id"] = line.replace("# Task:", "").strip()

        return metadata

    def _load_chunk(self, content: str, chunk_name: str) -> dict[str, str]:
        """Extract specific chunk from markdown.

        Args:
            content: Full markdown content
            chunk_name: Chunk identifier (SUMMARY, CONCLUSION, FULL)

        Returns:
            dict with chunk content
        """
        if chunk_name not in self.MARKERS:
            return {}

        start_marker, end_marker = self.MARKERS[chunk_name]

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            return {}

        # Extract content between markers
        chunk_content = content[start_idx + len(start_marker) : end_idx].strip()

        return {chunk_name.lower(): chunk_content}

    def write_chunked(
        self, file_path: Path, metadata: dict, summary: str, conclusion: str, full: str
    ) -> None:
        """Write chunked markdown file.

        Args:
            file_path: Target file path
            metadata: Metadata dict (task_id, status, timestamp)
            summary: Summary chunk content
            conclusion: Conclusion chunk content
            full: Full content chunk
        """
        # Build frontmatter
        frontmatter = f"""# Task: {metadata.get('task_id', 'Unknown')}

## Metadata
- Created: {metadata.get('timestamp', 'N/A')}
- Status: {metadata.get('status', 'UNKNOWN')}

"""

        # Build chunked sections
        summary_section = f"""{self.MARKERS['SUMMARY'][0]}
{summary}
{self.MARKERS['SUMMARY'][1]}

"""

        conclusion_section = f"""{self.MARKERS['CONCLUSION'][0]}
{conclusion}
{self.MARKERS['CONCLUSION'][1]}

"""

        full_section = f"""{self.MARKERS['FULL'][0]}
{full}
{self.MARKERS['FULL'][1]}
"""

        # Combine all sections
        content = frontmatter + summary_section + conclusion_section + full_section

        file_path.write_text(content, encoding="utf-8")
