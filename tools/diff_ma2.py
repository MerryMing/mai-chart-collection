import sys
import os
import difflib

# 在 Windows 上启用 ANSI 颜色代码支持
os.system('')

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GREY = '\033[90m'

class NoteLine:
    def __init__(self, raw_text, line_num):
        self.raw_text = raw_text.strip()
        self.line_num = line_num
        self.parts = self.raw_text.split()
        
        # 提取小节号 (第二列)
        if len(self.parts) >= 2:
            self.measure = self.parts[1]
        else:
            self.measure = "Unknown"

        # 生成指纹用于精确匹配
        self.fingerprint = "\t".join(self.parts)

    def __repr__(self):
        return f"{self.line_num}: {self.fingerprint}"

def parse_file(file_path):
    """读取文件并按小节号分组"""
    grouped_data = {} 
    
    if not os.path.exists(file_path):
        print(f"{Colors.RED}错误：找不到文件 {file_path}{Colors.RESET}")
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='gbk') as f:
            lines = f.readlines()
            
    for i, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        note = NoteLine(line, i + 1)
        
        if note.measure not in grouped_data:
            grouped_data[note.measure] = []
        grouped_data[note.measure].append(note)
    
    return grouped_data

def highlight_diff_words(parts_a, parts_b):
    """
    对比两个单词列表，返回带颜色的字符串。
    使用 difflib.SequenceMatcher 找出单词级别的差异。
    """
    sm = difflib.SequenceMatcher(None, parts_a, parts_b)
    
    out_a = []
    out_b = []
    
    for opcode, a0, a1, b0, b1 in sm.get_opcodes():
        if opcode == 'equal':
            # 内容相同，保持原色
            segment = " ".join(parts_a[a0:a1])
            out_a.append(segment)
            out_b.append(segment)
        elif opcode == 'replace':
            # 内容被替换：A显示红，B显示绿
            seg_a = " ".join(parts_a[a0:a1])
            seg_b = " ".join(parts_b[b0:b1])
            out_a.append(f"{Colors.RED}{seg_a}{Colors.RESET}")
            out_b.append(f"{Colors.GREEN}{seg_b}{Colors.RESET}")
        elif opcode == 'delete':
            # A中有，B中无：A显示红
            seg_a = " ".join(parts_a[a0:a1])
            out_a.append(f"{Colors.RED}{seg_a}{Colors.RESET}")
        elif opcode == 'insert':
            # A中无，B中有：B显示绿
            seg_b = " ".join(parts_b[b0:b1])
            out_b.append(f"{Colors.GREEN}{seg_b}{Colors.RESET}")
            
    return " ".join(out_a), " ".join(out_b)

