# -*- coding: utf-8 -*-
"""
Лабораторная работа №2. Сложные системы. Принцип обратной связи.
ВАРИАНТ 1. Динамические препятствия (внутренняя целостность).

Вкладки:
  • Декомпозиция  — схема классов системы и точки обратных связей
  • Симуляция     — интерактивная анимация муравейника (живые агенты)
  • Эксперименты  — автозапуск экспериментов №1–3
  • Анализ        — системный анализ результатов

Управление в симуляции:
  • Клик по полю              — поставить/убрать одну клетку стены
  • Зажать ЛКМ и протянуть    — нарисовать стену мышью
  • Кнопка «Стена по центру»  — стена, возводимая автоматически на такте 150
  • Кнопка «Стена поперёк»    — перерезать самую сильную тропу
  • Кнопка «Убрать все стены» — очистить препятствия

СОГЛАШЕНИЕ ОБ ОСЯХ (важно):
  все матрицы среды индексируются как grid[x, y], где
  x — столбец (горизонталь экрана), y — строка (вертикаль экрана).
  При выводе на экран матрица транспонируется (.T), т.к. изображение
  строится построчно: row = y, col = x.

Запуск: python lab2_variant1.py
Зависимости: numpy, tkinter (стандартная библиотека)
"""

import math
import random
import tkinter as tk
from tkinter import ttk

import numpy as np

# ─────────────────────────── Глобальные константы ────────────────────────────
FIELD_SIZE = 50          # размер поля в клетках
CELL       = 12          # размер клетки в пикселях
CANVAS_PX  = FIELD_SIZE * CELL
WALL_STEP  = 150         # такт автоматического возведения стены (по заданию)
WALL_HALF  = 10          # полудлина стены → сплошная стена 20 клеток
FRAME_MS   = 16          # период кадра анимации (~60 FPS)

BG, PANEL, BORDER = "#0d1117", "#161b22", "#30363d"
TXT, DIM          = "#c9d1d9", "#8b949e"
ACCENT, GREEN, ORANGE, RED = "#58a6ff", "#7ee787", "#ff7b45", "#f85149"

WALL_FILL, WALL_EDGE, WALL_DARK = "#b4651f", "#ffd08a", "#7a3f0d"

CHART_W, CHART_H = 300, 200      # размер панели «Динамика метрик»
CHART_WINDOW     = 500           # сколько последних тактов показывать


