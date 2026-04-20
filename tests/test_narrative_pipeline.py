import unittest

from engines.narrative_pipeline import (
    build_canonical_state,
    build_narrative_plan,
    needs_critic_pass,
    rank_candidates,
    render_pipeline_context,
    retrieve_memory_stack,
    update_narrative_state,
)


class TestNarrativePipeline(unittest.TestCase):
    def test_retrieve_memory_stack(self):
        history = [
            {"role": "user", "content": "We planned to go to the market later."},
            {"role": "assistant", "content": "Yes, the scene is still the town square."},
            {"role": "user", "content": "Actually not true, it was the harbor."},
        ]
        stack = retrieve_memory_stack(history, "harbor plan later", short_limit=1)
        self.assertTrue(stack["short_term"])
        self.assertTrue(stack["episodic"])
        self.assertTrue(stack["semantic"])

    def test_plan_and_rank(self):
        state = build_canonical_state(
            {"name": "A", "personality_type": "Warm", "backstory": "Adventurer", "relationship_score": 12},
            {"current_scene": "Harbor", "narrative_state": {"unresolved_threads": ["Find the map"]}},
            "What do we do next?",
        )
        plan = build_narrative_plan(state, "What do we do next?", "rp")
        ranked = rank_candidates(
            [
                'I do not know.',
                '*I glance at the map.* "Next, we head to the lighthouse and test the old key."',
            ],
            state,
            plan,
            "rp",
        )
        self.assertGreaterEqual(ranked[0]["metrics"]["total"], ranked[1]["metrics"]["total"])
        context = render_pipeline_context(state, {"continuity_flags": [], "episodic": [], "semantic": []}, plan)
        self.assertIn("[TURN PLAN]", context)
        self.assertIn("PRIORITY: Respond to the latest user message first", context)

    def test_planner_prioritizes_latest_message_over_unresolved_thread(self):
        state = build_canonical_state(
            {"name": "A", "personality_type": "Warm", "backstory": "Adventurer", "relationship_score": 12},
            {"current_scene": "Harbor", "narrative_state": {"unresolved_threads": ["Find the map in the lighthouse"]}},
            "How are you feeling right now?",
        )
        plan = build_narrative_plan(state, "How are you feeling right now?", "rp")
        self.assertIn("Directly answer the user's latest message", plan["next_beat"])

    def test_critic_and_state_update(self):
        self.assertTrue(needs_critic_pass("As an AI I cannot do that.", "rp"))
        updated = update_narrative_state({}, "continue", "I will return later with the answer.", 1, "Inn")
        self.assertEqual(updated["current_scene"], "Inn")
        self.assertTrue(updated["unresolved_threads"])


if __name__ == "__main__":
    unittest.main()