def process_measure_diff(measure, lines_a, lines_b):
    """
    处理单个小节的差异。
    1. 移除完全相同的行。
    2. 对剩下的行进行相似度匹配，找出“修改”的行。
    3. 剩下的视为纯粹的“删除”或“新增”。
    """
    # 1. 找出完全匹配的行并剔除
    # 为了处理重复行，使用列表移除
    unmatched_a = lines_a[:]
    unmatched_b = lines_b[:]
    
    # 简单的完全匹配剔除
    i = 0
    while i < len(unmatched_a):
        found = False
        for j, note_b in enumerate(unmatched_b):
            if unmatched_a[i].fingerprint == note_b.fingerprint:
                unmatched_b.pop(j)
                found = True
                break
        if found:
            unmatched_a.pop(i)
        else:
            i += 1
            
    if not unmatched_a and not unmatched_b:
        return False, [] # 无差异

    diff_outputs = []

    # 2. 尝试在剩余的 A 和 B 中寻找最佳配对 (视为修改)
    # 使用 difflib 计算行之间的相似度
    # 贪心算法：每次找最相似的一对
    while unmatched_a and unmatched_b:
        best_ratio = 0
        best_pair_idx = (-1, -1) # (index_in_a, index_in_b)
        
        for idx_a, note_a in enumerate(unmatched_a):
            for idx_b, note_b in enumerate(unmatched_b):
                # 计算相似度 (基于token列表)
                ratio = difflib.SequenceMatcher(None, note_a.parts, note_b.parts).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_pair_idx = (idx_a, idx_b)
        
        # 阈值判定：如果相似度太低（比如小于 0.6），则不认为是修改，而是独立的增/删
        # 但ma2每一行结构很像，通常相似度都很高。
        # 我们这里设定一个宽松的阈值，只要第一列(类型)相同，往往就是同一条Note的修改
        
        idx_a, idx_b = best_pair_idx
        is_modification = False
        
        if idx_a != -1:
            # 额外规则：如果 Note 类型 (第一列) 都不一样，那肯定不是修改
            if unmatched_a[idx_a].parts[0] == unmatched_b[idx_b].parts[0]:
                is_modification = True
            elif best_ratio > 0.6:
                is_modification = True

        if is_modification:
            note_a = unmatched_a.pop(idx_a)
            note_b = unmatched_b.pop(idx_b)
            
            str_a, str_b = highlight_diff_words(note_a.parts, note_b.parts)
            
            # 格式化输出
            diff_outputs.append(f"{Colors.GREY}[MOD]{Colors.RESET} 行 {note_a.line_num} -> {note_b.line_num}:")
            diff_outputs.append(f"  - {str_a}")
            diff_outputs.append(f"  + {str_b}")
        else:
            break # 剩下的都不匹配了

    # 3. 处理剩下的孤儿 (纯删除 或 纯新增)
    for note in unmatched_a:
        # 整行标红
        diff_outputs.append(f"{Colors.RED}- [行 {note.line_num}] {note.raw_text}{Colors.RESET}")
    
    for note in unmatched_b:
        # 整行标绿
        diff_outputs.append(f"{Colors.GREEN}+ [行 {note.line_num}] {note.raw_text}{Colors.RESET}")

    # 按照行号简单排个序，让输出看起来顺眼一点
    # 但由于已经分成了配对和非配对，直接输出即可，或者按列表中第一个出现的行号排序
    
    return True, diff_outputs

def sort_key(measure_key):
    try:
        return float(measure_key)
    except ValueError:
        return float('inf')

def main():
    # 命令行参数处理
    if len(sys.argv) == 3:
        file_a_path = sys.argv[1]
        file_b_path = sys.argv[2]
    else:
        print(f"{Colors.CYAN}=== MA2 差异精细对比工具 ==={Colors.RESET}")
        print("用法: python diff_ma2.py <原文件> <新文件>")
        file_a_path = input("请输入【原文件】路径: ").strip().strip('"').strip("'")
        file_b_path = input("请输入【新文件】路径: ").strip().strip('"').strip("'")

    data_a = parse_file(file_a_path)
    data_b = parse_file(file_b_path)

    all_measures = set(data_a.keys()) | set(data_b.keys())
    sorted_measures = sorted(list(all_measures), key=sort_key)

    total_diff_blocks = 0
    
    print(f"\n{Colors.BOLD}开始对比: {os.path.basename(file_a_path)} vs {os.path.basename(file_b_path)}{Colors.RESET}\n")

    for measure in sorted_measures:
        lines_a = data_a.get(measure, [])
        lines_b = data_b.get(measure, [])

        has_diff, output_lines = process_measure_diff(measure, lines_a, lines_b)

        if has_diff:
            total_diff_blocks += 1
            print(f"{Colors.YELLOW}>>> 差异出现在第 {measure} 小节:{Colors.RESET}")
            for line in output_lines:
                print(line)
            print("-" * 40)

    if total_diff_blocks == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}完美匹配！忽略顺序后，内容完全一致。{Colors.RESET}")
    else:
        print(f"\n{Colors.BOLD}对比结束。共发现 {total_diff_blocks} 处小节有差异。{Colors.RESET}")

if __name__ == "__main__":
    main()
