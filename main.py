# -*- coding: utf-8 -*-
import math
import tkinter as tk
from tkinter import ttk, scrolledtext


class BlackBoxBase:
    NAME = "Система"
    DESCRIPTION = ""
    INPUT_SPECS = []
    OUTPUT_LABELS = []

    def validate(self, d):
        return None

    def compute(self, d):
        return {}

    def emergency(self, message):
        return {lbl: f"АВАРИЙНЫЙ РЕЖИМ: {message}" for lbl in self.OUTPUT_LABELS}

    def run(self, data):
        err = self.validate(data)
        if err:
            return self.emergency(err)
        return self.compute(data)

    def input_label(self, key):
        for k, label, *_ in self.INPUT_SPECS:
            if k == key:
                return label
        return key


class StudentBlackBox(BlackBoxBase):
    NAME = "Образовательный процесс (точка зрения СТУДЕНТА)"
    DESCRIPTION = ("Система глазами студента: цель — успешно завершить обучение "
                   "при ограниченных личных ресурсах.")
    INPUT_SPECS = [
        ("attendance",      "Посещаемость, % [Инф]",            "70",    float, "0..100"),
        ("study_hours",     "Время подготовки, ч/нед [Энерг]",  "10",    float, "0..168"),
        ("prev_gpa",        "Средний балл прошлой сессии [Инф]","3.5",   float, "0..5"),
        ("missed_deadlines","Пропущено дедлайнов [Инф]",        "1",     int,   ">=0"),
        ("motivation",      "Мотивация [Инф]",                  "СРЕДНИЙ", str, "ВЫСОКИЙ/СРЕДНИЙ/НИЗКИЙ"),
    ]
    OUTPUT_LABELS = [
        "Выход 1 (Инф):   Прогноз итоговой оценки",
        "Выход 2 (Инф):   Вероятность отчисления",
        "Выход 3 (Энерг): Доп. время на подготовку",
        "Выход 4 (Инф):   Статус студента",
        "Выход 5 (Инф):   Рекомендация",
    ]

    def validate(self, d):
        if not (0 <= d["attendance"] <= 100):
            return "Посещаемость должна быть 0..100%"
        if not (0 <= d["study_hours"] <= 168):
            return "Время подготовки 0..168 ч/нед"
        if not (0 <= d["prev_gpa"] <= 5):
            return "Средний балл должен быть 0..5"
        if d["missed_deadlines"] < 0:
            return "Число пропущенных дедлайнов не может быть < 0"
        if d["motivation"] not in ("ВЫСОКИЙ", "СРЕДНИЙ", "НИЗКИЙ"):
            return "Мотивация: ВЫСОКИЙ / СРЕДНИЙ / НИЗКИЙ"
        return None

    def compute(self, d):
        att = d["attendance"] / 100.0
        sh = min(d["study_hours"] / 25.0, 1.0)
        gpa = d["prev_gpa"] / 5.0
        dl = max(0.0, 1.0 - d["missed_deadlines"] / 5.0)
        base = 0.25 * att + 0.30 * sh + 0.30 * gpa + 0.15 * dl

        mf = {"ВЫСОКИЙ": 1.15, "СРЕДНИЙ": 1.00, "НИЗКИЙ": 0.80}[d["motivation"]]
        score = base * mf

        predicted = round(min(5.0, 2.0 + score * 3.0), 2)
        expel = max(0.0, min(100.0, (1.0 - score) * 80 + d["missed_deadlines"] * 3))
        extra = round(max(0.0, (0.85 - score) * 30), 1)

        if score >= 0.85:
            status, rec = "Отличник (стабильно)", "Поддерживать режим, можно участвовать в олимпиадах"
        elif score >= 0.65:
            status, rec = "Успевающий", "Увеличить время на практику"
        elif score >= 0.45:
            status, rec = "Требуется внимание", "Срочно закрыть дедлайны и поднять посещаемость"
        else:
            status, rec = "Критическая зона", "Риск отчисления. Обратиться к куратору"

        return {
            self.OUTPUT_LABELS[0]: f"{predicted} балла",
            self.OUTPUT_LABELS[1]: f"{expel:.1f} %",
            self.OUTPUT_LABELS[2]: f"{extra} ч/нед",
            self.OUTPUT_LABELS[3]: status,
            self.OUTPUT_LABELS[4]: rec,
        }


