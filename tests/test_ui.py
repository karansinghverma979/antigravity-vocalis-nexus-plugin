"""
Tests for Vocalis Desktop Pet UI component.
Verifies state transitions, vector scaling, click-to-evoke action queue dispatch, and preferences.
"""
import queue
import tempfile
import unittest
from pathlib import Path

from vocalis.ui.pet import VocalisPetUI, PREFS_FILE


class TestVocalisPetUI(unittest.TestCase):
    def test_pet_state_transitions(self):
        q = queue.Queue()
        act_q = queue.Queue()
        pet = VocalisPetUI(event_queue=q, action_queue=act_q)

        # Verify initial state
        self.assertEqual(pet.state, "STANDBY")

        # Test state transitions
        pet.set_state("LISTENING", "🎙️ listening...")
        self.assertEqual(pet.state, "LISTENING")
        self.assertEqual(pet.status_text, "🎙️ listening...")

        pet.set_state("TRANSCRIBING", "⚡ thinking...")
        self.assertEqual(pet.state, "TRANSCRIBING")

        pet.set_state("QUEUED", "✓ Queued", "clean RAM")
        self.assertEqual(pet.state, "QUEUED")
        self.assertEqual(pet.command_preview, "clean RAM")

        pet.set_state("STANDBY", "💤 nexus")
        self.assertEqual(pet.state, "STANDBY")

        pet.root.destroy()

    def test_vector_scaling(self):
        q = queue.Queue()
        pet = VocalisPetUI(event_queue=q)

        # Base dimensions at 1.0 scale
        self.assertEqual(pet.width, 136)
        self.assertEqual(pet.height, 120)

        # Scale up to 1.5
        pet.set_scale(1.5)
        self.assertEqual(pet.scale, 1.5)
        self.assertEqual(pet.width, int(136 * 1.5))
        self.assertEqual(pet.height, int(120 * 1.5))

        # Clamp check: min 0.65, max 2.50
        pet.set_scale(5.0)
        self.assertEqual(pet.scale, 2.50)
        pet.set_scale(0.1)
        self.assertEqual(pet.scale, 0.65)

        pet.root.destroy()

    def test_click_to_evoke_dispatch(self):
        q = queue.Queue()
        act_q = queue.Queue()
        evoked = []

        pet = VocalisPetUI(
            event_queue=q,
            action_queue=act_q,
            on_evoke=lambda: evoked.append(True),
        )

        pet.trigger_evoke()

        # UI state immediately shifts to LISTENING
        self.assertEqual(pet.state, "LISTENING")
        self.assertEqual(pet.status_text, "🎙️ speak now...")

        # Action queue received MANUAL_TRIGGER command
        msg = act_q.get_nowait()
        self.assertEqual(msg.get("cmd"), "MANUAL_TRIGGER")

        # Custom callback triggered
        self.assertEqual(len(evoked), 1)

        pet.root.destroy()


if __name__ == "__main__":
    unittest.main()
