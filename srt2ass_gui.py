import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

def srt_time_to_ass(srt_time):
    h, m, s_ms = srt_time.split(":")
    s, ms = s_ms.split(",")
    # ASS时间格式为 H:MM:SS.ss，所以毫秒需要除以10
    return f"{int(h)}:{int(m):02d}:{int(s):02d}.{int(ms)//10:02d}"

def parse_available_styles(styles_text):
    """解析用户输入的样式，提取可用的样式名称"""
    style_names = []
    lines = styles_text.split('\n')
    for line in lines:
        if line.strip().startswith('Style:'):
            # 提取样式名称 (Style: 名称,字体,...)
            parts = line.split(',')
            if len(parts) > 0:
                style_name = parts[0].replace('Style:', '').strip()
                style_names.append(style_name)
    return style_names

def get_style_mapping(available_styles):
    """根据可用样式智能映射主要和次要样式"""
    primary_style = "Default"
    secondary_style = "Secondary"

    # 如果用户定义了 Default，优先使用
    if "Default" in available_styles:
        primary_style = "Default"
    elif available_styles:
        primary_style = available_styles[0]  # 使用第一个样式

    # 寻找次要样式
    if "Secondary" in available_styles:
        secondary_style = "Secondary"
    elif len(available_styles) > 1:
        secondary_style = available_styles[1]  # 使用第二个样式
    else:
        secondary_style = primary_style  # 如果只有一个样式，双语都用同一个

    return primary_style, secondary_style

def extract_margin_v_from_style(styles_text, style_name):
    """从用户样式中提取指定样式的 MarginV 值"""
    lines = styles_text.split('\n')
    for line in lines:
        if line.strip().startswith(f'Style: {style_name},'):
            parts = line.split(',')
            if len(parts) >= 22:  # MarginV 是第22个字段 (从0开始计数是21)
                try:
                    return int(parts[21].strip())
                except (ValueError, IndexError):
                    pass
    return None  # 如果找不到，返回 None

def clean_styles_text(styles_text):
    """清理样式文本，移除重复的 Script Info 部分，只保留样式定义"""
    lines = styles_text.split('\n')
    cleaned_lines = []
    in_styles_section = False
    skip_script_info = False

    for line in lines:
        stripped_line = line.strip()

        # 跳过重复的 Script Info 部分
        if stripped_line.startswith('[Script Info]'):
            skip_script_info = True
            continue
        elif stripped_line.startswith('[V4+ Styles]'):
            in_styles_section = True
            skip_script_info = False
            cleaned_lines.append(line)
        elif stripped_line.startswith('[') and not stripped_line.startswith('[V4+ Styles]'):
            in_styles_section = False
            skip_script_info = False
            cleaned_lines.append(line)
        elif not skip_script_info and (in_styles_section or stripped_line.startswith('Style:') or stripped_line.startswith('Format:')):
            cleaned_lines.append(line)
        elif not skip_script_info and not in_styles_section:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)

def convert_srt_to_ass(srt_path, ass_path, styles_text, bilingual, cn_first):
    # 解析用户样式
    available_styles = parse_available_styles(styles_text)
    primary_style, secondary_style = get_style_mapping(available_styles)

    # 提取用户定义的 MarginV 值
    primary_margin_v = extract_margin_v_from_style(styles_text, primary_style)
    secondary_margin_v = extract_margin_v_from_style(styles_text, secondary_style)

    # 如果用户没有定义 MarginV，使用默认值
    if primary_margin_v is None:
        primary_margin_v = 40 if bilingual else 10
    if secondary_margin_v is None:
        secondary_margin_v = 10

    # 清理样式文本
    cleaned_styles = clean_styles_text(styles_text)

    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.read().strip().splitlines()

    events = []
    i = 0
    while i < len(lines):
        if re.match(r"^\d+$", lines[i]): # 匹配序号
            time_line = lines[i+1] # 时间轴
            start, end = time_line.split(" --> ")
            start = srt_time_to_ass(start)
            end = srt_time_to_ass(end)

            # 提取中英文文本行
            text_lines = []
            j = i+2
            while j < len(lines) and lines[j].strip() and not re.match(r"^\d+$", lines[j].strip()) and '-->' not in lines[j]:
                text_lines.append(lines[j])
                j += 1

            if bilingual and len(text_lines) >= 2:
                # 根据 cn_first 决定中文和英文行的顺序
                if cn_first:
                    cn_line_text = text_lines[0].strip()
                    en_line_text = text_lines[1].strip()
                else:
                    en_line_text = text_lines[0].strip()
                    cn_line_text = text_lines[1].strip()

                # 使用动态样式名称和用户定义的 MarginV 值
                if en_line_text:
                    events.append(f"Dialogue: 0,{start},{end},{secondary_style},,0,0,{secondary_margin_v},,{en_line_text.replace('\n', '\\N')}")
                if cn_line_text:
                    events.append(f"Dialogue: 0,{start},{end},{primary_style},,0,0,{primary_margin_v},,{cn_line_text.replace('\n', '\\N')}")
            else:
                # 非双语或不足两行时，只输出一行，使用主要样式
                combined_text = ' '.join(text_lines).strip()
                if combined_text:
                    events.append(f"Dialogue: 0,{start},{end},{primary_style},,0,0,{primary_margin_v},,{combined_text.replace('\n', '\\N')}")

            i = j # 更新主循环索引到下一个字幕块
        else:
            i += 1 # 如果不是序号行，跳过当前行

    # 写入 ASS 文件
    with open(ass_path, 'w', encoding='utf-8-sig') as f: # 使用 utf-8-sig 以确保 BOM，更好地兼容播放器
        f.write("[Script Info]\n")
        f.write("; Script generated by srt_to_ass_gui.py\n")
        f.write("ScriptType: v4.00+\n")
        f.write("PlayResX: 1280\n")
        f.write("PlayResY: 720\n\n")
        f.write(cleaned_styles.strip() + "\n\n")
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for e in events:
            f.write(e + "\n")

