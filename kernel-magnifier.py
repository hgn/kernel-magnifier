#!/usr/bin/env python3

import argparse
import time
import os
import sys
import re
import pygraphviz as pgv
from dataclasses import dataclass
import types
import subprocess
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.ticker import ScalarFormatter
import numpy as np


FTRACE_DIR = "/sys/kernel/tracing/"
RECORD_OUT_FILE = "kernel-magnifier.data"


@dataclass
class FunctionTracerData:
    task_name: str
    pid: str
    cpu: str
    function: str
    parent: str


class Node(object):
    def __init__(self, name, map_db):
        self.name = name
        self.filepath = None
        if map_db and name in map_db.symbol:
            self.filepath = map_db.symbol[name]


    def label(self, executed=0):
        if self.filepath:
            return f"{self.name}()\n{self.filepath}\nExecuted: {executed}"
        return f"{self.name}()\nExecuted: {executed}"

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.name == other.name
        return False

    def __hash__(self):
        return hash(self.name)


class Edge(object):
    def __init__(self):
        self.calls = 0

    def update(self):
        self.calls += 1


class Network(object):
    def __init__(self):
        self.adjacency = dict()
        self.clusters = list()
        self.calls_max = 0
        self.node_calls = dict()
        self.executed_max = 0

    def add(self, calling_function_name, called_function_name, map_db):
        calling_node = Node(calling_function_name, map_db)
        if not calling_node in self.adjacency:
            self.adjacency[calling_node] = dict()
        called_node = Node(called_function_name, map_db)
        if called_node not in self.adjacency[calling_node]:
            self.adjacency[calling_node][called_node] = Edge()
        self.adjacency[calling_node][called_node].update()
        if self.adjacency[calling_node][called_node].calls > self.calls_max:
            self.calls_max = self.adjacency[calling_node][called_node].calls
        self._update_call_graph_cluster(calling_function_name, called_function_name)

        # statistics stuff
        if called_function_name not in self.node_calls:
            self.node_calls[called_function_name] = 0
        self.node_calls[called_function_name] += 1
        if self.node_calls[called_function_name] > self.executed_max:
            self.executed_max = self.node_calls[called_function_name]

    def executed_no(self, function_name):
        if function_name not in self.node_calls:
            return 0
        return self.node_calls[function_name]


    def is_filepath_filtered(self, args, node):
        # if true, the node is NOT shown
        if args.filter_filepath and not node.filepath:
            return True
        if not args.filter_filepath or not node.filepath:
            return False
        for filter_filepath in args.filter_filepath:
            if filter_filepath in node.filepath:
                return False

        return True


    def nodes(self, args, filter_calls=0):
        nodes = set()
        for caller_node, caller_data in self.adjacency.items():
            for called_node, edge in caller_data.items():
                if edge.calls <= filter_calls:
                    continue
                if self.is_filepath_filtered(args, caller_node):
                    continue
                if self.is_filepath_filtered(args, called_node):
                    continue
                nodes.add(caller_node)
                nodes.add(called_node)
        for node in nodes:
            yield node


    def calls(self, args, filter_calls=0):
        for caller_node, caller_data in self.adjacency.items():
            for called_node, edge in caller_data.items():
                if edge.calls <= filter_calls:
                    continue
                if self.is_filepath_filtered(args, caller_node) and self.is_filepath_filtered(args, called_node):
                    continue
                yield caller_node, called_node, edge


    def _update_call_graph_cluster(self, calling_function_name, called_function_name):
        found = False
        for cluster in self.clusters:
            if calling_function_name in cluster or called_function_name in cluster:
                cluster.add(calling_function_name)
                cluster.add(called_function_name)
                found = True
        if not found:
            self.clusters.append(set([calling_function_name, called_function_name]))

GDB = Network()

def get_file_size(file_path):
    try:
        return os.path.getsize(file_path)
    except FileNotFoundError:
        return -1

def convert_size(size_in_bytes):
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KiB"
    elif size_in_bytes < 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024):.2f} MiB"
    else:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} GiB"

