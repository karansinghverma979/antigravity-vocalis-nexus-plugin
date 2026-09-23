"""
Vocalis-Nexus Desktop Pet & Floating HUD.

A tiny, zero-freeze, always-on-top companion widget that lives on your desktop.
Renders live animated states:
- STANDBY: Sleeping / relaxed cat (gentle breathing animation, waiting for wake-word)
- LISTENING: Awake, electric glowing cyan eyes, perked ears, dancing audio bars
- TRANSCRIBING: Thoughtful purple aura, spinning / pulsing thinking dots
- QUEUED: Happy wink, emerald green badge, shows transcribed command

Key Capabilities:
1. Click-to-Evoke: Left-click anywhere on the pet to instantly trigger listening (0ms delay).
2. Adjustable Size: Zoom in/out via Mouse Wheel (65% to 250%) or right-click preset sizes.
3. Persistent State: Saves scale and desktop position across restarts.
4. Smooth Dragging: Freely drag anywhere across screens.
5. Zero CPU (<0.2%), 100% standard library (Tkinter).
"""
from __future__ import annotations

import json
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

PREFS_FILE = Path.home() / ".gemini" / "config" / "vocalis_pet.json"


class VocalisPetUI:
    BASE_WIDTH = 136
    BASE_HEIGHT = 120

    # Color Palette
    BG_CHROMA = "#010101"        # Transparent key
    CARD_BG = "#0f131f"          # Dark glass card
    CARD_BORDER_IDLE = "#1e263d"
    CARD_BORDER_LISTEN = "#00f0ff"
    CARD_BORDER_THINK = "#a855f7"
    CARD_BORDER_SUCCESS = "#10b981"

    CAT_BODY = "#1e2538"
    CAT_INNER_EAR = "#f472b6"
    CAT_NOSE = "#fb7185"

    def __init__(
        self,
        event_queue: Optional[queue.Queue] = None,
        action_queue: Optional[queue.Queue] = None,
        on_evoke: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
    ):
        self.queue = event_queue or queue.Queue()
        self.action_queue = action_queue
        self.on_evoke = on_evoke
        self.on_close = on_close

        # Size scaling (default 1.0 = 136x120)
        self.scale: float = 1.0
        self.width = self.BASE_WIDTH
        self.height = self.BASE_HEIGHT

        self.root = tk.Tk()
        self.root.title("Vocalis Sentinel")

        # Frameless & Always on top
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # Transparent Chroma Key on Windows
        try:
            self.root.attributes("-transparentcolor", self.BG_CHROMA)
        except Exception:
            pass

        # Load saved scale and position preferences
        pref_x, pref_y = self._load_preferences()

        # Fallback position: bottom-left corner of screen (above taskbar)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = pref_x if pref_x is not None else 24
        pos_y = pref_y if pref_y is not None else max(40, screen_h - self.height - 70)
        self.root.geometry(f"{self.width}x{self.height}+{pos_x}+{pos_y}")

        # Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.BG_CHROMA,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)

        # State tracking
        self.state = "STANDBY"   # STANDBY, LISTENING, TRANSCRIBING, QUEUED
        self.status_text = "💤 nexus"
        self.command_preview = ""
        self.anim_tick = 0

        # Mouse interaction (Drag vs Click-to-Evoke)
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_root_x = 0
        self._drag_root_y = 0
        self._dragged = False

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", lambda e: self.trigger_evoke())

        # Mouse Wheel Zoom
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.adjust_scale(0.1))
        self.canvas.bind("<Button-5>", lambda e: self.adjust_scale(-0.1))

        # Right-click context menu
        self._init_context_menu()
        self.canvas.bind("<Button-3>", self._show_context_menu)

        # Start animation & queue polling loops
        self._schedule_animation()
        self._poll_queue()

    # -------------------------------------------------------------
    # Scale Helpers
    # -------------------------------------------------------------
    def S(self, val: float | int) -> int:
        """Scale integer value proportionally with current scale."""
        return max(1, int(round(val * self.scale)))

    def Sf(self, val: float) -> float:
        """Scale floating point value proportionally with current scale."""
        return val * self.scale

    def set_scale(self, new_scale: float) -> None:
        """Set scale factor (0.65 to 2.50) and resize window."""
        new_scale = max(0.65, min(2.50, round(new_scale, 2)))
        if abs(new_scale - self.scale) < 0.01:
            return
        self.scale = new_scale
        self.width = self.S(self.BASE_WIDTH)
        self.height = self.S(self.BASE_HEIGHT)

        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"{self.width}x{self.height}+{cur_x}+{cur_y}")
        self.canvas.config(width=self.width, height=self.height)
        self._save_preferences()

    def adjust_scale(self, delta: float) -> None:
        """Increment or decrement scale by delta."""
        self.set_scale(self.scale + delta)

    def _on_mouse_wheel(self, event) -> None:
        """Handle mouse wheel zooming."""
        if hasattr(event, "delta") and event.delta:
            if event.delta > 0:
                self.adjust_scale(0.1)
            else:
                self.adjust_scale(-0.1)

    # -------------------------------------------------------------
    # Preferences Persistence (Size & Position)
    # -------------------------------------------------------------
    def _load_preferences(self) -> tuple[Optional[int], Optional[int]]:
        try:
            if PREFS_FILE.exists():
                data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
                saved_scale = float(data.get("scale", 1.0))
                self.scale = max(0.65, min(2.50, saved_scale))
                self.width = int(round(self.BASE_WIDTH * self.scale))
                self.height = int(round(self.BASE_HEIGHT * self.scale))
                px = data.get("pos_x")
                py = data.get("pos_y")
                return (int(px) if px is not None else None, int(py) if py is not None else None)
        except Exception:
            pass
        return None, None

    def _save_preferences(self) -> None:
        try:
            PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "scale": self.scale,
                "pos_x": self.root.winfo_x(),
                "pos_y": self.root.winfo_y(),
                "updated_at": time.time(),
            }
            PREFS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # -------------------------------------------------------------
    # Mouse & Evoke Interaction
    # -------------------------------------------------------------
    def _on_press(self, event) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._drag_root_x = event.x_root
        self._drag_root_y = event.y_root
        self._dragged = False

    def _on_motion(self, event) -> None:
        dist = ((event.x_root - self._drag_root_x) ** 2 + (event.y_root - self._drag_root_y) ** 2) ** 0.5
        if dist > 6:
            self._dragged = True
            deltax = event.x - self._drag_start_x
            deltay = event.y - self._drag_start_y
            new_x = self.root.winfo_x() + deltax
            new_y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{new_x}+{new_y}")

    def _on_release(self, event) -> None:
        if self._dragged:
            self._save_preferences()
        else:
            # Check if clicked on close icon (top-right corner)
            close_zone = self.S(20)
            if event.x >= self.width - close_zone and event.y <= close_zone:
                self._quit()
            else:
                # Instant Click-to-Evoke!
                self.trigger_evoke()

    def trigger_evoke(self) -> None:
        """Immediately trigger listening mode upon click or external signal."""
        # 1. Immediate visual feedback (<1ms)
        self.set_state("LISTENING", text="🎙️ speak now...")

        # 2. Inform worker via action queue if present
        if self.action_queue:
            try:
                self.action_queue.put_nowait({"cmd": "MANUAL_TRIGGER"})
            except Exception:
                pass

        # 3. Fire custom callback if provided
        if self.on_evoke:
            try:
                self.on_evoke()
            except Exception:
                pass

    # -------------------------------------------------------------
    # Context Menu
    # -------------------------------------------------------------
    def _init_context_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=0, bg="#131722", fg="#e2e8f0", activebackground="#2563eb")
        self.menu.add_command(label="🎙️ Evoke / Listen Now", command=self.trigger_evoke)
        self.menu.add_separator()

        # Size Presets Submenu
        self.size_menu = tk.Menu(self.menu, tearoff=0, bg="#131722", fg="#e2e8f0", activebackground="#2563eb")
        self.size_menu.add_command(label="Mini (70%)", command=lambda: self.set_scale(0.70))
        self.size_menu.add_command(label="Standard (100%)", command=lambda: self.set_scale(1.0))
        self.size_menu.add_command(label="Medium (135%)", command=lambda: self.set_scale(1.35))
        self.size_menu.add_command(label="Large (170%)", command=lambda: self.set_scale(1.70))
        self.size_menu.add_command(label="Jumbo (220%)", command=lambda: self.set_scale(2.20))
        self.size_menu.add_separator()
        self.size_menu.add_command(label="Zoom In (+10%)", command=lambda: self.adjust_scale(0.10))
        self.size_menu.add_command(label="Zoom Out (-10%)", command=lambda: self.adjust_scale(-0.10))
        self.menu.add_cascade(label="📏 Pet Size (Mouse Wheel)", menu=self.size_menu)

        self.menu.add_separator()
        self.menu.add_command(label="🔊 Test Chime", command=self._test_chime)
        self.menu.add_command(label="🔄 Reset Position (Bottom-Left)", command=self._reset_position)
        self.menu.add_separator()
        self.menu.add_command(label="❌ Exit Sentinel", command=self._quit)

    def _show_context_menu(self, event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _reset_position(self) -> None:
        screen_h = self.root.winfo_screenheight()
        pos_y = max(40, screen_h - self.height - 70)
        self.root.geometry(f"{self.width}x{self.height}+24+{pos_y}")
        self._save_preferences()

    def _test_chime(self) -> None:
        try:
            from vocalis.tools.notifications import play_wake_chime
            threading.Thread(target=play_wake_chime, daemon=True).start()
        except Exception:
            pass

    def _quit(self) -> None:
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.root.destroy()
        sys.exit(0)

    # -------------------------------------------------------------
    # State & Event Management
    # -------------------------------------------------------------
    def set_state(self, new_state: str, text: str = "", command: str = "") -> None:
        self.state = new_state
        if text:
            self.status_text = text
        if command:
            self.command_preview = command

    def _poll_queue(self) -> None:
        """Read state changes sent from audio worker thread."""
        try:
            while True:
                msg = self.queue.get_nowait()
                if isinstance(msg, dict):
                    action = msg.get("state")
                    txt = msg.get("text", "")
                    cmd = msg.get("command", "")
                    if action:
                        self.set_state(action, txt, cmd)
                elif msg == "QUIT":
                    self._quit()
                    return
        except queue.Empty:
            pass
        finally:
            self.root.after(40, self._poll_queue)

    # -------------------------------------------------------------
    # Scale-Aware Vector Canvas Rendering Engine
    # -------------------------------------------------------------
    def _schedule_animation(self) -> None:
        self._render_frame()
        self.anim_tick += 1
        # ~25 fps, smooth & minimal CPU (<0.2%)
        self.root.after(40, self._schedule_animation)

    def _render_frame(self) -> None:
        self.canvas.delete("all")
        t = self.anim_tick
        S = self.S
        Sf = self.Sf

        # State-driven border & aura
        if self.state == "LISTENING":
            border_color = self.CARD_BORDER_LISTEN
            badge_fg = "#00f0ff"
        elif self.state == "TRANSCRIBING":
            border_color = self.CARD_BORDER_THINK
            badge_fg = "#c084fc"
        elif self.state == "QUEUED":
            border_color = self.CARD_BORDER_SUCCESS
            badge_fg = "#34d399"
        else:  # STANDBY
            border_color = self.CARD_BORDER_IDLE
            badge_fg = "#94a3b8"

        # 1. Background Rounded Card
        pad = S(4)
        x0, y0, x1, y1 = pad, pad, self.width - pad, self.height - pad
        radius = S(16)
        self._draw_rounded_rect(x0, y0, x1, y1, radius, fill=self.CARD_BG, outline=border_color, width=max(1, S(2)))

        # Center reference point for cat
        cx = self.width // 2
        cy = S(44)

        # Breathing / Sleeping vertical float
        if self.state == "STANDBY":
            b_y = Sf(math.sin(t * 0.08) * 2.0)
        elif self.state == "LISTENING":
            b_y = Sf(-2.0 + math.sin(t * 0.3) * 1.2)
        else:
            b_y = 0.0

        cat_cy = cy + b_y

        # 2. Cat Ears
        ear_perk = Sf(-3.0) if self.state == "LISTENING" else 0.0
        # Left Ear Outer
        self.canvas.create_polygon(
            cx - S(24), cat_cy - S(8),
            cx - S(34), cat_cy - S(28) + ear_perk,
            cx - S(10), cat_cy - S(18),
            fill=self.CAT_BODY, outline=border_color, width=max(1, S(1)),
        )
        # Left Ear Inner
        self.canvas.create_polygon(
            cx - S(22), cat_cy - S(10),
            cx - S(30), cat_cy - S(24) + ear_perk,
            cx - S(14), cat_cy - S(18),
            fill=self.CAT_INNER_EAR, outline="",
        )
        # Right Ear Outer
        self.canvas.create_polygon(
            cx + S(24), cat_cy - S(8),
            cx + S(34), cat_cy - S(28) + ear_perk,
            cx + S(10), cat_cy - S(18),
            fill=self.CAT_BODY, outline=border_color, width=max(1, S(1)),
        )
        # Right Ear Inner
        self.canvas.create_polygon(
            cx + S(22), cat_cy - S(10),
            cx + S(30), cat_cy - S(24) + ear_perk,
            cx + S(14), cat_cy - S(18),
            fill=self.CAT_INNER_EAR, outline="",
        )

        # 3. Cat Head / Body (Smooth oval)
        head_w, head_h = S(28), S(22)
        self.canvas.create_oval(
            cx - head_w, cat_cy - head_h,
            cx + head_w, cat_cy + head_h,
            fill=self.CAT_BODY, outline=border_color, width=max(1, S(1)),
        )

        # 4. Whiskers (Left & Right)
        w_col = "#64748b"
        self.canvas.create_line(cx - S(32), cat_cy - S(1), cx - S(18), cat_cy + S(1), fill=w_col, width=max(1, S(1)))
        self.canvas.create_line(cx - S(32), cat_cy + S(5), cx - S(18), cat_cy + S(4), fill=w_col, width=max(1, S(1)))
        self.canvas.create_line(cx + S(18), cat_cy + S(1), cx + S(32), cat_cy - S(1), fill=w_col, width=max(1, S(1)))
        self.canvas.create_line(cx + S(18), cat_cy + S(4), cx + S(32), cat_cy + S(5), fill=w_col, width=max(1, S(1)))

        # 5. Nose & Cute Smile (:3)
        self.canvas.create_polygon(
            cx - S(3), cat_cy + S(2),
            cx + S(3), cat_cy + S(2),
            cx, cat_cy + S(5),
            fill=self.CAT_NOSE,
        )
        # Mouth curves
        self.canvas.create_arc(
            cx - S(7), cat_cy + S(3), cx, cat_cy + S(8),
            start=180, extent=180, style="arc", outline=w_col, width=max(1, S(1)),
        )
        self.canvas.create_arc(
            cx, cat_cy + S(3), cx + S(7), cat_cy + S(8),
            start=180, extent=180, style="arc", outline=w_col, width=max(1, S(1)),
        )

        # 6. EYES & EXPRESSION
        eye_y = cat_cy - S(3)
        if self.state == "STANDBY":
            # Sleepy smiling closed eyes: ^ ^
            self.canvas.create_arc(
                cx - S(16), eye_y - S(4), cx - S(6), eye_y + S(4),
                start=0, extent=180, style="arc", outline="#94a3b8", width=max(1, S(2)),
            )
            self.canvas.create_arc(
                cx + S(6), eye_y - S(4), cx + S(16), eye_y + S(4),
                start=0, extent=180, style="arc", outline="#94a3b8", width=max(1, S(2)),
            )

            # Floating sleeping Z's
            z_phase = (t * 0.05) % 3
            z_y = cat_cy - S(18) - Sf(z_phase * 6)
            z_x = cx + S(22) + Sf(z_phase * 3)
            self.canvas.create_text(
                z_x, z_y,
                text="z", fill="#64748b",
                font=("Segoe UI", max(6, int(round((7 + z_phase * 1.5) * self.scale))), "bold"),
            )

        elif self.state == "LISTENING":
            # Big open glowing cyan eyes with pupil & highlight!
            # Left Eye
            self.canvas.create_oval(
                cx - S(16), eye_y - S(6), cx - S(6), eye_y + S(6),
                fill="#00f0ff", outline="#ffffff", width=max(1, S(1)),
            )
            self.canvas.create_oval(
                cx - S(13), eye_y - S(4), cx - S(9), eye_y + S(4),
                fill="#0b1329", outline="",
            )
            self.canvas.create_oval(
                cx - S(14), eye_y - S(5), cx - S(11), eye_y - S(2),
                fill="#ffffff", outline="",
            )

            # Right Eye
            self.canvas.create_oval(
                cx + S(6), eye_y - S(6), cx + S(16), eye_y + S(6),
                fill="#00f0ff", outline="#ffffff", width=max(1, S(1)),
            )
            self.canvas.create_oval(
                cx + S(9), eye_y - S(4), cx + S(13), eye_y + S(4),
                fill="#0b1329", outline="",
            )
            self.canvas.create_oval(
                cx + S(8), eye_y - S(5), cx + S(11), eye_y - S(2),
                fill="#ffffff", outline="",
            )

            # Dancing Audio Visualizer Bars under mouth
            bar_cx = cx
            bar_y = cat_cy + S(18)
            for i in range(5):
                bx = bar_cx - S(16) + i * S(8)
                bh = Sf(3.0) + abs(math.sin((t * 0.35) + i * 1.1)) * Sf(9.0)
                bw = max(1, S(2))
                self.canvas.create_rectangle(
                    bx - bw, bar_y - bh / 2, bx + bw, bar_y + bh / 2,
                    fill="#00f0ff", outline="",
                )

        elif self.state == "TRANSCRIBING":
            # Thinking / Processing Sparkle Eyes (✦ ✦)
            font_sparkle = ("Segoe UI", max(8, int(round(11 * self.scale))), "bold")
            self.canvas.create_text(cx - S(11), eye_y, text="✦", fill="#c084fc", font=font_sparkle)
            self.canvas.create_text(cx + S(11), eye_y, text="✦", fill="#c084fc", font=font_sparkle)

            # Pulsing thinking dots below
            dot_phase = (t // 5) % 3
            for i in range(3):
                col = "#c084fc" if i == dot_phase else "#4c1d95"
                self.canvas.create_oval(
                    cx - S(10) + i * S(10), cat_cy + S(16),
                    cx - S(6) + i * S(10), cat_cy + S(20),
                    fill=col, outline="",
                )

        elif self.state == "QUEUED":
            # Adorable Proud Wink (^ <)
            self.canvas.create_arc(
                cx - S(16), eye_y - S(4), cx - S(6), eye_y + S(4),
                start=0, extent=180, style="arc", outline="#34d399", width=max(1, S(2)),
            )
            font_star = ("Segoe UI", max(8, int(round(11 * self.scale))), "bold")
            self.canvas.create_text(cx + S(11), eye_y, text="★", fill="#34d399", font=font_star)

            # Success checkmark text
            font_chk = ("Segoe UI", max(7, int(round(8 * self.scale))), "bold")
            self.canvas.create_text(cx, cat_cy + S(18), text="✓ Sent", fill="#34d399", font=font_chk)

        # 7. Bottom Status Pill Badge
        badge_y = self.height - S(17)
        badge_text = self.status_text
        if self.command_preview and self.state == "QUEUED":
            badge_text = f"✓ {self.command_preview[:12]}"

        # Truncate text according to scale
        max_chars = max(12, int(round(16 * self.scale)))
        if len(badge_text) > max_chars:
            badge_text = badge_text[:max_chars - 2] + ".."

        badge_font = ("Segoe UI", max(7, int(round(8 * self.scale))), "bold")
        self.canvas.create_text(cx, badge_y, text=badge_text, fill=badge_fg, font=badge_font)

        # 8. Subtle close icon in top right
        close_font = ("Segoe UI", max(6, int(round(7 * self.scale))))
        self.canvas.create_text(self.width - S(12), S(12), text="✕", fill="#475569", font=close_font)

    def _draw_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        """Draw a sleek rounded rectangle on Tkinter canvas."""
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    # Test runner for standalone verification
    q = queue.Queue()
    act_q = queue.Queue()
    pet = VocalisPetUI(event_queue=q, action_queue=act_q)

    def test_cycle():
        time.sleep(2)
        q.put({"state": "LISTENING", "text": "🎙️ listening (2s)..."})
        time.sleep(3)
        q.put({"state": "TRANSCRIBING", "text": "⚡ thinking..."})
        time.sleep(2)
        q.put({"state": "QUEUED", "text": "✓ Queued", "command": "clean RAM"})
        time.sleep(2)
        q.put({"state": "STANDBY", "text": "💤 nexus"})

    threading.Thread(target=test_cycle, daemon=True).start()
    pet.run()
