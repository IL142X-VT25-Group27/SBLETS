"""
Utility functions for data fetching, parsing, and visualization in Jupyter Notebooks.

This module provides tools for interacting with APIs, parsing log and
histogram data, and generating various plots.
"""

import json
import struct
import matplotlib
matplotlib.use('Agg')  # Prevent GUI backend and suppress warnings
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import re
import requests
import seaborn as sns
import base64
import io
from collections import defaultdict

def parse_histogram(hex_data):
    if not hex_data:
        return None, None

    offset = 0
    data = hex_data.replace(" ", "")

    try:
        hg_type = int(data[offset:offset+2], 16)
        offset += 2
        hg_version = int(data[offset:offset+2], 16)
        offset += 2
        hg_float_start = struct.unpack('!f', bytes.fromhex(data[offset:offset+8]))[0]
        offset += 8
        hg_float_width = struct.unpack('!f', bytes.fromhex(data[offset:offset+8]))[0]
        offset += 8
        hg_num_intervals = int(data[offset:offset+4], 16)
        offset += 4
        hg_interval_data_type = int(data[offset:offset+4], 16)
        offset += 4
        hg_value_unit = int(data[offset:offset+4], 16)
        offset += 4
        hg_float_scale_factor = struct.unpack('!f', bytes.fromhex(data[offset:offset+8]))[0]
        offset += 8

        values = []
        intervals = []

        for i in range(hg_num_intervals):
            interval_value = struct.unpack('!f', bytes.fromhex(data[offset:offset+8]))[0]
            start = hg_float_start + (hg_float_width * i)
            intervals.append(f'{start:.2f}')
            value_int_ms = int(interval_value * hg_float_scale_factor)
            values.append(value_int_ms)
            offset += 8

        return intervals, values

    except (ValueError, struct.error):
        return None, None


def parse_log_time_per_speed(log_file_path):
    step = (100 / 60)
    ref = np.round(np.arange(0, 300, step), 2)
    log_time_per_speed = dict.fromkeys(ref, 0.0)

    info_pattern = re.compile(r'revspeed:\s*([0-9.]+),.*?accumulated_time:\s*(\d+)')
    recv_pattern = re.compile(r'"accumulated_time":\s*(\d+)')

    with open(log_file_path, 'r') as f:
        lines = f.readlines()

    revspeed_time_pairs = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'INFO:control' in line:
            info_match = info_pattern.search(line)
            if info_match:
                revspeed = float(info_match.group(1))
                for j in range(i + 1, len(lines)):
                    recv_match = recv_pattern.search(lines[j])
                    if recv_match:
                        time = int(recv_match.group(1))
                        revspeed_time_pairs.append((revspeed, time))
                        break
        i += 1

    def round_to_nearest(val):
        idx = np.abs(ref - val).argmin()
        return ref[idx]

    if len(revspeed_time_pairs) == 1:
        raw_revspeed, curr_time = revspeed_time_pairs[0]
        binned_revspeed = round_to_nearest(raw_revspeed)
        log_time_per_speed[binned_revspeed] += curr_time / 1e6
    else:
        for i in range(len(revspeed_time_pairs) - 1):
            raw_revspeed, curr_time = revspeed_time_pairs[i]
            next_time = revspeed_time_pairs[i + 1][1]
            delta = (next_time - curr_time) / 1e6
            binned_revspeed = round_to_nearest(raw_revspeed)
            log_time_per_speed[binned_revspeed] += delta

        raw_revspeed, last_time = revspeed_time_pairs[-1]
        prev_time = revspeed_time_pairs[-2][1]
        delta = (last_time - prev_time) / 1e6
        binned_revspeed = round_to_nearest(raw_revspeed)
        log_time_per_speed[binned_revspeed] += delta

    revspeeds = np.array(list(log_time_per_speed.keys()))
    times = np.array(list(log_time_per_speed.values()))

    return revspeeds, times


### Plotting functions ###

