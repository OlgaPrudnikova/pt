# pip install rich
# pip install pyyaml

from pathlib import Path
import sys
#import yaml
import datetime
import subprocess
import uuid
import copy
import rich.table
import rich.markup
import re
import json
import os
import time

import wx
import wx.adv
import wx.html
import wx.lib.splitter
import wx.py.editwindow

from threading import Timer
import psutil

import hashlib

def load_task(task_name):
  task_file_name = "{0}.json".format(task_name)
  task_file_path = Path('.') / "tasks" / task_file_name
  if not task_file_path.is_file(): raise Exception("Файл завдання \"{0}\" не знайдено.".format(task_name))
  last_modify_date = datetime.datetime.fromtimestamp(task_file_path.stat().st_mtime)

  task = None
  with open(task_file_path, 'r', encoding='utf8') as file: task = json.load(file)
  task["name"] = task_name
  task["filename"] = task_file_name
  task["lastmodify"] = last_modify_date
  task["is_task"] = True

  if isinstance(task["Опис"], list):
    task["Опис"] = "".join(task["Опис"])

  return task

def load_tasks():
  files = map(lambda x: re.sub("\\.json$","", str(x.name)), [f for f in (Path('.') / "tasks").glob("*.json") if f.is_file()])
  return list([load_task(f) for f in files])

def load_category(category_no):
  category_file_name = "{0}.txt".format(category_no)
  category_file_path = Path('.') / "tasks" / category_file_name
  if not category_file_path.is_file(): raise Exception("Файл категорії \"{0}\" не знайдено.".format(category_no))

  category = {}
  category["name"] = category_no
  category["filename"] = category_file_name
  with open(category_file_path, 'r', encoding='utf8') as file: category["Опис"] = file.read()

  return category

def load_categories():
  files = map(lambda x: re.sub("\\.txt$","", str(x.name)), [f for f in (Path('.') / "tasks").glob("*.txt") if f.is_file()])
  return list([load_category(f) for f in files])

def load_code(task_name,user):
  code_file_name = "{0}.py".format(task_name)
  code_file_path = Path('.') / "users" / user / code_file_name

  #if not code_file_path.is_file(): raise Exception("Програма завдання \"{0}\" для користувача \"{1}\" не знайдена.".format(task_name,user))

  code = ''
  if code_file_path.is_file():
    with open(code_file_path, 'r', encoding='utf8') as file: code = file.read()
  return code

def save_code(task_name,user,code):
  code_file_name = "{0}.py".format(task_name)
  if not((Path('.') / "users" / user).is_dir()):
    os.mkdir(Path('.') / "users" / user)
  code_file_path = Path('.') / "users" / user / code_file_name
  if str(code).strip():
    with open(code_file_path, 'w', encoding='utf8', newline='') as file: file.write(code)
  else:
    if code_file_path.is_file(): os.remove(code_file_path)

def load_reviews():
  reviews_file_name = "reviews.json"
  reviews_file_path = Path('.') / "users" / reviews_file_name
  if reviews_file_path.is_file():
    with open(reviews_file_path, 'r', encoding='utf8') as file: return(json.load(file))
  else:
    return([])