class TeacherBlackBox(BlackBoxBase):
    NAME = "Образовательный процесс (точка зрения ПРЕПОДАВАТЕЛЯ)"
    DESCRIPTION = ("Система глазами преподавателя: цель — обеспечить усвоение "
                   "материала группой при заданных ресурсах.")
    INPUT_SPECS = [
        ("group_size",      "Размер группы, чел. [Инф]",            "25",   int,   "1..200"),
        ("avg_performance", "Средняя успеваемость, % [Инф]",        "70",   float, "0..100"),
        ("workload_hours",  "Учебная нагрузка, ч/нед [Энерг]",      "20",   float, "0..60"),
        ("has_materials",   "Есть методички? [Матер]",              "ДА",   str,   "ДА/НЕТ"),
        ("tech_level",      "Тех. оснащение [Матер]",               "СРЕДНИЙ", str, "ВЫСОКИЙ/СРЕДНИЙ/НИЗКИЙ"),
    ]
    OUTPUT_LABELS = [
        "Выход 1 (Инф):   Качество усвоения материала",
        "Выход 2 (Инф):   Нужны доп. занятия",
        "Выход 3 (Энерг): Затраты времени на проверку",
        "Выход 4 (Инф):   Рекомендуемый формат занятий",
        "Выход 5 (Инф):   Удовлетворённость преподавателя",
    ]

    def validate(self, d):
        if not (1 <= d["group_size"] <= 200):
            return "Размер группы 1..200"
        if not (0 <= d["avg_performance"] <= 100):
            return "Успеваемость 0..100%"
        if not (0 <= d["workload_hours"] <= 60):
            return "Нагрузка 0..60 ч/нед"
        if d["has_materials"] not in ("ДА", "НЕТ"):
            return "Методички: ДА / НЕТ"
        if d["tech_level"] not in ("ВЫСОКИЙ", "СРЕДНИЙ", "НИЗКИЙ"):
            return "Тех. оснащение: ВЫСОКИЙ / СРЕДНИЙ / НИЗКИЙ"
        return None

    def compute(self, d):
        tech_bonus = {"ВЫСОКИЙ": 15, "СРЕДНИЙ": 7, "НИЗКИЙ": 0}[d["tech_level"]]
        mat_bonus = 20 if d["has_materials"] == "ДА" else 0
        quality = min(100.0, d["avg_performance"] * 0.6 + mat_bonus + tech_bonus)

        if quality >= 80:
            q_label = f"Высокое ({quality:.0f}%)"
        elif quality >= 60:
            q_label = f"Среднее ({quality:.0f}%)"
        else:
            q_label = f"Низкое ({quality:.0f}%)"

        need_extra = "ДА" if quality < 60 else "НЕТ"

        check_time = d["group_size"] * 0.3
        if d["has_materials"] == "НЕТ":
            check_time *= 1.3
        check_time = round(check_time, 1)

        if d["tech_level"] == "ВЫСОКИЙ":
            fmt = "Смешанный (онлайн + офлайн)"
        elif d["tech_level"] == "СРЕДНИЙ":
            fmt = "Комбинированный с элементами онлайн"
        else:
            fmt = "Традиционный аудиторный"

        overload = max(0.0, d["workload_hours"] - 30.0)
        satisfaction = max(0.0, min(100.0, 100 - overload * 2 - (100 - quality) * 0.3))

        return {
            self.OUTPUT_LABELS[0]: q_label,
            self.OUTPUT_LABELS[1]: need_extra,
            self.OUTPUT_LABELS[2]: f"{check_time} ч/нед",
            self.OUTPUT_LABELS[3]: fmt,
            self.OUTPUT_LABELS[4]: f"{satisfaction:.0f} %",
        }


