import sys
import os
import difflib
import itertools
import re
import platform

# ================= 配置区域 =================
FILE_PATH_A = "maidata_old.txt"
FILE_PATH_B = "maidata_new.txt"
# ===========================================

def enable_windows_ansi_support():
    """
    在 Windows 系统上开启 ANSI 颜色支持。
    不需要安装第三方库，使用 ctypes 调用 Windows API。
    """
    if platform.system() != "Windows":
        return

    # 引入 ctypes
    import ctypes
    
    # Windows API 常量
    STD_OUTPUT_HANDLE = -11
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    try:
        kernel32 = ctypes.windll.kernel32
        # 获取标准输出句柄
        hOut = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        
        # 获取当前控制台模式
        dwMode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(hOut, ctypes.byref(dwMode)):
            return

        # 设置新模式：开启虚拟终端处理
        dwMode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(hOut, dwMode)
    except Exception:
        # 如果设置失败（比如非 Windows 10/11 或权限问题），不做处理
        pass

# 脚本启动时立即尝试开启颜色支持
enable_windows_ansi_support()

class Colors:
    """用于终端输出颜色的类"""
    RESET = '\033[0m'
    RED = '\033[91m'      # 红色
    GREEN = '\033[92m'    # 绿色
    YELLOW = '\033[93m'   # 黄色
    CYAN = '\033[96m'     # 青色

def normalize_slide_note(note):
    """
    处理单个音符内的 Slide 路径顺序问题。
    例如: "1-5[8:1]*-3[8:1]" -> "1-3[8:1]*-5[8:1]"
    """
    if '*' not in note:
        return note

    parts = note.split('*')
    first_part = parts[0]

    # 寻找 Slide 起始符
    match = re.search(r"([-^v<>pqszwV])", first_part)
    
    if not match:
        return note

    split_index = match.start()
    head = first_part[:split_index]
    path1 = first_part[split_index:]
    
    all_paths = [path1] + parts[1:]
    all_paths.sort()
    
    return head + '*'.join(all_paths)

def normalize_simai_segment(segment):
    """
    处理单个逗号分隔的片段
    """
    segment = segment.strip()
    if not segment:
        return ""

    # 提取前缀 {x}
    match = re.match(r"^(\{.*?\})(.*)$", segment)
    prefix = ""
    content = segment

    if match:
        prefix = match.group(1)
        content = match.group(2)
    
    if content:
        # 按 / 分割多押
        notes = content.split('/')
        
        # 对每个音符进行 Slide 路径标准化
        processed_notes = []
        for n in notes:
            clean_n = n.strip()
            norm_n = normalize_slide_note(clean_n)
            processed_notes.append(norm_n)
            
        # 对多押整体进行排序
        processed_notes.sort()
        
        sorted_content = '/'.join(processed_notes)
    else:
        sorted_content = ""

    return prefix + sorted_content

def normalize_simai_line(line):
    line = line.strip()
    if not line: return ""
    if line.startswith('&'): return line

    segments = line.split(',')
    normalized_segments = []

    for seg in segments:
        norm_seg = normalize_simai_segment(seg)
        normalized_segments.append(norm_seg)

    return ','.join(normalized_segments)

def highlight_diff(text_a, text_b):
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    output_a = []
    output_b = []

    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            output_a.append(text_a[a0:a1])
            output_b.append(text_b[b0:b1])
        elif opcode == 'insert':
            output_b.append(Colors.GREEN + text_b[b0:b1] + Colors.RESET)
        elif opcode == 'delete':
            output_a.append(Colors.RED + text_a[a0:a1] + Colors.RESET)
        elif opcode == 'replace':
            output_a.append(Colors.RED + text_a[a0:a1] + Colors.RESET)
            output_b.append(Colors.GREEN + text_b[b0:b1] + Colors.RESET)

    return "".join(output_a), "".join(output_b)

def compare_files(file_a_path, file_b_path):
    if not os.path.exists(file_a_path):
        print(f"错误: 找不到文件 {file_a_path}")
        return
    if not os.path.exists(file_b_path):
        print(f"错误: 找不到文件 {file_b_path}")
        return

    def read_file(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return f.readlines()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='gb18030') as f: return f.readlines()

    lines_a = read_file(file_a_path)
    lines_b = read_file(file_b_path)

    print(f"正在对比:\n A: {file_a_path}\n B: {file_b_path}\n")
    print("-" * 60)

    diff_count = 0
    
    for i, (line_a, line_b) in enumerate(itertools.zip_longest(lines_a, lines_b, fillvalue="")):
        line_num = i + 1
        raw_a = line_a.strip() if line_a else ""
        raw_b = line_b.strip() if line_b else ""

        norm_a = normalize_simai_line(raw_a)
        norm_b = normalize_simai_line(raw_b)

        if norm_a != norm_b:
            diff_count += 1
            display_a, display_b = highlight_diff(raw_a, raw_b)
            
            print(f"{Colors.CYAN}Line {line_num}:{Colors.RESET} 发现差异")
            if not raw_a: print(f"  文件A (空)")
            else: print(f"  文件A: {display_a}")
            
            if not raw_b: print(f"  文件B (空)")
            else: print(f"  文件B: {display_b}")
            print("-" * 40)

    print("=" * 60)
    if diff_count == 0:
        print(f"{Colors.GREEN}完全一致！{Colors.RESET} (已忽略等价的乱序字符)")
    else:
        print(f"对比完成，共发现 {Colors.RED}{diff_count}{Colors.RESET} 处实质性差异。")

if __name__ == "__main__":
    path_a = FILE_PATH_A
    path_b = FILE_PATH_B
    if len(sys.argv) >= 3:
        path_a = sys.argv[1]
        path_b = sys.argv[2]
    compare_files(path_a, path_b)
