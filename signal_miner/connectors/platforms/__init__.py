"""P12-2 站点级采集适配器包。"""

from signal_miner.connectors.platforms.bilibili_adapter import BilibiliEvidenceAdapter
from signal_miner.connectors.platforms.cnblogs_adapter import CnblogsEvidenceAdapter
from signal_miner.connectors.platforms.generic_adapter import GenericEvidenceAdapter
from signal_miner.connectors.platforms.github_adapter import GitHubEvidenceAdapter
from signal_miner.connectors.platforms.search_adapter import SearchEvidenceAdapter

__all__ = [
    "BilibiliEvidenceAdapter",
    "CnblogsEvidenceAdapter",
    "GenericEvidenceAdapter",
    "GitHubEvidenceAdapter",
    "SearchEvidenceAdapter",
]
