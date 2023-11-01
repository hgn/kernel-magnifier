#!/usr/bin/env python3

import argparse
import time
import os
import sys
import re
import pygraphviz as pgv
from dataclasses import dataclass
import types

ftrace_dir = "/sys/kernel/tracing/"
output_file = "ftrace-callgrapher.data"


@dataclass
class FunctionTracerData:
    task_name_pid: str
    cpu: str
    stats: str
    timestamp: str
    function: str
    parent: str

class Node(object):
    def __init__(self, name):
        self.name = name

    def label(self, executed=0):
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

    def add(self, calling_function_name, called_function_name):
        calling_node = Node(calling_function_name)
        if not calling_node in self.adjacency:
            self.adjacency[calling_node] = dict()
        called_node = Node(called_function_name)
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


    def nodes(self, filter_calls=0):
        nodes = set()
        for caller_node, caller_data in self.adjacency.items():
            for called_node, edge in caller_data.items():
                if edge.calls > filter_calls:
                    nodes.add(caller_node)
                    nodes.add(called_node)
        for node in nodes:
            yield node

    def calls(self, filter_calls=0):
        for caller_node, caller_data in self.adjacency.items():
            for called_node, edge in caller_data.items():
                if edge.calls > filter_calls:
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
        

graph_db = Network()


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
    if not os.path.exists(ftrace_dir):
        print("ftrace directory not found. Make sure you have enabled CONFIG_FTRACE in your kernel.")
        return None

    # we are not interessted in timekeeping, lower the overhead by using
    # a counter
    with open(os.path.join(ftrace_dir, "trace_clock"), "w") as fd:
        fd.write("counter")

    with open(os.path.join(ftrace_dir, "current_tracer"), "w") as fd:
        fd.write("function")

    with open(os.path.join(ftrace_dir, "buffer_size_kb"), "r") as fd:
        buffer_size = int(fd.read()) * 1024
        env.buffer_size = buffer_size

    if args.cpumask:
        with open(os.path.join(ftrace_dir, "tracing_cpumask"), "w") as fd:
            print(args.cpumask)
            fd.write(args.cpumask)

    with open(os.path.join(ftrace_dir, "tracing_on"), "w") as fd:
        fd.write("1")

    return env


def tracing_disable():
    with open(os.path.join(ftrace_dir, "tracing_on"), "w") as fd:
        fd.write("0")

    with open(os.path.join(ftrace_dir, "current_tracer"), "w") as fd:
        fd.write("nop")

    with open(os.path.join(ftrace_dir, "trace_clock"), "w") as fd:
        fd.write("local")

    with open(os.path.join(ftrace_dir, "tracing_cpumask"), "w") as fd:
        fd.write("0")

def record_data(env, capture_time=10):
    pipe_path = os.path.join(ftrace_dir, "trace_pipe")

    # Check if trace_pipe exists
    if not os.path.exists(pipe_path):
        print("trace_pipe not found. Make sure the Linux kernel tracing is enabled.")
        sys.exit(1)

    # Open the trace_pipe for reading
    with open(pipe_path, "rb") as trace_pipe:
        try:
            with open(output_file, "wb") as output:
                start_time = time.time()

                if capture_time:
                    end_time = start_time + capture_time
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
    print(f"wrote data to {output_file}")
    make_file_world_readable(output_file)

def record(args):
    print(f"Record mode is enabled. Start recording data for {args.capture_time} seconds")
    env = tracing_enable(args)
    record_data(env, capture_time=args.capture_time)
    tracing_disable()


def parse_lost_event_lines(line):
    # parse for "CPU:2 [LOST 1305 EVENTS]"
    m = re.search(r".*LOST\W+(\d+)\W+EVENTS", line)
    if m:
        return int(m.group(1))
    return None

def parse_ftrace_line(line):
    try:
        remain, parent = line.split("<-")
        splits = remain.split()
        function = splits[-1]
        if splits[-2].endswith(":"):
            splits[-2] = splits[-2][:-1]
        timestamp, stats, cpu = splits[-2], splits[-3], splits[-4]
        task_name_pid, cpu, stats, timestamp, function = remain.split()
        func_tracer_data = FunctionTracerData(task_name_pid, cpu, stats, timestamp, function, parent)
        return func_tracer_data, None
    except Exception as e:
        pass
    missed_events = parse_lost_event_lines(line)
    if missed_events is None:
        return None, None
    return None, missed_events