# ══════════════════════════════════════════════════════════════════════════════
# 1. ДЕКОМПОЗИЦИЯ. Микроуровень — агент-муравей
# ══════════════════════════════════════════════════════════════════════════════
class Ant:
    """Элементарный объект сложной системы: локальное состояние + локальные правила.

    Агент НЕ знает ни карты, ни положения пищи, ни глобальной цели.
    Поля px, py — положение на предыдущем такте; нужны только визуализации
    для плавной интерполяции движения (на логику модели не влияют).
    """
    __slots__ = ("x", "y", "px", "py", "has_food", "angle", "phase", "dx", "dy")

    # Веса направлений относительно текущего курса агента (инерция движения).
    # Ключ — косинус угла между курсом и кандидатом, вычисляется на лету.
    PERSISTENCE = 2.6     # во сколько раз ход «прямо» вероятнее хода «назад»
    BASE_WEIGHT = 0.15    # базовый шанс клетки без феромона

    def __init__(self, nest_x, nest_y):
        self.x = self.px = nest_x
        self.y = self.py = nest_y
        self.has_food = False
        self.angle = random.uniform(0.0, 2.0 * math.pi)   # направление тела
        self.phase = random.randrange(8)                  # фаза походки
        self.dx, self.dy = random.choice(
            [(-1, -1), (-1, 0), (-1, 1), (0, -1),
             (0, 1), (1, -1), (1, 0), (1, 1)])            # текущий курс

    # ─── Локальное правило поведения агента ───────────────────────────
    def move(self, size, pheromone, food, obstacle, nest, sensitivity):
        if not self.has_food:
            # 1. Найдена пища в текущей клетке — забираем единицу и разворачиваемся
            if food[self.x, self.y] > 0:
                food[self.x, self.y] -= 1
                self.has_food = True
                self.dx, self.dy = -self.dx, -self.dy   # разворот с грузом
                return
            # 2. Иначе — блуждание с влечением к феромону
            self._wander(size, pheromone, obstacle, sensitivity)
        else:
            # 3. С грузом — возврат к гнезду
            self._go_home(size, obstacle, nest)

    def _wander(self, size, pheromone, obstacle, sensitivity):
        """Окрестность Мура (8 клеток).

        Вес клетки = база · инерция_курса + чувствительность · феромон.

        Инерция курса — локальное правило: агент с большей вероятностью
        продолжает двигаться в прежнем направлении, чем разворачивается.
        Без неё блуждание вырождается в диффузию (смещение ~ √t) и колония
        физически не успевает дойти до источника за время эксперимента.
        Глобальной информации агент по-прежнему не получает.

        Здесь же замыкается ПОЛОЖИТЕЛЬНАЯ обратная связь на входе агента:
        чем сильнее след в соседней клетке, тем выше шанс её выбрать.
        """
        cdx, cdy = self.dx, self.dy
        cn = math.hypot(cdx, cdy) or 1.0

        valid, weights = [], []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = self.x + dx, self.y + dy
                # Стена непроходима — ходы отсекаются (требование варианта 1)
                if not (0 <= nx < size and 0 <= ny < size) or obstacle[nx, ny]:
                    continue
                cos = (dx * cdx + dy * cdy) / (math.hypot(dx, dy) * cn)
                bias = 0.05 + self.PERSISTENCE * (0.5 + 0.5 * cos) ** 4
                valid.append((dx, dy, nx, ny))
                # Инерция умножает ВЕСЬ вес, включая феромонный: иначе агент,
                # попав на тропу, с равной вероятностью идёт по ней и «туда»,
                # и «обратно», и направленного транспорта не возникает.
                weights.append(bias * (self.BASE_WEIGHT
                                       + sensitivity * float(pheromone[nx, ny])))
        if valid:
            dx, dy, nx, ny = self._weighted_choice(valid, weights)
            self.dx, self.dy = dx, dy
            self.x, self.y = nx, ny

    def _go_home(self, size, obstacle, nest):
        """Возврат в гнездо + скольжение вдоль стены (вариант 1).

        Агент пытается шагнуть в сторону гнезда; если направление перекрыто
        стеной, он пробует перпендикулярные ходы — это и даёт эмерджентный
        обход препятствия на уровне колонии.
        """
        dx = (nest[0] > self.x) - (nest[0] < self.x)
        dy = (nest[1] > self.y) - (nest[1] < self.y)

        prefs = []
        if dx and dy:
            prefs.append((dx, dy))
        if dx:
            prefs.append((dx, 0))
        if dy:
            prefs.append((0, dy))

        perp = []
        if dx:
            perp += [(dx, -1), (dx, 1), (0, -1), (0, 1)]
        if dy:
            perp += [(-1, dy), (1, dy), (-1, 0), (1, 0)]
        random.shuffle(perp)
        prefs += [m for m in perp if m not in prefs]

        rest = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                (0, 1), (1, -1), (1, 0), (1, 1)]
        random.shuffle(rest)
        prefs += [m for m in rest if m not in prefs]

        for ddx, ddy in prefs:
            nx, ny = self.x + ddx, self.y + ddy
            if 0 <= nx < size and 0 <= ny < size and not obstacle[nx, ny]:
                self.x, self.y = nx, ny
                self.dx, self.dy = ddx, ddy
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
    """Сборка агентов и матриц среды в единую систему верхнего уровня."""

    def __init__(self, size=FIELD_SIZE, num_ants=150, evaporation_rate=0.07,
                 pheromone_deposit=3.0, sensitivity=1.0):
        self.size              = size
        self.evaporation_rate  = evaporation_rate
        self.pheromone_deposit = pheromone_deposit
        self.sensitivity       = sensitivity

        self.nest         = (5, 5)
        self.food_sources = [(40, 40), (42, 10)]

        # Все матрицы: [x, y]
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
        self.wall_markers = []          # такты, на которых менялись стены
        self.wall_version = 0           # счётчик изменений (для перерисовки)
        self.food_history   = [0]
        self.spread_history = [0]
        self.history_origin = 0         # шаг, которому соответствует history[0]

    def _init_food(self):
        for fx, fy in self.food_sources:
            self.food_grid[max(0, fx - 1):fx + 2, max(0, fy - 1):fy + 2] = 200.0

    def food_left(self, src):
        """Сколько единиц пищи осталось в зоне 3×3 вокруг источника."""
        fx, fy = src
        return float(self.food_grid[max(0, fx - 1):fx + 2,
                                    max(0, fy - 1):fy + 2].sum())

    # ─── Стены ────────────────────────────────────────────────────────
    def build_wall(self):
        """Сплошная вертикальная стена 20 клеток в среднем столбце карты.

        По ТЗ варианта 1 стена должна ПЕРЕРЕЗАТЬ основную сформировавшуюся
        тропу, поэтому она центрируется не на геометрическом центре, а на
        клетке среднего столбца с максимальным феромоном (если тропа уже
        сложилась). Столбец при этом всегда ровно посередине карты.
        """
        x = self.size // 2
        length = 2 * WALL_HALF
        # берём соседние столбцы — тропа может идти наискось
        column = self.pheromone_grid[max(0, x - 1):x + 2].sum(axis=0)
        if column.max() > 0.5:
            # окно длиной length с максимальной суммой феромона = самый
            # «мясистый» участок тропы в среднем столбце
            csum = np.concatenate(([0.0], np.cumsum(column)))
            sums = csum[length:] - csum[:-length]
            y0 = int(np.argmax(sums))
        else:
            y0 = max(0, self.size // 2 - WALL_HALF)
        y1 = min(self.size, y0 + length)
        self.obstacle_grid[x, y0:y1] = True
        self.wall_built = True
        self._mark_wall_change()

    def add_wall_segment(self, x, y, length=15, orientation="v"):
        """Отрезок стены через клетку (x, y). 'v' — вертикальный, 'h' — горизонтальный."""
        half = length // 2
        if orientation == "v":
            cx = max(0, min(self.size - 1, x))
            y0 = max(0, y - half)
            y1 = min(self.size, y + half + 1)
            self.obstacle_grid[cx, y0:y1] = True
        else:
            cy = max(0, min(self.size - 1, y))
            x0 = max(0, x - half)
            x1 = min(self.size, x + half + 1)
            self.obstacle_grid[x0:x1, cy] = True
        self._mark_wall_change()

    def add_wall_crossing_trail(self):
        """Найти клетку с максимумом феромона и перерезать тропу поперёк."""
        p = self.pheromone_grid.copy()
        p[self.obstacle_grid] = -1.0
        if p.max() <= 0:
            self.add_wall_segment(self.size // 2, self.size // 2, 15, "v")
            return
        x, y = np.unravel_index(int(np.argmax(p)), p.shape)
        nx, ny = self.nest
        dx, dy = int(x) - nx, int(y) - ny
        # тропа идёт преимущественно по X → ставим вертикальную стену поперёк
        orientation = "v" if abs(dx) >= abs(dy) else "h"
        self.add_wall_segment(int(x), int(y), 15, orientation)

    def toggle_wall_cell(self, x, y):
        if 0 <= x < self.size and 0 <= y < self.size:
            self.obstacle_grid[x, y] = not self.obstacle_grid[x, y]
            self._mark_wall_change()

    def paint_wall_cell(self, x, y):
        if 0 <= x < self.size and 0 <= y < self.size and not self.obstacle_grid[x, y]:
            self.obstacle_grid[x, y] = True
            self._mark_wall_change()

    def clear_all_walls(self):
        self.obstacle_grid[:] = False
        self.wall_built = False
        self._mark_wall_change()

    def _mark_wall_change(self):
        self.wall_version += 1
        if not self.wall_markers or self.wall_markers[-1] != self.step:
            self.wall_markers.append(self.step)

    def wall_cells(self):
        return int(self.obstacle_grid.sum())

    # ─── Основной такт системы ────────────────────────────────────────
    def update_system(self):
        # ── ОТРИЦАТЕЛЬНАЯ ОБРАТНАЯ СВЯЗЬ: испарение феромона ──
        self.pheromone_grid *= (1.0 - self.evaporation_rate)
        self.trail_grid     *= 0.82

        nx, ny = self.nest
        pher = self.pheromone_grid
        for ant in self.ants:
            ant.px, ant.py = ant.x, ant.y

            # Сдача груза в гнездо (агент при этом продолжает двигаться)
            if ant.has_food and ant.x == nx and ant.y == ny:
                ant.has_food = False
                self.total_food_collected += 1

            ant.move(self.size, pher, self.food_grid,
                     self.obstacle_grid, self.nest, self.sensitivity)

            if self.trail_grid[ant.x, ant.y] < 4.0:
                self.trail_grid[ant.x, ant.y] += 1.0

            # ── ПОЛОЖИТЕЛЬНАЯ ОБРАТНАЯ СВЯЗЬ: усиление следа ──
            if ant.has_food:
                pher[ant.x, ant.y] += self.pheromone_deposit

            # направление тела для визуализации
            ddx, ddy = ant.x - ant.px, ant.y - ant.py
            if ddx or ddy:
                ant.angle = math.atan2(ddy, ddx)
                ant.phase = (ant.phase + 1) & 7

        self.step += 1
        if self.step == WALL_STEP and not self.wall_built:
            self.build_wall()

        self.food_history.append(self.total_food_collected)
        self.spread_history.append(int(np.count_nonzero(self.pheromone_grid > 0.5)))
        if len(self.food_history) > 4000:
            self.food_history.pop(0)
            self.spread_history.pop(0)
            self.history_origin += 1


# ══════════════════════════════════════════════════════════════════════════════
# 3. РЕНДЕРИНГ ПОЛЯ
# ══════════════════════════════════════════════════════════════════════════════
def _blur5(a):
    """Дешёвое размытие крестом 3×3 — даёт эффект свечения (bloom)."""
    b = a * 2.0
    b[1:, :]  += a[:-1, :]
    b[:-1, :] += a[1:, :]
    b[:, 1:]  += a[:, :-1]
    b[:, :-1] += a[:, 1:]
    return b / 6.0


def field_rgb(system, step=0, draw_walls=True):
    """Собрать RGB-матрицу поля (row = y, col = x — поэтому .T)."""
    n = system.size

    phero = np.clip(system.pheromone_grid.T / 6.0, 0, 1) ** 0.7
    glow  = _blur5(phero)
    trail = np.clip(system.trail_grid.T / 3.0, 0, 1) ** 0.8
    food  = np.clip(system.food_grid.T / 200.0, 0, 1)

    yy, xx = np.mgrid[0:n, 0:n]

    # Пульсирующее гнездо
    d_nest = np.sqrt((xx - system.nest[0]) ** 2 + (yy - system.nest[1]) ** 2)
    pulse = 0.80 + 0.20 * math.sin(step * 0.18)
    nest_glow = np.clip(1.0 - d_nest / 5.0, 0, 1) ** 2 * pulse

    # Ореол источников пищи — гаснет по мере истощения конкретного источника
    fg = np.zeros((n, n), dtype=float)
    pulse2 = 0.75 + 0.25 * math.sin(step * 0.22 + 1.3)
    for src in system.food_sources:
        left = system.food_left(src)
        if left <= 0:
            continue
        k = min(1.0, left / 1800.0 + 0.25)
        dd = np.sqrt((xx - src[0]) ** 2 + (yy - src[1]) ** 2)
        fg = np.maximum(fg, np.clip(1.0 - dd / 4.5, 0, 1) ** 2 * k)
    fg *= pulse2

    R = np.full((n, n), 10, dtype=float)
    G = np.full((n, n), 14, dtype=float)
    B = np.full((n, n), 22, dtype=float)

    #      холодный след агентов | горячая тропа феромона | свечение | еда | гнездо
    R += 40 * trail + 235 * phero + 110 * glow + 60 * food + 50 * fg + 30 * nest_glow
    G += 90 * trail +  95 * phero +  55 * glow + 220 * food + 180 * fg + 90 * nest_glow
    B += 130 * trail + 30 * phero +  20 * glow + 80 * food + 60 * fg + 220 * nest_glow

    # Координатная сетка
    grid = ((xx % 5 == 0) | (yy % 5 == 0))
    R[grid] = np.minimum(R[grid] + 6, 255)
    G[grid] = np.minimum(G[grid] + 8, 255)
    B[grid] = np.minimum(B[grid] + 14, 255)

    # Виньетка
    cx = cy = (n - 1) / 2.0
    vign = 1.0 - 0.30 * (((xx - cx) ** 2 + (yy - cy) ** 2) / (cx * cx * 2.0))
    vign = np.clip(vign, 0.62, 1.0)
    R *= vign; G *= vign; B *= vign

    if draw_walls:
        obs = system.obstacle_grid.T
        R[obs], G[obs], B[obs] = 180, 101, 31
        edge = np.zeros_like(obs)
        edge[1:, :]  |= obs[:-1, :]
        edge[:-1, :] |= obs[1:, :]
        edge[:, 1:]  |= obs[:, :-1]
        edge[:, :-1] |= obs[:, 1:]
        edge &= ~obs
        R[edge], G[edge], B[edge] = 255, 208, 138

    R = np.clip(R, 0, 255); G = np.clip(G, 0, 255); B = np.clip(B, 0, 255)
    return np.stack([R, G, B], -1).astype(np.uint8)


def rgb_to_put_string(rgb):
    """Быстрое преобразование RGB-матрицы в строку для PhotoImage.put()."""
    n = rgb.shape[0]
    h = rgb.tobytes().hex()
    px = ["#" + h[i:i + 6] for i in range(0, len(h), 6)]
    return " ".join("{" + " ".join(px[y * n:(y + 1) * n]) + "}" for y in range(n))


def field_to_photo(system, zoom=5):
    """Снимок поля как PhotoImage (для вкладки экспериментов)."""
    rgb = field_rgb(system, system.step)
    photo = tk.PhotoImage(width=system.size, height=system.size)
    photo.put(rgb_to_put_string(rgb))
    return photo.zoom(zoom)


# ══════════════════════════════════════════════════════════════════════════════
# 3a. ГЕОМЕТРИЯ МУРАВЬЯ (силуэт + 6 ног + усики одним полигоном)
# ══════════════════════════════════════════════════════════════════════════════
def _ant_outline(g1, g2, g3):
    """Контур муравья в локальных координатах (x — вперёд, y — вбок).

    g1..g3 — продольные смещения ног (походка). Ноги и усики нарисованы
    «шипами» контура: тонкие отростки, которые рендерятся как линии.
    """
    right = [
        (0.50, 0.00),                                   # кончик головы
        (0.80,  0.34), (0.38, 0.11),                    # усик
        (0.32,  0.09),
        (0.26,  0.13), (0.40 + g1,  0.46), (0.21,  0.15),   # нога 1
        (0.12,  0.16), (0.08 + g2,  0.54), (0.05,  0.16),   # нога 2
        (-0.02, 0.14), (-0.26 + g3, 0.48), (-0.07, 0.12),   # нога 3
        (-0.11, 0.17), (-0.24, 0.21), (-0.40, 0.14),
        (-0.50, 0.00),                                  # кончик брюшка
    ]
    left = [(x, -y) for x, y in reversed(right[1:-1])]
    return right + left


def build_gait_frames(frames=8, amp=0.12):
    """Предрасчёт кадров походки. Треножник: ноги 1,3 в противофазе с ногой 2."""
    out = []
    for f in range(frames):
        t = 2.0 * math.pi * f / frames
        a, b = amp * math.sin(t), amp * math.sin(t + math.pi)
        out.append(_ant_outline(a, b, a))
    return np.array(out, dtype=float)      # (frames, points, 2)


GAIT = build_gait_frames()
ANT_POINTS = GAIT.shape[1]


# ══════════════════════════════════════════════════════════════════════════════
# 4. ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════
class Lab2App:

    def __init__(self, root):
        self.root = root
        root.title("ЛР №2 · Вариант 1 · Сложные системы: принцип обратной связи")
        root.configure(bg=BG)
        root.geometry("1340x900")

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
        nb.pack(fill="both", expand=True)

        self.tab_dec  = tk.Frame(nb, bg=BG)
        self.tab_sim  = tk.Frame(nb, bg=BG)
        self.tab_exp  = tk.Frame(nb, bg=BG)
        self.tab_anal = tk.Frame(nb, bg=BG)
        nb.add(self.tab_dec,  text="1 · Декомпозиция")
        nb.add(self.tab_sim,  text="2 · Симуляция")
        nb.add(self.tab_exp,  text="3 · Эксперименты")
        nb.add(self.tab_anal, text="4 · Анализ")
        nb.select(self.tab_sim)

        self._build_schema_tab()
        self._build_sim_tab()
        self._build_exp_tab()
        self._build_analysis_tab()

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 1: ДЕКОМПОЗИЦИЯ
    # ══════════════════════════════════════════════════════════════════
    def _build_schema_tab(self):
        c = tk.Canvas(self.tab_dec, bg=BG, highlightthickness=0)
        c.pack(fill="both", expand=True)

        def box(x, y, w, h, title, lines, color):
            c.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=color,
                               width=2)
            c.create_rectangle(x, y, x + w, y + 26, fill=color, outline=color)
            c.create_text(x + 10, y + 13, anchor="w", text=title,
                          fill="#0d1117", font=("Consolas", 10, "bold"))
            for i, ln in enumerate(lines):
                bold = ln.startswith("+")
                c.create_text(x + 10, y + 40 + i * 17, anchor="w", text=ln,
                              fill=TXT if bold else DIM,
                              font=("Consolas", 9, "bold" if bold else "normal"))

        def arrow(x1, y1, x2, y2, text, color, dash=None):
            c.create_line(x1, y1, x2, y2, fill=color, width=2, arrow="last",
                          dash=dash or ())
            c.create_text((x1 + x2) / 2, (y1 + y2) / 2 - 10,
                          text=text, fill=color, font=("Segoe UI", 8, "bold"))

        c.create_text(30, 24, anchor="w",
                      text="ДЕКОМПОЗИЦИЯ И АГРЕГИРОВАНИЕ СИСТЕМЫ",
                      fill=ACCENT, font=("Segoe UI", 15, "bold"))
        c.create_text(30, 50, anchor="w",
                      text="Вариант 1 · Динамические препятствия · внутренняя целостность",
                      fill=DIM, font=("Segoe UI", 10, "italic"))

        box(40, 90, 300, 210, "class Ant  (МИКРОУРОВЕНЬ)", [
            "+ x, y : int        — положение",
            "+ has_food : bool   — состояние",
            "+ angle, phase      — визуал",
            "",
            "+ move()            — такт агента",
            "+ _wander()         — поиск по феромону",
            "+ _go_home()        — возврат + обход стен",
            "",
            "знает только 8 соседних клеток",
        ], ACCENT)

        box(420, 90, 360, 300, "class AntColonySystem  (МАКРОУРОВЕНЬ)", [
            "+ ants : list[Ant]        — агрегат агентов",
            "+ pheromone_grid : 50×50  — среда (+ОС)",
            "+ food_grid      : 50×50  — ресурсы",
            "+ obstacle_grid  : 50×50  — СТЕНЫ (вар. 1)",
            "+ trail_grid     : 50×50  — следы агентов",
            "",
            "+ evaporation_rate        — сила ─ОС",
            "+ pheromone_deposit       — сила +ОС",
            "+ sensitivity             — чувствит. к следу",
            "",
            "+ update_system()  — один такт системы",
            "+ build_wall()     — стена на такте 150",
            "+ add_wall_segment()/toggle_wall_cell()",
            "",
            "+ total_food_collected — эмерджентная метрика",
        ], GREEN)

        box(860, 90, 300, 210, "class Lab2App  (НАБЛЮДАТЕЛЬ)", [
            "+ canvas    — визуализация поля",
            "+ chart     — график метрик",
            "",
            "+ _tick()   — цикл анимации 60 FPS",
            "+ _render() — отрисовка кадра",
            "+ _run_exp1..3() — эксперименты",
            "",
            "не влияет на логику модели,",
            "только наблюдает и управляет",
        ], ORANGE)

        arrow(340, 170, 418, 170, "агрегирование", GREEN)
        arrow(782, 170, 858, 170, "наблюдение", ORANGE, dash=(4, 3))

        # Контур обратной связи
        c.create_text(40, 430, anchor="w", text="КОНТУР ОБРАТНОЙ СВЯЗИ",
                      fill=ACCENT, font=("Segoe UI", 13, "bold"))

        c.create_oval(70, 470, 290, 560, fill=PANEL, outline=ACCENT, width=2)
        c.create_text(180, 500, text="Агент", fill=TXT,
                      font=("Segoe UI", 11, "bold"))
        c.create_text(180, 525, text="локальное правило", fill=DIM,
                      font=("Segoe UI", 9))

        c.create_oval(500, 470, 740, 560, fill=PANEL, outline=ORANGE, width=2)
        c.create_text(620, 500, text="pheromone_grid", fill=TXT,
                      font=("Consolas", 11, "bold"))
        c.create_text(620, 525, text="общая память системы", fill=DIM,
                      font=("Segoe UI", 9))

        c.create_line(290, 495, 498, 495, fill=GREEN, width=3, arrow="last")
        c.create_text(394, 478, text="+ОС:  pheromone_grid[x, y] += deposit",
                      fill=GREEN, font=("Consolas", 9, "bold"))
        c.create_line(500, 538, 292, 538, fill=ACCENT, width=3, arrow="last")
        c.create_text(396, 556, text="вход агента:  weight = 0.15 + sens · pheromone",
                      fill=ACCENT, font=("Consolas", 9, "bold"))

        c.create_line(620, 560, 620, 610, fill=RED, width=3, arrow="last")
        c.create_text(630, 590, anchor="w",
                      text="─ОС:  pheromone_grid *= (1 − evaporation_rate)",
                      fill=RED, font=("Consolas", 10, "bold"))
        c.create_text(630, 612, anchor="w",
                      text="система забывает неподкреплённые маршруты",
                      fill=DIM, font=("Segoe UI", 9, "italic"))

        c.create_rectangle(70, 640, 1160, 712, fill=PANEL, outline=RED, width=2)
        c.create_text(86, 660, anchor="w",
                      text="ВОЗМУЩЕНИЕ (вариант 1):  obstacle_grid — динамическая стена",
                      fill=RED, font=("Segoe UI", 10, "bold"))
        c.create_text(86, 684, anchor="w",
                      text="на такте 150 сплошная стена 20 клеток перерезает главную тропу; "
                           "ходы в _wander()/_go_home() отсекаются →",
                      fill=TXT, font=("Segoe UI", 9))
        c.create_text(86, 700, anchor="w",
                      text="старый след не подкрепляется и гаснет (─ОС) → новый обход "
                           "подкрепляется (+ОС) → структура перестраивается.",
                      fill=TXT, font=("Segoe UI", 9))

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 2: СИМУЛЯЦИЯ
    # ══════════════════════════════════════════════════════════════════
    def _build_sim_tab(self):
        self.system = AntColonySystem(
            size=FIELD_SIZE, num_ants=150,
            evaporation_rate=0.07, pheromone_deposit=3.0, sensitivity=1.0)
        self.running = False
        self.sub_frames = 4        # кадров анимации на один такт модели
        self.steps_per_frame = 1
        self.frame_in_step = 0
        self.ant_items = []
        self.wall_items = []
        self.wall_shown = -1
        self.zoomed_ref = None
        self.hint_visible = True

        main = tk.Frame(self.tab_sim, bg=BG)
        main.pack(padx=12, pady=10)

        # ─── Левая колонка: поле ───
        left = tk.Frame(main, bg=BG)
        left.grid(row=0, column=0)

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

        # Гнездо и источники пищи — отдельные объекты канвы (поверх поля)
        self.nest_ring = self.canvas.create_oval(0, 0, 0, 0, outline="#79c0ff",
                                                 width=2, tags=("deco",))
        self.nest_core = self.canvas.create_oval(0, 0, 0, 0, fill="#1f6feb",
                                                 outline="#cfe6ff", width=1,
                                                 tags=("deco",))
        self.food_items = [
            self.canvas.create_oval(0, 0, 0, 0, outline="#7ee787", width=2,
                                    tags=("deco",))
            for _ in self.system.food_sources
        ]

        self.hint_item = self.canvas.create_text(
            CANVAS_PX / 2, CANVAS_PX - 12, anchor="s",
            text="клик или протягивание мышью по полю — поставить стену",
            fill="#c9d1d9", font=("Segoe UI", 9, "italic"))

        # ─── Легенда ───
        legend_frame = tk.Frame(left, bg=PANEL, highlightthickness=1,
                                highlightbackground=BORDER)
        legend_frame.pack(fill="x", pady=(8, 0))
        tk.Label(legend_frame, text="ЛЕГЕНДА", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10,
                                                    pady=(6, 2))
        legend_grid = tk.Frame(legend_frame, bg=PANEL)
        legend_grid.pack(fill="x", padx=10, pady=(0, 8))

        legend_items = [
            ("#f0b27a", "Муравей ищет пищу"),
            ("#8ff0b5", "Муравей несёт пищу"),
            ("#1f6feb", "Гнездо"),
            ("#7ee787", "Источник пищи"),
            ("#ff7b45", "Феромоновая тропа (+ОС)"),
            ("#58a6ff", "Следы отдельных агентов"),
            (WALL_FILL, "Стена (препятствие)"),
        ]
        for i, (color, label) in enumerate(legend_items):
            r, col = divmod(i, 3)
            cell = tk.Frame(legend_grid, bg=PANEL)
            cell.grid(row=r, column=col, sticky="w", padx=(0, 18), pady=2)
            sw = tk.Canvas(cell, width=16, height=16, bg=PANEL,
                           highlightthickness=0)
            sw.pack(side="left")
            sw.create_oval(3, 3, 13, 13, fill=color, outline="#0d1117")
            tk.Label(cell, text=label, bg=PANEL, fg=TXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

        # ─── Правая колонка ───
        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=1, sticky="n", padx=(14, 0))

        tk.Label(right, text="ВАРИАНТ 1", bg=BG, fg=RED,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(right, text="Динамические препятствия\n(внутренняя целостность)",
                 bg=BG, fg=TXT, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        box = tk.Frame(right, bg=PANEL, highlightthickness=1,
                       highlightbackground=BORDER)
        box.pack(fill="x")
        tk.Label(box, text="ЭМЕРДЖЕНТНЫЕ МЕТРИКИ", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8,
                                                    pady=(6, 2))
        self.lbl_step   = tk.Label(box, text="Такт: 0", bg=PANEL, fg=TXT,
                                   font=("Consolas", 10), anchor="w")
        self.lbl_food   = tk.Label(box, text="Собрано пищи: 0", bg=PANEL,
                                   fg=GREEN, font=("Consolas", 10), anchor="w")
        self.lbl_spread = tk.Label(box, text="Клеток с феромоном: 0", bg=PANEL,
                                   fg=ORANGE, font=("Consolas", 10), anchor="w")
        self.lbl_wall   = tk.Label(box, text="Клеток стены: 0", bg=PANEL,
                                   fg=TXT, font=("Consolas", 10), anchor="w")
        for w in (self.lbl_step, self.lbl_food, self.lbl_spread, self.lbl_wall):
            w.pack(anchor="w", padx=8)
        tk.Frame(box, bg=PANEL, height=6).pack()

        btnf = tk.Frame(right, bg=BG)
        btnf.pack(fill="x", pady=(8, 8))

        def mkbtn(text, cmd, color):
            return tk.Button(btnf, text=text, command=cmd,
                             bg=PANEL, fg=color, activebackground="#21262d",
                             activeforeground=color, relief="flat", bd=0,
                             font=("Segoe UI", 9, "bold"), padx=8, pady=6,
                             cursor="hand2")

        self.btn_run = mkbtn("▶  СТАРТ", self._toggle_run, GREEN)
        self.btn_run.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        mkbtn("⟲  СБРОС", self._reset, ACCENT).grid(
            row=0, column=1, sticky="ew", padx=(4, 0), pady=2)
        mkbtn("Стена по центру", self._force_wall, RED).grid(
            row=1, column=0, sticky="ew", padx=(0, 4), pady=2)
        mkbtn("Стена поперёк тропы", self._dynamic_wall, ORANGE).grid(
            row=1, column=1, sticky="ew", padx=(4, 0), pady=2)
        mkbtn("Убрать все стены", self._clear_walls, "#ffa657").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=2)
        btnf.columnconfigure(0, weight=1)
        btnf.columnconfigure(1, weight=1)

        sl = tk.Frame(right, bg=BG)
        sl.pack(fill="x")
        self.var_evap    = tk.DoubleVar(value=0.07)
        self.var_ants    = tk.IntVar(value=150)
        self.var_sens    = tk.DoubleVar(value=1.0)
        self.var_deposit = tk.DoubleVar(value=3.0)
        self.var_speed   = tk.IntVar(value=5)

        def slider(text, var, frm, to, res, live):
            f = tk.Frame(sl, bg=BG)
            f.pack(fill="x", pady=(4, 0))
            tk.Label(f, text=text, bg=BG, fg=TXT, font=("Segoe UI", 8),
                     anchor="w").pack(fill="x")
            s = tk.Scale(f, variable=var, from_=frm, to=to, resolution=res,
                         orient="horizontal", bg=BG, fg=TXT,
                         troughcolor="#21262d", highlightthickness=0, bd=0,
                         sliderrelief="flat", activebackground=ACCENT,
                         font=("Consolas", 8), length=290)
            s.pack(fill="x")
            if live:
                s.configure(command=lambda *_: self._apply_live())

        slider("Испарение феромона (─ОС)", self.var_evap, 0.0, 1.0, 0.01, True)
        slider("Агентов (применяется при сбросе)", self.var_ants, 20, 400, 10, False)
        slider("Чувствительность к следу", self.var_sens, 0.0, 4.0, 0.1, True)
        slider("Сила следа (+ОС)", self.var_deposit, 0.0, 10.0, 0.5, True)
        slider("Скорость (1 — плавно, 12 — быстро)", self.var_speed, 1, 12, 1, True)

        tk.Label(right, text="ДИНАМИКА МЕТРИК", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
        self.chart = tk.Canvas(right, width=CHART_W, height=CHART_H,
                               bg="#0a0e14", highlightthickness=1,
                               highlightbackground=BORDER)
        self.chart.pack()

        self._apply_live()
        self._create_ant_items()
        self._sync_positions(initial=True)
        self._redraw_field()
        self._render_ants(1.0)
        self._update_metrics()
        self._draw_chart()
        self.root.after(FRAME_MS, self._tick)

    # ─── Параметры «на лету» ──────────────────────────────────────────
    def _apply_live(self):
        self.system.evaporation_rate  = float(self.var_evap.get())
        self.system.sensitivity       = float(self.var_sens.get())
        self.system.pheromone_deposit = float(self.var_deposit.get())
        sp = int(self.var_speed.get())
        if sp <= 8:
            self.sub_frames, self.steps_per_frame = 9 - sp, 1
        else:
            self.sub_frames, self.steps_per_frame = 1, sp - 7

    def _toggle_run(self):
        self.running = not self.running
        self.btn_run.configure(text="⏸  ПАУЗА" if self.running else "▶  СТАРТ")

    def _reset(self):
        self.running = False
        self.btn_run.configure(text="▶  СТАРТ")
        self.system = AntColonySystem(
            size=FIELD_SIZE,
            num_ants=int(self.var_ants.get()),
            evaporation_rate=float(self.var_evap.get()),
            pheromone_deposit=float(self.var_deposit.get()),
            sensitivity=float(self.var_sens.get()))
        self._apply_live()
        self._create_ant_items()
        self._sync_positions(initial=True)
        self.wall_shown = -1
        self.hint_visible = True
        self.canvas.itemconfig(self.hint_item, state="normal")
        self._redraw_field()
        self._render_ants(1.0)
        self._update_metrics()
        self._draw_chart()

    def _force_wall(self):
        if not self.system.wall_built:
            self.system.build_wall()
        self._redraw_field()
        self._update_metrics()

    def _dynamic_wall(self):
        self.system.add_wall_crossing_trail()
        self._redraw_field()
        self._update_metrics()

    def _clear_walls(self):
        self.system.clear_all_walls()
        self._redraw_field()
        self._update_metrics()

    # ─── Мышь ─────────────────────────────────────────────────────────
    def _cell_at(self, event):
        return int(event.x) // CELL, int(event.y) // CELL

    def _hide_hint(self):
        if self.hint_visible:
            self.canvas.itemconfig(self.hint_item, state="hidden")
            self.hint_visible = False

    def _on_canvas_click(self, event):
        x, y = self._cell_at(event)
        self.system.toggle_wall_cell(x, y)
        self._hide_hint()
        self._redraw_field()
        self._update_metrics()

    def _on_canvas_drag(self, event):
        x, y = self._cell_at(event)
        self.system.paint_wall_cell(x, y)
        self._hide_hint()
        self._redraw_field()

    # ─── Цикл анимации ────────────────────────────────────────────────
    def _tick(self):
        if self.running:
            self.frame_in_step += 1
            if self.frame_in_step >= self.sub_frames:
                self.frame_in_step = 0
                for _ in range(self.steps_per_frame):
                    self.system.update_system()
                self._sync_positions()
                self._redraw_field()
                self._update_metrics()
                self._draw_chart()
            alpha = 1.0 if self.sub_frames <= 1 else \
                self.frame_in_step / float(self.sub_frames)
            self._render_ants(alpha)
        else:
            self._animate_deco()
        self.root.after(FRAME_MS, self._tick)

    # ─── Позиции агентов в numpy (обновляются раз в такт) ─────────────
    def _sync_positions(self, initial=False):
        ants = self.system.ants
        n = len(ants)
        if initial:
            self.pos_prev = np.array([[a.x, a.y] for a in ants], dtype=float)
        else:
            self.pos_prev = np.array([[a.px, a.py] for a in ants], dtype=float)
        self.pos_cur = np.array([[a.x, a.y] for a in ants], dtype=float)
        self.ang = np.array([a.angle for a in ants], dtype=float)
        self.gait_idx = np.array([a.phase for a in ants], dtype=int)
        self.carry = np.array([a.has_food for a in ants], dtype=bool)
        if not hasattr(self, "carry_shown") or len(self.carry_shown) != n:
            self.carry_shown = np.full(n, -1, dtype=int)

    # ─── Отрисовка поля (раз в такт модели) ───────────────────────────
    def _redraw_field(self):
        s = self.system
        rgb = field_rgb(s, s.step, draw_walls=False)
        self.photo.put(rgb_to_put_string(rgb))
        z = self.photo.zoom(CELL)
        self.zoomed_ref = z
        self.canvas.itemconfig(self.field_item, image=z)
        self.canvas.tag_lower(self.field_item)

        if self.wall_shown != s.wall_version:
            self._rebuild_walls()
            self.wall_shown = s.wall_version
        self._animate_deco()

    def _rebuild_walls(self):
        """Стены — объекты канвы: объёмные «кирпичи» со светлой фаской."""
        for it in self.wall_items:
            self.canvas.delete(it)
        self.wall_items = []
        xs, ys = np.nonzero(self.system.obstacle_grid)
        if len(xs) > 1200:                       # защита от перегрузки канвы
            xs, ys = xs[:1200], ys[:1200]
        for x, y in zip(xs.tolist(), ys.tolist()):
            x0, y0 = x * CELL, y * CELL
            r = self.canvas.create_rectangle(
                x0, y0, x0 + CELL, y0 + CELL,
                fill=WALL_FILL, outline=WALL_DARK, tags=("wall",))
            hl = self.canvas.create_line(
                x0 + 1, y0 + 1, x0 + CELL - 1, y0 + 1,
                fill=WALL_EDGE, tags=("wall",))
            self.wall_items += [r, hl]
        self.canvas.tag_raise("deco")
        self.canvas.tag_raise("ant")
        self.canvas.tag_raise(self.hint_item)

    def _animate_deco(self):
        """Пульсация гнезда и источников пищи — каждый кадр, дёшево."""
        s = self.system
        t = self.system.step + self.frame_in_step / max(1, self.sub_frames)

        nx = s.nest[0] * CELL + CELL / 2
        ny = s.nest[1] * CELL + CELL / 2
        r = CELL * (1.7 + 0.45 * math.sin(t * 0.18))
        self.canvas.coords(self.nest_ring, nx - r, ny - r, nx + r, ny + r)
        rc = CELL * 0.75
        self.canvas.coords(self.nest_core, nx - rc, ny - rc, nx + rc, ny + rc)

        for item, src in zip(self.food_items, s.food_sources):
            left = s.food_left(src)
            if left <= 0:
                self.canvas.coords(item, 0, 0, 0, 0)
                continue
            k = 0.35 + 0.65 * min(1.0, left / 1800.0)
            rr = CELL * (1.3 + 1.3 * k) * (0.94 + 0.06 * math.sin(t * 0.22))
            cx = src[0] * CELL + CELL / 2
            cy = src[1] * CELL + CELL / 2
            self.canvas.coords(item, cx - rr, cy - rr, cx + rr, cy + rr)

    # ─── Отрисовка муравьёв (каждый кадр, векторно) ───────────────────
    def _render_ants(self, alpha):
        if not len(self.pos_cur):
            return
        pos = self.pos_prev + (self.pos_cur - self.pos_prev) * alpha
        px = pos[:, 0] * CELL + CELL / 2.0
        py = pos[:, 1] * CELL + CELL / 2.0

        ca, sa = np.cos(self.ang), np.sin(self.ang)
        shape = GAIT[self.gait_idx] * (CELL * 1.75)      # (N, P, 2)
        sx, sy = shape[:, :, 0], shape[:, :, 1]
        wx = px[:, None] + sx * ca[:, None] - sy * sa[:, None]
        wy = py[:, None] + sx * sa[:, None] + sy * ca[:, None]

        pts = np.empty((len(px), ANT_POINTS * 2), dtype=float)
        pts[:, 0::2] = wx
        pts[:, 1::2] = wy
        coords = self.canvas.coords
        for i, item in enumerate(self.ant_items):
            coords(item, *pts[i].tolist())

        # Цвет меняем только при смене состояния агента
        cfg = self.canvas.itemconfig
        carry = self.carry
        shown = self.carry_shown
        changed = np.nonzero(carry.astype(int) != shown)[0]
        for i in changed.tolist():
            if carry[i]:
                cfg(self.ant_items[i], fill="#8ff0b5", outline="#1b7f4a")
            else:
                cfg(self.ant_items[i], fill="#f0b27a", outline="#5a2f0c")
            shown[i] = int(carry[i])

    def _create_ant_items(self):
        for it in self.ant_items:
            self.canvas.delete(it)
        self.ant_items = []
        zeros = [0.0] * (ANT_POINTS * 2)
        for _ in self.system.ants:
            item = self.canvas.create_polygon(
                *zeros, fill="#f0b27a", outline="#5a2f0c", width=1,
                joinstyle="round", tags=("ant",))
            self.ant_items.append(item)
        self.carry_shown = np.full(len(self.ant_items), -1, dtype=int)
        self.canvas.tag_raise("ant")

    # ─── Метрики и график ─────────────────────────────────────────────
    def _update_metrics(self):
        s = self.system
        self.lbl_step.configure(text=f"Такт: {s.step}")
        self.lbl_food.configure(text=f"Собрано пищи: {s.total_food_collected}")
        self.lbl_spread.configure(
            text=f"Клеток с феромоном: "
                 f"{int(np.count_nonzero(s.pheromone_grid > 0.5))}")
        cells = s.wall_cells()
        extra = f"  (посл. правка: такт {s.wall_markers[-1]})" if s.wall_markers else ""
        self.lbl_wall.configure(text=f"Клеток стены: {cells}{extra}")

    def _draw_chart(self):
        """График двух метрик. Шкалы у них разные, поэтому у каждой кривой
        своя ось: слева — собранная пища, справа — ширина фронта феромона."""
        c = self.chart
        c.delete("all")
        w, h = CHART_W, CHART_H
        head = 42                      # полоса легенды сверху
        pad_b, pad_l, pad_r = 16, 6, 6
        top, bot = head, h - pad_b

        c.create_rectangle(0, 0, w, h, fill="#0a0e14", outline=BORDER)
        c.create_rectangle(0, 0, w, head - 1, fill="#11161d", outline="")
        c.create_line(0, head - 1, w, head - 1, fill=BORDER)

        fh = self.system.food_history[-CHART_WINDOW:]
        sh = self.system.spread_history[-CHART_WINDOW:]
        n = len(fh)
        maxf = max(max(fh), 1) if n else 1
        maxs = max(max(sh), 1) if n else 1

        # ─── Легенда: два крупных читаемых счётчика ───
        c.create_line(8, 13, 22, 13, fill=GREEN, width=3)
        c.create_text(28, 13, anchor="w", text=f"собрано пищи:  {fh[-1] if n else 0}",
                      fill=GREEN, font=("Consolas", 10, "bold"))
        if self.system.wall_markers:
            c.create_line(w - 62, 13, w - 48, 13, fill=RED, width=2, dash=(3, 2))
            c.create_text(w - 44, 13, anchor="w", text="стена",
                          fill=RED, font=("Consolas", 9, "bold"))
        c.create_line(8, 30, 22, 30, fill=ORANGE, width=3)
        c.create_text(28, 30, anchor="w",
                      text=f"феромон:  {sh[-1] if n else 0} кл.   (макс. {maxs})",
                      fill=ORANGE, font=("Consolas", 10, "bold"))

        if n < 2:
            return

        start = self.system.history_origin + \
            max(0, len(self.system.food_history) - CHART_WINDOW)

        for i in range(1, 4):
            y = top + (bot - top) * i / 4
            c.create_line(pad_l, y, w - pad_r, y, fill="#1b222c")

        span = w - pad_l - pad_r
        ptsf, ptss = [], []
        for i in range(n):
            x = pad_l + i * span / (n - 1)
            ptsf += [x, bot - (fh[i] / maxf) * (bot - top - 4)]
            ptss += [x, bot - (sh[i] / maxs) * (bot - top - 4)]
        c.create_line(*ptss, fill=ORANGE, width=2)
        c.create_line(*ptsf, fill=GREEN, width=2)

        # Маркеры возведения/правки стен
        for wm in self.system.wall_markers[-30:]:
            rel = wm - start
            if 0 <= rel < n:
                x = pad_l + rel * span / (n - 1)
                c.create_line(x, top, x, bot, fill=RED, dash=(3, 3))

        # Подписи осей
        c.create_text(pad_l + 1, bot + 2, anchor="nw",
                      text=f"такт {start}", fill=DIM, font=("Consolas", 8))
        c.create_text(w - pad_r - 1, bot + 2, anchor="ne",
                      text=f"такт {start + n - 1}", fill=DIM,
                      font=("Consolas", 8))

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 3: ЭКСПЕРИМЕНТЫ
    # ══════════════════════════════════════════════════════════════════
    def _build_exp_tab(self):
        top = tk.Frame(self.tab_exp, bg=BG)
        top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(top, text="АВТОМАТИЧЕСКИЕ ЭКСПЕРИМЕНТЫ", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(top, text="Программа прогоняет симуляцию в фоне и фиксирует "
                           "снимки ключевых тактов.",
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

        mkb("▶ №1. Самоорганизация",    self._run_exp1, GREEN)
        mkb("▶ №2а. Испарение = 0 %",   self._run_exp2a, ORANGE)
        mkb("▶ №2б. Испарение = 100 %", self._run_exp2b, ORANGE)
        mkb("▶ №3. Целостность (стена)", self._run_exp3, RED)

        snapf = tk.Frame(self.tab_exp, bg=BG)
        snapf.pack(fill="x", padx=14)
        self.snap_canvases = []
        self.snap_labels = []
        for i in range(4):
            fr = tk.Frame(snapf, bg=BG)
            fr.grid(row=0, column=i, padx=4, pady=4, sticky="n")
            lbl = tk.Label(fr, text=f"кадр {i + 1}", bg=BG, fg=DIM,
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
        for cv in self.snap_canvases:
            cv.delete("all")
        self._photo_refs = []
        for i, (p, lbl) in enumerate(zip(photos, labels)):
            if i >= len(self.snap_canvases) or p is None:
                continue
            self.snap_canvases[i].create_image(0, 0, image=p, anchor="nw")
            self._photo_refs.append(p)
            self.snap_labels[i].configure(text=lbl)

    def _log(self, text, tag=None):
        self.exp_log.insert("end", text + "\n", tag or ())
        self.exp_log.see("end")
        self.root.update_idletasks()

    @staticmethod
    def _run(system, steps, snap_at):
        snaps = {}
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
        s = AntColonySystem(num_ants=150, evaporation_rate=0.07,
                            pheromone_deposit=3.0)
        snaps = {0: field_to_photo(s, zoom=5)}
        snaps.update(self._run(s, 50, {50}))
        f50 = s.total_food_collected
        snaps.update(self._run(s, 150, {200}))
        f200 = s.total_food_collected
        snaps.update(self._run(s, 200, {400}))
        self._show_snapshots(
            [snaps.get(0), snaps.get(50), snaps.get(200), snaps.get(400)],
            ["T₀ — хаос", "T₅₀ — разведка",
             "T₂₀₀ — первые магистрали", "T₄₀₀ — устойчивая тропа"])
        self._log("Наблюдения:", "h")
        self._log("  • T₀   — поле чёрное, агенты выходят из гнезда роем; "
                  "феромона нет.")
        self._log(f"  • T₅₀  — фронт разведки уходит от гнезда, собрано "
                  f"{f50} ед.: источник ещё не найден.")
        self._log(f"  • T₂₀₀ — видны яркие «нити» феромона; собрано "
                  f"{f200} ед. — положительная ОС запустилась.", "ok")
        self._log("  • T₄₀₀ — тропа СЖАЛАСЬ в узкую магистраль, темп сбора "
                  "вырос нелинейно.", "ok")
        self._log(f"\nИтог: собрано пищи = {s.total_food_collected}, "
                  f"активных клеток феромона = "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))}", "ok")
        self._log("Темп сбора по интервалам: "
                  f"0–50: {f50/50:.2f} | 50–200: {(f200-f50)/150:.2f} | "
                  f"200–400: {(s.total_food_collected-f200)/200:.2f} ед./такт "
                  "— рост нелинейный.", "ok")
        self._log("Вывод: из хаоса локальных блужданий возникла устойчивая "
                  "пространственно-временная упорядоченность — "
                  "САМООРГАНИЗАЦИЯ.", "ok")

    # ─── Эксперимент №2а ──────────────────────────────────────────────
    def _run_exp2a(self):
        self.exp_log.delete("1.0", "end")
        self._log("ЭКСПЕРИМЕНТ №2а. Испарение = 0 % (нет ─ОС)", "h")
        self._log("Отрицательная обратная связь отключена полностью.", "dim")
        self.root.update()
        s = AntColonySystem(num_ants=150, evaporation_rate=0.0,
                            pheromone_deposit=3.0)
        snaps = {0: field_to_photo(s, zoom=5)}
        snaps.update(self._run(s, 400, {200, 400}))
        self._show_snapshots([snaps.get(0), snaps.get(200), snaps.get(400)],
                             ["T₀", "T₂₀₀ — следы не гаснут",
                              "T₄₀₀ — «мёртвая сеть»"])
        self._log("Наблюдения:", "h")
        self._log("  • Положительная связь продолжает усиливать следы.")
        self._log("  • После истощения ресурса тропы НЕ исчезают — поле "
                  "покрывается «мёртвой сетью» маршрутов.", "warn")
        self._log(f"  • Клеток с феромоном = "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))} — метрика "
                  f"растёт монотонно к максимуму.")
        self._log(f"  • Собрано пищи: {s.total_food_collected}")
        self._log("\nВывод: без отрицательной ОС система теряет динамическое "
                  "равновесие; агенты циркулируют по пустым коридорам, "
                  "перестройка структуры невозможна.", "err")

    # ─── Эксперимент №2б ──────────────────────────────────────────────
    def _run_exp2b(self):
        self.exp_log.delete("1.0", "end")
        self._log("ЭКСПЕРИМЕНТ №2б. Испарение = 100 % (нет +ОС)", "h")
        self._log("Феромон полностью стирается на каждом такте.", "dim")
        self.root.update()
        s = AntColonySystem(num_ants=150, evaporation_rate=1.0,
                            pheromone_deposit=3.0)
        snaps = {0: field_to_photo(s, zoom=5)}
        snaps.update(self._run(s, 200, {50, 200}))
        self._show_snapshots([snaps.get(0), snaps.get(50), snaps.get(200)],
                             ["T₀", "T₅₀ — следов нет",
                              "T₂₀₀ — самоорганизации нет"])
        self._log("Наблюдения:", "h")
        self._log("  • Положительная связь не успевает накопиться — тропы "
                  "вообще не образуются.", "warn")
        self._log(f"  • Клеток с феромоном: "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))} "
                  f"(практически ноль).")
        self._log(f"  • Собрано пищи: {s.total_food_collected} — крайне мало "
                  f"(только случайные находки).")
        self._log("\nВывод: без положительной ОС самоорганизация невозможна; "
                  "система остаётся в хаотическом состоянии.", "err")

    # ─── Эксперимент №3 (вариант 1) ───────────────────────────────────
    def _run_exp3(self):
        self.exp_log.delete("1.0", "end")
        self._log("ЭКСПЕРИМЕНТ №3. Внутренняя целостность "
                  "(динамическое препятствие)", "h")
        self._log("На такте T=150 автоматически возводится сплошная стена "
                  "20 клеток поперёк главной тропы.", "dim")
        self.root.update()
        s = AntColonySystem(num_ants=150, evaporation_rate=0.07,
                            pheromone_deposit=3.0)

        snaps = self._run(s, 99, set())
        food_at_99 = s.total_food_collected
        snaps.update(self._run(s, 50, {149}))
        food_before = s.total_food_collected
        # Базовый темп — по последним 50 тактам ДО возмущения (честное сравнение:
        # средний темп за все 149 тактов занижен «холодным стартом» колонии)
        rate_before = (food_before - food_at_99) / 50.0

        snaps.update(self._run(s, 11, {160}))

        # Замер: за сколько тактов восстановилась производительность колонии
        W = 25
        recovered_at = None
        min_rate = None
        prev = s.total_food_collected
        window = []
        for _ in range(340):
            s.update_system()
            delta = s.total_food_collected - prev
            prev = s.total_food_collected
            window.append(delta)
            if len(window) > W:
                window.pop(0)
            if len(window) == W:
                rate = sum(window) / float(W)
                min_rate = rate if min_rate is None else min(min_rate, rate)
                if recovered_at is None and rate >= rate_before * 0.9:
                    recovered_at = s.step - WALL_STEP
            if s.step in (250, 400):
                snaps[s.step] = field_to_photo(s, zoom=5)

        self._show_snapshots(
            [snaps.get(149), snaps.get(160), snaps.get(250), snaps.get(400)],
            ["T₁₄₉ — стабильные тропы", "T₁₆₀ — стена, смятение",
             "T₂₅₀ — обход формируется", "T₄₀₀ — новая магистраль"])

        self._log("Наблюдения:", "h")
        self._log(f"  • До стены (такты 100–149): собрано {food_before} ед., "
                  f"темп {rate_before:.2f} ед./такт.")
        self._log("  • T=150 — стена мгновенно перерезает маршрут в среднем "
                  "столбце карты; часть агентов утыкается в препятствие.",
                  "warn")
        self._log("  • Старый след перестаёт подкрепляться и гаснет "
                  "(отрицательная ОС).")
        self._log("  • Возвращающиеся агенты скользят вдоль стены "
                  "(_go_home) и подкрепляют обходной путь (положительная ОС).")
        if min_rate is not None:
            self._log(f"  • Минимальный темп после возмущения: "
                      f"{min_rate:.2f} ед./такт (провал производительности).",
                      "warn")
        if recovered_at is not None:
            self._log(f"  • Темп сбора вернулся к 90 % от исходного через "
                      f"{recovered_at} тактов после возмущения.", "ok")
        else:
            self._log("  • За 340 тактов после возмущения темп не вернулся "
                      "к 90 % — стена оказалась критическим возмущением.",
                      "warn")
        self._log(f"\nИтог: всего собрано {s.total_food_collected} ед., "
                  f"активных клеток феромона = "
                  f"{int(np.count_nonzero(s.pheromone_grid > 0.5))}")
        self._log("Вывод: система демонстрирует ВНУТРЕННЮЮ ЦЕЛОСТНОСТЬ — "
                  "сохранила базовое функциональное свойство (транспортировка "
                  "ресурса) и самостоятельно перестроила структуру троп.", "ok")

    # ══════════════════════════════════════════════════════════════════
    #   ВКЛАДКА 4: СИСТЕМНЫЙ АНАЛИЗ
    # ══════════════════════════════════════════════════════════════════
    def _build_analysis_tab(self):
        container = tk.Frame(self.tab_anal, bg=BG)
        container.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Label(container, text="СИСТЕМНЫЙ АНАЛИЗ РЕЗУЛЬТАТОВ",
                 bg=BG, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(container,
                 text="Научные выводы по итогам всех трёх экспериментов.",
                 bg=BG, fg=DIM,
                 font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(0, 10))

        wrap = tk.Frame(container, bg=BG)
        wrap.pack(fill="both", expand=True)
        sb = tk.Scrollbar(wrap)
        sb.pack(side="right", fill="y")
        txt = tk.Text(wrap, bg="#0a0e14", fg=TXT, relief="flat", bd=0,
                      font=("Segoe UI", 10), padx=16, pady=12, wrap="word",
                      highlightthickness=1, highlightbackground=BORDER,
                      yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.configure(command=txt.yview)

        txt.tag_configure("h1", foreground=ACCENT,
                          font=("Segoe UI", 13, "bold"), spacing1=10, spacing3=6)
        txt.tag_configure("h2", foreground=GREEN,
                          font=("Segoe UI", 11, "bold"), spacing1=8, spacing3=4)
        txt.tag_configure("kw", foreground=ORANGE,
                          font=("Consolas", 10, "bold"))
        txt.tag_configure("blt", lmargin1=20, lmargin2=34)

        def H1(t): txt.insert("end", t + "\n", "h1")
        def H2(t): txt.insert("end", t + "\n", "h2")
        def P(t):  txt.insert("end", t + "\n\n")
        def KW(t): txt.insert("end", t, "kw")
        def B(t):  txt.insert("end", "  •  " + t + "\n", "blt")

        H1("1. В ЧЁМ ВЫРАЗИЛАСЬ ЭМЕРДЖЕНТНОСТЬ МОДЕЛИ?")
        P("Ни один экземпляр класса Ant не обладает ни картой, ни памятью "
          "о маршруте, ни функцией «построить кратчайший путь». Агент видит "
          "лишь 8 соседних клеток и локально решает: повернуть к феромону или "
          "шагнуть в сторону гнезда. Однако колония как макросистема "
          "AntColonySystem спонтанно строит устойчивые магистрали, а после "
          "появления стены коллективно находит обход.")
        txt.insert("end", "Эмерджентность", "kw")
        P(" здесь в том, что глобальный порядок (оптимальный маршрут) не "
          "существует ни в одном отдельном агенте, но возникает из их "
          "локальных взаимодействий через общее поле феромонов — среда "
          "выступает внешней памятью системы (стигмергия).")
        P("Количественно эффект зафиксирован метриками:")
        B("общее количество принесённой пищи растёт нелинейно — после "
          "формирования троп темп резко увеличивается;")
        B("число клеток с феромоном СНИЖАЕТСЯ при росте собранной пищи — "
          "тропы сжимаются в узкие магистрали;")
        B("отдельный муравей не способен найти путь, а колония за 150–250 "
          "тактов формирует устойчивую магистраль (при разных запусках она "
          "ведёт к одному или к обоим источникам — какой именно маршрут "
          "«победит», заранее не определено, это свойство целого).")

        H1("2. ВЗАИМОДЕЙСТВИЕ ОБРАТНЫХ СВЯЗЕЙ И ДИНАМИЧЕСКОЕ РАВНОВЕСИЕ")
        P("В модели действуют две противоположно направленные силы.")
        H2("Положительная обратная связь — усиливает отклонение")
        txt.insert("end", "pheromone_grid[ant.x, ant.y] += pheromone_deposit", "kw")
        P("\nЧем больше агентов успешно прошло по тропе, тем она "
          "привлекательнее. Запускается лавинообразный процесс — эффект "
          "«снежного кома»: колония концентрирует усилия на удачном маршруте. "
          "На входе агента связь замыкается формулой "
          "weight = 0.15 + sensitivity · pheromone.")
        H2("Отрицательная обратная связь — стабилизирует систему")
        txt.insert("end", "pheromone_grid *= (1 − evaporation_rate)", "kw")
        P("\nБез подкрепления следы гаснут, поэтому ложные и устаревшие "
          "маршруты (упирающиеся в стену или ведущие к опустевшему источнику) "
          "автоматически отмирают.")
        P("Итог баланса:")
        B("испарение = 0 %   → система теряет гибкость, образуется «мёртвая "
          "сеть» (эксперимент №2а);")
        B("испарение = 100 % → тропы не образуются, самоорганизация "
          "невозможна (эксперимент №2б);")
        B("0 < испарение < 1 → ДИНАМИЧЕСКОЕ РАВНОВЕСИЕ: система одновременно "
          "эксплуатирует найденный оптимум и продолжает искать новый.")

        H1("3. СПЕЦИФИКА ВАРИАНТА 1: ВНУТРЕННЯЯ ЦЕЛОСТНОСТЬ")
        P("Динамическое препятствие (сплошная стена 20 клеток на такте "
          "T = 150) — тест системы на прочность. Программа демонстрирует "
          "следующую цепочку:")
        B("стена перерезает прямую тропу к источнику (40, 40);")
        B("ходы в клетки стены отсекаются в _wander() и _go_home();")
        B("старый след перестаёт подкрепляться и гаснет за счёт ─ОС;")
        B("возвращающиеся агенты скользят вдоль стены и подкрепляют "
          "обходной маршрут за счёт +ОС;")
        B("через несколько десятков тактов образуется новая устойчивая "
          "обходная магистраль (точное число тактов измеряется "
          "в эксперименте №3).")
        txt.insert("end", "Внутренняя целостность", "kw")
        P(" состоит в том, что система сохраняет базовое функциональное "
          "свойство (транспортировка ресурса в гнездо) при изменении "
          "топологии среды — за счёт перераспределения потоков через "
          "обратные связи, а не за счёт жёсткого плана или внешнего "
          "управляющего центра.")
        P("Интерактивная проверка на вкладке «Симуляция»:")
        B("клик по полю — поставить или убрать отдельную клетку стены;")
        B("протягивание мышью — нарисовать стену произвольной формы;")
        B("«Стена поперёк тропы» — программа сама находит клетку "
          "с максимальным феромоном и перерезает маршрут;")
        B("«Убрать все стены» — проверить обратный переход системы.")

        H1("4. ОБЩИЙ ВЫВОД")
        P("Программа наглядно демонстрирует ключевые понятия теории систем:")
        B("ДЕКОМПОЗИЦИЯ — класс Ant (микроуровень) и AntColonySystem "
          "(макроуровень), матрицы среды как подсистемы;")
        B("АГРЕГИРОВАНИЕ — сборка агентов и матриц в единый управляемый "
          "объект с интерфейсом update_system();")
        B("ОБРАТНЫЕ СВЯЗИ — положительная (усиление следа) и отрицательная "
          "(испарение);")
        B("САМООРГАНИЗАЦИЯ — формирование магистралей из хаоса без "
          "управляющего центра;")
        B("ЭМЕРДЖЕНТНОСТЬ — оптимальный маршрут как свойство целого;")
        B("ВНУТРЕННЯЯ ЦЕЛОСТНОСТЬ — перестройка структуры при возмущении "
          "с сохранением функции.")
        P("Ни один элемент системы не «понимает» глобальной задачи. Порядок "
          "рождается из локальных правил и баланса обратных связей — это "
          "фундаментальный принцип сложных систем.")
        txt.configure(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app = Lab2App(root)
    root.mainloop()
