import psutil
import curses
import time
import argparse
import shutil
import platform
import os
import sys

VERSION = "OmniHUD v1.0 Final Polished"

def load_waifu_ascii(filename):
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.replace('\t', '    ').replace('\r', '') for line in f.readlines()]
            return lines
    except:
        return ["(×_×) Failed to load waifu..."]

def make_bar(percentage, total_width):
    bar_length = max(10, total_width - 50)
    filled_length = int(bar_length * percentage / 100)
    return "[" + "█" * filled_length + "-" * (bar_length - filled_length) + f"] {percentage:.1f}%"

def get_disk_usage(drive_letter):
    if platform.system() == "Windows":
        path = f"{drive_letter}:/"
    else:
        path = "/" if drive_letter.upper() == "C" else "/home"
    try:
        usage = shutil.disk_usage(path)
        used = usage.used / (1024**3)
        total = usage.total / (1024**3)
        percent = (used / total) * 100
        return f"{used:.0f}GB / {total:.0f}GB ({percent:.1f}%)"
    except:
        return "N/A"

def draw_omnihud(stdscr, waifu_file):
    curses.curs_set(0)
    stdscr.nodelay(True)

    waifu_lines = load_waifu_ascii(waifu_file)

    prev_disk = psutil.disk_io_counters()
    prev_net = psutil.net_io_counters()
    prev_time = time.time()

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        if width < 60 or height < 35:
            msg = "Terminal too small. Resize to at least 80x35 for OmniHUD!"
            stdscr.addstr(0, 0, msg.center(width))
            stdscr.refresh()
            time.sleep(1)
            continue

        waifu_max_lines = max(0, min(len(waifu_lines), height - 25))
        visible_waifu = waifu_lines[:waifu_max_lines]
        offset = waifu_max_lines + 1

        for i, line in enumerate(visible_waifu):
            try:
                stdscr.addstr(i, 2, line.strip()[:width - 4])
            except curses.error:
                pass

        cpu_total = psutil.cpu_percent()
        cpu_per_core = psutil.cpu_percent(percpu=True)
        ram = psutil.virtual_memory()
        curr_disk = psutil.disk_io_counters()
        curr_net = psutil.net_io_counters()
        curr_time = time.time()
        elapsed = max(curr_time - prev_time, 0.1)

        read_mb = (curr_disk.read_bytes - prev_disk.read_bytes) / (1024 * 1024) / elapsed
        write_mb = (curr_disk.write_bytes - prev_disk.write_bytes) / (1024 * 1024) / elapsed
        net_sent_rate = (curr_net.bytes_sent - prev_net.bytes_sent) / (1024 * 1024) / elapsed
        net_recv_rate = (curr_net.bytes_recv - prev_net.bytes_recv) / (1024 * 1024) / elapsed
        net_sent_total = curr_net.bytes_sent / (1024 * 1024 * 1024)
        net_recv_total = curr_net.bytes_recv / (1024 * 1024 * 1024)

        prev_disk, prev_net, prev_time = curr_disk, curr_net, curr_time

        processes = []
        for p in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
            try:
                if p.info['name'] and 'idle' not in p.info['name'].lower():
                    processes.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        top_processes = sorted(processes, key=lambda p: p.info['cpu_percent'], reverse=True)[:3]

        def safe_add(y, content):
            if offset + y < height - 1:
                try:
                    stdscr.addstr(offset + y, 2, content[:width - 4].ljust(width - 4) + " |")
                except curses.error:
                    pass

        def line():
            return "+" + "-" * (width - 4) + "+"

        safe_add(0, line())
        safe_add(1, f"| {VERSION.center(width - 6)} ")
        safe_add(2, line())
        safe_add(3, f"| CPU Total Usage : {make_bar(cpu_total, width)}")

        for i, core_percent in enumerate(cpu_per_core):
            label = f"Core {i:>2}"
            safe_add(4 + i, f"| {label:<17}: {make_bar(core_percent, width)}")

        bar_offset = 4 + len(cpu_per_core)

        used_gb = ram.used / (1024**3)
        total_gb = ram.total / (1024**3)
        ram_bar = make_bar(ram.percent, width)
        ram_line = f"| {'RAM':<17}: {ram_bar} ({used_gb:.1f}GB / {total_gb:.1f}GB)"
        safe_add(bar_offset, ram_line)

        safe_add(bar_offset + 1, f"| Disk Read       : {read_mb:.2f} MB/s")
        safe_add(bar_offset + 2, f"| Disk Write      : {write_mb:.2f} MB/s")
        safe_add(bar_offset + 3, f"| Disk C:         : {get_disk_usage('C')}")
        safe_add(bar_offset + 4, f"| Disk D:         : {get_disk_usage('D')}")
        safe_add(bar_offset + 5, f"| Net Sent Rate   : {net_sent_rate:.2f} MB/s")
        safe_add(bar_offset + 6, f"| Net Recv Rate   : {net_recv_rate:.2f} MB/s")
        safe_add(bar_offset + 7, f"| Net Sent Total  : {net_sent_total:.2f} GB")
        safe_add(bar_offset + 8, f"| Net Recv Total  : {net_recv_total:.2f} GB")
        safe_add(bar_offset + 9, line())
        safe_add(bar_offset + 10, f"| {'Top 3 Processes by CPU'.center(width - 6)} ")
        safe_add(bar_offset + 11, line())

        for idx, proc in enumerate(top_processes):
            try:
                name = proc.info['name'][:15]
                cpu_p = proc.info['cpu_percent']
                mem = proc.info['memory_info'].rss / (1024 * 1024)
                safe_add(bar_offset + 12 + idx, f"| {idx+1}. {name:<15} CPU: {cpu_p:>5.1f}% RAM: {mem:.0f}MB")
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                continue

        safe_add(bar_offset + 16, line())
        quote = "\"Desire is noble. If you already desire it, it means you've walked the first step.\" — Jack"
        safe_add(bar_offset + 17, f"| {quote.center(width - 6)} ")
        safe_add(bar_offset + 18, line())

        stdscr.refresh()
        time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    default_waifu = os.path.join(sys._MEIPASS if getattr(sys, 'frozen', False) else '.', 'waifu.txt')
    parser.add_argument("--waifu", help="Path to waifu ASCII file", default=default_waifu)
    args = parser.parse_args()
    curses.wrapper(draw_omnihud, args.waifu)