class DeanBlackBox(BlackBoxBase):
    NAME = "Образовательный процесс (точка зрения ДЕКАНАТА)"
    DESCRIPTION = ("Система глазами деканата: цель — эффективно управлять "
                   "ресурсами курса и поддерживать рейтинг факультета.")
    INPUT_SPECS = [
        ("students_count", "Студентов на курсе, чел. [Инф]",     "300",  int,   "1..10000"),
        ("budget_places",  "Бюджетных мест [Инф]",               "150",  int,   "0..5000"),
        ("teachers_count", "Преподавателей, чел. [Инф]",         "30",   int,   "1..2000"),
        ("avg_ege",        "Средний балл ЕГЭ (0..100) [Инф]",    "70",   float, "0..100"),
        ("funding",        "Финансирование, тыс. руб. [Матер]",  "45000",float, ">=0"),
    ]
    OUTPUT_LABELS = [
        "Выход 1 (Инф):   Прогноз успеваемости курса",
        "Выход 2 (Инф):   Потребность в преподавателях",
        "Выход 3 (Инф):   Рейтинг факультета",
        "Выход 4 (Энерг): Затраты на 1 студента",
        "Выход 5 (Инф):   Рекомендуемый план набора",
    ]

    def validate(self, d):
        if not (1 <= d["students_count"] <= 10000):
            return "Студентов 1..10000"
        if not (0 <= d["budget_places"] <= 5000):
            return "Бюджетных мест 0..5000"
        if not (1 <= d["teachers_count"] <= 2000):
            return "Преподавателей 1..2000"
        if not (0 <= d["avg_ege"] <= 100):
            return "Средний балл ЕГЭ 0..100"
        if d["funding"] < 0:
            return "Финансирование не может быть < 0"
        return None

    def compute(self, d):
        ratio = d["students_count"] / max(1, d["teachers_count"])
        ege_norm = d["avg_ege"]
        ratio_penalty = max(0.0, (ratio - 12.0) * 2.5)
        success = max(0.0, min(100.0, ege_norm * 0.8 + 20 - ratio_penalty))

        if success >= 75:
            succ_label = f"Высокая ({success:.0f}%)"
        elif success >= 55:
            succ_label = f"Средняя ({success:.0f}%)"
        else:
            succ_label = f"Низкая ({success:.0f}%)"

        teachers_needed = int(math.ceil(d["students_count"] / 12.0))

        rating = round(min(100.0, ege_norm * 0.5 + success * 0.5), 1)

        cost = round(d["funding"] * 1000 / max(1, d["students_count"]), 1)

        if success >= 75 and d["budget_places"] > 0:
            plan = int(d["budget_places"] * 1.10)
        elif success >= 55:
            plan = d["budget_places"]
        else:
            plan = int(d["budget_places"] * 0.85)

        return {
            self.OUTPUT_LABELS[0]: succ_label,
            self.OUTPUT_LABELS[1]: f"{teachers_needed} чел. (норма 1:12)",
            self.OUTPUT_LABELS[2]: f"{rating} / 100",
            self.OUTPUT_LABELS[3]: f"{cost} руб./год",
            self.OUTPUT_LABELS[4]: f"{plan} мест",
        }


