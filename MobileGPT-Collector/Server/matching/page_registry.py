"""Page knowledge registry."""

from typing import Optional

from ..data.models import PageKnowledge, Subtask, UIAttributes


class PageRegistry:
    """Registry for storing and retrieving page knowledge."""

    def __init__(self):
        self._bundles: dict[str, PageKnowledge] = {}

    def add(self, page_knowledge: PageKnowledge) -> None:
        self._bundles[page_knowledge.bundle_id] = page_knowledge

    def get(self, bundle_id: str) -> Optional[PageKnowledge]:
        return self._bundles.get(bundle_id)

    def get_all_bundle_ids(self) -> list[str]:
        return list(self._bundles.keys())

    def get_all(self) -> dict[str, PageKnowledge]:
        return self._bundles.copy()

    def has(self, bundle_id: str) -> bool:
        return bundle_id in self._bundles

    def add_subtask(self, bundle_id: str, subtask: Subtask, keyui_attrs: Optional[list[UIAttributes]] = None) -> None:
        if bundle_id in self._bundles:
            bundle = self._bundles[bundle_id]
            existing_names = [s.name for s in bundle.subtasks]
            if subtask.name not in existing_names:
                bundle.subtasks.append(subtask)
                if keyui_attrs:
                    bundle.keyuis[subtask.name] = keyui_attrs

    def remove(self, bundle_id: str) -> None:
        if bundle_id in self._bundles:
            del self._bundles[bundle_id]

    def clear(self) -> None:
        self._bundles.clear()

    def __len__(self) -> int:
        return len(self._bundles)

    def __contains__(self, bundle_id: str) -> bool:
        return bundle_id in self._bundles

    def to_dict(self) -> dict:
        return {
            bundle_id: {
                "bundle_id": bundle.bundle_id,
                "app_name": bundle.app_name,
                "subtasks": [s.model_dump() for s in bundle.subtasks],
                "keyuis": {name: [ui.to_dict() for ui in attrs] for name, attrs in bundle.keyuis.items()},
                "extra_uis": [ui.to_dict() for ui in bundle.extra_uis],
            }
            for bundle_id, bundle in self._bundles.items()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PageRegistry":
        registry = cls()
        for bundle_id, bundle_data in data.items():
            subtasks = [Subtask(**s) for s in bundle_data.get("subtasks", [])]
            keyuis = {name: [UIAttributes(**a) for a in attrs_list] for name, attrs_list in bundle_data.get("keyuis", {}).items()}
            extra_uis = [UIAttributes(**a) for a in bundle_data.get("extra_uis", [])]
            bundle = PageKnowledge(
                bundle_id=bundle_data.get("bundle_id", bundle_id),
                app_name=bundle_data.get("app_name", ""),
                subtasks=subtasks, keyuis=keyuis, extra_uis=extra_uis
            )
            registry.add(bundle)
        return registry
