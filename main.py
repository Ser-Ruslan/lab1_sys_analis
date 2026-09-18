# -*- coding: utf-8 -*-
"""
Лабораторная работа № 3.
Вариант 1. Документальное обеспечение управленческой деятельности
коммерческой фирмы.

Приложение содержит:
  1) контекстную диаграмму IDEF0 (A-0);
  2) диаграмму декомпозиции A0 ровно на два функциональных блока (A1, A2);
  3) таблицы информационных связей для обеих диаграмм;
  4) объектно-ориентированную имитацию спроектированных блоков A1 и A2.

Запуск:  python lab3_variant1.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime, timedelta

# ===========================================================================
# 1. ПРЕДМЕТНАЯ ОБЛАСТЬ (ОБЪЕКТНАЯ МОДЕЛЬ)
# ===========================================================================

# Номенклатура дел фирмы (управляющее воздействие для блока A1)
CASE_NOMENCLATURE = {
    "Приказ":            "01-01 «Приказы по основной деятельности»",
    "Распоряжение":      "01-02 «Распоряжения по основной деятельности»",
    "Письмо":            "01-15 «Переписка по основным вопросам деятельности»",
    "Заявление":         "01-20 «Обращения организаций и граждан»",
    "Служебная записка": "01-08 «Служебные записки»",
}


class IncomingDocument:
    """ВХОДНОЙ ПОТОК системы: входящая корреспонденция / поручение руководства."""

    def __init__(self, number, correspondent, subject, doc_kind,
                 pages, executor, urgent=False):
        self.number = number                # исходящий номер корреспондента
        self.correspondent = correspondent  # от кого поступил документ
        self.subject = subject              # тема (заголовок к тексту)
        self.doc_kind = doc_kind            # вид документа
        self.pages = pages                  # объём в листах
        self.executor = executor            # назначенный исполнитель
        self.urgent = urgent                # признак срочности

        self.is_valid = True                # прошёл ли контроль по инструкции
        self.reg_index = None               # регистрационный номер
        self.reg_date = None                # дата регистрации
        self.deadline = None                # срок исполнения
        self.resolution = None              # резолюция руководителя
        self.case_index = None              # дело по номенклатуре дел


class OutgoingDocument:
    """Объект документа, формируемый блоком A2 (проект → подписанный документ)."""

    def __init__(self, incoming: IncomingDocument):
        self.incoming = incoming
        self.reg_index = None
        self.status = "Проект"
        self.is_approved = False
        self.is_signed = False
        self.is_sent = False
        self.is_filed = False


class Registrar:
    """ФУНКЦИОНАЛЬНЫЙ БЛОК A1: Регистрация и распределение входящей документации.

    Механизмы: секретарь-референт, ПК с СЭД, сканер.
    Управление: Инструкция по делопроизводству, Номенклатура дел фирмы.
    """

    MAX_PAGES_WITHOUT_VISA = 50

    def __init__(self, name):
        self.name = name
        self.counter = 0
        self.journal = []       # журнал регистрации входящих документов

    def process(self, doc: IncomingDocument, log):
        log(f"[Блок A1] Секретарь-референт {self.name} принимает документ "
            f"№ {doc.number} от «{doc.correspondent}».")
        log("[Управление] Проверка по Инструкции по делопроизводству...")

        # --- контроль входного потока по регламенту ---
        if not doc.number.strip():
            log("[Управление] ОТКАЗ: не указан номер входящего документа. "
                "Регистрация невозможна.")
            doc.is_valid = False
            return None

        if not doc.subject.strip():
            log("[Управление] ОТКАЗ: не указана тема (заголовок к тексту) документа "
                "— п. 3.2 Инструкции по делопроизводству.")
            doc.is_valid = False
            return None

        if doc.pages <= 0:
            log("[Управление] ОТКАЗ: некорректно указан объём документа.")
            doc.is_valid = False
            return None

        if doc.pages > self.MAX_PAGES_WITHOUT_VISA:
            log(f"[Управление] ВНИМАНИЕ: объём {doc.pages} л. превышает "
                f"{self.MAX_PAGES_WITHOUT_VISA} л. — требуется дополнительная "
                f"виза руководителя.")

        # --- регистрация ---
        self.counter += 1
        doc.reg_index = f"{self.counter:03d}-ВХ"
        doc.reg_date = datetime.now()

        days = 1 if doc.urgent else 30
        doc.deadline = doc.reg_date + timedelta(days=days)

        # --- определение дела по номенклатуре дел ---
        doc.case_index = CASE_NOMENCLATURE.get(
            doc.doc_kind, "01-15 «Переписка по основным вопросам деятельности»")

        # --- резолюция руководителя ---
        doc.resolution = (f"Исполнитель: {doc.executor}. "
                          f"Срок исполнения: {doc.deadline:%d.%m.%Y}.")

        self.journal.append((doc.reg_index, doc.reg_date, doc.number, doc.subject))

        log(f"[Блок A1] Документу присвоен регистрационный номер "
            f"{doc.reg_index} от {doc.reg_date:%d.%m.%Y}.")
        log(f"[Блок A1] Дело по номенклатуре дел: {doc.case_index}.")
        log(f"[Блок A1] Резолюция руководителя: {doc.resolution}")
        log(f"[Блок A1] Записей в журнале регистрации: {len(self.journal)}.")
        log("[Блок A1] ВЫХОД: зарегистрированный документ с резолюцией "
            "передан в блок A2.")
        return doc


class DocumentSupport:
    """ФУНКЦИОНАЛЬНЫЙ БЛОК A2: Подготовка и оформление исходящего документа.

    Механизмы: делопроизводитель, исполнитель, ПК, принтер, СЭД.
    Управление: ГОСТ Р 7.0.97-2016, Устав фирмы.
    """

    def __init__(self, name):
        self.name = name
        self.counter = 0
        self.archive = []       # сформированные дела

    def process(self, incoming: IncomingDocument, log):
        if incoming is None or not incoming.is_valid:
            log("[Блок A2] ОШИБКА: на вход блока не поступил "
                "зарегистрированный документ.")
            log("[Блок A2] Обработка невозможна. Процесс остановлен.")
            return None

        log(f"[Блок A2] Делопроизводитель {self.name} принял документ "
            f"№ {incoming.reg_index}.")
        log(f"[Блок A2] Исполнитель {incoming.executor} подготовил проект ответа "
            f"по теме «{incoming.subject}».")

        self.counter += 1
        doc = OutgoingDocument(incoming)
        doc.reg_index = f"{self.counter:03d}-ИСХ"
        doc.status = "Проект подготовлен"
        log(f"[Блок A2] Проекту исходящего документа присвоен номер {doc.reg_index}.")

        # --- контроль оформления (управление: ГОСТ) ---
        log("[Управление] Проверка оформления по ГОСТ Р 7.0.97-2016:")
        log("             • реквизиты документа ............ в норме;")
        log("             • поля, шрифт, абзацы ............ в норме;")
        log("             • гриф подписи и дата ............ в норме.")
        doc.is_approved = True
        doc.status = "Согласован"

        log(f"[Блок A2] Документ {doc.reg_index} согласован и подписан "
            f"руководителем фирмы.")
        doc.is_signed = True
        doc.status = "Подписан"

        log(f"[Блок A2] Документ зарегистрирован в журнале исходящих "
            f"и отправлен в «{incoming.correspondent}».")
        doc.is_sent = True
        doc.status = "Отправлен адресату"

        doc.is_filed = True
        self.archive.append(doc)
        log(f"[Блок A2] Копия документа подшита в дело: {incoming.case_index}.")
        log(f"[Блок A2] Дело передано в архив фирмы. "
            f"Всего дел в архиве: {len(self.archive)}.")
        log(f"[ВЫХОД] Документ № {doc.reg_index} обработан. "
            f"Итоговый статус: «{doc.status}».")
        return doc


# ===========================================================================
# 2. ГРАФИЧЕСКИЙ ИНТЕРФЕЙС
# ===========================================================================

class Lab3App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("ЛР № 3 — IDEF0 и ООП-имитация | Вариант 1: "
                   "Документационное обеспечение управленческой деятельности")
        self.geometry("1280x820")
        self.minsize(1150, 720)

        # Исполнители (механизмы) — создаются один раз, счётчики сохраняются
        self.registrar = Registrar("Смирнова О.В.")
        self.doc_support = DocumentSupport("Кузнецова Н.П.")

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.tab_a0 = ttk.Frame(nb)
        self.tab_a0_decomp = ttk.Frame(nb)
        self.tab_tables = ttk.Frame(nb)
        self.tab_sim = ttk.Frame(nb)

        nb.add(self.tab_a0, text="  Диаграмма A-0  ")
        nb.add(self.tab_a0_decomp, text="  Диаграмма A0 (2 блока)  ")
        nb.add(self.tab_tables, text="  Таблицы информационных связей  ")
        nb.add(self.tab_sim, text="  Имитация процесса  ")

        self._build_a0()
        self._build_a0_decomp()
        self._build_tables()
        self._build_sim()

    # ------------------------------------------------------------------
    # Вспомогательное: стрелка IDEF0
    # ------------------------------------------------------------------
    @staticmethod
    def _arrow(canvas, x1, y1, x2, y2, color="#1f4e79"):
        canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST,
                           arrowshape=(16, 20, 7), width=2, fill=color)

    # ------------------------------------------------------------------
    # Вкладка 1. Контекстная диаграмма A-0
    # ------------------------------------------------------------------
    def _build_a0(self):
        c = tk.Canvas(self.tab_a0, bg="white", highlightthickness=0)
        c.pack(fill=tk.BOTH, expand=True)

        c.create_text(560, 26, text="Контекстная диаграмма A-0",
                      font=("Segoe UI", 15, "bold"), fill="#1f4e79")

        # --- функциональный блок A0 ---
        c.create_rectangle(360, 250, 760, 390,
                           outline="#1f4e79", width=2, fill="#eaf3fb")
        c.create_text(560, 310,
                      text="Документационное обеспечение\n"
                           "управленческой деятельности\n"
                           "коммерческой фирмы",
                      font=("Segoe UI", 11, "bold"),
                      fill="#1f4e79", justify="center")
        c.create_text(748, 378, text="A0",
                      font=("Segoe UI", 11, "bold"), fill="#1f4e79")

        # --- ВХОД ---
        self._arrow(c, 60, 320, 360, 320)
        c.create_text(65, 305, anchor="sw",
                      text="Входящая корреспонденция,\nпоручения руководства",
                      font=("Segoe UI", 9), fill="#333333")

        # --- УПРАВЛЕНИЕ ---
        self._arrow(c, 560, 90, 560, 250)
        c.create_text(575, 100, anchor="w",
                      text="ГОСТ Р 7.0.97-2016;\n"
                           "Инструкция по делопроизводству;\n"
                           "Номенклатура дел фирмы",
                      font=("Segoe UI", 9), fill="#333333")

        # --- МЕХАНИЗМЫ ---
        self._arrow(c, 560, 580, 560, 390)
        c.create_text(575, 560, anchor="w",
                      text="Секретарь-референт,\n"
                           "делопроизводитель,\n"
                           "ПК с СЭД, сканер, принтер",
                      font=("Segoe UI", 9), fill="#333333")

        # --- ВЫХОД ---
        self._arrow(c, 760, 320, 1060, 320)
        c.create_text(1055, 305, anchor="se",
                      text="Оформленный управленческий\n"
                           "документ; дело, подшитое\n"
                           "в номенклатуру дел",
                      font=("Segoe UI", 9), fill="#333333")

    # ------------------------------------------------------------------
    # Вкладка 2. Диаграмма декомпозиции A0 (ровно 2 блока)
    # ------------------------------------------------------------------
    def _build_a0_decomp(self):
        c = tk.Canvas(self.tab_a0_decomp, bg="white", highlightthickness=0)
        c.pack(fill=tk.BOTH, expand=True)

        c.create_text(560, 24,
                      text="Диаграмма декомпозиции A0 — два функциональных блока",
                      font=("Segoe UI", 15, "bold"), fill="#1f4e79")

        # --- Блок A1 ---
        c.create_rectangle(150, 250, 470, 400,
                           outline="#1f4e79", width=2, fill="#eaf3fb")
        c.create_text(310, 315,
                      text="Регистрация и распределение\nвходящей документации",
                      font=("Segoe UI", 10, "bold"),
                      fill="#1f4e79", justify="center")
        c.create_text(458, 388, text="A1",
                      font=("Segoe UI", 10, "bold"), fill="#1f4e79")

        # --- Блок A2 ---
        c.create_rectangle(650, 250, 970, 400,
                           outline="#1f4e79", width=2, fill="#eaf3fb")
        c.create_text(810, 315,
                      text="Подготовка и оформление\nисходящего документа",
                      font=("Segoe UI", 10, "bold"),
                      fill="#1f4e79", justify="center")
        c.create_text(958, 388, text="A2",
                      font=("Segoe UI", 10, "bold"), fill="#1f4e79")

        # --- Вход в A1 ---
        self._arrow(c, 40, 325, 150, 325)
        c.create_text(45, 310, anchor="sw",
                      text="Входящая корреспонденция,\nпоручения руководства",
                      font=("Segoe UI", 9), fill="#333333")

        # --- A1 -> A2 (внутренняя связь) ---
        self._arrow(c, 470, 325, 650, 325)
        c.create_text(560, 312, anchor="s",
                      text="Зарегистрированный документ\nс резолюцией руководителя",
                      font=("Segoe UI", 9), fill="#333333")

        # --- Ветвление выхода A1: журнал регистрации ---
        self._arrow(c, 560, 325, 560, 470)
        c.create_text(572, 452, anchor="nw",
                      text="Отметка в журнале регистрации\nвходящих документов",
                      font=("Segoe UI", 9), fill="#333333")

        # --- Управление A1 ---
        self._arrow(c, 310, 90, 310, 250)
        c.create_text(322, 130, anchor="w",
                      text="Инструкция по\nделопроизводству;\nНоменклатура дел фирмы",
                      font=("Segoe UI", 9), fill="#333333")

        # --- Механизмы A1 ---
        self._arrow(c, 310, 590, 310, 400)
        c.create_text(322, 560, anchor="w",
                      text="Секретарь-референт,\nСЭД, сканер",
                      font=("Segoe UI", 9), fill="#333333")

        # --- Управление A2 ---
        self._arrow(c, 810, 90, 810, 250)
        c.create_text(822, 130, anchor="w",
                      text="ГОСТ Р 7.0.97-2016;\nУстав фирмы",
                      font=("Segoe UI", 9), fill="#333333")

        # --- Механизмы A2 ---
        self._arrow(c, 810, 590, 810, 400)
        c.create_text(822, 560, anchor="w",
                      text="Делопроизводитель,\nисполнитель, ПК, принтер",
                      font=("Segoe UI", 9), fill="#333333")

        # --- Выход A2 ---
        self._arrow(c, 970, 325, 1090, 325)
        c.create_text(1085, 310, anchor="se",
                      text="Оформленный документ,\nдело в архиве",
                      font=("Segoe UI", 9), fill="#333333")

    # ------------------------------------------------------------------
    # Вкладка 3. Таблицы информационных связей
    # ------------------------------------------------------------------
    def _build_tables(self):
        style = ttk.Style()
        style.configure("Treeview", rowheight=42, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

        outer = ttk.Frame(self.tab_tables)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---------- Таблица 1: контекстная диаграмма ----------
        lf1 = ttk.LabelFrame(
            outer, text=" Таблица информационных связей контекстной диаграммы A-0 ")
        lf1.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        cols1 = ("type", "name", "desc")
        tv1 = ttk.Treeview(lf1, columns=cols1, show="headings", height=5)
        tv1.heading("type", text="Тип потока (IDEF0)")
        tv1.heading("name", text="Название стрелки")
        tv1.heading("desc", text="Описание информационного / материального объекта")
        tv1.column("type", width=150, anchor="center")
        tv1.column("name", width=320, anchor="w")
        tv1.column("desc", width=700, anchor="w")

        rows1 = [
            ("Вход (Input)",
             "Входящая корреспонденция, поручения руководства",
             "Первичные данные: письма, запросы, заявления, служебные записки "
             "и поручения руководства, требующие документационного оформления."),
            ("Управление (Control)",
             "ГОСТ Р 7.0.97-2016; Инструкция по делопроизводству; "
             "Номенклатура дел фирмы; Устав фирмы",
             "Законодательные нормы и внутренние корпоративные правила "
             "оформления, регистрации, согласования и хранения управленческих "
             "документов."),
            ("Механизмы (Mechanism)",
             "Секретарь-референт, делопроизводитель, ПК с СЭД, сканер, принтер",
             "Сотрудники, выполняющие работу, и технические средства "
             "автоматизации документооборота фирмы."),
            ("Выход (Output)",
             "Оформленный управленческий документ; дело, подшитое "
             "в номенклатуру дел",
             "Готовый документ, прошедший проверку оформления, подписанный "
             "и отправленный адресату; сформированное дело для передачи в архив."),
        ]
        for r in rows1:
            tv1.insert("", tk.END, values=r)

        sb1y = ttk.Scrollbar(lf1, orient="vertical", command=tv1.yview)
        sb1x = ttk.Scrollbar(lf1, orient="horizontal", command=tv1.xview)
        tv1.configure(yscrollcommand=sb1y.set, xscrollcommand=sb1x.set)
        tv1.grid(row=0, column=0, sticky="nsew")
        sb1y.grid(row=0, column=1, sticky="ns")
        sb1x.grid(row=1, column=0, sticky="ew")
        lf1.rowconfigure(0, weight=1)
        lf1.columnconfigure(0, weight=1)

        # ---------- Таблица 2: диаграмма A0 ----------
        lf2 = ttk.LabelFrame(
            outer, text=" Таблица информационных связей диаграммы декомпозиции A0 ")
        lf2.pack(fill=tk.BOTH, expand=True)

        cols2 = ("block", "inout", "mech", "out")
        tv2 = ttk.Treeview(lf2, columns=cols2, show="headings", height=3)
        tv2.heading("block", text="Функциональный блок")
        tv2.heading("inout", text="Входные потоки / Управление")
        tv2.heading("mech", text="Исполнители (Механизмы)")
        tv2.heading("out", text="Выходные потоки")
        tv2.column("block", width=250, anchor="w")
        tv2.column("inout", width=380, anchor="w")
        tv2.column("mech", width=230, anchor="w")
        tv2.column("out", width=320, anchor="w")

        rows2 = [
            ("A1: Регистрация и распределение входящей документации",
             "Вход: входящая корреспонденция, поручения руководства. "
             "Управление: Инструкция по делопроизводству; Номенклатура дел фирмы.",
             "Секретарь-референт, ПК с СЭД, сканер",
             "Зарегистрированный документ с резолюцией руководителя "
             "(передаётся в блок A2); отметка в журнале регистрации "
             "входящих документов."),
            ("A2: Подготовка и оформление исходящего документа",
             "Вход: зарегистрированный документ с резолюцией (из блока A1). "
             "Управление: ГОСТ Р 7.0.97-2016; Устав фирмы.",
             "Делопроизводитель, исполнитель, ПК, принтер, СЭД",
             "Оформленный исходящий документ, отправленный адресату; "
             "дело, подшитое в номенклатуру дел и переданное в архив "
             "(конечный результат)."),
        ]
        for r in rows2:
            tv2.insert("", tk.END, values=r)

        sb2y = ttk.Scrollbar(lf2, orient="vertical", command=tv2.yview)
        sb2x = ttk.Scrollbar(lf2, orient="horizontal", command=tv2.xview)
        tv2.configure(yscrollcommand=sb2y.set, xscrollcommand=sb2x.set)
        tv2.grid(row=0, column=0, sticky="nsew")
        sb2y.grid(row=0, column=1, sticky="ns")
        sb2x.grid(row=1, column=0, sticky="ew")
        lf2.rowconfigure(0, weight=1)
        lf2.columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Вкладка 4. Имитация процесса
    # ------------------------------------------------------------------
    def _build_sim(self):
        main = ttk.Frame(self.tab_sim)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = ttk.LabelFrame(main, text=" Входные данные (Вход системы) ")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        right = ttk.LabelFrame(main, text=" Протокол выполнения процесса ")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- переменные формы ---
        self.var_number = tk.StringVar(value="REQ-001")
        self.var_corr = tk.StringVar(value="ООО «ТехноПром»")
        self.var_subject = tk.StringVar(
            value="О предоставлении коммерческого предложения")
        self.var_kind = tk.StringVar(value="Письмо")
        self.var_pages = tk.IntVar(value=3)
        self.var_exec = tk.StringVar(value="Иванов И.И.")
        self.var_urgent = tk.BooleanVar(value=False)

        fields = [
            ("Номер входящего:", tk.Entry(left, textvariable=self.var_number, width=30)),
            ("Корреспондент:", tk.Entry(left, textvariable=self.var_corr, width=30)),
            ("Тема документа:", tk.Entry(left, textvariable=self.var_subject, width=30)),
            ("Вид документа:", ttk.Combobox(left, textvariable=self.var_kind,
                                            values=list(CASE_NOMENCLATURE.keys()),
                                            state="readonly", width=28)),
            ("Количество листов:", ttk.Spinbox(left, from_=1, to=200,
                                                textvariable=self.var_pages, width=29)),
            ("Исполнитель:", ttk.Combobox(left, textvariable=self.var_exec,
                                           values=["Иванов И.И.", "Петров П.П.",
                                                   "Сидорова А.А."],
                                           state="readonly", width=28)),
        ]
        for i, (label, widget) in enumerate(fields):
            ttk.Label(left, text=label).grid(row=i, column=0, sticky="w",
                                             padx=6, pady=5)
            widget.grid(row=i, column=1, sticky="ew", padx=6, pady=5)

        ttk.Checkbutton(left, text="Срочный документ (срок — 1 день)",
                        variable=self.var_urgent).grid(
            row=len(fields), column=0, columnspan=2, sticky="w", padx=6, pady=6)

        ttk.Separator(left, orient="horizontal").grid(
            row=len(fields) + 1, column=0, columnspan=2,
            sticky="ew", padx=6, pady=8)

        ttk.Button(left, text="▶  Запустить процесс",
                   command=self.run_process).grid(
            row=len(fields) + 2, column=0, columnspan=2,
            sticky="ew", padx=6, pady=4)

        ttk.Button(left, text="✖  Очистить протокол",
                   command=lambda: self.log_widget.delete("1.0", tk.END)).grid(
            row=len(fields) + 3, column=0, columnspan=2,
            sticky="ew", padx=6, pady=(0, 10))

        # --- протокол ---
        self.log_widget = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=("Consolas", 10),
            bg="#0f1b2a", fg="#d6e4f0", insertbackground="white")
        self.log_widget.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ------------------------------------------------------------------
    # Логирование в протокол
    # ------------------------------------------------------------------
    def _log(self, text=""):
        self.log_widget.insert(tk.END, text + "\n")
        self.log_widget.see(tk.END)
        self.update_idletasks()

    # ------------------------------------------------------------------
    # Запуск имитации
    # ------------------------------------------------------------------
    def run_process(self):
        self.log_widget.delete("1.0", tk.END)
        log = self._log

        log("=" * 78)
        log("  СИСТЕМА ДОКУМЕНТАЦИОННОГО ОБЕСПЕЧЕНИЯ УПРАВЛЕНЧЕСКОЙ ДЕЯТЕЛЬНОСТИ")
        log("  Вариант 1. Имитация блоков A1 и A2 функциональной модели IDEF0")
        log("=" * 78)

        try:
            pages = int(self.var_pages.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Ошибка ввода",
                                 "Количество листов должно быть целым числом.")
            return

        doc = IncomingDocument(
            number=self.var_number.get().strip(),
            correspondent=self.var_corr.get().strip(),
            subject=self.var_subject.get().strip(),
            doc_kind=self.var_kind.get(),
            pages=pages,
            executor=self.var_exec.get(),
            urgent=self.var_urgent.get(),
        )

        log("")
        log(f"[ВХОД] Документ № {doc.number} от «{doc.correspondent}»")
        log(f"       Вид: {doc.doc_kind} | Тема: «{doc.subject}» | "
            f"Объём: {doc.pages} л.")
        log(f"       Срочность: {'СРОЧНЫЙ' if doc.urgent else 'обычный'}")
        log("-" * 78)

        registered = self.registrar.process(doc, log)

        log("-" * 78)
        outgoing = self.doc_support.process(registered, log)
        log("-" * 78)

        if outgoing is not None:
            log("=== ПРОЦЕСС ЗАВЕРШЁН УСПЕШНО. ОШИБОК НЕ ВЫЯВЛЕНО ===")
        else:
            log("=== ПРОЦЕСС ОСТАНОВЛЕН. ДОКУМЕНТ НЕ ОБРАБОТАН ===")


# ===========================================================================
# 3. ТОЧКА ВХОДА
# ===========================================================================

if __name__ == "__main__":
    app = Lab3App()
    app.mainloop()