def graph_function_call_frequency2(args):
    data = []
    for node in GDB.nodes(args, filter_calls=args.filter_execution_no):
        cumulative_called = GDB.executed_no(node.name)
        data.append([node.name, cumulative_called])
    sorted_data = sorted(data, key=lambda x: x[1], reverse=True)
    names, occurrences = zip(*sorted_data)
    limit = 35
    names = names[:limit]
    values = occurrences[:limit]

    plt.rcParams.update({'font.size': 4})
    fig, ax = plt.subplots()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(which='major', linestyle='-', linewidth='0.5', color='black')
    ax.xaxis.grid(which='minor', linestyle=':', linewidth='0.5', color='black')
    ax.set_axisbelow(True)
    ax.ticklabel_format(style='plain')

    num_bars = len(names)
    colors = plt.cm.plasma(np.linspace(0.1, 0.9, num_bars))
    ax.barh(names, values, color=colors)
    ax.invert_yaxis()
    ax.set_xscale('log')

    ax.get_xaxis().get_major_formatter().labelOnlyBase = False
    ax.xaxis.set_minor_formatter(ticker.FormatStrFormatter('%d'))

    ax.set_ylabel("Function Names")
    ax.set_xlabel("Calls")

    plt.tight_layout()
    filename = "function-calls.png"
    print(f"{filename} generated")
    plt.savefig("function-calls.png", dpi=600, bbox_inches="tight")
    plt.close()

def graph_function_call_frequency(args):
    data = []
    for node in GDB.nodes(args, filter_calls=args.filter_execution_no):
        cumulative_called = GDB.executed_no(node.name)
        data.append([node.name, cumulative_called])
    sorted_data = sorted(data, key=lambda x: x[1], reverse=True)
    names, occurrences = zip(*sorted_data)
    limit = 30
    names = names[:limit]
    occurrences = occurrences[:limit]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(which='major', linestyle='-', linewidth='0.5', color='black')
    ax.yaxis.grid(which='minor', linestyle=':', linewidth='0.5', color='black')
    ax.set_axisbelow(True)
    ax.ticklabel_format(style='plain')

    num_bars = len(names)
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, num_bars))

    ax.bar(names, occurrences, color=colors)
    ax.set_yscale('log')

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    ax.get_yaxis().get_major_formatter().labelOnlyBase = False
    ax.yaxis.set_minor_formatter(ticker.FormatStrFormatter('%d'))

    ax.set_xlabel("Function Names")
    ax.set_ylabel("Calls")

    ax.set_xticks(ax.get_xticks(), ax.get_xticklabels(), ha='right', rotation=45, rotation_mode='anchor')

    plt.tight_layout()
    filename = "kernel-function-calls-sorted.png"
    print(f"{filename} generated")
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()


def make_file_world_readable(file_path):
    try:
        current_permissions = os.stat(file_path).st_mode
        new_permissions = current_permissions | 0o444
        os.chmod(file_path, new_permissions)
    except FileNotFoundError:
        print(f"The file '{file_path}' does not exist.")
    except PermissionError:
        print(f"You don't have permission to change the file permissions.")


def tracing_enable(args):
    env = types.SimpleNamespace()

    # Check if the ftrace directory exists
    if not os.path.exists(FTRACE_DIR):
        print(
            "ftrace directory not found. Make sure you have enabled CONFIG_FTRACE in your kernel."
        )
        return None

    # we are not interessted in timekeeping, lower the overhead by using
    # a counter
    with open(os.path.join(FTRACE_DIR, "trace_clock"), "w") as fd:
        fd.write("counter")

    with open(os.path.join(FTRACE_DIR, "current_tracer"), "w") as fd:
        fd.write("function")

    with open(os.path.join(FTRACE_DIR, "buffer_size_kb"), "r") as fd:
        buffer_size = int(fd.read()) * 1024
        env.buffer_size = buffer_size

    if args.cpumask:
        with open(os.path.join(FTRACE_DIR, "tracing_cpumask"), "w") as fd:
            print(f"Limit recording to CPU mask {args.cpumask}")
            fd.write(args.cpumask)

    with open(os.path.join(FTRACE_DIR, "tracing_on"), "w") as fd:
        fd.write("1")

    return env


def tracing_disable():
    with open(os.path.join(FTRACE_DIR, "tracing_on"), "w") as fd:
        fd.write("0")

    with open(os.path.join(FTRACE_DIR, "current_tracer"), "w") as fd:
        fd.write("nop")

    with open(os.path.join(FTRACE_DIR, "trace_clock"), "w") as fd:
        fd.write("local")

    with open(os.path.join(FTRACE_DIR, "tracing_cpumask"), "w") as fd:
        fd.write("0")


def record_data(env, record_time):
    pipe_path = os.path.join(FTRACE_DIR, "trace_pipe")

    # Check if trace_pipe exists
    if not os.path.exists(pipe_path):
        print("trace_pipe not found. Make sure the Linux kernel tracing is enabled.")
        sys.exit(1)

    # Open the trace_pipe for reading
    with open(pipe_path, "rb") as trace_pipe:
        try:
            with open(RECORD_OUT_FILE, "wb") as output:
                start_time = time.time()
                if record_time:
                    end_time = start_time + record_time
                else:
                    end_time = float("inf")

                while time.time() < end_time:
                    data = trace_pipe.read(env.buffer_size)
                    if data:
                        output.write(data)

        except KeyboardInterrupt:
            print("Recording interrupted by the user.")
        except Exception as e:
            print(f"Error: {e}")
    print(f"Wrote data to {RECORD_OUT_FILE}")
    make_file_world_readable(RECORD_OUT_FILE)
    print(f"Record filesize: {convert_size(get_file_size(RECORD_OUT_FILE))}")