db = dict()
db_parent_calls = dict()

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
    g = pgv.AGraph(strict=True, directed=True, ranksep="1.0", page="18,11",ratio="fill",center="1")
    g.node_attr['fontname'] = "Helvetica,Arial,sans-serif"
    g.node_attr['style'] = "filled"
    g.node_attr['fillcolor'] = "#f8f8f8"
    g.edge_attr['fontname'] = "Helvetica,Arial,sans-serif"

    for node in graph_db.nodes(filter_calls=10):
        cumulative_called = graph_db.executed_no(node.name)
        fillcolor = normalize_to_color(cumulative_called, graph_db.executed_max)
        label = f" {node.label(executed=cumulative_called)}"
        g.add_node(node.name, label=label, shape="box", fillcolor=fillcolor)

    for caller_name, called_name, edge in graph_db.calls(filter_calls=10):
        penwidth = visualize_def_normalize_penwidth(edge.calls, graph_db.calls_max)
        g.add_edge(caller_name.name, called_name.name, label=f"{edge.calls}", penwidth=penwidth, weight=edge.calls)

    g.draw(args.image_name, prog="dot")


no_missed_events = 0
no_events = 0
unparseable_ftrace_lines = []

def parse_data():
    global no_missed_events, unparseable_ftrace_lines, no_events
    try:
        with open(output_file, "r") as file:
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
                graph_db.add(data.parent, data.function)

    except FileNotFoundError:
        print(f"The file '{file_path}' does not exist.")
    except PermissionError:
        print(f"You don't have permission to read the file.")
    except Exception as e:
        print(f"An error occurred: {e}")


def visualize(args):
    print("Visualizion mode - now generating visualization...")
    parse_data()
    percent_lost = (no_missed_events / (no_missed_events + no_events)) * 100
    print(f"parsing completed, found {no_events} events")
    print(f"{no_missed_events} events missed during capturing process ({percent_lost:.2f}%)")
    visualize_data(args)


import subprocess


def execute_command_incremental(command):
    try:
        # Run the command and capture both standard output and standard error
        process = subprocess.Popen(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        for line in process.stdout:
            yield line.strip()

        return_code = process.wait()

        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}")
        print(f"Error output: {e.stderr}")
        return None



def gen_mapping_db(args):
    command = f"dwarfdump {args.debug_kernel_path}"
    sym_name = sym_file = None
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
                print(f"{sym_name} {sym_file}")
                sym_name = sym_file = None


def parse_command_line_args():
    parser = argparse.ArgumentParser(description='Parse two arguments like git subcommand style')
    subparsers = parser.add_subparsers(title="Subcommands", dest="subcommand")

    subcommand1_parser = subparsers.add_parser("record", help="")
    subcommand1_parser.add_argument("--capture-time", type=float, default=10.0)
    subcommand1_parser.add_argument("--cpumask", type=str, default=None, help="cpumask, not hex, e.g. 0")

    subcommand2_parser = subparsers.add_parser("visualize", help="")
    subcommand2_parser.add_argument("--debug-kernel-path", help="often /usr/lib/debug/boot/vmlinux-$(uname -r)")
    subcommand1_parser.add_argument("--image-name", type=str, default="ftrace-callgrapher.pdf", help="foo.pdf, foo.png, ...")

    subcommand2_parser = subparsers.add_parser("generate-mapping-db", help="")
    subcommand2_parser.add_argument("--debug-kernel-path", help="often /usr/lib/debug/boot/vmlinux-$(uname -r)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_command_line_args()

    if args.subcommand == "record":
        record(args)
    elif args.subcommand == "visualize":
        visualize(args)
    elif args.subcommand == "generate-mapping-db":
        gen_mapping_db(args)
    else:
        print("Please specify a subcommand (e.g., record or visualize).")
