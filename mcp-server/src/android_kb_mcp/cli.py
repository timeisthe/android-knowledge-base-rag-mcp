from __future__ import annotations

import argparse
import json
from typing import Optional, Sequence

from .factory import build_service
from .server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="android-kb-mcp",
        description="Android 面经知识库 RAG 与 MCP Server",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("serve", help="通过配置的 transport 启动 MCP Server")

    ingest = subparsers.add_parser("ingest", help="批量导入指定目录")
    ingest.add_argument("directory", nargs="?", default=".")
    subparsers.add_parser("reindex", help="重建全部向量索引")
    subparsers.add_parser("metadata", help="输出知识库统计信息")

    search = subparsers.add_parser("search", help="从命令行执行语义搜索")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--category")
    search.add_argument("--difficulty")
    search.add_argument("--tag", action="append", dest="tags")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command in {None, "serve"}:
        run_server()
        return

    service = build_service()
    if args.command == "ingest":
        print(service.bulk_ingest(args.directory))
    elif args.command == "reindex":
        service.reindex_all()
        print(json.dumps(service.metadata_summary(), ensure_ascii=False, default=str))
    elif args.command == "metadata":
        print(json.dumps(service.metadata_summary(), ensure_ascii=False, default=str, indent=2))
    elif args.command == "search":
        filters = {
            key: value
            for key, value in {
                "category": args.category,
                "difficulty": args.difficulty,
                "tags": args.tags,
            }.items()
            if value
        }
        print(
            json.dumps(
                service.search_knowledge(args.query, args.top_k, filters),
                ensure_ascii=False,
                default=str,
                indent=2,
            )
        )