TEST_CASES = {
    "Студент": [
        ("Нормальные условия",
         dict(attendance=85, study_hours=15, prev_gpa=4.2, missed_deadlines=0, motivation="ВЫСОКИЙ")),
        ("Граничные (минимум)",
         dict(attendance=0, study_hours=0, prev_gpa=0, missed_deadlines=0, motivation="НИЗКИЙ")),
        ("Граничные (максимум)",
         dict(attendance=100, study_hours=168, prev_gpa=5, missed_deadlines=0, motivation="ВЫСОКИЙ")),
        ("Ошибка: посещаемость < 0",
         dict(attendance=-5, study_hours=10, prev_gpa=3, missed_deadlines=0, motivation="СРЕДНИЙ")),
        ("Ошибка: мотивация некорректна",
         dict(attendance=50, study_hours=10, prev_gpa=3, missed_deadlines=0, motivation="НЕТ")),
        ("Ошибка: пропуски < 0",
         dict(attendance=50, study_hours=10, prev_gpa=3, missed_deadlines=-2, motivation="СРЕДНИЙ")),
    ],
    "Преподаватель": [
        ("Нормальные условия",
         dict(group_size=25, avg_performance=75, workload_hours=18, has_materials="ДА", tech_level="СРЕДНИЙ")),
        ("Граничные (min): 1 студент, 0%",
         dict(group_size=1, avg_performance=0, workload_hours=0, has_materials="НЕТ", tech_level="НИЗКИЙ")),
        ("Граничные (max): 200 студентов, 100%",
         dict(group_size=200, avg_performance=100, workload_hours=60, has_materials="ДА", tech_level="ВЫСОКИЙ")),
        ("Ошибка: группа = 0",
         dict(group_size=0, avg_performance=70, workload_hours=20, has_materials="ДА", tech_level="СРЕДНИЙ")),
        ("Ошибка: успеваемость > 100",
         dict(group_size=25, avg_performance=150, workload_hours=20, has_materials="ДА", tech_level="СРЕДНИЙ")),
        ("Ошибка: тех. оснащение",
         dict(group_size=25, avg_performance=70, workload_hours=20, has_materials="ДА", tech_level="СУПЕР")),
    ],
    "Деканат": [
        ("Нормальные условия",
         dict(students_count=300, budget_places=150, teachers_count=30, avg_ege=70, funding=45000)),
        ("Граничные (min): 1 студент",
         dict(students_count=1, budget_places=0, teachers_count=1, avg_ege=0, funding=0)),
        ("Граничные (max)",
         dict(students_count=10000, budget_places=5000, teachers_count=2000, avg_ege=100, funding=10**7)),
        ("Ошибка: студентов < 1",
         dict(students_count=0, budget_places=150, teachers_count=30, avg_ege=70, funding=45000)),
        ("Ошибка: ЕГЭ > 100",
         dict(students_count=300, budget_places=150, teachers_count=30, avg_ege=250, funding=45000)),
        ("Ошибка: финансирование < 0",
         dict(students_count=300, budget_places=150, teachers_count=30, avg_ege=70, funding=-1)),
    ],
}


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("ЛР №1. Черный ящик: образовательный процесс (Вариант 1)")
        self.root.geometry("1050x720")

        self.systems = {
            "Студент":       StudentBlackBox(),
            "Преподаватель": TeacherBlackBox(),
            "Деканат":       DeanBlackBox(),
        }
        self.entries = {}

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_user = ttk.Frame(nb)
        nb.add(self.tab_user, text="  Режим пользователя  ")
        self._build_user_tab()

        self.tab_test = ttk.Frame(nb)
        nb.add(self.tab_test, text="  Режим преподавателя (автотесты)  ")
        self._build_test_tab()

    def _build_user_tab(self):
        top = ttk.Frame(self.tab_user)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(top, text="Точка зрения:", font=("Arial", 10, "bold")).pack(side="left")
        self.persp_var = tk.StringVar(value="Студент")
        cb = ttk.Combobox(top, textvariable=self.persp_var,
                          values=list(self.systems.keys()),
                          state="readonly", width=20)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._rebuild_inputs())

        ttk.Button(top, text="▶ Выполнить", command=self._run_user).pack(side="left", padx=6)

        self.desc_lbl = ttk.Label(self.tab_user, text="", foreground="#555",
                                  wraplength=1000, justify="left")
        self.desc_lbl.pack(fill="x", padx=10, pady=(0, 6))

        body = ttk.Frame(self.tab_user)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        self.inputs_frame = ttk.LabelFrame(body, text="Входы (X) — параметры внешней среды")
        self.inputs_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        out_frame = ttk.LabelFrame(body, text="Выходы (Y) — реакция системы")
        out_frame.pack(side="right", fill="both", expand=True, padx=(4, 0))
        self.user_out = scrolledtext.ScrolledText(out_frame, width=55, height=22,
                                                  font=("Consolas", 10))
        self.user_out.pack(fill="both", expand=True, padx=4, pady=4)

        self._rebuild_inputs()

    def _rebuild_inputs(self):
        for w in self.inputs_frame.winfo_children():
            w.destroy()
        self.entries.clear()

        name = self.persp_var.get()
        sys = self.systems[name]
        self.desc_lbl.config(text=sys.DESCRIPTION)

        for i, (key, label, default, cast, hint) in enumerate(sys.INPUT_SPECS):
            ttk.Label(self.inputs_frame, text=label).grid(
                row=i * 2, column=0, sticky="w", padx=4, pady=(8, 0))
            ttk.Label(self.inputs_frame, text=f"допустимо: {hint}",
                      foreground="#888", font=("Arial", 8)).grid(
                row=i * 2 + 1, column=0, sticky="w", padx=4)
            e = ttk.Entry(self.inputs_frame, width=24)
            e.insert(0, default)
            e.grid(row=i * 2, column=1, rowspan=2, padx=8, pady=4, sticky="w")
            self.entries[key] = (e, cast)

    def _run_user(self):
        name = self.persp_var.get()
        sys = self.systems[name]

        data = {}
        try:
            for key, (entry, cast) in self.entries.items():
                raw = entry.get().strip()
                if cast is str:
                    data[key] = raw.upper()
                else:
                    data[key] = cast(raw)
        except ValueError as e:
            self.user_out.delete("1.0", "end")
            self.user_out.insert("end", f"Ошибка преобразования ввода: {e}\n")
            return

        result = sys.run(data)

        self.user_out.delete("1.0", "end")
        self.user_out.insert("end", f"{sys.NAME}\n\n")
        self.user_out.insert("end", "ВХОДЫ:\n")
        for k, v in data.items():
            self.user_out.insert("end", f"  • {sys.input_label(k)} = {v}\n")
        self.user_out.insert("end", "\n" + "-" * 60 + "\nВЫХОДЫ:\n")
        for k, v in result.items():
            self.user_out.insert("end", f"  {k}\n      → {v}\n")

    def _build_test_tab(self):
        top = ttk.Frame(self.tab_test)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(top, text="Тестируемая система:", font=("Arial", 10, "bold")).pack(side="left")
        self.test_persp = tk.StringVar(value="Студент")
        ttk.Combobox(top, textvariable=self.test_persp,
                     values=list(self.systems.keys()),
                     state="readonly", width=20).pack(side="left", padx=6)
        ttk.Button(top, text="▶ Запустить автотесты",
                   command=self._run_tests).pack(side="left", padx=6)
        ttk.Button(top, text="Очистить",
                   command=lambda: self.test_out.delete("1.0", "end")).pack(side="left", padx=6)

        self.test_out = scrolledtext.ScrolledText(self.tab_test, height=30,
                                                  font=("Consolas", 10))
        self.test_out.pack(fill="both", expand=True, padx=8, pady=6)

    def _run_tests(self):
        name = self.test_persp.get()
        sys = self.systems[name]
        cases = TEST_CASES[name]

        self.test_out.delete("1.0", "end")
        self.test_out.insert("end", f"АВТОТЕСТЫ: {sys.NAME}\n")
        self.test_out.insert("end", f"{sys.DESCRIPTION}\n\n")

        ok, fail = 0, 0
        for title, data in cases:
            self.test_out.insert("end", f"— {title} —\n")
            self.test_out.insert("end", "   Вход:\n")
            for k, v in data.items():
                self.test_out.insert("end", f"      • {sys.input_label(k)} = {v}\n")
            res = sys.run(data)
            self.test_out.insert("end", "   Выход:\n")
            for k, v in res.items():
                self.test_out.insert("end", f"      {k} = {v}\n")

            is_emergency = any("АВАРИЙНЫЙ РЕЖИМ" in str(v) for v in res.values())
            is_error_case = title.startswith("Ошибка")
            if is_emergency and is_error_case:
                self.test_out.insert("end", "   [+] Система корректно ушла в защиту\n\n")
                ok += 1
            elif not is_emergency and not is_error_case:
                self.test_out.insert("end", "   [+] Система отработала штатно\n\n")
                ok += 1
            else:
                self.test_out.insert("end", "   [-] Неожиданное поведение!\n\n")
                fail += 1

        self.test_out.insert("end", f"\nИТОГ: успешно {ok} / ошибок {fail}\n")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except Exception:
        pass
    App(root)
    root.mainloop()