def plot_bar_red(log_speeds, log_times):
    fig = plt.figure(figsize=(14, 8))
    plt.bar(np.array(log_speeds, dtype=float) + 1, log_times, width=2,
            color='red', alpha=0.6, label='Simulation Data')
    plt.xlabel('Engine Revolution (Hz)')
    plt.xlim(0, 300)
    plt.ylabel('Time (s)')
    plt.title('Bar Plot: Engine Revolution vs Time')
    plt.grid(True, axis='y')
    plt.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def plot_bar_blue(intervals, values):
    fig = plt.figure(figsize=(14, 8))
    plt.bar(np.array(intervals, dtype=float) - 1, values,
            width=2, color='skyblue', label='Captured Data')
    plt.xlabel('Engine Revolution (Hz)')
    plt.xlim(0, 300)
    plt.ylabel('Time (s)')
    plt.title('Bar Plot: Engine Revolution vs Time')
    plt.grid(True, axis='y')
    plt.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def plot_bar(intervals, values, log_speeds, log_times):
    # Convert and validate data
    try:
        x1 = np.array(intervals, dtype=float) - 1
        y1 = np.array(values, dtype=float)
        x2 = np.array(log_speeds, dtype=float) + 1
        y2 = np.array(log_times, dtype=float)
    except (ValueError, OverflowError, TypeError) as e:
        print(f"Data conversion error: {e}")
        return ""

    # Filter out problematic entries
    mask = np.isfinite(x1) & np.isfinite(y1)
    x1, y1 = x1[mask], y1[mask]

    mask2 = np.isfinite(x2) & np.isfinite(y2)
    x2, y2 = x2[mask2], y2[mask2]

    fig = plt.figure(figsize=(14, 8))
    plt.bar(x1, y1, width=2, color='skyblue', label='Captured Data')
    plt.bar(x2, y2, width=2, color='red', alpha=0.6, label='Simulation Data')

    plt.xlabel('Engine Revolution (Hz)')
    plt.ylabel('Time (s)')
    plt.title('Bar Plot: Engine Revolution vs Time')
    plt.xlim(0, 300)
    plt.grid(True, axis='y')
    plt.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def plot_scatter(intervals, values, log_speeds, log_times):
    fig = plt.figure(figsize=(14, 8))
    plt.scatter(np.array(intervals, dtype=float), values,
                label='Captured Data', color='skyblue')
    plt.scatter(np.array(log_speeds, dtype=float), log_times,
                label='Simulation Data', color='red', alpha=0.6)
    plt.xlabel('Engine Revolution (Hz)')
    plt.xlim(0, 300)
    plt.ylabel('Time (s)')
    plt.title('Scatter Plot: Engine Revolution vs Time')
    plt.grid(True)
    plt.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def plot_step(revspeed1, time1, revspeed2, time2):
    revspeed1 = np.array(revspeed1, dtype=float)
    revspeed2 = np.array(revspeed2, dtype=float)
    time1 = np.array(time1, dtype=float)
    time2 = np.array(time2, dtype=float)

    def build_steps(rs, ts):
        x, y = [], []
        t = 0
        for speed, dur in zip(rs, ts):
            if dur > 0:
                x.extend([t, t + dur])
                y.extend([speed, speed])
                t += dur
        return x, y, t

    fig = plt.figure(figsize=(14, 8))
    x1, y1, end1 = build_steps(revspeed1, time1)
    x2, y2, end2 = build_steps(revspeed2, time2)

    if x1:
        plt.step(x1, y1, where='post', label='Captured Data', color='skyblue')
    if x2:
        plt.step(x2, y2, where='post', linestyle='--', label='Simulated Data', color='red')

    total_duration = max(end1, end2)
    max_speed = max([*revspeed1, *revspeed2, 0.0]) + 10

    plt.xlim(0, total_duration)
    plt.ylim(0, max_speed)
    plt.xlabel('Time (seconds)')
    plt.ylabel('Rev-speed')
    plt.title('Rev-speed Over Time (Step)')
    plt.grid(True)
    plt.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def plot_heatmap(rev1, time1, rev2, time2):
    rev1 = np.array(rev1, dtype=float)
    rev2 = np.array(rev2, dtype=float)
    time1 = np.array(time1, dtype=float)
    time2 = np.array(time2, dtype=float)

    time_dict1 = {float(r): t for r, t in zip(rev1, time1) if t > 0}
    time_dict2 = {float(r): t for r, t in zip(rev2, time2) if t > 0}
    all_revs = sorted(set(time_dict1.keys()).union(time_dict2.keys()))
    time_diffs = [time_dict1.get(r, 0) - time_dict2.get(r, 0) for r in all_revs]

    fig = plt.figure(figsize=(12, 8))
    sns.heatmap([time_diffs], cmap="coolwarm", annot=True, fmt=".1f",
                xticklabels=all_revs, cbar_kws={'label': 'Duration Difference (s)'})
    plt.xlabel("Rev-speed (Hz)")
    plt.yticks([], [])
    plt.title("Heatmap")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')
