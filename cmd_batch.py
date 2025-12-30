import os
import json
import time
import subprocess
import threading
import re
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, Menu,font
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from tkinterdnd2 import DND_FILES, TkinterDnD

# 配置文件
CONFIG_FILE = "cmd_presets.json"

class BatchProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("智能批处理工具--liug")
        self.root.geometry("800x700")
        
        self.style = ttkb.Style(theme="cosmo")
        # 1. 获取系统默认字体的对象
        default_font = font.nametofont("TkDefaultFont")
        # 2. 修改字体的具体属性
        default_font.configure(family="Microsoft YaHei", size=10, weight="normal")
        
        # 核心变量
        # 支持的文件格式
        self.video_exts = ('.mp4', '.mkv', '.avi', '.mpeg', '.mpg', '.wmv')
        self.audio_exts = ('.mp3', '.aac', '.mka', '.mpa', '.flac', '.wav', '.wma', '.ogg', '.ape')
        self.process_signal= ["frame=", "time=", "正在处理视频："]
        self.is_running = False
        self.current_process = None 
        self.recursive_var = ttkb.BooleanVar(value=False)
        self.shutdown_var = ttkb.BooleanVar(value=False)
        self.overwrite_var = ttkb.StringVar(value="skip") 
        self.output_path_var = ttkb.StringVar(value="")
        self.use_own_dir = True
        self.pattern_pitch = re.compile(r"(?<=rubberband=pitch=)([-]?\d+)")
        self.pattern_name = re.compile(r'[\S]*?\{name\}[\S]*')
        
        self.setup_ui()
        self.create_context_menu()
        self.load_presets()
        self.register_dnd()

    def setup_ui(self):

        main_frame = ttkb.Frame(self.root, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)
        # 创建 Style 对象
        style = ttkb.Style()

        # --- 1. 顶部标签页 (输入/输出设置) ---
        self.input_output = ttkb.LabelFrame(main_frame, text="输入输出设置", style="info")
        self.input_output.pack(fill=BOTH, expand=YES, pady=5)

        # 标签页 1: 输入设置
        input_tab = ttkb.Frame(self.input_output, padding=10)
        input_tab.pack(fill=BOTH, expand=YES)
        
        in_btn_frame = ttkb.Frame(input_tab)
        in_btn_frame.pack(fill=X, pady=(0, 10))
        ttkb.Button(in_btn_frame, text="🎬 添加文件", command=self.add_files, bootstyle="primary-link").pack(side=LEFT, padx=5)
        ttkb.Button(in_btn_frame, text="📂 添加文件夹", command=self.add_folder, bootstyle="warning-link").pack(side=LEFT, padx=5)
        style.configure("MyColor.TCheckbutton", foreground="seagreen")
        ttkb.Checkbutton(in_btn_frame, text="递归子目录", variable=self.recursive_var, style="MyColor.TCheckbutton").pack(side=LEFT, padx=10)
        ttkb.Button(in_btn_frame, text="清空列表", command=self.clear_list, bootstyle="danger-link",width=8).pack(side=RIGHT, padx=0)

        # 文件列表框：
        tree_container = ttkb.Frame(input_tab)
        tree_container.pack(fill=BOTH, expand=YES)

        # 2. 配置 Treeview 的字体（表格内部内容）
        # 注意：'Treeview' 是组件的样式名
        style.configure(
            "Treeview",
            font=("Microsoft YaHei", 10),     # 设置字体和大小
            rowheight=30,
            bootstyle="primary"                                  # 重要：根据字体大小调整行高
        )
        # 3. 配置 Treeview.Heading 的字体（表头）
        style.configure(
            "Treeview.Heading",
            font=("Microsoft YaHei", 9, "bold"), # 设置表头字体、大小和加粗
        )

        columns = ("name", "size", "duration", "v_codec", "v_bitrate", "a_codec", "a_bitrate", "path")
        self.tree = ttkb.Treeview(tree_container, columns=columns, show='headings', height=4, bootstyle="primary")
        col_map = {
            "name": ("文件名", 200), "size": ("大小", 80), "duration": ("时长", 80),
            "v_codec": ("视频编码", 70), "v_bitrate": ("视频码率", 70),
            "a_codec": ("音频编码", 70), "a_bitrate": ("音频码率", 70), "path": ("全路径", 300)
        }
        for col, (text, width) in col_map.items():
            self.tree.heading(col, text=text, anchor=W)
            self.tree.column(col, width=width, anchor=W)
        self.tree.bind("<Button-3>", self.show_context_menu)
        # 增加水平滚动条
        hbar = ttkb.Scrollbar(tree_container, orient=HORIZONTAL, bootstyle="primary")
        # 双向绑定
        self.tree.configure(xscrollcommand=hbar.set)
        hbar.configure(command=self.tree.xview)

        # 采用 grid 布局
        self.tree.grid(row=0, column=0, sticky=NSEW)
        hbar.grid(row=1, column=0, sticky=EW)
        # 设置权重，应对扩展
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        output_tab = ttkb.Frame(self.input_output, padding=5)
        output_tab.pack(fill=X, expand=YES)
        # ttkb.Label(output_tab, text="输出目录:",bootstyle="primary").pack(side=LEFT)
        ttkb.Button(output_tab, text="🔍 输出目录：", command=self.browse_output, bootstyle="primary-link").pack(side=LEFT,padx=0)
        ttkb.Entry(output_tab, textvariable=self.output_path_var,bootstyle="light", state="readonly").pack(side=LEFT, fill=X, expand=YES, padx=(5,40))        

        ttkb.Radiobutton(output_tab, text="强制覆盖", variable=self.overwrite_var, bootstyle="info", value="overwrite").pack(side=RIGHT, padx=5)
        ttkb.Radiobutton(output_tab, text="跳过", variable=self.overwrite_var, bootstyle="info",value="skip").pack(side=RIGHT, padx=5)
        ttkb.Label(output_tab, text="同名处理:").pack(side=RIGHT, padx=(5,5))


        # --- 2. 命令编辑区 (常驻) ---
        cmd_frame = ttkb.LabelFrame(main_frame, text="执行命令",bootstyle="warning",padding=5)
        cmd_frame.pack(fill=X, pady=10)

        preset_row = ttkb.Frame(cmd_frame)
        preset_row.pack(fill=X, pady=5)
        ttkb.Label(preset_row, text="选择预设:", bootstyle="primary").pack(side=LEFT, padx=0)
        self.preset_combo = ttkb.Combobox(preset_row, bootstyle="primary",state="readonly",width=25)
        self.preset_combo.pack(side=LEFT, padx=(5,0))
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_change)
        ttkb.Button(preset_row, text="⚒️ 编 辑", command=self.edit_preset, bootstyle="dark-link", width=10,padding=0).pack(side=LEFT, padx=(0,10))
    
        
        ttkb.Button(preset_row, text="💾 保 存", command=self.save_preset, bootstyle="warning-link", width=10,padding=0).pack(side=RIGHT, padx=(0,5))
        self.preset_name_entry = ttkb.Entry(preset_row, bootstyle="primary",width=30)
        self.preset_name_entry.pack(side=RIGHT)
        ttkb.Label(preset_row, text="另存预设:", bootstyle="primary").pack(side=RIGHT, padx=0)

        self.cmd_text = ttkb.Text(cmd_frame, height=4, font=("Consolas", 11))
        self.cmd_text.configure(foreground="blue")
        self.cmd_text.pack(fill=X, pady=5)
        self.cmd_text.insert(END, "ffmpeg -i {input} -c:v hevc_nvenc -preset p4 -cq 16 -c:a copy {name}_done.mp4")
        ttkb.Label(cmd_frame, text="输入文件名：{input}；      输出文件名：{name}=原名, {ext}=原后缀", font=("Microsoft YaHei", 9)).pack(fill=X, padx=(5,5))


        button_f = ttkb.Frame(main_frame)
        button_f.pack(fill=X, pady=5)
        self.start_btn = ttkb.Button(button_f, text="💪 开始批处理", command=self.start_process, bootstyle=SUCCESS, width=15, padding=3)
        self.start_btn.pack(side=RIGHT, padx=(5,15))

        self.stop_btn = ttkb.Button(button_f, text="⏹️ 终止任务", command=self.stop_process, bootstyle=DANGER, width=12, state=DISABLED)
        # self.stop_btn.pack(side=RIGHT, padx=5)
        
        self.open_output = ttkb.Button(button_f, text="📂 打开输出目录", command=self.open_output_folder, bootstyle="primary-link")
        self.open_output.pack(side=RIGHT, padx=5)

        ttkb.Checkbutton(button_f, text="完成后关机", variable=self.shutdown_var, style="MyColor.TCheckbutton", width=15).pack(side=RIGHT, padx=(5,5))
        ttkb.Button(button_f, text="🗑清空日志", command=self.clear_logs, bootstyle="warning-link").pack(side=LEFT)

        # 日志工具栏
        self.log_area = ttkb.ScrolledText(main_frame, height=5, state=DISABLED, font=("Consolas", 9))
        self.log_area.pack(fill=BOTH, expand=YES, pady=0)
        
        # 定义日志标签颜色
        self.log_area.tag_configure("信息", foreground="#8f0a74")
        self.log_area.tag_configure("进展", foreground="#6b0693")
        self.log_area.tag_configure("结果", foreground="#059803")
        self.log_area.tag_configure("错误", foreground="#e74c3c")
        self.log_area.tag_configure("命令", foreground="#043E64")

        # 底部进度条及状态
        status_f = ttkb.Frame(main_frame)
        status_f.pack(fill=X, pady=(10,0))
        status_f.columnconfigure(0, weight=1)  
        self.progress = ttkb.Progressbar(status_f, bootstyle="success")
        self.progress.grid(row=0, column=0, sticky=EW, padx=(0,5))
        
        self.status_lbl = ttkb.Label(status_f, text="就绪", anchor=E, width=20)
        self.status_lbl.grid(row=0, column=1, sticky=E, padx=(5,0))
        

    # --- 日志与路径操作 ---
    def clear_logs(self):
        """清空日志框"""
        self.log_area.configure(state=NORMAL)
        self.log_area.delete("1.0", END)
        self.log_area.configure(state=DISABLED)

    def save_log(self, content, first_time=False):
        """将当前日志保存到输出目录"""
        out_dir = self.output_path_var.get()
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        log_file = os.path.join(out_dir, f"batch_cmd.log")
    
        timestamp = datetime.now().strftime("%m-%d %H:%M:%S")      
        try:
            if first_time:
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {content}")
                    # self.log_area.insert(END, f"日志保存至：\n{log_file}", "信息")
            else:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n[{timestamp}] {content}")
            
        except Exception as e:
            self.log_area.insert(END, f"无法保存日志：{e}", "错误")

    def open_output_folder(self):
        """打开输出文件夹"""
        path = self.output_path_var.get()
        if os.path.exists(path):
            os.startfile(path) # Windows 特有
        else:
            messagebox.showwarning("警告", "输出目录尚不存在")

    # --- 任务控制逻辑 ---
    def stop_process(self):
        if not self.is_running: 
            self.start_btn.configure(text="💪 开始批处理", command=self.start_process, bootstyle="success", width=12)
            return
        if messagebox.askyesno("确认", "确定要强制终止当前任务并停止队列吗？"):
            self.is_running = False
            if self.current_process:
                try:
                    # Windows下彻底杀死进程树
                    subprocess.run(f"taskkill /F /T /PID {self.current_process.pid}", shell=True, capture_output=True)
                except:
                    self.current_process.terminate()
            self.log("🛑 任务已被用户手动终止！", "错误")
            self.start_btn.configure(text="💪 开始批处理", command=self.start_process, bootstyle="success", width=12)

    def log(self, message, level="命令"):
        self.log_area.configure(state=NORMAL)
        # 识别是否为 FFmpeg 进度行
        is_progress_line = False
        for id in self.process_signal:
            if id in message:
                is_progress_line = True
                break
        
        if is_progress_line and self.last_log_is_progress:
            # 如果上一行也是进度，删除最后一行 (从倒数第二字符开始所在的行首，到结尾)
            self.log_area.delete("end-2c linestart", "end-1c")
        
        timestamp = datetime.now().strftime("%m-%d %H:%M:%S")   
        
        # 插入新内容
        if is_progress_line:
            self.log_area.insert(END, f"[{timestamp}] {message.strip()}\n", "进展")
            self.last_log_is_progress = True
        else:
            self.log_area.insert(END, f"[{timestamp}] {message.strip()}\n", level)
            # 保存日志到文件
            if level != "命令":
                self.save_log(message.strip())
            self.last_log_is_progress = False

        self.log_area.see(END)
        self.log_area.configure(state=DISABLED)

    # --- 右键菜单 ---
    def create_context_menu(self):
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="上移文件 ▲", command=lambda: self.move_item(-1))
        self.context_menu.add_command(label="下移文件 ▼", command=lambda: self.move_item(1))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="移出列表 ❌", command=self.delete_selected, foreground="red")

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    # --- 媒体信息与列表管理 ---
    def get_media_info(self, file_path):
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            data = json.loads(result.stdout)
            f = data.get('format', {})
            streams = data.get('streams', [])
            size = f"{int(f.get('size', 0)) / (1024*1024):.2f} MB"
            dur = time.strftime('%H:%M:%S', time.gmtime(float(f.get('duration', 0))))
            v_codec, v_br, a_codec, a_br = "N/A", "N/A", "N/A", "N/A"
            for s in streams:
                br = f"{int(s.get('bit_rate', 0)) // 1000}k" if s.get('bit_rate') else "N/A"
                if s.get('codec_type') == 'video':
                    v_codec, v_br = s.get('codec_name', 'unknown'), br
                elif s.get('codec_type') == 'audio':
                    a_codec, a_br = s.get('codec_name', 'unknown'), br
            return size, dur, v_codec, v_br, a_codec, a_br
        except:
            return "Error", "N/A", "N/A", "N/A", "N/A", "N/A"

    def move_item(self, direction):
        selected = self.tree.selection()
        if not selected: return
        for item in selected:
            idx = self.tree.index(item)
            self.tree.move(item, '', idx + direction)

    def delete_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)

    def add_to_list(self, *paths):
        if not paths: return
        files_input = []
        supported_exts = list(self.video_exts).extend(list(self.audio_exts))
        for path in paths:
            # 如果路径是文件夹，则递归或直接遍历其下的文件
            if os.path.isdir(path):
                if self.recursive_var.get():
                    # 递归模式
                    for root_dir, _, files in os.walk(path):
                        for f in files:
                            if f.lower().endswith(supported_exts):
                                files_input.append(os.path.join(root_dir, f))
                else:
                    # 非递归模式，只看当前层级
                    for f in os.listdir(path):
                        full_p = os.path.join(path, f)
                        if os.path.isfile(full_p) and f.lower().endswith(supported_exts):
                            files_input.append(full_p)
            else:   # 单文件
                if os.path.isfile(path) and path.lower().endswith(supported_exts):
                    files_input.append(path)
        
        # 检查文件列表框里是否已存在
        files_in_list = [self.tree.item(item)['values'][-1] for item in self.tree.get_children()]
        seen = set(files_in_list)
        new_paths = []
        for path in files_input:
            if path not in seen:
                new_paths.append(path)
                seen.add(path)

        """更新文件列表 Treeview"""
        # 清空现有内容
        for i in self.tree.get_children():
            self.tree.delete(i)

        # 重新插入数据
        for file in seen:  
            info = self.get_media_info(file)
            self.tree.insert("", END, values=(os.path.basename(file), *info, file))
    def add_to_list(self, *paths):
        if not paths:
            return
        # 1. 修复 extend 返回 None 的 Bug，并转换为 tuple (endswith 接受 tuple 效率更高)
        # 使用 set 去重并预处理为小写
        supported_exts = tuple(ext.lower() for ext in (set(self.video_exts) | set(self.audio_exts)))
        # 2. 获取当前 Treeview 中已有的路径，避免重复处理
        # 假设路径存储在最后一列
        existing_paths = {self.tree.item(item)['values'][-1] for item in self.tree.get_children()}
        
        new_files_to_add = []
        def is_supported(filename):
            return filename.lower().endswith(supported_exts)
        
        # 3. 收集新增文件
        for path in paths:
            if os.path.isdir(path):
                if self.recursive_var.get():
                    # 递归模式：使用 os.walk
                    for root_dir, _, files in os.walk(path):
                        for f in files:
                            full_p = os.path.join(root_dir, f)
                            if is_supported(f) and full_p not in existing_paths:
                                new_files_to_add.append(full_p)
                                existing_paths.add(full_p) # 防止本次添加中出现重复
                else:
                    # 非递归模式：使用 os.scandir 性能比 listdir 更好
                    with os.scandir(path) as it:
                        for entry in it:
                            if entry.is_file() and is_supported(entry.name) and entry.path not in existing_paths:
                                new_files_to_add.append(entry.path)
                                existing_paths.add(entry.path)
            elif os.path.isfile(path):
                if is_supported(path) and path not in existing_paths:
                    new_files_to_add.append(path)
                    existing_paths.add(path)
        # 4. 增量更新 Treeview (不要清空现有内容)
        # 这样可以避免对旧文件重复执行耗时的 get_media_info
        for file_path in new_files_to_add:
            try:
                info = self.get_media_info(file_path)
                # 插入新行
                self.tree.insert(
                    "", 
                    "end", 
                    values=(os.path.basename(file_path), *info, file_path)
                )
            except Exception as e:
                print(f"解析媒体信息失败: {file_path}, 错误: {e}")

    def clear_list(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.output_path_var.set("")

    def add_files(self):
        filetypes = [("视频文件", self.video_exts),("音频文件", self.audio_exts), ("所有文件", "*.*")]
        files = filedialog.askopenfilenames(
            title="选择多媒体文件",
            filetypes=filetypes
        )
        self.add_to_list(*files)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.add_to_list(folder)

    def browse_output(self):
        p = filedialog.askdirectory()
        if p: 
            self.output_path_var.set(p)
            self.use_own_dir = False

    def register_dnd(self):
        self.tree.drop_target_register(DND_FILES)
        # self.tree.dnd_bind('<<Drop>>', lambda e: [self.add_to_list(p.strip('{}')) for p in re.findall(r'\{.*?\}|\S+', e.data)])
        self.tree.dnd_bind('<<Drop>>', self.on_files_drop)
    
    def on_files_drop(self, event):
        paths = [p.strip('{}') for p in re.findall(r'\{.*?\}|\S+', event.data)]
        self.add_to_list(*paths)

    # --- 预设逻辑 ---
    def save_preset(self):
        name = self.preset_name_entry.get().strip()
        cmd = self.cmd_text.get("1.0", END).strip()
        if not name or not cmd: return
        presets = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: presets = json.load(f)
        presets[name] = cmd
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(presets, f, indent=4, ensure_ascii=False)
        self.load_presets()
        messagebox.showinfo("成功", f"预设 '{name}' 已保存")

    def load_presets(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    presets = json.load(f)
                    self.preset_combo['values'] = list(presets.keys())
            except: pass

    def on_preset_change(self, event):
        name = self.preset_combo.get()
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            presets = json.load(f)
            self.cmd_text.delete("1.0", END)
            self.cmd_text.insert(END, presets.get(name, ""))

    def edit_preset(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    subprocess.Popen(['notepad.exe', CONFIG_FILE])
            except:
                messagebox.showwarning("警告", "无法打开配置文件")

        else:
            messagebox.showwarning("警告", "配置文件尚不存在")

    # --- 执行引擎 ---
    def start_process(self):
        items = self.tree.get_children()
        if not items or self.is_running: return
        # 取命令窗口中的第一行
        cmd_tpl = self.cmd_text.get("1.0", END).splitlines(False)[0].strip()
        if "{input}" not in cmd_tpl:
            messagebox.showwarning("警告", "命令模版必须包含 {input}")
            return

        #使用 rubberband 滤镜改变音频音调时，（推荐，音质最好）
        # 将半音数转换为倍率：2^(n/12)  其中 n 为半音数
        def chang_pitch(match):
            try:
                input = int(match.group(1))
                return "{:.4f}".format(2**(input/12))
            except ValueError:
                return match.group(1) 
        
        cmd_tpl = re.sub(self.pattern_pitch, chang_pitch, cmd_tpl)

        self.is_running = True
        self.start_btn.configure(text="⏹️ 终止任务", command=self.stop_process, bootstyle="danger", width=12)
        threading.Thread(target=self.run_worker, args=(cmd_tpl,), daemon=True).start()

    def run_worker(self, cmd_tpl):
        files_list = [self.tree.item(item)['values'][-1] for item in self.tree.get_children()]   
        if not files_list:return

        # 获取输出目录
        output_dir = self.output_path_var.get()
        if not output_dir:
            output_dir = os.path.dirname(files_list[0])
            self.output_path_var.set(output_dir)

        # 获取输出名称模板
        search_name = re.findall(self.pattern_name, cmd_tpl)

        # 清空log文件
        self.save_log("批处理任务开始",first_time=True)
        self.root.after(0, self.log, f"启动命令：\n {cmd_tpl}", "信息")
        self.root.after(0, self.log, "-------------------------------------", "信息")
        
        files_total = len(files_list)
        processed_count = 0
        failed_count = 0
        skip_count = 0
        total_processing_time = timedelta(0)

        # 恢复进度条及状态栏
        self.root.after(0, lambda: self.progress.configure(value=0))
        self.root.after(0, lambda: self.status_lbl.configure(text=f"开始执行: 1/{files_total}"))

        for i, in_path in enumerate(files_list):
            if not self.is_running: break
            
            fname = os.path.basename(in_path)
            name_only, ext = os.path.splitext(fname)
            if search_name: 
                out_fname = search_name[0].replace("{name}", name_only).replace("{ext}", ext)
            else:
                out_fname = f"{name_only}_done{ext}"

            if self.use_own_dir:
                out_dir = os.path.dirname(in_path)
                
            full_out = os.path.join(out_dir, out_fname)

            if os.path.exists(full_out) and self.overwrite_var.get() == "skip":
                self.root.after(0, self.log, f"跳过已存在文件: {fname}", "信息")
                skip_count += 1
                self.update_status(i + 1, files_total)
                continue

            final_cmd = cmd_tpl.replace("{input}", f'"{in_path}"')
            final_cmd = re.sub(self.pattern_name, lambda m :f'"{full_out}"', final_cmd)

            # 1. 记录开始时间
            start_time = datetime.now()
            self.root.after(0, self.log, f"第{i+1}/{files_total}个任务启动: \n{final_cmd}", "信息")

            try:
                self.current_process = subprocess.Popen(
                    final_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='gbk', errors='replace'
                )
                
                for line in iter(self.current_process.stdout.readline, ''):
                    if not self.is_running: break
                    if line.strip():
                        lvl = "错误" if "error" in line.lower() or "failed" in line.lower() else "命令"
                        self.root.after(0, self.log, f" {line.strip()}", lvl)
                
                self.current_process.wait()
                if not self.is_running: break
                
                if self.current_process.returncode == 0:
                    self.root.after(0, self.log, f"第{i+1}/{files_total}个任务成功输出：【{full_out}】", "信息")
                    processed_count += 1
                else:
                    self.root.after(0, self.log, f"第{i+1}/{files_total}个任务处理失败: 【{fname}】", "错误")
                    failed_count += 1
            except Exception as e:
                self.root.after(0, self.log, f"第{i+1}/{files_total}个任务系统错误: {str(e)}", "错误")
                failed_count += 1
            
            # 2. 记录结束时间
            end_time = datetime.now()
            # self.root.after(0, self.log, f"第{i+1}/{files_total}个任务结束 at {end_time.strftime('%Y-%m-%d %H:%M:%S')}", "信息")
    
            # 3. 计算时间差
            duration = end_time - start_time
            total_processing_time += duration
            
            # 4. 格式化输出
            # duration 是一个 timedelta 对象
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.root.after(0, self.log, f"第{i+1}/{files_total}个任务耗时：{hours} 小时 {minutes} 分钟 {seconds} 秒", "信息")
            self.root.after(0, self.log, "-------------------------------------", "信息")
            self.update_status(i + 1, files_total)

        if self.is_running:
            self.root.after(0, self.log, "", "结果")
            self.root.after(0, self.log, "✨ 所有批处理任务已顺利结束", "结果")

        # 显示处理结果
        # duration 是一个 timedelta 对象
        total_seconds = int(total_processing_time.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        self.root.after(0, self.log, "========= 处理总结 =========", "结果")
        self.root.after(0, self.log, f"文件总数：{files_total}", "结果")
        self.root.after(0, self.log, f"成功完成：{processed_count}", "结果")
        self.root.after(0, self.log, f"  已跳过：{skip_count}", "结果")
        self.root.after(0, self.log, f"处理失败：{failed_count}", "结果")
        self.root.after(0, self.log, f"共计耗时：{hours} 小时 {minutes} 分钟 {seconds} 秒", "结果")
        self.root.after(0, self.log, "==========================", "结果")
        
        # 任务完成后关机
        if self.shutdown_var.get() and self.is_running: 
            os.system("shutdown /s /t 60")
        
        self.is_running = False
        self.current_process = None
        self.start_btn.configure(text="💪 开始批处理", command=self.start_process, bootstyle="success", width=12)

    def update_status(self, current, files_total):
        pct = (current / files_total) * 100
        self.root.after(0, lambda: self.progress.configure(value=pct))
        self.root.after(0, lambda: self.status_lbl.configure(text=f"总进度: {current}/{files_total} ({pct:.1f}%)"))

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = BatchProcessorApp(root)
    root.mainloop()
