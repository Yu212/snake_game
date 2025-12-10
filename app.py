"""
Tkinter visualizer for the snake AI in solver.py.
Defines the expected API (move/measure/get_pos_* etc.) and then imports solver,
so solver.py can run unchanged while the board is rendered.
"""
import builtins
import importlib
import random
import sys
import threading
import tkinter as tk
import time
from queue import Queue, Empty

# Direction constants expected by solver.py
North, East, South, West = 0, 1, 2, 3

BOARD_SIZE = 32
CELL_PX = 32
CANVAS_SIZE = BOARD_SIZE * CELL_PX
BG_COLOR = "#0b1021"
SNAKE_COLOR = "#22c55e"
HEAD_COLOR = "#16a34a"
APPLE_COLOR = "#f97316"
GRID_COLOR = "#1e293b"

# Game state (guarded by state_lock)
state_lock = threading.RLock()
snake = [(0, 0)]  # list of (x, y) from tail to head
snake_set = {(0, 0)}
apple = None
apple_eaten = True
step_counter = 0
game_over = False
error_message = None
hc_dirs = {}  # {(x,y): dir}
tree_edges = {}  # {(bx,by): [status*4]}
grow_pending = 0
headless_mode = False

# Render queue so the solver thread can push frames safely
render_queue: Queue = Queue(maxsize=4)
stop_event = threading.Event()
step_wait_enabled = True
step_gate = threading.Event()
step_wait_millis = 5
SOLVER_MODULE_NAME = None

# ========= Snake/solver API =========

def get_world_size():
    return BOARD_SIZE


def get_pos_x():
    with state_lock:
        return snake[-1][0]


def get_pos_y():
    with state_lock:
        return snake[-1][1]


def _spawn_apple_locked():
    global apple, apple_eaten
    free = []
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if (x, y) not in snake_set:
                free.append((x, y))
    if not free:
        apple = None
        apple_eaten = False
        return None
    apple = random.choice(free)
    apple_eaten = False
    return apple


def measure():
    """Return the current apple position, creating one if needed."""
    with state_lock:
        if apple is None or apple_eaten:
            _spawn_apple_locked()
        return apple


DIR_VECS = {
    # y+ is north (up), as expected by solver.py
    North: (0, 1),
    East: (1, 0),
    South: (0, -1),
    West: (-1, 0),
}


def move(direction):
    """Advance the snake by one cell in the given direction."""
    global apple_eaten, game_over, step_counter, error_message, hc_dirs, tree_edges, grow_pending, step_wait_millis
    if direction not in DIR_VECS:
        error_message = f"Invalid direction: {direction}"
        return

    with state_lock:
        if game_over:
            return

        dx, dy = DIR_VECS[direction]
        hx, hy = snake[-1]
        nx = hx + dx
        ny = hy + dy

        # Bounds check
        if nx < 0 or ny < 0 or nx >= BOARD_SIZE or ny >= BOARD_SIZE:
            game_over = True
            error_message = f"Hit the wall at {(nx, ny)}"
            raise RuntimeError(error_message)

        # Self-collision check (moving into the tail is allowed if it vacates)
        # Tail only vacates if we will pop it this step
        will_pop_tail = grow_pending == 0 and not (apple is not None and (nx, ny) == apple)
        tail_vacating = snake[0] if will_pop_tail else None
        if (nx, ny) in snake_set and (tail_vacating is None or (nx, ny) != tail_vacating):
            game_over = True
            error_message = f"Ran into itself at {(nx, ny)}"
            _queue_state()
            raise RuntimeError(error_message)

        ate = apple is not None and (nx, ny) == apple
        snake.append((nx, ny))
        snake_set.add((nx, ny))
        # Apply previously scheduled growth: if pending, skip pop this turn
        if grow_pending > 0:
            grow_pending -= 1
        else:
            tail = snake.pop(0)
            snake_set.discard(tail)
        # Eating schedules growth for the *next* move
        if ate:
            apple_eaten = True
            grow_pending += 1

        step_counter += 1

        if step_counter < 5000 or step_counter > 60000:
            step_wait_millis = 5
        else:
            step_wait_millis = 1

        # Capture latest Hamiltonian data if solver exposed it
        solver_mod = sys.modules.get(SOLVER_MODULE_NAME)
        if solver_mod is not None:
            hc_map = getattr(solver_mod, "hamilton_cycle", None)
            if hc_map:
                hc_dirs = dict(hc_map)
            tree_state = getattr(solver_mod, "tree", None)
            if tree_state:
                # Deep copy lists to avoid mutation across threads
                tree_edges = {k: list(v) for k, v in tree_state.items()}
        _queue_state()
    _wait_for_step()