def add_review(user, review_text):
  reviews = load_reviews();
  review = {}
  review["Користувач"] = user
  review["Відгук"] = review_text
  review["Час"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
  reviews.append(review)
  reviews_file_name = "reviews.json"
  reviews_file_path = Path('.') / "users" / reviews_file_name
  with open(reviews_file_path, 'w', encoding='utf8') as file: file.write(json.dumps(reviews, indent=4, ensure_ascii=False))

def append_log(login, user, message):
  log_file_name = "log.txt"
  log_file_path = Path('.') / "users" / log_file_name
  with open(log_file_path, 'a', encoding='utf8') as file: 
    file.write("{0} - {1} ({2}) : {3}\n".format(str(datetime.datetime.now()), login, user, message))

def kill(proc_pid):
    process = psutil.Process(proc_pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()

def run_task(task, user, code):

  for test in task["Тести"]:
    test["Отримано"] = ""
    test["Статус"] = ""
    test["Повідомлення"] = ""
  task["Статус"] = ""

  if not(code.strip()): return

  task["code"] = code

  code = "{0}\n{1}".format(
    "import builtins\ndef input(*args): x = builtins.input(*args); print(); return x",
    code
    )

  program_file_name = "{0}.py".format(uuid.uuid4())
  program_file_path = Path(".") / "users" / user / program_file_name

  try:
    with open(program_file_path, 'w', encoding='utf8') as file: file.write(code)

    for test in task["Тести"]:
      test_input = "\n".join(test["Вхід"])
      expected_output = test["Вихід"].strip()

      actual_output = None 
      actual_errors = None

      os.environ['PYTHONIOENCODING'] =  'utf-8'
      proc = subprocess.Popen("python {0} {1}".format(program_file_path, test_input), 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE,
                              encoding="utf-8", universal_newlines=True, creationflags = subprocess.CREATE_NO_WINDOW)
      try:
        (actual_output, actual_errors) = map(lambda x: x.strip(), proc.communicate(input=test_input,timeout=2))
      except subprocess.TimeoutExpired:
        kill(proc.pid)
        test["Отримано"] = "Час вичерпано"
        test["Повідомлення"] = "Час вичерпано"
        test["Статус"] = "Помилка"


      if not actual_errors and test["Повідомлення"] != "Час вичерпано":
        a_actual_output = list(filter(lambda x: x, map(lambda x: x.strip(), actual_output.split("\n"))))
        actual_output = a_actual_output[-1].strip() if len(a_actual_output) > 0 else ""
        test["Отримано"] = actual_output

      if test["Повідомлення"] != "Час вичерпано":
        if actual_errors:
          test["Статус"] = "Помилка"
          test["Повідомлення"] = actual_errors
        elif not(actual_output):
          test["Статус"] = "Помилка"
          test["Повідомлення"] = "Значення відсутнє"
        elif expected_output == actual_output:
          test["Статус"] = "Пройдено"
          test["Повідомлення"] = ""
        else:
          test["Статус"] = "Не пройдено"
          test["Повідомлення"] = ""

  finally:
    program_file_path.unlink(True)

  if task["Тести"]:
    if len(list(filter(lambda x: x["Статус"] == "Помилка", task["Тести"]))) > 0:
      task["Статус"] = "Помилка"
    elif len(list(filter(lambda x: x["Статус"] == "Не пройдено", task["Тести"]))) > 0:
      task["Статус"] = "Не пройдено"
    elif len(list(filter(lambda x: x["Статус"] == "Пройдено", task["Тести"]))) > 0:
      task["Статус"] = "Пройдено"

def run_tasks(win, tasks, user):
  for i, task in enumerate(tasks):
    code = load_code(task["name"], user)
    if code: run_task(task, user, code)
    win.progress_lbl.SetLabel("Виконую завдання {0}/{1}".format(i+1, len(tasks)))
    win.Layout()
    win.Update()
    wx.YieldIfNeeded()



main_frame = None
login_frame = None


class MainFrame(wx.Frame):
  def __init__(self):
    wx.Frame.__init__(self, None, -1, "Python Тренажер", size=(1200, 700))

    self.menuBar = wx.MenuBar()

    self.file_menu = wx.Menu()
    self.menuBar.Append(self.file_menu, "Файл")
    self.save_item = self.file_menu.Append(-1, "Зберегти код завдання", "Код поточного завдання буде збережено для подальшої розробки.")
    self.Bind(wx.EVT_MENU, self.on_menu_save, self.save_item)
    self.file_menu.AppendSeparator()
    self.logout_item = self.file_menu.Append(-1, "Завершити сеанс", "")
    self.Bind(wx.EVT_MENU, self.on_menu_logout, self.logout_item)
    self.quit_item = self.file_menu.Append(-1, "Закрити програму", "")
    self.Bind(wx.EVT_MENU, self.on_menu_quit, self.quit_item)

    review_menu = wx.Menu()
    self.menuBar.Append(review_menu, "Відгуки")
    self.create_review_item = review_menu.Append(-1, "Створити", "")
    self.Bind(wx.EVT_MENU, self.on_menu_create_review, self.create_review_item)

    self.show_reviews_item = review_menu.Append(-1, "Переглянути", "")
    self.Bind(wx.EVT_MENU, self.on_menu_show_reviews, self.show_reviews_item)

    help_menu = wx.Menu()
    self.menuBar.Append(help_menu, "Допомога")
    self.about_item = help_menu.Append(-1, "Про програму", "")
    self.Bind(wx.EVT_MENU, self.on_menu_about, self.about_item)


    self.SetMenuBar(self.menuBar)


    self.splitter = wx.lib.splitter.MultiSplitterWindow(self, style=wx.SP_NO_XP_THEME | wx.SP_3DSASH | wx.SP_LIVE_UPDATE)

    top_text_font = wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
    code_name_font = wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD)

    img_question_mark = wx.Bitmap()
    img_question_mark.LoadFile(r"images/icons8-question-mark-16.png", wx.BITMAP_TYPE_PNG)
    img_success = wx.Bitmap()
    img_success.LoadFile(r"images/icons8-success-16.png", wx.BITMAP_TYPE_PNG)
    img_failure = wx.Bitmap()
    img_failure.LoadFile(r"images/icons8-warning-16.png", wx.BITMAP_TYPE_PNG)
    img_error = wx.Bitmap()
    img_error.LoadFile(r"images/icons8-error-16.png", wx.BITMAP_TYPE_PNG)

    self.status_image_list = wx.ImageList(16,16)
    self.status_image_list.Add(img_question_mark)
    self.status_image_list.Add(img_success)
    self.status_image_list.Add(img_failure)
    self.status_image_list.Add(img_error)
    
    self.task_tree_panel = wx.Panel(self.splitter)
    self.task_tree_sizer = wx.BoxSizer(wx.VERTICAL)
    self.task_tree_top_text = wx.StaticText(self.task_tree_panel, -1, "Обери завдання ->", style=wx.ALIGN_CENTER)
    self.task_tree_top_text.SetFont(top_text_font)
    self.task_tree_sizer.Add(self.task_tree_top_text, 0, flag=wx.EXPAND)
    self.task_tree_ctrl = wx.TreeCtrl(self.task_tree_panel, style=wx.TR_HAS_BUTTONS | wx.BORDER_NONE | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT)    
    self.task_tree_ctrl.AssignImageList(self.status_image_list)
    self.Bind(wx.EVT_TREE_SEL_CHANGED, self.task_tree_sel_changed, self.task_tree_ctrl)
    self.task_tree_sizer.Add(self.task_tree_ctrl, 1, flag=wx.EXPAND)
    self.task_tree_panel.SetSizer(self.task_tree_sizer)

    self.code_panel = wx.Panel(self.splitter)
    self.code_sizer = wx.BoxSizer(wx.VERTICAL)
    self.code_top_text = wx.StaticText(self.code_panel, -1, "Виконай завдання ->", style=wx.ALIGN_CENTER)
    self.code_top_text.SetFont(top_text_font)
    self.code_sizer.Add(self.code_top_text, 0, flag=wx.EXPAND)
    self.code_name_text = wx.StaticText(self.code_panel, -1, "", style=wx.LEFT)
    self.code_name_text.SetFont(code_name_font)
    self.code_sizer.Add(self.code_name_text, 0, wx.EXPAND|wx.ALL, 5)
    self.code_desc_text = wx.StaticText(self.code_panel, -1, "", style=wx.LEFT)
    self.code_sizer.Add(self.code_desc_text, 0, wx.EXPAND|wx.ALL, 5)
    self.code_editor = wx.py.editwindow.EditWindow(self.code_panel)
    self.code_editor.setDisplayLineNumbers(True)
    self.code_sizer.Add(self.code_editor, 1, wx.EXPAND|wx.ALL, 5)
    self.code_error_text = wx.StaticText(self.code_panel, -1, "", style=wx.LEFT)
    self.code_error_text.SetBackgroundColour(wx.Colour(0xFF,0xCD,0xD2))
    self.code_sizer.Add(self.code_error_text, 0, wx.EXPAND|wx.ALL, 5)
    self.code_run_button = wx.Button(self.code_panel, -1, "Зберегти та перевірити", size=(200,40))
    self.code_run_button.SetFont(top_text_font)
    self.Bind(wx.EVT_BUTTON, self.run_selected_task, self.code_run_button)
    self.code_sizer.Add(self.code_run_button, 0, wx.CENTER|wx.ALL, 5)
    self.code_html_description = wx.html.HtmlWindow(self.code_panel, -1)
    self.code_html_description.Hide()
    self.code_sizer.Add(self.code_html_description, 1, wx.EXPAND|wx.ALL, 5)
    self.code_panel.SetSizer(self.code_sizer)


    self.results_image_list = wx.ImageList(16,16)
    self.results_image_list.Add(img_question_mark)
    self.results_image_list.Add(img_success)
    self.results_image_list.Add(img_failure)
    self.results_image_list.Add(img_error)
    
    self.results_panel = wx.Panel(self.splitter)
    self.results_sizer = wx.BoxSizer(wx.VERTICAL)
    self.results_top_text = wx.StaticText(self.results_panel, -1, "Перевір завдання", style=wx.ALIGN_CENTER)
    self.results_top_text.SetFont(top_text_font)
    self.results_sizer.Add(self.results_top_text, 0, flag=wx.EXPAND)
    self.results_tree_ctrl = wx.TreeCtrl(self.results_panel, style=wx.TR_HAS_BUTTONS | wx.BORDER_NONE | wx.TR_HIDE_ROOT | wx.TR_LINES_AT_ROOT)    
    self.results_tree_ctrl.AssignImageList(self.results_image_list)
    self.results_sizer.Add(self.results_tree_ctrl, 1, flag=wx.EXPAND)
    self.results_panel.SetSizer(self.results_sizer)


    self.splitter.SetMinimumPaneSize(200)

    self.splitter.AppendWindow(self.task_tree_panel, 300)
    self.splitter.AppendWindow(self.code_panel, 600)
    self.splitter.AppendWindow(self.results_panel, 200)

    self.code_error_text.Hide()

    self.current_user = "user"
    self.selected_task_item_id = None
    self.selected_task = None
    self.selected_task_initial_code = None

    self.Bind(wx.EVT_CLOSE, self.on_close)
   
  def clear_frame(self):
    self.code_name_text.SetLabel("")
    self.code_desc_text.SetLabel("")
    self.code_editor.SetValue("")
    self.hide_error()
    self.results_tree_ctrl.DeleteAllItems()
    self.save_item.Enable(False)
    self.selected_task_initial_code = None

  def show_error(self, message):
    self.code_error_text.Show(True)
    self.code_error_text.SetLabel(message)
    self.code_error_text.Wrap(self.splitter.GetSashPosition(1) - 5)
    self.code_panel.Layout()

  def hide_error(self):
    self.code_error_text.SetLabel("")
    self.code_error_text.Hide()
    self.code_panel.Layout()

  def hide_task_controls(self):
    self.code_desc_text.Hide()
    self.code_editor.Hide()
    self.code_error_text.SetLabel("")
    self.code_error_text.Hide()
    self.code_run_button.Hide()
    self.code_html_description.Show()
    self.code_panel.Layout()

  def show_task_controls(self):
    self.code_desc_text.Show()
    self.code_editor.Show()
    self.code_run_button.Show()
    self.code_html_description.Hide()
    self.code_panel.Layout()


  def get_image_by_status(self, status):
    if status == "Пройдено": return 1
    elif status == "Не пройдено": return 2
    elif status == "Помилка": return 3
    return 0

  def refresh_task_tree(self):
    self.task_tree_ctrl.DeleteAllItems()
    root_id = self.task_tree_ctrl.AddRoot("root")
    for i, category in enumerate(sorted(set(list(map(lambda x: x["Категорія"], self.all_tasks))))):
      cat_no = category.split(".")[0].strip()
      cat_id = self.task_tree_ctrl.AppendItem(root_id, category)
      category_hash = list(filter(lambda x: x["name"] == cat_no, self.all_categories))[0]
      if category_hash: category_hash["Назва"] = category
      self.task_tree_ctrl.SetItemData(cat_id, category_hash)
      self.task_tree_ctrl.SetItemBold(cat_id)
      self.task_tree_ctrl.SetItemHasChildren(cat_id, True)

      for j, task in enumerate(list(filter(lambda x: x["Категорія"] == category, self.all_tasks))):
        task_node_id = self.task_tree_ctrl.AppendItem(cat_id, task["Назва"])
        self.task_tree_ctrl.SetItemData(task_node_id, task)
        self.task_tree_ctrl.SetItemImage(task_node_id, self.get_image_by_status(task.get("Статус")))

    
      self.task_tree_ctrl.Expand(cat_id)

  def refresh_results_tree(self):
    self.hide_error()
    self.results_tree_ctrl.DeleteAllItems()
    root_id = self.results_tree_ctrl.AddRoot("root")
    if self.selected_task["Тести"]:
      for i, test in enumerate(self.selected_task["Тести"]):
        test_id = self.results_tree_ctrl.AppendItem(root_id, "Перевірка № {0}".format(i+1))
        self.results_tree_ctrl.SetItemHasChildren(test_id, True)
        self.results_tree_ctrl.AppendItem(test_id, "Вхідні дані: {0}".format(" ".join(test["Вхід"])))
        self.results_tree_ctrl.AppendItem(test_id, "Очікую: {0}".format(test["Вихід"]))
        if test.get("Отримано"): self.results_tree_ctrl.AppendItem(test_id, "Отримано: {0}".format(test["Отримано"]))
        
        if test.get("Статус"): 
          self.results_tree_ctrl.AppendItem(test_id, "Статус: {0}".format(test["Статус"]))     
          if test.get("Статус") == "Помилка": 
            self.show_error(test.get("Повідомлення"))

        self.task_tree_ctrl.SetItemImage(test_id, self.get_image_by_status(test.get("Статус")))

        self.results_tree_ctrl.Expand(test_id)


  def refresh_selected_task(self):
    self.Freeze()
    if self.selected_task and self.selected_task.get("is_task"):
      self.code_name_text.SetLabel(self.selected_task.get("Назва"))
      self.code_desc_text.SetLabel(self.selected_task.get("Опис"))
      self.code_desc_text.Wrap(self.splitter.GetSashPosition(1) - 5)
      self.code_editor.SetValue(load_code(self.selected_task["name"], self.current_user))
      self.selected_task_initial_code = self.code_editor.GetValue()
      self.show_task_controls()
      self.code_panel.Layout()
      self.refresh_results_tree()
      self.task_tree_ctrl.SetItemImage(self.selected_task_item_id, self.get_image_by_status(self.selected_task.get("Статус")))
      self.save_item.Enable(True)
    elif self.selected_task:
      self.clear_frame()
      self.code_name_text.SetLabel(self.selected_task.get("Назва"))
      self.code_html_description.SetPage(self.selected_task.get("Опис"))
      self.hide_task_controls()
    else: self.clear_frame()
    self.Thaw()

  def task_tree_sel_changed(self, evt):
    if (self.selected_task and self.selected_task.get("is_task") and 
        self.selected_task_initial_code != self.code_editor.GetValue()):
      dlg = wx.MessageDialog(None, "До коду завдання \"{0}\" було внесено зміни. Зберегти їх?".format(self.selected_task["Назва"]), "Підтверження", wx.YES_NO)
      dlg.SetYesNoLabels('Так', 'Ні')
      retCode = dlg.ShowModal()
      dlg.Destroy()
      if (retCode == wx.ID_YES):
        code = self.code_editor.GetValue()
        save_code(self.selected_task["name"], self.current_user, code)
        run_task(self.selected_task, self.current_user, code)
        self.refresh_selected_task()

    self.selected_task_item_id = self.task_tree_ctrl.GetSelection()
    self.selected_task = self.task_tree_ctrl.GetItemData(self.selected_task_item_id)
    self.refresh_selected_task()

  def run_selected_task(self, evt):
    code = self.code_editor.GetValue()
    save_code(self.selected_task["name"], self.current_user, code)
    run_task(self.selected_task, self.current_user, code)
    self.refresh_selected_task()

  def on_menu_save(self, evt):
    code = self.code_editor.GetValue()
    save_code(self.selected_task["name"], self.current_user, code)
    run_task(self.selected_task, self.current_user, code)
    self.refresh_selected_task()

  def on_menu_logout(self, evt):
    dlg = wx.MessageDialog(None, "Завершити сеанс?", "Підтверження", wx.YES_NO)
    dlg.SetYesNoLabels('Так', 'Ні')
    retCode = dlg.ShowModal()
    dlg.Destroy()
    if (retCode == wx.ID_YES):
      login_frame.surname_text.SetValue("")
      login_frame.name_text.SetValue("")
      login_frame.class_text.SetValue("")
      login_frame.progress_lbl.Hide()
      login_frame.login_btn.Show()
      login_frame.Centre()
      self.Hide()
      login_frame.Show()
    
  def on_menu_quit(self, evt):
    dlg = wx.MessageDialog(None, "Завершити програму?", "Підтверження", wx.YES_NO)
    dlg.SetYesNoLabels('Так', 'Ні')
    retCode = dlg.ShowModal()
    dlg.Destroy()
    if (retCode == wx.ID_YES):
      login_frame.Destroy()
      self.Destroy()

  def on_menu_create_review(self, evt):
    dlg = AddReviewDialog(self, -1, style=(wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER) ^ wx.MAXIMIZE_BOX ^ wx.MINIMIZE_BOX)
    dlg.Centre()
    dlg.ShowModal()
    dlg.Destroy()

  def on_menu_show_reviews(self, evt):
    dlg = ReviewsDialog(self, -1, style=(wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER) ^ wx.MAXIMIZE_BOX ^ wx.MINIMIZE_BOX)
    reviews = list(reversed(load_reviews()))
    page = "\n".join(
      list(
        map(
          lambda x: "{0} користувач <b>{1}</b> залишив відгук: <pre>{2}</pre><hr/>".format(x["Час"], x["Користувач"], x["Відгук"].replace("<","&lt;").replace(">","&gt;")),
          reviews
        )
      )
    )
    dlg.reviews.SetPage(page)
    dlg.Centre()
    dlg.ShowModal()
    dlg.Destroy()

  def on_menu_about(self, evt):
    dlg = AboutDialog(self, -1, style=(wx.DEFAULT_FRAME_STYLE ) ^ wx.MAXIMIZE_BOX ^ wx.MINIMIZE_BOX ^ wx.RESIZE_BORDER)
    dlg.Centre()
    dlg.ShowModal()
    dlg.Destroy()

  def on_close(self, event):
    login_frame.Destroy()
    self.Destroy()


class LoginFrame(wx.Frame):
  def __init__(self):
    wx.Frame.__init__(self, None, -1, "Python Тренажер - Вхід", size=(400, 250), style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER ^ wx.MAXIMIZE_BOX)
    self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
    self.panel = wx.Panel(self, -1)
    self.hsizer.Add(self.panel, 1, wx.EXPAND)
    img1 = wx.Image(r"images/welcome.png", wx.BITMAP_TYPE_PNG)
    self.bitmap = wx.StaticBitmap(self, -1, wx.Bitmap(img1))
    self.hsizer.Add(self.bitmap, 0, wx.CENTER)

    self.vsizer = wx.BoxSizer(wx.VERTICAL)
    self.surname_lbl = wx.StaticText(self.panel, -1, "Прізвище:", style=wx.LEFT)
    self.vsizer.Add(self.surname_lbl, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 7)
    self.surname_text = wx.TextCtrl(self.panel, -1)
    self.Bind(wx.EVT_TEXT, self.text_changed, self.surname_text)
    self.vsizer.Add(self.surname_text, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 7)

    self.name_lbl = wx.StaticText(self.panel, -1, "Ім'я:", style=wx.LEFT)
    self.vsizer.Add(self.name_lbl, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 7)
    self.name_text = wx.TextCtrl(self.panel, -1)
    self.Bind(wx.EVT_TEXT, self.text_changed, self.name_text)
    self.vsizer.Add(self.name_text, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 7)

    self.class_lbl = wx.StaticText(self.panel, -1, "Клас:", style=wx.LEFT)
    self.vsizer.Add(self.class_lbl, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 7)
    self.class_text = wx.TextCtrl(self.panel, -1)
    self.Bind(wx.EVT_TEXT, self.text_changed, self.class_text)
    self.vsizer.Add(self.class_text, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 7)

    self.login_btn = wx.Button(self.panel, -1, "Увійти до тренажеру", size =(200, 40))
    self.Bind(wx.EVT_BUTTON, self.on_login, self.login_btn)
    self.vsizer.Add(self.login_btn, 0, wx.CENTER|wx.ALL, 20)
    self.login_btn.Enable(False)

    self.progress_lbl = wx.StaticText(self.panel, -1, "Завантажую завдання", style=wx.LEFT)
    self.vsizer.Add(self.progress_lbl, 0, wx.CENTER|wx.ALL, 20)

    self.Bind(wx.EVT_CLOSE, self.on_close)

    self.panel.SetSizer(self.vsizer)

    self.SetSizer(self.hsizer)

    self.progress_lbl.Hide()


  def text_changed(self, evt):
    self.login_btn.Enable((len(self.surname_text.GetValue().strip()) > 0 and
      len(self.name_text.GetValue().strip()) > 0 and
      len(self.class_text.GetValue().strip()) > 0) or
      (self.surname_text.GetValue().strip() == "user" and
       self.name_text.GetValue().strip() == "" and
       self.class_text.GetValue().strip() == ""))

  def on_login(self, evt):
    login_name = None
    current_user = None
    if (self.surname_text.GetValue().strip() == "user" and
       self.name_text.GetValue().strip() == "" and
       self.class_text.GetValue().strip() == ""):
      login_name = "user"
      current_user = "user"       
    else:
      login_name = (self.name_text.GetValue().strip().upper() + " " +
        self.surname_text.GetValue().strip().upper() + " " +
        self.class_text.GetValue().strip().upper())
      current_user = hashlib.md5(login_name.encode('utf-8')).hexdigest()

    main_frame.Freeze()

    self.login_btn.Hide()
    self.progress_lbl.SetLabel("Завантажую завдання")
    self.progress_lbl.Show()
    self.Layout()
    self.Update()

    all_categories = load_categories()

    all_tasks = load_tasks()

    self.progress_lbl.SetLabel("Виконую завдання")
    self.Layout()
    self.Update()

    run_tasks(self, all_tasks, current_user)
    main_frame.all_categories = all_categories
    main_frame.all_tasks = all_tasks
    main_frame.current_user = current_user
    main_frame.current_login = login_name
    main_frame.refresh_task_tree()
    main_frame.SetTitle("Python Тренажер - {0}".format(login_name))
    main_frame.Thaw()
    login_frame.Hide()
    main_frame.Centre()
    main_frame.Show()
    append_log(main_frame.current_login, main_frame.current_user, "Successful login")

  def on_close(self, event):
    main_frame.Destroy()
    self.Destroy()

class AddReviewDialog(wx.Dialog):
  def __init__(self, *args, **kw):
    super(AddReviewDialog, self).__init__(*args, **kw)

    self.vsizer = wx.BoxSizer(wx.VERTICAL)
    self.panel = wx.Panel(self, -1)

    self.review = wx.TextCtrl(self.panel, -1, style=wx.TE_MULTILINE)
    self.vsizer.Add(self.review, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)

    self.vsizer.Add(wx.StaticLine(self.panel, -1), 0, wx.EXPAND|wx.TOP, 10)

    self.close_button = wx.Button(self.panel, -1, "Додати відгук")
    self.vsizer.Add(self.close_button, 0, wx.ALIGN_CENTER|wx.ALL, 10)
    self.Bind(wx.EVT_BUTTON, self.on_close, self.close_button)

    self.panel.SetSizer(self.vsizer)

    self.SetSize((600, 400))
    self.SetTitle("Створення відгуку")

  def on_close(self, evt):
    text = str(self.review.GetValue()).strip()
    if text: add_review(main_frame.current_login, text)
    self.Destroy()

    
class ReviewsDialog(wx.Dialog):
  def __init__(self, *args, **kw):
    super(ReviewsDialog, self).__init__(*args, **kw)

    self.vsizer = wx.BoxSizer(wx.VERTICAL)
    self.panel = wx.Panel(self, -1)

    self.reviews = wx.html.HtmlWindow(self.panel, -1)
    self.vsizer.Add(self.reviews, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)

    self.vsizer.Add(wx.StaticLine(self.panel, -1), 0, wx.EXPAND|wx.TOP, 10)

    self.close_button = wx.Button(self.panel, -1, "Закрити")
    self.vsizer.Add(self.close_button, 0, wx.ALIGN_CENTER|wx.ALL, 10)
    self.Bind(wx.EVT_BUTTON, self.on_close, self.close_button)

    self.panel.SetSizer(self.vsizer)

    self.SetSize((800, 600))
    self.SetTitle("Перегляд відгуків")

  def on_close(self, evt):
    self.Destroy()


class AboutDialog(wx.Dialog):
  def __init__(self, *args, **kw):
    super(AboutDialog, self).__init__(*args, **kw)

    soft_name_font = wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD)
    soft_link_font = wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD)

    self.vsizer = wx.BoxSizer(wx.VERTICAL)
    self.panel = wx.Panel(self, -1)
    self.soft_name_lbl = wx.StaticText(self.panel, -1, "Python Тренажер 1.0", style=wx.ALIGN_CENTER)
    self.soft_name_lbl.SetFont(soft_name_font)
    self.vsizer.Add(self.soft_name_lbl, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
    self.copyright_lbl = wx.StaticText(self.panel, -1, "Copyright \xA9 2023 Пруднікова Ольга", style=wx.ALIGN_CENTER)
    self.vsizer.Add(self.copyright_lbl, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
    self.about_lbl = wx.StaticText(self.panel, -1, "Python Тренажер - освітній програмний продукт, що впроваджує підхід автоматизованого тестування до тренувальних вправ здобувачів освіти.", style=wx.ALIGN_CENTER)
    self.about_lbl.Wrap(400)
    self.vsizer.Add(self.about_lbl, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 10)

    self.link_ctrl = wx.adv.HyperlinkCtrl(self.panel, -1, "https://www.github.com", "https://www.github.com", style=wx.ALIGN_CENTER)
    self.link_ctrl.SetFont(soft_link_font)
    self.vsizer.Add(self.link_ctrl, 0, wx.ALL|wx.ALIGN_CENTER, 10)

    self.license_text = wx.html.HtmlWindow(self.panel, -1)
    self.license_text.SetPage("""<p>Copyright &copy; 2023 Пруднікова Ольга</p>
<p>Безоплатно надається дозвіл будь-якій особі, що отримала копію цього програмного забезпечення та супутньої документації (надалі "Програмне забезпечення"), застосовувати Програмне забезпечення без обмежень, включно без обмежень прав на використання, копіювання, редагування, доповнення, публікацію, поширення, субліцензування та / або продаж копій Програмного забезпечення, також як і особам, яким надається це Програмне забезпечення, за дотримання наступних умов:</p>
<p>Вищезгадані авторські права та ці умови мають бути включені в усі копії або значущі частини цього Програмного забезпечення.</p>
<p>ЦЕ ПРОГРАМНЕ ЗАБЕЗПЕЧЕННЯ НАДАЄТЬСЯ «ЯК Є», БЕЗ ГАРАНТІЙ БУДЬ-ЯКОГО ВИДУ, ПРЯМИХ АБО НЕПРЯМИХ, ВКЛЮЧАЮЧИ, АЛЕ НЕ ОБМЕЖУЮЧИСЬ, ГАРАНТІЯМИ КОМЕРЦІЙНОЇ ВИГОДИ, ВІДПОВІДНОСТІ ЙОГО КОНКРЕТНОМУ ПРИЗНАЧЕННЮ Й ВІДСУТНОСТІ ПОРУШЕННЯ ПРАВ. У ЖОДНОМУ РАЗІ АВТОРИ АБО ВЛАСНИКИ АВТОРСЬКИХ ПРАВ НЕ ВІДПОВІДАЮТЬ ЗА БУДЬ-ЯКИМИ СУДОВИМИ ПОЗОВАМИ, ЩОДО ЗБИТКІВ АБО ІНШИХ ПРЕТЕНЗІЙ, ЧИ ДІЙ ДОГОВОРУ, ЦИВІЛЬНОГО ПРАВОПОРУШЕННЯ АБО ІНШИХ, ЩО ВИНИКАЮТЬ ПОЗА, АБО У ЗВ'ЯЗКУ З ПРОГРАМНИМ ЗАБЕЗПЕЧЕННЯМ АБО ВИКОРИСТАННЯМ ЧИ ІНШИМИ ДІЯМИ ПРОГРАМНОГО ЗАБЕЗПЕЧЕННЯ.</p>""")
    self.vsizer.Add(self.license_text, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)


    self.vsizer.Add(wx.StaticLine(self.panel, -1), 0, wx.EXPAND|wx.TOP, 10)

    self.close_button = wx.Button(self.panel, -1, "Закрити")
    self.vsizer.Add(self.close_button, 0, wx.ALIGN_CENTER|wx.ALL, 10)
    self.Bind(wx.EVT_BUTTON, self.on_close, self.close_button)

    self.panel.SetSizer(self.vsizer)

    self.SetSize((450, 400))
    self.SetTitle("Про програму")

  def on_close(self, evt):
    self.Destroy()




app = wx.App()
login_frame = LoginFrame()
main_frame = MainFrame()
login_frame.SetIcon(wx.Icon("images/python.png", wx.BITMAP_TYPE_PNG))
main_frame.SetIcon(wx.Icon("images/python.png", wx.BITMAP_TYPE_PNG))
login_frame.Centre()
login_frame.Show()
main_frame.Centre()
app.SetTopWindow(login_frame)
app.MainLoop()

