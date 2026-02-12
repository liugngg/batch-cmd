import os
import shutil
import json
import time
import subprocess
import threading
import re
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, Menu, font
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
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Microsoft YaHei", size=10, weight="normal")
        
        # 核心变量
        self.video_exts = ('.mp4', '.mkv', '.mov', '.avi', '.mpeg', '.mpg', '.wmv', '.m2ts', '.webm', '.flv')
        self.audio_exts = ('.mp3', '.aac', '.mka', '.mpa', '.m4a', '.flac', '.wav', '.wma', '.ogg', '.ape')
        self.process_signal = ["frame=", "time=", "speed=", "正在处理视频："]
        
        self.is_running = False
        self.current_process = None 
        self.last_log_is_progress = False
        
        self.new_console_var = ttkb.BooleanVar(value=True)
        self.recursive_var = ttkb.BooleanVar(value=False)
        self.shutdown_var = ttkb.BooleanVar(value=False)
        self.overwrite_var = ttkb.StringVar(value="skip") 
        self.output_path_var = ttkb.StringVar(value="默认使用输入文件所在目录")

        self.pattern_pitch = re.compile(r"(?<=rubberband=pitch=)([-]?\d+)")
        self.pattern_name = re.compile(r'[\S]*?\{name\}[\S]*')
        self.pattern_input = re.compile(r'-i\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))')
        self.pattern_output = re.compile(r'(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
        
        self.setup_ui()
        self.create_context_menu()
        self.load_presets()
        self.register_dnd()

    def setup_ui(self):
        main_frame = ttkb.Frame(self.root, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)
        style = ttkb.Style()

        # --- 1. 输入输出设置 ---
        self.input_output = ttkb.LabelFrame(main_frame, text="输入输出设置")
        self.input_output.pack(fill=BOTH, expand=YES, pady=5)

        input_tab = ttkb.Frame(self.input_output, padding=10)
        input_tab.pack(fill=BOTH, expand=YES)
        
        in_btn_frame = ttkb.Frame(input_tab)
        in_btn_frame.pack(fill=X, pady=(0, 5))
        ttkb.Button(in_btn_frame, text="🎬 添加文件", command=self.add_files, bootstyle="primary-link").pack(side=LEFT, padx=5)
        ttkb.Button(in_btn_frame, text="📂 添加文件夹", command=self.add_folder, bootstyle="warning-link").pack(side=LEFT, padx=5)
        
        style.configure("MyColor.TCheckbutton", foreground="seagreen")
        ttkb.Checkbutton(in_btn_frame, text="递归子目录", variable=self.recursive_var, style="MyColor.TCheckbutton").pack(side=LEFT, padx=10)
        ttkb.Button(in_btn_frame, text="清空列表", command=self.clear_tree_items, bootstyle="danger-link", width=8).pack(side=RIGHT, padx=0)

        # 文件列表
        tree_container = ttkb.Frame(input_tab)
        tree_container.pack(fill=BOTH, expand=YES)

        style.configure("Treeview", font=("Microsoft YaHei", 10), rowheight=30)
        style.configure("Treeview.Heading", font=("Microsoft YaHei", 9, "bold"))

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
        
        # 绑定右键菜单
        self.tree.bind("<Button-3>", self.show_context_menu)
        # 绑定Del键
        self.tree.bind("<Delete>", self.clear_tree_items)

        # 配置Tree Tag：设置前景色为红色
        self.tree.tag_configure("red_tag", foreground="red")

        hbar = ttkb.Scrollbar(tree_container, orient=HORIZONTAL, bootstyle="primary")
        self.tree.configure(xscrollcommand=hbar.set)
        hbar.configure(command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky=NSEW)
        hbar.grid(row=1, column=0, sticky=EW)
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        output_tab = ttkb.Frame(self.input_output, padding=5)
        output_tab.pack(fill=X, expand=YES)
        ttkb.Entry(output_tab, textvariable=self.output_path_var, bootstyle="light", width=40, state="readonly").pack(side=LEFT, padx=(5,0)) 
        ttkb.Button(output_tab, text="🔍输出目录", command=self.browse_output, bootstyle="primary-link").pack(side=LEFT, padx=0) 
        ttkb.Button(output_tab, text="📂打开输出", command=self.open_output_folder, bootstyle="primary-link").pack(side=LEFT, padx=(0,20))
        
        ttkb.Radiobutton(output_tab, text="强制覆盖", variable=self.overwrite_var, bootstyle="info", value="overwrite").pack(side=RIGHT, padx=5)
        ttkb.Radiobutton(output_tab, text="跳过", variable=self.overwrite_var, bootstyle="info", value="skip").pack(side=RIGHT, padx=5)
        ttkb.Label(output_tab, text="同名处理:").pack(side=RIGHT, padx=(5,5))

        # --- 2. 命令编辑区 ---
        cmd_frame = ttkb.LabelFrame(main_frame, text="批量执行的命令", bootstyle="success", padding=5)
        cmd_frame.pack(fill=X, pady=10)

        preset_row = ttkb.Frame(cmd_frame)
        preset_row.pack(fill=X, pady=5)
        ttkb.Label(preset_row, text="选择预设:", bootstyle="primary").pack(side=LEFT, padx=0)
        self.preset_combo = ttkb.Combobox(preset_row, bootstyle="primary", state="readonly", width=25)
        self.preset_combo.pack(side=LEFT, padx=(5,0))
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_change)
        ttkb.Button(preset_row, text="⚒️ 编 辑", command=self.edit_preset, bootstyle="dark-link").pack(side=LEFT, padx=(0,10))
        
        ttkb.Button(preset_row, text="💾 保 存", command=self.save_preset, bootstyle="warning-link").pack(side=RIGHT, padx=(0,5))
        self.preset_name_entry = ttkb.Entry(preset_row, bootstyle="primary", width=25)
        self.preset_name_entry.pack(side=RIGHT)
        ttkb.Label(preset_row, text="另存预设:", bootstyle="primary").pack(side=RIGHT, padx=0)

        self.cmd_text = ttkb.Text(cmd_frame, height=4, font=("Consolas", 11), foreground="blue")
        self.cmd_text.pack(fill=X, pady=5)
        self.cmd_text.insert(END, "ffmpeg -i {input} -c:v libx265 -preset medium -cq 16 -c:a copy {name}_done.mp4")
        ttkb.Label(cmd_frame, text="输入：{input}； 输出：{name}=原名, {ext}=原后缀", font=("Microsoft YaHei", 9)).pack(side=LEFT)

        # 运行控制排
        button_f = ttkb.Frame(main_frame)
        button_f.pack(fill=X, pady=5)
        ttkb.Button(button_f, text="🗑清空日志", command=self.clear_logs, bootstyle="warning-link").pack(side=LEFT)
        ttkb.Checkbutton(button_f, text="新输出窗口", variable=self.new_console_var, style="MyColor.TCheckbutton").pack(side=LEFT, padx=(40,10))
        ttkb.Checkbutton(button_f, text="完成后关机", variable=self.shutdown_var, style="MyColor.TCheckbutton").pack(side=LEFT, padx=10)  
        
        self.start_btn = ttkb.Button(button_f, text="💪 开始批处理", command=self.batch_process, bootstyle=SUCCESS, width=15)
        self.start_btn.pack(side=RIGHT, padx=(5,15))
        self.merge_btn = ttkb.Button(button_f, text="🔗 合并输入", command=self.merge_process, bootstyle="info", width=15)
        self.merge_btn.pack(side=RIGHT, padx=10) 

        self.log_area = ttkb.ScrolledText(main_frame, height=5, state=DISABLED, font=("Consolas", 9))
        self.log_area.pack(fill=BOTH, expand=YES, pady=0)
        self.log_area.tag_configure("信息", foreground="#8f0a74")
        self.log_area.tag_configure("进展", foreground="#059803")
        self.log_area.tag_configure("结果", foreground="#059803")
        self.log_area.tag_configure("错误", foreground="#e74c3c")
        self.log_area.tag_configure("命令", foreground="#043E64")

        status_f = ttkb.Frame(main_frame)
        status_f.pack(fill=X, pady=(10,0))
        self.progress = ttkb.Progressbar(status_f, bootstyle="success")
        self.progress.pack(side=LEFT, fill=X, expand=YES, padx=(0,5))
        self.status_lbl = ttkb.Label(status_f, text="就绪", anchor=E, width=20)
        self.status_lbl.pack(side=RIGHT)

    # --- 核心控制逻辑 ---
    def get_media_info(self, file_path):
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            data = json.loads(result.stdout)
            f = data.get('format', {})
            streams = data.get('streams', [])
            size = f"{int(f.get('size', 0)) / (1024*1024):.2f} MB"
            dur = time.strftime('%H:%M:%S', time.gmtime(float(f.get('duration', 0))))
            v_codec = v_br = a_codec = a_br = a_sr = v_w = v_h = v_pf = "N/A"
            for s in streams:
                br = f"{int(s.get('bit_rate', 0)) // 1000}k" if s.get('bit_rate') else "N/A"
                if s.get('codec_type') == 'video':
                    v_codec, v_br, v_w, v_h, v_pf = s.get('codec_name'), br, s.get('width'), s.get('height'), s.get('pix_fmt')
                elif s.get('codec_type') == 'audio':
                    a_codec, a_br, a_sr = s.get('codec_name'), br, s.get('sample_rate')
            return size, dur, v_codec, v_br, a_codec, a_br, a_sr, v_w, v_h, v_pf
        except: return ("Error",) * 10

    def check_compatibility(self, file_list):
        if not file_list: return False
        base = self.get_media_info(file_list[0])
        for i in range(1, len(file_list)):
            curr = self.get_media_info(file_list[i])
            if base[2] != "N/A": # 视频
                if any(base[k] != curr[k] for k in [2, 7, 8, 9]): return False
            else: # 纯音频
                if any(base[k] != curr[k] for k in [4, 6]): return False
        return True

    def kill_process_tree(self):
        """强制杀死当前进程及其子进程"""
        if self.current_process:
            try:
                # /F 强制 /T 杀死子进程
                subprocess.run(f"taskkill /F /T /PID {self.current_process.pid}", shell=True, capture_output=True)
            except Exception as e:
                print(f"终止进程失败: {e}")
            finally:
                self.current_process = None

    def stop_all_tasks(self, task_type="batch"):
        """用户点击终止时的处理"""
        if not self.is_running:
            return
        
        if messagebox.askyesno("确认", "确定要强制终止当前任务吗？"):
            self.is_running = False
            self.kill_process_tree()
            time.sleep(1)
            self.reset_ui_states()
            self.log("🛑 任务已被手动终止！", "错误")

    def reset_ui_states(self):
        """重置按钮和状态栏文字"""
        self.start_btn.configure(text="💪 开始批处理", bootstyle="success")
        self.merge_btn.configure(text="🔗 合并输入", bootstyle="info")
        self.status_lbl.configure(text="任务已停止")

    def batch_process(self):
        """批处理按钮分发"""
        if self.is_running:
            self.stop_all_tasks("batch")
            return
        
        cmd_tpl = self.cmd_text.get("1.0", END).splitlines(False)[0].strip()
        # windows 环境下，CMD 不把单引号当作路径包裹符，需要替换为双引号：
        cmd_tpl = cmd_tpl.replace("'", '"')
        # 如果文件路径中不包含{input}，则从命令行中获取输入文件路径
        if "{input}" not in cmd_tpl:
            match = re.search(self.pattern_input, cmd_tpl)
            if match:
                input_path = match.group(1) or match.group(2) or match.group(3)
                input_path = os.path.abspath(input_path.strip())
                if os.path.exists(input_path):
                    # 由于没有使用{input}，则清空列表：
                    for item in self.tree.get_children(): self.tree.delete(item)
                    self.output_path_var.set("默认使用输入文件所在目录")
                    self.add_to_list(input_path)

        if not self.tree.get_children():
            messagebox.showwarning("警告", "输入文件列表为空！\n请先添加文件或从命令行中输入")
            return
            
        self.is_running = True
        self.start_btn.configure(text="⏹️ 终止任务", bootstyle="danger")
        self.save_log("批处理任务开始", first_time=True)
        threading.Thread(target=self.run_worker, args=(cmd_tpl,), daemon=True).start()

    def run_worker(self, cmd_tpl):
        # 预处理音调
        def chang_pitch(match):
            try:
                return "{:.4f}".format(2**(int(match.group(1))/12))
            except: return match.group(1) 
        
        cmd_tpl = re.sub(self.pattern_pitch, chang_pitch, cmd_tpl)
        items = self.tree.get_children()
        files_total = len(items)
        processed_count = failed_count = skip_count = 0
        total_processing_time = timedelta(0)
        output_dir_base = self.output_path_var.get()

        # 切换当前工作路径（cwd）到命令所在目录
        cwd_path = os.path.dirname(shutil.which(cmd_tpl.split()[0]))
        self.root.after(0, self.log, f"命令文件路径: {cwd_path}", "信息")

        for i, item in enumerate(items):
            if not self.is_running: break # 检查停止信号
            
            in_path = self.tree.item(item)['values'][-1]
            fname = os.path.basename(in_path)
            name_only, ext = os.path.splitext(fname)
            # 确定输入路径
            final_cmd = cmd_tpl.replace("{input}", f'"{in_path}"')

            # 确定输出路径
            out_dir = os.path.dirname(in_path) if output_dir_base == "默认使用输入文件所在目录" else output_dir_base
            full_out = os.path.join(out_dir, f"{name_only}_done{ext}")
            
            # 解析输出名
            search_name = re.findall(self.pattern_name, cmd_tpl)
            # 如何命令行中存在输出模板{name}
            if search_name:
                out_fname = search_name[0].replace("{name}", name_only).replace("{ext}", ext)
                full_out = os.path.join(out_dir, out_fname)
                final_cmd = re.sub(self.pattern_name, lambda m :f'"{full_out}"', final_cmd)
            else:    # 使用命令行中指定的输出名称
                match = re.search(self.pattern_output, cmd_tpl)
                if match:
                    out = match.group(1) or match.group(2) or match.group(3)
                    out = out.strip()
                    if os.path.dirname(out):
                        out_dir = os.path.dirname(out)
                    full_out = os.path.join(out_dir, os.path.basename(out))
                    final_cmd = final_cmd.replace(out, f'{full_out}')
                    

            if not os.path.exists(out_dir): os.makedirs(out_dir)
            # self.root.after(0, self.log, f"输出文件名：\n{full_out}", "信息")

            if os.path.exists(full_out) and self.overwrite_var.get() == "skip":
                self.root.after(0, self.log, f"跳过已存在文件: {fname}", "信息")
                skip_count += 1
                self.root.after(0, self.update_status, i+1, files_total)
                continue

            start_time = datetime.now()
            self.root.after(0, self.log, f"第{i+1}/{files_total}个启动: {fname}", "信息")
            self.hightlight_treerow(item)

            try:
                # 启动进程
                if self.new_console_var.get():
                    # 新窗口模式：无法捕获输出，只能等待
                    self.root.after(0, self.log, f"执行命令：\n{final_cmd}", "信息")
                    self.current_process = subprocess.Popen(final_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=cwd_path)
                    while self.is_running and self.current_process.poll() is None: time.sleep(1)
                else:
                    # 捕获输出模式
                    self.current_process = subprocess.Popen(
                        final_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd_path,
                        text=True, encoding='gbk', errors='replace'
                    )
                    while self.is_running:
                        line = self.current_process.stdout.readline()
                        if self.current_process.poll() is not None:
                            break
                        if line:
                            self.root.after(0, self.log, line.strip(), "命令")

                if self.is_running and self.current_process and self.current_process.returncode == 0:
                    processed_count += 1
                elif self.is_running:
                    failed_count += 1
            except Exception as e:
                self.root.after(0, self.log, f"处理异常: {e}", "错误")
                failed_count += 1
            finally:
                self.hightlight_treerow(item, False)
            
            if not self.is_running: break

            duration = datetime.now() - start_time
            total_processing_time += duration
            self.root.after(0, self.update_status, i+1, files_total)

        # 任务总结
        if self.is_running:
            self.root.after(0, self.log, f"========= 处理总结 =========\n成功:{processed_count} 跳过:{skip_count} 失败:{failed_count}\n耗时:{total_processing_time}", "结果")
            if self.shutdown_var.get(): os.system("shutdown /s /t 60")
            
        self.is_running = False
        self.root.after(0, self.reset_ui_states)

    def merge_process(self):
        """合并按钮分发"""
        if self.is_running:
            self.stop_all_tasks("merge")
            return
        if len(self.tree.get_children()) < 2: 
            messagebox.showwarning("警告", "文件数不足2个，无法合并！")
            return
        
        self.is_running = True
        self.merge_btn.configure(text="⏹️ 停止合并", bootstyle="danger")
        threading.Thread(target=self.merge_worker, daemon=True).start()

    def merge_worker(self):
        file_lst = [self.tree.item(item, 'values')[-1] for item in self.tree.get_children()]
        out_dir = self.output_path_var.get()
        if out_dir == "默认使用输入文件所在目录":
            out_dir = os.path.dirname(file_lst[0])
        
        if not self.check_compatibility(file_lst):
            self.root.after(0, self.log, "编码参数不一致，无法合并", "错误")
            self.is_running = False
            self.root.after(0, self.reset_ui_states)
            return

        list_file = os.path.join(out_dir, 'files_to_merge.txt')
        with open(list_file, 'w', encoding='utf-8') as f:
            for file in file_lst: f.write(f"file '{file}'\n")
        
        out_name = os.path.join(out_dir, f"{os.path.splitext(os.path.basename(file_lst[0]))[0]}_merged{os.path.splitext(file_lst[0])[1]}")
        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', out_name]
        
        try:
            self.current_process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            # 采用轮询的方式获取进程状态
            while self.is_running and self.current_process.poll() is None: time.sleep(1)
            
            if self.is_running and self.current_process.returncode == 0:
                self.root.after(0, self.log, f"合并成功: {out_name}", "信息")
        except Exception as e:
            self.root.after(0, self.log, f"合并失败: {e}", "错误")
        finally:
            if os.path.exists(list_file): os.remove(list_file)
            self.is_running = False
            self.root.after(0, self.reset_ui_states)

    def add_to_list(self, *paths):
        exts = tuple(ext.lower() for ext in (set(self.video_exts) | set(self.audio_exts)))
        existing = {self.tree.item(item)['values'][-1] for item in self.tree.get_children()}
        for path in paths:
            if os.path.isdir(path):
                for root_dir, _, files in (os.walk(path) if self.recursive_var.get() else [(path, None, os.listdir(path))]):
                    for f in files:
                        full_p = os.path.join(root_dir, f)
                        if f.lower().endswith(exts) and full_p not in existing:
                            info = self.get_media_info(full_p)
                            self.tree.insert("", "end", values=(f, *info[:6], full_p))
                            existing.add(full_p)
            elif os.path.isfile(path) and path.lower().endswith(exts) and path not in existing:
                info = self.get_media_info(path)
                self.tree.insert("", "end", values=(os.path.basename(path), *info[:6], path))

    def clear_tree_items(self, event=None):
        # 删除选中的项目
        if self.tree.selection():
            for item in self.tree.selection(): self.tree.delete(item)
        # 如何没有选择的项目，则清空列表
        else:
            for item in self.tree.get_children(): self.tree.delete(item)
            self.output_path_var.set("默认使用输入文件所在目录")

    def hightlight_treerow(self, item, is_set=True):
        if not self.tree.exists(item): return 
        if(is_set):
            old_tag = list(self.tree.item(item, "tags"))
            if "red_tag" not in old_tag:
                new_tag = old_tag + ["red_tag"]
            self.tree.item(item, tags=new_tag)
        else:
            old_tag = list(self.tree.item(item, "tags"))
            if "red_tag" in old_tag:
                new_tag = [tag for tag in old_tag if tag != "red_tag"]
            self.tree.item(item, tags=new_tag)

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("媒体文件", self.video_exts + self.audio_exts), ("所有文件", "*.*")])
        self.add_to_list(*files)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if folder: self.add_to_list(folder)

    def browse_output(self):
        p = filedialog.askdirectory()
        if p: self.output_path_var.set(p)

    def open_output_folder(self):
        p = self.output_path_var.get()
        if p == "默认使用输入文件所在目录" and self.tree.get_children():
            p = os.path.dirname(self.tree.item(self.tree.get_children()[0])['values'][-1])
        if os.path.exists(p): os.startfile(p)

    def register_dnd(self):
        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind('<<Drop>>', lambda e: self.add_to_list(*[p.strip('{}') for p in re.findall(r'\{.*?\}|\S+', e.data)]))

    def create_context_menu(self):
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🔼 上移", command=self.move_up)
        self.context_menu.add_command(label="🔽 下移", command=self.move_down)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ 移除(Del)", command=self.clear_tree_items)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def move_up(self):
        items = self.tree.selection()
        for item in items:
            idx = self.tree.index(item)
            if idx > 0:
                self.tree.move(item, '', idx - 1)
    def move_down(self):
        items = self.tree.selection()
        # 反转处理，保证连续选中的项移动正常
        for item in reversed(items):
            idx = self.tree.index(item)
            if idx < len(self.tree.get_children()) - 1:
                self.tree.move(item, '', idx + 1)

    def load_presets(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.preset_combo['values'] = list(json.load(f).keys())
            except: pass

    def on_preset_change(self, e):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cmd = json.load(f).get(self.preset_combo.get(), "")
            self.cmd_text.delete("1.0", END)
            self.cmd_text.insert(END, cmd)

    def save_preset(self):
        name, cmd = self.preset_name_entry.get().strip(), self.cmd_text.get("1.0", END).strip()
        if not name or not cmd: return
        presets = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: presets = json.load(f)
        presets[name] = cmd
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(presets, f, indent=4, ensure_ascii=False)
        self.load_presets()
        messagebox.showinfo("成功", f"预设 '{name}' 已保存")

    def edit_preset(self):
        if os.path.exists(CONFIG_FILE): subprocess.Popen(['notepad.exe', CONFIG_FILE])

    def clear_logs(self):
        self.log_area.configure(state=NORMAL)
        self.log_area.delete("1.0", END)
        self.log_area.configure(state=DISABLED)

    # --- 通用辅助方法 ---
    def log(self, message, level="命令"):
        self.log_area.configure(state=NORMAL)
        is_progress = any(sig in message for sig in self.process_signal)
        
        if is_progress and self.last_log_is_progress:
            self.log_area.delete("end-2c linestart", "end-1c")
        
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.insert(END, f"[{ts}] {message}\n", level if not is_progress else "进展")
        self.last_log_is_progress = is_progress
        self.log_area.see(END)
        self.log_area.configure(state=DISABLED)
        if level != "命令" and not is_progress: self.save_log(message)

    def save_log(self, content, first_time=False):
        try:
            out_dir = self.output_path_var.get()
            if out_dir == "默认使用输入文件所在目录":
                if not self.tree.get_children(): return
                out_dir = os.path.dirname(self.tree.item(self.tree.get_children()[0])['values'][-1])
            if not os.path.exists(out_dir): os.makedirs(out_dir)
            
            log_file = os.path.join(out_dir, "batch_cmd.log")
            mode = "w" if first_time else "a"
            with open(log_file, mode, encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%m-%d %H:%M:%S')}] {content}\n")
        except: pass

    def update_status(self, current, total):
        pct = (current / total) * 100
        self.progress.configure(value=pct)
        self.status_lbl.configure(text=f"进度: {current}/{total} ({pct:.1f}%)")


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = BatchProcessorApp(root)
    root.mainloop()
