"""MobileGPT-V2 compatible memory adapter.

Stores collected data in the same format as MobileGPT-V2's auto explore,
allowing seamless data reuse between MobileGPT-Collector and MobileGPT-V2 Task mode.

Directory structure:
    memory/{app_name}/
    ├── pages.csv               (index, available_subtasks, trigger_uis, extra_uis, screen, summary)
    ├── hierarchy.csv           (index, screen, embedding)
    ├── subtask_graph.json      (nodes, edges)
    └── pages/
        └── {page_index}/
            ├── available_subtasks.csv  (name, description, parameters, trigger_ui_index, exploration)
            ├── subtasks.csv            (name, description, guideline, trigger_ui_index, start_page, end_page, parameters, example)
            ├── actions.csv             (subtask_name, trigger_ui_index, step, start_page, end_page, action, description, guideline, example)
            └── screen/
                ├── screenshot.jpg
                ├── raw.xml
                ├── parsed.xml
                ├── hierarchy.xml
                ├── encoded.xml
                └── pretty.xml
"""

import json
import os
import shutil
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from ..utils.embedding import get_openai_embedding, cosine_similarity, safe_literal_eval


# CSV column definitions
PAGES_COLUMNS = ["index", "available_subtasks", "trigger_uis", "extra_uis", "screen", "summary"]
HIERARCHY_COLUMNS = ["index", "screen", "embedding"]
AVAILABLE_SUBTASKS_COLUMNS = ["name", "description", "parameters", "trigger_ui_index", "exploration"]
SUBTASKS_COLUMNS = ["name", "description", "guideline", "trigger_ui_index", "start_page", "end_page", "parameters", "example"]
ACTIONS_COLUMNS = ["subtask_name", "trigger_ui_index", "step", "start_page", "end_page", "action", "description", "guideline", "example"]


def _init_csv(path: str, columns: list[str]) -> pd.DataFrame:
    """Initialize or load a CSV file."""
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    return pd.DataFrame(columns=columns)