def record(args):
    print(f"Record mode - now starting recording traces for {args.record_time} seconds")
    env = tracing_enable(args)
    record_data(env, args.record_time)
    tracing_disable()
    return 0


def parse_lost_event_lines(line):
    # parse for "CPU:2 [LOST 1305 EVENTS]"
    m = re.search(r".*LOST\W+(\d+)\W+EVENTS", line)
    if m:
        return int(m.group(1))
    return None


RE_FTRACE_LINE = re.compile(r"(.*)-(\d+)\s+\[(\d+)\]\s+\S+\s+\S+\s+(\S+)\s+<-(\S+)")


def chunk_ftrace_dataline(line):
    # kworker/u64:1-145123  [000] d..3.   1207319054: preempt_count_sub <- foobar
    match = RE_FTRACE_LINE.match(line)
    if not match:
        raise Exception()
    task_name = match.group(1)
    pid = match.group(2)
    cpu = match.group(3)
    function = match.group(4)
    parent = match.group(5)
    return FunctionTracerData(task_name, pid, cpu, function, parent)


def parse_ftrace_line(line):
    try:
        func_tracer_data = chunk_ftrace_dataline(line)
        return func_tracer_data, None
    except Exception as e:
        pass
    missed_events = parse_lost_event_lines(line)
    if missed_events is None:
        print(f"unexpected line: {line}, ignoreing it")
        return None, None
    return None, missed_events


def visualize_def_normalize_penwidth(value, max_value):
    if value <= 0:
        return 1
    elif value >= max_value:
        return 5
    else:
        return int(1.0 + (value / max_value) * 4.0)


def normalize_to_color(value, max_value):
    if value <= 0:
        return "#D3D3D3"  # Minimum value, mapped to gray (#808080)
    elif value >= max_value:
        return "#FF0000"  # Maximum value, mapped to red (#FF0000)
    else:
        # Linear interpolation between gray and red
        r = int(211 + (44 * (value / max_value)))
        g = 211
        b = 211
        return "#{:02X}{:02X}{:02X}".format(r, g, b)


def visualize_data(args):
    g = pgv.AGraph(
        strict=True,
        directed=True,
        ranksep="1.0",
        page="18,11",
        ratio="fill",
        center="1",
    )
    g.node_attr["fontname"] = "Helvetica,Arial,sans-serif"
    g.node_attr["style"] = "filled"
    g.node_attr["fillcolor"] = "#f8f8f8"
    g.edge_attr["fontname"] = "Helvetica,Arial,sans-serif"

    for node in GDB.nodes(args, filter_calls=args.filter_execution_no):
        cumulative_called = GDB.executed_no(node.name)
        fillcolor = normalize_to_color(cumulative_called, GDB.executed_max)
        label = f" {node.label(executed=cumulative_called)}"
        g.add_node(node.name, label=label, shape="box", fillcolor=fillcolor)

    for caller_name, called_name, edge in GDB.calls(args, filter_calls=args.filter_execution_no):
        penwidth = visualize_def_normalize_penwidth(edge.calls, GDB.calls_max)
        g.add_edge(
            caller_name.name,
            called_name.name,
            label=f"{edge.calls}",
            penwidth=penwidth,
            weight=edge.calls,
        )

    g.draw(args.image_name, prog="dot")
    print(f"{args.image_name} generated")


no_missed_events = 0
no_events = 0
unparseable_ftrace_lines = []


def parse_data(map_db):
    global no_missed_events, unparseable_ftrace_lines, no_events
    try:
        with open(RECORD_OUT_FILE, "r") as file:
            for line in file:
                data, missed_events = parse_ftrace_line(line.strip())
                if missed_events:
                    no_missed_events += missed_events
                    continue
                if not data:
                    continue
                if not data and not missed_events:
                    unparseable_ftrace_lines.add(line)
                    continue
                no_events += 1
                GDB.add(data.parent, data.function, map_db)

    except FileNotFoundError:
        print(f"The file '{file_path}' does not exist.")
    except PermissionError:
        print(f"You don't have permission to read the file.")
    except Exception as e:
        print(f"An error occurred: {e}")