# --- GUI 逻辑部分（与你现有脚本保持一致，仅做少量调整） ---
def select_srt_files():
    return filedialog.askopenfilenames(filetypes=[("SRT Files", "*.srt")])

def select_output_dir():
    return filedialog.askdirectory()

def run_conversion():
    srt_files = select_srt_files()
    if not srt_files:
        messagebox.showinfo("提示", "未选择任何SRT文件。")
        return
    output_dir = select_output_dir()
    if not output_dir:
        messagebox.showinfo("提示", "未选择输出目录。")
        return
    
    styles_text = style_text.get("1.0", tk.END).strip()
    if not styles_text:
        messagebox.showwarning("警告", "样式代码为空，将使用默认 ASS 样式。")
        # 如果样式为空，可以提供一个简单的默认样式，或者要求用户粘贴
        styles_text = """[Script Info]
; Script generated by srt_to_ass_gui.py
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,36,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,40,1
Style: Secondary,Arial,24,&H00CCCCCC,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1
"""


    bilingual = bilingual_var.get()
    cn_first = cn_first_var.get()

    log_area.delete("1.0", tk.END) # 清空日志区域
    log_area.insert(tk.END, "开始转换...\n")
    log_area.see(tk.END)
    root.update_idletasks() # 强制更新UI

    processed_count = 0
    for srt_file in srt_files:
        try:
            base_name = os.path.splitext(os.path.basename(srt_file))[0]
            ass_path = os.path.join(output_dir, base_name + ".ass")
            convert_srt_to_ass(srt_file, ass_path, styles_text, bilingual, cn_first)
            log_area.insert(tk.END, f"√ 成功转换: {os.path.basename(srt_file)}\n")
            processed_count += 1
        except Exception as e:
            log_area.insert(tk.END, f"X 转换失败: {os.path.basename(srt_file)} - {e}\n")
            messagebox.showerror("转换错误", f"转换 {os.path.basename(srt_file)} 时发生错误: {e}")
        log_area.see(tk.END)
        root.update_idletasks() # 强制更新UI

    log_area.insert(tk.END, f"\n转换完成！共处理 {len(srt_files)} 个文件，成功 {processed_count} 个。\n")
    log_area.see(tk.END)
    messagebox.showinfo("完成", f"转换完成！共处理 {len(srt_files)} 个文件，成功 {processed_count} 个。")


root = tk.Tk()
root.title("SRT 转 ASS 工具")
root.geometry("700x650") # 调整窗口大小，给日志和样式文本框更多空间

# --- 配置行和列的权重，使其在窗口拉伸时自动调整大小 ---
root.grid_rowconfigure(3, weight=1) # style_text 所在行
root.grid_rowconfigure(6, weight=1) # log_area 所在行
root.grid_columnconfigure(0, weight=1) # 所有控件都在第0列

# --- UI 元素布局 ---
# 顶部控制区域
control_frame = tk.Frame(root, padx=10, pady=5)
control_frame.pack(fill=tk.X, anchor='n')

bilingual_var = tk.BooleanVar(value=True)
cn_first_var = tk.BooleanVar(value=True)

tk.Checkbutton(control_frame, text="双语字幕", variable=bilingual_var).grid(row=0, column=0, sticky='w', padx=5, pady=2)
tk.Checkbutton(control_frame, text="中文在前 (SRT 中)，生成时中文在上", variable=cn_first_var).grid(row=1, column=0, sticky='w', padx=5, pady=2)

# ASS 样式文本框
tk.Label(root, text="ASS 样式 (支持任意样式名称，脚本会自动适配。可复制 Aegisub 中的 [Script Info] 和 [V4+ Styles] 部分):").pack(anchor='w', padx=10, pady=(10,0))
style_text = scrolledtext.ScrolledText(root, width=80, height=15, font=("Courier New", 10))
style_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

# 默认样式代码 (根据你提供的样式)
style_text.insert(tk.END, """[Script Info]
; Script generated by srt_to_ass_gui.py
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,微软雅黑,42,&H00729ccc,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,3.2,0,1,1.8,0,2,10,10,40,1
Style: Secondary,微软雅黑,28,&H00ffffff,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0.8,0,1,2.0,0,2,10,10,10,1
""")


# 转换按钮
convert_button = tk.Button(root, text="选择 SRT 文件并转换", command=run_conversion, font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white")
convert_button.pack(pady=10)

# 日志区域
tk.Label(root, text="转换日志:").pack(anchor='w', padx=10, pady=(0,0))
log_area = scrolledtext.ScrolledText(root, width=80, height=10, font=("Consolas", 9), bg="black", fg="lime green")
log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))


root.mainloop()