"""Scout reminder -- an always-on-top nudge to scout every few rounds.

No screenshots, no API key, no game access of any kind. It just counts down and
then beeps + flashes "SCOUT NOW" so you remember to click through opponents.

Note: it works on a time interval (TFT rounds are ~30-40s), not true round
detection -- knowing the actual round number would require reading the screen,
which is a later (opt-in) capture feature. Tune --interval to taste.
"""
import sys
import time


def beep(enabled: bool = True) -> None:
    if not enabled:
        return
    try:
        import winsound
        winsound.Beep(880, 180)
        winsound.Beep(1175, 220)
    except Exception:
        print("\a", end="", flush=True)  # terminal bell fallback


def _run_console(interval: int, sound: bool) -> int:
    print(f"Scout reminder running -- nudging every {interval}s. Ctrl+C to stop.\n")
    cycle = 0
    try:
        while True:
            time.sleep(interval)
            cycle += 1
            beep(sound)
            print(f">>> SCOUT NOW  (cycle {cycle})  -- click each opponent <<<")
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0


def _run_popup(interval: int, sound: bool) -> int:
    import tkinter as tk

    state = {"remaining": interval, "cycles": 0, "paused": False}

    root = tk.Tk()
    root.title("TFTwatch")
    root.attributes("-topmost", True)
    root.geometry("260x110+40+40")
    root.configure(bg="#1b1b22")

    status = tk.Label(root, text="next scout in", fg="#9aa0aa", bg="#1b1b22",
                      font=("Segoe UI", 9))
    status.pack(pady=(10, 0))
    timer = tk.Label(root, text=str(interval), fg="#6cf08a", bg="#1b1b22",
                     font=("Segoe UI", 30, "bold"))
    timer.pack()

    def toggle():
        state["paused"] = not state["paused"]
        btn.config(text="Resume" if state["paused"] else "Pause")

    btn = tk.Button(root, text="Pause", command=toggle, width=8)
    btn.pack(pady=(0, 8))

    def tick():
        if not state["paused"]:
            state["remaining"] -= 1
            if state["remaining"] <= 0:
                state["cycles"] += 1
                state["remaining"] = interval
                beep(sound)
                status.config(text=f"SCOUT NOW!  (cycle {state['cycles']})", fg="#ff6b6b")
                timer.config(fg="#ff6b6b")
                root.after(2500, lambda: (status.config(text="next scout in", fg="#9aa0aa"),
                                          timer.config(fg="#6cf08a")))
            timer.config(text=str(state["remaining"]))
        root.after(1000, tick)

    root.after(1000, tick)
    root.mainloop()
    return 0


def run(interval: int = 40, sound: bool = True, popup: bool = True) -> int:
    if popup:
        try:
            import tkinter  # noqa: F401
        except Exception:
            print("(tkinter unavailable -- using console mode)")
            popup = False
    return _run_popup(interval, sound) if popup else _run_console(interval, sound)
