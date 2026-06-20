'''
in this file, i have tried to extract the contents of a notion doc using NOTION CLIENT API as well as 
page_id, 
- And then stored that into a txt file!


'''
from notion_client import Client
from typing import List
from dotenv import load_dotenv
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")

notion = Client(auth=NOTION_TOKEN)


def get_all_blocks(block_id: str) -> List[dict]:
    """
    Fetches ALL blocks from a page/block,
    handling Notion pagination automatically.
    """

    all_blocks = []
    cursor = None

    while True:

        response = notion.blocks.children.list(
            block_id=block_id,
            start_cursor=cursor
        )

        all_blocks.extend(response["results"])

        if not response["has_more"]:
            break

        cursor = response["next_cursor"]

    return all_blocks


def extract_rich_text(block: dict) -> str:

    block_type = block["type"]

    if block_type not in block:
        return ""

    rich_text = block[block_type].get(
        "rich_text",
        []
    )

    return "".join(
        item["plain_text"]
        for item in rich_text
    )


def crawl_page(page_id: str, depth: int = 0) -> str:

    blocks = get_all_blocks(page_id)

    content = []

    for block in blocks:

        block_type = block["type"]

        # ----------------------------------
        # Child Page
        # ----------------------------------

        if block_type == "child_page":

            title = block["child_page"]["title"]

            content.append(
                f"\n\n{'='*20}\n"
                f"PAGE: {title}\n"
                f"{'='*20}\n"
            )

            child_page_id = block["id"]

            child_content = crawl_page(
                child_page_id,
                depth + 1
            )

            content.append(child_content)

            continue

        # ----------------------------------
        # Text-like blocks
        # ----------------------------------

        text = extract_rich_text(block)

        if text:

            if block_type.startswith("heading"):

                content.append(
                    f"\n{text}\n"
                )

            elif block_type == "bulleted_list_item":

                content.append(
                    f"• {text}"
                )

            elif block_type == "numbered_list_item":

                content.append(
                    f"1. {text}"
                )

            elif block_type == "quote":

                content.append(
                    f"> {text}"
                )

            elif block_type == "callout":

                content.append(
                    f"[CALLOUT] {text}"
                )

            elif block_type == "code":

                content.append(
                    f"\n```{block['code']['language']}\n"
                    f"{text}\n"
                    f"```\n"
                )

            else:

                content.append(text)

        # ----------------------------------
        # Images
        # ----------------------------------

        if block_type == "image":

            image_data = block["image"]

            if image_data["type"] == "file":
                image_url = image_data["file"]["url"]

            else:
                image_url = image_data["external"]["url"]

            content.append(
                f"[IMAGE] {image_url}"
            )

    return "\n".join(content)


def load_notion_document(root_page_id: str) -> str:
    """
    Entry point.
    Returns the full text content of the page,
    including all nested child pages.
    """

    return crawl_page(root_page_id)


# document_text = load_notion_document(root_page_id="PAGE_ID")
# with open("notion_docs.txt", "w", encoding="utf-8") as f:
#     f.write(document_text)

# print("Saved to notion_docs.txt")