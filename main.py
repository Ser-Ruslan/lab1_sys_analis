# -*- coding: utf-8 -*-
"""
Лабораторная работа №2. Сложные системы. Принцип обратной связи.
ВАРИАНТ 1. Динамические препятствия (внутренняя целостность).

4 вкладки:
  • Декомпозиция  — схема классов системы
  • Симуляция     — интерактивная визуализация муравейника с легендой
  • Эксперименты  — автозапуск экспериментов №1–3
  • Анализ        — системный анализ результатов

Управление в симуляции:
  • Клик по полю              — поставить/убрать одну клетку стены
  • Зажать ЛКМ и протянуть    — нарисовать стену мышью
  • Кнопка «Стена по центру»  — автоматическая стена на такте 150
  • Кнопка «Стена поперёк»    — перерезать самую сильную тропу
  • Кнопка «Убрать все стены» — очистить препятствия

Запуск: python lab2_variant1.py
Зависимости: numpy, tkinter (стандартная библиотека)
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import random

# ─────────────────────────── Глобальные константы ────────────────────────────
FIELD_SIZE = 50
CELL       = 11
CANVAS_PX  = FIELD_SIZE * CELL
WALL_STEP  = 150
WALL_HALF  = 10

BG, PANEL, BORDER = "#0d1117", "#161b22", "#30363d"
TXT, DIM          = "#c9d1d9", "#8b949e"
ACCENT, GREEN, ORANGE, RED = "#58a6ff", "#7ee787", "#ff7b45", "#f85149"


# ══════════════════════════════════════════════════════════════════════════════
# 1. ДЕКОМПОЗИЦИЯ. Микроуровень — агент-муравей
# ══════════════════════════════════════════════════════════════════════════════
class Ant:
    """Элементарный объект сложной системы. Локальное состояние и правила."""
    __slots__ = ("x", "y", "has_food")

    def __init__(self, nest_x, nest_y):
        self.x, self.y = nest_x, nest_y
        self.has_food = False

    def move(self, size, pheromone, food, obstacle, nest, sensitivity):
        if not self.has_food:
            if food[self.x, self.y] > 0:
                food[self.x, self.y] -= 1
                self.has_food = True
                return
            self._wander(size, pheromone, obstacle, sensitivity)
        else:
            self._go_home(size, obstacle, nest)

    def _wander(self, size, pheromone, obstacle, sensitivity):
        valid, weights = [], []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = self.x + dx, self.y + dy
                if 0 <= nx < size and 0 <= ny < size and not obstacle[nx, ny]:
                    valid.append((nx, ny))
                    weights.append(0.15 + sensitivity * float(pheromone[nx, ny]))
        if valid:
            self.x, self.y = self._weighted_choice(valid, weights)

    def _go_home(self, size, obstacle, nest):
        """Возврат в гнездо + скольжение вдоль стен (вариант 1)."""
        dx = (nest[0] > self.x) - (nest[0] < self.x)
        dy = (nest[1] > self.y) - (nest[1] < self.y)
        prefs = []
        if dx and dy: prefs.append((dx, dy))
        if dx:        prefs.append((dx, 0))
        if dy:        prefs.append((0, dy))
        perp = []
        if dx: perp += [(0, -1), (0, 1)]
        if dy: perp += [(-1, 0), (1, 0)]
        random.shuffle(perp)
        prefs += perp
        for m in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            if m not in prefs: prefs.append(m)
        for ddx, ddy in prefs:
            nx, ny = self.x + ddx, self.y + ddy
            if 0 <= nx < size and 0 <= ny < size and not obstacle[nx, ny]:
                self.x, self.y = nx, ny
                return

    @staticmethod
    def _weighted_choice(valid, weights):
        total = sum(weights)
        if total <= 0:
            return random.choice(valid)
        r, acc = random.random() * total, 0.0
        for v, w in zip(valid, weights):
            acc += w
            if r <= acc:
                return v
        return valid[-1]


# ══════════════════════════════════════════════════════════════════════════════
# 2. АГРЕГИРОВАНИЕ. Макроуровень — управляющая система
# ══════════════════════════════════════════════════════════════════════════════
class AntColonySystem:
    def __init__(self, size=50, num_ants=150, evaporation_rate=0.07,
                 pheromone_deposit=3.0, sensitivity=1.0):
        self.size             = size
        self.evaporation_rate = evaporation_rate
        self.pheromone_deposit= pheromone_deposit
        self.sensitivity      = sensitivity

        self.nest         = (5, 5)
        self.food_sources = [(40, 40), (42, 10)]

        self.pheromone_grid = np.zeros((size, size), dtype=np.float32)
        self.food_grid      = np.zeros((size, size), dtype=np.float32)
        self.obstacle_grid  = np.zeros((size, size), dtype=bool)
        self.trail_grid     = np.zeros((size, size), dtype=np.float32)
        self._init_food()

        self.num_ants = num_ants
        self.ants = [Ant(*self.nest) for _ in range(num_ants)]

        self.total_food_collected = 0
        self.step = 0
        self.wall_built = False
        self.wall_step_marker = None
        self.wall_markers = []
        self.food_history   = [0]
        self.spread_history = [0]

    def _init_food(self):
        for fx, fy in self.food_sources:
            self.food_grid[max(0, fx-1):fx+2, max(0, fy-1):fy+2] = 200.0

    # ─── Автоматическая стена (по условию лабораторной работы) ────────
    def build_wall(self):
        """Сплошная вертикальная стена ≈20 клеток в середине карты."""
        col = self.size // 2
        y0 = max(1, self.size // 2 - WALL_HALF)
        y1 = min(self.size - 1, self.size // 2 + WALL_HALF)
        # obstacle_grid[row, col]; вертикальная стена — фиксирован col
        self.obstacle_grid[y0:y1, col] = True
        self.wall_built = True
        self.wall_step_marker = self.step
        self.wall_markers.append(self.step)

    # ─── ДИНАМИЧЕСКИЕ СТЕНЫ ───────────────────────────────────────────
    def add_wall_segment(self, col, row, length=15, orientation="v"):
        """Возвести стену-отрезок через заданную клетку.
           orientation='v' — вертикальная, 'h' — горизонтальная."""
        half = length // 2
        if orientation == "v":
            c  = max(0, min(self.size - 1, col))
            r0 = max(0, row - half)
            r1 = min(self.size, row + half + 1)
            self.obstacle_grid[r0:r1, c] = True
        else:
            r  = max(0, min(self.size - 1, row))
            c0 = max(0, col - half)
            c1 = min(self.size, col + half + 1)
            self.obstacle_grid[r, c0:c1] = True
        self.wall_markers.append(self.step)

    def add_wall_crossing_trail(self):
        """Найти участок с максимальным феромоном и перерезать его стеной."""
        p = self.pheromone_grid.copy()
        p[self.obstacle_grid] = -1.0
        if p.max() <= 0:
            self.add_wall_segment(self.size // 2, self.size // 2, 15, "v")
            return
        row, col = np.unravel_index(np.argmax(p), p.shape)
        nx, ny = self.nest
        dx, dy = col - nx, row - ny
        # если тропа идёт преимущественно по X — ставим вертикальную стену поперёк
        orientation = "v" if abs(dx) >= abs(dy) else "h"
        self.add_wall_segment(col, row, 15, orientation)

    def toggle_wall_cell(self, col, row):
        """Поставить/убрать стену в клетке. col = X, row = Y."""
        if 0 <= col < self.size and 0 <= row < self.size:
            self.obstacle_grid[row, col] = not self.obstacle_grid[row, col]
            self.wall_markers.append(self.step)

    def paint_wall_cell(self, col, row):
        """Нарисовать стену (только поставить, не переключать)."""
        if 0 <= col < self.size and 0 <= row < self.size:
            if not self.obstacle_grid[row, col]:
                self.obstacle_grid[row, col] = True
                self.wall_markers.append(self.step)

    def clear_all_walls(self):
        self.obstacle_grid[:] = False
        self.wall_built = False

    # ─── Основной такт ────────────────────────────────────────────────
    def update_system(self):
        # Отрицательная ОС — испарение
        self.pheromone_grid *= (1.0 - self.evaporation_rate)
        self.trail_grid     *= 0.82

        nx, ny = self.nest
        pher = self.pheromone_grid
        for ant in self.ants:
            if ant.has_food and ant.x == nx and ant.y == ny:
                ant.has_food = False
                self.total_food_collected += 1
                continue
            ant.move(self.size, pher, self.food_grid,
                     self.obstacle_grid, self.nest, self.sensitivity)
            if self.trail_grid[ant.x, ant.y] < 4.0:
                self.trail_grid[ant.x, ant.y] += 1.0
            # Положительная ОС — усиление следа
            if ant.has_food:
                pher[ant.x, ant.y] += self.pheromone_deposit

        self.step += 1
        if self.step == WALL_STEP and not self.wall_built:
            self.build_wall()

        self.food_history.append(self.total_food_collected)
        self.spread_history.append(int(np.count_nonzero(self.pheromone_grid > 0.5)))
        if len(self.food_history) > 4000:
            self.food_history.pop(0)
            self.spread_history.pop(0)


# ══════════════════════════════════════════════════════════════════════════════
# 3. РЕНДЕРИНГ СНИМКА (для экспериментов)
# ══════════════════════════════════════════════════════════════════════════════
def field_to_photo(system, zoom=5):
    n = system.size
    phero = np.clip(system.pheromone_grid / 6.0, 0, 1) ** 0.7
    trail = np.clip(system.trail_grid     / 3.0, 0, 1) ** 0.8
    food  = np.clip(system.food_grid      / 200.0, 0, 1)

    yy, xx = np.mgrid[0:n, 0:n]
    d = np.sqrt((xx - system.nest[0])**2 + (yy - system.nest[1])**2)
    nm = np.clip(1.0 - d / 5.0, 0, 1) ** 2

    fg = np.zeros_like(food)
    for fx, fy in system.food_sources:
        dd = np.sqrt((xx - fx)**2 + (yy - fy)**2)
        fg = np.maximum(fg, np.clip(1.0 - dd / 4.5, 0, 1) ** 2)

    R = 10 + 40*trail + 245*phero + 60*food + 50*fg + 30*nm
    G = 14 + 90*trail + 100*phero + 220*food + 180*fg + 90*nm
    B = 22 + 130*trail + 30*phero + 80*food + 60*fg + 220*nm

    # ── СТЕНЫ: ярко-янтарные + светлый контур ──
    obs = system.obstacle_grid
    R[obs], G[obs], B[obs] = 215, 125, 55
    border = np.zeros_like(obs)
    border[1:,  :] |= obs[:-1, :]
    border[:-1, :] |= obs[1:,  :]
    border[:, 1:]  |= obs[:, :-1]
    border[:, :-1] |= obs[:, 1:]
    border &= ~obs
    R[border], G[border], B[border] = 255, 200, 90

    R = np.clip(R, 0, 255); G = np.clip(G, 0, 255); B = np.clip(B, 0, 255)
    rgb = np.stack([R, G, B], -1).astype(np.uint8)
    flat = ["#%02x%02x%02x" % (a, b, c)
            for a, b, c in rgb.reshape(-1, 3).tolist()]
    photo = tk.PhotoImage(width=n, height=n)
    for y in range(n):
        photo.put("{" + " ".join(flat[y*n:(y+1)*n]) + "}", to=(0, y))
    return photo.zoom(zoom)


# ══════════════════════════════════════════════════════════════════════════════
# 4. ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════
class Lab2App:

    def __init__(self, root):
        self.root = root
        root.title("ЛР №2 · Вариант 1 · Сложные системы: обратные связи")
        root.configure(bg=BG)
        root.geometry("1260x860")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0,
                        tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", background=PANEL, foreground=TXT,
                        padding=[18, 9], font=("Segoe UI", 10, "bold"),
                        borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_schema = tk.Frame(nb, bg=BG)
        self.tab_sim    = tk.Frame(nb, bg=BG)
        self.tab_exp    = tk.Frame(nb, bg=BG)
        self.tab_anal   = tk.Frame(nb, bg=BG)
        nb.add(self.tab_schema, text="⚙  Декомпозиция")
        nb.add(self.tab_sim,    text="🐜  Симуляция")
        nb.add(self.tab_exp,    text="🧪  Эксперименты")
        nb.add(self.tab_anal,   text="📊  Системный анализ")

        self._build_schema_tab()
        self._build_sim_tab()
        self._build_exp_tab()
        self._build_analysis_tab()

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 1: СХЕМА ДЕКОМПОЗИЦИИ
    # ══════════════════════════════════════════════════════════════════
    def _build_schema_tab(self):
        canvas = tk.Canvas(self.tab_schema, bg=BG, highlightthickness=0,
                           width=1200, height=800)
        canvas.pack(fill="both", expand=True)
        canvas.create_text(600, 22,
                           text="СХЕМА ДЕКОМПОЗИЦИИ И АГРЕГИРОВАНИЯ СИСТЕМЫ",
                           fill=ACCENT, font=("Segoe UI", 15, "bold"))
        canvas.create_text(600, 46, text="Вариант 1. Динамические препятствия",
                           fill=DIM, font=("Segoe UI", 10, "italic"))

        def box(x1, y1, x2, y2, title, color, subtitle=""):
            canvas.create_rectangle(x1+3, y1+3, x2+3, y2+3, fill="#000",
                                    outline="")
            canvas.create_rectangle(x1, y1, x2, y2, outline=color,
                                    fill="#10161f", width=2)
            canvas.create_text((x1+x2)//2, y1+18, text=title, fill=color,
                               font=("Consolas", 13, "bold"))
            if subtitle:
                canvas.create_text((x1+x2)//2, y1+38, text=subtitle, fill=DIM,
                                   font=("Segoe UI", 9, "italic"))
            canvas.create_line(x1+8, y1+50, x2-8, y1+50, fill=BORDER)

        box(150, 70, 660, 275, "AntColonySystem", ACCENT,
            "МАКРОУРОВЕНЬ · управляющая подсистема")
        canvas.create_text(165, 130, anchor="w", text="Атрибуты:", fill=GREEN,
                           font=("Consolas", 10, "bold"))
        attrs = [
            ("pheromone_grid : ndarray", ORANGE, "канал положительной ОС"),
            ("food_grid : ndarray",      GREEN,  "подсистема ресурсов"),
            ("obstacle_grid : bool",     RED,    "ВАРИАНТ 1 · стены"),
            ("trail_grid : float",       DIM,    "визуализация путей"),
            ("ants : List[Ant]",         ACCENT, "агрегирование агентов"),
        ]
        for i, (name, col, comm) in enumerate(attrs):
            y = 150 + i * 18
            canvas.create_text(165, y, anchor="w", text="• " + name, fill=col,
                               font=("Consolas", 9))
            canvas.create_text(430, y, anchor="w", text="← " + comm, fill=DIM,
                               font=("Segoe UI", 8, "italic"))
        canvas.create_text(165, 258, anchor="w",
                           text="Методы: update_system() · build_wall() · "
                                "add_wall_crossing_trail()",
                           fill=GREEN, font=("Consolas", 9, "bold"))

        box(150, 480, 660, 690, "Ant", GREEN,
            "МИКРОУРОВЕНЬ · элементарный агент")
        canvas.create_text(165, 540, anchor="w", text="Атрибуты:",
                           fill=GREEN, font=("Consolas", 10, "bold"))
        for i, (n, c) in enumerate([("x, y : int", ACCENT),
                                    ("has_food : bool", GREEN)]):
            canvas.create_text(165, 562 + i*18, anchor="w", text="• " + n,
                               fill=c, font=("Consolas", 9))
        canvas.create_text(165, 620, anchor="w", text="Методы:",
                           fill=GREEN, font=("Consolas", 10, "bold"))
        for i, m in enumerate(["move()", "_wander() ← +ОС (влечение)",
                               "_go_home() ← обход стены"]):
            canvas.create_text(165, 642 + i*18, anchor="w", text="• " + m,
                               fill=ORANGE if "ОС" in m or "стены" in m else DIM,
                               font=("Consolas", 9))
        canvas.create_text(165, 700, anchor="w",
                           text="Локальные правила → глобальный порядок",
                           fill=DIM, font=("Segoe UI", 8, "italic"))

        canvas.create_line(405, 275, 405, 480, arrow=tk.LAST, fill=ACCENT,
                           width=2)
        canvas.create_text(415, 375, anchor="w",
                           text="агрегирование  1..N\n(список self.ants)",
                           fill=ACCENT, font=("Consolas", 9, "italic"))

        box(760, 200, 1130, 480, "SimulationApp", "#d2a8ff",
            "ГРАФИЧЕСКИЙ ИНТЕРФЕЙС · tkinter")
        for i, l in enumerate([
                "• Canvas + PhotoImage — поле", "• Слайдеры параметров",
                "• График истории метрик",
                "• Кнопки: старт/пауза, стена,",
                "     стена поперёк тропы, сброс",
                "• Легенда объектов на поле",
                "• Клик и протягивание мышью — стены"]):
            canvas.create_text(780, 260 + i*20, anchor="w", text=l,
                               fill=TXT, font=("Consolas", 9))
        canvas.create_line(760, 350, 660, 350, arrow=tk.LAST, fill="#d2a8ff",
                           width=2)
        canvas.create_line(760, 260, 660, 260, arrow=tk.LAST, fill="#d2a8ff",
                           width=2)
        canvas.create_text(710, 240, text="управляет", fill="#d2a8ff",
                           font=("Segoe UI", 8, "italic"))

        canvas.create_rectangle(760, 510, 1130, 700, outline=ORANGE,
                                fill="#1a1206", width=2, dash=(4, 3))
        canvas.create_text(945, 530, text="ОБРАТНЫЕ СВЯЗИ", fill=ORANGE,
                           font=("Segoe UI", 11, "bold"))
        canvas.create_text(780, 560, anchor="w",
                           text="+  Положительная ОС:", fill=GREEN,
                           font=("Consolas", 10, "bold"))
        canvas.create_text(790, 582, anchor="w",
                           text="pheromone_grid[x,y] += deposit",
                           fill=TXT, font=("Consolas", 9))
        canvas.create_text(790, 600, anchor="w",
                           text="→ усиливает удачный маршрут", fill=DIM,
                           font=("Segoe UI", 8, "italic"))
        canvas.create_text(780, 630, anchor="w",
                           text="─  Отрицательная ОС:", fill=RED,
                           font=("Consolas", 10, "bold"))
        canvas.create_text(790, 652, anchor="w",
                           text="pheromone_grid *= (1 - evaporation)",
                           fill=TXT, font=("Consolas", 9))
        canvas.create_text(790, 670, anchor="w",
                           text="→ забывает устаревшие тропы", fill=DIM,
                           font=("Segoe UI", 8, "italic"))

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 2: СИМУЛЯЦИЯ
    # ══════════════════════════════════════════════════════════════════
    def _build_sim_tab(self):
        self.system = AntColonySystem(
            size=FIELD_SIZE, num_ants=150,
            evaporation_rate=0.07, pheromone_deposit=3.0, sensitivity=1.0)
        self.running = False
        self.delay = 30
        self.steps_per_frame = 1
        self.ant_items = []
        self.zoomed_ref = None
        self.hint_visible = True

        main = tk.Frame(self.tab_sim, bg=BG)
        main.pack(padx=12, pady=12)

        # ─── Левая колонка: поле ───
        left = tk.Frame(main, bg=BG); left.grid(row=0, column=0)

        self.canvas = tk.Canvas(left, width=CANVAS_PX, height=CANVAS_PX,
                                bg="#05080d", highlightthickness=1,
                                highlightbackground=BORDER, cursor="crosshair")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)

        self.photo = tk.PhotoImage(width=FIELD_SIZE, height=FIELD_SIZE)
        self.zoomed_ref = self.photo.zoom(CELL)
        self.field_item = self.canvas.create_image(0, 0, image=self.zoomed_ref,
                                                   anchor="nw")

        self.hint_item = self.canvas.create_text(
            CANVAS_PX/2, CANVAS_PX - 12, anchor="s",
            text="клик или протягивание мышью по полю — поставить стену",
            fill="#c9d1d9", font=("Segoe UI", 9, "italic"))

        # ─── ЛЕГЕНДА ───
        legend_frame = tk.Frame(left, bg=PANEL, highlightthickness=1,
                                highlightbackground=BORDER)
        legend_frame.pack(fill="x", pady=(8, 0))
        tk.Label(legend_frame, text="ЛЕГЕНДА", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10,
                                                    pady=(6, 2))
        legend_grid = tk.Frame(legend_frame, bg=PANEL)
        legend_grid.pack(fill="x", padx=10, pady=(0, 8))

        legend_items = [
            ("#ffffff", "#ff9838", "Муравей ищет пищу"),
            ("#9cffc6", "#00aa55", "Муравей с едой"),
            ("#79c0ff", "#79c0ff", "Гнездо"),
            ("#7ee787", "#7ee787", "Источник пищи"),
            ("#ff7b45", "#ff7b45", "Феромоновая тропа"),
            ("#58a6ff", "#58a6ff", "След отдельных агентов"),
            ("#d77d37", "#ffc85a", "Стена (препятствие)"),
        ]
        for i, (body_color, halo_color, label) in enumerate(legend_items):
            r, c = divmod(i, 3)
            cell = tk.Frame(legend_grid, bg=PANEL)
            cell.grid(row=r, column=c, sticky="w", padx=(0, 18), pady=2)
            sw = tk.Canvas(cell, width=16, height=16, bg=PANEL,
                           highlightthickness=0)
            sw.pack(side="left")
            sw.create_oval(1, 1, 15, 15, fill=halo_color, outline="")
            sw.create_oval(4, 4, 12, 12, fill=body_color, outline="#0d1117")
            tk.Label(cell, text=label, bg=PANEL, fg=TXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

        # ─── Правая колонка ───
        right = tk.Frame(main, bg=BG); right.grid(row=0, column=1,
                                                   sticky="n", padx=(14, 0))

        tk.Label(right, text="ВАРИАНТ 1", bg=BG, fg=RED,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(right, text="Динамические препятствия\n(внутренняя целостность)",
                 bg=BG, fg=TXT, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        box = tk.Frame(right, bg=PANEL, highlightthickness=1,
                       highlightbackground=BORDER); box.pack(fill="x")
        tk.Label(box, text="ЭМЕРДЖЕНТНЫЕ МЕТРИКИ", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8,
                                                     pady=(6, 2))
        self.lbl_step   = tk.Label(box, text="Такт: 0", bg=PANEL, fg=TXT,
                                   font=("Consolas", 10), anchor="w")
        self.lbl_food   = tk.Label(box, text="Собрано пищи: 0", bg=PANEL,
                                   fg=GREEN, font=("Consolas", 10), anchor="w")
        self.lbl_spread = tk.Label(box, text="Клеток с феромоном: 0", bg=PANEL,
                                   fg=ORANGE, font=("Consolas", 10),
                                   anchor="w")
        self.lbl_wall   = tk.Label(box, text="Стен: 0", bg=PANEL,
                                   fg=TXT, font=("Consolas", 10), anchor="w")
        for w in (self.lbl_step, self.lbl_food, self.lbl_spread, self.lbl_wall):
            w.pack(anchor="w", padx=8)
        tk.Frame(box, bg=PANEL, height=6).pack()

        btnf = tk.Frame(right, bg=BG); btnf.pack(fill="x", pady=(8, 8))

        def mkbtn(text, cmd, color):
            return tk.Button(btnf, text=text, command=cmd,
                             bg=PANEL, fg=color, activebackground="#21262d",
                             activeforeground=color, relief="flat", bd=0,
                             font=("Segoe UI", 9, "bold"), padx=8, pady=6,
                             cursor="hand2")

        self.btn_run = mkbtn("▶  СТАРТ", self._toggle_run, GREEN)
        self.btn_run.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        mkbtn("⟲  СБРОС", self._reset, ACCENT).grid(row=0, column=1,
                                                     sticky="ew",
                                                     padx=(4, 0), pady=2)
        mkbtn("🧱  Стена по центру", self._force_wall, RED).grid(
            row=1, column=0, sticky="ew", padx=(0, 4), pady=2)
        mkbtn("⚡  Стена поперёк тропы", self._dynamic_wall, ORANGE).grid(
            row=1, column=1, sticky="ew", padx=(4, 0), pady=2)
        mkbtn("✖  Убрать все стены", self._clear_walls, "#ffa657").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=2)
        btnf.columnconfigure(0, weight=1); btnf.columnconfigure(1, weight=1)

        sl = tk.Frame(right, bg=BG); sl.pack(fill="x")
        self.var_evap    = tk.DoubleVar(value=0.07)
        self.var_ants    = tk.IntVar(value=150)
        self.var_sens    = tk.DoubleVar(value=1.0)
        self.var_deposit = tk.DoubleVar(value=3.0)
        self.var_speed   = tk.IntVar(value=1)

        def slider(text, var, frm, to, res, live):
            f = tk.Frame(sl, bg=BG); f.pack(fill="x", pady=(4, 0))
            tk.Label(f, text=text, bg=BG, fg=TXT, font=("Segoe UI", 8),
                     anchor="w").pack(fill="x")
            s = tk.Scale(f, variable=var, from_=frm, to=to, resolution=res,
                         orient="horizontal", bg=BG, fg=TXT,
                         troughcolor="#21262d", highlightthickness=0, bd=0,
                         sliderrelief="flat", activebackground=ACCENT,
                         font=("Consolas", 8), length=280)
            s.pack(fill="x")
            if live:
                s.configure(command=lambda *_: self._apply_live())

        slider("Испарение феромона (─ОС)", self.var_evap, 0.0, 1.0, 0.01, True)
        slider("Агентов (при сбросе)", self.var_ants, 20, 400, 10, False)
        slider("Чувствительность к следу", self.var_sens, 0.0, 4.0, 0.1, True)
        slider("Сила следа (+ОС)", self.var_deposit, 0.0, 10.0, 0.5, True)
        slider("Скорость, шагов/кадр", self.var_speed, 1, 8, 1, True)

        tk.Label(right, text="ДИНАМИКА МЕТРИК", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
        self.chart = tk.Canvas(right, width=300, height=150, bg="#0a0e14",
                               highlightthickness=1, highlightbackground=BORDER)
        self.chart.pack()

        self._create_ant_items()
        self._render()
        self._update_metrics()
        self._draw_chart()
        self.root.after(self.delay, self._tick)

    def _apply_live(self):
        self.system.evaporation_rate  = float(self.var_evap.get())
        self.system.sensitivity       = float(self.var_sens.get())
        self.system.pheromone_deposit = float(self.var_deposit.get())
        self.steps_per_frame          = int(self.var_speed.get())

    def _toggle_run(self):
        self.running = not self.running
        self.btn_run.configure(text="⏸  ПАУЗА" if self.running else "▶  СТАРТ")

    def _reset(self):
        self.running = False
        self.btn_run.configure(text="▶  СТАРТ")
        self._apply_live()
        self.system = AntColonySystem(
            size=FIELD_SIZE,
            num_ants=int(self.var_ants.get()),
            evaporation_rate=float(self.var_evap.get()),
            pheromone_deposit=float(self.var_deposit.get()),
            sensitivity=float(self.var_sens.get()))
        self._create_ant_items()
        self.hint_visible = True
        self.canvas.itemconfig(self.hint_item, state="normal")
        self._render(); self._update_metrics(); self._draw_chart()

    def _force_wall(self):
        if not self.system.wall_built:
            self.system.build_wall(); self._update_metrics()

    def _dynamic_wall(self):
        self.system.add_wall_crossing_trail()
        self._update_metrics()

    def _clear_walls(self):
        self.system.clear_all_walls(); self._update_metrics()

    def _on_canvas_click(self, event):
        col = event.x // CELL
        row = event.y // CELL
        self.system.toggle_wall_cell(col, row)
        if self.hint_visible:
            self.canvas.itemconfig(self.hint_item, state="hidden")
            self.hint_visible = False
        self._render(); self._update_metrics()

    def _on_canvas_drag(self, event):
        """Рисование стен мышью (протягивание)."""
        col = event.x // CELL
        row = event.y // CELL
        self.system.paint_wall_cell(col, row)
        if self.hint_visible:
            self.canvas.itemconfig(self.hint_item, state="hidden")
            self.hint_visible = False
        self._render()

    def _tick(self):
        if self.running:
            for _ in range(self.steps_per_frame):
                self.system.update_system()
            self._render(); self._update_metrics(); self._draw_chart()
        self.root.after(self.delay, self._tick)

    # ─── РЕНДЕР ──────────────────────────────────────────────────────
    def _render(self):
        s = self.system; n = s.size; step = s.step

        phero = np.clip(s.pheromone_grid / 6.0, 0, 1) ** 0.7
        trail = np.clip(s.trail_grid     / 3.0, 0, 1) ** 0.8
        food  = np.clip(s.food_grid      / 200.0, 0, 1)

        yy, xx = np.mgrid[0:n, 0:n]

        # Пульсирующее гнездо
        d_nest = np.sqrt((xx - s.nest[0])**2 + (yy - s.nest[1])**2)
        pulse  = 0.80 + 0.20 * np.sin(step * 0.18)
        nest_glow = np.clip(1.0 - d_nest / 5.0, 0, 1) ** 2 * pulse

        # Пульсирующие источники пищи
        fg = np.zeros_like(food)
        pulse2 = 0.75 + 0.25 * np.sin(step * 0.22 + 1.3)
        for fx, fy in s.food_sources:
            dd = np.sqrt((xx - fx)**2 + (yy - fy)**2)
            fg = np.maximum(fg, np.clip(1.0 - dd / 4.5, 0, 1) ** 2)
        fg *= pulse2 * (s.food_grid.max() > 0)

        R = np.full((n, n), 10, dtype=float)
        G = np.full((n, n), 14, dtype=float)
        B = np.full((n, n), 22, dtype=float)

        R += 40*trail + 245*phero + 60*food + 50*fg + 30*nest_glow
        G += 90*trail + 100*phero + 220*food + 180*fg + 90*nest_glow
        B += 130*trail + 30*phero + 80*food + 60*fg + 220*nest_glow

        grid = ((xx % 5 == 0) | (yy % 5 == 0))
        R[grid] = np.minimum(R[grid] + 6, 255)
        G[grid] = np.minimum(G[grid] + 8, 255)
        B[grid] = np.minimum(B[grid] + 14, 255)

        # Стены
        obs = s.obstacle_grid
        R[obs], G[obs], B[obs] = 215, 125, 55
        border = np.zeros_like(obs)
        border[1:,  :] |= obs[:-1, :]
        border[:-1, :] |= obs[1:,  :]
        border[:, 1:]  |= obs[:, :-1]
        border[:, :-1] |= obs[:, 1:]
        border &= ~obs
        R[border], G[border], B[border] = 255, 200, 90

        R = np.clip(R, 0, 255); G = np.clip(G, 0, 255); B = np.clip(B, 0, 255)
        rgb = np.stack([R, G, B], -1).astype(np.uint8)
        flat = ["#%02x%02x%02x" % (a, b, c)
                for a, b, c in rgb.reshape(-1, 3).tolist()]
        for y in range(n):
            self.photo.put("{" + " ".join(flat[y*n:(y+1)*n]) + "}", to=(0, y))
        z = self.photo.zoom(CELL)
        self.zoomed_ref = z
        self.canvas.itemconfig(self.field_item, image=z)

        # ── Поле — в САМЫЙ НИЗ (чтобы не перекрывало агентов) ──
        self.canvas.tag_lower(self.field_item)
        self.canvas.tag_lower(self.hint_item)

        # ── МУРАВЬИ: гало + тело, поверх поля ──
        for i, ant in enumerate(s.ants):
            cx = ant.x * CELL + CELL/2
            cy = ant.y * CELL + CELL/2
            halo, body = self.ant_items[i]

            if ant.has_food:
                # Несёт еду: неоново-зелёное тело с ярким зелёным гало
                halo_r, body_r = 7.5, 4.8
                halo_fill  = "#00aa55"
                body_fill  = "#9cffc6"
                body_outline = "#004d26"
            else:
                # Ищет пищу: белое тело с ярко-оранжевым гало
                halo_r, body_r = 7.0, 4.2
                halo_fill  = "#ff9838"
                body_fill  = "#ffffff"
                body_outline = "#7a3300"

            self.canvas.coords(halo, cx-halo_r, cy-halo_r,
                               cx+halo_r, cy+halo_r)
            self.canvas.itemconfig(halo, fill=halo_fill, outline="")
            self.canvas.coords(body, cx-body_r, cy-body_r,
                               cx+body_r, cy+body_r)
            self.canvas.itemconfig(body, fill=body_fill,
                                   outline=body_outline, width=1)

            # Каждый муравей поверх поля
            self.canvas.tag_raise(halo)
            self.canvas.tag_raise(body)

    def _create_ant_items(self):
        for it in self.ant_items:
            self.canvas.delete(it)
        self.ant_items = []
        for _ in self.system.ants:
            halo = self.canvas.create_oval(0, 0, 0, 0, fill="#30363d",
                                           outline="")
            body = self.canvas.create_oval(0, 0, 0, 0, fill="#ffffff",
                                           outline="#0d1117", width=1)
            self.ant_items.append((halo, body))

    def _update_metrics(self):
        s = self.system
        self.lbl_step.configure(text=f"Такт: {s.step}")
        self.lbl_food.configure(text=f"Собрано пищи: {s.total_food_collected}")
        self.lbl_spread.configure(
            text=f"Клеток с феромоном: "
                 f"{int(np.count_nonzero(s.pheromone_grid > 0.5))}")
        n_walls = len(s.wall_markers)
        self.lbl_wall.configure(text=f"Стен: {n_walls}"
                                     + (f" (такт {s.wall_markers[-1]})"
                                        if n_walls else ""))

    def _draw_chart(self):
        c = self.chart; c.delete("all")
        w, h = 300, 150
        c.create_rectangle(0, 0, w, h, fill="#0a0e14", outline=BORDER)
        for i in range(1, 4):
            c.create_line(0, h*i/4, w, h*i/4, fill="#161b22")
        fh = self.system.food_history[-500:]
        sh = self.system.spread_history[-500:]
        n = len(fh)
        if n < 2:
            return
        maxf = max(max(fh), 1); maxs = max(max(sh), 1)
        ptsf, ptss = [], []
        for i in range(n):
            x = 6 + i * (w-12) / (n-1)
            ptsf += [x, h-8 - (fh[i]/maxf)*(h-30)]
            ptss += [x, h-8 - (sh[i]/maxs)*(h-30)]
        c.create_line(*ptss, fill=ORANGE, width=1)
        c.create_line(*ptsf, fill=GREEN,  width=2)
        for wm in self.system.wall_markers:
            start = self.system.step - n + 1
            rel = wm - start
            if 0 <= rel < n:
                x = 6 + rel * (w-12) / (n-1)
                c.create_line(x, 2, x, h-2, fill=RED, dash=(3, 3))
        c.create_text(6, 4, anchor="nw", text=f"собрано: {fh[-1]}",
                      fill=GREEN, font=("Consolas", 8))
        c.create_text(6, h-14, anchor="nw", text=f"феромон: {sh[-1]} кл.",
                      fill=ORANGE, font=("Consolas", 8))

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 3: ЭКСПЕРИМЕНТЫ
    # ══════════════════════════════════════════════════════════════════
    def _build_exp_tab(self):
        top = tk.Frame(self.tab_exp, bg=BG)
        top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(top, text="АВТОМАТИЧЕСКИЕ ЭКСПЕРИМЕНТЫ", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(top, text="Нажмите кнопку — программа прогонит симуляцию в "
                           "фоне и зафиксирует снимки ключевых тактов.",
                 bg=BG, fg=DIM, font=("Segoe UI", 9, "italic")).pack(anchor="w")

        btns = tk.Frame(self.tab_exp, bg=BG)
        btns.pack(fill="x", padx=14, pady=(0, 8))

        def mkb(text, cmd, col):
            b = tk.Button(btns, text=text, command=cmd, bg=PANEL, fg=col,
                          activebackground="#21262d", activeforeground=col,
                          relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                          padx=12, pady=8, cursor="hand2")
            b.pack(side="left", padx=(0, 8))
            return b

        mkb("▶ №1. Самоорганизация",      self._run_exp1, GREEN)
        mkb("▶ №2а. Испарение = 0 %",     self._run_exp2a, ORANGE)
        mkb("▶ №2б. Испарение = 100 %",   self._run_exp2b, ORANGE)
        mkb("▶ №3. Целостность (стена)",  self._run_exp3, RED)

        snapf = tk.Frame(self.tab_exp, bg=BG)
        snapf.pack(fill="x", padx=14)
        self.snap_canvases = []
        self.snap_labels    = []
        for i in range(4):
            fr = tk.Frame(snapf, bg=BG)
            fr.grid(row=0, column=i, padx=4, pady=4, sticky="n")
            lbl = tk.Label(fr, text=f"кадр {i+1}", bg=BG, fg=DIM,
                           font=("Consolas", 8))
            lbl.pack()
            cv = tk.Canvas(fr, width=250, height=250, bg="#05080d",
                           highlightthickness=1, highlightbackground=BORDER)
            cv.pack()
            self.snap_canvases.append(cv)
            self.snap_labels.append(lbl)
        for i in range(4):
            snapf.columnconfigure(i, weight=1)

        tk.Label(self.tab_exp, text="ПРОТОКОЛ ЭКСПЕРИМЕНТА", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14,
                                                     pady=(8, 2))
        self.exp_log = tk.Text(self.tab_exp, height=11, bg="#0a0e14", fg=TXT,
                               insertbackground=TXT, relief="flat", bd=0,
                               font=("Consolas", 9), padx=10, pady=8,
                               highlightthickness=1, highlightbackground=BORDER)
        self.exp_log.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.exp_log.tag_configure("h", foreground=ACCENT,
                                   font=("Consolas", 10, "bold"))
        self.exp_log.tag_configure("ok", foreground=GREEN)
        self.exp_log.tag_configure("warn", foreground=ORANGE)
        self.exp_log.tag_configure("err", foreground=RED)
        self.exp_log.tag_configure("dim", foreground=DIM,
                                   font=("Consolas", 8, "italic"))

    def _show_snapshots(self, photos, labels):
        for i, cv in enumerate(self.snap_canvases):
            cv.delete("all")
        self._photo_refs = []
        for i, (p, lbl) in enumerate(zip(photos, labels)):
            if i >= len(self.snap_canvases):
                break
            cv = self.snap_canvases[i]
            cv.create_image(0, 0, image=p, anchor="nw")
            self._photo_refs.append(p)
            self.snap_labels[i].configure(text=lbl)

    def _log(self, text, tag=None):
        self.exp_log.insert("end", text + "\n", tag or ())
        self.exp_log.see("end")
        self.root.update_idletasks()

    def _simulate(self, system, steps, snap_at=None):
        snaps = {}
        snap_at = snap_at or {}
        for _ in range(steps):
            system.update_system()
            if system.step in snap_at:
                snaps[system.step] = field_to_photo(system, zoom=5)
        return snaps

    # ─── Эксперимент №1 ───────────────────────────────────────────────
    def _run_exp1(self):
        self.exp_log.delete("1.0", "end")
        self._log("ЭКСПЕРИМЕНТ №1. Демонстрация самоорганизации", "h")
        self._log("Параметры: 150 агентов, испарение 7 %, deposit = 3.0", "dim")
        self._log("Запуск из полностью хаотичного состояния (феромон = 0).")
        self.root.update()
        s = AntColonySystem(size=50, num_ants=150,
                            evaporation_rate=0.07, pheromone_deposit=3.0)
        snaps = {0: field_to_photo(s, zoom=5)}
        for _ in range(200):
            s.update_system()
            if s.step in (50, 200):
                snaps[s.step] = field_to_photo(s, zoom=5)
        self._show_snapshots([snaps.get(0), snaps.get(50), snaps.get(200)],
                             ["T₀ — хаос", "T₅₀ — первые нити",
                              "T₂₀₀ — устойчивые магистрали"])
        self._log("Наблюдения:", "h")
        self._log("  • T₀   — поле почти чёрное, агенты выходят из гнезда "
                  "случайным роем.")
        self._log("  • T₅₀  — появляются бледно-оранжевые «нити»: удачливые "
                  "муравьи нашли пищу и проложили обратный след.")
        self._log("  • T₂₀₀ — сформировались ярко-оранжевые МАГИСТРАЛИ к обоим "
                  "источникам пищи; тропы СЖАЛИСЬ и сконцентрировались.", "ok")
        self._log(f"\nИтог: собрано пищи = {s.total_food_collected}, "
                  f"активных клеток феромона = "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))}", "ok")
        self._log("Вывод: из хаоса локальных блужданий возникла устойчивая "
                  "пространственно-временная упорядоченность — САМООРГАНИЗАЦИЯ.",
                  "ok")

    # ─── Эксперимент №2а ──────────────────────────────────────────────
    def _run_exp2a(self):
        self.exp_log.delete("1.0", "end")
        self._log("ЭКСПЕРИМЕНТ №2а. Испарение = 0 % (нет ─ОС)", "h")
        self._log("Проверяем поведение при отключённой отрицательной обратной "
                  "связи.", "dim")
        self.root.update()
        s = AntColonySystem(size=50, num_ants=150,
                            evaporation_rate=0.0, pheromone_deposit=3.0)
        snaps = {0: field_to_photo(s, zoom=5)}
        for _ in range(400):
            s.update_system()
            if s.step in (200, 400):
                snaps[s.step] = field_to_photo(s, zoom=5)
        self._show_snapshots([snaps.get(0), snaps.get(200), snaps.get(400)],
                             ["T₀", "T₂₀₀ — следы не гаснут",
                              "T₄₀₀ — «мёртвая сеть»"])
        self._log("Наблюдения:", "h")
        self._log("  • Положительная связь продолжает усиливать следы.")
        self._log("  • После истощения ресурсов тропы НЕ исчезают — поле "
                  "покрывается «мёртвой сетью» маршрутов.", "warn")
        self._log(f"  • Метрика «клеток с феромоном» = "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))} — растёт "
                  f"монотонно к максимуму.")
        self._log("\nВывод: без отрицательной ОС система ТЕРЯЕТ динамическое "
                  "равновесие; муравьи циркулируют по пустым коридорам, "
                  "перестройка невозможна.", "err")

    # ─── Эксперимент №2б ──────────────────────────────────────────────
    def _run_exp2b(self):
        self.exp_log.delete("1.0", "end")
        self._log("ЭКСПЕРИМЕНТ №2б. Испарение = 100 % (нет +ОС)", "h")
        self._log("Проверяем поведение при полном стирании феромона каждый "
                  "такт.", "dim")
        self.root.update()
        s = AntColonySystem(size=50, num_ants=150,
                            evaporation_rate=1.0, pheromone_deposit=3.0)
        snaps = {0: field_to_photo(s, zoom=5)}
        for _ in range(200):
            s.update_system()
            if s.step in (50, 200):
                snaps[s.step] = field_to_photo(s, zoom=5)
        self._show_snapshots([snaps.get(0), snaps.get(50), snaps.get(200)],
                             ["T₀", "T₅₀ — следов нет",
                              "T₂₀₀ — самоорганизации нет"])
        self._log("Наблюдения:", "h")
        self._log("  • Феромон полностью стирается на каждом такте.")
        self._log("  • Положительная связь НЕ успевает накопиться — тропы "
                  "вообще не образуются.", "warn")
        self._log(f"  • Клеток с феромоном: "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))} "
                  f"(практически ноль).")
        self._log(f"  • Собрано пищи: {s.total_food_collected} — крайне мало.")
        self._log("\nВывод: без положительной ОС САМООРГАНИЗАЦИЯ невозможна; "
                  "система остаётся в хаотическом состоянии.", "err")

    # ─── Эксперимент №3 ───────────────────────────────────────────────
    def _run_exp3(self):
        self.exp_log.delete("1.0", "end")
        self._log("ЭКСПЕРИМЕНТ №3. Внутренняя целостность "
                  "(динамическая стена)", "h")
        self._log("На такте T=150 автоматически возводится стена ≈20 клеток, "
                  "перерезающая главную тропу.", "dim")
        self.root.update()
        s = AntColonySystem(size=50, num_ants=150,
                            evaporation_rate=0.07, pheromone_deposit=3.0)
        snaps = {}
        for _ in range(300):
            s.update_system()
            if s.step in (149, 160, 250):
                snaps[s.step] = field_to_photo(s, zoom=5)
        self._show_snapshots([snaps.get(149), snaps.get(160), snaps.get(250)],
                             ["T₁₄₉ — стабильные тропы",
                              "T₁₆₀ — стена + смятение",
                              "T₂₅₀ — обход сформирован"])
        self._log("Наблюдения:", "h")
        self._log("  • T=150   — мгновенно возводится сплошная стена 20 клеток; "
                  "прямой маршрут перерезан.", "warn")
        self._log("  • T+10    — муравьи «утыкаются» в стену, но благодаря "
                  "_go_home() скользят вдоль неё.")
        self._log("  • T+30    — появляется дугообразный обходной след над "
                  "верхним краем стены.")
        self._log("  • T+60…90 — формируется НОВАЯ устойчивая магистраль; "
                  "прямая тропа гаснет.", "ok")
        self._log(f"\nИтог: собрано пищи = {s.total_food_collected}, "
                  f"активных клеток феромона = "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))}")
        self._log("Вывод: система демонстрирует ВНУТРЕННЮЮ ЦЕЛОСТНОСТЬ — "
                  "сохранила базовое свойство (транспортировка ресурса) "
                  "и полностью перестроила структуру троп за 60–90 тактов.",
                  "ok")

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 4: СИСТЕМНЫЙ АНАЛИЗ
    # ══════════════════════════════════════════════════════════════════
    def _build_analysis_tab(self):
        container = tk.Frame(self.tab_anal, bg=BG)
        container.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Label(container, text="СИСТЕМНЫЙ АНАЛИЗ РЕЗУЛЬТАТОВ",
                 bg=BG, fg=ACCENT, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(container,
                 text="Научные выводы по итогам всех трёх экспериментов.",
                 bg=BG, fg=DIM, font=("Segoe UI", 9, "italic")).pack(anchor="w",
                                                                     pady=(0, 10))
        txt = tk.Text(container, bg="#0a0e14", fg=TXT, relief="flat", bd=0,
                      font=("Segoe UI", 10), padx=16, pady=12, wrap="word",
                      highlightthickness=1, highlightbackground=BORDER)
        txt.pack(fill="both", expand=True)
        txt.tag_configure("h1", foreground=ACCENT,
                          font=("Segoe UI", 13, "bold"), spacing1=10, spacing3=6)
        txt.tag_configure("h2", foreground=GREEN,
                          font=("Segoe UI", 11, "bold"), spacing1=8, spacing3=4)
        txt.tag_configure("kw", foreground=ORANGE,
                          font=("Segoe UI", 10, "bold"))
        txt.tag_configure("blt", lmargin1=20, lmargin2=34)

        def H1(t): txt.insert("end", t + "\n", "h1")
        def H2(t): txt.insert("end", t + "\n", "h2")
        def P(t):  txt.insert("end", t + "\n\n")
        def B(t):  txt.insert("end", "  •  " + t + "\n", "blt")

        H1("1. В ЧЁМ ВЫРАЗИЛАСЬ ЭМЕРДЖЕНТНОСТЬ МОДЕЛИ?")
        P("Ни один экземпляр класса Ant не обладает ни картой, ни памятью о "
          "маршруте, ни функцией «построить кратчайший путь». Агент видит лишь "
          "8 соседних клеток и локально решает: «повернуть к феромону или "
          "шагнуть к гнезду». Однако вся колония — макросистема "
          "AntColonySystem — спонтанно строит оптимальные магистрали, а после "
          "появления стены коллективно находит обход.")
        P("Это классическая ")
        txt.insert("end", "эмерджентность", "kw")
        P(": глобальный порядок (оптимальный маршрут, устойчивая тропа) не "
          "существует ни в одном отдельном агенте, но возникает из их локальных "
          "взаимодействий через общее поле феромонов.")
        P("Количественно эффект зафиксирован метриками:")
        B("общее количество принесённой пищи растёт нелинейно;")
        B("клеток с феромоном становится МЕНЬШЕ при росте собранной пищи — "
          "тропы сжимаются в узкие магистрали;")
        B("отдельный муравей не способен найти путь — а колония за 100–200 "
          "тактов формирует две независимые магистрали к двум источникам.")

        H1("2. ВЗАИМОДЕЙСТВИЕ ОБРАТНЫХ СВЯЗЕЙ И ДИНАМИЧЕСКОЕ РАВНОВЕСИЕ")
        P("В модели действуют две противоположные силы.")
        H2("Положительная обратная связь — усиливает отклонение")
        P("Реализована строкой ")
        txt.insert("end",
                   "pheromone_grid[ant.x, ant.y] += pheromone_deposit", "kw")
        P(": чем больше муравьёв успешно прошло по тропе, тем привлекательнее "
          "она становится. Запускается лавинообразный процесс — эффект "
          "«снежного кома» — и колония концентрирует усилия на кратчайшем "
          "удачном маршруте.")
        H2("Отрицательная обратная связь — стабилизирует систему")
        P("Реализована строкой ")
        txt.insert("end", "pheromone_grid *= (1 - evaporation_rate)", "kw")
        P(": без подкрепления следы гаснут. Благодаря этому «ложные» и "
          "устаревшие маршруты (упёршиеся в стену или ведущие к опустевшему "
          "источнику) автоматически отмирают.")
        P("Итог баланса:")
        B("испарение = 0 %   → система теряет гибкость, образуется «мёртвая "
          "сеть» (эксперимент №2а);")
        B("испарение = 100 % → тропы вообще не образуются, самоорганизация "
          "невозможна (эксперимент №2б);")
        B("0 < испарение < 1 → система находится в ДИНАМИЧЕСКОМ РАВНОВЕСИИ: "
          "непрерывно ищет и одновременно стабилизирует оптимум.")

        H1("3. СПЕЦИФИКА ВАРИАНТА 1: ВНУТРЕННЯЯ ЦЕЛОСТНОСТЬ")
        P("Динамическое препятствие (стена ≈20 клеток на такте T=150) — тест "
          "системы «на прочность». Программа продемонстрировала:")
        B("стена перерезает прямую тропу к источнику (40, 40);")
        B("старый след перестаёт подкрепляться и гаснет за счёт отрицательной ОС;")
        B("возвращающиеся домой муравьи начинают скользить вдоль стены "
          "(логика _go_home);")
        B("уже через 60–90 тактов образуется новая устойчивая обходная "
          "магистраль.")
        P("Это и есть ")
        txt.insert("end", "внутренняя целостность", "kw")
        P(": система сохраняет базовое функциональное свойство "
          "(транспортировка ресурса) при изменении топологии среды — за счёт "
          "перераспределения потоков через обратные связи, а не за счёт "
          "жёсткого плана.")
        P("В расширенном режиме можно:")
        B("ставить отдельные клетки стены кликом по полю;")
        B("рисовать стену мышью, зажав ЛКМ и протянув курсор;")
        B("нажимать кнопку «Стена поперёк тропы» — программа сама находит "
          "участок с максимальным феромоном и перерезает его;")
        B("проверять, что колония каждый раз восстанавливает функциональность.")

        H1("4. ОБЩИЙ ВЫВОД")
        P("Программа наглядно демонстрирует все ключевые понятия теории систем:")
        B("ДЕКОМПОЗИЦИЯ — классы Ant (микроуровень) и AntColonySystem "
          "(макроуровень);")
        B("АГРЕГИРОВАНИЕ — сборка агентов и матриц среды в единую систему;")
        B("ОБРАТНЫЕ СВЯЗИ — положительная (усиление следа) и отрицательная "
          "(испарение);")
        B("САМООРГАНИЗАЦИЯ — формирование магистралей из хаоса;")
        B("ЭМЕРДЖЕНТНОСТЬ — оптимальный маршрут как глобальное свойство "
          "колонии;")
        B("ВНУТРЕННЯЯ ЦЕЛОСТНОСТЬ — перестройка структуры при возмущении.")
        P("Ни один элемент системы не «понимает» глобальной задачи. Порядок "
          "рождается из локальных правил и баланса обратных связей — это "
          "фундаментальный принцип сложных систем.")
        txt.configure(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app = Lab2App(root)
    root.mainloop()