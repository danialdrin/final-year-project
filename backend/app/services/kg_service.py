import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId
from app.db.mongo import get_collection

logger = logging.getLogger(__name__)

class KGService:
    async def build_material_kg(self, analysis_id: ObjectId, extracted_data: Dict[str, Any]):
        skill_nodes_coll = get_collection("skill_nodes")
        kg_edges_coll = get_collection("kg_edges")

        concepts = extracted_data.get("concepts", [])
        relationships = extracted_data.get("relationships", [])

        name_to_id: Dict[str, ObjectId] = {}

        # 1. Upsert skill nodes for each concept
        for c in concepts:
            raw_name = c.get("name", "")
            norm_name = raw_name.strip().lower()
            if not norm_name:
                continue

            existing_node = await skill_nodes_coll.find_one({"name": norm_name})
            if existing_node:
                node_id = existing_node["_id"]
            else:
                new_node_doc = {
                    "name": norm_name,
                    "display_name": raw_name,
                    "description": c.get("definition", ""),
                    "type": "concept",
                    "bloom_level": c.get("bloom_level", "understand"),
                    "parent_id": None,
                    "prerequisite_ids": [],
                    "created_at": datetime.now(timezone.utc)
                }
                res = await skill_nodes_coll.insert_one(new_node_doc)
                node_id = res.inserted_id

            name_to_id[norm_name] = node_id

        # 2. Insert KG Edges
        for rel in relationships:
            from_name = rel.get("from", "").strip().lower()
            to_name = rel.get("to", "").strip().lower()
            relation_type = rel.get("relation", "prerequisite")

            from_id = name_to_id.get(from_name)
            to_id = name_to_id.get(to_name)

            if from_id and to_id and from_id != to_id:
                edge_doc = {
                    "from_node_id": from_id,
                    "to_node_id": to_id,
                    "relation": relation_type,
                    "material_id": analysis_id,
                    "created_at": datetime.now(timezone.utc)
                }
                await kg_edges_coll.insert_one(edge_doc)

                # Update prerequisite_ids if relation is prerequisite
                if relation_type == "prerequisite":
                    await skill_nodes_coll.update_one(
                        {"_id": to_id},
                        {"$addToSet": {"prerequisite_ids": from_id}}
                    )

    async def get_material_kg(self, analysis_id_str: str) -> Dict[str, Any]:
        analysis_id = ObjectId(analysis_id_str)
        kg_edges_coll = get_collection("kg_edges")
        skill_nodes_coll = get_collection("skill_nodes")

        edges_cursor = kg_edges_coll.find({"material_id": analysis_id})
        edges_docs = await edges_cursor.to_list(length=500)

        node_ids = set()
        formatted_edges = []
        for e in edges_docs:
            from_id_str = str(e["from_node_id"])
            to_id_str = str(e["to_node_id"])
            node_ids.add(e["from_node_id"])
            node_ids.add(e["to_node_id"])
            formatted_edges.append({
                "edge_id": str(e["_id"]),
                "from_node_id": from_id_str,
                "to_node_id": to_id_str,
                "relation": e.get("relation", "prerequisite"),
                "material_id": analysis_id_str
            })

        # Also get all concept nodes linked to this analysis
        analyses_coll = get_collection("analyses")
        analysis_doc = await analyses_coll.find_one({"_id": analysis_id})
        if analysis_doc:
            concepts = analysis_doc.get("extracted_data", {}).get("concepts", [])
            for c in concepts:
                norm_name = c.get("name", "").strip().lower()
                node_doc = await skill_nodes_coll.find_one({"name": norm_name})
                if node_doc:
                    node_ids.add(node_doc["_id"])

        nodes_cursor = skill_nodes_coll.find({"_id": {"$in": list(node_ids)}})
        nodes_docs = await nodes_cursor.to_list(length=500)

        formatted_nodes = [
            {
                "node_id": str(n["_id"]),
                "name": n["name"],
                "display_name": n.get("display_name", n["name"]),
                "description": n.get("description"),
                "type": n.get("type", "concept"),
                "bloom_level": n.get("bloom_level"),
                "parent_id": str(n["parent_id"]) if n.get("parent_id") else None,
                "prerequisite_ids": [str(pid) for pid in n.get("prerequisite_ids", [])]
            }
            for n in nodes_docs
        ]

        return {
            "analysis_id": analysis_id_str,
            "nodes": formatted_nodes,
            "edges": formatted_edges
        }

kg_service = KGService()
