import sys
import os
import difflib
import itertools
import re
import platform

# ================= 配置区域 =================
DEFAULT_PATH_A = "maidata_old.txt"
DEFAULT_PATH_B = "maidata_new.txt"
# ===========================================

def enable_windows_ansi_support():
    if platform.system() != "Windows": return
    import ctypes
    STD_OUTPUT_HANDLE = -11
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    try:
        kernel32 = ctypes.windll.kernel32
        hOut = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        dwMode = ctypes.c_ulong()
        kernel32.GetConsoleMode(hOut, ctypes.byref(dwMode))
        dwMode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(hOut, dwMode)
    except: pass

enable_windows_ansi_support()

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'

def normalize_slide_note(note):
    """处理 Slide 路径顺序 (*连接部分)"""
    if '*' not in note: return note
    parts = note.split('*')
    match = re.search(r"([-^v<>pqszwV])", parts[0])
    if not match: return note
    split_index = match.start()
    head = parts[0][:split_index]
    path1 = parts[0][split_index:]
    all_paths = [path1] + parts[1:]
    all_paths.sort()
    return head + '*'.join(all_paths)

def normalize_simai_segment(segment):
    """处理逗号片段: 去除空白 -> 拆分多押 -> 标准化Slide -> 多押排序"""
    segment = segment.strip()
    if not segment: return ""
    match = re.match(r"^(\{.*?\})(.*)$", segment)
    prefix, content = (match.group(1), match.group(2)) if match else ("", segment)
    
    if content:
        notes = [normalize_slide_note(n.strip()) for n in content.split('/')]
        notes.sort()
        content = '/'.join(notes)
    return prefix + content

def normalize_simai_line(line):
    line = line.strip()
    if not line or line.startswith('&'): return line
    return ','.join([normalize_simai_segment(s) for s in line.split(',')])

def highlight_line_diff(text_a, text_b):
    """为单行文本生成高亮差异字符串"""
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    out_a, out_b = [], []
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            out_a.append(text_a[a0:a1])
            out_b.append(text_b[b0:b1])
        elif opcode == 'insert':
            out_b.append(Colors.GREEN + text_b[b0:b1] + Colors.RESET)
        elif opcode == 'delete':
            out_a.append(Colors.RED + text_a[a0:a1] + Colors.RESET)
        elif opcode == 'replace':
            out_a.append(Colors.RED + text_a[a0:a1] + Colors.RESET)
            out_b.append(Colors.GREEN + text_b[b0:b1] + Colors.RESET)
    return "".join(out_a), "".join(out_b)

def compare_files(file_a_path, file_b_path):
    # 路径清理
    file_a_path = file_a_path.strip().strip('"').strip("'")
    file_b_path = file_b_path.strip().strip('"').strip("'")

    if not os.path.exists(file_a_path) or not os.path.exists(file_b_path):
        print(f"{Colors.RED}错误: 找不到文件。{Colors.RESET}")
        return

    def read_lines(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return f.readlines()
        except:
            with open(path, 'r', encoding='gb18030') as f: return f.readlines()

    lines_a = read_lines(file_a_path)
    lines_b = read_lines(file_b_path)

    print(f"\n正在对比:\n A: {file_a_path}\n B: {file_b_path}\n" + "-"*60)
    
    # 使用 SequenceMatcher 获取行级别的差异块
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
    diff_count = 0

    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            continue
        
        # 获取这一块涉及的行
        chunk_a = lines_a[a0:a1]
        chunk_b = lines_b[b0:b1]
        
        # === 核心修改逻辑 ===
        # 使用 zip_longest 强制在当前差异块内进行“行对行”的遍历
        # 这样即使 difflib 认为是一大块 replace，我们也会一行一行地打印
        for i, (line_a, line_b) in enumerate(itertools.zip_longest(chunk_a, chunk_b, fillvalue="")):
            
            # 计算真实的行号
            current_line_num_a = a0 + i + 1 if line_a else ""
            
            raw_a = line_a.strip()
            raw_b = line_b.strip()

            # 进行 Simai 语法标准化对比
            norm_a = normalize_simai_line(raw_a)
            norm_b = normalize_simai_line(raw_b)

            # 如果标准化后相同，且不是纯插入/删除的情况，则忽略
            # (处理：虽然被包含在 replace 块里，但可能只有这一行是相同的，或者等价的)
            if norm_a == norm_b and line_a and line_b:
                continue

            diff_count += 1
            
            # 生成高亮
            disp_a, disp_b = highlight_line_diff(raw_a, raw_b)
            
            line_str = f"Line {current_line_num_a}" if current_line_num_a else "插入行"
            print(f"{Colors.CYAN}{line_str}:{Colors.RESET}")
            
            if raw_a: print(f"  A: {disp_a}")
            else:     print(f"  A: (空/不存在)")
            
            if raw_b: print(f"  B: {disp_b}")
            else:     print(f"  B: (空/被删除)")
            
            print("-" * 40)

    print("=" * 60)
    print(f"对比完成，共发现 {Colors.RED}{diff_count}{Colors.RESET} 处实质性差异。")
    
    if len(sys.argv) < 3: input("\n按回车键退出...")

def get_user_input_path(prompt, default_val):
    path = input(prompt).strip().strip('"').strip("'")
    return path if path else default_val

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        compare_files(sys.argv[1], sys.argv[2])
    else:
        print(f"{Colors.CYAN}=== Simai 谱面差异对比工具 (行对行修复版) ==={Colors.RESET}\n")
        pa = get_user_input_path(f"File A [默认: {DEFAULT_PATH_A}]: ", DEFAULT_PATH_A)
        pb = get_user_input_path(f"File B [默认: {DEFAULT_PATH_B}]: ", DEFAULT_PATH_B)
        compare_files(pa, pb)
