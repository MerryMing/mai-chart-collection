import sys
import os
import difflib
import itertools
import re
import platform

# ================= 配置区域 =================
# 这里是默认备用路径，仅当用户直接回车不输入时使用
DEFAULT_PATH_A = "maidata_old.txt"
DEFAULT_PATH_B = "maidata_new.txt"
# ===========================================

def enable_windows_ansi_support():
    """
    在 Windows 系统上开启 ANSI 颜色支持。
    """
    if platform.system() != "Windows":
        return
    import ctypes
    STD_OUTPUT_HANDLE = -11
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    try:
        kernel32 = ctypes.windll.kernel32
        hOut = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        dwMode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(hOut, ctypes.byref(dwMode)):
            return
        dwMode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(hOut, dwMode)
    except Exception:
        pass

enable_windows_ansi_support()

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'

def normalize_slide_note(note):
    """处理 Slide 路径顺序 (*连接部分)"""
    if '*' not in note:
        return note
    parts = note.split('*')
    first_part = parts[0]
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
    """处理逗号分隔的片段 (BPM/分音 + 多押排序 + Slide排序)"""
    segment = segment.strip()
    if not segment: return ""
    
    match = re.match(r"^(\{.*?\})(.*)$", segment)
    prefix = ""
    content = segment
    if match:
        prefix = match.group(1)
        content = match.group(2)
    
    if content:
        notes = content.split('/')
        processed_notes = []
        for n in notes:
            clean_n = n.strip()
            norm_n = normalize_slide_note(clean_n)
            processed_notes.append(norm_n)
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
    return ','.join([normalize_simai_segment(seg) for seg in segments])

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
    # 简单的路径清理
    file_a_path = file_a_path.strip().strip('"').strip("'")
    file_b_path = file_b_path.strip().strip('"').strip("'")

    if not os.path.exists(file_a_path):
        print(f"{Colors.RED}错误: 找不到文件 A -> {file_a_path}{Colors.RESET}")
        return
    if not os.path.exists(file_b_path):
        print(f"{Colors.RED}错误: 找不到文件 B -> {file_b_path}{Colors.RESET}")
        return

    def read_file(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return f.readlines()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='gb18030') as f: return f.readlines()
        except Exception as e:
            print(f"读取文件失败: {e}")
            return []

    lines_a = read_file(file_a_path)
    lines_b = read_file(file_b_path)

    print(f"\n正在对比:")
    print(f" A: {Colors.YELLOW}{file_a_path}{Colors.RESET}")
    print(f" B: {Colors.YELLOW}{file_b_path}{Colors.RESET}\n")
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
            print(f"  文件A: {display_a if raw_a else '(空)'}")
            print(f"  文件B: {display_b if raw_b else '(空)'}")
            print("-" * 40)

    print("=" * 60)
    if diff_count == 0:
        print(f"{Colors.GREEN}完全一致！{Colors.RESET} (已忽略等价的乱序字符)")
    else:
        print(f"对比完成，共发现 {Colors.RED}{diff_count}{Colors.RESET} 处实质性差异。")
    
    # 交互模式下暂停，防止窗口直接关闭
    if len(sys.argv) < 3:
        input("\n按回车键退出...")

def get_user_input_path(prompt_text, default_val):
    """获取用户输入，如果直接回车则使用默认值"""
    path = input(prompt_text).strip()
    # 去除拖拽文件可能产生的引号
    path = path.strip('"').strip("'")
    if not path:
        return default_val
    return path

if __name__ == "__main__":
    # 检查是否传入了命令行参数
    if len(sys.argv) >= 3:
        path_a = sys.argv[1]
        path_b = sys.argv[2]
        compare_files(path_a, path_b)
    else:
        print(f"{Colors.CYAN}=== Simai 谱面差异对比工具 ==={Colors.RESET}")
        print("提示: 您可以直接将文件拖入窗口来输入路径。\n")
        
        path_a = get_user_input_path(f"请输入旧文件(File A)路径 [默认: {DEFAULT_PATH_A}]: ", DEFAULT_PATH_A)
        path_b = get_user_input_path(f"请输入新文件(File B)路径 [默认: {DEFAULT_PATH_B}]: ", DEFAULT_PATH_B)
        
        compare_files(path_a, path_b)