class ExploreMemoryAdapter:
    """Stores collected data in MobileGPT-V2 memory format."""

    def __init__(self, memory_dir: str, app_name: str):
        self.memory_dir = memory_dir
        self.app_name = app_name
        self.base_path = os.path.join(memory_dir, app_name)
        self.pages_csv_path = os.path.join(self.base_path, "pages.csv")
        self.hierarchy_csv_path = os.path.join(self.base_path, "hierarchy.csv")
        self.subtask_graph_path = os.path.join(self.base_path, "subtask_graph.json")
        self.pages_dir = os.path.join(self.base_path, "pages")

        self.pages_db: Optional[pd.DataFrame] = None
        self.hierarchy_db: Optional[pd.DataFrame] = None
        self.subtask_graph: dict = {"nodes": [], "edges": []}

        # Per-page managers keyed by page_index
        self._page_dbs: dict[int, dict] = {}

    def initialize(self) -> None:
        """Create directory structure and load existing data."""
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(self.pages_dir, exist_ok=True)

        self.pages_db = _init_csv(self.pages_csv_path, PAGES_COLUMNS)
        self.hierarchy_db = _init_csv(self.hierarchy_csv_path, HIERARCHY_COLUMNS)

        # Load hierarchy embeddings
        if "embedding" in self.hierarchy_db.columns and len(self.hierarchy_db) > 0:
            self.hierarchy_db["embedding"] = self.hierarchy_db["embedding"].apply(safe_literal_eval)

        # Load subtask graph
        if os.path.exists(self.subtask_graph_path):
            try:
                with open(self.subtask_graph_path, "r", encoding="utf-8") as f:
                    self.subtask_graph = json.load(f)
            except Exception:
                self.subtask_graph = {"nodes": [], "edges": []}

        logger.info(f"ExploreMemory initialized: {self.base_path}")

    # ─── Page Operations ─────────────────────────────────────────

    def add_page(
        self,
        page_index: int,
        available_subtasks: list[dict],
        trigger_uis: dict,
        extra_uis: list,
        parsed_xml: str,
        hierarchy_xml: str,
        encoded_xml: str,
        screenshot_path: str,
        raw_xml: str,
        pretty_xml: str,
        screen_num: int,
    ) -> None:
        """Add a new page to memory (pages.csv + hierarchy.csv + per-page files)."""
        # 1. Generate embedding for hierarchy XML
        try:
            embedding = get_openai_embedding(hierarchy_xml)
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            embedding = []

        # 2. Update pages.csv
        new_row = {
            "index": page_index,
            "available_subtasks": json.dumps(available_subtasks, ensure_ascii=False),
            "trigger_uis": json.dumps(trigger_uis, ensure_ascii=False),
            "extra_uis": json.dumps(extra_uis, ensure_ascii=False),
            "screen": parsed_xml,
            "summary": "",
        }
        self.pages_db = pd.concat(
            [self.pages_db, pd.DataFrame([new_row])], ignore_index=True
        )
        self.pages_db.to_csv(self.pages_csv_path, index=False)

        # 3. Update hierarchy.csv
        hierarchy_row = {
            "index": page_index,
            "screen": hierarchy_xml,
            "embedding": str(embedding),
        }
        self.hierarchy_db = pd.concat(
            [self.hierarchy_db, pd.DataFrame([hierarchy_row])], ignore_index=True
        )
        self.hierarchy_db.to_csv(self.hierarchy_csv_path, index=False)
        # Reload embedding as array
        self.hierarchy_db["embedding"] = self.hierarchy_db["embedding"].apply(safe_literal_eval)

        # 4. Create per-page directory and files
        page_dir = os.path.join(self.pages_dir, str(page_index))
        screen_dir = os.path.join(page_dir, "screen")
        os.makedirs(screen_dir, exist_ok=True)

        # available_subtasks.csv
        for s in available_subtasks:
            if "exploration" not in s:
                s["exploration"] = "unexplored"
        avail_df = pd.DataFrame(available_subtasks, columns=AVAILABLE_SUBTASKS_COLUMNS)
        avail_df.to_csv(os.path.join(page_dir, "available_subtasks.csv"), index=False)

        # Initialize empty subtasks.csv and actions.csv
        pd.DataFrame(columns=SUBTASKS_COLUMNS).to_csv(
            os.path.join(page_dir, "subtasks.csv"), index=False
        )
        pd.DataFrame(columns=ACTIONS_COLUMNS).to_csv(
            os.path.join(page_dir, "actions.csv"), index=False
        )

        # Save screen files
        self._write(os.path.join(screen_dir, "raw.xml"), raw_xml)
        self._write(os.path.join(screen_dir, "parsed.xml"), parsed_xml)
        self._write(os.path.join(screen_dir, "hierarchy.xml"), hierarchy_xml)
        self._write(os.path.join(screen_dir, "encoded.xml"), encoded_xml)
        self._write(os.path.join(screen_dir, "pretty.xml"), pretty_xml)
        if screenshot_path and os.path.exists(screenshot_path):
            shutil.copy2(screenshot_path, os.path.join(screen_dir, "screenshot.jpg"))

        # Add node to subtask graph
        if page_index not in self.subtask_graph["nodes"]:
            self.subtask_graph["nodes"].append(page_index)
            self.subtask_graph["nodes"].sort()
            self._save_subtask_graph()

        logger.debug(f"ExploreMemory: added page {page_index}")

    def update_summary(self, page_index: int, summary: str) -> None:
        """Update page summary in pages.csv."""
        if self.pages_db is None:
            return
        mask = self.pages_db["index"] == page_index
        if mask.any():
            self.pages_db.loc[mask, "summary"] = summary
            self.pages_db.to_csv(self.pages_csv_path, index=False)

    # ─── Subtask Operations ──────────────────────────────────────

    def mark_subtask_explored(
        self,
        page_index: int,
        subtask_name: str,
        trigger_ui_index: int,
        action: dict,
        start_page: int,
        end_page: int,
        parsed_xml: str,
        guideline: str = "",
    ) -> None:
        """Mark subtask as explored and record in subtasks.csv + actions.csv."""
        page_dir = os.path.join(self.pages_dir, str(page_index))
        if not os.path.exists(page_dir):
            logger.warning(f"Page dir not found: {page_dir}")
            return

        # 1. Update available_subtasks.csv
        avail_path = os.path.join(page_dir, "available_subtasks.csv")
        avail_db = _init_csv(avail_path, AVAILABLE_SUBTASKS_COLUMNS)
        cond = avail_db["name"] == subtask_name
        if trigger_ui_index >= 0:
            cond = cond & (avail_db["trigger_ui_index"] == trigger_ui_index)
        if cond.any():
            avail_db.loc[cond, "exploration"] = "explored"
            avail_db.to_csv(avail_path, index=False)

        # 2. Get subtask data from available_subtasks
        desc = ""
        params = "{}"
        if cond.any():
            row = avail_db[cond].iloc[0]
            desc = str(row.get("description", ""))
            params = str(row.get("parameters", "{}"))

        # 3. Save to subtasks.csv
        subtask_path = os.path.join(page_dir, "subtasks.csv")
        subtask_db = _init_csv(subtask_path, SUBTASKS_COLUMNS)
        dup = subtask_db["name"] == subtask_name
        if trigger_ui_index >= 0:
            dup = dup & (subtask_db["trigger_ui_index"] == trigger_ui_index)
        if not dup.any():
            new_subtask = {
                "name": subtask_name,
                "description": desc,
                "guideline": guideline,
                "trigger_ui_index": trigger_ui_index,
                "start_page": start_page,
                "end_page": end_page,
                "parameters": params,
                "example": "{}",
            }
            subtask_db = pd.concat(
                [subtask_db, pd.DataFrame([new_subtask])], ignore_index=True
            )
            subtask_db.to_csv(subtask_path, index=False)

        # 4. Save to actions.csv
        action_path = os.path.join(page_dir, "actions.csv")
        action_db = _init_csv(action_path, ACTIONS_COLUMNS)

        # Click action (step 0)
        click_row = {
            "subtask_name": subtask_name,
            "trigger_ui_index": trigger_ui_index,
            "step": 0,
            "start_page": start_page,
            "end_page": end_page,
            "action": json.dumps(action, ensure_ascii=False),
            "description": "",
            "guideline": guideline,
            "example": "{}",
        }
        action_db = pd.concat(
            [action_db, pd.DataFrame([click_row])], ignore_index=True
        )

        # Finish action (step 1)
        finish_row = {
            "subtask_name": subtask_name,
            "trigger_ui_index": trigger_ui_index,
            "step": 1,
            "start_page": end_page,
            "end_page": end_page,
            "action": json.dumps({"name": "finish", "parameters": {}}, ensure_ascii=False),
            "description": "",
            "guideline": "",
            "example": "{}",
        }
        action_db = pd.concat(
            [action_db, pd.DataFrame([finish_row])], ignore_index=True
        )
        action_db.to_csv(action_path, index=False)

    def update_end_page(
        self,
        page_index: int,
        subtask_name: str,
        trigger_ui_index: int,
        end_page: int,
    ) -> None:
        """Update end_page for a subtask in subtasks.csv and actions.csv."""
        page_dir = os.path.join(self.pages_dir, str(page_index))
        if not os.path.exists(page_dir):
            return

        # Update subtasks.csv
        subtask_path = os.path.join(page_dir, "subtasks.csv")
        subtask_db = _init_csv(subtask_path, SUBTASKS_COLUMNS)
        cond = subtask_db["name"] == subtask_name
        if trigger_ui_index >= 0:
            cond = cond & (subtask_db["trigger_ui_index"] == trigger_ui_index)
        if cond.any():
            subtask_db.loc[cond, "end_page"] = end_page
            subtask_db.to_csv(subtask_path, index=False)

        # Update actions.csv
        action_path = os.path.join(page_dir, "actions.csv")
        action_db = _init_csv(action_path, ACTIONS_COLUMNS)
        a_cond = (action_db["subtask_name"] == subtask_name) & (action_db["end_page"] == -1)
        if trigger_ui_index >= 0:
            a_cond = a_cond & (action_db["trigger_ui_index"] == trigger_ui_index)
        if a_cond.any():
            action_db.loc[a_cond, "end_page"] = end_page
            # Also update finish action start_page
            for idx in action_db[a_cond].index:
                act_str = str(action_db.loc[idx, "action"])
                if '"name": "finish"' in act_str or "'name': 'finish'" in act_str:
                    action_db.loc[idx, "start_page"] = end_page
            action_db.to_csv(action_path, index=False)

    def update_guideline(
        self,
        page_index: int,
        subtask_name: str,
        trigger_ui_index: int,
        guideline: str,
    ) -> None:
        """Update guideline for a subtask's action in actions.csv, then aggregate to subtasks.csv."""
        page_dir = os.path.join(self.pages_dir, str(page_index))
        if not os.path.exists(page_dir):
            return

        # Update actions.csv guideline for step 0
        action_path = os.path.join(page_dir, "actions.csv")
        action_db = _init_csv(action_path, ACTIONS_COLUMNS)
        cond = (action_db["subtask_name"] == subtask_name) & (action_db["step"] == 0)
        if trigger_ui_index >= 0:
            cond = cond & (action_db["trigger_ui_index"] == trigger_ui_index)
        if cond.any():
            action_db.loc[cond, "guideline"] = guideline
            action_db.to_csv(action_path, index=False)

        # Aggregate action guidelines to subtask guideline
        subtask_path = os.path.join(page_dir, "subtasks.csv")
        subtask_db = _init_csv(subtask_path, SUBTASKS_COLUMNS)
        s_cond = subtask_db["name"] == subtask_name
        if trigger_ui_index >= 0:
            s_cond = s_cond & (subtask_db["trigger_ui_index"] == trigger_ui_index)
        if s_cond.any():
            subtask_db.loc[s_cond, "guideline"] = guideline
            subtask_db.to_csv(subtask_path, index=False)

    # ─── Transition / Subtask Graph ──────────────────────────────

    def add_transition(
        self,
        from_page: int,
        to_page: int,
        subtask_name: str,
        trigger_ui_index: int,
        action_sequence: Optional[list[dict]] = None,
    ) -> None:
        """Add transition edge to subtask graph."""
        if from_page == to_page:
            return

        edge = {
            "from_page": from_page,
            "to_page": to_page,
            "subtask": subtask_name,
            "trigger_ui_index": trigger_ui_index,
            "action_sequence": action_sequence or [],
            "explored": True,
        }

        if not self._edge_exists(edge):
            for p in (from_page, to_page):
                if p not in self.subtask_graph["nodes"]:
                    self.subtask_graph["nodes"].append(p)
            self.subtask_graph["nodes"].sort()
            self.subtask_graph["edges"].append(edge)
            self._save_subtask_graph()

    # ─── Page Search ─────────────────────────────────────────────

    def search_page(self, hierarchy_xml: str, threshold: float = 0.95) -> tuple[int, float]:
        """Search for matching page using embedding cosine similarity.

        Returns: (page_index, similarity) or (-1, 0.0) if no match.
        """
        if self.hierarchy_db is None or len(self.hierarchy_db) == 0:
            return -1, 0.0

        try:
            new_embedding = np.array(get_openai_embedding(hierarchy_xml))
        except Exception as e:
            logger.warning(f"Embedding search failed: {e}")
            return -1, 0.0

        best_idx = -1
        best_sim = 0.0
        for _, row in self.hierarchy_db.iterrows():
            emb = row.get("embedding")
            if emb is None:
                continue
            emb_arr = np.array(emb) if not isinstance(emb, np.ndarray) else emb
            sim = cosine_similarity(new_embedding, emb_arr)
            if sim > best_sim:
                best_sim = sim
                best_idx = int(row["index"])

        if best_sim >= threshold:
            return best_idx, best_sim
        return -1, 0.0

    # ─── Internal ────────────────────────────────────────────────

    def _edge_exists(self, edge: dict) -> bool:
        for existing in self.subtask_graph.get("edges", []):
            if (
                existing["from_page"] == edge["from_page"]
                and existing["to_page"] == edge["to_page"]
                and existing["subtask"] == edge["subtask"]
                and existing["trigger_ui_index"] == edge["trigger_ui_index"]
            ):
                return True
        return False

    def _save_subtask_graph(self) -> None:
        try:
            with open(self.subtask_graph_path, "w", encoding="utf-8") as f:
                json.dump(self.subtask_graph, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save subtask graph: {e}")

    @staticmethod
    def _write(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