def wait_for_step():
    global apple_eaten, game_over, step_counter, error_message, hc_dirs, tree_edges, grow_pending

    """Push a frame to the UI and block until the next Right-key step."""
    # Capture latest Hamiltonian data if solver exposed it
    solver_mod = sys.modules.get(SOLVER_MODULE_NAME)
    if solver_mod is not None:
        hc_map = getattr(solver_mod, "hamilton_cycle", None)
        if hc_map:
            hc_dirs = dict(hc_map)
        tree_state = getattr(solver_mod, "tree", None)
        if tree_state:
            # Deep copy lists to avoid mutation across threads
            tree_edges = {k: list(v) for k, v in tree_state.items()}
    _queue_state()
    _wait_for_step()


def _wait_for_step():
    """Wait for a Right-key trigger; supports key repeat from UI."""
    if not step_wait_enabled:
        return
    step_gate.wait()
    step_gate.clear()


def _install_api_into_builtins():
    """Expose expected API/directions to solver.py."""
    builtins.measure = measure
    builtins.move = move
    builtins.wait_for_step = wait_for_step

# Install immediately so importing solver.py directly also works
_install_api_into_builtins()

# ========= Rendering =========

def _queue_state():
    if headless_mode:
        return
    snapshot = None
    with state_lock:
        snapshot = (
            list(snake),
            apple,
            dict(hc_dirs),
            {k: list(v) for k, v in tree_edges.items()},
            step_counter,
            game_over,
            error_message,
        )
    try:
        if render_queue.full():
            render_queue.get_nowait()
        render_queue.put_nowait(snapshot)
    except Exception:
        pass


def _draw_grid(canvas: tk.Canvas):
    for i in range(1, BOARD_SIZE):
        offset = i * CELL_PX
        canvas.create_line(offset, 0, offset, CANVAS_SIZE, fill=GRID_COLOR, width=1)
        canvas.create_line(0, offset, CANVAS_SIZE, offset, fill=GRID_COLOR, width=1)


def _canvas_coords(x, y):
    cy = BOARD_SIZE - 1 - y
    return x * CELL_PX, cy * CELL_PX



