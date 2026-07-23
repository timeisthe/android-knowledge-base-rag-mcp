import asyncio
import json
from pathlib import Path

from pydantic import AnyUrl

from android_kb_mcp import server
from android_kb_mcp.embeddings import LocalHashEmbeddingProvider
from android_kb_mcp.repository import MarkdownRepository
from android_kb_mcp.service import KnowledgeService
from android_kb_mcp.vector_store import InMemoryVectorStore


def test_server_registers_expected_tools_and_resources() -> None:
    expected_tools = {
        "search_knowledge",
        "get_document",
        "create_document",
        "update_document",
        "delete_document",
        "append_to_section",
        "list_documents",
        "bulk_ingest",
        "reindex_all",
    }

    async def registered_contract():
        tools = {tool.name for tool in await server.mcp.list_tools()}
        resources = {str(resource.uri) for resource in await server.mcp.list_resources()}
        templates = {
            template.uriTemplate
            for template in await server.mcp.list_resource_templates()
        }
        return tools, resources, templates

    tools, resources, templates = asyncio.run(registered_contract())
    assert tools == expected_tools
    assert resources == {"knowledge://metadata", "knowledge://tags"}
    assert templates == {
        "knowledge://documents/{category}",
        "knowledge://document/{file_path}",
    }


def test_encoded_document_resource_path(tmp_path: Path) -> None:
    service = KnowledgeService(
        MarkdownRepository(tmp_path),
        LocalHashEmbeddingProvider(dimensions=32),
        InMemoryVectorStore(),
    )
    service.create_document(
        "android/four-components/activity.md",
        "# Activity\n\n## 概述\n生命周期",
        {"title": "Activity", "category": "android", "tags": ["高频"]},
    )
    previous = server._service
    server._service = service
    try:
        contents = asyncio.run(
            server.mcp.read_resource(
                AnyUrl(
                    "knowledge://document/"
                    "android%2Ffour-components%2Factivity.md"
                )
            )
        )
    finally:
        server._service = previous

    payload = json.loads(contents[0].content)
    assert payload["file_path"] == "android/four-components/activity.md"