def load_symbol_filepath_map(args):
    map_db = types.SimpleNamespace()
    map_db.symbol = dict()
    if not os.path.exists(args.symbol_file_path):
        return None
    if os.path.getsize(args.symbol_file_path) <= 0:
        return None
    with open(args.symbol_file_path, 'r') as file:
        for line in file:
            symbol, filepath = line.strip().split("|")
            map_db.symbol[symbol] = filepath
    return map_db


def visualize(args):
    print("Visualization mode - now generating visualization...")
    map_db = load_symbol_filepath_map(args)
    parse_data(map_db)
    percent_lost = (no_missed_events / (no_missed_events + no_events)) * 100
    print(f"parsing completed, found {no_events} events")
    print(
        f"{no_missed_events} events missed during capturing process ({percent_lost:.2f}%)"
    )
    graph_function_call_frequency(args)
    visualize_data(args)
    return 0


def execute_command_incremental(command):
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for line in process.stdout:
            yield line.strip()

        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    except subprocess.CalledProcessError as e:
        print(f"Command \"{command}\" failed with return code {e.returncode}")
        print(f"Error output: {e.stderr}")
        return None

def mapping_sanitize_path(map_db):
    limit = 200
    analized = map_db[:200]
    paths = [item[1] for item  in analized]
    common_path = os.path.commonpath(paths)
    modified_tuple_list = [(symbol, path[len(common_path):]) for symbol, path in map_db]
    return modified_tuple_list

def gen_mapping_db(args):
    command = f"dwarfdump {args.debug_kernel_path}"
    sym_name = sym_file = None
    map_db = []
    for line in execute_command_incremental(command):
        if "DW_AT_name" in line:
            atoms = line.split()
            if len(atoms) != 2:
                continue
            sym_name = atoms[1]
        if "DW_AT_decl_file" in line:
            atoms = line.split()
            if len(atoms) != 3:
                continue
            sym_file = atoms[2]
            if sym_name:
                map_db.append([sym_name,sym_file])
                sym_name = sym_file = None
    map_db = mapping_sanitize_path(map_db)
    filename = "symbol-filepath.map"
    with open(filename, "w") as fd:
        for entry in map_db:
            fd.write(f"{entry[0]}|{entry[1]}\n")
    print(f"wrote mapping table to {filename}")

def uname_r():
    try:
        return subprocess.check_output(['uname', '-r'], universal_newlines=True).strip()
    except subprocess.CalledProcessError as e:
        print("Error:", e)

def parse_command_line_args():
    parser = argparse.ArgumentParser(
        description="Parse two arguments like git subcommand style"
    )
    subparsers = parser.add_subparsers(title="Subcommands", dest="subcommand")

    # record
    parser_record = subparsers.add_parser("record", help="")
    parser_record.add_argument(
        "--record-time",
        type=float,
        default=10.0,
        help="time to record live data (default: %(default)s)",
    )
    parser_record.add_argument(
        "--cpumask", type=str, default=None, help="cpumask, not hex, e.g. 0"
    )

    # visualize
    parser_visualize = subparsers.add_parser("visualize", help="")
    parser_visualize.add_argument(
        "--debug-kernel-path", help="often /usr/lib/debug/boot/vmlinux-$(uname -r)"
    )
    parser_visualize.add_argument(
        "--image-name",
        type=str,
        default="kernel-magnifier.pdf",
        help="foo.pdf, foo.png, ... (default: %(default)s)",
    )
    parser_visualize.add_argument(
            "--filter-execution-no",
        type=int,
        default="0",
        help="show only called functions when called over n (default: %(default)s)",
    )
    parser_visualize.add_argument(
        "--symbol-file-path",
        type=str,
        default="symbol-filepath.map",
        help="path to symbol-filepath.map (default: %(default)s)",
    )
    parser_visualize.add_argument(
        "--filter-filepath",
        type=str,
        default=None,
        help="filter functions based on locations, can be a list; e.g kernel/sched,net",
    )

    # generate-symbol-map
    parser_symbol_generator = subparsers.add_parser("generate-symbol-map",
            help="generated symbol-filename mapping file")
    parser_symbol_generator.add_argument(
        "-k",
        "--debug-kernel-path",
        type=str,
        default=f"/usr/lib/debug/boot/vmlinux-{uname_r()}",
        help="path to uncompressed, kernel with debug symbols (default: %(default)s)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_command_line_args()
    if args.subcommand == "record":
        sys.exit(record(args))
    elif args.subcommand == "visualize":
        if args.filter_filepath:
            # convert into filter array
            args.filter_filepath = args.filter_filepath.split(",")
        sys.exit(visualize(args))
    elif args.subcommand == "generate-symbol-map":
        gen_mapping_db(args)
    else:
        print("Please specify a subcommand (e.g., record, visualize or generate-symbol-map).")
        sys.exit(1)