def draw_state(canvas: tk.Canvas, state):
    snake_cells, apple_pos, hc_map, tree_state, steps, over, err = state
    canvas.delete("all")
    canvas.configure(bg=BG_COLOR)
    _draw_grid(canvas)

    # Draw spanning tree edges on block grid
    if tree_state:
        color_map = {0: "#334155", 1: "#b91c1c", 2: "#38bdf8"}  # FREE/forbidden/must (must = cyan)
        for (bx, by), dirs in tree_state.items():
            cx, cy = _canvas_coords(bx * 2 + 1, by * 2)
            for d, status in enumerate(dirs):
                if status is None:
                    continue
                if d in (1, 2):  # draw E and S to avoid duplicates (S instead of N)
                    dx, dy = DIR_VECS[East] if d == 1 else DIR_VECS[South]
                    nbx, nby = bx + dx, by + dy
                    if 0 <= nbx < BOARD_SIZE // 2 and 0 <= nby < BOARD_SIZE // 2:
                        nx, ny = _canvas_coords(nbx * 2 + 1, nby * 2)
                        width = 1 if status == 1 else 3
                        canvas.create_line(cx, cy, nx, ny, fill=color_map.get(status, "#475569"), width=width)

    # Draw Hamiltonian cycle directions
    if hc_map:
        for (x, y), d in hc_map.items():
            dx, dy = DIR_VECS.get(d, (0, 0))
            x0, y0 = _canvas_coords(x, y)
            sx, sy = x0 + CELL_PX * 0.5, y0 + CELL_PX * 0.5
            ex, ey = sx + dx * CELL_PX * 0.6, sy - dy * CELL_PX * 0.6
            canvas.create_line(sx, sy, ex, ey, fill="#60a5fa", width=2, arrow=tk.LAST, arrowshape=(6, 8, 3))

    if apple_pos is not None:
        ax, ay = apple_pos
        x0, y0 = _canvas_coords(ax, ay)
        canvas.create_rectangle(
            x0 + 2,
            y0 + 2,
            x0 + CELL_PX - 2,
            y0 + CELL_PX - 2,
            fill=APPLE_COLOR,
            outline="",
        )

    for i, (sx, sy) in enumerate(snake_cells):
        x0, y0 = _canvas_coords(sx, sy)
        fill = HEAD_COLOR if i == len(snake_cells) - 1 else SNAKE_COLOR
        if i > 0:
            px, py = snake_cells[i - 1]
            px0, py0 = _canvas_coords(px, py)
            cx, cy = x0 + CELL_PX * 0.5, y0 + CELL_PX * 0.5
            pcx, pcy = px0 + CELL_PX * 0.5, py0 + CELL_PX * 0.5
            # Draw a thick connector so body looks continuous
            canvas.create_line(
                pcx,
                pcy,
                cx,
                cy,
                fill=SNAKE_COLOR,
                width=8,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
        canvas.create_rectangle(
            x0 + 4,
            y0 + 4,
            x0 + CELL_PX - 4,
            y0 + CELL_PX - 4,
            fill=fill,
            outline="",
        )

    if over:
        canvas.create_text(
            CANVAS_SIZE // 2,
            CANVAS_SIZE // 2,
            text="Game over" if err is None else err,
            fill="white",
            font=("Helvetica", 20, "bold"),
        )


# ========= Runner / UI =========

def _solver_runner():
    global error_message, hc_dirs, tree_edges
    _install_api_into_builtins()
    _queue_state()
    _wait_for_step()
    importlib.import_module(SOLVER_MODULE_NAME)  # running the module drives the game
    with state_lock:
        hc_map = getattr(sys.modules.get(SOLVER_MODULE_NAME), "hamilton_cycle", None)
        if hc_map:
            hc_dirs = dict(hc_map)
        tree_state = getattr(sys.modules.get(SOLVER_MODULE_NAME), "tree", None)
        if tree_state:
            tree_edges = {k: list(v) for k, v in tree_state.items()}
        _queue_state()


def launch_ui():
    if stop_event.is_set():
        stop_event.clear()
    _queue_state()  # initial frame

    root = tk.Tk()
    root.title("Snake solver visualizer")
    canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE, highlightthickness=0)
    canvas.pack(padx=10, pady=10)

    status_var = tk.StringVar()
    status = tk.Label(root, textvariable=status_var, anchor="w")
    status.pack(fill="x")

    repeat = {"job": None, "start_ts": None, "pressed": False, "release_job": None}

    def adjust_step_wait(delta_ms: int):
        """Adjust the wait time between repeated steps (clamped to >= 0)."""
        global step_wait_millis
        step_wait_millis = max(0, step_wait_millis + delta_ms)

    def trigger_step():
        step_gate.set()

    def schedule_repeat():
        if not repeat["pressed"]:
            repeat["job"] = None
            return
        now = time.monotonic()
        if repeat["start_ts"] is None:
            repeat["start_ts"] = now
        held = now - repeat["start_ts"]
        # begin auto-repeat only after holding 0.3s
        if held >= 0:
            trigger_step()
        repeat["job"] = root.after(step_wait_millis, schedule_repeat)

    def on_right_press(event=None):
        # Cancel a pending release triggered by key-repeat
        if repeat["release_job"] is not None:
            try:
                root.after_cancel(repeat["release_job"])
            except tk.TclError:
                pass
            repeat["release_job"] = None
        if repeat["pressed"]:
            return
        repeat["pressed"] = True
        repeat["start_ts"] = time.monotonic()
        trigger_step()
        schedule_repeat()

    def _confirm_release():
        repeat["release_job"] = None
        if not repeat["pressed"]:
            return
        repeat["pressed"] = False
        repeat["start_ts"] = None
        if repeat["job"] is not None:
            try:
                root.after_cancel(repeat["job"])
            except tk.TclError:
                pass
            repeat["job"] = None

    def on_right_release(event=None):
        # Defer release to ignore synthetic KeyRelease events from key-repeat
        if repeat["release_job"] is not None:
            try:
                root.after_cancel(repeat["release_job"])
            except tk.TclError:
                pass
        repeat["release_job"] = root.after(50, _confirm_release)

    root.bind("<KeyPress-Right>", on_right_press)
    root.bind("<KeyRelease-Right>", on_right_release)
    root.bind("<KeyPress-Up>", lambda e: adjust_step_wait(-1))
    root.bind("<KeyPress-Down>", lambda e: adjust_step_wait(1))
    root.focus_set()

    def pump():
        if stop_event.is_set():
            return
        latest = None
        try:
            while True:
                latest = render_queue.get_nowait()
        except Empty:
            pass
        if latest is not None:
            draw_state(canvas, latest)
            snake_cells, apple_pos, hc_map, tree_state, steps, over, err = latest
            length = len(snake_cells)
            msg = f"Length: {length} | Steps: {steps}"
            if over:
                msg += " | Finished" if err is None else f" | {err}"
            msg += f" | Delay: {step_wait_millis} ms"
            status_var.set(msg)
        if not stop_event.is_set():
            try:
                root.after(30, pump)
            except tk.TclError:
                stop_event.set()

    pump()

    def on_close():
        stop_event.set()
        try:
            root.destroy()
        except tk.TclError:
            pass

    root.protocol("WM_DELETE_WINDOW", on_close)

    threading.Thread(target=_solver_runner, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app.py <solver> [--fast] [--seed <value>]")
        sys.exit(1)
    solver_arg = sys.argv[1]
    SOLVER_MODULE_NAME = solver_arg
    args = sys.argv[2:]

    # Seed handling
    seed_val = None
    if "--seed" in args:
        try:
            idx = args.index("--seed")
            seed_val = int(args[idx + 1])
        except Exception:
            seed_val = None
    if seed_val is None:
        seed_val = random.randrange(0, 1 << 16)
    random.seed(seed_val)
    print(f"Using random seed: {seed_val}")

    if "--fast" in args:
        headless_mode = True
        step_wait_enabled = False
        try:
            _install_api_into_builtins()
            importlib.import_module(SOLVER_MODULE_NAME)
            print(f"Finished. Steps: {step_counter}")
        except Exception as exc:
            print(f"Solver crashed: {exc}")
    else:
        launch_ui()
